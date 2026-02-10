#!/usr/bin/env python3
"""
Offline AI Runtime Authority
============================

SINGLE AUTHORITY over:
- AI lifecycle (summon/dismiss/consolidate)
- Audio input/output ownership
- Vision/camera capture
- Wake/dismiss phrase detection
- State machine enforcement (BOOT→IDLE→LISTENING→THINKING→SPEAKING)
- UI state signaling
- Expression signal routing:
  * Audio prosody (pitch, tempo, volume) → AI.affect
  * Visual observations (faces, gestures) → AI.affect
  * Phonetic signatures → AI.audio.phonetic_lexemes (evolution)
  * Voice fingerprints → AI.voice_profiles (recognition)
  * Sound classes → AI.audio.sound_concept_memory
  * Turn-taking reactions (interrupt, yield, continue)
  * Emotional mirroring
  * Lip sync coordination
- Intro/first-boot sequence
- Consolidation management
- Introvert/Extrovert mode handling
- Corpus training integration

EVOLUTIONARY SYSTEMS ROUTED THROUGH RUNTIME:
    Language evolution        → AI.language.evo
    Phonetic evolution        → AI.audio.phonetic_lexemes
    Voice template evolution  → AI.audio.voice_templates
    Visual percept evolution  → AI.vision.percept_templates
    Sound concept evolution   → AI.audio.sound_concept_memory

No other module may:
- Start/stop microphone
- Start/stop speech
- Change AI state
- Directly access camera
- Trigger consolidation
- Modify affect state directly
"""

import time
import logging
from enum import Enum
from typing import Any, Optional, Callable, Dict, List
from dataclasses import dataclass

# Safe Clock import for both Kivy and non-Kivy environments
try:
    from kivy.clock import Clock
    from kivy.utils import platform
    IS_ANDROID = platform == 'android'
except ImportError:
    Clock = None
    IS_ANDROID = False

# JNIUS detection for Android native features
if IS_ANDROID:
    try:
        from jnius import autoclass
        JNIUS_AVAILABLE = True
    except ImportError:
        JNIUS_AVAILABLE = False
else:
    JNIUS_AVAILABLE = False

# Audio engine
from offline_ai_audio_engine import create_audio_engine, VoiceParams

# Vision capture
from offline_ai_vision_capture import create_vision_capture, VisionFrame

# Expression processing
from offline_ai_expression import (
    process_audio_prosody, 
    process_visual_gesture,
    AffectState,
    play_animation,
    VoiceGnome,
    VisualCompetency
)

# Corpus training - optional, only needed for training mode
try:
    from offline_ai_corpus_trainer import CorpusTrainer, quick_train_ai
    HAS_CORPUS_TRAINER = True
except ImportError as e:
    CorpusTrainer = None
    quick_train_ai = None
    HAS_CORPUS_TRAINER = False
    logging.getLogger(__name__).info(f"[RUNTIME] Corpus trainer not available: {e}")

logger = logging.getLogger(__name__)

# ============================================================================
# SAFE SCHEDULING HELPERS
# ============================================================================

def schedule_once(callback, delay=0):
    """Safely schedule a callback using Clock or threading fallback."""
    if Clock is not None:
        Clock.schedule_once(lambda dt: callback(), delay)
    else:
        import threading
        timer = threading.Timer(delay, callback)
        timer.daemon = True
        timer.start()

def schedule_interval(callback, interval):
    """Safely schedule a recurring callback using Clock or threading fallback."""
    if Clock is not None:
        return Clock.schedule_interval(lambda dt: callback(), interval)
    else:
        # Threading fallback for interval
        import threading
        def repeat():
            while True:
                time.sleep(interval)
                callback()
        t = threading.Thread(target=repeat, daemon=True)
        t.start()
        return t

# ============================================================================
# 1. STATE MACHINE
# ============================================================================

class AIRuntimeState(Enum):
    """Canonical Runtime State Machine."""
    BOOT = "boot"
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    CONSOLIDATING = "consolidating"
    TRAINING = "training"
    SHUTDOWN = "shutdown"


class InteractionMode(Enum):
    """User-selected interaction mode."""
    INTROVERT = "introvert"
    EXTROVERT = "extrovert"


# ============================================================================
# 2. SIGNAL DATA STRUCTURES
# ============================================================================

@dataclass
class AudioSignal:
    """Audio-derived signals for expression system."""
    pitch: float = 0.5
    tempo: float = 0.5
    volume: float = 0.5
    is_speech: bool = True
    has_emphasis: bool = False
    phonetic_signature: Optional[str] = None
    voice_fingerprint: Optional[str] = None
    timestamp: float = 0.0
    
    def to_prosody_tuple(self) -> tuple:
        return (self.pitch, self.tempo, self.volume)


@dataclass
class VisualSignal:
    """Visual-derived signals for expression system."""
    faces_detected: int = 0
    primary_face_x: float = 0.5
    primary_face_y: float = 0.5
    face_size: float = 0.0
    user_smiling: bool = False
    user_frowning: bool = False
    user_surprised: bool = False
    eye_contact: bool = False
    sudden_motion: bool = False
    objects_detected: List[str] = None
    brightness: float = 0.5
    motion_level: float = 0.0
    timestamp: float = 0.0
    
    def __post_init__(self):
        if self.objects_detected is None:
            self.objects_detected = []
    
    def to_observation_dict(self) -> Dict[str, Any]:
        return {
            "faces_detected": self.faces_detected,
            "user_smiling": self.user_smiling,
            "user_frowning": self.user_frowning,
            "user_surprised": self.user_surprised,
            "eye_contact": self.eye_contact,
            "sudden_motion": self.sudden_motion,
            "smile": self.user_smiling,
        }


@dataclass
class PhoneticSignal:
    """Phonetic evolution signal."""
    signature: str
    text_content: Optional[str] = None
    intent: Optional[str] = None
    spectral_features: Optional[Dict] = None
    timestamp: float = 0.0


@dataclass
class SoundEvent:
    """Sound classification for sound concept memory."""
    sound_class: str  # "speech", "music", "ambient", "alarm", "impulse"
    confidence: float
    acoustic_vector: Optional[List[float]] = None
    timestamp: float = 0.0


# ============================================================================
# 3. UI ADAPTER
# ============================================================================

