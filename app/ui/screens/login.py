#!/usr/bin/env python3
"""
Agora AI Platform - Login Screen
=================================

Login/Signup with:
- Admin access (password: agora2024)
- User login
- Email/Google signup
- Guest mode
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle
from kivy.properties import StringProperty
from kivy.metrics import dp
from kivy.app import App
import hashlib
import json


class LoginScreen(Screen):
    """
    Login/Signup screen for Agora AI Platform.
    """
    
    mode = StringProperty('login')  # 'login' or 'signup'
    
    # Admin credentials
    ADMIN_USERNAME = 'admin'
    ADMIN_PASSWORD = 'agora2024'
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build_ui()
    
    def _build_ui(self):
        """Build the login UI with proper mobile sizing"""
        self.clear_widgets()
        
        # Main layout with safe margins for mobile
        main = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(15))
        
        # Background
        with main.canvas.before:
            Color(0.05, 0.05, 0.08, 1)
            self.bg_rect = RoundedRectangle(pos=main.pos, size=main.size)
        main.bind(pos=self._update_bg, size=self._update_bg)
        
        # Title section
        main.add_widget(Widget(size_hint_y=0.08))
        
        main.add_widget(Label(
            text='[b]Agora AI[/b]',
            font_size=dp(32),
            markup=True,
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(50)
        ))
        
        main.add_widget(Label(
            text='Your Offline AI Companion',
            font_size=dp(16),
            color=(0.6, 0.6, 0.8, 1),
            size_hint_y=None,
            height=dp(25)
        ))
        
        main.add_widget(Widget(size_hint_y=0.05))
        
        # Mode toggle (Login / Sign Up)
        toggle_box = BoxLayout(
            orientation='horizontal',
            size_hint_y=None,
            height=dp(50),
            spacing=dp(10),
            padding=[dp(20), 0]
        )
        
        self.login_btn = ToggleButton(
            text='Login',
            group='mode',
            state='down',
            font_size=dp(16),
            background_color=(0.3, 0.5, 0.9, 1),
            color=(1, 1, 1, 1)
        )
        self.login_btn.bind(on_press=lambda x: self._set_mode('login'))
        
        self.signup_btn = ToggleButton(
            text='Sign Up',
            group='mode',
            font_size=dp(16),
            background_color=(0.15, 0.15, 0.2, 1),
            color=(0.7, 0.7, 0.7, 1)
        )
        self.signup_btn.bind(on_press=lambda x: self._set_mode('signup'))
        
        toggle_box.add_widget(self.login_btn)
        toggle_box.add_widget(self.signup_btn)
        main.add_widget(toggle_box)
        
        main.add_widget(Widget(size_hint_y=0.03))
        
        # Form card
        self.form_card = self._create_form_card()
        main.add_widget(self.form_card)
        
        # Action button
        main.add_widget(Widget(size_hint_y=0.02))
        
        self.action_btn = Button(
            text='Login',
            font_size=dp(18),
            bold=True,
            background_color=(0.3, 0.5, 0.9, 1),
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(55)
        )
        self.action_btn.bind(on_release=self._do_action)
        main.add_widget(self.action_btn)
        
        # Status message
        self.status_label = Label(
            text='',
            font_size=dp(14),
            color=(1, 0.4, 0.4, 1),
            size_hint_y=None,
            height=dp(30)
        )
        main.add_widget(self.status_label)
        
        # Guest mode
        main.add_widget(Widget(size_hint_y=0.02))
        
        guest_btn = Button(
            text='Continue as Guest',
            font_size=dp(14),
            background_color=(0, 0, 0, 0),
            color=(0.6, 0.6, 0.7, 1),
            size_hint_y=None,
            height=dp(40)
        )
        guest_btn.bind(on_release=self._guest_mode)
        main.add_widget(guest_btn)
        
        main.add_widget(Widget(size_hint_y=0.05))
        
        # Dev hint
        main.add_widget(Label(
            text='Admin: admin / agora2024',
            font_size=dp(10),
            color=(0.4, 0.4, 0.5, 1),
            size_hint_y=None,
            height=dp(20)
        ))
        
        self.add_widget(main)
    
    def _create_form_card(self):
        """Create the form input card"""
        card = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(12), size_hint_y=None, height=dp(320))
        with card.canvas.before:
            Color(0.12, 0.12, 0.18, 1)
            RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(18)])
        card.bind(pos=self._update_card_bg, size=self._update_card_bg)
        
        # Email field
        card.add_widget(Label(
            text='Email or Username',
            font_size=dp(14),
            color=(0.7, 0.7, 0.8, 1),
            halign='left',
            size_hint_y=None,
            height=dp(25),
            text_size=(None, None)
        ))
        
        self.username_input = TextInput(
            hint_text='Enter email or username',
            font_size=dp(16),
            multiline=False,
            background_color=(0.15, 0.15, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.5, 0.5, 0.5, 1),
            padding=[dp(15), dp(15)],
            size_hint_y=None,
            height=dp(55)
        )
        card.add_widget(self.username_input)
        
        # Password field
        card.add_widget(Label(
            text='Password',
            font_size=dp(14),
            color=(0.7, 0.7, 0.8, 1),
            halign='left',
            size_hint_y=None,
            height=dp(25)
        ))
        
        self.password_input = TextInput(
            hint_text='Enter password',
            font_size=dp(16),
            multiline=False,
            password=True,
            background_color=(0.15, 0.15, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.5, 0.5, 0.5, 1),
            padding=[dp(15), dp(15)],
            size_hint_y=None,
            height=dp(55)
        )
        self.password_input.bind(on_text_validate=self._do_action)
        card.add_widget(self.password_input)
        
        # Confirm password (signup only)
        self.confirm_label = Label(
            text='Confirm Password',
            font_size=dp(14),
            color=(0.7, 0.7, 0.8, 1),
            halign='left',
            size_hint_y=None,
            height=dp(25)
        )
        card.add_widget(self.confirm_label)
        
        self.confirm_input = TextInput(
            hint_text='Confirm password',
            font_size=dp(16),
            multiline=False,
            password=True,
            background_color=(0.15, 0.15, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.5, 0.5, 0.5, 1),
            padding=[dp(15), dp(15)],
            size_hint_y=None,
            height=dp(55)
        )
        self.confirm_input.bind(on_text_validate=self._do_action)
        card.add_widget(self.confirm_input)
        
        # Initially hide confirm fields for login mode
        self.confirm_label.opacity = 0
        self.confirm_input.opacity = 0
        self.confirm_input.disabled = True
        
        return card
    
    def _set_mode(self, mode):
        """Switch between login and signup mode"""
        self.mode = mode
        
        if mode == 'login':
            self.login_btn.state = 'down'
            self.login_btn.background_color = (0.3, 0.5, 0.9, 1)
            self.login_btn.color = (1, 1, 1, 1)
            self.signup_btn.state = 'normal'
            self.signup_btn.background_color = (0.15, 0.15, 0.2, 1)
            self.signup_btn.color = (0.7, 0.7, 0.7, 1)
            self.action_btn.text = 'Login'
            self.confirm_label.opacity = 0
            self.confirm_input.opacity = 0
            self.confirm_input.disabled = True
            self.form_card.height = dp(220)
        else:
            self.signup_btn.state = 'down'
            self.signup_btn.background_color = (0.3, 0.5, 0.9, 1)
            self.signup_btn.color = (1, 1, 1, 1)
            self.login_btn.state = 'normal'
            self.login_btn.background_color = (0.15, 0.15, 0.2, 1)
            self.login_btn.color = (0.7, 0.7, 0.7, 1)
            self.action_btn.text = 'Sign Up'
            self.confirm_label.opacity = 1
            self.confirm_input.opacity = 1
            self.confirm_input.disabled = False
            self.form_card.height = dp(320)
    
    def _update_bg(self, instance, value):
        if hasattr(self, 'bg_rect'):
            self.bg_rect.pos = instance.pos
            self.bg_rect.size = instance.size
    
    def _update_card_bg(self, instance, value):
        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(0.12, 0.12, 0.18, 1)
            RoundedRectangle(pos=instance.pos, size=instance.size, radius=[dp(18)])
    
    def _do_action(self, *args):
        """Handle login or signup"""
        if self.mode == 'login':
            self._do_login()
        else:
            self._do_signup()
    
    def _do_login(self):
        """Handle login"""
        username = self.username_input.text.strip()
        password = self.password_input.text.strip()
        
        if not username or not password:
            self._show_error('Please enter email and password')
            return
        
        app = App.get_running_app()
        
        # Check admin credentials FIRST
        if username.lower() == self.ADMIN_USERNAME:
            # Direct password comparison (not hash for simplicity)
            if password == self.ADMIN_PASSWORD:
                self._admin_login(app)
                return
            else:
                self._show_error('Invalid admin password')
                return
        
        # Regular user login through auth system
        if app.auth:
            result = app.auth.login(username, password)
            if result.get('success'):
                app.current_user = result['user']
                app.is_logged_in = True
                app.is_ai_purchased = app.auth.check_ai_purchase()
                app.save_config()
                app.screen_manager.current = 'platform_home'
                return
            else:
                self._show_error(result.get('error', 'Login failed'))
                return
        
        # Fallback if no auth system
        self._user_login(app, username)
    
    def _do_signup(self):
        """Handle signup"""
        username = self.username_input.text.strip()
        password = self.password_input.text.strip()
        confirm = self.confirm_input.text.strip()
        
        if not username or not password:
            self._show_error('Please fill in all fields')
            return
        
        if password != confirm:
            self._show_error('Passwords do not match')
            return
        
        if len(password) < 6:
            self._show_error('Password must be at least 6 characters')
            return
        
        app = App.get_running_app()
        
        # Create user account
        # For now, create local user (in production: register with server)
        user_id = f"user_{hashlib.md5(username.encode()).hexdigest()[:8]}"
        
        # Save user credentials locally
        users_file = app.storage_path / 'users.json' if app.storage_path else None
        users = {}
        if users_file and users_file.exists():
            try:
                with open(users_file, 'r') as f:
                    users = json.load(f)
            except:
                pass
        
        if username in users:
            self._show_error('User already exists. Please login.')
            return
        
        # Store user
        users[username] = {
            'user_id': user_id,
            'password_hash': hashlib.sha256(password.encode()).hexdigest(),
            'created_at': str(__import__('time').time())
        }
        
        if users_file:
            try:
                with open(users_file, 'w') as f:
                    json.dump(users, f, indent=2)
            except Exception as e:
                print(f"[LOGIN] Could not save user: {e}")
        
        # Auto login after signup
        app.current_user = {
            'username': username,
            'user_id': user_id,
            'is_admin': False,
            'is_premium': False,
            'display_name': username
        }
        app.is_logged_in = True
        app.is_ai_purchased = False  # New users need to purchase
        app.save_config()
        
        print(f"[LOGIN] New user registered: {username}")
        app.screen_manager.current = 'platform_home'
    
    def _admin_login(self, app):
        """Admin login - unlocks everything"""
        print("[LOGIN] Admin login successful")
        
        # Set admin privileges
        app.current_user = {
            'username': 'admin',
            'user_id': 'admin_001',
            'is_admin': True,
            'is_premium': True,
            'display_name': 'Agora Admin'
        }
        app.is_ai_purchased = True
        app.is_logged_in = True
        
        # Generate license through auth
        if app.auth:
            app.auth.login('admin', self.ADMIN_PASSWORD)
        
        app.save_config()
        app.screen_manager.current = 'platform_home'
    
    def _user_login(self, app, username):
        """Regular user login (fallback)"""
        print(f"[LOGIN] User login: {username}")
        
        app.current_user = {
            'username': username,
            'user_id': f"user_{hashlib.md5(username.encode()).hexdigest()[:8]}",
            'is_admin': False,
            'is_premium': False,
            'display_name': username
        }
        app.is_logged_in = True
        app.is_ai_purchased = False
        app.save_config()
        
        app.screen_manager.current = 'platform_home'
    
    def _guest_mode(self, *args):
        """Continue as guest"""
        print("[LOGIN] Guest mode")
        
        app = App.get_running_app()
        app.current_user = {
            'username': 'guest',
            'user_id': 'guest',
            'is_admin': False,
            'is_premium': False,
            'display_name': 'Guest'
        }
        app.is_logged_in = False
        app.is_ai_purchased = False
        
        app.screen_manager.current = 'platform_home'
    
    def _show_error(self, message):
        """Show error message"""
        self.status_label.text = message
        print(f"[LOGIN ERROR] {message}")
    
    def on_enter(self, *args):
        """Called when screen is shown"""
        # Clear inputs
        self.username_input.text = ''
        self.password_input.text = ''
        self.confirm_input.text = ''
        self.status_label.text = ''
        
        # Check for existing license (auto-login)
        app = App.get_running_app()
        if app.auth and app.auth.license_manager.has_valid_license():
            print("[LOGIN] Auto-login with existing license")
            app.is_logged_in = True
            app.is_ai_purchased = True
            if app.auth.current_user:
                app.current_user = app.auth.current_user
            else:
                app.current_user = {
                    'username': 'user',
                    'user_id': 'user',
                    'is_admin': False,
                    'is_premium': True,
                    'display_name': 'User'
                }
            app.screen_manager.current = 'platform_home'
