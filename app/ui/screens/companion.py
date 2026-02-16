#!/usr/bin/env python3
"""
Agora AI Platform - Modern Companion Screen
===========================================
Creative, modern chat interface.
"""

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


class CompanionScreen(Screen):
    """Modern AI companion screen"""
    
    is_listening = False
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
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
        
        # Welcome message
        self._add_message("Hello! I'm your AI companion. How can I help you today?", is_ai=True)
        
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
            text='Hold to Speak',
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
    
    def _send_message(self, *args):
        text = self.text_input.text.strip()
        if text:
            self._add_message(text, is_ai=False)
            self.text_input.text = ''
            # Simulate AI response
            Clock.schedule_once(lambda dt: self._add_message("I received your message! (Demo response)", is_ai=True), 1)
    
    def _start_listening(self, *args):
        self.is_listening = True
        self.mic_btn.text = 'Listening...'
        self.mic_btn.background_color = (0.3, 0.7, 0.4, 1)
        print("[MIC] Started listening")
    
    def _stop_listening(self, *args):
        self.is_listening = False
        self.mic_btn.text = 'Hold to Speak'
        self.mic_btn.background_color = (0.9, 0.3, 0.4, 1)
        print("[MIC] Stopped listening")
    
    def _go_back(self, *args):
        app = App.get_running_app()
        app.screen_manager.current = 'platform_home'
