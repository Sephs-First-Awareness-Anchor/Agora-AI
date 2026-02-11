#!/usr/bin/env python3
"""
KO Companion - Main Application
===============================
Authors: Sunni (Sir) Morningstar & Cael Devo

Kivy application managing onboarding and companion screens.
"""

import os
import json
import logging
from pathlib import Path
from datetime import datetime

from kivy.app import App
from kivy.utils import platform
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.properties import ObjectProperty, StringProperty, BooleanProperty

from app.ui.components.theme import ThemeManager, COLOR_THEMES
from app.ui.screens.onboarding import OnboardingScreen
from app.ui.screens.companion import CompanionScreen

# Import core AI modules
from engine.offline_ai_core import OfflineAIFactory, OfflineAI
from engine.offline_ai_expression import OnboardingProfile
from engine.offline_ai_runtime import create_runtime, OfflineAIRuntime

logger = logging.getLogger(__name__)

# Storage paths
def get_storage_path(app_instance=None):
    """
    Get appropriate storage path for platform.

    On Android, uses app-internal storage which doesn't require permissions.
    This must be called AFTER the app is running to get the correct path.

    Args:
        app_instance: Optional KOCompanionApp instance for getting user_data_dir
    """
    if platform == 'android':
        # First try: use provided app instance's user_data_dir (safest, no permissions needed)
        if app_instance and hasattr(app_instance, 'user_data_dir'):
            if app_instance.user_data_dir:
                return app_instance.user_data_dir

        # Second try: get running app's user_data_dir
        running_app = App.get_running_app()
        if running_app and hasattr(running_app, 'user_data_dir'):
            if running_app.user_data_dir:
                return running_app.user_data_dir

        # Third try: android.storage internal path (no permissions needed)
        try:
            from android.storage import app_storage_path
            path = app_storage_path()
            if path:
                return path
        except (ImportError, Exception):
            pass

        # Last resort: fallback to local directory if all else fails on Android
        return './ko_companion_data'
    else:
        # For non-Android, use home directory
        try:
            path = os.path.expanduser('~/.ko_companion')
            # Final check: if expanduser returns just '/data' or similar restricted path
            if path == '/data/.ko_companion':
                return './ko_companion_data'
            return path
        except Exception:
            return './ko_companion_data'


