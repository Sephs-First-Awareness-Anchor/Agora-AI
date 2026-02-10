#!/usr/bin/env python3
"""
KO Companion - Face Personality Engine
======================================
Authors: Sunni (Sir) Morningstar & Cael Devo

Creative expression system inspired by Nickelodeon's "Face".
Handles:
- Screen roaming and positioning for emphasis
- Face rearrangement (eyes swapping, stretching, etc.)
- Reactive behaviors to audio/visual input
- Idle creativity and personality expression
- Integration with AI's perception and learning systems
"""

import random
import math
import time
import logging
from typing import Dict, Any, Optional, Tuple, List, Callable
from dataclasses import dataclass, field
from enum import Enum
from collections import deque

from kivy.clock import Clock
from kivy.core.window import Window
from offline_ai_logic import OperatingMode

logger = logging.getLogger(__name__)


class FaceMood(Enum):
    """Current emotional state driving expression"""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    CURIOUS = "curious"
    SURPRISED = "surprised"
    THINKING = "thinking"
    SLEEPY = "sleepy"
    EXCITED = "excited"
    CONCERNED = "concerned"
    PLAYFUL = "playful"
    LISTENING = "listening"


class ScreenPosition(Enum):
    """Named positions on screen for emphasis movements"""
    CENTER = "center"
    TOP_LEFT = "top_left"
    TOP_RIGHT = "top_right"
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_RIGHT = "bottom_right"
    TOP_CENTER = "top_center"
    BOTTOM_CENTER = "bottom_center"
    LEFT_CENTER = "left_center"
    RIGHT_CENTER = "right_center"
    # Special positions
    PEEK_LEFT = "peek_left"      # Peeking from left edge
    PEEK_RIGHT = "peek_right"    # Peeking from right edge
    PEEK_TOP = "peek_top"        # Peeking from top
    PEEK_BOTTOM = "peek_bottom"  # Peeking from bottom


@dataclass
class FaceGeometry:
    """
    Defines the spatial arrangement of face features.
    Allows creative rearrangement while maintaining identity.
    """
    # Position on screen (0-1 normalized)
    screen_x: float = 0.5
    screen_y: float = 0.6
    
    # Feature positions relative to face center
    left_eye_offset: Tuple[float, float] = (-0.15, 0.08)
    right_eye_offset: Tuple[float, float] = (0.15, 0.08)
    mouth_offset: Tuple[float, float] = (0.0, -0.12)
    
    # Feature scales
    eye_scale: float = 1.0
    mouth_scale: float = 1.0
    overall_scale: float = 1.0
    
    # Rotation
    rotation: float = 0.0
    
    # Squash and stretch
    squash_x: float = 1.0
    squash_y: float = 1.0


@dataclass 
class PerceptionState:
    """Current perception inputs from AI systems"""
    # Audio
    audio_energy: float = 0.0       # Volume/energy level
    audio_pitch: float = 0.5        # Pitch (0=low, 1=high)
    audio_tempo: float = 0.5        # Speech tempo
    is_user_speaking: bool = False
    detected_emotion: str = "neutral"
    
    # Visual
    user_present: bool = False
    user_looking: bool = False      # Eye contact
    user_smiling: bool = False
    sudden_motion: bool = False
    brightness: float = 0.5
    
    # Context
    last_intent: str = ""
    conversation_energy: float = 0.5
    time_since_interaction: float = 0.0


