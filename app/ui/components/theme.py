#!/usr/bin/env python3
"""
KO Companion - Theme Manager
============================
Authors: Sunni (Sir) Morningstar & Cael Devo

Color theming system based on user's favorite color.
Each color creates a cohesive palette for the UI.
"""

from kivy.utils import get_color_from_hex
from kivy.properties import ListProperty, StringProperty

# Color themes based on favorite color selection
# Each theme provides: background, primary, secondary, accent, text, text_secondary
COLOR_THEMES = {
    'red': {
        'name': 'Crimson Flame',
        'background': '#1a0a0a',      # Deep dark red-black
        'primary': '#8b0000',          # Dark red
        'secondary': '#2d0a0a',        # Slightly lighter bg
        'accent': '#ff4444',           # Bright red accent
        'text': '#ffffff',             # White text
        'text_secondary': '#ff9999',   # Light red text
        'glow': '#ff0000',             # Red glow for face
    },
    'blue': {
        'name': 'Ocean Depths',
        'background': '#0a0a1a',      # Deep dark blue-black
        'primary': '#1a4a7a',          # Navy blue
        'secondary': '#0d1525',        # Slightly lighter bg
        'accent': '#00aaff',           # Bright blue accent
        'text': '#ffffff',
        'text_secondary': '#99ccff',
        'glow': '#0088ff',
    },
    'green': {
        'name': 'Forest Spirit',
        'background': '#0a1a0a',      # Deep dark green-black
        'primary': '#1a5a2a',          # Forest green
        'secondary': '#0d200d',
        'accent': '#44ff88',           # Bright green accent
        'text': '#ffffff',
        'text_secondary': '#99ffbb',
        'glow': '#00ff66',
    },
    'yellow': {
        'name': 'Golden Dawn',
        'background': '#1a1a0a',      # Deep dark yellow-black
        'primary': '#5a5a1a',          # Dark gold
        'secondary': '#252510',
        'accent': '#ffdd44',           # Bright yellow accent
        'text': '#ffffff',
        'text_secondary': '#ffee99',
        'glow': '#ffcc00',
    },
    'purple': {
        'name': 'Mystic Twilight',
        'background': '#150a1a',      # Deep dark purple-black
        'primary': '#4a1a6a',          # Deep purple
        'secondary': '#1d0d25',
        'accent': '#bb44ff',           # Bright purple accent
        'text': '#ffffff',
        'text_secondary': '#dd99ff',
        'glow': '#aa00ff',
    },
    'orange': {
        'name': 'Ember Glow',
        'background': '#1a100a',      # Deep dark orange-black
        'primary': '#6a3a1a',          # Burnt orange
        'secondary': '#251a0d',
        'accent': '#ff8844',           # Bright orange accent
        'text': '#ffffff',
        'text_secondary': '#ffbb99',
        'glow': '#ff6600',
    },
    'pink': {
        'name': 'Rose Quartz',
        'background': '#1a0a14',      # Deep dark pink-black
        'primary': '#6a1a4a',          # Deep pink
        'secondary': '#250d1d',
        'accent': '#ff66aa',           # Bright pink accent
        'text': '#ffffff',
        'text_secondary': '#ffaacc',
        'glow': '#ff0088',
    },
    'cyan': {
        'name': 'Arctic Aurora',
        'background': '#0a1a1a',      # Deep dark cyan-black
        'primary': '#1a5a5a',          # Teal
        'secondary': '#0d2525',
        'accent': '#44ffff',           # Bright cyan accent
        'text': '#ffffff',
        'text_secondary': '#99ffff',
        'glow': '#00ffff',
    },
    'white': {
        'name': 'Moonlight',
        'background': '#121215',      # Very dark gray
        'primary': '#3a3a40',          # Medium gray
        'secondary': '#1a1a1d',
        'accent': '#ffffff',           # White accent
        'text': '#ffffff',
        'text_secondary': '#cccccc',
        'glow': '#ffffff',
    },
    'black': {
        'name': 'Void Walker',
        'background': '#050505',      # Near black
        'primary': '#1a1a1a',          # Dark gray
        'secondary': '#0a0a0a',
        'accent': '#666666',           # Gray accent
        'text': '#ffffff',
        'text_secondary': '#888888',
        'glow': '#333333',
    },
}

# Default theme if color not found
DEFAULT_THEME = 'blue'


class ThemeManager:
    """
    Manages application theming based on user's favorite color.
    
    Usage:
        theme = ThemeManager()
        theme.set_color('purple')
        bg_color = theme.background  # Returns RGBA tuple
    """
    
    def __init__(self, color: str = DEFAULT_THEME):
        self._current_color = color
        self._theme = COLOR_THEMES.get(color, COLOR_THEMES[DEFAULT_THEME])
    
    @property
    def current_color(self) -> str:
        return self._current_color
    
    @property
    def theme_name(self) -> str:
        return self._theme['name']
    
    def set_color(self, color: str):
        """Set the theme color"""
        color = color.lower()
        if color in COLOR_THEMES:
            self._current_color = color
            self._theme = COLOR_THEMES[color]
        else:
            self._current_color = DEFAULT_THEME
            self._theme = COLOR_THEMES[DEFAULT_THEME]
    
    def _hex_to_rgba(self, hex_color: str) -> tuple:
        """Convert hex color to RGBA tuple (0-1 range)"""
        return get_color_from_hex(hex_color)
    
    @property
    def background(self) -> tuple:
        return self._hex_to_rgba(self._theme['background'])
    
    @property
    def primary(self) -> tuple:
        return self._hex_to_rgba(self._theme['primary'])
    
    @property
    def secondary(self) -> tuple:
        return self._hex_to_rgba(self._theme['secondary'])
    
    @property
    def accent(self) -> tuple:
        return self._hex_to_rgba(self._theme['accent'])
    
    @property
    def text(self) -> tuple:
        return self._hex_to_rgba(self._theme['text'])
    
    @property
    def text_secondary(self) -> tuple:
        return self._hex_to_rgba(self._theme['text_secondary'])
    
    @property
    def glow(self) -> tuple:
        return self._hex_to_rgba(self._theme['glow'])
    
    @property
    def background_hex(self) -> str:
        return self._theme['background']
    
    @property
    def primary_hex(self) -> str:
        return self._theme['primary']
    
    @property
    def secondary_hex(self) -> str:
        return self._theme['secondary']
    
    @property
    def accent_hex(self) -> str:
        return self._theme['accent']
    
    @property
    def glow_hex(self) -> str:
        return self._theme['glow']
    
    def get_face_colors(self) -> dict:
        """Get colors specifically for the face rendering"""
        return {
            'eye_color': self._hex_to_rgba(self._theme['accent']),
            'glow_color': self._hex_to_rgba(self._theme['glow']),
            'mouth_color': self._hex_to_rgba(self._theme['text']),
            'pupil_color': self._hex_to_rgba(self._theme['text']),
        }


# Utility function for KV files
def get_theme_color(color_name: str, component: str) -> tuple:
    """
    Get a specific color component from a theme.
    Useful for KV language bindings.
    
    Args:
        color_name: The favorite color (e.g., 'blue', 'purple')
        component: The color component ('background', 'primary', 'accent', etc.)
    
    Returns:
        RGBA tuple
    """
    theme = COLOR_THEMES.get(color_name.lower(), COLOR_THEMES[DEFAULT_THEME])
    hex_color = theme.get(component, '#ffffff')
    return get_color_from_hex(hex_color)
