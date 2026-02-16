#!/usr/bin/env python3
"""
Agora AI Platform - Purchase Screen
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp
from kivy.app import App


class PurchaseScreen(Screen):
    """Purchase screen for Offline AI"""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build_ui()
    
    def _build_ui(self):
        self.clear_widgets()
        
        main = BoxLayout(orientation='vertical', padding=dp(25), spacing=dp(15))
        
        # Background
        with main.canvas.before:
            Color(0.05, 0.05, 0.08, 1)
            self.bg_rect = RoundedRectangle(pos=main.pos, size=main.size)
        main.bind(pos=self._update_bg, size=self._update_bg)
        
        # Header
        main.add_widget(Widget(size_hint_y=0.05))
        
        main.add_widget(Label(
            text='Unlock AI Companion',
            font_size=dp(30),
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(50)
        ))
        
        main.add_widget(Label(
            text='Your personal offline AI',
            font_size=dp(16),
            color=(0.6, 0.6, 0.8, 1),
            size_hint_y=None,
            height=dp(30)
        ))
        
        main.add_widget(Widget(size_hint_y=0.05))
        
        # Features card
        features = self._create_card()
        
        features_list = [
            'Complete offline operation',
            'Voice-first AI companion',
            'Learns and evolves with you',
            'Privacy-focused design',
            'Vision and audio capable',
            'Platform sync when online',
        ]
        
        for feat in features_list:
            features.add_widget(Label(
                text=f'• {feat}',
                font_size=dp(14),
                color=(0.85, 0.85, 0.9, 1),
                halign='left',
                size_hint_y=None,
                height=dp(32),
                text_size=(None, None)
            ))
        
        main.add_widget(features)
        
        main.add_widget(Widget(size_hint_y=0.05))
        
        # Price
        main.add_widget(Label(
            text='$9.99',
            font_size=dp(48),
            bold=True,
            color=(0.3, 0.9, 0.5, 1),
            size_hint_y=None,
            height=dp(60)
        ))
        
        main.add_widget(Label(
            text='One-time purchase',
            font_size=dp(14),
            color=(0.6, 0.6, 0.7, 1),
            size_hint_y=None,
            height=dp(25)
        ))
        
        main.add_widget(Widget(size_hint_y=0.03))
        
        # Purchase button (real purchase)
        buy_btn = Button(
            text='BUY NOW',
            font_size=dp(18),
            bold=True,
            background_color=(0.2, 0.6, 0.4, 1),
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(55)
        )
        buy_btn.bind(on_release=self._do_purchase)
        main.add_widget(buy_btn)
        
        # Test unlock button
        test_btn = Button(
            text='UNLOCK FOR TESTING',
            font_size=dp(14),
            background_color=(0.3, 0.3, 0.4, 1),
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(45)
        )
        test_btn.bind(on_release=self._test_unlock)
        main.add_widget(test_btn)
        
        # Back button
        back_btn = Button(
            text='Back to Home',
            font_size=dp(14),
            background_color=(0, 0, 0, 0),
            color=(0.6, 0.6, 0.7, 1),
            size_hint_y=None,
            height=dp(40)
        )
        back_btn.bind(on_release=self._go_back)
        main.add_widget(back_btn)
        
        main.add_widget(Widget(size_hint_y=0.1))
        
        self.add_widget(main)
    
    def _create_card(self):
        card = BoxLayout(
            orientation='vertical',
            padding=dp(20),
            spacing=dp(5),
            size_hint_y=None,
            height=dp(240)
        )
        with card.canvas.before:
            Color(0.12, 0.12, 0.18, 1)
            RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(15)])
        card.bind(pos=self._update_card, size=self._update_card)
        return card
    
    def _update_bg(self, instance, value):
        if hasattr(self, 'bg_rect'):
            self.bg_rect.pos = instance.pos
            self.bg_rect.size = instance.size
    
    def _update_card(self, instance, value):
        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(0.12, 0.12, 0.18, 1)
            RoundedRectangle(pos=instance.pos, size=instance.size, radius=[dp(15)])
    
    def _do_purchase(self, *args):
        """Real purchase flow"""
        print("[PURCHASE] Initiating purchase...")
        # In production: integrate Google Play / Stripe
    
    def _test_unlock(self, *args):
        """Test unlock"""
        app = App.get_running_app()
        
        if app.auth:
            app.auth.license_manager.generate_license('test_user', is_admin=False)
        
        app.is_ai_purchased = True
        app.save_config()
        print("[PURCHASE] Unlocked for testing")
        
        app.screen_manager.current = 'platform_home'
    
    def _go_back(self, *args):
        app = App.get_running_app()
        app.screen_manager.current = 'platform_home'
