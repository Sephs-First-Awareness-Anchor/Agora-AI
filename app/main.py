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
import threading
from pathlib import Path
from datetime import datetime

from kivy.app import App
from kivy.utils import platform as kivy_platform
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.core.window import Window
from kivy.clock import Clock
from kivy.properties import ObjectProperty, StringProperty, BooleanProperty

from app.ui.components.theme import ThemeManager, COLOR_THEMES
from app.ui.screens.onboarding import OnboardingScreen
from app.ui.screens.name_enrollment import NameEnrollmentScreen
from app.ui.screens.companion import CompanionScreen
from app.ui.screens.platform_home import PlatformHomeScreen
from app.ui.screens.purchase import PurchaseScreen
from app.ui.screens.login import LoginScreen
from app.auth import AgoraAuth
from app.entity_manager import EntityManager, EntityIdentity

# Import core AI modules
from engine.offline_ai_core import OfflineAIFactory, OfflineAI
from engine.offline_ai_expression import OnboardingProfile
from engine.agora_enrollment import EnrollmentSession, NameLearningStore
from engine.agora_birth import BirthStore, select_birth
from engine.offline_ai_audio_engine import create_audio_engine
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
    if kivy_platform == 'android':
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
    is_ai_purchased = BooleanProperty(False)  # PRODUCTION: False - requires purchase or admin login
    
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
        self.enrollment_audio = None
        self.enrollment_session = None
        self.birth_record = None
        
        # Authentication system
        self.auth = None
        self.current_user = None
        self.is_logged_in = False
        
        # Entity management
        self.entity_manager = None
        
    def on_start(self):
        """Called when the application starts"""
        # SECURITY: Request permissions lazily to avoid "harmful app" warning
        # Permissions are now requested only when AI is activated, not at startup
        logger.info("[APP] App started - permissions will be requested when AI is activated")

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

        # Initialize authentication and entity systems
        if self._storage_initialized:
            self.auth = AgoraAuth(str(self.storage_path))
            self.entity_manager = EntityManager(str(self.storage_path))
            
            # Check for offline license FIRST (works without internet)
            has_license = self.auth.license_manager.has_valid_license()
            
            if has_license:
                # Valid license exists - restore session automatically
                self.is_ai_purchased = True
                license_info = self.auth.license_manager.get_license_info()
                if license_info:
                    self.current_user = {
                        'username': license_info.get('user_id', 'user'),
                        'display_name': license_info.get('user_id', 'User'),
                        'is_admin': license_info.get('is_admin', False)
                    }
                    self.is_logged_in = True
                    logger.info(f"[APP] Valid offline license found for: {self.current_user['display_name']}")
            elif self.auth.is_logged_in():
                # No license but has auth session
                self.current_user = self.auth.current_user
                self.is_logged_in = True
                self.is_ai_purchased = self.auth.check_ai_purchase()
                logger.info(f"[APP] Restored auth session for: {self.auth.get_display_name()}")

        # Load existing config if storage is ready
        if self._storage_initialized:
            self._load_config()

        # Apply theme
        self.theme.set_color(self.favorite_color)
        Window.clearcolor = self.theme.background

        # Create screen manager
        self.screen_manager = ScreenManager(transition=FadeTransition(duration=0.3))

        # Add all screens
        self.login_screen = LoginScreen(name='login')
        self.platform_home_screen = PlatformHomeScreen(name='platform_home')
        self.purchase_screen = PurchaseScreen(name='purchase')
        self.onboarding_screen = OnboardingScreen(name='onboarding')
        self.name_enrollment_screen = NameEnrollmentScreen(name='name_enrollment')
        self.companion_screen = CompanionScreen(name='companion')

        self.screen_manager.add_widget(self.login_screen)
        self.screen_manager.add_widget(self.platform_home_screen)
        self.screen_manager.add_widget(self.purchase_screen)
        self.screen_manager.add_widget(self.onboarding_screen)
        self.screen_manager.add_widget(self.name_enrollment_screen)
        self.screen_manager.add_widget(self.companion_screen)

        # Start at Platform Home if has license, otherwise Login
        # OFFLINE-FIRST: License check works without internet
        if self.is_ai_purchased and self.is_logged_in:
            self.screen_manager.current = 'platform_home'
            logger.info("[APP] Starting at Platform Home (license validated)")
        else:
            self.screen_manager.current = 'login'
            logger.info("[APP] Starting at Login (no valid license found)")

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
                # Only use saved purchase status if user is logged in
                if self.is_logged_in:
                    self.is_ai_purchased = config.get('is_ai_purchased', False)
                else:
                    self.is_ai_purchased = False

                logger.info(f"[APP] Loaded config: user={self.user_name}, onboarded={self.is_onboarded}, purchased={self.is_ai_purchased}")
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
            'is_ai_purchased': self.is_ai_purchased,
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
    
    def save_config(self):
        """Public method to save config (called from screens)"""
        self._save_config()
    
    def get_pending_enrollment(self):
        """Reload the one saved six-sample session after a process restart."""
        if not self._storage_initialized:
            self._init_storage()
        if self.enrollment_session is None:
            pending = Path(self.storage_path) / "enrollment" / "pending.json"
            self.enrollment_session = EnrollmentSession(pending)
        return self.enrollment_session

    def has_pending_enrollment(self):
        return bool(self.storage_path and
                    (Path(self.storage_path) / "enrollment" / "pending.json").exists()
                    and not self.is_onboarded)

    def begin_name_enrollment(self, user_name: str, ai_name: str,
                              favorite_color: str, mode: str, birthday: str):
        """Prepare locally; create no AI account and no composer until six PCM takes."""
        if self.is_onboarded:
            raise ValueError("This companion is already born; do not re-enroll as new")
        if not self._storage_initialized:
            if not self._init_storage():
                raise RuntimeError("Local storage unavailable")
        identity = {"user_name":user_name.strip(), "ai_name":ai_name.strip(),
                    "color":favorite_color, "mode":mode, "dob":birthday}
        self.enrollment_session = EnrollmentSession(
            Path(self.storage_path) / "enrollment" / "pending.json", identity)
        if self.enrollment_audio is None:
            self.enrollment_audio = create_audio_engine("en-US")
        if kivy_platform == "android":
            from android.permissions import request_permissions, Permission
            request_permissions([Permission.RECORD_AUDIO])
        self.screen_manager.current = "name_enrollment"

    def capture_enrollment_name(self, done):
        """Exactly one short recording at a time, owned by the audio subsystem."""
        session=self.get_pending_enrollment()
        target=session.next_target()
        if target is None:
            Clock.schedule_once(lambda dt: done("Six samples already recorded"),0)
            return
        if self.enrollment_audio is None:
            self.enrollment_audio = create_audio_engine("en-US")

        def worker():
            error=None
            try:
                pcm=self.enrollment_audio.capture_name_pcm(
                    duration_seconds=1.8, sample_rate=16000)
                session.add_pcm(target,pcm,16000)
            except Exception as exc:
                logger.warning("[ENROLLMENT] Audio sample not accepted: %s",exc)
                error=str(exc)
            Clock.schedule_once(lambda dt: done(error),0)
        threading.Thread(target=worker,daemon=True,name="agora-name-enrollment").start()

    def finish_name_enrollment(self):
        session=self.get_pending_enrollment()
        if not session.ready():
            raise ValueError("Three owner-name and three AI-name samples are required")
        identity=session.data["identity"]
        self.complete_onboarding(
            user_name=identity["user_name"],ai_name=identity["ai_name"],
            favorite_color=identity["color"],mode=identity["mode"],
            birthday=identity["dob"])

    def reset_name_enrollment(self):
        """Delete local provisional pronunciation/speaker data before commitment."""
        if self.is_onboarded:
            raise ValueError("A committed companion cannot be reset by onboarding")
        session=self.get_pending_enrollment()
        if session.data.get("birth_account"):
            raise ValueError("Account commit underway; complete recovery rather than reset")
        session.path.unlink(missing_ok=True)
        self.enrollment_session=None
        self.screen_manager.current="onboarding"

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

            # A hard lifecycle gate: never initialize AI from typed fields alone.
            session=self.get_pending_enrollment()
            if not session.ready():
                raise ValueError("Pronunciation enrollment is incomplete")
            identity=session.data["identity"]
            if (identity["user_name"],identity["ai_name"],identity["mode"],
                    identity["color"],identity["dob"]) != (
                    user_name,ai_name,mode,favorite_color,birthday):
                raise ValueError("Enrollment identity differs from requested birth")
            sample_result=session.result()
            decision=select_birth(
                ai_name=ai_name, mode=mode, color=favorite_color, dob=birthday,
                ai_pronunciation=sample_result["ai_pronunciation"],
                user_enrollment_complete=True, require_audio=True)
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
            if kivy_platform == 'android':
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

            # Crash-safe pending account checkpoint, then immutable birth file.
            prior=session.data.get("birth_account")
            if prior:
                account_id, serial_code = prior["id"], prior["serial_code"]
            else:
                account_id, serial_code = self.factory.create_new_account(f"{user_name}@local")
                session.stage_account(account_id,serial_code)
            self.birth_record=BirthStore(Path(ai_data_path) / account_id).commit(decision)
            if (self.birth_record["primary"] != decision.primary
                    or self.birth_record["secondary"] != decision.secondary
                    or self.birth_record["mode"] != decision.mode):
                raise ValueError("Existing committed birth conflicts with enrollment")
            # Independently mutable, local-only voice and pronunciation data.
            # This never participates in reselecting the frozen birth record.
            NameLearningStore(Path(ai_data_path) / account_id).seed_once(
                identity,sample_result)
            self.serial_code = serial_code
            session.mark_committed(account_id,serial_code)

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
            raise

    def delete_companion_voice_data(self):
        """Owner-initiated deletion affects local acoustic learning, not birth."""
        if not self.factory or not self.serial_code:
            raise ValueError("No activated companion")
        valid,account_id,_=self.factory.account_manager.verify_serial_code(
            self.serial_code)
        if not valid:
            raise ValueError("Cannot verify companion account")
        NameLearningStore(self.factory.storage_dir/account_id).delete_voice_data()
        # Provisional enrollment details must also be deleted for privacy.
        enrollment_file=Path(self.storage_path)/"enrollment"/"pending.json"
        if enrollment_file.exists() and self.is_onboarded:
            enrollment_file.unlink()
        self.enrollment_session=None

    def _get_safe_window_width(self):
        """Get window width safely for Android"""
        try:
            return Window.width if Window.width > 0 else 1080
        except:
            return 1080
    
    def _show_error_popup(self, message: str, title: str = "Error"):
        """Show a general error popup"""
        from kivy.uix.popup import Popup
        from kivy.uix.label import Label
        from kivy.uix.boxlayout import BoxLayout
        from kivy.uix.button import Button

        content = BoxLayout(orientation='vertical', padding=20, spacing=15)
        content.add_widget(Label(
            text=message,
            text_size=(self._get_safe_window_width() * 0.7, None),
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
    
    def _request_runtime_permissions(self):
        """Request permissions at runtime when AI is activated"""
        if kivy_platform == 'android':
            from android.permissions import request_permissions, Permission
            
            def on_permissions_result(permissions, grant_results):
                logger.info(f"[APP] Runtime permissions result: {dict(zip(permissions, grant_results))}")
                # Continue activation regardless - AI works without all permissions
            
            # Request only essential permissions
            request_permissions([
                Permission.RECORD_AUDIO,
                Permission.CAMERA,
            ], on_permissions_result)
    
    def _activate_ai(self, first_boot: bool = False):
        """
        Activate the AI instance with Runtime Authority.
        Includes entity binding and lazy permission requests.
        """
        if self._ai_activated:
            return
        self._ai_activated = True
        
        # Request permissions at activation time (not at startup)
        # This avoids the "harmful app" warning
        self._request_runtime_permissions()

        def _deferred_activation(dt):
            try:
                if not self._storage_initialized:
                    self._init_storage()
                
                # ENTITY MANAGEMENT: Check/create entity
                if self.entity_manager:
                    if not self.entity_manager.current_entity:
                        # Create new entity
                        user_id = self.current_user.get('user_id', 'user') if self.current_user else 'user'
                        self.entity_manager.create_new_entity(user_id=user_id)
                        logger.info(f"[APP] Created new AI entity")
                    else:
                        # Try to activate existing entity
                        entity = self.entity_manager.activate_entity()
                        if entity:
                            logger.info(f"[APP] Activated entity: {entity.entity_id[:16]}...")
                        else:
                            # Entity active on another device
                            self._show_activation_error(
                                "AI is active on another device.\n\n"
                                "Use Transfer Device in settings to move your AI here."
                            )
                            self._ai_activated = False
                            return

                if not self.factory:
                    ai_data_path = os.path.join(self.storage_path, 'ai_data') if self.storage_path else self.user_data_dir
                    self.factory = OfflineAIFactory(ai_data_path)

                # Activate AI instance with entity ID
                device_id = self._get_device_id()
                if self.entity_manager and self.entity_manager.current_entity:
                    # Include entity ID in device ID for tracking
                    entity_prefix = self.entity_manager.current_entity.entity_id[:8]
                    device_id = f"{entity_prefix}_{device_id}"
                
                birth_profile = OnboardingProfile(
                    user_name=self.user_name or "User",
                    ai_name=self.ai_name or "KO",
                    favorite_color=self.favorite_color or "blue",
                    mode=self.mode or "introvert"
                )
                # All new companions must already have an immutable birth.
                # Existing accounts without one are treated as legacy and
                # keep their saved variation profile without reassignment.
                is_valid, account_id, _ = self.factory.account_manager.verify_serial_code(
                    self.serial_code)
                if not is_valid:
                    raise ValueError("Saved companion serial cannot be verified")
                birth_profile.birth_record = BirthStore(
                    self.factory.storage_dir / account_id).read()
                self.birth_record=birth_profile.birth_record
                if self.birth_record and self.birth_record["mode"] != self.mode:
                    self.mode = self.birth_record["mode"]
                    birth_profile.mode = self.mode
                self.ai_instance = self.factory.activate(
                    self.serial_code,
                    device_id=device_id,
                    device_name=self._get_device_name(),
                    onboarding_profile=birth_profile
                )

                if self.ai_instance:
                    self.ai_instance.user_name = self.user_name or "User"
                    self.ai_instance.favorite_color = self.favorite_color or "blue"
                    self.ai_instance.set_mode(extrovert=(self.mode == 'extrovert'))

                    # Create Runtime Authority - this is the SINGLE AUTHORITY
                    # Runtime owns: audio, vision, state machine, expression routing
                    from engine.offline_ai_runtime import create_runtime

                    self.ai_runtime = create_runtime(
                        ai=self.ai_instance,
                        screen=self.companion_screen,
                        interaction_mode=self.mode,
                        language="en-US",
                        enable_vision=True,
                        enable_corpus=False,
                        audio_engine=self.enrollment_audio
                    )

                    # Runtime takes exclusive ownership of the prebirth audio engine.
                    self.enrollment_audio = None

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
            text_size=(self._get_safe_window_width() * 0.7, None),
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
        if kivy_platform == 'android':
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
        if kivy_platform == 'android':
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
