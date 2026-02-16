#!/usr/bin/env python3
"""
Agora AI Platform - Login Screen
=================================
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
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
    """Login/Signup screen"""
    
    mode = StringProperty('login')
    
    # Admin credentials - CHANGE THIS FOR PRODUCTION
    ADMIN_USER = 'admin'
    ADMIN_PASS = 'agora2024'
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build_ui()
    
    def _build_ui(self):
        self.clear_widgets()
        
        # Main container
        main = BoxLayout(orientation='vertical', padding=dp(25), spacing=dp(15))
        
        # Background
        with main.canvas.before:
            Color(0.05, 0.05, 0.08, 1)
            self.bg_rect = RoundedRectangle(pos=main.pos, size=main.size)
        main.bind(pos=self._update_bg, size=self._update_bg)
        
        # Spacer
        main.add_widget(Widget(size_hint_y=0.1))
        
        # Title
        main.add_widget(Label(
            text='Agora AI',
            font_size=dp(36),
            bold=True,
            color=(1, 1, 1, 1),
            size_hint_y=None,
            height=dp(50)
        ))
        
        main.add_widget(Label(
            text='Offline AI Platform',
            font_size=dp(16),
            color=(0.6, 0.6, 0.8, 1),
            size_hint_y=None,
            height=dp(30)
        ))
        
        main.add_widget(Widget(size_hint_y=0.08))
        
        # Mode Toggle
        toggle = BoxLayout(
            size_hint_y=None,
            height=dp(50),
            spacing=dp(10),
            padding=[dp(20), 0]
        )
        
        self.login_btn = ToggleButton(
            text='LOGIN',
            group='mode',
            state='down',
            font_size=dp(16),
            background_color=(0.2, 0.5, 0.9, 1)
        )
        self.login_btn.bind(on_press=lambda x: self._set_mode('login'))
        
        self.signup_btn = ToggleButton(
            text='SIGN UP',
            group='mode',
            font_size=dp(16),
            background_color=(0.15, 0.15, 0.2, 1)
        )
        self.signup_btn.bind(on_press=lambda x: self._set_mode('signup'))
        
        toggle.add_widget(self.login_btn)
        toggle.add_widget(self.signup_btn)
        main.add_widget(toggle)
        
        main.add_widget(Widget(size_hint_y=0.05))
        
        # Form Card
        card = BoxLayout(
            orientation='vertical',
            padding=dp(25),
            spacing=dp(15),
            size_hint_y=None
        )
        
        # Dynamic height based on mode
        self.card_height_login = dp(200)
        self.card_height_signup = dp(280)
        card.height = self.card_height_login
        
        with card.canvas.before:
            Color(0.12, 0.12, 0.18, 1)
            RoundedRectangle(pos=card.pos, size=card.size, radius=[dp(15)])
        card.bind(pos=self._update_card, size=self._update_card)
        self.form_card = card
        
        # Username
        card.add_widget(Label(
            text='USERNAME',
            font_size=dp(12),
            color=(0.6, 0.6, 0.7, 1),
            halign='left',
            size_hint_y=None,
            height=dp(20),
            text_size=(None, None)
        ))
        
        self.user_input = TextInput(
            hint_text='Enter username',
            font_size=dp(18),
            multiline=False,
            background_color=(0.15, 0.15, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.5, 0.5, 0.5, 1),
            padding=[dp(15), dp(15)],
            size_hint_y=None,
            height=dp(55)
        )
        card.add_widget(self.user_input)
        
        # Password
        card.add_widget(Label(
            text='PASSWORD',
            font_size=dp(12),
            color=(0.6, 0.6, 0.7, 1),
            halign='left',
            size_hint_y=None,
            height=dp(20)
        ))
        
        self.pass_input = TextInput(
            hint_text='Enter password',
            font_size=dp(18),
            multiline=False,
            password=True,
            background_color=(0.15, 0.15, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.5, 0.5, 0.5, 1),
            padding=[dp(15), dp(15)],
            size_hint_y=None,
            height=dp(55)
        )
        self.pass_input.bind(on_text_validate=self._do_action)
        card.add_widget(self.pass_input)
        
        # Confirm Password (signup only)
        self.confirm_label = Label(
            text='CONFIRM PASSWORD',
            font_size=dp(12),
            color=(0.6, 0.6, 0.7, 1),
            halign='left',
            size_hint_y=None,
            height=dp(20)
        )
        card.add_widget(self.confirm_label)
        
        self.confirm_input = TextInput(
            hint_text='Confirm password',
            font_size=dp(18),
            multiline=False,
            password=True,
            background_color=(0.15, 0.15, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.5, 0.5, 0.5, 1),
            padding=[dp(15), dp(15)],
            size_hint_y=None,
            height=dp(55)
        )
        card.add_widget(self.confirm_input)
        
        # Hide confirm initially
        self.confirm_label.opacity = 0
        self.confirm_input.opacity = 0
        self.confirm_input.disabled = True
        
        main.add_widget(card)
        
        main.add_widget(Widget(size_hint_y=0.03))
        
        # Action Button
        self.action_btn = Button(
            text='LOGIN',
            font_size=dp(18),
            bold=True,
            background_color=(0.2, 0.5, 0.9, 1),
            size_hint_y=None,
            height=dp(55)
        )
        self.action_btn.bind(on_release=self._do_action)
        main.add_widget(self.action_btn)
        
        # Error Label
        self.error_label = Label(
            text='',
            font_size=dp(14),
            color=(0.9, 0.3, 0.3, 1),
            size_hint_y=None,
            height=dp(30)
        )
        main.add_widget(self.error_label)
        
        main.add_widget(Widget(size_hint_y=0.1))
        
        # Dev hint
        main.add_widget(Label(
            text='Admin: admin / agora2024',
            font_size=dp(10),
            color=(0.4, 0.4, 0.5, 1),
            size_hint_y=None,
            height=dp(20)
        ))
        
        self.add_widget(main)
    
    def _set_mode(self, mode):
        self.mode = mode
        if mode == 'login':
            self.login_btn.state = 'down'
            self.login_btn.background_color = (0.2, 0.5, 0.9, 1)
            self.signup_btn.state = 'normal'
            self.signup_btn.background_color = (0.15, 0.15, 0.2, 1)
            self.action_btn.text = 'LOGIN'
            self.confirm_label.opacity = 0
            self.confirm_input.opacity = 0
            self.confirm_input.disabled = True
            self.form_card.height = self.card_height_login
        else:
            self.signup_btn.state = 'down'
            self.signup_btn.background_color = (0.2, 0.5, 0.9, 1)
            self.login_btn.state = 'normal'
            self.login_btn.background_color = (0.15, 0.15, 0.2, 1)
            self.action_btn.text = 'SIGN UP'
            self.confirm_label.opacity = 1
            self.confirm_input.opacity = 1
            self.confirm_input.disabled = False
            self.form_card.height = self.card_height_signup
    
    def _update_bg(self, instance, value):
        if hasattr(self, 'bg_rect'):
            self.bg_rect.pos = instance.pos
            self.bg_rect.size = instance.size
    
    def _update_card(self, instance, value):
        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(0.12, 0.12, 0.18, 1)
            RoundedRectangle(pos=instance.pos, size=instance.size, radius=[dp(15)])
    
    def _do_action(self, *args):
        self.error_label.text = ''
        
        username = self.user_input.text.strip()
        password = self.pass_input.text.strip()
        
        if not username or not password:
            self.error_label.text = 'Please enter username and password'
            return
        
        app = App.get_running_app()
        
        if self.mode == 'login':
            self._do_login(app, username, password)
        else:
            confirm = self.confirm_input.text.strip()
            if password != confirm:
                self.error_label.text = 'Passwords do not match'
                return
            self._do_signup(app, username, password)
    
    def _do_login(self, app, username, password):
        # Check admin login FIRST
        if username == self.ADMIN_USER and password == self.ADMIN_PASS:
            print(f"[LOGIN] Admin login successful")
            app.current_user = {
                'username': 'admin',
                'user_id': 'admin_001',
                'is_admin': True,
                'is_premium': True,
                'display_name': 'Admin'
            }
            app.is_logged_in = True
            app.is_ai_purchased = True
            
            # Generate license
            if app.auth:
                app.auth.license_manager.generate_license('admin_001', is_admin=True)
            
            app.save_config()
            app.screen_manager.current = 'platform_home'
            return
        
        # Check regular users
        users_file = app.storage_path / 'users.json' if app.storage_path else None
        users = {}
        if users_file and users_file.exists():
            try:
                with open(users_file, 'r') as f:
                    users = json.load(f)
            except:
                pass
        
        if username in users:
            stored_hash = users[username].get('password_hash', '')
            if hashlib.sha256(password.encode()).hexdigest() == stored_hash:
                print(f"[LOGIN] User login: {username}")
                app.current_user = {
                    'username': username,
                    'user_id': users[username].get('user_id', username),
                    'is_admin': False,
                    'is_premium': False,
                    'display_name': username
                }
                app.is_logged_in = True
                app.is_ai_purchased = False
                app.save_config()
                app.screen_manager.current = 'platform_home'
                return
        
        self.error_label.text = 'Invalid username or password'
    
    def _do_signup(self, app, username, password):
        users_file = app.storage_path / 'users.json' if app.storage_path else None
        users = {}
        if users_file and users_file.exists():
            try:
                with open(users_file, 'r') as f:
                    users = json.load(f)
            except:
                pass
        
        if username in users:
            self.error_label.text = 'Username already exists'
            return
        
        # Create user
        user_id = f"usr_{hashlib.md5(username.encode()).hexdigest()[:8]}"
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
                print(f"[LOGIN] Error saving user: {e}")
        
        print(f"[LOGIN] New user: {username}")
        app.current_user = {
            'username': username,
            'user_id': user_id,
            'is_admin': False,
            'is_premium': False,
            'display_name': username
        }
        app.is_logged_in = True
        app.is_ai_purchased = False
        app.save_config()
        app.screen_manager.current = 'platform_home'
    
    def on_enter(self, *args):
        self.user_input.text = ''
        self.pass_input.text = ''
        self.confirm_input.text = ''
        self.error_label.text = ''
        
        # Auto-login if has license
        app = App.get_running_app()
        if app.auth and app.auth.license_manager.has_valid_license():
            app.is_logged_in = True
            app.is_ai_purchased = True
            app.screen_manager.current = 'platform_home'
