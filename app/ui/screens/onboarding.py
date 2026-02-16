#!/usr/bin/env python3
"""
Agora AI Platform - Modern Onboarding Screen
============================================
Creative onboarding with step-by-step intro.
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Ellipse
from kivy.metrics import dp
from kivy.app import App
from kivy.clock import Clock


class OnboardingScreen(Screen):
    """Modern onboarding screen"""
    
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
            padding=dp(30),
            spacing=dp(20),
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            size_hint=(0.9, 0.9)
        )
        
        content.add_widget(Widget(size_hint_y=0.1))
        
        # Title
        content.add_widget(Label(
            text='Meet Your AI',
            font_size=dp(36),
            bold=True,
            color=(1, 1, 1, 1)
        ))
        
        content.add_widget(Label(
            text='Getting started',
            font_size=dp(16),
            color=(0.6, 0.8, 1, 0.9)
        ))
        
        content.add_widget(Widget(size_hint_y=0.08))
        
        # Info cards
        for title, desc in [
            ('1. Introduce Yourself', 'Share your name and interests'),
            ('2. Voice Optional', 'Speak or type - your choice'),
            ('3. Grows With You', 'Learns from every conversation'),
        ]:
            card = BoxLayout(
                orientation='vertical',
                padding=dp(20),
                spacing=dp(5),
                size_hint_y=None,
                height=dp(110)
            )
            
            with card.canvas.before:
                Color(1, 1, 1, 0.05)
                RoundedRectangle(
                    pos=card.pos,
                    size=card.size,
                    radius=[dp(20)]
                )
            
            card.bind(pos=self._make_card_updater(), size=self._make_card_updater())
            
            card.add_widget(Label(
                text=title,
                font_size=dp(18),
                bold=True,
                color=(1, 1, 1, 1)
            ))
            
            card.add_widget(Label(
                text=desc,
                font_size=dp(13),
                color=(0.7, 0.7, 0.8, 1)
            ))
            
            content.add_widget(card)
        
        content.add_widget(Widget(size_hint_y=0.05))
        
        # Start button
        start_btn = Button(
            text='START',
            font_size=dp(18),
            bold=True,
            background_color=(0.2, 0.5, 0.9, 1),
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(60)
        )
        start_btn.bind(on_release=self._start_ai)
        content.add_widget(start_btn)
        
        # Skip
        skip_btn = Button(
            text='Skip',
            font_size=dp(14),
            background_color=(0, 0, 0, 0),
            color=(0.6, 0.6, 0.7, 1),
            size_hint_y=None,
            height=dp(40)
        )
        skip_btn.bind(on_release=self._skip)
        content.add_widget(skip_btn)
        
        content.add_widget(Widget(size_hint_y=0.05))
        
        root.add_widget(content)
        self.add_widget(root)
    
    def _make_card_updater(self):
        def updater(instance, value):
            instance.canvas.before.clear()
            with instance.canvas.before:
                Color(1, 1, 1, 0.05)
                RoundedRectangle(
                    pos=instance.pos,
                    size=instance.size,
                    radius=[dp(20)]
                )
        return updater
    
    def _update_bg(self, instance, value):
        if hasattr(self, 'bg'):
            self.bg.pos = instance.pos
            self.bg.size = instance.size
    
    def _start_ai(self, *args):
        app = App.get_running_app()
        app.screen_manager.current = 'companion'
    
    def _skip(self, *args):
        app = App.get_running_app()
        app.screen_manager.current = 'companion'
