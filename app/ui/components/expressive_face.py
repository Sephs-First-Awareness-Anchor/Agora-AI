#!/usr/bin/env python3
"""
KO Companion - Expressive Face Overlay
======================================
Authors: Sunni (Sir) Morningstar & Cael Devo

A living, breathing face overlay inspired by Face from Nickelodeon.
- Floats as an overlay on the screen
- Reacts to audio/visual input
- Moves around for emphasis
- Collapses to bubble when idle (introvert) or dismissed
- Creative expression with personality
"""

import random
import math
import time
import logging
from typing import Optional, Callable, Dict, Any

from kivy.uix.widget import Widget
from kivy.uix.floatlayout import FloatLayout
from kivy.graphics import (
    Color, Ellipse, Line, RoundedRectangle,
    PushMatrix, PopMatrix, Rotate, Translate, Scale,
    Bezier, Canvas
)
from kivy.clock import Clock
from kivy.animation import Animation
from kivy.core.window import Window
from kivy.properties import (
    NumericProperty, BooleanProperty, ObjectProperty,
    ListProperty, StringProperty
)

logger = logging.getLogger(__name__)


class ExpressiveFace(Widget):
    """
    The living face of KO - two eyes and a mouth with personality.
    
    Inspired by Face from Nickelodeon: expressive, playful, can
    rearrange features and move around the screen for emphasis.
    
    Wired into:
    - AI's FaceState for parameter sync
    - AI's AffectState for emotional expression
    - AI's EmoteSystem for gesture triggers
    - AI's MicroReactionEngine for reactive behavior
    - AI's IdleMicroGestureLoop for ambient life
    """
    
    # === Core Face Parameters (synced from AI) ===
    eye_open_l = NumericProperty(1.0)
    eye_open_r = NumericProperty(1.0)
    eye_width = NumericProperty(1.0)
    eye_height = NumericProperty(1.0)
    gaze_x = NumericProperty(0.0)
    gaze_y = NumericProperty(0.0)
    pupil_dilate = NumericProperty(1.0)
    
    mouth_open = NumericProperty(0.2)
    mouth_width = NumericProperty(0.6)
    mouth_curve = NumericProperty(0.0)  # -1 frown to +1 smile
    mouth_skew = NumericProperty(0.0)   # Asymmetric expression
    
    brow_raise_l = NumericProperty(0.0)
    brow_raise_r = NumericProperty(0.0)
    lid_droop = NumericProperty(0.0)    # Sleepy/relaxed
    squint = NumericProperty(0.0)       # Suspicious/focused
    
    # === Position & Transform ===
    face_x = NumericProperty(0.5)       # 0-1 screen position
    face_y = NumericProperty(0.6)
    face_scale = NumericProperty(1.0)
    face_rotation = NumericProperty(0.0)
    face_alpha = NumericProperty(1.0)
    
    # === Creative Expression Parameters ===
    eye_separation = NumericProperty(1.0)   # Eyes can spread/squish
    feature_chaos = NumericProperty(0.0)    # Random feature displacement
    wobble = NumericProperty(0.0)           # Jelly-like wobble
    stretch_x = NumericProperty(1.0)        # Horizontal stretch
    stretch_y = NumericProperty(1.0)        # Vertical stretch
    
    # === State ===
    is_bubble = BooleanProperty(False)
    is_speaking = BooleanProperty(False)
    is_listening = BooleanProperty(False)
    is_thinking = BooleanProperty(False)
    
    # === Theme Colors ===
    eye_color = ListProperty([0, 0.7, 1, 1])
    glow_color = ListProperty([0, 0.5, 1, 0.3])
    mouth_color = ListProperty([1, 1, 1, 1])
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # AI reference (set via connect_ai)
        self.ai = None
        self.theme = None
        
        # Animation state
        self._idle_timer = 0
        self._last_idle_action = time.time()
        self._creative_timer = 0
        self._wobble_phase = 0
        self._blink_cooldown = 0
        
        # Screen movement targets
        self._target_x = 0.5
        self._target_y = 0.6
        self._move_speed = 0.02
        
        # Expression queue for creative moments
        self._expression_queue = []
        
        # Bind redraw
        self.bind(pos=self._request_redraw, size=self._request_redraw)
        for prop in ['eye_open_l', 'eye_open_r', 'eye_width', 'eye_height',
                     'gaze_x', 'gaze_y', 'pupil_dilate', 'mouth_open',
                     'mouth_width', 'mouth_curve', 'mouth_skew',
                     'brow_raise_l', 'brow_raise_r', 'lid_droop', 'squint',
                     'face_x', 'face_y', 'face_scale', 'face_rotation',
                     'face_alpha', 'eye_separation', 'feature_chaos',
                     'wobble', 'stretch_x', 'stretch_y', 'is_bubble']:
            self.bind(**{prop: self._request_redraw})
        
        self._needs_redraw = True

        # Start only render loop (behavior and creative merged into AI core tick)
        # Store reference for cleanup
        self._render_event = Clock.schedule_interval(self._render_loop, 1/60)

    def cleanup(self):
        """Cancel scheduled events to prevent crashes on widget destruction"""
        if hasattr(self, '_render_event') and self._render_event:
            self._render_event.cancel()
            self._render_event = None

    def __del__(self):
        """Ensure cleanup on garbage collection"""
        self.cleanup()
    
    def connect_ai(self, ai_instance):
        """Connect to the AI instance for full integration"""
        self.ai = ai_instance
        
        if ai_instance:
            # Wire up the face animator to call our sync method
            if hasattr(ai_instance, 'face_animator'):
                # Override the animator's update to also sync to us
                original_update = ai_instance.face_animator.update
                def patched_update(dt):
                    original_update(dt)
                    self._sync_from_ai_state()
                ai_instance.face_animator.update = patched_update
            
            logger.info("[FACE] Connected to AI instance")
    
    def set_theme(self, theme):
        """Set color theme"""
        self.theme = theme
        if theme:
            colors = theme.get_face_colors()
            self.eye_color = list(colors['eye_color'])
            self.glow_color = list(colors['glow_color'])
            self.mouth_color = list(colors['mouth_color'])
    
    def _request_redraw(self, *args):
        self._needs_redraw = True
    
    def _sync_from_ai_state(self):
        """Sync parameters from AI's FaceState"""
        if not self.ai or not hasattr(self.ai, "face_state") or self.ai.face_state is None:
            return
        
        state = self.ai.face_state
        
        # Core parameters
        self.eye_open_l = state.eye_open_l
        self.eye_open_r = state.eye_open_r
        self.eye_width = state.eye_width
        self.eye_height = state.eye_height
        self.gaze_x = state.gaze_x
        self.gaze_y = state.gaze_y
        self.mouth_open = state.mouth_open
        self.mouth_width = state.mouth_width
        self.mouth_curve = state.mouth_curve
        self.mouth_skew = state.mouth_skew
        self.brow_raise_l = state.brow_raise
        self.brow_raise_r = state.brow_raise
        self.face_rotation = state.face_rotation * 15
        self.face_scale = state.scale
        self.face_alpha = state.alpha
        
        # Map lid_tension to squint
        self.squint = state.lid_tension
        
        # Sync affect to expression
        if hasattr(self.ai, 'affect') and self.ai.affect is not None:
            affect = self.ai.affect
            # Valence influences smile
            if hasattr(affect, 'valence'):
                self.mouth_curve = max(-1, min(1, self.mouth_curve + affect.valence * 0.3))
            # Arousal influences eye openness
            if hasattr(affect, 'arousal') and affect.arousal > 0.5:
                self.eye_open_l = min(1.2, self.eye_open_l + (affect.arousal - 0.5) * 0.4)
                self.eye_open_r = min(1.2, self.eye_open_r + (affect.arousal - 0.5) * 0.4)
    
    # === BEHAVIOR LOOPS ===
    
    def _behavior_loop(self, dt):
        """Main behavior update - idle gestures, reactions, etc."""
        if self.is_bubble:
            return
        
        now = time.time()
        
        # Blink cooldown
        if self._blink_cooldown > 0:
            self._blink_cooldown -= dt
        
        # Natural blinking (every 3-7 seconds)
        if now - self._last_idle_action > random.uniform(3, 7) and self._blink_cooldown <= 0:
            self._do_blink()
            self._last_idle_action = now
        
        # Smooth movement toward target position
        dx = self._target_x - self.face_x
        dy = self._target_y - self.face_y
        if abs(dx) > 0.01 or abs(dy) > 0.01:
            self.face_x += dx * self._move_speed
            self.face_y += dy * self._move_speed
        
        # Wobble physics
        self._wobble_phase += dt * 5
        if self.wobble > 0:
            self.wobble *= 0.95  # Decay
        
        # Speaking animation
        if self.is_speaking:
            self.mouth_open = 0.2 + random.uniform(0.1, 0.4)
    
    def _creative_loop(self, dt):
        """Creative expression - the personality shines through"""
        if self.is_bubble or not self.ai:
            return
        
        self._creative_timer += dt
        
        # Every 10-30 seconds, do something expressive
        if self._creative_timer > random.uniform(10, 30):
            self._creative_timer = 0
            self._do_creative_expression()
        
        # Process expression queue
        if self._expression_queue:
            expr = self._expression_queue.pop(0)
            self._execute_expression(expr)
    
    def _do_creative_expression(self):
        """Spontaneous creative expression - Face-style personality"""
        if not self.ai:
            return
        
        # Get current affect to influence choice
        valence = self.ai.affect.valence if hasattr(self.ai, 'affect') else 0
        arousal = self.ai.affect.arousal if hasattr(self.ai, 'affect') else 0.5
        
        expressions = []
        
        # Happy expressions
        if valence > 0.2:
            expressions.extend([
                'big_smile', 'eye_sparkle', 'happy_bounce',
                'side_to_side', 'playful_wink'
            ])
        
        # Curious expressions
        if arousal > 0.5:
            expressions.extend([
                'head_tilt', 'eye_widen', 'lean_forward',
                'scanning_look', 'raised_brow'
            ])
        
        # Calm expressions
        if arousal < 0.3:
            expressions.extend([
                'slow_blink', 'gentle_sway', 'dreamy_look',
                'soft_smile', 'relaxed_droop'
            ])
        
        # Mischievous (occasionally)
        if random.random() < 0.1:
            expressions.extend([
                'sly_smirk', 'one_eye_bigger', 'wiggly_brows',
                'tongue_out', 'dramatic_gasp'
            ])
        
        # Screen movement (occasionally)
        if random.random() < 0.15:
            expressions.extend([
                'move_to_corner', 'move_to_center', 'peek_from_side',
                'bounce_around', 'dramatic_entrance'
            ])
        
        if expressions:
            choice = random.choice(expressions)
            self._expression_queue.append(choice)
    
    def _execute_expression(self, expr_name: str):
        """Execute a named creative expression"""
        
        # === FACIAL EXPRESSIONS ===
        
        if expr_name == 'big_smile':
            anim = Animation(mouth_curve=0.9, mouth_width=0.9, duration=0.3)
            anim += Animation(mouth_curve=0.5, mouth_width=0.7, duration=0.5)
            anim.start(self)
        
        elif expr_name == 'eye_sparkle':
            anim = Animation(pupil_dilate=1.4, eye_open_l=1.1, eye_open_r=1.1, duration=0.2)
            anim += Animation(pupil_dilate=1.0, eye_open_l=1.0, eye_open_r=1.0, duration=0.3)
            anim.start(self)
        
        elif expr_name == 'happy_bounce':
            self.wobble = 0.3
            anim = Animation(stretch_y=1.15, duration=0.1)
            anim += Animation(stretch_y=0.9, duration=0.1)
            anim += Animation(stretch_y=1.0, duration=0.15)
            anim.start(self)
        
        elif expr_name == 'playful_wink':
            anim = Animation(eye_open_l=0.1, brow_raise_r=0.3, mouth_skew=0.3, duration=0.15)
            anim += Animation(duration=0.3)  # Hold
            anim += Animation(eye_open_l=1.0, brow_raise_r=0.0, mouth_skew=0.0, duration=0.2)
            anim.start(self)
        
        elif expr_name == 'head_tilt':
            direction = random.choice([-1, 1])
            anim = Animation(face_rotation=15 * direction, duration=0.3)
            anim += Animation(duration=1.0)  # Hold
            anim += Animation(face_rotation=0, duration=0.3)
            anim.start(self)
        
        elif expr_name == 'eye_widen':
            anim = Animation(eye_open_l=1.3, eye_open_r=1.3, brow_raise_l=0.5, brow_raise_r=0.5, duration=0.2)
            anim += Animation(duration=0.5)
            anim += Animation(eye_open_l=1.0, eye_open_r=1.0, brow_raise_l=0.0, brow_raise_r=0.0, duration=0.3)
            anim.start(self)
        
        elif expr_name == 'scanning_look':
            anim = Animation(gaze_x=-0.6, duration=0.4)
            anim += Animation(gaze_x=0.6, duration=0.8)
            anim += Animation(gaze_x=0.0, duration=0.4)
            anim.start(self)
        
        elif expr_name == 'slow_blink':
            anim = Animation(eye_open_l=0.0, eye_open_r=0.0, duration=0.3)
            anim += Animation(duration=0.2)
            anim += Animation(eye_open_l=1.0, eye_open_r=1.0, duration=0.4)
            anim.start(self)
        
        elif expr_name == 'gentle_sway':
            anim = Animation(face_rotation=5, duration=1.0)
            anim += Animation(face_rotation=-5, duration=2.0)
            anim += Animation(face_rotation=0, duration=1.0)
            anim.start(self)
        
        elif expr_name == 'sly_smirk':
            anim = Animation(mouth_curve=0.4, mouth_skew=0.5, eye_open_l=0.7, brow_raise_r=0.3, duration=0.3)
            anim += Animation(duration=1.0)
            anim += Animation(mouth_curve=0.0, mouth_skew=0.0, eye_open_l=1.0, brow_raise_r=0.0, duration=0.3)
            anim.start(self)
        
        elif expr_name == 'one_eye_bigger':
            anim = Animation(eye_open_r=1.4, eye_open_l=0.6, duration=0.2)
            anim += Animation(duration=0.8)
            anim += Animation(eye_open_r=1.0, eye_open_l=1.0, duration=0.2)
            anim.start(self)
        
        elif expr_name == 'wiggly_brows':
            for _ in range(3):
                anim = Animation(brow_raise_l=0.5, brow_raise_r=-0.2, duration=0.15)
                anim += Animation(brow_raise_l=-0.2, brow_raise_r=0.5, duration=0.15)
            anim += Animation(brow_raise_l=0.0, brow_raise_r=0.0, duration=0.2)
            anim.start(self)
        
        elif expr_name == 'dramatic_gasp':
            anim = Animation(mouth_open=0.8, eye_open_l=1.4, eye_open_r=1.4, 
                           brow_raise_l=0.7, brow_raise_r=0.7, duration=0.15)
            anim += Animation(duration=0.5)
            anim += Animation(mouth_open=0.2, eye_open_l=1.0, eye_open_r=1.0,
                            brow_raise_l=0.0, brow_raise_r=0.0, duration=0.4)
            anim.start(self)
        
        elif expr_name == 'relaxed_droop':
            anim = Animation(lid_droop=0.3, mouth_curve=0.2, duration=0.5)
            anim += Animation(duration=2.0)
            anim += Animation(lid_droop=0.0, duration=0.5)
            anim.start(self)
        
        # === SCREEN MOVEMENT ===
        
        elif expr_name == 'move_to_corner':
            corner = random.choice([
                (0.2, 0.8), (0.8, 0.8), (0.2, 0.3), (0.8, 0.3)
            ])
            self._target_x, self._target_y = corner
            self._move_speed = 0.03
        
        elif expr_name == 'move_to_center':
            self._target_x, self._target_y = 0.5, 0.55
            self._move_speed = 0.02
        
        elif expr_name == 'peek_from_side':
            side = random.choice(['left', 'right'])
            if side == 'left':
                self._target_x = 0.15
                anim = Animation(face_rotation=20, gaze_x=0.8, duration=0.3)
            else:
                self._target_x = 0.85
                anim = Animation(face_rotation=-20, gaze_x=-0.8, duration=0.3)
            self._move_speed = 0.05
            anim.start(self)
            
            # Return after a moment
            def return_to_center(dt):
                self._target_x = 0.5
                Animation(face_rotation=0, gaze_x=0, duration=0.4).start(self)
            Clock.schedule_once(return_to_center, 2.0)
        
        elif expr_name == 'bounce_around':
            positions = [(0.3, 0.7), (0.7, 0.7), (0.7, 0.4), (0.3, 0.4), (0.5, 0.55)]
            self._move_speed = 0.08
            
            def move_to_next(i):
                if i < len(positions):
                    self._target_x, self._target_y = positions[i]
                    self.wobble = 0.2
                    Clock.schedule_once(lambda dt: move_to_next(i + 1), 0.4)
            
            move_to_next(0)
    
    def _do_blink(self, both=True):
        """Natural blink"""
        self._blink_cooldown = 0.5
        
        if both:
            anim = Animation(eye_open_l=0.0, eye_open_r=0.0, duration=0.06)
            anim += Animation(eye_open_l=1.0, eye_open_r=1.0, duration=0.06)
        else:
            # Wink
            eye = random.choice(['l', 'r'])
            if eye == 'l':
                anim = Animation(eye_open_l=0.0, duration=0.08)
                anim += Animation(eye_open_l=1.0, duration=0.08)
            else:
                anim = Animation(eye_open_r=0.0, duration=0.08)
                anim += Animation(eye_open_r=1.0, duration=0.08)
        
        anim.start(self)
    
    # === REACTIVE BEHAVIORS ===
    
    def react_to_audio(self, volume: float, pitch: float):
        """React to audio input"""
        if self.is_bubble:
            return
        
        # Attention shift
        if volume > 0.5:
            self.eye_open_l = min(1.2, 1.0 + volume * 0.3)
            self.eye_open_r = min(1.2, 1.0 + volume * 0.3)
        
        # Look toward sound (simulated with slight gaze shift)
        self.gaze_x += random.uniform(-0.1, 0.1)
    
    def react_to_user_emotion(self, emotion: str, intensity: float):
        """React to detected user emotion"""
        if self.is_bubble:
            return
        
        if emotion == 'happy':
            self._expression_queue.append('big_smile')
        elif emotion == 'sad':
            # Empathetic response
            anim = Animation(mouth_curve=-0.2, brow_raise_l=0.3, brow_raise_r=0.3, duration=0.3)
            anim.start(self)
        elif emotion == 'surprised':
            self._expression_queue.append('dramatic_gasp')
        elif emotion == 'angry':
            # Concerned look
            anim = Animation(brow_raise_l=-0.2, brow_raise_r=0.3, gaze_y=-0.1, duration=0.3)
            anim.start(self)
    
    def on_interrupt(self):
        """Called when user interrupts AI speaking"""
        if self.ai and hasattr(self.ai, 'is_extrovert'):
            if self.ai.is_extrovert:
                # Extrovert: slight annoyance then continue
                self._expression_queue.append('sly_smirk')
            else:
                # Introvert: yield politely
                anim = Animation(eye_open_l=0.6, eye_open_r=0.6, mouth_open=0.0, duration=0.2)
                anim.start(self)
    
    def start_speaking(self):
        """Called when AI starts speaking"""
        self.is_speaking = True
        # Slight smile when speaking
        Animation(mouth_curve=0.2, duration=0.2).start(self)
    
    def stop_speaking(self):
        """Called when AI stops speaking"""
        self.is_speaking = False
        Animation(mouth_open=0.15, duration=0.2).start(self)
    
    def start_listening(self):
        """Called when listening for user input"""
        self.is_listening = True
        # Attentive look
        anim = Animation(eye_open_l=1.1, eye_open_r=1.1, brow_raise_l=0.15, brow_raise_r=0.15, duration=0.2)
        anim.start(self)
    
    def stop_listening(self):
        """Called when done listening"""
        self.is_listening = False
        anim = Animation(eye_open_l=1.0, eye_open_r=1.0, brow_raise_l=0.0, brow_raise_r=0.0, duration=0.2)
        anim.start(self)
    
    def start_thinking(self):
        """Called when AI is processing"""
        self.is_thinking = True
        # Look up and to the side
        anim = Animation(gaze_x=0.4, gaze_y=0.3, eye_open_l=0.8, eye_open_r=0.8, duration=0.3)
        anim.start(self)
    
    def stop_thinking(self):
        """Called when done processing"""
        self.is_thinking = False
        anim = Animation(gaze_x=0.0, gaze_y=0.0, eye_open_l=1.0, eye_open_r=1.0, duration=0.2)
        anim.start(self)
    
    # === BUBBLE STATE ===
    
    def collapse_to_bubble(self, animate=True):
        """Collapse face to small bubble"""
        if self.is_bubble:
            return
        
        if animate:
            anim = Animation(
                face_scale=0.25,
                face_alpha=0.7,
                eye_open_l=0.5,
                eye_open_r=0.5,
                mouth_open=0.0,
                duration=0.4,
                t='out_cubic'
            )
            anim.bind(on_complete=lambda *a: setattr(self, 'is_bubble', True))
            anim.start(self)
            
            # Move to corner
            self._target_x = 0.85
            self._target_y = 0.15
            self._move_speed = 0.05
        else:
            self.is_bubble = True
            self.face_scale = 0.25
            self.face_alpha = 0.7
            self.face_x = 0.85
            self.face_y = 0.15
    
    def expand_from_bubble(self, animate=True):
        """Expand from bubble to full face"""
        if not self.is_bubble:
            return
        
        self.is_bubble = False
        
        if animate:
            # Dramatic entrance
            self._target_x = 0.5
            self._target_y = 0.55
            self._move_speed = 0.06
            
            anim = Animation(
                face_scale=1.0,
                face_alpha=1.0,
                eye_open_l=1.0,
                eye_open_r=1.0,
                mouth_curve=0.3,
                duration=0.4,
                t='out_back'
            )
            anim.start(self)
            
            # Add a little wobble for personality
            self.wobble = 0.3
        else:
            self.face_scale = 1.0
            self.face_alpha = 1.0
            self.face_x = 0.5
            self.face_y = 0.55
    
    # === RENDERING ===
    
    def _render_loop(self, dt):
        """Main render loop"""
        if not self._needs_redraw:
            return
        self._needs_redraw = False
        
        self.canvas.clear()
        
        # Calculate actual position
        cx = self.x + self.width * self.face_x
        cy = self.y + self.height * self.face_y
        
        # Apply wobble
        wobble_offset_x = math.sin(self._wobble_phase) * self.wobble * 10
        wobble_offset_y = math.cos(self._wobble_phase * 1.3) * self.wobble * 8
        cx += wobble_offset_x
        cy += wobble_offset_y
        
        # Base scale (affected by bubble state and stretch)
        base_size = min(self.width, self.height) * 0.3 * self.face_scale
        
        with self.canvas:
            PushMatrix()
            
            Translate(cx, cy)
            Rotate(angle=self.face_rotation, origin=(0, 0))
            Scale(self.stretch_x, self.stretch_y, 1)
            
            # Glow aura
            Color(*self.glow_color[:3], self.face_alpha * self.glow_color[3])
            glow_size = base_size * 2.5
            Ellipse(pos=(-glow_size/2, -glow_size/2), size=(glow_size, glow_size))
            
            # Eye separation (can be dynamic)
            eye_sep = base_size * 0.4 * self.eye_separation
            
            # Feature chaos offset
            chaos_l = (random.uniform(-1, 1) * self.feature_chaos * 5,
                       random.uniform(-1, 1) * self.feature_chaos * 5)
            chaos_r = (random.uniform(-1, 1) * self.feature_chaos * 5,
                       random.uniform(-1, 1) * self.feature_chaos * 5)
            
            # Left eye
            self._draw_eye(
                -eye_sep + chaos_l[0],
                base_size * 0.15 + chaos_l[1],
                base_size * 0.35,
                self.eye_open_l,
                self.brow_raise_l,
                True
            )
            
            # Right eye
            self._draw_eye(
                eye_sep + chaos_r[0],
                base_size * 0.15 + chaos_r[1],
                base_size * 0.35,
                self.eye_open_r,
                self.brow_raise_r,
                False
            )
            
            # Mouth
            self._draw_mouth(
                0,
                -base_size * 0.25,
                base_size * 0.6
            )
            
            PopMatrix()
    
    def _draw_eye(self, x, y, size, openness, brow, is_left):
        """Draw a single expressive eye"""
        # Clamp openness
        openness = max(0.05, openness)
        
        w = size * self.eye_width
        h = size * self.eye_height * openness
        
        # Apply lid droop
        h *= (1.0 - self.lid_droop * 0.3)
        
        # Apply squint
        if self.squint > 0:
            h *= (1.0 - self.squint * 0.4)
        
        # Eye glow
        Color(*self.glow_color[:3], self.face_alpha * 0.5)
        Ellipse(pos=(x - w/2 - 3, y - h/2 - 3), size=(w + 6, h + 6))
        
        # Eye white/color
        Color(*self.eye_color[:3], self.face_alpha)
        Ellipse(pos=(x - w/2, y - h/2), size=(w, h))
        
        # Pupil (if eye open enough)
        if openness > 0.2:
            pupil_w = w * 0.4 * self.pupil_dilate
            pupil_h = h * 0.5 * self.pupil_dilate
            
            # Gaze offset
            gaze_off_x = self.gaze_x * w * 0.25
            gaze_off_y = self.gaze_y * h * 0.2
            
            Color(1, 1, 1, self.face_alpha)
            Ellipse(
                pos=(x - pupil_w/2 + gaze_off_x, y - pupil_h/2 + gaze_off_y),
                size=(pupil_w, pupil_h)
            )
            
            # Highlight
            Color(1, 1, 1, self.face_alpha * 0.8)
            hl_size = pupil_w * 0.25
            Ellipse(
                pos=(x + pupil_w * 0.2 + gaze_off_x, y + pupil_h * 0.2 + gaze_off_y),
                size=(hl_size, hl_size)
            )
        
        # Eyebrow
        if abs(brow) > 0.05 or self.squint > 0.1:
            brow_y = y + h/2 + size * 0.15 + (brow * size * 0.2)
            brow_angle = brow * 15 * (-1 if is_left else 1)
            
            Color(*self.eye_color[:3], self.face_alpha * 0.7)
            
            # Brow as a curved line
            brow_w = w * 0.9
            PushMatrix()
            Translate(x, brow_y)
            Rotate(angle=brow_angle, origin=(0, 0))
            Line(points=[-brow_w/2, 0, brow_w/2, 0], width=2.5, cap='round')
            PopMatrix()
    
    def _draw_mouth(self, x, y, size):
        """Draw expressive mouth"""
        w = size * self.mouth_width
        h = max(3, size * 0.4 * self.mouth_open)
        curve = self.mouth_curve * size * 0.3
        skew = self.mouth_skew * size * 0.15
        
        # Mouth glow
        Color(*self.glow_color[:3], self.face_alpha * 0.3)
        
        # Bezier curve for mouth shape
        # Control points for smile/frown
        p0 = (x - w/2 + skew, y)
        p1 = (x - w/4, y + curve)
        p2 = (x + w/4, y + curve)
        p3 = (x + w/2 - skew, y)
        
        Line(bezier=[p0[0], p0[1], p1[0], p1[1], p2[0], p2[1], p3[0], p3[1]], 
             width=3)
        
        # Mouth interior when open
        if self.mouth_open > 0.15:
            Color(*self.mouth_color[:3], self.face_alpha * 0.3)
            interior_w = w * 0.7
            interior_h = h * 0.8
            Ellipse(
                pos=(x - interior_w/2, y - interior_h/2 + curve/2),
                size=(interior_w, interior_h)
            )
