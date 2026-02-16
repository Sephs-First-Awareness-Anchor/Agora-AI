#!/usr/bin/env python3
"""
Agora AI Platform - Modern Home Screen
======================================
Creative, abstract, modern design with gradients and animations.
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.uix.widget import Widget
from kivy.graphics import Color, RoundedRectangle, Ellipse, Line
from kivy.graphics.vertex_instructions import Bezier
from kivy.properties import StringProperty, NumericProperty, BooleanProperty, ListProperty
from kivy.metrics import dp
from kivy.app import App
from kivy.animation import Animation
from kivy.clock import Clock


class AnimatedButton(Button):
    """Button with hover/press animations"""
    base_color = ListProperty([0.2, 0.5, 0.9, 1])
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ''
        self.background_down = ''
        self.background_color = (0, 0, 0, 0)
        self.color = (1, 1, 1, 1)
        self.bold = True
        self.font_size = dp(16)
        self.bind(pos=self._update_canvas, size=self._update_canvas)
        self.bind(on_press=self._on_press)
        self.bind(on_release=self._on_release)
    
    def _update_canvas(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.base_color)
            RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[dp(20)]
            )
    
    def _on_press(self, *args):
        anim = Animation(opacity=0.8, duration=0.1)
        anim.start(self)
    
    def _on_release(self, *args):
        anim = Animation(opacity=1, duration=0.1)
        anim.start(self)


class GlassCard(BoxLayout):
    """Glassmorphism card widget"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self._update_canvas, size=self._update_canvas)
    
    def _update_canvas(self, instance, value):
        instance.canvas.before.clear()
        with instance.canvas.before:
            # Frosted glass effect
            Color(1, 1, 1, 0.08)
            RoundedRectangle(
                pos=instance.pos,
                size=instance.size,
                radius=[dp(24)]
            )
            # Glow border
            Color(0.5, 0.7, 1, 0.15)
            Line(
                rounded_rectangle=(
                    instance.x, instance.y,
                    instance.width, instance.height, dp(24)
                ),
                width=dp(1)
            )


