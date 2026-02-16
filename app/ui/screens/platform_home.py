#!/usr/bin/env python3
"""
Agora AI Platform - Home Screen
================================

Main platform hub with navigation to:
- Launch AI (if purchased)
- Purchase AI (if not purchased)
- Hubs, Rewards, Classes, etc.
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle
from kivy.properties import StringProperty, BooleanProperty, NumericProperty
from kivy.clock import Clock
from kivy.app import App

from app.ui.components.theme import COLOR_THEMES


class PlatformHomeScreen(Screen):
    """
    Agora AI Platform Home Screen.
    
    Features:
    - Launch AI button (checks purchase status)
    - Navigation to Hubs, Rewards, Classes
    - User identity display
    """
    
    # User properties
    public_handle = StringProperty("guest")
    agora_credits = NumericProperty(0)
    class_tokens = NumericProperty(0)
    is_ai_purchased = BooleanProperty(True)  # Default True for testing
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build_ui()
    
    def _build_ui(self):
        """Build the platform home UI"""
        self.clear_widgets()
        
        # Main layout
        main_layout = BoxLayout(orientation='vertical')
        
        # Header
        header = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=60,
            padding=[15, 10],
            spacing=10
        )
        with header.canvas.before:
            Color(0.1, 0.08, 0.15, 1)
            self.header_bg = RoundedRectangle(pos=header.pos, size=header.size)
        header.bind(pos=self._update_header_bg, size=self._update_header_bg)
        
        menu_btn = Button(
            text='☰',
            size_hint=(None, None),
            size=(40, 40),
            background_color=(0, 0, 0, 0),
            color=(1, 1, 1, 1),
            font_size='20sp'
        )
        menu_btn.bind(on_release=self._toggle_menu)
        
        title = Label(
            text='Agora AI',
            font_size='22sp',
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_x=1
        )
        
        header.add_widget(menu_btn)
        header.add_widget(title)
        main_layout.add_widget(header)
        
        # Scrollable content
        scroll = ScrollView()
        content = BoxLayout(
            orientation='vertical',
            padding=20,
            spacing=15,
            size_hint_y=None
        )
        content.bind(minimum_height=content.setter('height'))
        
        # Identity Card
        content.add_widget(self._create_identity_card())
        
        # Launch AI Button (BIG)
        content.add_widget(self._create_launch_ai_section())
        
        # Quick Actions Grid
        content.add_widget(self._create_quick_actions_grid())
        
        scroll.add_widget(content)
        main_layout.add_widget(scroll)
        
        self.add_widget(main_layout)
        self._content = content
    
    def _update_header_bg(self, instance, value):
        """Update header background"""
        if hasattr(self, 'header_bg'):
            self.header_bg.pos = instance.pos
            self.header_bg.size = instance.size
    
    def _create_identity_card(self):
        """Create user identity card"""
        card = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=100,
            padding=15,
            spacing=8
        )
        with card.canvas.before:
            Color(0.15, 0.12, 0.2, 1)
            RoundedRectangle(pos=card.pos, size=card.size, radius=[15])
        card.bind(pos=self._update_card_bg, size=self._update_card_bg)
        
        card.add_widget(Label(
            text='Identity',
            font_size='14sp',
            color=(0.7, 0.7, 0.8, 1),
            halign='left',
            size_hint_y=None,
            height=20
        ))
        
        self.handle_label = Label(
            text=f'Handle: {self.public_handle}',
            font_size='18sp',
            bold=True,
            color=(1, 1, 1, 1),
            halign='left',
            size_hint_y=None,
            height=30
        )
        card.add_widget(self.handle_label)
        
        self.credits_label = Label(
            text=f'Credits: {self.agora_credits} | Tokens: {self.class_tokens}',
            font_size='14sp',
            color=(0.8, 0.8, 0.9, 1),
            halign='left',
            size_hint_y=None,
            height=25
        )
        card.add_widget(self.credits_label)
        
        return card
    
    def _update_card_bg(self, instance, value):
        """Update card background"""
        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(0.15, 0.12, 0.2, 1)
            RoundedRectangle(pos=instance.pos, size=instance.size, radius=[15])
    
    def _create_launch_ai_section(self):
        """Create the Launch AI button section"""
        section = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=150,
            padding=20,
            spacing=10
        )
        
        # Status label
        self.ai_status_label = Label(
            text='AI Status: Active' if self.is_ai_purchased else 'AI Status: Not Purchased',
            font_size='14sp',
            color=(0.5, 1, 0.5, 1) if self.is_ai_purchased else (1, 0.5, 0.5, 1),
            size_hint_y=None,
            height=25
        )
        section.add_widget(self.ai_status_label)
        
        # Launch/Purchase button
        if self.is_ai_purchased:
            btn = Button(
                text='🚀 Launch AI Companion',
                font_size='20sp',
                bold=True,
                background_color=(0.2, 0.6, 0.4, 1),
                color=(1, 1, 1, 1),
                size_hint_y=None,
                height=60
            )
            btn.bind(on_release=self._launch_ai)
        else:
            btn = Button(
                text='🔒 Purchase AI ($9.99)',
                font_size='20sp',
                bold=True,
                background_color=(0.8, 0.4, 0.2, 1),
                color=(1, 1, 1, 1),
                size_hint_y=None,
                height=60
            )
            btn.bind(on_release=self._go_to_purchase)
        
        section.add_widget(btn)
        return section
    
    def _create_quick_actions_grid(self):
        """Create quick action buttons grid"""
        grid = GridLayout(
            cols=2,
            spacing=15,
            size_hint_y=None,
            height=300,
            padding=[0, 10]
        )
        
        actions = [
            ('📍 Hubs', 'Find meeting places', self._go_to_hubs),
            ('🏆 Rewards', 'View achievements', self._go_to_rewards),
            ('🎓 Classes', 'Training packs', self._go_to_classes),
            ('📚 Library', 'Knowledge base', self._go_to_library),
        ]
        
        for title, subtitle, callback in actions:
            card = self._create_action_card(title, subtitle, callback)
            grid.add_widget(card)
        
        return grid
    
    def _create_action_card(self, title, subtitle, callback):
        """Create a single action card"""
        card = BoxLayout(
            orientation='vertical',
            padding=15,
            spacing=5
        )
        with card.canvas.before:
            Color(0.12, 0.12, 0.18, 1)
            RoundedRectangle(pos=card.pos, size=card.size, radius=[12])
        card.bind(pos=self._update_action_card_bg, size=self._update_action_card_bg)
        
        card.add_widget(Label(
            text=title,
            font_size='18sp',
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=30
        ))
        
        card.add_widget(Label(
            text=subtitle,
            font_size='12sp',
            color=(0.7, 0.7, 0.8, 1),
            size_hint_y=None,
            height=20
        ))
        
        # Make clickable
        card.bind(on_touch_down=lambda x, t: callback() if t.button == 'left' else None)
        
        return card
    
    def _update_action_card_bg(self, instance, value):
        """Update action card background"""
        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(0.12, 0.12, 0.18, 1)
            RoundedRectangle(pos=instance.pos, size=instance.size, radius=[12])
    
    def _toggle_menu(self, *args):
        """Toggle side menu"""
        # TODO: Implement drawer
        app = App.get_running_app()
        if hasattr(app, 'show_drawer'):
            app.show_drawer()
    
    def _launch_ai(self, *args):
        """Launch the AI companion"""
        app = App.get_running_app()
        if self.is_ai_purchased:
            # Go to AI onboarding/companion flow
            app.screen_manager.current = 'onboarding'
        else:
            self._go_to_purchase()
    
    def _go_to_purchase(self, *args):
        """Go to purchase screen"""
        app = App.get_running_app()
        app.screen_manager.current = 'purchase'
    
    def _go_to_hubs(self, *args):
        """Navigate to hubs"""
        print("[PLATFORM] Navigate to Hubs")
    
    def _go_to_rewards(self, *args):
        """Navigate to rewards"""
        print("[PLATFORM] Navigate to Rewards")
    
    def _go_to_classes(self, *args):
        """Navigate to classes"""
        print("[PLATFORM] Navigate to Classes")
    
    def _go_to_library(self, *args):
        """Navigate to library"""
        print("[PLATFORM] Navigate to Library")
    
    def on_enter(self, *args):
        """Called when screen is shown"""
        app = App.get_running_app()
        
        # Sync with auth system's purchase status
        if app.auth:
            self.is_ai_purchased = app.auth.check_ai_purchase()
            # Update display name from auth
            if app.auth.current_user:
                self.public_handle = app.auth.get_display_name()
        else:
            self.is_ai_purchased = getattr(app, 'is_ai_purchased', False)
        
        # Update UI with current values
        self.handle_label.text = f'Handle: {self.public_handle}'
        self.credits_label.text = f'Credits: {self.agora_credits} | Tokens: {self.class_tokens}'
        self.ai_status_label.text = 'AI Status: Active' if self.is_ai_purchased else 'AI Status: Not Purchased'
        self.ai_status_label.color = (0.5, 1, 0.5, 1) if self.is_ai_purchased else (1, 0.5, 0.5, 1)
        
        # Rebuild UI if purchase status changed
        self._build_ui()