class AIRuntimeUIAdapter:
    """Interface between Runtime and UI."""

    def __init__(self, screen: Any):
        self.screen = screen
        self._is_bubble = False

    @property
    def ai_instance(self):
        """Get AI instance from screen (may be set after adapter creation)."""
        return getattr(self.screen, 'ai_instance', None)

    def set_idle(self, is_introvert: bool = True) -> None:
        """Set idle state - introvert collapses to bubble, extrovert dims."""
        if hasattr(self.screen, '_hide_speech'):
            self.screen._hide_speech()

        ai = self.ai_instance
        if ai and hasattr(ai, 'face_animator'):
            try:
                if is_introvert:
                    # Introvert: Collapse to bubble overlay
                    ai.face_animator.animate("scale", 0.35, 0.6, easing="in_out_quad")
                    ai.face_animator.animate("alpha", 0.7, 0.5)
                    ai.face_animator.animate("mouth_open", 0.0, 0.3)
                    ai.face_animator.animate("eye_open_l", 0.3, 0.5)
                    ai.face_animator.animate("eye_open_r", 0.3, 0.5)
                    self._is_bubble = True
                else:
                    # Extrovert: Just dim slightly, stay full size
                    ai.face_animator.animate("alpha", 0.6, 0.8)
                    ai.face_animator.animate("mouth_open", 0.0, 0.5)
                    ai.face_animator.animate("gaze_y", 0.0, 0.5)
                    self._is_bubble = False
            except Exception as e:
                logger.debug(f"[UI] Idle animation error: {e}")
        logger.debug(f"[UI] IDLE (bubble={self._is_bubble})")

    def set_listening(self) -> None:
        """Expand from bubble if needed and show listening state."""
        if hasattr(self.screen, '_show_speech'):
            self.screen._show_speech("Listening...", is_ai=False)

        ai = self.ai_instance
        if ai and hasattr(ai, 'face_animator'):
            try:
                # Always expand from bubble first
                if self._is_bubble:
                    ai.face_animator.animate("scale", 1.0, 0.4, easing="out_back")
                    self._is_bubble = False

                ai.face_animator.animate("alpha", 1.0, 0.3)
                ai.face_animator.animate("eye_open_l", 0.8, 0.3)
                ai.face_animator.animate("eye_open_r", 0.8, 0.3)
                ai.face_animator.animate("gaze_x", 0.0, 0.3)
                ai.face_animator.animate("gaze_y", 0.0, 0.3)
                logger.info("[UI] Face expanded to listening state")
            except Exception as e:
                logger.error(f"[UI] Listening animation error: {e}")
        else:
            logger.warning(f"[UI] No face_animator available for listening state")
    
    def set_thinking(self) -> None:
        if hasattr(self.screen, '_show_speech'):
            self.screen._show_speech("Thinking...", is_ai=True)
        ai = self.ai_instance
        if ai and hasattr(ai, 'face_animator'):
            try:
                ai.face_animator.animate("gaze_y", 0.0, 0.3)
                ai.face_animator.animate("gaze_x", 0.08, 0.4)
                ai.face_animator.animate("brow_raise", 0.1, 0.5)
                ai.face_animator.animate("mouth_curve", 0.05, 0.3)
            except:
                pass
        logger.debug("[UI] THINKING")

    def set_speaking(self, text: str) -> None:
        if hasattr(self.screen, '_show_speech'):
            self.screen._show_speech(text, is_ai=True)
        ai = self.ai_instance
        if ai and hasattr(ai, 'face_animator'):
            try:
                ai.face_animator.animate("gaze_y", 0.05, 0.3)
                ai.face_animator.animate("gaze_x", 0.0, 0.3)
                ai.face_animator.animate("brow_raise", 0.0, 0.3)
                ai.face_animator.animate("mouth_curve", 0.1, 0.2)
            except:
                pass
        logger.debug(f"[UI] SPEAKING: {text[:50]}...")
    
    def set_consolidating(self) -> None:
        if hasattr(self.screen, '_show_speech'):
            self.screen._show_speech("Consolidating...", is_ai=True)
        logger.debug("[UI] CONSOLIDATING")
    
    def show_wake_acknowledgment(self) -> None:
        ai = self.ai_instance
        if ai and hasattr(ai, 'face_animator'):
            try:
                # Force alpha to full first (in case it was dimmed in idle)
                ai.face_animator.animate("alpha", 1.0, 0.1)
                ai.face_animator.animate("eye_open_l", 1.0, 0.1)
                ai.face_animator.animate("eye_open_r", 1.0, 0.1)
                ai.face_animator.animate("brow_raise", 0.2, 0.2)
                if hasattr(ai, 'emote_system'):
                    ai.emote_system.trigger_gesture("blink")
                logger.info("[UI] Wake acknowledgment shown")
            except Exception as e:
                logger.error(f"[UI] Wake ack error: {e}")


# ============================================================================
# 4. RUNTIME AUTHORITY
# ============================================================================

