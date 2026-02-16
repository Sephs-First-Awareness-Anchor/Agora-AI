#!/usr/bin/env python3
"""
Agora AI Platform - Home Screen
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle
from kivy.properties import StringProperty, BooleanProperty, NumericProperty
from kivy.metrics import dp
from kivy.app import App


class PlatformHomeScreen(Screen):
    """Agora AI Platform Home Screen"""
    
    public_handle = StringProperty("User")
    agora_credits = NumericProperty(0)
    class_tokens = NumericProperty(0)
    is_ai_purchased = BooleanProperty(False)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build_ui()
    
    def _build_ui(self):
        self.clear_widgets()
        
        # Main layout
        root = BoxLayout(orientation='vertical')
        
        # Header
        header = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(60),
            padding=[dp(15), dp(10)]
        )
        with header.canvas.before:
            Color(0.08, 0.08, 0.12, 1)
            RoundedRectangle(pos=header.pos, size=header.size)
        header.bind(pos=self._update_header, size=self._update_header)
        
        header.add_widget(Label(
            text='AGORA AI',
            font_size=dp(22),
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_x=1,
            halign='left'
        ))
        
        # Menu button (placeholder)
        menu_btn = Button(
            text='MENU',
            font_size=dp(12),
            size_hint=(None, None),
            size=(dp(60), dp(35)),
            background_color=(0.2, 0.2, 0.3, 1)
        )
        menu_btn.bind(on_release=self._show_menu)
        header.add_widget(menu_btn)
        
        root.add_widget(header)
        
        # Scrollable content
        scroll = ScrollView()
        content = BoxLayout(
            orientation='vertical',
            padding=dp(20),
            spacing=dp(15),
            size_hint_y=None
        )
        content.bind(minimum_height=content.setter('height'))
        
        # Welcome Card
        welcome = self._create_card(dp(100))
        welcome.add_widget(Label(
            text='Welcome back,',
            font_size=dp(14),
            color=(0.6, 0.6, 0.7, 1),
            size_hint_y=None,
            height=dp(25)
        ))
        
        self.handle_label = Label(
            text=self.public_handle,
            font_size=dp(24),
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(35)
        )
        welcome.add_widget(self.handle_label)
        
        self.credits_label = Label(
            text=f'Credits: {self.agora_credits}',
            font_size=dp(14),
            color=(0.7, 0.7, 0.8, 1),
            size_hint_y=None,
            height=dp(25)
        )
        welcome.add_widget(self.credits_label)
        
        content.add_widget(welcome)
        
        # AI Status Card
        status_card = self._create_card(dp(180))
        
        status_card.add_widget(Label(
            text='AI COMPANION STATUS',
            font_size=dp(12),
            color=(0.5, 0.5, 0.6, 1),
            size_hint_y=None,
            height=dp(25)
        ))
        
        self.status_text = Label(
            text='ACTIVE' if self.is_ai_purchased else 'NOT PURCHASED',
            font_size=dp(28),
            bold=True,
            color=(0.3, 0.9, 0.5, 1) if self.is_ai_purchased else (0.9, 0.5, 0.3, 1),
            size_hint_y=None,
            height=dp(40)
        )
        status_card.add_widget(self.status_text)
        
        # Launch/Purchase button
        if self.is_ai_purchased:
            launch_btn = Button(
                text='LAUNCH AI',
                font_size=dp(18),
                bold=True,
                background_color=(0.2, 0.6, 0.4, 1),
                color=(1, 1, 1, 1),
                size_hint_y=None,
                height=dp(55)
            )
            launch_btn.bind(on_release=self._launch_ai)
        else:
            launch_btn = Button(
                text='PURCHASE AI',
                font_size=dp(18),
                bold=True,
                background_color=(0.8, 0.4, 0.2, 1),
                color=(1, 1, 1, 1),
                size_hint_y=None,
                height=dp(55)
            )
            launch_btn.bind(on_release=self._go_purchase)
        
        status_card.add_widget(Widget(size_hint_y=0.1))
        status_card.add_widget(launch_btn)
        
        content.add_widget(status_card)
        
        # Quick Actions Grid
        content.add_widget(Label(
            text='QUICK ACTIONS',
            font_size=dp(12),
            color=(0.5, 0.5, 0.6, 1),
            size_hint_y=None,
            height=dp(30),
            halign='left',
            text_size=(None, None)
        ))
        
        grid = GridLayout(
            cols=2,
            spacing=dp(15),
            size_hint_y=None,
            height=dp(280)
        )
        
        actions = [
            ('Hubs', 'Find meeting places', self._go_hubs),
            ('Rewards', 'View achievements', self._go_rewards),
            ('Classes', 'Training packs', self._go_classes),
            ('Library', 'Knowledge base', self._go_library),
        ]
        
        for title, desc, callback in actions:
            grid.add_widget(self._create_action_card(title, desc, callback))
        
        content.add_widget(grid)
        
        content.add_widget(Widget(size_hint_y=0.05))
        
        scroll.add_widget(content)
        root.add_widget(scroll)
        
        self.add_widget(root)
    
    def _create_card(self, height):
        """Create a styled card"""
        card = BoxLayout(
            orientation='vertical',
            padding=dp(20),
            spacing=dp(5),
            size_hint_y=None,
            height=height
        )
        with card.canvas.before:
            Color(0.12, 0.12, 0.18, 1)
            RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(15)])
        card.bind(pos=self._update_card, size=self._update_card)
        return card
    
    def _create_action_card(self, title, desc, callback):
        """Create an action button card"""
        card = BoxLayout(
            orientation='vertical',
            padding=dp(15),
            spacing=dp(5)
        )
        with card.canvas.before:
            Color(0.1, 0.1, 0.15, 1)
            RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(12)])
        
        card.bind(pos=self._update_action_card, size=self._update_action_card)
        
        card.add_widget(Label(
            text=title,
            font_size=dp(18),
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(30)
        ))
        
        card.add_widget(Label(
            text=desc,
            font_size=dp(12),
            color=(0.6, 0.6, 0.7, 1),
            size_hint_y=None,
            height=dp(20)
        ))
        
        # Make clickable
        btn = Button(
            background_color=(0, 0, 0, 0),
            background_normal='',
            size_hint=(1, 1),
            pos_hint={'center_x': 0.5, 'center_y': 0.5}
        )
        btn.bind(on_release=callback)
        card.add_widget(btn)
        
        return card
    
    def _update_header(self, instance, value):
        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(0.08, 0.08, 0.12, 1)
            RoundedRectangle(pos=instance.pos, size=instance.size)
    
    def _update_card(self, instance, value):
        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(0.12, 0.12, 0.18, 1)
            RoundedRectangle(pos=instance.pos, size=instance.size, radius=[dp(15)])
    
    def _update_action_card(self, instance, value):
        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(0.1, 0.1, 0.15, 1)
            RoundedRectangle(pos=instance.pos, size=instance.size, radius=[dp(12)])
    
    def _show_menu(self, *args):
        print("[PLATFORM] Menu clicked")
    
    def _launch_ai(self, *args):
        """Launch the AI"""
        app = App.get_running_app()
        if self.is_ai_purchased:
            app.screen_manager.current = 'onboarding'
        else:
            self._go_purchase()
    
    def _go_purchase(self, *args):
        """Go to purchase screen"""
        app = App.get_running_app()
        app.screen_manager.current = 'purchase'
    
    def _go_hubs(self, *args):
        print("[PLATFORM] Hubs")
    
    def _go_rewards(self, *args):
        print("[PLATFORM] Rewards")
    
    def _go_classes(self, *args):
        print("[PLATFORM] Classes")
    
    def _go_library(self, *args):
        print("[PLATFORM] Library")
    
    def on_enter(self, *args):
        """Update UI when screen shown"""
        app = App.get_running_app()
        
        # Update from app state
        if app.current_user:
            self.public_handle = app.current_user.get('display_name', 'User')
        self.is_ai_purchased = getattr(app, 'is_ai_purchased', False)
        
        # Update labels
        self.handle_label.text = self.public_handle
        self.credits_label.text = f'Credits: {self.agora_credits}'
        
        # Update status
        if self.is_ai_purchased:
            self.status_text.text = 'ACTIVE'
            self.status_text.color = (0.3, 0.9, 0.5, 1)
        else:
            self.status_text.text = 'NOT PURCHASED'
            self.status_text.color = (0.9, 0.5, 0.3, 1)
        
        # Rebuild UI to update button
        self._build_ui()