class PlatformHomeScreen(Screen):
    """Modern creative home screen"""
    
    public_handle = StringProperty("User")
    agora_credits = NumericProperty(0)
    is_ai_purchased = BooleanProperty(False)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._build_ui()
    
    def _build_ui(self):
        self.clear_widgets()
        
        # Root with animated background
        root = FloatLayout()
        
        # Abstract gradient background
        with root.canvas.before:
            # Deep space base
            Color(0.015, 0.015, 0.06, 1)
            self.bg_rect = RoundedRectangle(pos=root.pos, size=root.size)
            
            # Gradient orbs for depth
            Color(0.25, 0.1, 0.4, 0.25)
            self.orb1 = Ellipse(pos=(dp(-50), dp(500)), size=(dp(350), dp(350)))
            
            Color(0.1, 0.25, 0.4, 0.2)
            self.orb2 = Ellipse(pos=(dp(220), dp(-50)), size=(dp(300), dp(300)))
            
            Color(0.15, 0.4, 0.35, 0.15)
            self.orb3 = Ellipse(pos=(dp(50), dp(650)), size=(dp(250), dp(250)))
        
        root.bind(pos=self._update_bg, size=self._update_bg)
        
        # Scrollable content
        scroll = ScrollView(
            pos_hint={'center_x': 0.5, 'center_y': 0.5},
            size_hint=(0.95, 0.95)
        )
        
        content = BoxLayout(
            orientation='vertical',
            padding=dp(20),
            spacing=dp(20),
            size_hint_y=None
        )
        content.bind(minimum_height=content.setter('height'))
        
        # Header with glass effect
        header = self._create_glass_container(dp(120))
        
        header_content = BoxLayout(
            orientation='vertical',
            padding=dp(20)
        )
        
        header_content.add_widget(Label(
            text='AGORA AI',
            font_size=dp(28),
            bold=True,
            color=(1, 1, 1, 1)
        ))
        
        self.handle_display = Label(
            text=f'Welcome, {self.public_handle}',
            font_size=dp(16),
            color=(0.6, 0.8, 1, 0.9)
        )
        header_content.add_widget(self.handle_display)
        
        header.add_widget(header_content)
        content.add_widget(header)
        
        # AI Status Card - The star of the show
        status_card = self._create_glass_container(dp(240))
        status_content = BoxLayout(
            orientation='vertical',
            padding=dp(25),
            spacing=dp(10)
        )
        
        # Status indicator with pulse
        status_box = BoxLayout(
            size_hint_y=None,
            height=dp(40),
            padding=[dp(20), 0]
        )
        
        # Status dot
        status_color = (0.3, 0.9, 0.5, 1) if self.is_ai_purchased else (0.9, 0.5, 0.3, 1)
        with status_box.canvas.before:
            Color(*status_color)
            self.status_dot = Ellipse(pos=(0, 0), size=(dp(12), dp(12)))
        
        self.status_label = Label(
            text='ACTIVE' if self.is_ai_purchased else 'LOCKED',
            font_size=dp(14),
            bold=True,
            color=status_color,
            halign='left'
        )
        status_box.add_widget(self.status_label)
        
        status_content.add_widget(status_box)
        
        # Big AI name
        status_content.add_widget(Label(
            text='AI Companion',
            font_size=dp(32),
            bold=True,
            color=(1, 1, 1, 1)
        ))
        
        status_content.add_widget(Label(
            text='Your offline personal AI' if self.is_ai_purchased else 'Purchase to unlock',
            font_size=dp(14),
            color=(0.7, 0.7, 0.8, 1)
        ))
        
        status_content.add_widget(Widget(size_hint_y=0.1))
        
        # Main action button
        if self.is_ai_purchased:
            action_btn = AnimatedButton(
                text='LAUNCH AI',
                size_hint_y=None,
                height=dp(60),
                base_color=[0.2, 0.7, 0.5, 1]
            )
            action_btn.bind(on_release=self._launch_ai)
        else:
            action_btn = AnimatedButton(
                text='UNLOCK AI',
                size_hint_y=None,
                height=dp(60),
                base_color=[0.9, 0.4, 0.2, 1]
            )
            action_btn.bind(on_release=self._go_purchase)
        
        status_content.add_widget(action_btn)
        status_card.add_widget(status_content)
        content.add_widget(status_card)
        
        # Quick Actions Grid
        content.add_widget(Label(
            text='EXPLORE',
            font_size=dp(13),
            bold=True,
            color=(0.5, 0.6, 0.8, 0.8),
            halign='left',
            size_hint_y=None,
            height=dp(30),
            text_size=(None, None)
        ))
        
        grid = GridLayout(
            cols=2,
            spacing=dp(15),
            size_hint_y=None,
            height=dp(280)
        )
        
        actions = [
            ('Hubs', 'Find meetups', (0.2, 0.5, 0.9, 0.8)),
            ('Rewards', 'Achievements', (0.5, 0.3, 0.8, 0.8)),
            ('Classes', 'Training', (0.8, 0.3, 0.5, 0.8)),
            ('Library', 'Knowledge', (0.3, 0.7, 0.6, 0.8)),
        ]
        
        for title, subtitle, color in actions:
            grid.add_widget(self._create_action_card(title, subtitle, color))
        
        content.add_widget(grid)
        
        content.add_widget(Widget(size_hint_y=0.1))
        
        scroll.add_widget(content)
        root.add_widget(scroll)
        self.add_widget(root)
    
    def _create_glass_container(self, height):
        """Create glassmorphism container"""
        container = BoxLayout(
            orientation='vertical',
            size_hint_y=None,
            height=height
        )
        
        with container.canvas.before:
            Color(1, 1, 1, 0.06)
            RoundedRectangle(
                pos=container.pos,
                size=container.size,
                radius=[dp(24)]
            )
            Color(0.5, 0.7, 1, 0.12)
            Line(
                rounded_rectangle=(0, 0, 100, height, dp(24)),
                width=dp(1)
            )
        
        container.bind(pos=self._update_glass, size=self._update_glass)
        return container
    
    def _create_action_card(self, title, subtitle, color):
        """Create action card"""
        card = BoxLayout(
            orientation='vertical',
            padding=dp(20),
            spacing=dp(5)
        )
        
        with card.canvas.before:
            Color(1, 1, 1, 0.05)
            RoundedRectangle(
                pos=card.pos,
                size=card.size,
                radius=[dp(20)]
            )
            Color(*color[:3], 0.3)
            Line(
                rounded_rectangle=(0, 0, 100, 100, dp(20)),
                width=dp(1.5)
            )
        
        card.bind(pos=self._update_card, size=self._update_card)
        
        card.add_widget(Label(
            text=title,
            font_size=dp(20),
            bold=True,
            color=(1, 1, 1, 1)
        ))
        
        card.add_widget(Label(
            text=subtitle,
            font_size=dp(12),
            color=(0.7, 0.7, 0.8, 1)
        ))
        
        # Invisible button for click
        btn = Button(
            background_color=(0, 0, 0, 0),
            size_hint=(1, 1)
        )
        btn.bind(on_release=lambda x: print(f'[HOME] {title}'))
        card.add_widget(btn)
        
        return card
    
    def _update_bg(self, instance, value):
        self.bg_rect.pos = instance.pos
        self.bg_rect.size = instance.size
    
    def _update_glass(self, instance, value):
        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(1, 1, 1, 0.06)
            RoundedRectangle(
                pos=instance.pos,
                size=instance.size,
                radius=[dp(24)]
            )
            Color(0.5, 0.7, 1, 0.12)
            Line(
                rounded_rectangle=(instance.x, instance.y, instance.width, instance.height, dp(24)),
                width=dp(1)
            )
    
    def _update_card(self, instance, value):
        instance.canvas.before.clear()
        with instance.canvas.before:
            Color(1, 1, 1, 0.05)
            RoundedRectangle(
                pos=instance.pos,
                size=instance.size,
                radius=[dp(20)]
            )
    
    def _launch_ai(self, *args):
        app = App.get_running_app()
        app.screen_manager.current = 'onboarding'
    
    def _go_purchase(self, *args):
        app = App.get_running_app()
        app.screen_manager.current = 'purchase'
    
    def on_enter(self, *args):
        app = App.get_running_app()
        
        if app.current_user:
            self.public_handle = app.current_user.get('display_name', 'User')
        self.is_ai_purchased = getattr(app, 'is_ai_purchased', False)
        
        self.handle_display.text = f'Welcome, {self.public_handle}'
        self._build_ui()
