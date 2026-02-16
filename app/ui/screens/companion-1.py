#!/usr/bin/env python3
"""
KO Companion - Companion Screen
===============================
Authors: Sunni (Sir) Morningstar & Cael Devo

Main interaction screen for the AI companion.
Follows production runtime rules:
- Attaches ai.face_widget
- Uses screen lifecycle for activation
- NO direct AI calls - all through Runtime Authority
- No callback patching or Clock timers for AI initialization
"""

import logging

logger = logging.getLogger(__name__)
import time
from typing import Optional, Dict, Any

from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.core.window import Window
from kivy.properties import (
    ObjectProperty, BooleanProperty, StringProperty, NumericProperty
)
from kivy.app import App

# Import Professional UI
try:
    from companion_ui_professional import (
        ProfessionalCompanionUI, 
        ProfessionalSpeechBubble,
        StatusIndicator,
        ParticleField,
        AudioVisualizer
    )
    USE_PROFESSIONAL_UI = True
except ImportError as e:
    USE_PROFESSIONAL_UI = False
    logger.warning(f"[COMPANION] Professional UI not available: {e}")



class SpeechBubbleWidget(Widget):
    """Visual speech bubble for displaying text"""
    
    text = StringProperty('')
    is_ai = BooleanProperty(True)
    alpha = NumericProperty(0.0)
    
    def __init__(self, text: str = '', is_ai: bool = True, **kwargs):
        super().__init__(**kwargs)
        self.text = text
        self.is_ai = is_ai
        self.size_hint = (None, None)
        
        # Create label
        self.label = Label(
            text=text,
            font_size='15sp',
            color=(1, 1, 1, 1),
            halign='center',
            valign='middle',
            text_size=(None, None)
        )
        self.add_widget(self.label)
        
        self.bind(pos=self._update, size=self._update, text=self._update_text)
    
    def _update_text(self, *args):
        self.label.text = self.text
        # Resize based on text
        self.label.texture_update()
        if self.label.texture:
            self.size = (
                min(Window.width * 0.8, self.label.texture_size[0] + 30),
                self.label.texture_size[1] + 20
            )
        self._update()
    
    def _update(self, *args):
        self.label.pos = self.pos
        self.label.size = self.size
        self.label.text_size = (self.width - 20, None)
        
        self.canvas.before.clear()
        with self.canvas.before:
            if self.is_ai:
                Color(0.12, 0.12, 0.18, self.alpha * 0.9)
            else:
                Color(0.18, 0.22, 0.28, self.alpha * 0.9)
            
            RoundedRectangle(pos=self.pos, radius=[12], size=self.size)


