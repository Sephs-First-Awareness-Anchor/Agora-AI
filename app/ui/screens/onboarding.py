#!/usr/bin/env python3
"""
Agora AI - Onboarding Screen
================================
Authors: Sunni (Sir) Morningstar & Cael Devo

First-run onboarding flow for new users.
Collects: AI name, favorite color, mode, user name, birthday.
"""

from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.button import Button
from kivy.uix.togglebutton import ToggleButton
from kivy.uix.widget import Widget
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle, Line
from kivy.animation import Animation
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.properties import StringProperty, NumericProperty, ListProperty
from kivy.app import App
from kivy.metrics import dp

from app.ui.components.theme import COLOR_THEMES, ThemeManager


class ColorButton(Button):
    """Circular button for color selection"""
    color_name = StringProperty('')
    is_selected = False
    
    def __init__(self, color_name: str, **kwargs):
        super().__init__(**kwargs)
        self.color_name = color_name
        self.size_hint = (None, None)
        self.size = (60, 60)
        self.background_color = (0, 0, 0, 0)
        self.background_normal = ''
        self.background_down = ''
        
        # Get the accent color for this theme
        theme = COLOR_THEMES.get(color_name, COLOR_THEMES['blue'])
        from kivy.utils import get_color_from_hex
        self.button_color = get_color_from_hex(theme['accent'])
        
        self.bind(pos=self._update_canvas, size=self._update_canvas)
    
    def _update_canvas(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            # Button fill
            Color(*self.button_color)
            self.bg_rect = RoundedRectangle(
                pos=self.pos,
                size=self.size,
                radius=[30]
            )
            
            # Selection ring if selected
            if self.is_selected:
                Color(1, 1, 1, 1)
                Line(
                    rounded_rectangle=[self.x - 4, self.y - 4, 
                                       self.width + 8, self.height + 8, 15],
                    width=2
                )
    
    def select(self):
        self.is_selected = True
        self._update_canvas()
        
        # Pulse animation
        anim = Animation(size=(70, 70), duration=0.1) + Animation(size=(60, 60), duration=0.1)
        anim.start(self)
    
    def deselect(self):
        self.is_selected = False
        self._update_canvas()


class ModeToggle(BoxLayout):
    """Toggle between Introvert and Extrovert modes"""
    selected_mode = StringProperty('introvert')
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.orientation = 'horizontal'
        self.size_hint_y = None
        self.height = dp(60)
        self.spacing = 10
        self.padding = [20, 0]
        
        # Introvert button
        self.introvert_btn = ToggleButton(
            text='🌙 Introvert',
            group='mode',
            state='down',
            font_size='16sp',
            background_color=(0.2, 0.2, 0.3, 1),
            background_normal='',
            color=(1, 1, 1, 1)
        )
        self.introvert_btn.bind(on_press=lambda x: self._select('introvert'))
        
        # Extrovert button
        self.extrovert_btn = ToggleButton(
            text='☀️ Extrovert',
            group='mode',
            state='normal',
            font_size='16sp',
            background_color=(0.15, 0.15, 0.2, 1),
            background_normal='',
            color=(0.7, 0.7, 0.7, 1)
        )
        self.extrovert_btn.bind(on_press=lambda x: self._select('extrovert'))
        
        self.add_widget(self.introvert_btn)
        self.add_widget(self.extrovert_btn)
    
    def _select(self, mode):
        self.selected_mode = mode
        if mode == 'introvert':
            self.introvert_btn.background_color = (0.2, 0.2, 0.3, 1)
            self.introvert_btn.color = (1, 1, 1, 1)
            self.extrovert_btn.background_color = (0.15, 0.15, 0.2, 1)
            self.extrovert_btn.color = (0.7, 0.7, 0.7, 1)
        else:
            self.extrovert_btn.background_color = (0.3, 0.25, 0.2, 1)
            self.extrovert_btn.color = (1, 1, 1, 1)
            self.introvert_btn.background_color = (0.15, 0.15, 0.2, 1)
            self.introvert_btn.color = (0.7, 0.7, 0.7, 1)


class OnboardingScreen(Screen):
    """
    Multi-step onboarding flow.
    
    Steps:
    1. Welcome + AI Name
    2. Favorite Color
    3. Mode Selection
    4. User Name + Birthday
    5. Confirmation
    """
    
    current_step = NumericProperty(0)
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # User data
        self.ai_name = ''
        self.favorite_color = 'blue'
        self.mode = 'introvert'
        self.user_name = ''
        self.birthday = ''
        
        # Color buttons reference
        self.color_buttons = {}
        
        # Build initial UI
        self._build_ui()
    
    def _build_ui(self):
        """Build the onboarding UI"""
        self.clear_widgets()
        
        # Main container
        self.main_layout = FloatLayout()
        
        # Background
        with self.main_layout.canvas.before:
            Color(0.05, 0.05, 0.08, 1)
            self.bg_rect = RoundedRectangle(pos=self.pos, size=Window.size)
        
        # Content can exceed the viewport when Android font scaling, screen
        # height or the keyboard changes. Never clip fields or navigation.
        self.scroll = ScrollView(size_hint=(1, 1), do_scroll_x=False,
                                 bar_width=dp(4))
        self.content = BoxLayout(
            orientation='vertical',
            padding=[dp(18), dp(24), dp(18), dp(26)],
            spacing=dp(14),
            size_hint=(1, None),
        )
        self.content.bind(minimum_height=self._fit_content)
        self.scroll.bind(height=self._fit_content)
        self.scroll.add_widget(self.content)
        self.main_layout.add_widget(self.scroll)
        self.add_widget(self.main_layout)

        # The content can scroll vertically on small screens.
        self._show_step(0)

    def _fit_content(self, *args):
        self.content.height = max(
            self.content.minimum_height, self.scroll.height - dp(4))
    
    def _show_step(self, step: int):
        """Show a specific onboarding step"""
        self.content.clear_widgets()
        self.current_step = step
        self.scroll.scroll_y = 1
        
        if step == 0:
            self._build_step_welcome()
        elif step == 1:
            self._build_step_color()
        elif step == 2:
            self._build_step_mode()
        elif step == 3:
            self._build_step_user()
        elif step == 4:
            self._build_step_confirm()
    
    def _build_step_welcome(self):
        """Step 1: Welcome and AI Name"""
        # Spacer
        self.content.add_widget(Widget(size_hint_y=0.1))
        
        # Title
        title = Label(
            text="[b]Welcome to Agora[/b]",
            font_size='32sp',
            markup=True,
            size_hint_y=None,
            height=dp(50),
            color=(1, 1, 1, 1)
        )
        self.content.add_widget(title)
        
        # Subtitle
        subtitle = Label(
            text="Your own offline AI companion",
            font_size='18sp',
            size_hint_y=None,
            height=dp(30),
            color=(0.7, 0.7, 0.7, 1)
        )
        self.content.add_widget(subtitle)
        
        # Spacer
        self.content.add_widget(Widget(size_hint_y=0.1))
        
        # Instruction
        instruction = Label(
            text="What would you like to name your companion?",
            font_size='16sp',
            size_hint_y=None,
            height=dp(40),
            color=(0.9, 0.9, 0.9, 1)
        )
        self.content.add_widget(instruction)
        
        # Subtle hint - no reveal of the magic
        hint = Label(
            text="[i]Choose wisely — names have power[/i]",
            font_size='14sp',
            markup=True,
            size_hint_y=None,
            height=dp(30),
            color=(0.5, 0.5, 0.6, 1)
        )
        self.content.add_widget(hint)
        
        # Name input
        self.ai_name_input = TextInput(
            hint_text='Enter a name...',
            font_size='20sp',
            multiline=False,
            size_hint_y=None,
            height=dp(56),
            background_color=(0.15, 0.15, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.5, 0.5, 0.5, 1),
            padding=[dp(15), dp(14)],
            cursor_color=(1, 1, 1, 1)
        )
        self.content.add_widget(self.ai_name_input)
        
        # Spacer
        self.content.add_widget(Widget(size_hint_y=0.2))
        
        # Next button
        next_btn = Button(
            text='Continue',
            font_size='18sp',
            size_hint=(1, None),
            height=dp(55),
            background_color=(0.2, 0.4, 0.8, 1),
            background_normal='',
            color=(1, 1, 1, 1)
        )
        next_btn.bind(on_release=self._next_from_welcome)
        self.content.add_widget(next_btn)
    
    def _build_step_color(self):
        """Step 2: Favorite Color"""
        # Spacer
        self.content.add_widget(Widget(size_hint_y=0.05))
        
        # Title
        title = Label(
            text="[b]Your favorite color[/b]",
            font_size='28sp',
            markup=True,
            size_hint_y=None,
            height=dp(50),
            color=(1, 1, 1, 1)
        )
        self.content.add_widget(title)
        
        # Instruction
        instruction = Label(
            text=f"A small influence on {self.ai_name}'s beginnings",
            font_size='16sp',
            size_hint_y=None,
            height=dp(40),
            color=(0.8, 0.8, 0.8, 1)
        )
        instruction.halign = 'center'
        instruction.valign = 'middle'
        instruction.bind(width=lambda w, width: setattr(
            w, 'text_size', (max(dp(90), width - dp(12)), None)))
        instruction.bind(texture_size=lambda w, size: setattr(
            w, 'height', max(dp(40), size[1] + dp(12))))
        self.content.add_widget(instruction)
        
        # Color grid
        color_grid = GridLayout(
            cols=5,
            spacing=15,
            size_hint_y=None,
            height=200,
            padding=[20, 20]
        )
        
        colors = ['red', 'orange', 'yellow', 'green', 'cyan', 
                  'blue', 'purple', 'pink', 'white', 'black']
        
        self.color_buttons = {}
        for color in colors:
            btn = ColorButton(color_name=color)
            btn.bind(on_release=lambda x, c=color: self._select_color(c))
            self.color_buttons[color] = btn
            color_grid.add_widget(btn)
        
        # Pre-select blue
        self.color_buttons['blue'].select()
        
        self.content.add_widget(color_grid)
        
        # Color name label
        self.color_label = Label(
            text="Ocean Depths",
            font_size='18sp',
            size_hint_y=None,
            height=dp(40),
            color=(0.6, 0.8, 1, 1)
        )
        self.content.add_widget(self.color_label)
        
        # Spacer
        self.content.add_widget(Widget(size_hint_y=0.15))
        
        # Navigation
        nav = BoxLayout(size_hint_y=None, height=dp(55), spacing=dp(15))
        
        back_btn = Button(
            text='Back',
            font_size='16sp',
            background_color=(0.3, 0.3, 0.35, 1),
            background_normal='',
            color=(1, 1, 1, 1)
        )
        back_btn.bind(on_release=lambda x: self._show_step(0))
        
        next_btn = Button(
            text='Continue',
            font_size='16sp',
            background_color=(0.2, 0.4, 0.8, 1),
            background_normal='',
            color=(1, 1, 1, 1)
        )
        next_btn.bind(on_release=lambda x: self._show_step(2))
        
        nav.add_widget(back_btn)
        nav.add_widget(next_btn)
        self.content.add_widget(nav)
    
    def _build_step_mode(self):
        """Step 3: Mode Selection"""
        # Spacer
        self.content.add_widget(Widget(size_hint_y=0.1))
        
        # Title
        title = Label(
            text="[b]Choose a Mode[/b]",
            font_size='28sp',
            markup=True,
            size_hint_y=None,
            height=dp(50),
            color=(1, 1, 1, 1)
        )
        self.content.add_widget(title)
        
        # Spacer
        self.content.add_widget(Widget(size_hint_y=0.05))
        
        # Mode toggle
        self.mode_toggle = ModeToggle()
        self.content.add_widget(self.mode_toggle)
        
        # Spacer
        self.content.add_widget(Widget(size_hint_y=0.03))
        
        # Mode descriptions
        intro_desc = Label(
            text="[b]Introvert[/b]: Waits for you to speak first.\nListens quietly. Minimal proactive interaction.",
            font_size='14sp',
            markup=True,
            size_hint_y=None,
            height=dp(60),
            color=(0.7, 0.7, 0.8, 1),
            halign='center'
        )
        intro_desc.bind(size=intro_desc.setter('text_size'))
        self.content.add_widget(intro_desc)
        
        extro_desc = Label(
            text="[b]Extrovert[/b]: May initiate conversation.\nMore expressive. Always listening.",
            font_size='14sp',
            markup=True,
            size_hint_y=None,
            height=dp(60),
            color=(0.8, 0.7, 0.6, 1),
            halign='center'
        )
        extro_desc.bind(size=extro_desc.setter('text_size'))
        self.content.add_widget(extro_desc)
        
        # Spacer
        self.content.add_widget(Widget(size_hint_y=0.15))
        
        # Navigation
        nav = BoxLayout(size_hint_y=None, height=dp(55), spacing=dp(15))
        
        back_btn = Button(
            text='Back',
            font_size='16sp',
            background_color=(0.3, 0.3, 0.35, 1),
            background_normal='',
            color=(1, 1, 1, 1)
        )
        back_btn.bind(on_release=lambda x: self._show_step(1))
        
        next_btn = Button(
            text='Continue',
            font_size='16sp',
            background_color=(0.2, 0.4, 0.8, 1),
            background_normal='',
            color=(1, 1, 1, 1)
        )
        next_btn.bind(on_release=self._next_from_mode)
        
        nav.add_widget(back_btn)
        nav.add_widget(next_btn)
        self.content.add_widget(nav)
    
    def _build_step_user(self):
        """Step 4: User Info"""
        # Spacer
        self.content.add_widget(Widget(size_hint_y=0.05))
        
        # Title
        title = Label(
            text="[b]Tell me about you[/b]",
            font_size='28sp',
            markup=True,
            size_hint_y=None,
            height=dp(50),
            color=(1, 1, 1, 1)
        )
        self.content.add_widget(title)
        
        subtitle = Label(
            text=f"So {self.ai_name} knows who you are",
            font_size='16sp',
            size_hint_y=None,
            height=dp(30),
            color=(0.7, 0.7, 0.7, 1)
        )
        self.content.add_widget(subtitle)
        
        # Spacer
        self.content.add_widget(Widget(size_hint_y=0.05))
        
        # Your name
        name_label = Label(
            text="Your Name",
            font_size='14sp',
            size_hint_y=None,
            height=dp(25),
            color=(0.8, 0.8, 0.8, 1),
            halign='left'
        )
        name_label.bind(size=name_label.setter('text_size'))
        self.content.add_widget(name_label)
        
        self.user_name_input = TextInput(
            hint_text='What should I call you?',
            font_size='18sp',
            multiline=False,
            size_hint_y=None,
            height=dp(56),
            background_color=(0.15, 0.15, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.5, 0.5, 0.5, 1),
            padding=[dp(15), dp(14)],
            cursor_color=(1, 1, 1, 1)
        )
        self.content.add_widget(self.user_name_input)
        
        # Spacer
        self.content.add_widget(Widget(size_hint_y=0.03))
        
        # Birthday
        bday_label = Label(
            text="Your Birthday",
            font_size='14sp',
            size_hint_y=None,
            height=dp(25),
            color=(0.8, 0.8, 0.8, 1),
            halign='left'
        )
        bday_label.bind(size=bday_label.setter('text_size'))
        self.content.add_widget(bday_label)
        
        self.birthday_input = TextInput(
            hint_text='MM/DD/YYYY',
            font_size='18sp',
            multiline=False,
            size_hint_y=None,
            height=dp(56),
            background_color=(0.15, 0.15, 0.2, 1),
            foreground_color=(1, 1, 1, 1),
            hint_text_color=(0.5, 0.5, 0.5, 1),
            padding=[dp(15), dp(14)],
            cursor_color=(1, 1, 1, 1),
            input_filter=lambda text, from_undo: text if text.isdigit() or text == '/' else ''
        )
        self.content.add_widget(self.birthday_input)
        
        # Spacer
        self.content.add_widget(Widget(size_hint_y=0.15))
        
        # Navigation
        nav = BoxLayout(size_hint_y=None, height=dp(55), spacing=dp(15))
        
        back_btn = Button(
            text='Back',
            font_size='16sp',
            background_color=(0.3, 0.3, 0.35, 1),
            background_normal='',
            color=(1, 1, 1, 1)
        )
        back_btn.bind(on_release=lambda x: self._show_step(2))
        
        next_btn = Button(
            text='Continue',
            font_size='16sp',
            background_color=(0.2, 0.4, 0.8, 1),
            background_normal='',
            color=(1, 1, 1, 1)
        )
        next_btn.bind(on_release=self._next_from_user)
        
        nav.add_widget(back_btn)
        nav.add_widget(next_btn)
        self.content.add_widget(nav)
    
    def _build_step_confirm(self):
        """Step 5: Confirmation"""
        # Pre-arm the AI runtime for summoning (Contract Requirement)
        try:
            app = App.get_running_app()
            if hasattr(app, 'ai_runtime') and app.ai_runtime:
                app.ai_runtime.prepare_for_summon()
        except Exception:
            pass

        # Spacer
        self.content.add_widget(Widget(size_hint_y=0.1))
        
        # Title
        title = Label(
            text="[b]Ready to Meet?[/b]",
            font_size='28sp',
            markup=True,
            size_hint_y=None,
            height=dp(50),
            color=(1, 1, 1, 1)
        )
        self.content.add_widget(title)
        
        # Summary
        summary = Label(
            text=f"[b]{self.ai_name}[/b] is ready to meet you, [b]{self.user_name}[/b]!",
            font_size='18sp',
            markup=True,
            size_hint_y=None,
            height=dp(40),
            color=(0.9, 0.9, 0.9, 1)
        )
        summary.halign = 'center'
        summary.valign = 'middle'
        summary.bind(width=lambda w, width: setattr(
            w, 'text_size', (max(dp(90), width - dp(16)), None)))
        summary.bind(texture_size=lambda w, size: setattr(
            w, 'height', max(dp(40), size[1] + dp(14))))
        self.content.add_widget(summary)
        
        # Details
        theme_name = COLOR_THEMES.get(self.favorite_color, {}).get('name', 'Custom')
        details = Label(
            text=f"Theme: {theme_name}\nMode: {self.mode.capitalize()}",
            font_size='16sp',
            size_hint_y=None,
            height=dp(60),
            color=(0.7, 0.7, 0.7, 1)
        )
        self.content.add_widget(details)
        
        # Spacer
        self.content.add_widget(Widget(size_hint_y=0.2))
        
        # Begin button
        begin_btn = Button(
            text=f'Meet {self.ai_name}',
            font_size='20sp',
            size_hint=(1, None),
            height=dp(60),
            background_color=(0.2, 0.6, 0.4, 1),
            background_normal='',
            color=(1, 1, 1, 1),
            bold=True
        )
        begin_btn.bind(on_release=self._complete_onboarding)
        self.content.add_widget(begin_btn)
        
        # Back link
        back_btn = Button(
            text='← Go Back',
            font_size='14sp',
            size_hint=(1, None),
            height=dp(40),
            background_color=(0, 0, 0, 0),
            background_normal='',
            color=(0.6, 0.6, 0.7, 1)
        )
        back_btn.bind(on_release=lambda x: setattr(
            App.get_running_app().screen_manager, 'current', 'name_enrollment'))
        self.content.add_widget(back_btn)
    
    def _select_color(self, color: str):
        """Handle color selection"""
        # Deselect all
        for btn in self.color_buttons.values():
            btn.deselect()
        
        # Select new
        self.color_buttons[color].select()
        self.favorite_color = color
        
        # Update label
        theme_name = COLOR_THEMES.get(color, {}).get('name', 'Custom')
        self.color_label.text = theme_name
        
        # Update label color to match
        from kivy.utils import get_color_from_hex
        accent = COLOR_THEMES.get(color, {}).get('accent', '#ffffff')
        self.color_label.color = get_color_from_hex(accent)
    
    def _next_from_welcome(self, *args):
        """Validate and proceed from welcome step"""
        name = self.ai_name_input.text.strip()
        if not name:
            # TODO: Show error
            return
        
        # Preserve the exact name chosen by the user; pronunciation
        # enrollment, not English capitalization, determines acoustic identity.
        self.ai_name = name
        self._show_step(1)
    
    def _next_from_mode(self, *args):
        """Save mode and proceed"""
        self.mode = self.mode_toggle.selected_mode
        self._show_step(3)
    
    def _next_from_user(self, *args):
        """Validate user info and proceed"""
        name = self.user_name_input.text.strip()
        birthday = self.birthday_input.text.strip()
        
        if not name:
            # TODO: Show error
            return
        
        self.user_name = name
        self.birthday = birthday
        app = App.get_running_app()
        try:
            # First learn the two spoken names. The meeting screen belongs
            # AFTER six valid recordings, not before them.
            app.begin_name_enrollment(
                user_name=self.user_name, ai_name=self.ai_name,
                favorite_color=self.favorite_color, mode=self.mode,
                birthday=self.birthday)
        except Exception as error:
            app._show_error_popup(f"Could not begin name recordings: {error}")
    
    def _complete_onboarding(self, *args):
        """Complete onboarding and launch companion"""
        app = App.get_running_app()
        # The final introduction is shown only after voice enrollment.
        app.finish_name_enrollment()
