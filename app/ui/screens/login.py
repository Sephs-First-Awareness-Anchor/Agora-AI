#!/usr/bin/env python3
"""
Agora AI Platform - Login Screen
=================================

Production login with:
- User authentication
- Admin auto-unlock (for development/testing)
- Guest mode (limited features)
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle
from kivy.properties import StringProperty
from kivy.clock import Clock
from kivy.app import App
import hashlib


class LoginScreen(Screen):
    """
    Login screen for Agora AI Platform.
    
    Admin credentials (for development):
    - Username: admin
    - Password: agora2024
    
    This auto-unlocks the AI and all features.
    """
    
    status_message = StringProperty('')
    
    # Admin credentials - in production, this would be server-side only
    ADMIN_USERNAME = 'admin'
    ADMIN_PASSWORD_HASH = hashlib.sha256('agora2024'.encode()).hexdigest()
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build_ui()
    
    def _build_ui(self):
        """Build the login UI"""
        self.clear_widgets()
        
        main = BoxLayout(orientation='vertical', padding=30, spacing=15)
        
        # Background
        with main.canvas.before:
            Color(0.05, 0.05, 0.08, 1)
            self.bg_rect = RoundedRectangle(pos=main.pos, size=main.size)
        main.bind(pos=self._update_bg, size=self._update_bg)
        
        # Spacer
        main.add_widget(Widget(size_hint_y=0.15))
        
        # Logo/Title
        main.add_widget(Label(
            text='[b]Agora AI[/b]',
            font_size='36sp',
            markup=True,
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=60
        ))
        
        main.add_widget(Label(
            text='Platform Login',
            font_size='18sp',
            color=(0.6, 0.6, 0.8, 1),
            size_hint_y=None,
            height=30
        ))
        
        # Spacer
        main.add_widget(Widget(size_hint_y=0.1))
        
        # Login Card
        card = BoxLayout(orientation='vertical', padding=25, spacing=15, size_hint_y=None, height=280)
        with card.canvas.before:
            Color(0.12, 0.12, 0.18, 1)
            RoundedRectangle(pos=card.pos, size=card.size, radius=[18])
        card.bind(pos=self._update_card_bg, size=self._update_card_bg)
        
        # Username
        card.add_widget(Label(
            text='Username',
            font_size='12sp',
            color=(0.7, 0.7, 0.8, 1),
            halign='left',
            size_hint_y=None,
            height=20
        ))
        self.username_input = TextInput(
            hint_text='Enter username',
            font_size='16sp',
            multiline=False,
            background_color=(0.15, 0.15, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.5, 0.5, 0.5, 1),
            padding=[12, 12],
            size_hint_y=None,
            height=45
        )
        card.add_widget(self.username_input)
        
        # Password
        card.add_widget(Label(
            text='Password',
            font_size='12sp',
            color=(0.7, 0.7, 0.8, 1),
            halign='left',
            size_hint_y=None,
            height=20
        ))
        self.password_input = TextInput(
            hint_text='Enter password',
            font_size='16sp',
            multiline=False,
            password=True,
            background_color=(0.15, 0.15, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.5, 0.5, 0.5, 1),
            padding=[12, 12],
            size_hint_y=None,
            height=45
        )
        self.password_input.bind(on_text_validate=self._do_login)
        card.add_widget(self.password_input)
        
        # Status message
        self.status_label = Label(
            text=self.status_message,
            font_size='12sp',
            color=(1, 0.4, 0.4, 1),
            size_hint_y=None,
            height=25
        )
        card.add_widget(self.status_label)
        
        main.add_widget(card)
        
        # Spacer
        main.add_widget(Widget(size_hint_y=0.05))
        
        # Login button
        login_btn = Button(
            text='Login',
            font_size='18sp',
            bold=True,
            background_color=(0.3, 0.5, 0.9, 1),
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=55
        )
        login_btn.bind(on_release=self._do_login)
        main.add_widget(login_btn)
        
        # Guest mode button
        guest_btn = Button(
            text='Continue as Guest (Limited)',
            font_size='14sp',
            background_color=(0, 0, 0, 0),
            color=(0.6, 0.6, 0.7, 1),
            size_hint_y=None,
            height=40
        )
        guest_btn.bind(on_release=self._guest_mode)
        main.add_widget(guest_btn)
        
        # Admin hint (remove in production)
        main.add_widget(Label(
            text='[Dev] Admin: admin / agora2024',
            font_size='10sp',
            color=(0.4, 0.4, 0.5, 1),
            size_hint_y=None,
            height=20
        ))
        
        self.add_widget(main)
    
    def _update_bg(self, instance, value):
        if hasattr(self, 'bg_rect'):
            self.bg_rect.pos = instance.pos
            self.bg_rect.size = instance.size
    
    def _update_card_bg(self, instance, value):
        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(0.12, 0.12, 0.18, 1)
            RoundedRectangle(pos=instance.pos, size=instance.size, radius=[18])
    
    def _do_login(self, *args):
        """Handle login"""
        username = self.username_input.text.strip()
        password = self.password_input.text.strip()
        
        if not username or not password:
            self._show_error('Please enter username and password')
            return
        
        app = App.get_running_app()
        
        # Check admin credentials
        if username == self.ADMIN_USERNAME:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            if password_hash == self.ADMIN_PASSWORD_HASH:
                self._admin_login(app)
                return
        
        # Regular user login - would validate against server
        # For now, create a basic user session
        self._user_login(app, username)
    
    def _admin_login(self, app):
        """Admin login - unlocks everything"""
        print("[LOGIN] Admin login successful - unlocking all features")
        
        # Set admin privileges
        app.current_user = {
            'username': 'admin',
            'is_admin': True,
            'is_premium': True,
            'display_name': 'Agora Admin'
        }
        app.is_ai_purchased = True
        app.is_logged_in = True
        
        # Save to config
        app.save_config()
        
        # Go to platform home
        app.screen_manager.current = 'platform_home'
    
    def _user_login(self, app, username):
        """Regular user login"""
        print(f"[LOGIN] User login: {username}")
        
        # In production: validate against server
        # For now, check if user has purchased
        app.current_user = {
            'username': username,
            'is_admin': False,
            'is_premium': False,
            'display_name': username
        }
        app.is_logged_in = True
        
        # Check server for purchase status (would be API call)
        # For now, use saved config
        
        # Go to platform home
        app.screen_manager.current = 'platform_home'
    
    def _guest_mode(self, *args):
        """Continue as guest - limited features, no AI"""
        print("[LOGIN] Guest mode")
        
        app = App.get_running_app()
        app.current_user = {
            'username': 'guest',
            'is_admin': False,
            'is_premium': False,
            'display_name': 'Guest'
        }
        app.is_logged_in = False
        app.is_ai_purchased = False  # Guests don't have AI
        
        # Go to platform home
        app.screen_manager.current = 'platform_home'
    
    def _show_error(self, message):
        """Show error message"""
        self.status_label.text = message
        self.status_message = message

    def on_enter(self, *args):
        """Called when screen is shown - check for existing license"""
        # Clear inputs
        self.username_input.text = ''
        self.password_input.text = ''
        self.status_label.text = ''
        
        # Check if we can auto-login with existing license
        app = App.get_running_app()
        if app.auth and app.auth.license_manager.has_valid_license():
            # Auto-login with license (offline)
            result = app.auth.login('', '')  # Empty credentials triggers license check
            if result.get('success') and result.get('restored_from_license'):
                print("[LOGIN] Auto-restored from license")
                app.is_logged_in = True
                app.is_ai_purchased = True
                app.current_user = result['user']
                app.screen_manager.current = 'platform_home'
                return
