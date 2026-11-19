#!/usr/bin/env python3
"""
Agora AI Platform - Modern Login Screen
=======================================
Creative, abstract, classy design with gradients and glassmorphism.
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Rectangle, Ellipse
from kivy.graphics.vertex_instructions import Line
from kivy.properties import StringProperty, ListProperty
from kivy.metrics import dp
from kivy.app import App
from kivy.clock import Clock
import hashlib
import json


class ModernTextInput(TextInput):
    """Custom styled text input"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_active = ''
        self.background_disabled = ''
        self.background_color = (0.1, 0.1, 0.15, 0.6)
        self.cursor_color = (0.4, 0.8, 1, 1)
        self.foreground_color = (1, 1, 1, 1)
        self.hint_text_color = (0.5, 0.5, 0.6, 1)
        self.padding = [dp(20), dp(15)]
        self.font_size = dp(16)
        self.multiline = False


class GradientButton(Button):
    """Button with gradient effect"""
    gradient_colors = ListProperty([(0.2, 0.5, 0.9, 1), (0.4, 0.3, 0.9, 1)])
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)
        self.color = (1, 1, 1, 1)
        self.bold = True
        self.font_size = dp(16)
        # CRITICAL: Schedule canvas update after initialization
        Clock.schedule_once(self._init_canvas, 0)
    
    def _init_canvas(self, dt):
        self.bind(pos=self._update_canvas, size=self._update_canvas)
        self._update_canvas()
    
    def _update_canvas(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.gradient_colors[0])
            self.rect = RoundedRectangle(
                pos=self.pos, 
                size=self.size,
                radius=[dp(25)]
            )


