#!/usr/bin/env python3
"""
Agora AI Platform - Modern Purchase Screen
==========================================
Creative, modern design with gradient accents.
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Ellipse, Line
from kivy.metrics import dp
from kivy.app import App
from kivy.clock import Clock


class PurchaseScreen(Screen):
    """Modern purchase screen"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # CRITICAL: Delay UI build to prevent canvas initialization crashes
        Clock.schedule_once(self._build_ui, 0)
    
    def _build_ui(self, *args):
        self.clear_widgets()
        
        root = FloatLayout()
        
        # Abstract gradient background
        with root.canvas.before:
            Color(0.015, 0.015, 0.06, 1)
            self.bg = RoundedRectangle(pos=root.pos, size=root.size)
            
            Color(0.3, 0.1, 0.4, 0.3)
            Ellipse(pos=(dp(-80), dp(500)), size=(dp(350), dp(350)))
            
            Color(0.1, 0.3, 0.4, 0.25)
            Ellipse(pos=(dp(200), dp(-80)), size=(dp(300), dp(300)))
            
            Color(0.2, 0.4, 0.3, 0.2)
            Ellipse(pos=(dp(80), dp(600)), size=(dp(250), dp(250)))
        
        root.bind(pos=self._update_bg, size=self._update_bg)
        
        # Content
        content = BoxLayout(
            orientation='vertical',
            padding=dp(30),
            spacing=dp(20),
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            size_hint=(0.9, 0.9)
        )
        
        content.add_widget(Widget(size_hint_y=0.05))
        
        # Title
        content.add_widget(Label(
            text='Unlock Your AI',
            font_size=dp(36),
            bold=True,
            color=(1, 1, 1, 1)
        ))
        
        content.add_widget(Label(
            text='Personal offline companion',
            font_size=dp(16),
            color=(0.6, 0.8, 1, 0.9)
        ))
        
        content.add_widget(Widget(size_hint_y=0.05))
        
        # Features card
        features = BoxLayout(
            orientation='vertical',
            padding=dp(25),
            spacing=dp(12),
            size_hint_y=None,
            height=dp(280)
        )
        
        with features.canvas.before:
            Color(1, 1, 1, 0.06)
            RoundedRectangle(
                pos=features.pos,
                size=features.size,
                radius=[dp(24)]
            )
            Color(0.5, 0.7, 1, 0.1)
            Line(
                rounded_rectangle=(0, 0, 100, 100, dp(24)),
                width=dp(1)
            )
        
        features.bind(pos=self._update_features, size=self._update_features)
        
        feature_list = [
            'Complete offline operation',
            'Voice-first interaction',
            'Learns & evolves with you',
            'Privacy-first design',
            'Vision & audio capable',
            'Platform sync ready',
        ]
        
        for feat in feature_list:
            row = BoxLayout(
                size_hint_y=None,
                height=dp(35)
            )
            
            with row.canvas.before:
                Color(0.3, 0.9, 0.5, 1)
                RoundedRectangle(
                    pos=(0, dp(8)),
                    size=(dp(18), dp(18)),
                    radius=[dp(9)]
                )
            
            row.add_widget(Widget(size_hint_x=None, width=dp(30)))
            
            row.add_widget(Label(
                text=feat,
                font_size=dp(15),
                color=(0.9, 0.9, 0.95, 1),
                halign='left',
                text_size=(None, None)
            ))
            
            features.add_widget(row)
        
        content.add_widget(features)
        
        content.add_widget(Widget(size_hint_y=0.03))
        
        # Price
        content.add_widget(Label(
            text='$9.99',
            font_size=dp(52),
            bold=True,
            color=(0.3, 0.9, 0.6, 1)
        ))
        
        content.add_widget(Label(
            text='One-time purchase • Lifetime access',
            font_size=dp(13),
            color=(0.6, 0.6, 0.7, 1)
        ))
        
        content.add_widget(Widget(size_hint_y=0.03))
        
        # Buy button
        buy_btn = Button(
            text='BUY NOW',
            font_size=dp(18),
            bold=True,
            background_color=(0.2, 0.6, 0.4, 1),
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(60)
        )
        buy_btn.bind(on_release=self._do_purchase)
        content.add_widget(buy_btn)
        
        # Test button
        test_btn = Button(
            text='Unlock for Testing',
            font_size=dp(14),
            background_color=(0.2, 0.2, 0.3, 0.6),
            color=(0.8, 0.8, 0.9, 1),
            size_hint_y=None,
            height=dp(45)
        )
        test_btn.bind(on_release=self._test_unlock)
        content.add_widget(test_btn)
        
        # Back
        back_btn = Button(
            text='Back',
            font_size=dp(14),
            background_color=(0, 0, 0, 0),
            color=(0.6, 0.6, 0.7, 1),
            size_hint_y=None,
            height=dp(40)
        )
        back_btn.bind(on_release=self._go_back)
        content.add_widget(back_btn)
        
        content.add_widget(Widget(size_hint_y=0.1))
        
        root.add_widget(content)
        self.add_widget(root)
    
    def _update_bg(self, instance, value):
        if hasattr(self, 'bg'):
            self.bg.pos = instance.pos
            self.bg.size = instance.size
    
    def _update_features(self, instance, value):
        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(1, 1, 1, 0.06)
            RoundedRectangle(
                pos=instance.pos,
                size=instance.size,
                radius=[dp(24)]
            )
            Color(0.5, 0.7, 1, 0.1)
            Line(
                rounded_rectangle=(instance.x, instance.y, instance.width, instance.height, dp(24)),
                width=dp(1)
            )
    
    def _do_purchase(self, *args):
        print("[PURCHASE] Buy now clicked")
    
    def _test_unlock(self, *args):
        app = App.get_running_app()
        if app.auth:
            app.auth.license_manager.generate_license('test_user', is_admin=False)
        app.is_ai_purchased = True
        app.save_config()
        app.screen_manager.current = 'platform_home'
    
    def _go_back(self, *args):
        app = App.get_running_app()
        app.screen_manager.current = 'platform_home'
