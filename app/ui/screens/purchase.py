#!/usr/bin/env python3
"""
Agora AI Platform - Purchase Screen
====================================

Screen for purchasing the Offline AI.
For testing, includes a "Unlock for Testing" button.
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle
from kivy.properties import StringProperty
from kivy.app import App


class PurchaseScreen(Screen):
    """
    Purchase screen for Offline AI.
    
    Features:
    - Display AI features/benefits
    - Purchase button (would connect to payment)
    - Test unlock button (for development)
    """
    
    price = StringProperty('$9.99')
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build_ui()
    
    def _build_ui(self):
        """Build the purchase UI"""
        self.clear_widgets()
        
        main_layout = BoxLayout(orientation='vertical', padding=20, spacing=15)
        
        # Background
        with main_layout.canvas.before:
            Color(0.05, 0.05, 0.08, 1)
            self.bg_rect = RoundedRectangle(pos=main_layout.pos, size=main_layout.size)
        main_layout.bind(pos=self._update_bg, size=self._update_bg)
        
        # Spacer
        main_layout.add_widget(Widget(size_hint_y=0.1))
        
        # Title
        main_layout.add_widget(Label(
            text='[b]Unlock Offline AI[/b]',
            font_size='28sp',
            markup=True,
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=50
        ))
        
        # Subtitle
        main_layout.add_widget(Label(
            text='Your personal AI companion that works completely offline',
            font_size='14sp',
            color=(0.7, 0.7, 0.8, 1),
            size_hint_y=None,
            height=30
        ))
        
        # Spacer
        main_layout.add_widget(Widget(size_hint_y=0.05))
        
        # Features card
        features_card = self._create_features_card()
        main_layout.add_widget(features_card)
        
        # Spacer
        main_layout.add_widget(Widget(size_hint_y=0.1))
        
        # Price
        main_layout.add_widget(Label(
            text=f'[b]{self.price}[/b]',
            font_size='36sp',
            markup=True,
            color=(0.3, 0.9, 0.5, 1),
            size_hint_y=None,
            height=50
        ))
        
        # Purchase button (would be real payment in production)
        purchase_btn = Button(
            text='Purchase Now',
            font_size='20sp',
            bold=True,
            background_color=(0.2, 0.6, 0.4, 1),
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=60
        )
        purchase_btn.bind(on_release=self._do_purchase)
        main_layout.add_widget(purchase_btn)
        
        # Spacer
        main_layout.add_widget(Widget(size_hint_y=0.05))
        
        # Test unlock button (for development only)
        test_btn = Button(
            text='[TEST] Unlock for Testing',
            font_size='14sp',
            background_color=(0.4, 0.4, 0.5, 1),
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=45
        )
        test_btn.bind(on_release=self._test_unlock)
        main_layout.add_widget(test_btn)
        
        # Back button
        back_btn = Button(
            text='← Back to Home',
            font_size='14sp',
            background_color=(0, 0, 0, 0),
            color=(0.6, 0.6, 0.7, 1),
            size_hint_y=None,
            height=40
        )
        back_btn.bind(on_release=self._go_back)
        main_layout.add_widget(back_btn)
        
        self.add_widget(main_layout)
    
    def _update_bg(self, instance, value):
        """Update background"""
        if hasattr(self, 'bg_rect'):
            self.bg_rect.pos = instance.pos
            self.bg_rect.size = instance.size
    
    def _create_features_card(self):
        """Create features list card"""
        card = BoxLayout(
            orientation='vertical',
            padding=20,
            spacing=10,
            size_hint_y=None,
            height=250
        )
        with card.canvas.before:
            Color(0.12, 0.12, 0.18, 1)
            RoundedRectangle(pos=card.pos, size=card.size, radius=[15])
        card.bind(pos=self._update_card_bg, size=self._update_card_bg)
        
        features = [
            '✓ Complete offline operation - no internet needed',
            '✓ Voice-first AI companion',
            '✓ Learns and evolves with you',
            '✓ Privacy-focused (no cloud data)',
            '✓ Vision and audio capabilities',
            '✓ Sync with Agora platform when online',
        ]
        
        for feature in features:
            card.add_widget(Label(
                text=feature,
                font_size='13sp',
                color=(0.9, 0.9, 0.95, 1),
                halign='left',
                size_hint_y=None,
                height=30
            ))
        
        return card
    
    def _update_card_bg(self, instance, value):
        """Update card background"""
        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(0.12, 0.12, 0.18, 1)
            RoundedRectangle(pos=instance.pos, size=instance.size, radius=[15])
    
    def _do_purchase(self, *args):
        """Handle purchase (would integrate payment)"""
        app = App.get_running_app()
        print("[PURCHASE] Initiating purchase flow...")
        # In production: integrate Stripe/Google Play/Apple Pay
        # For now, show test unlock
        self._show_message("Use 'Unlock for Testing' button for now")
    
    def _test_unlock(self, *args):
        """Test unlock - uses auth system to unlock"""
        app = App.get_running_app()
        
        # Use auth system to record purchase
        if app.auth:
            success = app.auth.record_purchase('offline_ai', receipt='test_receipt')
            if success:
                app.is_ai_purchased = True
                app.save_config()
                print("[PURCHASE] AI unlocked via auth system!")
            else:
                print("[PURCHASE] Failed to record purchase")
        else:
            # Fallback for testing without auth
            app.is_ai_purchased = True
            app.save_config()
            print("[PURCHASE] AI unlocked (no auth system)")
        
        # Go back to platform home which will now show Launch AI
        app.screen_manager.current = 'platform_home'
    
    def _go_back(self, *args):
        """Go back to platform home"""
        app = App.get_running_app()
        app.screen_manager.current = 'platform_home'
    
    def _show_message(self, message):
        """Show a simple message"""
        # Simple implementation - could use popup
        print(f"[PURCHASE] Message: {message}")