class LoginScreen(Screen):
    """Modern creative login screen"""
    
    mode = StringProperty('login')
    ADMIN_USER = 'admin'
    ADMIN_PASS = 'agora2024'
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # CRITICAL: Schedule UI build to avoid canvas issues during init
        Clock.schedule_once(self._build_ui, 0)
    
    def _build_ui(self, *args):
        """Responsive sign-in/sign-up without overlapping fixed-height widgets."""
        self.clear_widgets()
        root = FloatLayout()
        with root.canvas.before:
            Color(0.02, 0.02, 0.08, 1)
            self.bg_rect = Rectangle(pos=root.pos, size=root.size)
            Color(.15, .05, .25, .30)
            self.orb1 = Ellipse(pos=(dp(-100), dp(400)),
                                size=(dp(400), dp(400)))
            Color(.05, .15, .25, .22)
            self.orb2 = Ellipse(pos=(dp(200), dp(-100)),
                                size=(dp(350), dp(350)))
            Color(.1, .3, .4, .15)
            self.orb3 = Ellipse(pos=(dp(100), dp(600)),
                                size=(dp(300), dp(300)))
        root.bind(pos=self._update_bg, size=self._update_bg)

        viewport = ScrollView(
            do_scroll_x=False, bar_width=dp(4), size_hint=(1, 1),
        )
        content = BoxLayout(
            orientation='vertical', size_hint_y=None,
            padding=[dp(20), dp(26), dp(20), dp(30)],
            spacing=dp(15),
        )
        content.bind(minimum_height=content.setter('height'))
        viewport.add_widget(content)
        root.add_widget(viewport)

        logo = BoxLayout(
            orientation='vertical', size_hint_y=None,
            height=dp(112), spacing=dp(6),
        )
        logo.add_widget(Label(
            text='AGORA', font_size='40sp', bold=True, color=(1, 1, 1, 1),
        ))
        logo.add_widget(Label(
            text='AI PLATFORM', font_size='15sp',
            color=(.4, .8, 1, 1), bold=True,
        ))
        content.add_widget(logo)

        toggle = BoxLayout(
            size_hint_y=None, height=dp(52), spacing=dp(8),
        )
        self.login_btn = ToggleButton(
            text='SIGN IN', group='mode', state='down',
            font_size='14sp', background_color=(.2, .5, .9, .8),
            background_normal='', background_down='',
            color=(1, 1, 1, 1), bold=True,
        )
        self.signup_btn = ToggleButton(
            text='CREATE ACCOUNT', group='mode',
            font_size='14sp', background_normal='', background_down='',
            background_color=(.1, .1, .15, .5), color=(.7, .7, .8, 1),
        )
        self.login_btn.bind(on_press=lambda *_: self._set_mode('login'))
        self.signup_btn.bind(on_press=lambda *_: self._set_mode('signup'))
        toggle.add_widget(self.login_btn)
        toggle.add_widget(self.signup_btn)
        content.add_widget(toggle)

        card = self._create_glass_card()
        self.user_input = ModernTextInput(
            hint_text='Username or Email', size_hint_y=None, height=dp(52),
        )
        card.add_widget(self._create_input_container('USERNAME', self.user_input))
        self.pass_input = ModernTextInput(
            hint_text='Password', password=True,
            size_hint_y=None, height=dp(52),
        )
        self.pass_input.bind(on_text_validate=self._do_action)
        card.add_widget(self._create_input_container('PASSWORD', self.pass_input))

        self.confirm_container = BoxLayout(
            orientation='vertical', size_hint_y=None, height=0, opacity=0,
        )
        self.confirm_input = ModernTextInput(
            hint_text='Confirm Password', password=True,
            size_hint_y=None, height=dp(52),
        )
        self.confirm_container.add_widget(
            self._create_input_container('CONFIRM PASSWORD', self.confirm_input))
        card.add_widget(self.confirm_container)

        self.error_label = Label(
            text='', font_size='13sp', color=(1, .4, .4, 1),
            halign='center', size_hint_y=None, height=dp(30),
        )
        self.error_label.bind(width=lambda widget, width: setattr(
            widget, 'text_size', (max(60, width - dp(8)), None)))
        card.add_widget(self.error_label)

        self.action_btn = GradientButton(
            text='SIGN IN', size_hint_y=None, height=dp(55),
            gradient_colors=[(.2, .5, .9, 1), (.5, .3, .8, 1)],
        )
        self.action_btn.bind(on_release=self._do_action)
        card.add_widget(self.action_btn)
        # The card follows its real form contents; no overlapping invisible
        # confirmation field or arbitrary fixed 360dp clipping.
        card.bind(minimum_height=card.setter('height'))
        content.add_widget(card)
        content.add_widget(Label(
            text='Agora local preview build', font_size='12sp',
            size_hint_y=None, height=dp(35),
            color=(.5, .55, .7, .9),
        ))
        self.add_widget(root)
        self._set_mode('login')

    def _create_glass_card(self):
        """Create glassmorphism card"""
        card = BoxLayout(
            orientation='vertical',
            padding=dp(16),
            spacing=dp(12),
            size_hint_y=None,
            height=dp(360)
        )
        
        with card.canvas.before:
            Color(1, 1, 1, 0.05)
            self.glass_rect = RoundedRectangle(
                pos=card.pos,
                size=card.size,
                radius=[dp(30)]
            )
            Color(0.4, 0.6, 1, 0.1)
            Line(
                rounded_rectangle=(0, 0, 100, 100, dp(30)),
                width=dp(1.5)
            )
        
        card.bind(pos=self._update_glass, size=self._update_glass)
        return card
    
    def _create_input_container(self, label_text, input_widget):
        """Create styled input container"""
        container = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=dp(85),
            spacing=dp(5)
        )
        
        container.add_widget(Label(
            text=label_text,
            font_size=dp(11),
            color=(0.6, 0.7, 0.9, 0.8),
            bold=True,
            halign='left',
            size_hint_y=None,
            height=dp(20),
            text_size=(None, None)
        ))
        
        container.add_widget(input_widget)
        return container
    
    def _update_bg(self, instance, value):
        if hasattr(self, 'bg_rect'):
            self.bg_rect.pos = instance.pos
            self.bg_rect.size = instance.size
    
    def _update_glass(self, instance, value):
        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(1, 1, 1, 0.05)
            RoundedRectangle(
                pos=instance.pos,
                size=instance.size,
                radius=[dp(30)]
            )
            Color(0.4, 0.6, 1, 0.1)
            Line(
                rounded_rectangle=(instance.x, instance.y, instance.width, instance.height, dp(30)),
                width=dp(1.5)
            )
    
    def _set_mode(self, mode):
        self.mode = mode
        if mode == 'login':
            self.login_btn.state = 'down'
            self.login_btn.background_color = (0.2, 0.5, 0.9, 0.8)
            self.login_btn.color = (1, 1, 1, 1)
            self.signup_btn.state = 'normal'
            self.signup_btn.background_color = (0.1, 0.1, 0.15, 0.5)
            self.signup_btn.color = (0.6, 0.6, 0.7, 1)
            self.action_btn.text = 'SIGN IN'
            self.action_btn.gradient_colors = [(0.2, 0.5, 0.9, 1), (0.5, 0.3, 0.8, 1)]
            self.confirm_container.opacity = 0
            self.confirm_container.height = 0
        else:
            self.signup_btn.state = 'down'
            self.signup_btn.background_color = (0.2, 0.5, 0.9, 0.8)
            self.signup_btn.color = (1, 1, 1, 1)
            self.login_btn.state = 'normal'
            self.login_btn.background_color = (0.1, 0.1, 0.15, 0.5)
            self.login_btn.color = (0.6, 0.6, 0.7, 1)
            self.action_btn.text = 'CREATE ACCOUNT'
            self.action_btn.gradient_colors = [(0.9, 0.3, 0.5, 1), (0.7, 0.2, 0.6, 1)]
            self.confirm_container.opacity = 1
            self.confirm_container.height = dp(85)
    
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
            except:
                pass
        
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
        # Schedule clear to avoid canvas issues
        Clock.schedule_once(self._clear_inputs, 0.1)
        
        # Auto-login if has license
        app = App.get_running_app()
        if app.auth and app.auth.license_manager.has_valid_license():
            app.is_logged_in = True
            app.is_ai_purchased = True
            app.screen_manager.current = 'platform_home'
    
    def _clear_inputs(self, dt):
        self.user_input.text = ''
        self.pass_input.text = ''
        self.confirm_input.text = ''
        self.error_label.text = ''