class KOCompanionApp(App):
    """
    Main application class for KO Companion.
    
    Manages:
    - Onboarding flow for new users
    - Companion interaction screen
    - Theme based on user preferences
    - AI lifecycle
    """
    
    title = 'KO Companion'
    name = 'ko_companion'
    
    # Application state
    ai_instance = ObjectProperty(None, allownone=True)
    ai_runtime = ObjectProperty(None, allownone=True)  # Runtime Authority - RESTORED
    factory = ObjectProperty(None, allownone=True)
    theme = ObjectProperty(None)
    
    # User profile
    user_name = StringProperty('')
    ai_name = StringProperty('')
    favorite_color = StringProperty('blue')
    mode = StringProperty('introvert')
    birthday = StringProperty('')
    serial_code = StringProperty('')
    
    # State flags
    is_onboarded = BooleanProperty(False)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Storage paths are initialized in build() after app is running
        # This avoids permission issues on Android
        self.storage_path = None
        self.config_path = None
        self.theme = ThemeManager()
        self._storage_initialized = False
        self._ai_activated = False  # Prevents double activation
        self._first_boot_pending = False
        
    def on_start(self):
        """Called when the application starts"""
        if platform == 'android':
            from android.permissions import request_permissions, Permission

            def on_permissions_result(permissions, grant_results):
                """Callback after permissions are requested"""
                logger.info(f"[APP] Permissions result: {dict(zip(permissions, grant_results))}")

                # Check if RECORD_AUDIO was granted
                audio_permission = Permission.RECORD_AUDIO
                audio_granted = False
                for p, g in zip(permissions, grant_results):
                    if p == audio_permission and g:
                        audio_granted = True
                        break

                if audio_granted:
                    logger.info("[APP] RECORD_AUDIO granted")
                    # Trigger audio and vision initialization
                    if self.ai_runtime:
                        logger.info("[APP] Triggering Runtime reinit after permissions...")
                        def _reinit_runtime(dt):
                            try:
                                # Call the new reinit method
                                if hasattr(self.ai_runtime, 'reinit_after_permissions'):
                                    self.ai_runtime.reinit_after_permissions()
                                else:
                                    # Fallback to old behavior
                                    ready = self.ai_runtime.audio.is_ready
                                    logger.info(f"[APP] Audio engine ready: {ready}")
                                    if ready:
                                        self.ai_runtime.enable_listening()
                            except Exception as e:
                                logger.error(f"[APP] Runtime reinit error: {e}")
                        Clock.schedule_once(_reinit_runtime, 0.5)

            # Store permissions callback for camera handling
            def on_all_permissions_result(permissions, grant_results):
                """Handle all permissions including camera"""
                on_permissions_result(permissions, grant_results)

                # Check camera permission specifically for vision
                camera_permission = Permission.CAMERA
                camera_granted = False
                for p, g in zip(permissions, grant_results):
                    if p == camera_permission and g:
                        camera_granted = True
                        break

                if camera_granted:
                    logger.info("[APP] CAMERA permission granted")
                    # Re-trigger vision if runtime exists
                    if self.ai_runtime and hasattr(self.ai_runtime, 'vision'):
                        def _reinit_vision(dt):
                            try:
                                if self.ai_runtime.vision and not self.ai_runtime.vision.is_active():
                                    logger.info("[APP] Starting vision after camera permission...")
                                    self.ai_runtime.vision.start()
                            except Exception as e:
                                logger.error(f"[APP] Vision reinit error: {e}")
                        Clock.schedule_once(_reinit_vision, 0.5)

            request_permissions([
                Permission.RECORD_AUDIO,
                Permission.WRITE_EXTERNAL_STORAGE,
                Permission.READ_EXTERNAL_STORAGE,
                Permission.CAMERA,
            ], on_all_permissions_result)

            # Request overlay permission separately (requires special handling on Android)
            try:
                from jnius import autoclass
                Context = autoclass('android.content.Context')
                Settings = autoclass('android.provider.Settings')
                Intent = autoclass('android.content.Intent')
                Uri = autoclass('android.net.Uri')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                activity = PythonActivity.mActivity

                # Check if we have overlay permission
                if not Settings.canDrawOverlays(activity):
                    # Open settings to grant overlay permission
                    intent = Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION)
                    intent.setData(Uri.parse(f"package:{activity.getPackageName()}"))
                    activity.startActivity(intent)
            except Exception as e:
                logger.warning(f"[APP] Could not request overlay permission: {e}")

    def _init_storage(self):
        """Initialize storage paths. Must be called after app is running."""
        if self._storage_initialized:
            return True

        # Get storage path now that app is running
        self.storage_path = get_storage_path(self)

        # On Android, user_data_dir is the safest fallback
        if self.storage_path is None:
            self.storage_path = self.user_data_dir

        if not self.storage_path:
            logger.error("[APP] Failed to determine storage path")
            return False

        self.config_path = os.path.join(self.storage_path, 'config.json')

        # Create storage directory (should work without permissions for internal storage)
        try:
            Path(self.storage_path).mkdir(parents=True, exist_ok=True)
            self._storage_initialized = True
            logger.info(f"[APP] Storage initialized at: {self.storage_path}")
            return True
        except Exception as e:
            logger.error(f"[APP] Failed to create storage directory: {e}")
            return False

    def build(self):
        """Build the application UI"""
        # Initialize storage (now that app is running, we have access to user_data_dir)
        if not self._init_storage():
            logger.warning("[APP] Storage initialization failed, using defaults")

        # Load existing config if storage is ready
        if self._storage_initialized:
            self._load_config()

        # Apply theme
        self.theme.set_color(self.favorite_color)
        Window.clearcolor = self.theme.background

        # Create screen manager
        self.screen_manager = ScreenManager(transition=FadeTransition(duration=0.3))

        # Add screens
        self.onboarding_screen = OnboardingScreen(name='onboarding')
        self.companion_screen = CompanionScreen(name='companion')

        self.screen_manager.add_widget(self.onboarding_screen)
        self.screen_manager.add_widget(self.companion_screen)

        # Determine starting screen
        if self.is_onboarded and self.serial_code:
            # Returning user - go straight to companion
            # Activation happens via CompanionScreen.on_enter (no Clock timers)
            self.screen_manager.current = 'companion'
        else:
            # New user - show onboarding
            self.screen_manager.current = 'onboarding'

        # Wired evolution system disabled for working APK

        return self.screen_manager
    
    def _load_config(self):
        """Load saved configuration"""
        if not self.config_path:
            logger.warning("[APP] No config path set, cannot load config")
            return

        logger.info(f"[APP] Looking for config at: {self.config_path}")
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r') as f:
                    config = json.load(f)

                self.user_name = config.get('user_name', '')
                self.ai_name = config.get('ai_name', '')
                self.favorite_color = config.get('favorite_color', 'blue')
                self.mode = config.get('mode', 'introvert')
                self.birthday = config.get('birthday', '')
                self.serial_code = config.get('serial_code', '')
                self.is_onboarded = config.get('is_onboarded', False)

                logger.info(f"[APP] Loaded config: user={self.user_name}, is_onboarded={self.is_onboarded}")
            except Exception as e:
                logger.error(f"[APP] Failed to load config: {e}")
        else:
            logger.info("[APP] No existing config file found - new user")
    
    def _save_config(self):
        """Save current configuration"""
        if not self._storage_initialized or not self.config_path:
            logger.warning("[APP] Cannot save config - storage not initialized")
            return

        config = {
            'user_name': self.user_name,
            'ai_name': self.ai_name,
            'favorite_color': self.favorite_color,
            'mode': self.mode,
            'birthday': self.birthday,
            'serial_code': self.serial_code,
            'is_onboarded': self.is_onboarded,
            'last_accessed': datetime.now().isoformat()
        }

        try:
            logger.info(f"[APP] Saving config to: {self.config_path}")
            with open(self.config_path, 'w') as f:
                json.dump(config, f, indent=2)
                f.flush()  # Flush Python buffer
                os.fsync(f.fileno())  # Force OS to write to disk
            logger.info(f"[APP] Config saved successfully (is_onboarded={self.is_onboarded})")
        except Exception as e:
            logger.error(f"[APP] Failed to save config to {self.config_path}: {e}")
    
    def complete_onboarding(self, user_name: str, ai_name: str,
                           favorite_color: str, mode: str, birthday: str):
        """
        Called when onboarding is complete.

        Prepares user data and transitions to companion screen.
        AI activation is deferred until the companion screen is active.
        """
        try:
            # Ensure storage is initialized
            if not self._storage_initialized:
                if not self._init_storage():
                    logger.error("[APP] Critical: Storage could not be initialized during onboarding")

            # Store user preferences
            self.user_name = user_name
            self.ai_name = ai_name
            self.favorite_color = favorite_color
            self.mode = mode
            self.birthday = birthday

            # Apply theme immediately
            self.theme.set_color(favorite_color)
            Window.clearcolor = self.theme.background

            # Initialize AI factory and create account
            # On Android, prioritize user_data_dir for internal storage (no permissions needed)
            if platform == 'android':
                ai_data_root = self.user_data_dir or self.storage_path
            else:
                ai_data_root = self.storage_path or self.user_data_dir

            if not ai_data_root:
                logger.warning("[APP] Both storage_path and user_data_dir are empty, using default")
                ai_data_path = './offline_ai_data'
            else:
                ai_data_path = os.path.join(ai_data_root, 'ai_data')

            logger.info(f"[APP] Initializing AI factory at: {ai_data_path}")
            self.factory = OfflineAIFactory(ai_data_path)

            # Create new account
            logger.info(f"[APP] Creating new account for: {user_name}")
            account_id, serial_code = self.factory.create_new_account(f"{user_name}@local")
            self.serial_code = serial_code

            # Mark as onboarded
            self.is_onboarded = True
            logger.info(f"[APP] Onboarding complete for '{ai_name}'. Serial: {serial_code}. Saving config...")
            self._save_config()

            # Defer AI activation until CompanionScreen.on_enter
            self._first_boot_pending = True

            # Transition to companion screen
            self.screen_manager.current = 'companion'
        except Exception as e:
            logger.error(f"[APP] Critical failure during onboarding completion: {e}", exc_info=True)
            self._show_error_popup(f"Failed to complete onboarding: {str(e)}")

    def _show_error_popup(self, message: str, title: str = "Error"):
        """Show a general error popup"""
        from kivy.uix.popup import Popup
        from kivy.uix.label import Label
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button

        content = BoxLayout(orientation='vertical', padding=20, spacing=15)
        content.add_widget(Label(
            text=message,
            text_size=(Window.width * 0.7, None),
            halign='center',
            valign='middle'
        ))

        close_btn = Button(
            text='Close',
            size_hint_y=None,
            height=50
        )

        def on_close(*args):
            popup.dismiss()

        close_btn.bind(on_release=on_close)
        content.add_widget(close_btn)

        popup = Popup(
            title=title,
            content=content,
            size_hint=(0.85, 0.4),
            auto_dismiss=True
        )
        popup.open()
    
    def _activate_ai(self, first_boot: bool = False):
        """
        Activate the AI instance with Runtime Authority.
        Runtime is the SINGLE AUTHORITY over AI lifecycle, audio, vision, and state.
        """
        if self._ai_activated:
            return
        self._ai_activated = True

        def _deferred_activation(dt):
            try:
                if not self._storage_initialized:
                    self._init_storage()

                if not self.factory:
                    ai_data_path = os.path.join(self.storage_path, 'ai_data') if self.storage_path else self.user_data_dir
                    self.factory = OfflineAIFactory(ai_data_path)

                # Activate AI instance
                self.ai_instance = self.factory.activate(
                    self.serial_code,
                    device_id=self._get_device_id(),
                    device_name=self._get_device_name()
                )

                if self.ai_instance:
                    self.ai_instance.set_mode(extrovert=(self.mode == 'extrovert'))

                    # Create Runtime Authority - this is the SINGLE AUTHORITY
                    # Runtime owns: audio, vision, state machine, expression routing
                    self.ai_runtime = create_runtime(
                        ai=self.ai_instance,
                        screen=self.companion_screen,
                        interaction_mode=self.mode,
                        language="en-US",
                        enable_vision=True,
                        enable_corpus=False
                    )

                    # Connect screen to AI and Runtime
                    self.companion_screen.connect_ai(self.ai_instance, self.ai_runtime)

                    # Set AI name from onboarding
                    self.ai_runtime.ai_name = self.ai_name

                    # If first boot, summon with intro sequence
                    if first_boot:
                        self.ai_runtime.summon(f"come on {self.ai_name}", is_first_boot=True)
                    else:
                        self.ai_runtime.summon(f"come on {self.ai_name}", is_first_boot=False)

                    logger.info(f"[APP] AI and Runtime activated for '{self.ai_name}'")
                else:
                    self._ai_activated = False
                    self._show_activation_error("Could not activate AI.")

            except Exception as e:
                self._ai_activated = False
                logger.error(f"[APP] AI activation failed: {e}", exc_info=True)
                self._show_activation_error(f"AI error: {str(e)}")

        Clock.schedule_once(_deferred_activation, 0.2)

    def _show_activation_error(self, message: str):
        """Show error popup when AI activation fails"""
        from kivy.uix.popup import Popup
        from kivy.uix.label import Label
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button

        content = BoxLayout(orientation='vertical', padding=20, spacing=15)
        content.add_widget(Label(
            text=message,
            text_size=(Window.width * 0.7, None),
            halign='center',
            valign='middle'
        ))

        retry_btn = Button(
            text='Retry',
            size_hint_y=None,
            height=50
        )

        def on_retry(*args):
            popup.dismiss()
            self._activate_ai()

        retry_btn.bind(on_release=on_retry)
        content.add_widget(retry_btn)

        popup = Popup(
            title='Activation Error',
            content=content,
            size_hint=(0.85, 0.4),
            auto_dismiss=False
        )
        popup.open()
        logger.warning(f"[APP] Showing activation error: {message}")

    def _get_device_id(self) -> str:
        """Get unique device identifier"""
        if platform == 'android':
            try:
                from jnius import autoclass
                Settings = autoclass('android.provider.Settings$Secure')
                Context = autoclass('android.content.Context')
                PythonActivity = autoclass('org.kivy.android.PythonActivity')
                return Settings.getString(
                    PythonActivity.mActivity.getContentResolver(),
                    Settings.ANDROID_ID
                )
            except Exception:
                pass
        
        # Fallback: generate from machine info
        import uuid
        return str(uuid.uuid4())[:16]
    
    def _get_device_name(self) -> str:
        """Get human-readable device name"""
        if platform == 'android':
            try:
                from jnius import autoclass
                Build = autoclass('android.os.Build')
                return f"{Build.MANUFACTURER} {Build.MODEL}"
            except Exception:
                return "Android Device"
        return "Desktop"
    
    def on_pause(self):
        """Called when app is paused (Android)"""
        if self.ai_instance:
            self.ai_instance.save_state()
            logger.info("[APP] State saved on pause")
        return True
    
    def on_resume(self):
        """Called when app resumes (Android)"""
        logger.info("[APP] Resumed")
    
    def on_stop(self):
        """Called when app is closing"""
        if self.factory:
            self.factory.shutdown_all()
        
        self._save_config()
        logger.info("[APP] Shutdown complete")