class CreativeFaceEngine:
    """
    The brain behind KO's expressive face.
    
    Handles all creative decisions about how the face moves,
    emotes, and expresses personality. Integrates with the
    AI's perception and learning systems.
    """
    
    def __init__(self, face_widget, ai_instance=None):
        self.face_widget = face_widget
        self.ai = ai_instance
        self.adapter = getattr(ai_instance, "face_adapter", None) if ai_instance else None
        
        # Current state
        self.geometry = FaceGeometry()
        self.mood = FaceMood.NEUTRAL
        self.perception = PerceptionState()
        
        # Behavior parameters (will be influenced by AI's learned personality)
        self.expressiveness = 0.7      # How animated (0-1)
        self.playfulness = 0.5         # Tendency for playful behaviors
        self.restlessness = 0.3        # How much it moves around
        self.curiosity = 0.5           # Reaction intensity to stimuli
        
        # Creative behavior state
        self._idle_timer = 0.0
        self._last_creative_action = 0.0
        self._creative_cooldown = 3.0   # Seconds between creative actions
        self._current_animation = None
        self._position_history = deque(maxlen=10)
        
        # Reaction queue (for sequencing reactions)
        self._reaction_queue: List[Callable] = []
        
        # Screen bounds
        self._screen_width = Window.width
        self._screen_height = Window.height
        Window.bind(on_resize=self._on_window_resize)

    def _safe_animate(self, param: str, value: float, duration: float, easing: str = "linear", layer: int = 1):
        """Safe wrapper for adapter.animate that checks for None adapter."""
        if self.adapter is not None:
            try:
                self.adapter.animate(param, value, duration, easing, layer)
            except Exception as e:
                logger.debug(f"[FACE] Animation failed for {param}: {e}")

    def _has_adapter(self) -> bool:
        """Check if adapter is available for animations."""
        return self.adapter is not None

    def update(self, dt):
        """Unified update loop called by the AI core tick."""
        self._creative_tick(dt)
        self._perception_sync(dt)
    
    def _on_window_resize(self, window, width, height):
        self._screen_width = width
        self._screen_height = height
    
    def connect_ai(self, ai_instance):
        """Connect to AI instance for perception/learning integration"""
        self.ai = ai_instance
        self._sync_personality_from_ai()
    
    def _sync_personality_from_ai(self):
        """Pull personality traits from AI's learned parameters"""
        if not self.ai:
            return
        
        try:
            # Get personality from voice gnome and expression style
            params = self.ai.governor.get_personalized_parameters()
            
            # Map AI traits to face behaviors
            voice = params.get('voice_gnome', {})
            expr = params.get('expression_style', {})
            comm = params.get('communication', {})
            
            self.expressiveness = voice.get('warmth', 0.6) * 0.8 + expr.get('curiosity', 0.5) * 0.2
            self.playfulness = expr.get('curiosity', 0.5) * 0.7 + voice.get('confidence', 0.5) * 0.3
            self.restlessness = self.ai.energy.presence * 0.5 if hasattr(self.ai, 'energy') else 0.3
            self.curiosity = expr.get('curiosity', 0.5)
            
            logger.debug(f"[FACE] Synced personality: expr={self.expressiveness:.2f}, play={self.playfulness:.2f}")
        except Exception as e:
            logger.warning(f"[FACE] Failed to sync personality: {e}")
    
    def _perception_sync(self, dt):
        """Sync perception state from AI systems"""
        if not self.ai:
            return
        
        try:
            # Sync from energy regulator
            if hasattr(self.ai, 'energy'):
                energy = self.ai.energy
                self.perception.conversation_energy = energy.presence
                self.perception.detected_emotion = energy.current_emotion
            
            # Sync from affect state
            if hasattr(self.ai, 'affect'):
                affect = self.ai.affect
                # Map VAD to mood
                self._update_mood_from_affect(affect.valence, affect.arousal, affect.dominance)
            
            # Update idle timer
            self.perception.time_since_interaction += dt
            
        except Exception as e:
            logger.debug(f"[FACE] Perception sync error: {e}")
    
    def _update_mood_from_affect(self, valence: float, arousal: float, dominance: float):
        """Map VAD affect space to discrete mood"""
        if arousal < -0.3:
            self.mood = FaceMood.SLEEPY
        elif valence > 0.4 and arousal > 0.3:
            self.mood = FaceMood.EXCITED
        elif valence > 0.3:
            self.mood = FaceMood.HAPPY
        elif valence < -0.3:
            self.mood = FaceMood.CONCERNED
        elif arousal > 0.4:
            self.mood = FaceMood.CURIOUS
        elif dominance > 0.5:
            self.mood = FaceMood.PLAYFUL
        else:
            self.mood = FaceMood.NEUTRAL
    
    # =========================================================================
    # CREATIVE BEHAVIORS
    # =========================================================================
    
    def _creative_tick(self, dt):
        """Main creative behavior loop"""
        self._idle_timer += dt
        
        # Process any queued reactions
        if self._reaction_queue:
            reaction = self._reaction_queue.pop(0)
            reaction()
            return
        
        # Check if we should do something creative
        time_since_creative = time.time() - self._last_creative_action
        
        if time_since_creative > self._creative_cooldown:
            # Weighted random choice based on state
            if self._should_do_creative_action():
                self._do_creative_action()
    
    def _should_do_creative_action(self) -> bool:
        """Decide if we should do something creative"""
        # More likely when idle
        idle_factor = min(1.0, self._idle_timer / 10.0)
        
        # Personality influence
        personality_factor = (self.playfulness + self.restlessness) / 2
        
        # Random check
        threshold = 0.3 + (idle_factor * 0.4) + (personality_factor * 0.2)
        return random.random() < threshold * 0.1  # Per-frame probability
    
    def _do_creative_action(self):
        """Execute a random creative action"""
        # Disable creativity during replay mode
        if self.ai and getattr(self.ai, "mode", None) == OperatingMode.REPLAY:
            return

        self._last_creative_action = time.time()
        
        # Weight actions by mood and personality
        actions = self._get_weighted_actions()
        
        if actions:
            action = random.choices(actions, weights=[a[1] for a in actions])[0][0]
            action()
    
    def _get_weighted_actions(self) -> List[Tuple[Callable, float]]:
        """Get list of (action, weight) tuples based on current state"""
        actions = []
        
        # Always available
        actions.append((self._action_blink_pattern, 1.0))
        actions.append((self._action_look_around, 0.8))
        
        # Mood-dependent
        if self.mood in [FaceMood.PLAYFUL, FaceMood.HAPPY, FaceMood.EXCITED]:
            actions.append((self._action_wiggle, self.playfulness))
            actions.append((self._action_bounce, self.playfulness * 0.8))
            actions.append((self._action_spin, self.playfulness * 0.3))
        
        if self.mood == FaceMood.CURIOUS:
            actions.append((self._action_tilt_head, self.curiosity))
            actions.append((self._action_lean_forward, self.curiosity * 0.7))
        
        if self.mood == FaceMood.SLEEPY:
            actions.append((self._action_drowsy_blink, 1.5))
            actions.append((self._action_yawn, 0.5))
        
        # Position changes (restlessness-dependent)
        if self.restlessness > 0.3:
            actions.append((self._action_move_to_random_position, self.restlessness))
            actions.append((self._action_peek_from_edge, self.restlessness * 0.5))
        
        # Face rearrangement (rare, playful)
        if self.playfulness > 0.6:
            actions.append((self._action_eye_swap, self.playfulness * 0.2))
            actions.append((self._action_squash_stretch, self.playfulness * 0.3))
        
        return actions
    
    # =========================================================================
    # CREATIVE ACTIONS
    # =========================================================================
    
    def _action_blink_pattern(self):
        """Do a creative blink pattern"""
        patterns = [
            [(0.08, 0.08)],                          # Single blink
            [(0.06, 0.06), (0.15, 0.06, 0.06)],     # Double blink
            [(0.1, 0.2)],                            # Slow blink
            [(0.05, 0.05), (0.08, 0.05), (0.08, 0.05)],  # Triple quick
        ]
        
        pattern = random.choice(patterns)
        self._execute_blink_pattern(pattern)
    
    def _execute_blink_pattern(self, pattern):
        """Execute a blink pattern: list of (close_dur, open_dur, [delay])"""
        delay = 0
        for step in pattern:
            close_dur = step[0]
            open_dur = step[1] if len(step) > 1 else step[0]
            wait = step[2] if len(step) > 2 else 0
            
            Clock.schedule_once(lambda dt, cd=close_dur: self._blink_close(cd), delay)
            delay += close_dur
            Clock.schedule_once(lambda dt, od=open_dur: self._blink_open(od), delay)
            delay += open_dur + wait
    
    def _blink_close(self, duration):
        if self.adapter:
            self.adapter.animate("eye_open_l", 0.0, duration)
            self.adapter.animate("eye_open_r", 0.0, duration)
    
    def _blink_open(self, duration):
        if self.adapter:
            self.adapter.animate("eye_open_l", 1.0, duration)
            self.adapter.animate("eye_open_r", 1.0, duration)
    
    def _action_look_around(self):
        """Look around curiously"""
        # Generate a path of gaze points
        points = [
            (random.uniform(-0.4, 0.4), random.uniform(-0.2, 0.2))
            for _ in range(random.randint(2, 4))
        ]
        points.append((0, 0))  # Return to center
        
        delay = 0
        for x, y in points:
            dur = random.uniform(0.3, 0.6)
            Clock.schedule_once(
                lambda dt, gx=x, gy=y, d=dur: self._animate_gaze(gx, gy, d),
                delay
            )
            delay += dur + random.uniform(0.1, 0.3)
    
    def _animate_gaze(self, x, y, duration):
        if self.adapter:
            self.adapter.animate("gaze_x", x, duration, easing="in_out")
            self.adapter.animate("gaze_y", y, duration, easing="in_out")
    
    def _action_wiggle(self):
        """Playful side-to-side wiggle"""
        if not self.adapter: return
        self._safe_animate("face_rotation", 0.15, 0.1)
        Clock.schedule_once(lambda dt: self._safe_animate("face_rotation", -0.15, 0.1), 0.1)
        Clock.schedule_once(lambda dt: self._safe_animate("face_rotation", 0.1, 0.08), 0.2)
        Clock.schedule_once(lambda dt: self._safe_animate("face_rotation", -0.1, 0.08), 0.28)
        Clock.schedule_once(lambda dt: self._safe_animate("face_rotation", 0.0, 0.1), 0.36)
    
    def _action_bounce(self):
        """Excited bounce"""
        if not self.adapter: return
        self._safe_animate("scale", 1.1, 0.1)
        Clock.schedule_once(lambda dt: self._safe_animate("scale", 0.95, 0.1), 0.1)
        Clock.schedule_once(lambda dt: self._safe_animate("scale", 1.0, 0.15, "elastic"), 0.2)
    
    def _action_spin(self):
        """Quick playful spin"""
        if not self.adapter: return
        self._safe_animate("face_rotation", 1.0, 0.3, "in_out")
        self._safe_animate("scale", 0.9, 0.15)
        Clock.schedule_once(lambda dt: self._safe_animate("scale", 1.0, 0.15), 0.15)
        Clock.schedule_once(lambda dt: self._safe_animate("face_rotation", 0.0, 0.2), 0.3)
    
    def _action_tilt_head(self):
        """Curious head tilt"""
        if not self.adapter: return
        direction = random.choice([-1, 1])
        self._safe_animate("face_rotation", 0.2 * direction, 0.3, "in_out")
        Clock.schedule_once(lambda dt: self._safe_animate("face_rotation", 0.0, 0.5), 0.3)
    
    def _action_lean_forward(self):
        """Lean in curiously (scale up slightly)"""
        if not self.adapter: return
        self._safe_animate("scale", 1.15, 0.4, "in_out")
        Clock.schedule_once(lambda dt: self._safe_animate("scale", 1.0, 0.6, "in_out"), 0.4)
    
    def _action_drowsy_blink(self):
        """Slow, sleepy blink"""
        if not self.adapter: return
        self._safe_animate("eye_open_l", 0.3, 0.4)
        self._safe_animate("eye_open_r", 0.3, 0.4)
        Clock.schedule_once(lambda dt: [self._safe_animate("eye_open_l", 0.1, 0.3), self._safe_animate("eye_open_r", 0.1, 0.3)], 0.4)
        Clock.schedule_once(lambda dt: [self._safe_animate("eye_open_l", 0.5, 0.5), self._safe_animate("eye_open_r", 0.5, 0.5)], 0.7)
        Clock.schedule_once(lambda dt: [self._safe_animate("eye_open_l", 1.0, 0.4), self._safe_animate("eye_open_r", 1.0, 0.4)], 1.2)
    
    def _action_yawn(self):
        """Yawning animation"""
        if not self.adapter: return
        self._safe_animate("mouth_open", 0.8, 0.5)
        self._safe_animate("mouth_curve", -0.2, 0.5)
        Clock.schedule_once(lambda dt: [
            self._safe_animate("mouth_open", 0.9, 0.8),
            self._safe_animate("eye_open_l", 0.3, 0.8),
            self._safe_animate("eye_open_r", 0.3, 0.8)
        ], 0.5)
        Clock.schedule_once(lambda dt: [
            self._safe_animate("mouth_open", 0.2, 0.4),
            self._safe_animate("eye_open_l", 1.0, 0.4),
            self._safe_animate("eye_open_r", 1.0, 0.4),
            self._safe_animate("mouth_curve", 0.1, 0.4)
        ], 1.3)
    
    def _action_move_to_random_position(self):
        """Move to a random position on screen"""
        positions = list(ScreenPosition)
        # Filter out peek positions for this action
        positions = [p for p in positions if 'PEEK' not in p.name]
        
        new_pos = random.choice(positions)
        self._move_to_position(new_pos)
    
    def _action_peek_from_edge(self):
        """Peek in from an edge of the screen"""
        peek_positions = [
            ScreenPosition.PEEK_LEFT,
            ScreenPosition.PEEK_RIGHT,
            ScreenPosition.PEEK_TOP,
            ScreenPosition.PEEK_BOTTOM
        ]
        
        pos = random.choice(peek_positions)
        self._execute_peek(pos)
    
    def _action_eye_swap(self):
        """Playfully swap eye positions momentarily"""
        # This is a visual gag - eyes swap sides briefly
        original_left = self.geometry.left_eye_offset
        original_right = self.geometry.right_eye_offset
        
        # Store and swap
        self.geometry.left_eye_offset = original_right
        self.geometry.right_eye_offset = original_left
        
        # Trigger reaction
        self._quick_surprised_reaction()
        
        # Swap back after delay
        def restore(dt):
            self.geometry.left_eye_offset = original_left
            self.geometry.right_eye_offset = original_right
        
        Clock.schedule_once(restore, 0.8)
    
    def _action_squash_stretch(self):
        """Squash and stretch for emphasis"""
        if not self.adapter: return
        self._safe_animate("scale", 0.85, 0.1)
        Clock.schedule_once(lambda dt: self._safe_animate("scale", 1.2, 0.15, "elastic"), 0.1)
        Clock.schedule_once(lambda dt: self._safe_animate("scale", 1.0, 0.2, "elastic"), 0.25)
    
    # =========================================================================
    # POSITION AND MOVEMENT
    # =========================================================================
    
    def _move_to_position(self, position: ScreenPosition, duration: float = 0.5):
        """Move face to a named screen position"""
        coords = self._get_position_coords(position)
        
        # Immediate move (removing direct animations)
        self.geometry.screen_x = coords[0]
        self.geometry.screen_y = coords[1]
        self._sync_widget_position()
        
        self._position_history.append(position)
    
    def _get_position_coords(self, position: ScreenPosition) -> Tuple[float, float]:
        """Get normalized (0-1) coordinates for a position"""
        coords = {
            ScreenPosition.CENTER: (0.5, 0.5),
            ScreenPosition.TOP_LEFT: (0.2, 0.8),
            ScreenPosition.TOP_RIGHT: (0.8, 0.8),
            ScreenPosition.BOTTOM_LEFT: (0.2, 0.25),
            ScreenPosition.BOTTOM_RIGHT: (0.8, 0.25),
            ScreenPosition.TOP_CENTER: (0.5, 0.85),
            ScreenPosition.BOTTOM_CENTER: (0.5, 0.2),
            ScreenPosition.LEFT_CENTER: (0.15, 0.5),
            ScreenPosition.RIGHT_CENTER: (0.85, 0.5),
            ScreenPosition.PEEK_LEFT: (-0.1, 0.5),
            ScreenPosition.PEEK_RIGHT: (1.1, 0.5),
            ScreenPosition.PEEK_TOP: (0.5, 1.1),
            ScreenPosition.PEEK_BOTTOM: (0.5, -0.1),
        }
        return coords.get(position, (0.5, 0.5))
    
    def _execute_peek(self, position: ScreenPosition):
        """Execute a peek sequence from edge"""
        start_coords = self._get_position_coords(position)
        end_coords = {
            ScreenPosition.PEEK_LEFT: (0.2, 0.5),
            ScreenPosition.PEEK_RIGHT: (0.8, 0.5),
            ScreenPosition.PEEK_TOP: (0.5, 0.8),
            ScreenPosition.PEEK_BOTTOM: (0.5, 0.25),
        }.get(position, (0.5, 0.5))
        
        # Start off-screen
        self.geometry.screen_x = start_coords[0]
        self.geometry.screen_y = start_coords[1]
        self._sync_widget_position()
        
        # Peek in (simulated sequence)
        Clock.schedule_once(lambda dt: [setattr(self.geometry, 'screen_x', end_coords[0]), setattr(self.geometry, 'screen_y', end_coords[1]), self._sync_widget_position()], 0.4)
        # Hold happens by delay to next steps
        Clock.schedule_once(lambda dt: [setattr(self.geometry, 'screen_x', start_coords[0]), setattr(self.geometry, 'screen_y', start_coords[1]), self._sync_widget_position()], 1.9)
        Clock.schedule_once(lambda dt: [setattr(self.geometry, 'screen_x', 0.5), setattr(self.geometry, 'screen_y', 0.5), self._sync_widget_position()], 2.3)
    
    def _sync_widget_position(self):
        """Sync face widget position from geometry"""
        if self.face_widget:
            self.face_widget.pos_hint = {
                'center_x': self.geometry.screen_x,
                'center_y': self.geometry.screen_y
            }
    
    # =========================================================================
    # REACTIVE BEHAVIORS (called by external systems)
    # =========================================================================
    
    def on_user_speaking_start(self):
        """React to user starting to speak"""
        self.perception.is_user_speaking = True
        self.perception.time_since_interaction = 0
        self._idle_timer = 0
        
        # Look at "user" and show attention
        self._reaction_queue.append(self._react_attention)
    
    def on_user_speaking_end(self):
        """React to user stopping speaking"""
        self.perception.is_user_speaking = False
        
        # Thoughtful pause before responding
        self._reaction_queue.append(self._react_thinking)
    
    def on_ai_speaking_start(self, text: str):
        """React to AI starting to speak"""
        # Expression based on content
        if '?' in text:
            self._reaction_queue.append(self._react_questioning)
        elif '!' in text:
            self._reaction_queue.append(self._react_emphasis)
        else:
            self._reaction_queue.append(self._react_speaking)
    
    def on_ai_speaking_end(self):
        """React to AI finishing speaking"""
        # Return to attentive state
        self._reaction_queue.append(self._react_attentive_listening)
    
    def on_visual_input(self, analysis: Dict[str, Any]):
        """React to visual perception"""
        if analysis.get('user_smiling'):
            self.perception.user_smiling = True
            self._reaction_queue.append(self._react_smile_back)
        
        if analysis.get('sudden_motion'):
            self.perception.sudden_motion = True
            self._reaction_queue.append(self._react_startled)
        
        if analysis.get('eye_contact'):
            self.perception.user_looking = True
            self._reaction_queue.append(self._react_eye_contact)
    
    def on_audio_input(self, prosody: Dict[str, float]):
        """React to audio prosody"""
        self.perception.audio_energy = prosody.get('volume', 0.5)
        self.perception.audio_pitch = prosody.get('pitch', 0.5)
        self.perception.audio_tempo = prosody.get('tempo', 0.5)
        
        # High energy speech = more animated listening
        if prosody.get('volume', 0.5) > 0.7:
            self.expressiveness = min(1.0, self.expressiveness + 0.1)
    
    def on_intent_detected(self, intent: str):
        """React to detected intent"""
        self.perception.last_intent = intent
        
        # Map intents to reactions
        reactions = {
            'QUESTION': self._react_curious,
            'CONNECT': self._react_friendly,
            'EXPRESS': self._react_empathetic,
            'THANK': self._react_pleased,
            'REQUEST': self._react_helpful,
        }
        
        if intent in reactions:
            self._reaction_queue.append(reactions[intent])
    
    # =========================================================================
    # REACTION IMPLEMENTATIONS
    # =========================================================================
    
    def _react_attention(self):
        """Show attentive listening"""
        if not self.adapter: return
        self.adapter.animate("eye_open_l", 1.0, 0.2)
        self.adapter.animate("eye_open_r", 1.0, 0.2)
        self.adapter.animate("gaze_x", 0.0, 0.2)
        self.adapter.animate("gaze_y", 0.0, 0.2)
        self.adapter.animate("mouth_curve", 0.1, 0.2)
    
    def _react_thinking(self):
        """Thinking expression"""
        if not self.adapter: return
        self._safe_animate("gaze_x", 0.3, 0.3)
        self._safe_animate("gaze_y", 0.2, 0.3)
        self._safe_animate("mouth_curve", 0.0, 0.3)
        Clock.schedule_once(lambda dt: self._safe_animate("gaze_x", -0.2, 0.4), 0.3)
        Clock.schedule_once(lambda dt: [self._safe_animate("gaze_x", 0.0, 0.2), self._safe_animate("gaze_y", 0.0, 0.2)], 0.7)
    
    def _react_questioning(self):
        """Questioning expression"""
        if not self.adapter: return
        self.adapter.animate("brow_raise", 0.4, 0.3)
        self.adapter.animate("face_rotation", 0.15, 0.3)
        self.adapter.animate("eye_open_l", 1.1, 0.3)
        self.adapter.animate("eye_open_r", 1.1, 0.3)
    
    def _react_emphasis(self):
        """Emphatic expression"""
        if not self.adapter: return
        self._safe_animate("scale", 1.1, 0.15)
        self._safe_animate("eye_open_l", 1.0, 0.15)
        self._safe_animate("eye_open_r", 1.0, 0.15)
        self._safe_animate("mouth_curve", 0.3, 0.15)
        Clock.schedule_once(lambda dt: self._safe_animate("scale", 1.0, 0.2), 0.15)
    
    def _react_speaking(self):
        """Normal speaking expression"""
        if not self.adapter: return
        self.adapter.animate("mouth_curve", 0.15, 0.2)
        self.adapter.animate("eye_open_l", 0.9, 0.2)
        self.adapter.animate("eye_open_r", 0.9, 0.2)
    
    def _react_attentive_listening(self):
        """Attentive listening after speaking"""
        if not self.adapter: return
        self.adapter.animate("mouth_curve", 0.05, 0.3)
        self.adapter.animate("eye_open_l", 1.0, 0.3)
        self.adapter.animate("eye_open_r", 1.0, 0.3)
        self.adapter.animate("brow_raise", 0.1, 0.3)
    
    def _react_smile_back(self):
        """Smile in response to user smile"""
        if not self.adapter: return
        self._safe_animate("mouth_curve", 0.6, 0.3)
        self._safe_animate("eye_open_l", 0.85, 0.3)
        self._safe_animate("eye_open_r", 0.85, 0.3)
        Clock.schedule_once(lambda dt: [
            self._safe_animate("mouth_curve", 0.3, 0.5),
            self._safe_animate("eye_open_l", 1.0, 0.5),
            self._safe_animate("eye_open_r", 1.0, 0.5)
        ], 0.3)
    
    def _react_startled(self):
        """Startled reaction to sudden motion"""
        if not self.adapter: return
        self._safe_animate("eye_open_l", 1.2, 0.1)
        self._safe_animate("eye_open_r", 1.2, 0.1)
        self._safe_animate("brow_raise", 0.6, 0.1)
        self._safe_animate("scale", 0.95, 0.1)
        Clock.schedule_once(lambda dt: [
            self._safe_animate("eye_open_l", 1.0, 0.4),
            self._safe_animate("eye_open_r", 1.0, 0.4),
            self._safe_animate("brow_raise", 0.0, 0.4),
            self._safe_animate("scale", 1.0, 0.4)
        ], 0.1)
    
    def _react_eye_contact(self):
        """React to eye contact"""
        if not self.adapter: return
        # Quick blink then soft smile
        self._safe_animate("eye_open_l", 0.0, 0.08)
        self._safe_animate("eye_open_r", 0.0, 0.08)
        Clock.schedule_once(lambda dt: [
            self._safe_animate("eye_open_l", 1.0, 0.15),
            self._safe_animate("eye_open_r", 1.0, 0.15),
            self._safe_animate("mouth_curve", 0.2, 0.15)
        ], 0.08)
    
    def _react_curious(self):
        """Curious expression"""
        if not self.adapter: return
        self.adapter.animate("face_rotation", 0.2, 0.3)
        self.adapter.animate("brow_raise", 0.3, 0.3)
        self.adapter.animate("eye_open_l", 1.05, 0.3)
        self.adapter.animate("eye_open_r", 1.05, 0.3)
        self.adapter.animate("gaze_y", 0.1, 0.3)
    
    def _react_friendly(self):
        """Friendly greeting expression"""
        if not self.adapter: return
        self._safe_animate("mouth_curve", 0.5, 0.2)
        self._safe_animate("eye_open_l", 0.9, 0.2)
        self._safe_animate("eye_open_r", 0.9, 0.2)
        Clock.schedule_once(lambda dt: self._safe_animate("face_rotation", 0.1, 0.15), 0.2)
        Clock.schedule_once(lambda dt: [
            self._safe_animate("face_rotation", 0.0, 0.2),
            self._safe_animate("mouth_curve", 0.3, 0.2)
        ], 0.35)
    
    def _react_empathetic(self):
        """Empathetic expression"""
        if not self.adapter: return
        self.adapter.animate("mouth_curve", 0.1, 0.4)
        self.adapter.animate("brow_raise", -0.1, 0.4)
        self.adapter.animate("face_rotation", 0.15, 0.4)
        self.adapter.animate("eye_open_l", 0.95, 0.4)
        self.adapter.animate("eye_open_r", 0.95, 0.4)
    
    def _react_pleased(self):
        """Pleased expression (after thanks)"""
        if not self.adapter: return
        self._safe_animate("mouth_curve", 0.4, 0.2)
        self._safe_animate("eye_open_l", 0.85, 0.2)
        self._safe_animate("eye_open_r", 0.85, 0.2)
        Clock.schedule_once(lambda dt: [self._safe_animate("eye_open_l", 0.0, 0.1), self._safe_animate("eye_open_r", 0.0, 0.1)], 0.2)
        Clock.schedule_once(lambda dt: [
            self._safe_animate("eye_open_l", 0.9, 0.15),
            self._safe_animate("eye_open_r", 0.9, 0.15),
            self._safe_animate("mouth_curve", 0.3, 0.15)
        ], 0.3)
    
    def _react_helpful(self):
        """Ready-to-help expression"""
        if not self.adapter: return
        self.adapter.animate("brow_raise", 0.2, 0.25)
        self.adapter.animate("eye_open_l", 1.0, 0.25)
        self.adapter.animate("eye_open_r", 1.0, 0.25)
        self.adapter.animate("mouth_curve", 0.15, 0.25)
        self.adapter.animate("scale", 1.05, 0.25)
    
    def _quick_surprised_reaction(self):
        """Quick surprise (for eye swap gag)"""
        if not self.adapter: return
        self._safe_animate("eye_open_l", 1.2, 0.1)
        self._safe_animate("eye_open_r", 1.2, 0.1)
        self._safe_animate("brow_raise", 0.5, 0.1)
        Clock.schedule_once(lambda dt: [
            self._safe_animate("eye_open_l", 1.0, 0.2),
            self._safe_animate("eye_open_r", 1.0, 0.2),
            self._safe_animate("brow_raise", 0.0, 0.2)
        ], 0.1)
    
    # =========================================================================
    # BUBBLE/OVERLAY STATES
    # =========================================================================
    
    def collapse_to_bubble(self, duration: float = 0.5):
        """Collapse face to bubble state"""
        if not self.adapter: return
        self._safe_animate("scale", 0.3, duration, "in_out")
        self._safe_animate("alpha", 0.6, duration, "in_out")
    
    def expand_from_bubble(self, duration: float = 0.4):
        """Expand from bubble to full face"""
        if not self.adapter: return
        self._safe_animate("scale", 1.0, duration, "elastic")
        self._safe_animate("alpha", 1.0, duration)

        # Add a friendly reaction
        Clock.schedule_once(lambda dt: self._react_friendly(), duration)
    
    def is_collapsed(self) -> bool:
        """Check if currently in bubble state"""
        return self.face_widget.scale < 0.5
