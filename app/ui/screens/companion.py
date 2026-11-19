#!/usr/bin/env python3
"""
Agora AI Platform - Modern Companion Screen
===========================================
Creative, modern chat interface.
"""

import logging

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.textinput import TextInput
from kivy.uix.gridlayout import GridLayout
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Ellipse
from kivy.metrics import dp
from kivy.app import App
from kivy.clock import Clock


logger = logging.getLogger(__name__)


class CompanionScreen(Screen):
    """Active Agora companion UI, connected through the one Runtime Authority."""

    is_listening = False
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.ai_instance = None
        self.runtime = None
        Clock.schedule_once(self._build_ui, 0)
    
    def _build_ui(self, *args):
        self.clear_widgets()
        
        root = FloatLayout()
        
        # Background
        with root.canvas.before:
            Color(0.015, 0.015, 0.06, 1)
            self.bg = RoundedRectangle(pos=root.pos, size=root.size)
            
            Color(0.3, 0.1, 0.4, 0.3)
            Ellipse(pos=(dp(-80), dp(500)), size=(dp(350), dp(350)))
            
            Color(0.1, 0.3, 0.4, 0.25)
            Ellipse(pos=(dp(200), dp(-80)), size=(dp(300), dp(300)))
        
        root.bind(pos=self._update_bg, size=self._update_bg)
        
        # Content
        content = BoxLayout(
            orientation='vertical',
            padding=dp(20),
            spacing=dp(15),
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            size_hint=(0.95, 0.95)
        )
        
        # Header
        header = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(60),
            padding=[dp(10), 0]
        )
        
        with header.canvas.before:
            Color(1, 1, 1, 0.06)
            RoundedRectangle(
                pos=header.pos,
                size=header.size,
                radius=[dp(15)]
            )
        
        header.bind(pos=self._update_header, size=self._update_header)
        
        header.add_widget(Label(
            text='AI Companion',
            font_size=dp(22),
            bold=True,
            color=(1, 1, 1, 1)
        ))
        
        back_btn = Button(
            text='Back',
            font_size=dp(14),
            background_color=(0, 0, 0, 0),
            color=(0.6, 0.8, 1, 1),
            size_hint_x=None,
            width=dp(60)
        )
        back_btn.bind(on_release=self._go_back)
        header.add_widget(back_btn)
        
        content.add_widget(header)

        # Real procedural face owned by the AI (not a decorative placeholder).
        self.face_container = FloatLayout(size_hint_y=None, height=dp(175))
        content.add_widget(self.face_container)
        self.status_label = Label(
            text="Connecting...", font_size=dp(12),
            color=(0.6, 0.8, 1, 0.9),
            size_hint_y=None, height=dp(24)
        )
        content.add_widget(self.status_label)

        # Chat area
        self.chat_scroll = ScrollView(
            size_hint_y=0.7
        )
        
        self.chat_container = BoxLayout(
            orientation='vertical',
            padding=dp(10),
            spacing=dp(10),
            size_hint_y=None
        )
        self.chat_container.bind(minimum_height=self.chat_container.setter('height'))
        
        self.chat_scroll.add_widget(self.chat_container)
        content.add_widget(self.chat_scroll)
        
        # The AI owns its greeting and all subsequent response text.
        
        # Input area
        input_box = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(70),
            spacing=dp(10)
        )
        
        with input_box.canvas.before:
            Color(1, 1, 1, 0.06)
            RoundedRectangle(
                pos=input_box.pos,
                size=input_box.size,
                radius=[dp(20)]
            )
        
        input_box.bind(pos=self._update_input_box, size=self._update_input_box)
        
        self.text_input = TextInput(
            hint_text='Type a message...',
            font_size=dp(16),
            background_color=(0, 0, 0, 0),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.5, 0.5, 0.6, 1),
            cursor_color=(0.5, 0.8, 1, 1),
            multiline=False,
            size_hint_x=0.75
        )
        self.text_input.bind(on_text_validate=self._send_message)
        input_box.add_widget(self.text_input)
        
        send_btn = Button(
            text='Send',
            font_size=dp(14),
            bold=True,
            background_color=(0.2, 0.5, 0.9, 1),
            color=(1, 1, 1, 1),
            size_hint_x=0.25
        )
        send_btn.bind(on_release=self._send_message)
        input_box.add_widget(send_btn)
        
        content.add_widget(input_box)
        
        # Mic button
        self.mic_btn = Button(
            text='Tap to Speak',
            font_size=dp(14),
            bold=True,
            background_color=(0.9, 0.3, 0.4, 1),
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(50)
        )
        self.mic_btn.bind(on_press=self._start_listening)
        self.mic_btn.bind(on_release=self._stop_listening)
        content.add_widget(self.mic_btn)
        
        root.add_widget(content)
        self.add_widget(root)
    
    def _add_message(self, text, is_ai=False):
        bubble = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            padding=[dp(15), dp(10)]
        )
        
        label = Label(
            text=text,
            font_size=dp(14),
            color=(1, 1, 1, 1),
            halign='left' if is_ai else 'right',
            valign='center',
            text_size=(dp(250), None)
        )
        label.bind(texture_size=lambda instance, value: setattr(instance, 'size', value))
        
        with bubble.canvas.before:
            if is_ai:
                Color(0.15, 0.25, 0.4, 0.8)
            else:
                Color(0.2, 0.5, 0.9, 0.8)
            RoundedRectangle(
                pos=bubble.pos,
                size=bubble.size,
                radius=[dp(15)]
            )
        
        bubble.bind(pos=self._make_bubble_updater(is_ai), size=self._make_bubble_updater(is_ai))
        
        if is_ai:
            bubble.add_widget(label)
            bubble.add_widget(Widget())
        else:
            bubble.add_widget(Widget())
            bubble.add_widget(label)
        
        bubble.height = label.texture_size[1] + dp(20)
        
        self.chat_container.add_widget(bubble)
        self.chat_scroll.scroll_y = 0
    
    def _make_bubble_updater(self, is_ai):
        color = [0.15, 0.25, 0.4, 0.8] if is_ai else [0.2, 0.5, 0.9, 0.8]
        def updater(instance, value):
            instance.canvas.before.clear()
            with instance.canvas.before:
                Color(*color)
                RoundedRectangle(
                    pos=instance.pos,
                    size=instance.size,
                    radius=[dp(15)]
                )
        return updater
    
    def _update_bg(self, instance, value):
        if hasattr(self, 'bg'):
            self.bg.pos = instance.pos
            self.bg.size = instance.size
    
    def _update_header(self, instance, value):
        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(1, 1, 1, 0.06)
            RoundedRectangle(
                pos=instance.pos,
                size=instance.size,
                radius=[dp(15)]
            )
    
    def _update_input_box(self, instance, value):
        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(1, 1, 1, 0.06)
            RoundedRectangle(
                pos=instance.pos,
                size=instance.size,
                radius=[dp(20)]
            )
    
    def on_enter(self, *args):
        """One activation after onboarding, then reuse the persisted instance."""
        app = App.get_running_app()
        if not getattr(app, "serial_code", ""):
            self._show_speech("Complete onboarding to activate your companion.", False)
            return
        if not getattr(app, "_ai_activated", False):
            first_boot = getattr(app, "_first_boot_pending", False)
            app._first_boot_pending = False
            app._activate_ai(first_boot=first_boot)
        elif getattr(app, "ai_instance", None) and self.ai_instance is None:
            self.connect_ai(app.ai_instance, getattr(app, "ai_runtime", None))

    def connect_ai(self, ai_instance, runtime=None):
        """Connect the original face and runtime authority without cloning them."""
        self.ai_instance = ai_instance
        self.runtime = runtime

        def attach(dt):
            if not hasattr(self, "face_container"):
                Clock.schedule_once(attach, 0.05)
                return
            self.face_container.clear_widgets()
            face = getattr(ai_instance, "face_widget", None)
            if face is not None:
                if face.parent is not None:
                    face.parent.remove_widget(face)
                self.face_container.add_widget(face)
            self.status_label.text = "Ready" if runtime is not None else "Connecting..."
        Clock.schedule_once(attach, 0)

    def _show_speech(self, text, is_ai=True):
        """The runtime adapter supplies actual text from text/ASR processing."""
        if not hasattr(self, "status_label"):
            return
        if text in ("Listening...", "Thinking...", "Consolidating..."):
            self.status_label.text = text
        elif is_ai and text:
            self.status_label.text = "Speaking"
            self._add_message(text, is_ai=True)
        elif text:
            self.status_label.text = text

    def _hide_speech(self):
        if hasattr(self, "status_label"):
            self.status_label.text = "Ready"

    def _send_message(self, *args):
        if not hasattr(self, "text_input"):
            return
        message = self.text_input.text.strip()
        if not message:
            return
        if self.runtime is None:
            self.status_label.text = "Companion is still connecting"
            return
        self.text_input.text = ""
        self._add_message(message, is_ai=False)
        # Typed messages follow the same Runtime path as recognized voice.
        Clock.schedule_once(lambda dt: self.runtime._process_text_input(message), 0)

    def _start_listening(self, *args):
        if self.runtime is None:
            self.status_label.text = "Microphone not connected"
            return
        self.is_listening = bool(self.runtime.enable_listening())
        self.mic_btn.text = "Listening..." if self.is_listening else "Microphone unavailable"
        if self.is_listening:
            self.mic_btn.background_color = (0.3, 0.7, 0.4, 1)

    def _stop_listening(self, *args):
        # Runtime manages continuous ASR and the introvert/extrovert policy.
        self.is_listening = False
        self.mic_btn.text = "Tap to Speak"
        self.mic_btn.background_color = (0.9, 0.3, 0.4, 1)
    
    def _go_back(self, *args):
        app = App.get_running_app()
        app.screen_manager.current = 'platform_home'