class OfflineAIRuntime:
    """
    SINGLE AUTHORITY over AI lifecycle, I/O, and state.
    
    FULL EXPRESSION SIGNAL ROUTING:
    - Audio prosody → AI.affect
    - Visual observations → AI.affect
    - Phonetic signatures → AI.audio.phonetic_lexemes (evolution)
    - Voice fingerprints → AI.voice_profiles (speaker recognition)
    - Sound classes → AI.audio.sound_concept_memory
    - Visual percepts → AI.vision.percept_templates (evolution)
    - TTS phonemes → AI.lip_sync
    - User interrupt → AI.emote_system
    """
    
    def __init__(
        self,
        ai: Any,
        ui_adapter: AIRuntimeUIAdapter,
        interaction_mode: InteractionMode = InteractionMode.INTROVERT,
        language: str = "en-US",
        enable_vision: bool = True,
        enable_corpus_training: bool = False
    ):
        self.ai = ai
        self.ui = ui_adapter
        self.mode = interaction_mode
        
        # State machine
        self.state = AIRuntimeState.BOOT
        self.previous_state: Optional[AIRuntimeState] = None
        self.last_state_change = time.time()
        
        # Audio subsystem
        self.audio = create_audio_engine(language)
        self.audio.on_speech_result = self._on_speech_result
        self.audio.on_speaking_complete = self._on_speech_complete
        
        # Vision subsystem
        self.vision = None
        if enable_vision:
            self.vision = create_vision_capture("front")
            self.vision.on_person_present = self._on_person_present
            self.vision.on_frame = self._on_vision_frame
        
        # Corpus trainer
        self.corpus_trainer = None
        if enable_corpus_training and HAS_CORPUS_TRAINER and CorpusTrainer:
            self.corpus_trainer = CorpusTrainer(ai)
        
        # Control phrases
        self.wake_phrases = ["come on", "ko", "hey", "okay"]
        self.dismiss_phrases = [
            "goodbye", "bye", "see you", "go away", "dismiss",
            "sleep", "rest", "that's all", "im done", "i'm done", "later"
        ]
        
        # AI name
        self.ai_name = ""
        
        # State tracking
        self.listening_enabled = False
        self.speech_in_progress = False
        
        # Expression signals
        self._last_audio_signal = AudioSignal()
        self._last_visual_signal = VisualSignal()
        
        # Tracking
        self._consolidation_pending = False
        self._last_interaction_time = time.time()
        self._idle_consolidation_timeout = 45
        self._intro_complete = False
        self._first_boot = False
        self._pre_armed = False

        # Idle timeout configuration (extrovert waits longer before going idle)
        self._introvert_idle_timeout = 30   # seconds of silence before idle
        self._extrovert_idle_timeout = 120  # extrovert waits longer
        self._extrovert_spontaneous_interval = (45, 90)  # random interval for spontaneous speech

        # Spontaneous speech tracking (extrovert mode)
        self._last_spontaneous_time = time.time()
        self._spontaneous_phrases = [
            "Just thinking about things...",
            "It's nice spending time with you.",
            "Anything on your mind?",
            "I'm here if you want to chat.",
            "Hey, what are you up to?",
        ]

        # Evolution queue - changes queued during interaction, processed at consolidation
        self._evolution_queue = {
            "lexicon": [],      # Lexical updates to process
            "audio": [],        # Phonetic/sound updates
            "vision": [],       # Visual percept updates
            "language": [],     # Intent/template updates
            "habit": [],        # Habit pattern updates
        }

        # Events
        self._scheduled_events = []
        self._expression_update_event = None
        self._idle_check_event = None

        logger.info(f"[RUNTIME] Initialized (mode={interaction_mode.value})")
    
    # ========================================================================
    # LIFECYCLE
    # ========================================================================
    
    def boot(self) -> bool:
        """Boot the runtime."""
        if self.state != AIRuntimeState.BOOT:
            return False

        self._transition_to(AIRuntimeState.IDLE)
        is_introvert = (self.mode == InteractionMode.INTROVERT)
        self.ui.set_idle(is_introvert=is_introvert)
        
        # Try to enable listening - audio engine uses lazy init
        # so it might not be ready immediately
        listening_started = self.enable_listening()
        if not listening_started:
            # Retry after delay to give audio time to initialize
            def _retry_listening(dt):
                if self.state == AIRuntimeState.IDLE:
                    result = self.enable_listening()
                    logger.info(f"[RUNTIME] Retry listening: {result}")
            schedule_once(_retry_listening, 1.0)

        if self.vision:
            vision_started = self.vision.start()
            if not vision_started:
                # Retry after delay (permissions might not be granted yet)
                def _retry_vision():
                    if self.vision and not self.vision.is_active():
                        result = self.vision.start()
                        logger.info(f"[RUNTIME] Retry vision: {result}")
                schedule_once(_retry_vision, 1.5)

        self._start_expression_loop()
        self._start_idle_check_loop()

        logger.info("[RUNTIME] Boot complete")
        return True

    def prepare_for_summon(self):
        """Pre-initialize I/O engines without asserting authority."""
        logger.info("[RUNTIME] Pre-arming I/O engines for summon...")

        # Force lazy initialization of TTS
        if hasattr(self.audio, 'tts'):
            _ = self.audio.tts.is_ready

        # Force lazy initialization of speech recognizer
        if hasattr(self.audio, 'recognizer'):
            _ = self.audio.recognizer.is_ready

        # Force lazy initialization of vision capture (if enabled)
        if self.vision and hasattr(self.vision, 'camera'):
            _ = getattr(self.vision.camera, 'state', None)

        # Bind callbacks if not already bound
        self.audio.on_speech_result = self._on_speech_result
        self.audio.on_speaking_complete = self._on_speech_complete

        # Record internal readiness flags
        self._pre_armed = True
        logger.info("[RUNTIME] Pre-arm complete")

    def _request_audio_focus(self) -> bool:
        """Explicitly request audio focus on Android."""
        if not IS_ANDROID or not JNIUS_AVAILABLE:
            return True

        try:
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            Context = autoclass('android.content.Context')
            AudioManager = autoclass('android.media.AudioManager')

            activity = PythonActivity.mActivity
            audio_manager = activity.getSystemService(Context.AUDIO_SERVICE)

            # Request focus - AUDIOFOCUS_GAIN = 1, STREAM_MUSIC = 3
            result = audio_manager.requestAudioFocus(None, 3, 1)
            granted = (result == 1) # AUDIOFOCUS_REQUEST_GRANTED = 1
            logger.info(f"[RUNTIME] Audio focus request: {'GRANTED' if granted else 'DENIED'}")
            return granted
        except Exception as e:
            logger.error(f"[RUNTIME] Audio focus request failed: {e}")
            return False

    def reinit_after_permissions(self):
        """
        Called after Android permissions are granted.
        Re-initializes audio and vision if they failed initially.
        """
        logger.info("[RUNTIME] Reinitializing after permissions grant...")

        # Retry audio
        if not self.audio.is_ready:
            logger.info("[RUNTIME] Retrying audio initialization...")
            # Force lazy init
            _ = self.audio.is_ready
            schedule_once(lambda: self.enable_listening(), 0.5)

        # Retry vision
        if self.vision and not self.vision.is_active():
            logger.info("[RUNTIME] Retrying vision initialization...")
            self.vision.start()
    
    def shutdown(self) -> None:
        """Shutdown the runtime."""
        logger.info("[RUNTIME] Shutting down...")

        # Process any queued evolution before shutdown
        self._process_evolution_queue()

        self._stop_expression_loop()
        self._stop_idle_check_loop()

        for event in self._scheduled_events:
            try:
                event.cancel()
            except:
                pass
        self._scheduled_events.clear()

        self.disable_listening()
        self.audio.stop_speaking()
        self.audio.shutdown()

        if self.vision:
            self.vision.stop()

        self._transition_to(AIRuntimeState.SHUTDOWN)
    
    def summon(self, trigger: str, is_first_boot: bool = False) -> bool:
        """Summon the AI."""
        if self.state not in [AIRuntimeState.IDLE, AIRuntimeState.BOOT]:
            logger.warning(f"[RUNTIME] Cannot summon - invalid state: {self.state}")
            return False
        
        logger.info(f"[RUNTIME] Summoned: {trigger}")
        
        self.ai_name = self._extract_ai_name(trigger)
        if self.ai:
            self.ai.ai_name = self.ai_name
            logger.info(f"[RUNTIME] AI name set to: {self.ai_name}")
        else:
            logger.error("[RUNTIME] No AI instance available!")
        
        self._first_boot = is_first_boot
        
        # --- MANDATORY CANONICAL ACTIVATION SEQUENCE (ANDROID-CORRECT) ---

        # 1. Transition runtime state to LISTENING / ENGAGED
        logger.info("[RUNTIME] Transitioning to LISTENING...")
        self._transition_to(AIRuntimeState.LISTENING)

        # 2. Request audio focus
        self._request_audio_focus()

        # 3. Issue TTS intro speak() request (fire-and-forget)
        logger.info("[RUNTIME] Issuing TTS intro speak request...")
        self._speak_text("Initializing.", on_complete=None)

        # 4. Immediately proceed with intro logic, UI activation, face attachment, and vision activation
        # DO NOT wait for onStart or is_speaking. Progression is gated only on platform-guaranteed signals.

        if self.vision and not self.vision.is_active():
            logger.info("[RUNTIME] Activating vision...")
            self.vision.start()

        self._continue_summon(trigger, is_first_boot)

        return True

    def _continue_summon(self, trigger: str, is_first_boot: bool):
        """Persona logic and intro sequence."""
        logger.info("[RUNTIME] Enabling listening...")
        listening_result = self.enable_listening()
        logger.info(f"[RUNTIME] Listening enabled: {listening_result}")
        
        logger.info("[RUNTIME] Showing wake acknowledgment...")
        self.ui.show_wake_acknowledgment()
        
        # Voice profile recognition on summon
        if trigger and self.ai and hasattr(self.ai, 'voice_profiles'):
            voice_fp = self._extract_voice_fingerprint(trigger)
            if voice_fp:
                profile = self.ai.voice_profiles.identify_voice(voice_fp)
                logger.info(f"[RUNTIME] Voice profile: {profile.fingerprint[:16]}...")
        
        if self.ai and hasattr(self.ai, 'summon'):
            from offline_ai_expression import OnboardingProfile
            profile = OnboardingProfile(
                user_name=getattr(self.ai, 'user_name', 'User'),
                ai_name=self.ai_name,
                favorite_color=getattr(self.ai, 'favorite_color', 'blue'),
                mode="extrovert" if self.mode == InteractionMode.EXTROVERT else "introvert",
                wake_phrase=trigger
            )
            self.ai.summon(trigger, profile=profile)
        
        # Intro is handled by AI.summon() via run_intro() - don't call twice
        if not is_first_boot:
            greeting = f"Hello again! I'm {self.ai_name}."
            # Defer speech slightly to give TTS time to initialize
            def _deferred_speak(dt):
                self._speak_text(greeting)
            schedule_once(_deferred_speak, 0.5)
    
    def dismiss(self) -> bool:
        """Dismiss the AI."""
        if self.state == AIRuntimeState.IDLE:
            return False
        
        logger.info("[RUNTIME] Dismissal")
        self.audio.stop_speaking()
        self._transition_to(AIRuntimeState.CONSOLIDATING)
        
        farewell = self._get_farewell()
        self._speak_text(farewell, on_complete=self._post_dismiss_consolidation)
        
        return True
    
    def _post_dismiss_consolidation(self):
        """Post-dismissal consolidation - processes queued evolution updates."""
        # First process any queued evolution updates
        self._process_evolution_queue()

        # Then run AI's consolidation stage
        if self.ai and hasattr(self.ai, 'consolidation_stage'):
            try:
                self.ai.consolidation_stage()
            except Exception as e:
                logger.error(f"[RUNTIME] Consolidation error: {e}")

        is_introvert = (self.mode == InteractionMode.INTROVERT)
        self._transition_to(AIRuntimeState.IDLE)
        self.ui.set_idle(is_introvert=is_introvert)
        self.enable_listening()

    # ========================================================================
    # EVOLUTION QUEUE - Changes queued during interaction, applied at consolidation
    # ========================================================================

    def queue_evolution(self, category: str, update: dict):
        """
        Queue an evolution update to be processed during consolidation.
        This prevents behavior changes mid-interaction.

        Categories: lexicon, audio, vision, language, habit
        """
        if category in self._evolution_queue:
            self._evolution_queue[category].append(update)
            logger.debug(f"[RUNTIME] Queued {category} evolution: {len(self._evolution_queue[category])} pending")

    def _process_evolution_queue(self):
        """Process all queued evolution updates during consolidation."""
        if not self.ai:
            return

        total_processed = 0

        # Process lexicon updates
        for update in self._evolution_queue.get("lexicon", []):
            try:
                if hasattr(self.ai, 'lexicon') and self.ai.lexicon:
                    if update.get("action") == "record":
                        self.ai.lexicon.process_text(update.get("text", ""), update.get("intent"))
                    total_processed += 1
            except Exception as e:
                logger.debug(f"[RUNTIME] Lexicon evolution error: {e}")

        # Process audio/phonetic updates
        for update in self._evolution_queue.get("audio", []):
            try:
                if hasattr(self.ai, 'audio') and self.ai.audio:
                    self.ai.audio.record_audio_interaction(
                        audio_features=update.get("features", {}),
                        text_content=update.get("text"),
                        intent=update.get("intent")
                    )
                    total_processed += 1
            except Exception as e:
                logger.debug(f"[RUNTIME] Audio evolution error: {e}")

        # Process vision updates
        for update in self._evolution_queue.get("vision", []):
            try:
                if hasattr(self.ai, 'vision') and self.ai.vision:
                    if update.get("action") == "grounding":
                        self.ai.vision.record_grounding(
                            update.get("intent", ""),
                            update.get("lexeme", ""),
                            update.get("visual_concept", ""),
                            update.get("sound_class", "speech")
                        )
                    total_processed += 1
            except Exception as e:
                logger.debug(f"[RUNTIME] Vision evolution error: {e}")

        # Process language/intent updates
        for update in self._evolution_queue.get("language", []):
            try:
                if hasattr(self.ai, 'language') and self.ai.language:
                    if hasattr(self.ai.language, 'intent_evolution') and self.ai.language.intent_evolution:
                        evo = self.ai.language.intent_evolution.evo
                        if evo and update.get("co_occurrence"):
                            evo.record_co_occurrence(
                                update["co_occurrence"][0],
                                update["co_occurrence"][1]
                            )
                    total_processed += 1
            except Exception as e:
                logger.debug(f"[RUNTIME] Language evolution error: {e}")

        # Process habit updates
        for update in self._evolution_queue.get("habit", []):
            try:
                if hasattr(self.ai, 'habit_engine') and self.ai.habit_engine:
                    if update.get("pattern"):
                        self.ai.habit_engine.record_pattern(update["pattern"])
                    total_processed += 1
            except Exception as e:
                logger.debug(f"[RUNTIME] Habit evolution error: {e}")

        # Clear queues after processing
        for key in self._evolution_queue:
            self._evolution_queue[key] = []

        if total_processed > 0:
            logger.info(f"[RUNTIME] Processed {total_processed} queued evolution updates")
    
    # ========================================================================
    # EXPRESSION SIGNAL ROUTING (COMPLETE)
    # ========================================================================
    
    def _start_expression_loop(self):
        """Start expression update loop."""
        def _update():
            self._update_expression_systems()

        self._expression_update_event = schedule_interval(_update, 1.0 / 30)

    def _stop_expression_loop(self):
        """Stop expression loop."""
        if self._expression_update_event:
            try:
                self._expression_update_event.cancel()
            except:
                pass
            self._expression_update_event = None

    def _start_idle_check_loop(self):
        """Start loop that checks for idle timeout and spontaneous speech."""
        def _check():
            self._check_idle_timeout()

        self._idle_check_event = schedule_interval(_check, 5.0)  # Check every 5 seconds

    def _stop_idle_check_loop(self):
        """Stop idle check loop."""
        if self._idle_check_event:
            try:
                self._idle_check_event.cancel()
            except:
                pass
            self._idle_check_event = None

    def _check_idle_timeout(self):
        """Check if we should transition to idle or trigger spontaneous speech."""
        if self.state in [AIRuntimeState.SPEAKING, AIRuntimeState.THINKING,
                          AIRuntimeState.CONSOLIDATING, AIRuntimeState.TRAINING]:
            return

        now = time.time()
        time_since_interaction = now - self._last_interaction_time

        # Determine timeout based on mode
        if self.mode == InteractionMode.INTROVERT:
            idle_timeout = self._introvert_idle_timeout
        else:
            idle_timeout = self._extrovert_idle_timeout

        # If in LISTENING and past timeout, go to IDLE
        if self.state == AIRuntimeState.LISTENING and time_since_interaction > idle_timeout:
            logger.info(f"[RUNTIME] Idle timeout ({time_since_interaction:.1f}s > {idle_timeout}s)")
            self._transition_to(AIRuntimeState.IDLE)
            is_introvert = (self.mode == InteractionMode.INTROVERT)
            self.ui.set_idle(is_introvert=is_introvert)
            return

        # Extrovert spontaneous speech (only when listening, not idle)
        if self.mode == InteractionMode.EXTROVERT and self.state == AIRuntimeState.LISTENING:
            time_since_spontaneous = now - self._last_spontaneous_time
            min_interval, max_interval = self._extrovert_spontaneous_interval

            import random
            threshold = random.uniform(min_interval, max_interval)

            if time_since_spontaneous > threshold:
                self._trigger_spontaneous_speech()
                self._last_spontaneous_time = now

    def _trigger_spontaneous_speech(self):
        """Extrovert mode: Say something unprompted."""
        if self.state != AIRuntimeState.LISTENING:
            return

        import random
        phrase = random.choice(self._spontaneous_phrases)

        # Could also generate context-aware phrases from AI
        if self.ai and hasattr(self.ai, 'get_spontaneous_thought'):
            try:
                thought = self.ai.get_spontaneous_thought()
                if thought:
                    phrase = thought
            except:
                pass

        logger.info(f"[RUNTIME] Spontaneous speech: {phrase}")
        self._speak_text(phrase)

    def _update_expression_systems(self):
        """Update all expression subsystems (30 FPS loop)."""
        if not self.ai:
            return

        dt = 1.0 / 30

        # Face animator (processes animation tracks)
        if hasattr(self.ai, 'face_animator') and self.ai.face_animator:
            try:
                self.ai.face_animator.update(dt)
            except Exception as e:
                logger.debug(f"[RUNTIME] Face animator error: {e}")

        # Emote runtime (affect decay, idle gestures, micro-reactions)
        if hasattr(self.ai, 'emote_runtime') and self.ai.emote_runtime:
            try:
                self.ai.emote_runtime.update()
            except Exception as e:
                logger.debug(f"[RUNTIME] Emote error: {e}")

        # Creative face engine
        if hasattr(self.ai, 'creative_face') and self.ai.creative_face:
            try:
                self.ai.creative_face.update(dt)
            except:
                pass

        # Lip sync engine (processes phoneme queue)
        if hasattr(self.ai, 'lip_sync') and self.ai.lip_sync:
            try:
                if hasattr(self.ai.lip_sync, 'update'):
                    self.ai.lip_sync.update(dt)
            except:
                pass

        # Micro-reaction engine (handles visual observation reactions)
        if hasattr(self.ai, 'micro_react') and self.ai.micro_react:
            try:
                if hasattr(self.ai.micro_react, 'update'):
                    self.ai.micro_react.update(dt)
            except:
                pass

        # Persona drift (subtle personality shifts - low frequency)
        # Only update occasionally, not every frame
        if hasattr(self, '_persona_drift_counter'):
            self._persona_drift_counter += 1
        else:
            self._persona_drift_counter = 0

        if self._persona_drift_counter >= 900:  # Every 30 seconds at 30fps
            self._persona_drift_counter = 0
            if hasattr(self.ai, 'persona_drift') and self.ai.persona_drift:
                try:
                    self.ai.persona_drift.drift_step()
                except:
                    pass
    
    # ---- AUDIO SIGNALS ----
    
    def process_audio_prosody(self, signal: AudioSignal):
        """Route audio prosody to affect and voice systems."""
        if not self.ai:
            return
        
        # Update affect
        if hasattr(self.ai, 'affect'):
            try:
                process_audio_prosody(
                    signal.pitch, signal.tempo, signal.volume,
                    self.ai.affect
                )
            except:
                pass
        
        # Update voice bridge for TTS modulation
        if hasattr(self.ai, 'voice_bridge') and self.ai.voice_bridge:
            try:
                self.ai.voice_bridge.apply_affect(self.ai.affect)
            except:
                pass
        
        # Update Voice Gnome (voice genome) if available
        if hasattr(self.ai, 'governor') and self.ai.governor:
            try:
                params = self.ai.governor.get_personalized_parameters()
                voice_gnome_data = params.get("voice_gnome", {})
                # Modulate based on prosody
                voice_gnome_data["pitch"] = signal.pitch
                voice_gnome_data["rate"] = 0.5 + (signal.tempo - 0.5) * 0.5
            except:
                pass
        
        self._last_audio_signal = signal
    
    def process_phonetic_signature(self, signal: PhoneticSignal):
        """
        Route phonetic signatures to phonetic lexeme evolution.
        Evolution is QUEUED for consolidation, not applied immediately.
        """
        if not self.ai:
            return

        # Queue for consolidation instead of immediate update
        self.queue_evolution("audio", {
            "features": {
                "phonetic_signature": signal.signature,
                "spectral_features": signal.spectral_features or {},
            },
            "text": signal.text_content,
            "intent": signal.intent
        })

        logger.debug(f"[RUNTIME] Phonetic signature queued: {signal.signature}")

    def process_sound_event(self, event: SoundEvent):
        """
        Route sound events to sound concept memory.
        Evolution is QUEUED for consolidation, not applied immediately.
        """
        if not self.ai:
            return

        # Queue for consolidation instead of immediate update
        self.queue_evolution("audio", {
            "features": {
                "acoustic_vector": event.acoustic_vector or [0.5] * 64,
                "category": event.sound_class,
            },
            "intent": event.sound_class.upper()
        })

        # Visual reactions ARE immediate (they don't change learned behavior)
        if event.sound_class == "alarm" and hasattr(self.ai, 'emote_system'):
            try:
                self.ai.emote_system.trigger_gesture("surprise")
            except:
                pass

        logger.debug(f"[RUNTIME] Sound event queued: {event.sound_class}")
    
    def process_voice_recognition(self, fingerprint: str, text: str = None):
        """
        Process voice fingerprint for speaker recognition.
        Routes to voice_profiles for identification.
        """
        if not self.ai or not hasattr(self.ai, 'voice_profiles'):
            return None
        
        try:
            profile = self.ai.voice_profiles.identify_voice(fingerprint)
            
            # Store in memory if text available
            if text and hasattr(self.ai, 'memory'):
                # Associate this voice with the interaction
                pass
            
            logger.debug(f"[RUNTIME] Voice recognized: {fingerprint[:16]}...")
            return profile
        except Exception as e:
            logger.debug(f"[RUNTIME] Voice recognition error: {e}")
            return None
    
    # ---- VISUAL SIGNALS ----
    
    def process_visual_gesture(self, signal: VisualSignal):
        """Route visual observations to affect and vision systems."""
        if not self.ai:
            return
        
        obs = signal.to_observation_dict()
        
        # Update affect
        if hasattr(self.ai, 'affect'):
            try:
                process_visual_gesture(obs, self.ai.affect)
            except:
                pass
        
        # Update micro-reaction engine
        if hasattr(self.ai, 'micro_react') and self.ai.micro_react:
            try:
                self.ai.micro_react.process_observation(obs)
            except:
                pass
        
        # Visual competency evolution
        if hasattr(self.ai, 'vision') and self.ai.vision:
            try:
                # Create visual analysis for vision manager
                analysis = {
                    "objects": signal.objects_detected or [],
                    "focus_level": 0.5 + signal.face_size * 0.5,
                    "detail_captured": signal.faces_detected > 0
                }
                self.ai.vision.last_analysis = analysis
                
                # Process percepts for template evolution
                for obj in signal.objects_detected:
                    if obj not in self.ai.vision.percept_templates:
                        from offline_ai_expression import VisionPerceptTemplate
                        self.ai.vision.percept_templates[obj] = VisionPerceptTemplate(obj)
                    template = self.ai.vision.percept_templates[obj]
                    template.usage_count += 1
                    template.confidence = min(1.0, template.confidence + 0.05)
                    
                    # Clustering/promotion trigger
                    if template.usage_count % 3 == 0:
                        if hasattr(self.ai.vision, 'cluster_and_promote'):
                            self.ai.vision.cluster_and_promote(obj)
            except:
                pass
        
        # Mirror smile
        if signal.user_smiling and hasattr(self.ai, 'emote_system'):
            try:
                self.ai.emote_system.trigger_gesture("smile")
            except:
                pass
        
        self._last_visual_signal = signal
    
    def process_visual_grounding(self, intent: str, lexeme: str, visual_concept: str, sound_class: str = "speech"):
        """
        Route multimodal grounding to vision system.
        Evolution is QUEUED for consolidation, not applied immediately.
        """
        if not self.ai:
            return

        # Queue for consolidation instead of immediate update
        self.queue_evolution("vision", {
            "action": "grounding",
            "intent": intent,
            "lexeme": lexeme,
            "visual_concept": visual_concept,
            "sound_class": sound_class
        })

        logger.debug(f"[RUNTIME] Grounding queued: {intent}-{lexeme}-{visual_concept}")
    
    # ---- TTS/LIP SYNC ----
    
    def process_tts_phoneme(self, phoneme: str):
        """Route TTS phonemes to lip sync."""
        if not self.ai or not hasattr(self.ai, 'lip_sync'):
            return
        
        try:
            self.ai.lip_sync.on_phoneme(phoneme)
        except:
            pass
    
    def process_tts_word(self, word: str):
        """Process TTS word for additional synchronization."""
        # Could trigger emphasis animations for key words
        pass
    
    # ---- INTERRUPT/REACTION ----
    
    def _handle_interruption(self):
        """Handle user interrupt."""
        logger.info("[RUNTIME] Interruption")
        self.audio.stop_speaking()
        
        if self.ai and hasattr(self.ai, 'emote_system'):
            try:
                self.ai.emote_system.trigger_interrupt_reaction()
            except:
                pass
    
    # ========================================================================
    # AUDIO CALLBACKS
    # ========================================================================
    
    def _on_speech_result(self, text: str) -> None:
        """Handle speech recognition with full signal extraction."""
        if not text or not text.strip():
            return
        
        logger.info(f"[RUNTIME] Audio: {text}")
        self._last_interaction_time = time.time()
        
        if self.state == AIRuntimeState.SPEAKING:
            self._handle_interruption()
        
        # Extract simulated signals from text characteristics
        text_hash = hash(text)
        audio_signal = AudioSignal(
            pitch=0.5 + (text_hash % 100) / 200.0,
            tempo=0.6,
            volume=0.7,
            phonetic_signature=self._extract_phonetic_signature(text),
            voice_fingerprint=self._extract_voice_fingerprint(text),
            timestamp=time.time()
        )
        
        # Route all signals
        self.process_audio_prosody(audio_signal)
        
        if audio_signal.phonetic_signature:
            phonetic_signal = PhoneticSignal(
                signature=audio_signal.phonetic_signature,
                text_content=text,
                intent=None  # Will be determined by AI
            )
            self.process_phonetic_signature(phonetic_signal)
        
        if audio_signal.voice_fingerprint:
            self.process_voice_recognition(audio_signal.voice_fingerprint, text)
        
        self._process_text_input(text)
    
    def _extract_phonetic_signature(self, text: str) -> str:
        """Extract simplified phonetic signature from text."""
        # Simplified - would use actual audio features
        words = text.lower().split()
        if not words:
            return "vowel_mid"
        
        # Characterize by first letters of words
        sig = "".join([w[0] for w in words[:3] if w])
        return f"sig_{sig}" if sig else "vowel_mid"
    
    def _extract_voice_fingerprint(self, text: str) -> str:
        """Extract voice fingerprint - simulated."""
        # In real implementation, this comes from audio analysis
        import hashlib
        return hashlib.md5(f"voice_{time.time() // 60}".encode()).hexdigest()[:16]
    
    def _on_speech_complete(self) -> None:
        """Handle TTS completion."""
        self.speech_in_progress = False
        self.on_speech_complete()
    
    # ========================================================================
    # VISION CALLBACKS
    # ========================================================================
    
    def _on_person_present(self, present: bool):
        """Handle person presence."""
        visual_signal = VisualSignal(
            faces_detected=1 if present else 0,
            eye_contact=present,
            timestamp=time.time()
        )
        self.process_visual_gesture(visual_signal)
        
        if self.ai and hasattr(self.ai, 'visible'):
            self.ai.visible = present
    
    def _on_vision_frame(self, frame: VisionFrame):
        """Handle vision frame with full analysis."""
        # Convert faces to visual signal
        signal = VisualSignal(
            faces_detected=len(frame.faces),
            brightness=frame.brightness,
            motion_level=0.5 if frame.motion_detected else 0.0,
            timestamp=frame.timestamp
        )
        
        if frame.faces:
            primary = frame.faces[0]
            signal.primary_face_x = primary.x
            signal.primary_face_y = primary.y
            signal.face_size = primary.width * primary.height
            signal.user_smiling = primary.has_smile
            signal.eye_contact = True
        
        self.process_visual_gesture(signal)
    
    # ========================================================================
    # INPUT PROCESSING
    # ========================================================================
    
    def _process_text_input(self, text: str) -> None:
        """Process text input."""
        normalized = text.lower().strip()
        
        if self._check_control_phrases(normalized):
            return
        
        if self.state == AIRuntimeState.IDLE:
            return
        
        self._process_user_input(text)
    
    def _check_control_phrases(self, text: str) -> bool:
        """Check wake/dismiss phrases."""
        for phrase in self.wake_phrases:
            if phrase.lower() in text:
                ai_name = self.ai_name.lower() if self.ai_name else ""
                if (ai_name and ai_name in text) or self.state == AIRuntimeState.IDLE:
                    if self.state == AIRuntimeState.IDLE:
                        self.summon(text)
                        return True
        
        for phrase in self.dismiss_phrases:
            if phrase.lower() in text:
                if self.state != AIRuntimeState.IDLE:
                    self.dismiss()
                    return True
        
        return False
    
    def _process_user_input(self, text: str) -> None:
        """Process user input through AI."""
        self._transition_to(AIRuntimeState.THINKING)
        self.disable_listening()
        
        if not self.ai or not hasattr(self.ai, 'process_input'):
            self.on_response_ready(f"I heard: {text}")
            return
        
        try:
            analysis = self.ai.process_input(text)
            
            if analysis.get("ignored"):
                self._transition_to(AIRuntimeState.LISTENING)
                self.enable_listening()
                return
            
            # Update phonetic signal with determined intent
            if hasattr(self.ai, 'audio') and analysis.get('language', {}).get('intent'):
                phonetic_signal = PhoneticSignal(
                    signature=self._extract_phonetic_signature(text),
                    text_content=text,
                    intent=analysis['language']['intent']
                )
                self.process_phonetic_signature(phonetic_signal)
            
            self._generate_response(analysis)
        except Exception as e:
            logger.error(f"[RUNTIME] Processing error: {e}")
            self._transition_to(AIRuntimeState.LISTENING)
            self.enable_listening()
    
    def _generate_response(self, analysis: dict) -> None:
        """Generate response."""
        try:
            intent = analysis.get('language', {}).get('intent', 'INFORM')
            user_input = analysis.get('user_input', '')
            
            if hasattr(self.ai, '_get_contextual_response'):
                content = self.ai._get_contextual_response(intent, user_input)
            else:
                content = "I understand."
            
            if hasattr(self.ai, 'generate_response'):
                response = self.ai.generate_response(analysis, content)
                text = response.get("text", content) if isinstance(response, dict) else str(response)
            else:
                text = content
            
            self.on_response_ready(text)
        except Exception as e:
            logger.error(f"[RUNTIME] Response error: {e}")
            self._transition_to(AIRuntimeState.LISTENING)
            self.enable_listening()
    
    def on_response_ready(self, text: str) -> None:
        """Response ready."""
        if not text:
            self._transition_to(AIRuntimeState.LISTENING)
            self.enable_listening()
            return
        
        self._transition_to(AIRuntimeState.SPEAKING)
        self.speech_in_progress = True
        self.ui.set_speaking(text)
        
        phoneme_cb = self.process_tts_phoneme
        self._speak_text(text, phoneme_cb=phoneme_cb)
    
    def on_speech_complete(self) -> None:
        """Speech complete - mode-based next state."""
        self.speech_in_progress = False
        self._last_interaction_time = time.time()  # Reset interaction timer

        if self.mode == InteractionMode.EXTROVERT:
            # Extrovert stays listening (will idle after longer timeout)
            self._transition_to(AIRuntimeState.LISTENING)
            self.enable_listening()
        else:
            # Introvert goes to idle immediately (collapses to bubble)
            self._transition_to(AIRuntimeState.IDLE)
            self.ui.set_idle(is_introvert=True)
            self.enable_listening()
    
    # ========================================================================
    # AUDIO CONTROL
    # ========================================================================
    
    def enable_listening(self) -> bool:
        """Enable listening."""
        if not self.audio.is_ready:
            return False
        
        if not self.listening_enabled:
            self.audio.start_listening(continuous=True)
            self.listening_enabled = True
        
        return True
    
    def disable_listening(self) -> bool:
        """Disable listening."""
        if self.listening_enabled:
            self.audio.stop_listening()
            self.listening_enabled = False
        return True
    
    def _speak_text(self, text: str, on_complete: Callable = None, phoneme_cb = None):
        """Speak text with lip sync."""
        if not text:
            if on_complete:
                on_complete()
            return
        
        logger.info(f"[RUNTIME] Speaking: {text[:50]}...")
        logger.info(f"[RUNTIME] Audio ready: {self.audio.is_ready}")
        
        # CRITICAL: Don't try to speak if audio isn't ready - prevents crash
        if not self.audio.is_ready:
            logger.warning("[RUNTIME] Audio not ready, skipping speech")
            if on_complete:
                on_complete()
            return
        
        was_listening = self.listening_enabled
        self.disable_listening()
        
        def _phoneme_wrapper(phoneme):
            try:
                if phoneme_cb:
                    phoneme_cb(phoneme)
            except Exception as e:
                logger.debug(f"[RUNTIME] Phoneme callback error: {e}")
        
        def _on_done():
            try:
                if on_complete:
                    on_complete()
                if was_listening and self.state != AIRuntimeState.IDLE:
                    schedule_once(lambda: self.enable_listening(), 0.2)
            except Exception as e:
                logger.error(f"[RUNTIME] Speak done callback error: {e}")
        
        try:
            self.audio.speak(text, phoneme_cb=_phoneme_wrapper, on_complete=_on_done)
        except Exception as e:
            logger.error(f"[RUNTIME] Audio speak error: {e}", exc_info=True)
            # If speak fails, still call on_complete and resume listening
            if on_complete:
                on_complete()
            if was_listening and self.state != AIRuntimeState.IDLE:
                schedule_once(lambda: self.enable_listening(), 0.2)
    
    # ========================================================================
    # INTRO
    # ========================================================================
    
    def _run_intro_sequence(self):
        """Run intro."""
        if not self.ai:
            return
        
        if hasattr(self.ai, 'run_intro'):
            try:
                from offline_ai_expression import OnboardingProfile
                profile = OnboardingProfile(
                    user_name=getattr(self.ai, 'user_name', 'User'),
                    ai_name=self.ai_name,
                    favorite_color=getattr(self.ai, 'favorite_color', 'blue'),
                    mode="extrovert" if self.mode == InteractionMode.EXTROVERT else "introvert",
                    wake_phrase="come on"
                )
                self.ai.run_intro(profile)
            except Exception as e:
                logger.error(f"[RUNTIME] Intro error: {e}")
                self._speak_text(f"Hello! I'm {self.ai_name}.")
        
        self._intro_complete = True
    
    # ========================================================================
    # CORPUS TRAINING
    # ========================================================================
    
    def start_corpus_training(self, corpus_path: str = "archive/Ubuntu-dialogue-corpus/",
                              num_dialogues: int = 500) -> bool:
        """Start corpus training."""
        if not HAS_CORPUS_TRAINER or not CorpusTrainer:
            logger.warning("[RUNTIME] Corpus trainer not available")
            return False

        if not self.corpus_trainer:
            self.corpus_trainer = CorpusTrainer(self.ai)

        logger.info(f"[RUNTIME] Starting training...")
        self._transition_to(AIRuntimeState.TRAINING)
        
        loaded = self.corpus_trainer.load_ubuntu_corpus(corpus_path, max_files=1)
        if loaded == 0:
            self._transition_to(AIRuntimeState.IDLE)
            return False
        
        def _train():
            stats = self.corpus_trainer.train_batch(num_dialogues=num_dialogues)
            logger.info(self.corpus_trainer.generate_training_report())
            schedule_once(lambda: self._transition_to(AIRuntimeState.IDLE), 0)
            schedule_once(lambda: self.ui.set_idle(), 0)
        
        import threading
        threading.Thread(target=_train, daemon=True).start()
        
        return True
    
    # ========================================================================
    # STATE MACHINE
    # ========================================================================
    
    def _transition_to(self, new_state: AIRuntimeState) -> bool:
        """State transition."""
        if not self._validate_transition(self.state, new_state):
            return False
        
        self.previous_state = self.state
        self.state = new_state
        self.last_state_change = time.time()
        
        logger.info(f"[RUNTIME] {self.previous_state.value} -> {self.state.value}")
        
        if new_state == AIRuntimeState.IDLE:
            self.ui.set_idle()
        elif new_state == AIRuntimeState.LISTENING:
            self.ui.set_listening()
        elif new_state == AIRuntimeState.THINKING:
            self.ui.set_thinking()
        elif new_state == AIRuntimeState.CONSOLIDATING:
            self.ui.set_consolidating()
        
        return True
    
    def _validate_transition(self, from_state: AIRuntimeState, to_state: AIRuntimeState) -> bool:
        """Validate transition."""
        if to_state in [AIRuntimeState.SHUTDOWN, AIRuntimeState.CONSOLIDATING, AIRuntimeState.TRAINING]:
            return True
        
        valid = {
            AIRuntimeState.BOOT: [AIRuntimeState.IDLE],
            AIRuntimeState.IDLE: [AIRuntimeState.LISTENING],
            AIRuntimeState.LISTENING: [AIRuntimeState.THINKING],
            AIRuntimeState.THINKING: [AIRuntimeState.SPEAKING],
            AIRuntimeState.SPEAKING: [AIRuntimeState.IDLE, AIRuntimeState.LISTENING],
            AIRuntimeState.CONSOLIDATING: [AIRuntimeState.IDLE],
            AIRuntimeState.TRAINING: [AIRuntimeState.IDLE],
            AIRuntimeState.SHUTDOWN: []
        }
        
        return to_state in valid.get(from_state, [])
    
    # ========================================================================
    # UTILITY
    # ========================================================================
    
    def _extract_ai_name(self, trigger: str) -> str:
        """Extract AI name."""
        for phrase in self.wake_phrases:
            if phrase.lower() in trigger.lower():
                parts = trigger.lower().split(phrase.lower())
                if len(parts) > 1 and parts[1].strip():
                    return parts[1].strip().capitalize()
        
        return getattr(self.ai, 'ai_name', "KO") if self.ai else "KO"
    
    def _get_farewell(self) -> str:
        """Get farewell."""
        if self.mode == InteractionMode.EXTROVERT:
            return f"I'll be here! Say 'hey {self.ai_name}'."
        return f"Goodbye! Say 'come on {self.ai_name}' to talk."
    
    def get_status(self) -> dict:
        """Get status."""
        return {
            "state": self.state.value,
            "mode": self.mode.value,
            "ai_name": self.ai_name,
            "audio_ready": self.audio.is_ready,
            "listening": self.listening_enabled,
            "speaking": self.speech_in_progress,
            "vision_active": self.vision.is_active() if self.vision else False,
        }


def create_runtime(ai, screen, interaction_mode: str = "introvert",
                   language: str = "en-US", enable_vision: bool = True,
                   enable_corpus: bool = False) -> OfflineAIRuntime:
    """Create and boot Runtime."""
    mode = InteractionMode.EXTROVERT if interaction_mode.lower() == "extrovert" else InteractionMode.INTROVERT
    ui_adapter = AIRuntimeUIAdapter(screen)
    runtime = OfflineAIRuntime(ai, ui_adapter, mode, language, enable_vision, enable_corpus)
    runtime.boot()
    ai.runtime = runtime
    return runtime