class CompanionScreen(Screen):
    """
    Main companion interaction screen.
    
    Follows strictly the production integration rules:
    - Activation via on_enter
    - Attaches ai.face_widget
    - ALL interactions go through Runtime Authority
    - No direct AI audio control
    """
    
    # AI instance and Runtime Authority
    ai_instance = ObjectProperty(None, allownone=True)
    runtime = ObjectProperty(None, allownone=True)  # Runtime Authority - RESTORED
    mode = StringProperty('introvert')
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._speech_bubble = None
        self._build_ui()

    def _build_ui(self):
        """Build the companion UI container"""
        self.main_layout = FloatLayout()
        
        # Container for the AI's face widget
        self.face_container = FloatLayout(size_hint=(1, 1))
        self.main_layout.add_widget(self.face_container)
        
        # Speech bubble
        self._speech_bubble = SpeechBubbleWidget(
            pos_hint={'center_x': 0.5, 'center_y': 0.25},
            alpha=0
        )
        self.main_layout.add_widget(self._speech_bubble)
        
        # Invisible touch area for interaction
        self.touch_area = Button(
            background_color=(0, 0, 0, 0),
            on_release=self._on_screen_tap
        )
        self.main_layout.add_widget(self.touch_area)
        
        self.add_widget(self.main_layout)

    def on_enter(self, *args):
        """Called when screen becomes active - triggers AI activation"""
        app = App.get_running_app()
        # Only activate if not already activated (prevents double activation)
        if not app._ai_activated:
            # Check if this is the first boot after onboarding
            first_boot = getattr(app, '_first_boot_pending', False)
            app._activate_ai(first_boot=first_boot)

            # Reset first boot flag
            if hasattr(app, '_first_boot_pending'):
                app._first_boot_pending = False

        # Ensure AI and Runtime are connected to this screen
        if app.ai_instance and self.ai_instance is None:
            self.connect_ai(app.ai_instance)

    def connect_ai(self, ai_instance, runtime=None):
        """
        Connect to AI instance and Runtime Authority.
        Runtime is the SINGLE AUTHORITY for all AI interactions.
        """
        self.ai_instance = ai_instance
        self.runtime = runtime

        if ai_instance:
            # Delay attachment until layout is finished
            def _attach(dt):
                try:
                    self.face_container.clear_widgets()
                    if hasattr(ai_instance, 'face_widget') and ai_instance.face_widget:
                        self.face_container.add_widget(ai_instance.face_widget)
                        logger.info(f"[COMPANION] Face widget attached: {ai_instance.face_widget}")
                    else:
                        logger.error("[COMPANION] AI has no face_widget!")
                    
                    if hasattr(ai_instance, 'is_extrovert'):
                        self.mode = 'extrovert' if ai_instance.is_extrovert else 'introvert'
                    
                    logger.info(f"[COMPANION] AI connected, runtime={'active' if runtime else 'none'}")
                except Exception as e:
                    logger.error(f"[COMPANION] Failed to attach AI: {e}", exc_info=True)
            
            Clock.schedule_once(_attach, 0.1)  # Slightly longer delay for safety

    def _on_screen_tap(self, *args):
        """Handle tap on screen for manual input/interaction"""
        self._show_input_popup()

    def _show_speech(self, text: str, is_ai: bool):
        """Show speech bubble - called by Runtime UI Adapter"""
        self._speech_bubble.text = text
        self._speech_bubble.is_ai = is_ai
        Animation(alpha=1.0, duration=0.3).start(self._speech_bubble)

    def _hide_speech(self):
        """Hide speech bubble - called by Runtime UI Adapter"""
        Animation(alpha=0.0, duration=0.5).start(self._speech_bubble)

    def _show_input_popup(self):
        """Show manual text input popup"""
        content = BoxLayout(orientation='vertical', padding=10, spacing=10)
        text_input = TextInput(hint_text='Say something...', multiline=False)
        
        # Button row
        btn_row = BoxLayout(size_hint_y=None, height=50, spacing=10)
        send_btn = Button(text='Send')
        
        # Audio test button
        test_audio_btn = Button(text='Test Audio', size_hint_x=None, width=100)
        
        btn_row.add_widget(send_btn)
        btn_row.add_widget(test_audio_btn)
        
        content.add_widget(text_input)
        content.add_widget(btn_row)
        
        # Audio status label
        audio_status = Label(text='Checking audio...', size_hint_y=None, height=30, font_size='12sp')
        content.add_widget(audio_status)
        
        popup = Popup(title='Talk to KO', content=content, size_hint=(0.8, 0.4))
        
        def update_audio_status(*args):
            """Update audio status display"""
            if self.runtime and hasattr(self.runtime, 'audio'):
                try:
                    ready = self.runtime.audio.is_ready
                    listening = getattr(self.runtime, 'listening_enabled', False)
                    status = f"Audio: {'Ready' if ready else 'Not Ready'} | Mic: {'On' if listening else 'Off'}"
                    audio_status.text = status
                    audio_status.color = (0.3, 1.0, 0.3, 1.0) if ready else (1.0, 0.3, 0.3, 1.0)
                except Exception as e:
                    audio_status.text = f"Audio error: {e}"
                    audio_status.color = (1.0, 0.3, 0.3, 1.0)
            else:
                audio_status.text = "Runtime not available"
                audio_status.color = (1.0, 0.3, 0.3, 1.0)
        
        # Update status immediately and schedule updates
        update_audio_status()
        Clock.schedule_interval(update_audio_status, 1.0)
        
        def on_send(*args):
            if text_input.text:
                text = text_input.text.strip()

                # Check for training command
                if text.lower().startswith('/train'):
                    parts = text.split()
                    num = 500
                    if len(parts) > 1:
                        try:
                            num = int(parts[1])
                        except:
                            pass
                    self._start_corpus_training(num)
                    popup.dismiss()
                    return

                # Route input through Runtime Authority
                if self.runtime:
                    logger.info(f"[COMPANION] Input -> Runtime: {text}")
                    self.runtime._process_text_input(text)
                else:
                    logger.warning(f"[COMPANION] No runtime, input ignored: {text}")
                popup.dismiss()
        
        def on_test_audio(*args):
            """Test audio output"""
            if self.runtime and hasattr(self.runtime, 'audio'):
                try:
                    # Force audio init and speak test
                    ready = self.runtime.audio.is_ready
                    if ready:
                        self.runtime._speak_text("Audio test. Can you hear me?")
                        audio_status.text = "Audio test sent!"
                    else:
                        audio_status.text = "Audio not ready. Check permissions."
                        # Try to force initialization
                        def _retry_init(dt):
                            if self.runtime:
                                _ = self.runtime.audio.is_ready
                                update_audio_status()
                        Clock.schedule_once(_retry_init, 0.5)
                except Exception as e:
                    audio_status.text = f"Audio test error: {e}"
            else:
                audio_status.text = "No runtime available"
        
        # Unschedule updates when popup closes
        def on_dismiss(*args):
            Clock.unschedule(update_audio_status)
        
        popup.bind(on_dismiss=on_dismiss)
        send_btn.bind(on_release=on_send)
        test_audio_btn.bind(on_release=on_test_audio)
        text_input.bind(on_text_validate=on_send)
        popup.open()
    
    def _start_corpus_training(self, num_dialogues: int = 500):
        """Start corpus training mode - DISABLED for working APK"""
        logger.warning("[COMPANION] Corpus training not available in this version")