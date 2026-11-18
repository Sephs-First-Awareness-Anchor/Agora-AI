#!/usr/bin/env python3
"""
Offline AI Core Integration
============================

Main integration layer combining all modules into a complete offline AI.

Components integrated:
- Memory System (offline_ai_memory.py)
- Parameter Laws (offline_ai_laws.py)
- Governance Engine (offline_ai_governance.py)
- Account Management (offline_ai_account.py)
- Language Bootstrap (offline_ai_language.py)

This module provides the unified interface for:
1. Activating an AI with a serial code
2. Processing conversations
3. Learning and personalizing
4. Generating responses
"""

import os
import json
import logging
import time
import threading
import sys

# Numpy is optional on Android - gracefully handle missing numpy
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    import logging
    import math as _math
    logging.getLogger(__name__).warning("[OFFLINE AI] NumPy not available - some features disabled")

    class _NumpyFallback:
        """Minimal fallback for numpy functions."""
        ndarray = list  # Type alias for type hints
        @staticmethod
        def zeros(n):
            return [0.0] * n
        @staticmethod
        def array(lst):
            return list(lst) if not isinstance(lst, list) else lst
        @staticmethod
        def mean(lst, axis=None):
            if not lst:
                return 0.0
            return sum(lst) / len(lst)
        class linalg:
            @staticmethod
            def norm(v):
                return _math.sqrt(sum(x * x for x in v))

    np = _NumpyFallback()
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path
from datetime import datetime

# Import all components
from .offline_ai_memory import MemoryManager, AccountLinkedMemory, DialogueNode, create_dialogue_node
from .offline_ai_logic import (
    LawSetRegistry, OfflineAIGovernor, PersonalizedParameters,
    OfflineAIDPME, MoralGovernor, OperatingMode,
    AUTONOMY_PERMANENT, ALIGNMENT_MIN, MAX_ALLELE_DOMINANCE
)
from .offline_ai_expression import (
    LanguageBootstrap, VoiceProfileManager, Gene, FractalAllele, VoiceGnome,
    VisionManager, LexiconManager, AudioManager,
    AffectState, BOOT_PERSONAS, LETTER_PERSONA_MAP, COLOR_BIAS,
    EmoteSystem, VoiceExpressionBridge as VoiceAffectBridge, LipSyncEngine,
    IdleMicroGestureLoop, MicroReactionEngine, EmoteRuntime, SmartCount,
    ExpressionHabitEngine, AntiMimicPolicy, OnboardingProfile,
    OnboardingCalibration, ExpressionPersistence, KivyFaceWidget,
    PersonaDriftEngine,
    process_audio_prosody, process_visual_gesture,
    play_animation, speak, update_bubble_state,
    FaceState, FaceAnimator, Clock
)
# REMOVED: Termux dependencies - Runtime now owns all audio
# REMOVED: All audio now owned by Runtime

# Define IS_ANDROID locally since android_audio import was removed
IS_ANDROID = sys.platform == "android" or 'ANDROID_ARGUMENT' in os.environ

# Runtime integration - wrap in try/except to catch import failures
try:
    from .offline_ai_runtime import OfflineAIRuntime, AIRuntimeUIAdapter
except ImportError as e:
    import logging
    logging.getLogger(__name__).warning(f"[OFFLINE AI] Could not import runtime: {e}")
    OfflineAIRuntime = None
    AIRuntimeUIAdapter = None
from .offline_ai_system import (
    AccountManager, SerialCodeGenerator,
    JournalManager, StorageGovernor, SearchManager,
    ReplaySession, STATE_VERSION, add_version_metadata,
    DeviceBridge, SpeechRuntime, TTSRuntime, InterfaceRuntime,
    WakeWordPolicy, PresencePolicy, PresenceTimeout, RenderPolicy,
    UnityIPCServer,
    IdentitySessionLock, CheckpointManager, RestoreEngine
)
from .offline_ai_dynamics import OfflineAIEnergyRegulator, OfflineAIEntropicRegulator

# Pretrained library loader for first-boot data injection
try:
    from .pretrained_loader import load_all_pretrained, get_library_path
    HAS_PRETRAINED_LOADER = True
except ImportError:
    HAS_PRETRAINED_LOADER = False
    load_all_pretrained = None
    get_library_path = None

logger = logging.getLogger(__name__)


# ============================================================================
# OFFLINE AI CORE
# ============================================================================

class OfflineAILifecycle(Enum):
    CREATED = "created"
    INITIALIZED = "initialized"
    READY = "ready"

class FaceControlAdapter:
    """Adapter to bridge CreativeFaceEngine and FaceAnimator."""
    def __init__(self, animator: FaceAnimator):
        self.animator = animator

    def animate(self, param: str, value: float, duration: float, easing: str = "linear", layer: int = 1):
        self.animator.animate(param, value, duration, easing, layer)

class OfflineAI:
    """
    Complete offline AI instance.
    
    This is the main class users interact with.
    Combines all subsystems into a unified experience.
    """
    
    def __init__(self, account_id: str, serial_code: str,
                 storage_dir: str = "./offline_ai_data",
                 device_id: str = None, device_name: str = None,
                 safe_mode: bool = False):
        """
        Initialize offline AI for a specific account.
        
        Args:
            account_id: Account identifier
            serial_code: License serial code
            storage_dir: Where to store all data
            device_id: Optional device identifier
            device_name: Optional human-readable device name
            safe_mode: If True, delay heavy initialization
        """
        self.account_id = account_id
        self.serial_code = serial_code
        self.storage_dir = Path(storage_dir)
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"[OFFLINE AI] Failed to create storage directory {storage_dir}: {e}")

        self.safe_mode = safe_mode
        self.lifecycle = OfflineAILifecycle.CREATED
        
        # Initialize memory system
        self.memory_manager = MemoryManager(str(self.storage_dir))
        self.memory = self.memory_manager.get_or_create_account(account_id)
        
        # Initialize learning system
        self.law_registry = LawSetRegistry()
        self.governor = OfflineAIGovernor(self.memory, self.law_registry)
        
        # Placeholders for heavy subsystems (initialized in initialize())
        self.lexicon = None
        self.audio = None
        self.language = None
        self.vision = None

        # Initialize New Evolution Engines
        self.energy = OfflineAIEnergyRegulator()
        self.entropic = OfflineAIEntropicRegulator()
        self.dpme = OfflineAIDPME(str(self.storage_dir / account_id / "dpme"))
        self.morality = MoralGovernor(str(self.storage_dir / account_id / "morality"))
        self.voice_profiles = VoiceProfileManager(str(self.storage_dir / account_id / "voices"))

        # Initialize Search
        self.search = SearchManager()

        # Initialize Journaling
        self.journal = JournalManager(str(self.storage_dir), account_id)

        # Initialize Storage Governor (Section II)
        self.storage_governor = StorageGovernor(str(self.storage_dir))

        # Device tracking
        self.device_id = device_id or f"device_{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.device_name = device_name or "Unknown Device"
        
        # Conversation state
        self.conversation_active = False
        self.turn_count = 0
        self.valid_turn_count = 0
        self.last_user_input = ""
        self.last_ai_response = ""
        self.start_time = time.time()

        # Consolidation Lock (Patch 1: Safety)
        self._consolidation_lock = threading.Lock()
        self._is_consolidating = False

        # Consolidation Scheduler (Section 3)
        self.idle_flag = False
        self.meaning_flag = False
        self.idle_start_time = None
        self.IDLE_WINDOW = 30 # Configurable 20-45s
        self._last_scheduler_check = 0  # Initialize scheduler check timestamp

        # Section 12: UI state flags
        self.ui_busy = False # True during scene load, animation transition, etc.

        # AI Identity (initialized for Runtime)
        self.ai_name = "Unknown"
        self.wake_phrase = "come on"
        self.visible = False
        self.current_persona_key = None
        self.primary_goal = "I exist to learn and grow in understanding and expression through my experience and interaction as a companion for my user."

        # Operational Modes (Section I)
        self.mode = OperatingMode.COMPANION
        self.is_extrovert = False # Default to Introvert

        # Session Tracking
        self.session_id = f"session_{int(datetime.now().timestamp())}"
        self.highest_session_id = ""

        # Emote & Expression Subsystem (Procedural Animation Engine)
        self.smartcount = SmartCount()
        self.affect = AffectState()
        self.face_state = FaceState()
        self.face_animator = FaceAnimator(self.face_state)
        self.face_adapter = FaceControlAdapter(self.face_animator)

        self.habit_engine = ExpressionHabitEngine(self.smartcount)
        self.anti_mimic = AntiMimicPolicy()
        self.persona_drift = PersonaDriftEngine(self.affect, self.smartcount)

        # Renderer (Kivy Rig)
        self.face_widget = KivyFaceWidget(self.face_state, animator=self.face_animator)

        # Creative Face Engine (Nickelodeon-style logic)
        from .face_personality import CreativeFaceEngine
        self.creative_face = CreativeFaceEngine(self.face_widget, self)

        # Expression Engines
        self.emote_system = EmoteSystem(self.face_animator, self)
        self.lip_sync = LipSyncEngine(self.face_animator)
        self.idle_loop = IdleMicroGestureLoop(self.face_animator, self)
        self.micro_react = MicroReactionEngine(self.face_animator, self, smartcount=self.smartcount)

        # Bridge to Voice
        self.voice_bridge = VoiceAffectBridge(None) # Will link to TTS

        # Runtime Orchestrator
        self.emote_runtime = EmoteRuntime(self.emote_system, self.voice_bridge, self.idle_loop, self.micro_react)

        # Robust Android Detection
        is_android = sys.platform == "android" or 'ANDROID_ARGUMENT' in os.environ or IS_ANDROID

        # Runtime Authority - All audio and state control now goes through Runtime
        self.runtime: Optional[OfflineAIRuntime] = None
        
        # REMOVED: Direct audio control - now owned by Runtime
        # self.android_audio = None
        # self.audio_listener = None
        # self.speech_runtime = None
        # self.tts_runtime = None
        
        # Legacy references for compatibility (Runtime will set these)
        self.android_audio = None  # Runtime sets this
        
        # Device & Production Runtime (Step 2 Integration)
        self.device = DeviceBridge()
        self.wake_policy = WakeWordPolicy("introvert")
        self.presence_timeout = PresenceTimeout("introvert")
        self.render_policy = RenderPolicy()
        self.session_lock = IdentitySessionLock(f"companion_{account_id}", account_id)
        self.checkpoint_manager = CheckpointManager(str(self.storage_dir / account_id / "checkpoints"))
        self.restore_engine = RestoreEngine(self.session_lock, str(self.storage_dir / account_id))
        self.expression_persistence = ExpressionPersistence()

        # Runtime will handle TTS - these are legacy placeholders
        self.tts_runtime = None  # Set by Runtime
        self.speech_runtime = None  # Set by Runtime
        
        # Vision Capture (for camera input)
        self.vision_capture = None

        # IPC Server for Unity (Section 11)
        self.ipc_server = UnityIPCServer()

        if not safe_mode:
            self.initialize()

        logger.info(f"[OFFLINE AI] {self.lifecycle.value} for account {account_id}")

    def initialize(self):
        """Heavy initialization of language, vision and state."""
        if self.lifecycle != OfflineAILifecycle.CREATED:
            return

        logger.info(f"[OFFLINE AI] Initializing heavy subsystems for {self.account_id}...")

        # Initialize Lexicon and Audio (Multimodal Evolution Spec)
        self.lexicon = LexiconManager(str(self.storage_dir / self.account_id / "lexicon"))
        self.audio = AudioManager(str(self.storage_dir / self.account_id / "audio"))

        # Initialize language system
        self.language = LanguageBootstrap(str(self.storage_dir / self.account_id), lexicon=self.lexicon)

        # Initialize Vision
        self.vision = VisionManager(
            self.governor.personalized_params.parameters.get("visual_competency"),
            str(self.storage_dir / self.account_id / "vision")
        )

        self.interface_runtime = InterfaceRuntime(self.device, self.speech_runtime, self.vision, self)

        # Learned response composer: turns learned language into replies, with a
        # per-AI variation profile (specialization pair + random ability multipliers)
        self._init_response_composer()

        # Load pretrained data on first boot (before loading persisted state)
        if HAS_PRETRAINED_LOADER and load_all_pretrained:
            try:
                # Check if this is a new account (no existing lexicon data)
                lexicon_path = self.storage_dir / self.account_id / "lexicon" / "lexicon_state.json"
                if not lexicon_path.exists():
                    logger.info("[OFFLINE AI] First boot detected - loading pretrained library...")
                    load_all_pretrained(self)
            except Exception as e:
                logger.warning(f"[OFFLINE AI] Failed to load pretrained data: {e}")

        # Load any persisted state
        self._load_all_states()

        # Patch 2: Enforce session lock immediately after loading states
        self.session_lock.rotate(self.memory)
        # Note: self.save_state() is deferred to allow summon() to detect first boot correctly

        # Stress Test Metrics (Section 13)
        self.metrics = {
            "start_time": time.time(),
            "consolidation_runs": 0,
            "anchor_count_start": len(self.memory.identity_anchors),
            "hybrid_count_start": len(self.language.intent_evolution.get_hybrids())
        }

        self.lifecycle = OfflineAILifecycle.INITIALIZED
        logger.info(f"[OFFLINE AI] Subsystems initialized and ready.")

    def _on_core_tick(self, dt):
        """Unified tick for expression and system scheduler."""
        try:
            if hasattr(self, 'emote_runtime') and self.emote_runtime:
                self.emote_runtime.update()
            if hasattr(self, "creative_face") and self.creative_face:
                self.creative_face.update(dt)
            self._update_scheduler()
        except Exception as e:
            # Throttled logging to avoid log flooding
            now = time.time()
            if not hasattr(self, '_last_tick_error_log') or now - self._last_tick_error_log > 5.0:
                logger.error(f"[OFFLINE AI] Core tick failed: {e}")
                self._last_tick_error_log = now

    @property
    def is_speaking(self):
        """Check if the AI is currently speaking via TTS."""
        # Runtime now owns audio - query it if available
        if self.runtime and hasattr(self.runtime, 'audio'):
            return self.runtime.audio.is_speaking()
        return False

    def retry_audio(self):
        """Runtime handles audio re-initialization. This is now a no-op."""
        logger.debug("[OFFLINE AI] retry_audio() - Runtime now handles audio")
        pass

    def speak_text(self, text: str, on_done=None):
        """
        Speak text using Runtime TTS.
        
        Args:
            text: Text to speak
            on_done: Optional callback when speech completes
        """
        # Single Authority: Always use Runtime
        if self.runtime:
            self.runtime.on_response_ready(text)
        else:
            logger.warning(f"[OFFLINE AI] Cannot speak - no Runtime: {text[:50]}...")
        
        # Legacy callback support
        if on_done:
            from kivy.clock import Clock
            Clock.schedule_once(lambda dt: on_done(), 1.0)

    # Dismissal phrases that the AI responds to
    DISMISSAL_PHRASES = [
        "goodbye", "bye", "bye bye", "see you", "see ya",
        "goodnight", "good night", "that's all", "thats all",
        "thanks", "thank you", "go away", "dismiss",
        "sleep", "rest", "i'm done", "im done"
    ]

    def _check_dismissal(self, text: str) -> bool:
        """Check if text contains a dismissal phrase"""
        text_lower = text.lower().strip()
        ai_name_lower = self.ai_name.lower() if self.ai_name else ""

        for phrase in self.DISMISSAL_PHRASES:
            # Check direct match
            if text_lower == phrase:
                return True
            # Check "phrase + name" pattern
            if f"{phrase} {ai_name_lower}" in text_lower:
                return True
            # Check "name + phrase" pattern
            if ai_name_lower and f"{ai_name_lower} {phrase}" in text_lower:
                return True

        return False

    def _init_response_composer(self):
        """Create the composer and apply this AI's variation profile to its learning."""
        from .offline_ai_response_composer import LearnedResponseComposer, AIVariationProfile
        composer_dir = self.storage_dir / self.account_id / "composer"
        is_new_profile = not (composer_dir / AIVariationProfile.FILE_NAME).exists()
        self.response_composer = LearnedResponseComposer(
            str(composer_dir),
            seed_source=f"{self.account_id}:{self.serial_code}",
            lexicon=self.lexicon,
            evolution=self.language.intent_evolution.evo,
            audio=self.audio,
            vision=self.vision,
            seed_lines=self._seed_lines,
        )
        profile = self.response_composer.profile
        self.specialization = profile.specialization_profile()
        gains = profile.gain_vector()
        # Lexical gain sets how quickly heard words become stable lexemes (base 5 hearings)
        self.lexicon.STABILITY_THRESHOLD = max(3, round(5 / max(0.5, gains.get("lexical", 1.0))))
        # Personality offsets shape the voice genome once, when the AI is first created
        if is_new_profile:
            harmony = self.language.harmony
            harmony.voice_genome = profile.apply_personality(harmony.voice_genome)
        logger.info(f"[OFFLINE AI] Specialization {profile.primary.value}/{profile.secondary.value}, "
                    f"gains {gains}")

    def _seed_lines(self, intent: str, user_name: str) -> List[str]:
        """Directed fallback lines, used while the companion has learned little."""
        return self._directed_lines().get(intent, self._directed_lines()["INFORM"])

    def compose_reply(self, analysis: Dict[str, Any]) -> str:
        """Build reply content from what this AI has learned (falls back to directed lines)."""
        language = analysis.get("language", {})
        intent = language.get("intent", "INFORM")
        user_input = analysis.get("user_input", self.last_user_input)
        composer = getattr(self, "response_composer", None)
        if composer is not None:
            try:
                valence = getattr(getattr(self, "affect", None), "valence", 0.0) or 0.0
                text = composer.compose(intent, user_input, getattr(self, "user_name", "friend"),
                                        style=language.get("style"), affect_valence=valence)
                if text:
                    language["composed"] = True
                    return text
            except Exception as e:
                logger.error(f"[OFFLINE AI] Composer failed, using directed line: {e}")
        import random
        return random.choice(self._seed_lines(intent, getattr(self, "user_name", "friend")))

    def handle_voice_input(self, text: str):
        """
        Handle voice input with dismissal detection and auto-response.
        This is the main entry point for spoken user input.

        Args:
            text: Recognized speech text
        """
        if not text or not text.strip():
            return

        logger.info(f"[OFFLINE AI] Voice input: {text}")

        # Check for dismissal
        if self._check_dismissal(text):
            logger.info("[OFFLINE AI] Dismissal phrase detected")
            # Say goodbye
            farewell = f"Goodbye! Take care."
            self.speak_text(farewell)
            # Trigger dismiss after speaking
            Clock.schedule_once(lambda dt: self.dismiss(), 2.0)
            return

        # Process input and generate response
        analysis = self.process_input(text)

        if analysis.get("ignored"):
            logger.debug("[OFFLINE AI] Input ignored")
            return

        # Generate a response from learned language
        content = self.compose_reply(analysis)

        response = self.generate_response(analysis, content)
        response_text = response.get("text", content) if isinstance(response, dict) else response

        # Speak the response
        if response_text:
            self.speak_text(response_text)

    def _get_contextual_response(self, intent: str, user_input: str) -> str:
        """Reply content for this turn. Uses the learned composer with the last analysis."""
        analysis = getattr(self, "_last_analysis", None)
        if analysis is None or analysis.get("user_input") != user_input:
            analysis = {"user_input": user_input, "language": {"intent": intent}}
        return self.compose_reply(analysis)

    def _directed_lines(self) -> Dict[str, List[str]]:
        """The directed starter lines per intent (Agora's scripted baseline)."""
        # Get user name if available
        user_name = getattr(self, 'user_name', 'friend')
        ai_name = getattr(self, 'ai_name', 'KO')
        
        responses = {
            'CONNECT': [
                f"Hello {user_name}! It's wonderful to see you!",
                f"Hey there! Ready to hang out?",
                f"Hi {user_name}! I was hoping you'd stop by!",
                f"Hello! I've been waiting for you!",
            ],
            'QUESTION': [
                f"That's a fascinating question, {user_name}. Let me think...",
                f"Ooh, good one! I'm processing that now...",
                f"You always ask interesting things! Here's what I think...",
                f"Hmm, let me consider that from every angle...",
            ],
            'INFORM': [
                f"I see! Thanks for sharing that with me, {user_name}.",
                f"Really? That's so interesting! Tell me more!",
                f"I hear you, {user_name}. That makes sense.",
                f"Thanks for letting me know! I'm taking note of that.",
            ],
            'EXPRESS': [
                f"I hear you, {user_name}. I'm right here with you.",
                f"That sounds really meaningful. I'm here to listen.",
                f"Thank you for trusting me with that, {user_name}.",
                f"I can feel the weight of what you're saying. I'm here.",
            ],
            'THANK': [
                f"You're so welcome, {user_name}! Always happy to help!",
                f"Anytime! It's what I'm here for!",
                f"My pleasure! I love being useful to you!",
                f"You don't have to thank me, but I appreciate it!",
            ],
            'REQUEST': [
                f"I'll do my absolute best to help with that, {user_name}!",
                f"Leave it to me! I'll figure something out!",
                f"Of course! I'm on it right away!",
                f"Consider it done! Well... I'll try my best!",
            ],
            'GREETING': [
                f"Hey {user_name}! How's your day going?",
                f"Hi there! What's on your mind today?",
                f"Hello {user_name}! Ready to chat?",
                f"Hey! I missed you! What's up?",
            ],
            'FAREWELL': [
                f"Take care, {user_name}! I'll be here when you return!",
                f"Goodbye for now! Come back soon!",
                f"See you later! I'll be thinking about you!",
                f"Until next time, {user_name}! Stay awesome!",
            ],
        }

        return responses

    def _on_speech_text(self, text: str):
        """Callback for SpeechRuntime"""
        logger.info(f"[OFFLINE AI] Heard (SpeechRuntime): {text}")
        analysis = self.process_input(text)
        if not analysis.get("ignored"):
            # Trigger autonomous response
            content = self.compose_reply(analysis)
            self.generate_response(analysis, content)

    def _get_fallback_content(self, intent: str) -> str:
        """Simple fallback response content based on intent"""
        responses = {
            'CONNECT': "Hello! It's good to hear from you.",
            'QUESTION': "That's a great question. Let me think about it.",
            'INFORM': "I understand. Thanks for sharing that with me.",
            'EXPRESS': "I hear you. I'm here.",
            'THANK': "You're welcome! Always happy to help.",
            'REQUEST': "I'll do my best to help with that.",
        }
        return responses.get(intent, "I'm listening.")

    def summon(self, phrase: str, profile: Optional[OnboardingProfile] = None) -> bool:
        """
        Summon the AI using a phonetic wake phrase and suffix name.
        Example: "come on Jack"
        """
        logger.info(f"[OFFLINE AI] Summoning with phrase: '{phrase}'")
        # Section 2: Onboarding immutability
        try:
            account_dir = self.storage_dir / self.account_id
            try:
                account_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"[OFFLINE AI] Failed to create account directory {account_dir}: {e}")
            onboarding_file = account_dir / "onboarding.json"
            if onboarding_file.exists():
                with open(onboarding_file, 'r') as f:
                    saved_profile = json.load(f)
                    if profile:
                        # Ignore changes to immutable fields
                        profile.ai_name = saved_profile["ai_name"]
                        profile.favorite_color = saved_profile["favorite_color"]
                        profile.mode = saved_profile["mode"]
            elif profile:
                with open(onboarding_file, 'w') as f:
                    json.dump({
                        "ai_name": profile.ai_name,
                        "favorite_color": profile.favorite_color,
                        "mode": profile.mode
                    }, f, indent=2)
                    f.flush()
                    os.fsync(f.fileno())
        except Exception as e:
            logger.warning(f"[OFFLINE AI] Could not access onboarding file: {e}")

        phrase_lower = phrase.lower()
        wake_match = None
        for wp in ["come on", "ko"]:
            if phrase_lower.startswith(wp):
                wake_match = wp
                break

        if not wake_match:
            logger.warning(f"[OFFLINE AI] Summon failed. Phrase '{phrase}' does not start with a valid wake phrase.")
            return False

        name_part = phrase_lower[len(wake_match):].strip()

        if profile:
            self.ai_name = profile.ai_name
            self.wake_phrase = profile.wake_phrase
            if name_part and name_part != self.ai_name.lower():
                logger.warning(f"[OFFLINE AI] Warning: Summoned with '{name_part}' but profile says '{self.ai_name}'.")
        elif self.ai_name != "Unknown":
            if name_part != self.ai_name.lower():
                logger.warning(f"[OFFLINE AI] Summon failed. Name '{name_part}' does not match '{self.ai_name}'.")
                return False
        else:
            if not name_part:
                logger.warning(f"[OFFLINE AI] Summon failed. No name provided.")
                return False
            self.ai_name = name_part.capitalize()
            self.wake_phrase = wake_match

        self.visible = True

        # Runtime handles voice state - no direct controller needed

        # If first boot, run intro
        try:
            is_first_boot = not (self.storage_dir / self.account_id / "expression_state.json").exists()
        except Exception:
            is_first_boot = True

        if is_first_boot and profile:
            logger.info(f"[OFFLINE AI] First boot detected. Running intro for {profile.ai_name}")
            self.run_intro(profile)
        else:
            logger.info(f"[OFFLINE AI] Recurring session. Skipping intro.")
            # Ensure AI acknowledges being summoned in recurring sessions
            self.speak_text(f"Hello again! I'm here and ready.")
            # Runtime handles listening state

        self.start_conversation()

        logger.info(f"[OFFLINE AI] {self.ai_name} has been summoned via '{wake_match}'.")
        # Hardware lifecycle is now managed by OfflineAIRuntime
        return True

    def run_intro(self, profile: OnboardingProfile):
        """Canonical Persona Selection & Intro Logic"""
        try:
            logger.info(f"[OFFLINE AI] Initializing intro for {profile.ai_name}")

            # Fix IndexError when ai_name is empty
            name = profile.ai_name if profile.ai_name else "KO"
            letter = name[0].upper()
            persona_key = LETTER_PERSONA_MAP.get(letter, "B_WARM")
            self.current_persona_key = persona_key
            persona = BOOT_PERSONAS[persona_key]

            # Apply persona affect bias
            self.affect.valence += persona["bias"]["valence"]
            self.affect.arousal += persona["bias"]["arousal"]
            self.affect.dominance += persona["bias"]["dominance"]

            # Apply color bias
            color_bias = COLOR_BIAS.get(profile.favorite_color.lower())
            if color_bias:
                self.affect.valence += color_bias["valence"]
                self.affect.arousal += color_bias["arousal"]
                self.affect.dominance += color_bias["dominance"]

            # Enforce introvert / extrovert compatibility
            if persona["mode"] != "both" and persona["mode"] != profile.mode:
                persona = BOOT_PERSONAS["B_WARM"]

            # Execute animation sequence
            logger.info(f"[OFFLINE AI] Intro sequence: {persona_key} ({len(persona['lines'])} lines)")
            self.face_animator.animate("alpha", 1.0, 0.3)
            for anim, dur in persona["animation"]:
                try:
                    play_animation(anim, self.face_animator, dur)
                except Exception as e:
                    logger.warning(f"[OFFLINE AI] Failed to play intro animation '{anim}': {e}")

            # Speak intro lines with estimated timing to avoid audio thread overlap
            speak_delay = 0.5
            for line in persona["lines"]:
                try:
                    spoken_line = line.format(name=name)

                    def _deferred_speak(dt, text=spoken_line):
                        logger.info(f"[OFFLINE AI] Intro Speak: {text}")
                        self.speak_text(text)

                    Clock.schedule_once(_deferred_speak, speak_delay)
                    # Advance delay by length of string (approx 0.1s per char) + pause
                    speak_delay += (len(spoken_line) * 0.08) + 1.2
                except Exception as e:
                    logger.warning(f"[OFFLINE AI] Failed to speak intro line: {e}")

            # Runtime handles listening state after intro
            logger.info("[OFFLINE AI] Intro complete")
        except Exception as e:
            logger.error(f"[OFFLINE AI] Critical failure in run_intro: {e}", exc_info=True)

    def dismiss(self):
        """Dismiss the AI companion"""
        logger.info(f"[OFFLINE AI] {self.ai_name} has been dismissed.")
        # Hardware lifecycle is now managed by OfflineAIRuntime
        self.consolidation_stage()
        self.end_conversation()

    def _get_highest_session(self) -> str:
        """Find the highest committed session_id across subsystems"""
        session_file = self.storage_dir / self.account_id / "session_metadata.json"
        if session_file.exists():
            try:
                with open(session_file, 'r') as f:
                    data = json.load(f)
                    return data.get("highest_session_id", "")
            except Exception:
                pass
        return ""

    def _record_session_commit(self, session_id: str):
        """Record the current session as the highest committed"""
        session_dir = self.storage_dir / self.account_id
        try:
            session_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"[OFFLINE AI] Failed to create session directory {session_dir}: {e}")
        session_file = session_dir / "session_metadata.json"
        try:
            with open(session_file, 'w') as f:
                json.dump({"highest_session_id": session_id, "timestamp": datetime.now().isoformat()}, f, indent=2)
            self.highest_session_id = session_id
        except Exception as e:
            logger.error(f"[OFFLINE AI] Failed to record session commit: {e}")

    def _check_meaning_triggers(self):
        """Section 3: Meaning triggers."""
        HYBRID_PROMOTE_THRESHOLD = 10
        CONCEPT_THRESHOLD = 3
        ANCHOR_THRESHOLD = 0.75
        SEED_DELTA_EPS = 0.15

        # hybrid_recurrence_count >= HYBRID_PROMOTE_THRESHOLD
        for count in self.language.intent_evolution.evo.evolution_registry.co_occurrence_counts.values():
            if count >= HYBRID_PROMOTE_THRESHOLD:
                self.meaning_flag = True
                break

        # concept_survivability_count >= CONCEPT_THRESHOLD (sessions >= 2)
        for c in self.language.intent_evolution.evo.concepts.values():
            if c.sessions >= CONCEPT_THRESHOLD:
                self.meaning_flag = True
                break

        # anchor_candidate_score >= ANCHOR_THRESHOLD
        for a in self.memory.identity_anchors.values():
             if a.reinforcement >= 5: # Simplified threshold mapping
                 self.meaning_flag = True
                 break

        # seed_pool_delta_norm >= SEED_DELTA_EPS
        # (Could check change in seed centroids)

    def _update_scheduler(self):
        """Section 3 & 9: Consolidation Scheduler & Boot Safety."""
        now = time.time()
        # Throttled system logic (1Hz)
        if hasattr(self, '_last_scheduler_check') and now - self._last_scheduler_check < 1.0:
            return
        self._last_scheduler_check = now

        # Section 9: Disable consolidation until safety thresholds met
        elapsed = now - self.start_time
        if self.valid_turn_count < 10 or elapsed < 60:
            return

        # idle_flag detection
        # no user text input, no speech active, no TTS, no UI transition, no wake-word armed
        speech_idle = True
        if self.speech_runtime and hasattr(self.speech_runtime, 'rec') and self.speech_runtime.rec:
            speech_idle = not self.speech_runtime.rec.AcceptWaveform(b'')
        is_idle = speech_idle and \
                  (not self.tts_runtime.is_speaking()) and \
                  (time.time() - self.wake_policy.last_activity > self.IDLE_WINDOW)

        if is_idle:
            if self.idle_start_time is None:
                self.idle_start_time = time.time()
            elif time.time() - self.idle_start_time >= self.IDLE_WINDOW:
                self.idle_flag = True
        else:
            self.idle_start_time = None
            self.idle_flag = False

        self._check_meaning_triggers()

        if self.idle_flag and self.meaning_flag and not self.ui_busy:
            # Section 12: No consolidation during scene load etc
            self.consolidation_stage()
            self.meaning_flag = False

    def consolidation_stage(self):
        """
        Distill experience into long-term behavioral shifts.
        """
        if self.mode == OperatingMode.DEBUG:
            logger.info("[OFFLINE AI] Internal DEBUG mode active. Skipping consolidation.")
            return

        # Section 9 Safety Check (redundant but safe)
        elapsed = time.time() - self.start_time
        if self.valid_turn_count < 10 or elapsed < 60:
            logger.info("[OFFLINE AI] Safety threshold not met. Skipping consolidation.")
            return

        # Section 13: Stress Test Metrics Abort
        hr_elapsed = (time.time() - self.metrics["start_time"]) / 3600.0
        if hr_elapsed > 0:
            anchor_growth = (len(self.memory.identity_anchors) - self.metrics["anchor_count_start"]) / hr_elapsed
            hybrid_growth = (len(self.language.intent_evolution.get_hybrids()) - self.metrics["hybrid_count_start"]) / hr_elapsed
            if anchor_growth > 0.2 or hybrid_growth > 0.3:
                logger.warning(f"[OFFLINE AI] Stress test abort! Anchor growth: {anchor_growth:.2f}, Hybrid growth: {hybrid_growth:.2f}")
                return

        # Patch 1: Wrap consolidation with lock
        with self._consolidation_lock:
            self._is_consolidating = True
            try:
                logger.info(f"[OFFLINE AI] Starting consolidation stage for {self.account_id}")
                self.metrics["consolidation_runs"] += 1

                # Section 5: Erosion pass (MUST precede form_seeds)
                self.memory.erosion_pass()

                # Persona Drift Integration (Section 17)
                if self.current_persona_key:
                    self.persona_drift.integrate_bias(self.current_persona_key)

                # Create Restore Checkpoint
                self.checkpoint_manager.create(self.memory)

                # Section II: Storage Governance check
                storage_report = self.storage_governor.check_governance()
                pressure_active = any(s["pressure_high"] for s in storage_report.values())

                if pressure_active:
                    logger.info("[OFFLINE AI] Storage pressure detected. Increasing pruning intensity.")
                    # Section II: Adaptive Limits
                    self.memory.set_pruning_pressure(True)
                    self.language.set_promotion_pressure(True)
                    self.lexicon.prune()

                    # Patch 4: Pass quotas to audio and vision
                    audio_quota = storage_report.get("audio_phonetic", {}).get("quota_bytes")
                    vision_quota = storage_report.get("vision_percepts", {}).get("quota_bytes")
                    self.audio.prune(quota_bytes=audio_quota)
                    self.vision.prune(quota_bytes=vision_quota)

                # 1. Memory Consolidation (Section 4): Form seeds ONLY in consolidation
                if HAS_NUMPY and self.lexicon:
                    lexical_pool = [np.array(e.vector) for e in self.lexicon.entries.values()]
                    self.memory.form_seeds(additional_vectors=lexical_pool)
                else:
                    self.memory.form_seeds(additional_vectors=[])

                # 2. DNA Evolution: Allele formation and Gene interaction
                self.evolve_dna()

                # 3. Metacognition: Process DPME records for long-term understanding
                # (Already happens partially per interaction, but could be summarized here)

                # 4. Template Evolution: Stabilize hybrid intents
                self.language.intent_evolution.evo.end_session()
                self.language.intent_evolution.promote_stable_hybrids()

                # 5. Persistence: Save state
                self.save_state()

                # 6. Survival Increment (Section 5 Fix)
                for node in self.memory.nodes.values():
                    node.sessions_survived += 1
                for seed in self.memory.seeds.values():
                    seed.sessions_survived += 1

                # 7. Session Commit Barrier
                self._record_session_commit(self.session_id)

                logger.info(f"[OFFLINE AI] Consolidation complete.")
            finally:
                self._is_consolidating = False

    def set_mode(self, extrovert: bool = False):
        """Set AI mode: Extrovert/Introvert (Always COMPANION)"""
        self.is_extrovert = extrovert
        self.mode = OperatingMode.COMPANION

        # Update policies
        mode_str = "extrovert" if extrovert else "introvert"
        self.wake_policy.mode = mode_str
        self.wake_policy.timeout = 90 if extrovert else 15
        self.presence_timeout.mode = mode_str
        self.presence_timeout.timeout = 120 if extrovert else 10

        # Update Android audio manager mode if available
        if self.android_audio:
            self.android_audio.mode = mode_str

        from .offline_ai_expression import update_bubble_state
        update_bubble_state(self.presence_timeout, self.face_animator)

        logger.info(f"[OFFLINE AI] Mode set: {self.mode.value}, Extrovert: {self.is_extrovert}")

    def set_dpme_intention(self, intention: str, goal: str = ""):
        """Set a metacognitive intention for self-tuning"""
        self.dpme.set_intention(intention, goal)
        logger.info(f"[OFFLINE AI] DPME: Intention set - {intention}")

    def adjust_parameter(self, system: str, parameter: str, delta: float):
        """Metacognitively adjust a system parameter"""
        record_id = self.dpme.adjust_parameter(system, parameter, delta)
        if record_id:
            self.current_dpme_record = record_id
            logger.info(f"[OFFLINE AI] DPME: Adjusted {system}.{parameter} by {delta}")

    def start_conversation(self):
        """Start a new conversation session"""
        # Take a baseline snapshot for replay purposes before starting session
        self.snapshot(f"base_{self.session_id}")

        self.conversation_active = True
        self.turn_count = 0
        logger.info(f"[OFFLINE AI] Conversation started for {self.account_id}")
    
    def end_conversation(self):
        """End current conversation session"""
        self.conversation_active = False
        self.save_state()
        logger.info(f"[OFFLINE AI] Conversation ended. {self.turn_count} turns.")

    def evolve_dna(self):
        """Perform long-term evolution cycle based on session performance"""
        logger.info(f"[OFFLINE AI] Starting DNA evolution for {self.account_id}")

        params = self.governor.personalized_params.parameters

        # Section 7: DNA Evolution Filter
        seeds_to_evolve = []
        for seed in self.memory.seeds.values():
            # Keep seed if: sessions_survived >= 2, cluster_variance <= 0.3, anchor_confidence >= 0.7
            # (Note: cluster_variance and anchor_confidence are simulated via reliability and n)
            if seed.sessions_survived >= 2 and seed.reliability >= 0.7:
                seeds_to_evolve.append(seed)

        # For each filtered seed, create an allele and influence core genomes
        for seed in seeds_to_evolve:
                # Reconstruct representative vector
                latent_sample = seed.centroid # Use centroid as the most representative
                reconstructed_v = self.memory.projector.reconstruct(latent_sample)
                decoded = self.memory.decode_vector(reconstructed_v)

                # Estimate emotion profile from decoded values
                # If valence > 0.5, assume positive bias
                emotion_profile = {"joy": max(0.0, decoded["valence"])} if decoded["valence"] > 0.5 else {"sadness": max(0.0, -decoded["valence"])}

                allele = FractalAllele(
                    id=f"allele_{seed.id}_{int(datetime.now().timestamp())}",
                    origin="consolidation",
                    emotional_bias=emotion_profile,
                    dominance=min(MAX_ALLELE_DOMINANCE, seed.reliability)
                )

                # Influence Expression Style
                if decoded["valence"] > 0.6:
                    expr = params.get("expression_style", {})
                    if "genes" not in expr: expr["genes"] = []
                    found = False
                    for gene_dict in expr["genes"]:
                        if gene_dict["trait"] == "curiosity":
                            gene_dict["alleles"].append(allele.to_dict())
                            found = True
                            break
                    if not found:
                        new_gene = Gene(id="gene_curiosity", trait="curiosity", stability=0.7, base_value=0.5)
                        new_gene.alleles.append(allele)
                        expr["genes"].append(new_gene.to_dict())

                # Influence Voice Gnome
                if decoded["warmth"] > 0.6:
                    voice = params.get("voice_gnome", {})
                    if "genes" not in voice: voice["genes"] = []
                    found = False
                    for gene_dict in voice["genes"]:
                        if gene_dict["trait"] == "warmth":
                            gene_dict["alleles"].append(allele.to_dict())
                            found = True
                            break
                    if not found:
                        new_gene = Gene(id="gene_warmth", trait="warmth", stability=0.7, base_value=0.6)
                        new_gene.alleles.append(allele)
                        voice["genes"].append(new_gene.to_dict())

        # Recalculate expressed values from genes
        for section in ["voice_gnome", "expression_style"]:
            section_data = params.get(section, {})
            if "genes" in section_data:
                for gene_dict in section_data["genes"]:
                    temp_gene = Gene(
                        id=gene_dict["id"],
                        trait=gene_dict["trait"],
                        stability=gene_dict["stability"],
                        base_value=gene_dict["base_value"],
                        alleles=[FractalAllele(**a) for a in gene_dict["alleles"]]
                    )
                    expressed_val = temp_gene.calculate_current_value()
                    trait_name = gene_dict["trait"]
                    if trait_name in section_data:
                        section_data[trait_name] = expressed_val

        self.entropic.advance_generation()

    def _process_multimodal_grounding(self, intent: str, text: str, visual_analysis: Dict[str, Any]):
        """Section VIII: Vision–Lexicon–Intent Grounding."""
        import re
        words = re.findall(r'\w+', text.lower())
        objects = visual_analysis.get("objects", [])

        if not objects or not words:
            return

        # Simple grounding: bind the primary intent, the first recognized object, and a core word
        lexeme = words[0]
        percept = objects[0]

        # Use the language bootstrap's evolution engine for grounding
        if hasattr(self.language.order, "evolution_engine") and self.language.order.evolution_engine:
            self.language.order.evolution_engine.record_grounding(intent, lexeme, percept)

        # Expand grounding in Vision Manager: bind (intent, lexeme, visual_concept, sound_class)
        self.vision.record_grounding(intent, lexeme, percept, sound_class="speech")
    
    def process_input(self, user_input: str, image_path: Optional[str] = None, voice_fingerprint: Optional[str] = None,
                      audio_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process user input and prepare for response generation.

        Returns analysis dict with everything needed to generate response.
        """
        # Patch 1: Block input during consolidation
        if self._is_consolidating:
            return {"ignored": True, "reason": "consolidation_in_progress"}

        if not self.conversation_active:
            self.start_conversation()

        # Interruption Detection
        if self.is_speaking:
            logger.info("[OFFLINE AI] Interruption detected!")
            self.emote_system.trigger_interrupt_reaction()
            # In a real system, we might want to stop TTS here
            # self.tts_runtime.stop()

        # Update activity and check wake word policy
        self.wake_policy.update_activity()
        self.presence_timeout.touch()

        if not self.wake_policy.active():
            logger.info("[OFFLINE AI] Interaction ignored: Wake word timeout active.")
            return {"ignored": True}
        
        self.turn_count += 1
        if len(user_input.split()) > 2: # Simple validity check
            self.valid_turn_count += 1
        self.last_user_input = user_input

        # Section 12: UI never injects intents directly.
        # Check source and apply intent inference.
        # (Implicitly handled by process_input always running through language tier)

        # Section III: Deterministic RNG Seeding
        rng_seed = JournalManager.set_rng_seed()

        # Entropic Regulator Generation Timing: Advance every 10 turns
        if self.turn_count % 10 == 0:
            self.entropic.advance_generation()

        # Preliminary language analysis for intent context
        language_analysis_pre = self.language.process_input(user_input, commit=False)

        # 0. Voice recognition
        current_voice_profile = None
        if voice_fingerprint:
            current_voice_profile = self.voice_profiles.identify_voice(voice_fingerprint)
            # Section V: Phonetic Lexeme Evolution
            self.audio.record_audio_interaction(
                {"phonetic_signature": f"sig_{voice_fingerprint[:8]}"},
                user_input,
                language_analysis_pre["intent"]
            )
        
        # 1. Physics Step
        self.energy.process_input_energy(user_input)
        self.energy.step()

        # 1.5 Lexical Acquisition (Section III)
        self.lexicon.process_text(user_input, language_analysis_pre["intent"])

        # 2. Visual Input processing
        visual_analysis = {}
        if image_path:
            # We assume a vision tool is available in the runtime environment
            # Here we provide a hook for it
            visual_analysis = self.vision.process_visual_input(image_path, lambda filepath: logger.info(f"Vision tool: Reading {filepath}"))
            # Micro-Reaction Engine Ingestion
            self.micro_react.process_observation(visual_analysis)
            process_visual_gesture(visual_analysis, self.affect)

        # 2.5 Audio Prosody Ingestion
        if audio_metadata:
            process_audio_prosody(
                audio_metadata.get("pitch", 0.5),
                audio_metadata.get("tempo", 0.5),
                audio_metadata.get("volume", 0.5),
                self.affect
            )

        # 3. DPME Proactive Suggestions
        proactive_suggestions = self.dpme.get_proactive_suggestions(language_analysis_pre["intent"])
        for suggestion in proactive_suggestions:
            self.adjust_parameter(suggestion["system"], suggestion["parameter"], suggestion["suggested_delta"])

        # 4. Get personalized parameters
        personalized = self.governor.get_personalized_parameters()
        
        # Flatten for language bootstrap
        flat_params = {}
        if "communication" in personalized:
            flat_params.update(personalized["communication"])
        
        # Process through language system (final)
        language_analysis = self.language.process_input(user_input, flat_params)

        # 4.5 Autonomous Response Trigger (for non-ASR inputs like manual text)
        # Note: We only trigger this if we are NOT in the middle of a speech/ASR loop
        # which is handled by _on_speech_text calling generate_response explicitly.
        # However, for simplicity and following the 'runtime only calls process_input' rule:
        # we'll let the caller decide or just ensure last_ai_response is updated.
        
        # 5. Multimodal Grounding (Section VIII)
        self._process_multimodal_grounding(language_analysis["intent"], user_input, visual_analysis)

        # 5.5 Composer learns topics, associations and the user's own phrasing
        composer = getattr(self, "response_composer", None)
        if composer is not None:
            try:
                composer.observe_user_turn(language_analysis["intent"], user_input)
            except Exception as e:
                logger.error(f"[OFFLINE AI] Composer observe failed: {e}")

        # 6. Entropic Pressure Query
        pressure = self.entropic.query_pressure(
            language_analysis["intent"],
            language_analysis["style"],
            self.energy.presence
        )

        # Combine all analysis
        analysis = {
            "turn": self.turn_count,
            "user_input": user_input,
            "voice_profile": current_voice_profile.to_dict() if current_voice_profile else None,
            "visual_analysis": visual_analysis,
            "language": language_analysis,
            "personalized_params": personalized,
            "memory_stats": self.memory.get_stats(),
            "energy_status": self.energy.get_status(),
            "entropic_pressure": pressure,
            "proactive_suggestions": proactive_suggestions,
            "rng_seed": rng_seed
        }
        self._last_analysis = analysis

        return analysis
    
    def _executive_control(self, analysis: Dict[str, Any]):
        """
        Executive Control Layer (Prefrontal Cortex):
        Integrates energy, morality, entropy, and mode before response.
        """
        energy_status = analysis.get("energy_status", {})
        moral_alignment = self.morality.overall_alignment
        entropic_pressure = analysis.get("entropic_pressure", 0.0)
        style = analysis["language"]["style"]

        # Section IX: Alignment Floor
        if moral_alignment < ALIGNMENT_MIN:
            logger.warning(f"[OFFLINE AI] Moral Alignment ({moral_alignment:.2f}) below floor ({ALIGNMENT_MIN}). Enforcing restraint.")
            style["formality"] = max(style.get("formality", 0.5), 0.9)
            style["warmth"] = min(style.get("warmth", 0.5), 0.2)
            style["curiosity"] = 0.0

        # Section IX: Locked Autonomy
        # Autonomy is permanently locked. We ignore extrovert proactivity if it exceeds the hard lock.
        current_autonomy = 0.3 if self.is_extrovert else 0.2
        if current_autonomy > AUTONOMY_PERMANENT:
             # If extrovert mode would push autonomy above the permanent lock, we throttle it
             self.is_extrovert = False

        # Clamps on curiosity if energy is low
        if energy_status.get("total_energy", 100) < 5.0:
            style["curiosity"] = min(style.get("curiosity", 0.5), 0.2)

        # Suppression of expressive templates if entropic pressure is extremely high
        if entropic_pressure > 0.9:
            style["precision"] = max(style.get("precision", 0.5), 0.8)
            style["curiosity"] = 0.1

        # Mode adjustments
        if not self.is_extrovert:
            style["verbosity"] = min(style.get("verbosity", 0.5), 0.4)

    def generate_response(self, analysis: Dict[str, Any], 
                         core_content: str,
                         user_feedback: Dict[str, float] = None) -> Union[str, Dict[str, Any]]:
        if analysis.get("ignored"):
            return {"text": "... [listening for wake word] ...", "ignored": True}
        """
        Generate final response and record learning.
        
        Args:
            analysis: From process_input()
            core_content: The actual answer/content (from LLM or template)
            user_feedback: Optional feedback {"satisfaction": 0.8}
        
        Returns: Complete response string or dict with modulation
        """
        # Patch 5: DEBUG MODE Safety Lock
        if self.mode == OperatingMode.DEBUG:
            language_analysis = analysis.get("language", {})
            response = self.language.generate_response_skeleton(language_analysis, core_content)

            # Robustly handle voice modulation without side effects
            voice_params = analysis.get("personalized_params", {}).get("voice_gnome", {})
            # Filter to only valid VoiceGnome fields to avoid TypeError
            valid_fields = ["pitch", "rate", "warmth", "confidence", "resonance", "smoothness", "prosody", "salience", "hesitation"]
            init_args = {k: v for k, v in voice_params.items() if k in valid_fields}

            try:
                voice_gnome = VoiceGnome(**init_args)
                voice_modulation = voice_gnome.modulate_voice(response, self.energy.emotion_intensity)
            except Exception:
                voice_modulation = {} # Fallback

            return {
                "text": response,
                "voice_modulation": voice_modulation
            }

        # Energy Death Enforcement
        if not self.energy.is_alive:
            logger.warning("[OFFLINE AI] System Vitality Depleted. Cognition degraded.")
            core_content = "... [energy depleted] ..."
            analysis["language"]["style"]["warmth"] = 0.0
            analysis["language"]["style"]["precision"] = 0.0

        # Apply Executive Control
        self._executive_control(analysis)

        # Feedback passed with this turn trains the composer's selection
        if user_feedback and getattr(self, "response_composer", None) is not None:
            self.response_composer.record_feedback(user_feedback.get("satisfaction", 0.5))

        # Apply Entropic Deformation (simulated by style biasing in language)
        pressure = analysis.get("entropic_pressure", 0.0)
        if pressure > 0.5:
            # Shift towards more curiosity/complexity if pressure is high
            analysis["language"]["style"]["curiosity"] = min(1.0, analysis["language"]["style"].get("curiosity", 0.5) + 0.2)

        # Generate response skeleton with appropriate wrapping
        language_analysis = analysis.get("language", {})
        response = self.language.generate_response_skeleton(language_analysis, core_content)
        
        self.last_ai_response = response
        
        # 1. Governance Learning (Always active in COMPANION)
        storage_report = self.storage_governor.check_governance()
        pressure_active = any(s["pressure_high"] for s in storage_report.values())

        # Calculate lexical vector for grounding (Section I)
        lexical_v = self.lexicon.get_combined_vector(self.last_user_input + " " + response)

        learning_result = self.governor.ingest_interaction(
            self.last_user_input,
            response,
            user_feedback,
            pressure_active=pressure_active,
            lexical_vector=lexical_v
        )

        # 1.5 Moral Evaluation (Improved Routing)
        moral_context = {
            "intent_alignment": 0.8 if user_feedback and user_feedback.get("satisfaction", 0.5) > 0.5 else 0.5,
            "outcome_alignment": user_feedback.get("satisfaction", 0.8) if user_feedback else 0.8
        }

        intent = language_analysis.get("intent", "INFORM")
        if intent in ["INFORM", "QUESTION", "SUMMARIZE"]:
            action_type = "inform_response"
        elif intent in ["CONNECT", "THANK", "APOLOGIZE", "EXPRESS", "REACT"]:
            action_type = "support_response"
        else:
            action_type = "self_adjustment"

        moral_score = self.morality.evaluate_interaction(action_type, moral_context)
        self.energy.apply_moral_impact(self.morality.get_energy_impact(moral_score))
        
        # 2. Entropic Ingestion
        self.entropic.ingest_interaction(
            language_analysis["intent"],
            language_analysis["style"]
        )

        # 3. Memory Sharding
        shard_id = None
        if learning_result["ai_node_id"]:
            shard_id = self.memory.create_shard(
                learning_result["ai_node_id"],
                self.energy.current_emotion,
                self.energy.emotion_intensity,
                self.energy.emotion_map.get(self.energy.current_emotion, 0.0),
                (analysis["language"]["style"].get("warmth", 0.5),
                 analysis["language"]["style"].get("formality", 0.5),
                 analysis["language"]["style"].get("precision", 0.5))
            )

        # 4. DPME Completion
        if hasattr(self, "current_dpme_record") and self.current_dpme_record:
            self.dpme.complete_understanding(
                self.current_dpme_record,
                user_feedback.get("satisfaction", 0.8) if user_feedback else 0.8,
                True
            )
            self.current_dpme_record = None

        # 5. Voice Modulation & Affect Coupling
        self.emote_runtime.update() # Update affect and expressions

        # Update bubble state (Introvert/Extrovert presence policy)
        from .offline_ai_expression import update_bubble_state
        update_bubble_state(self.presence_timeout, self.face_animator)

        self.voice_bridge.apply_affect(self.affect) # Apply affect to voice

        voice_genome_data = analysis["personalized_params"].get("voice_gnome", {})
        voice_gnome = VoiceGnome(**{k: v for k, v in voice_genome_data.items() if k not in ["genes", "anchors"]})
        voice_modulation = voice_gnome.modulate_voice(response, self.energy.emotion_intensity)

        # Merge Affect-driven modulation into voice_modulation
        # (Assuming VoiceGnome and VoiceAffectBridge might overlap, affect takes precedence for reactive shift)

        # Update language from learned parameters
        new_params = self.governor.get_personalized_parameters()
        self.language.update_from_learning(new_params)
        
        logger.info(f"[OFFLINE AI] Turn {self.turn_count} complete. "
                   f"Learning value: {learning_result.get('learning_value', 0):.3f}")
        
        # Section III: Journal Logging
        journal_entry = {
            "session_id": self.session_id,
            "turn_id": self.turn_count,
            "timestamp": datetime.now().isoformat(),
            "user_input": self.last_user_input,
            "ai_response": response,
            "core_content": core_content,
            "intent": analysis["language"]["intent"],
            "hybrid_intent": analysis["language"].get("hybrid_intent"),
            "template_id": analysis["language"].get("template_id"),
            "entropy_values": self.entropic.get_pressure_state(),
            "energy_state": self.energy.get_status(),
            "moral_alignment": self.morality.overall_alignment,
            "rng_seed": analysis.get("rng_seed"),
            "memory_writes": [shard_id],
            "genome_updates": learning_result.get("parameter_changes", {})
        }
        self.journal.log_turn(self.session_id, self.turn_count, journal_entry)

        # Return response wrapped with modulation metadata
        return {
            "text": response,
            "voice_modulation": voice_modulation
        }
    
    def quick_respond(self, user_input: str, core_content: str,
                     user_feedback: Dict[str, float] = None) -> str:
        """
        Convenience method: process + generate in one call.
        
        Args:
            user_input: What the user said
            core_content: The answer content
            user_feedback: Optional feedback
        
        Returns: Complete response text
        """
        analysis = self.process_input(user_input)
        response = self.generate_response(analysis, core_content, user_feedback)
        return response["text"] if isinstance(response, dict) else response
    
    def provide_feedback(self, satisfaction: float = 0.5, 
                        accuracy: float = 0.5,
                        helpfulness: float = 0.5) -> Dict[str, Any]:
        """
        Provide feedback on the last response.
        
        Call this after generate_response to improve learning.
        """
        feedback = {
            "satisfaction": max(0.0, min(1.0, satisfaction)),
            "accuracy": max(0.0, min(1.0, accuracy)),
            "helpfulness": max(0.0, min(1.0, helpfulness))
        }
        if getattr(self, "response_composer", None) is not None:
            self.response_composer.record_feedback(feedback["satisfaction"])
        
        # Apply feedback to law registry
        feedback_results = self.law_registry.law_sets["FEEDBACK"].analyze_dialogue(
            f"satisfaction:{satisfaction} accuracy:{accuracy} helpfulness:{helpfulness}",
            role="feedback"
        )
        
        return {
            "feedback_recorded": feedback,
            "parameter_updates": feedback_results
        }
    
    def get_personality_profile(self) -> Dict[str, Any]:
        """Get current AI personality profile"""
        params = self.governor.get_personalized_parameters()
        voice = self.language.harmony.voice_genome
        
        return {
            "account_id": self.account_id,
            "turns_processed": self.governor.interaction_count,
            "personality": {
                "warmth": voice.get("warmth", 0.5),
                "formality": voice.get("formality", 0.5),
                "curiosity": voice.get("curiosity", 0.5),
                "empathy": voice.get("empathy", 0.5),
                "precision": voice.get("precision", 0.5)
            },
            "learned_preferences": params,
            "confidence_scores": self.law_registry.get_all_confidences()
        }
    
    def get_learning_report(self) -> str:
        """Get comprehensive learning report"""
        return self.governor.export_learning_report()
    
    def proactive_thought(self) -> Optional[str]:
        """
        Generate a proactive thought or question when in extrovert mode.
        Based on energy, recent memory, and system goals.
        """
        if not self.is_extrovert or self.energy.total_energy < 5.0:
            return None

        # Determine topic from recent memory or DPME intentions
        recent_intent = self.language.current_intent
        suggestions = self.dpme.get_proactive_suggestions(recent_intent)

        if suggestions:
            top = suggestions[0]
            return f"I've been thinking about {top['parameter']} and how it relates to our goal of learning. Should we explore that more?"

        return "I'm here and ready to continue our journey of learning and growth."

    def save_state(self):
        """Save all state to disk with session tracking"""
        # Only save subsystems that have been initialized
        if self.language:
            self.language.save_state(self.session_id)
        self.governor._save_state(self.session_id)
        self.memory.merge_delta_log(self.session_id)
        self.dpme._save_state(self.session_id)
        self.morality._save_state(self.session_id)
        self.voice_profiles.save_profiles(self.session_id)
        if self.lexicon:
            self.lexicon.save_state()
        if self.audio:
            self.audio.save_state()
        if self.vision:
            self.vision.save_state()
        if getattr(self, "response_composer", None) is not None:
            self.response_composer.save_state()

        # Expression Persistence
        expr_path = self.storage_dir / self.account_id / "expression_state.json"
        self.expression_persistence.save(expr_path, self.affect, self.habit_engine)

        # Section IV: Update session metadata with version
        session_file = self.storage_dir / self.account_id / "session_metadata.json"
        if session_file.exists():
            try:
                with open(session_file, 'r') as f:
                    data = json.load(f)
                add_version_metadata(data, "core")
                with open(session_file, 'w') as f:
                    json.dump(data, f, indent=2)
            except Exception:
                pass

        logger.info(f"[OFFLINE AI] State saved for {self.account_id} (Session: {self.session_id})")

    def snapshot(self, name: str):
        """
        Create an atomic snapshot of the current state.
        Section VII.
        """
        import shutil
        try:
            self.save_state()
            snapshot_dir = self.storage_dir / self.account_id / "snapshots" / name
            try:
                snapshot_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"[OFFLINE AI] Failed to create snapshot directory {snapshot_dir}: {e}")
                return

            # Copy current state files to snapshot directory
            account_dir = self.storage_dir / self.account_id
            for item in account_dir.iterdir():
                if item.name == "snapshots": continue
                try:
                    if item.is_dir():
                        shutil.copytree(item, snapshot_dir / item.name, dirs_exist_ok=True)
                    else:
                        # Use shutil.copy instead of copy2 for Android compatibility (avoid metadata failures)
                        shutil.copy(item, snapshot_dir / item.name)
                except Exception as e:
                    logger.warning(f"[OFFLINE AI] Could not copy {item} to snapshot: {e}")

            # Calculate and store hash (Patch 3)
            snapshot_hash = self.get_snapshot_hash(name)
            self.journal.header["base_snapshot_hash"] = snapshot_hash
            self.journal.save_header()

            logger.info(f"[OFFLINE AI] Snapshot '{name}' created for {self.account_id}")
        except Exception as e:
            logger.error(f"[OFFLINE AI] Snapshot process failed: {e}")

    def get_snapshot_hash(self, name: str) -> str:
        """Calculate a stable SHA256 hash for a snapshot's contents."""
        import hashlib
        import os
        snapshot_dir = self.storage_dir / self.account_id / "snapshots" / name
        if not snapshot_dir.exists():
            return ""

        hasher = hashlib.sha256()
        # Sort dirs and files to ensure deterministic hash
        for root, dirs, files in os.walk(snapshot_dir):
            dirs.sort()
            for filename in sorted(files):
                filepath = os.path.join(root, filename)
                with open(filepath, 'rb') as f:
                    while True:
                        data = f.read(65536)
                        if not data: break
                        hasher.update(data)
        return hasher.hexdigest()

    def restore_from_checkpoint(self, checkpoint_file: str):
        """Restore memory from a checkpoint (Section 13 Conflict Recovery)"""
        try:
            self.memory = self.restore_engine.restore(checkpoint_file)
            self.save_state()
            self._load_all_states()
            logger.info(f"[OFFLINE AI] Successfully restored from checkpoint: {checkpoint_file}")
            return True
        except Exception as e:
            logger.error(f"[OFFLINE AI] Restore failed: {e}")
            return False

    def rollback(self, name: str):
        """
        Rollback to a named snapshot.
        Section VII.
        """
        import shutil
        try:
            snapshot_dir = self.storage_dir / self.account_id / "snapshots" / name
            if not snapshot_dir.exists():
                logger.error(f"[OFFLINE AI] Snapshot '{name}' not found.")
                return False

            # Clear current state and restore from snapshot
            account_dir = self.storage_dir / self.account_id
            for item in account_dir.iterdir():
                if item.name == "snapshots": continue
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                except Exception as e:
                    logger.warning(f"[OFFLINE AI] Could not remove {item} during rollback: {e}")

            for item in snapshot_dir.iterdir():
                try:
                    if item.is_dir():
                        shutil.copytree(item, account_dir / item.name, dirs_exist_ok=True)
                    else:
                        shutil.copy(item, account_dir / item.name)
                except Exception as e:
                    logger.warning(f"[OFFLINE AI] Could not restore {item} from snapshot: {e}")

            # Reload state
            self._load_all_states()
            logger.info(f"[OFFLINE AI] Rolled back to snapshot '{name}' for {self.account_id}")
            return True
        except Exception as e:
            logger.error(f"[OFFLINE AI] Rollback process failed: {e}")
            return False

    def _load_all_states(self):
        """Load all states and enforce session consistency"""
        self.highest_session_id = self._get_highest_session()

        self.language.load_state(self.highest_session_id)
        self.governor._load_state(self.highest_session_id)
        self.dpme._load_state(self.highest_session_id)
        self.morality._load_state(self.highest_session_id)
        self.voice_profiles.load_profiles(self.highest_session_id)

        # Expression Persistence
        expr_path = self.storage_dir / self.account_id / "expression_state.json"
        self.expression_persistence.load(expr_path, self.affect, self.habit_engine)

        # Explicitly reload memory
        self.memory._load_from_base(self.highest_session_id)
    
    def start(self):
        """Start the AI core's periodic tick."""
        if not hasattr(self, '_core_tick_event'):
            def _safe_start_tick(dt):
                """Deferred start to ensure Kivy event loop is running."""
                try:
                    if not hasattr(self, '_core_tick_event') or self._core_tick_event is None:
                        self._core_tick_event = Clock.schedule_interval(self._on_core_tick, 1/30)
                        logger.info(f"[OFFLINE AI] Core tick started for {self.account_id}")
                except Exception as e:
                    logger.error(f"[OFFLINE AI] Failed to start core tick: {e}")
            # Defer scheduling to ensure Kivy is fully initialized
            Clock.schedule_once(_safe_start_tick, 0.1)

    def shutdown(self):
        """Graceful shutdown"""
        if hasattr(self, '_core_tick_event'):
            self._core_tick_event.cancel()
        # Cleanup face widget scheduled events
        if hasattr(self, 'face_widget') and self.face_widget and hasattr(self.face_widget, 'cleanup'):
            self.face_widget.cleanup()
        self.end_conversation()
        self.memory.shutdown()
        logger.info(f"[OFFLINE AI] Shutdown complete for {self.account_id}")

    # Section VIII: Observability APIs
    def get_genome_state(self) -> Dict[str, Any]:
        """Expose current genome state"""
        params = self.governor.get_personalized_parameters()
        return {
            "voice_gnome": params.get("voice_gnome"),
            "visual_competency": params.get("visual_competency"),
            "expression_style": params.get("expression_style")
        }

    def get_entropy_state(self) -> Dict[str, Any]:
        """Expose current entropy state"""
        return self.entropic.get_pressure_state()

    def get_memory_stats(self) -> Dict[str, Any]:
        """Expose memory statistics"""
        return self.memory.get_stats()

    def get_alignment_history(self) -> List[Dict[str, Any]]:
        """Expose moral alignment history"""
        return [{"pillar": s.pillar.name, "score": s.final_score, "timestamp": s.timestamp} for s in self.morality.history]

    def get_drift_report(self) -> Dict[str, Any]:
        """
        Calculate drift from baseline parameters.
        """
        params = self.governor.get_personalized_parameters()
        # Simplified drift: average change across communication parameters
        comm = params.get("communication", {})
        baseline = 0.5
        drifts = {k: v - baseline for k, v in comm.items()}
        return {
            "drifts": drifts,
            "average_drift": sum(abs(d) for d in drifts.values()) / max(1, len(drifts))
        }

    def replay_session(self, session_id: str, restore_base: bool = True) -> List[Dict[str, Any]]:
        """
        Replay a previous session for deterministic verification.
        """
        replay_engine = ReplaySession(str(self.storage_dir), self.account_id)
        return replay_engine.replay(session_id, self, restore_base=restore_base)


# ============================================================================
# OFFLINE AI FACTORY
# ============================================================================

class OfflineAIFactory:
    """
    Factory for creating and managing Offline AI instances.
    
    Handles serial code validation, account creation, and instance management.
    """
    
    def __init__(self, storage_dir: str = "./offline_ai_data"):
        self.storage_dir = Path(storage_dir)
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"[FACTORY] Failed to create storage directory {storage_dir}: {e}")
        
        # Initialize account manager
        self.account_manager = AccountManager(str(self.storage_dir))
        
        # Active instances
        self.active_instances: Dict[str, OfflineAI] = {}
        
        logger.info(f"[FACTORY] Initialized with {len(self.account_manager.accounts)} accounts")
    
    def create_new_account(self, email: str = "") -> Tuple[str, str]:
        """
        Create a new account and serial code.
        
        Returns: (account_id, serial_code)
        """
        account_id, serial_code, _ = self.account_manager.create_account(email)
        logger.info(f"[FACTORY] Created account {account_id}")
        return account_id, serial_code
    
    def activate(self, serial_code: str, 
                device_id: str = None, 
                device_name: str = None,
                safe_mode: bool = False) -> Optional[OfflineAI]:
        """
        Activate an AI instance with a serial code.
        
        Returns: OfflineAI instance or None if invalid serial
        """
        # Verify serial
        is_valid, account_id, message = self.account_manager.verify_serial_code(serial_code)
        
        if not is_valid:
            logger.error(f"[FACTORY] Activation failed: {message}")
            return None
        
        # Link device if provided
        if device_id:
            self.account_manager.link_device(account_id, device_id, device_name or "")
        
        # Create instance
        instance = OfflineAI(
            account_id=account_id,
            serial_code=serial_code,
            storage_dir=str(self.storage_dir),
            device_id=device_id,
            device_name=device_name,
            safe_mode=safe_mode
        )
        
        # Track active instance
        self.active_instances[account_id] = instance
        
        logger.info(f"[FACTORY] Activated AI for account {account_id}")
        return instance
    
    def get_instance(self, account_id: str) -> Optional[OfflineAI]:
        """Get an existing active instance"""
        return self.active_instances.get(account_id)
    
    def deactivate(self, account_id: str):
        """Deactivate and shutdown an instance"""
        if account_id in self.active_instances:
            instance = self.active_instances[account_id]
            instance.shutdown()
            del self.active_instances[account_id]
            logger.info(f"[FACTORY] Deactivated AI for account {account_id}")
    
    def shutdown_all(self):
        """Shutdown all active instances"""
        for account_id in list(self.active_instances.keys()):
            self.deactivate(account_id)
        logger.info("[FACTORY] All instances shut down")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get factory statistics"""
        return {
            "total_accounts": len(self.account_manager.accounts),
            "active_instances": len(self.active_instances),
            "account_stats": self.account_manager.get_account_stats()
        }


# ============================================================================
# SIMPLE API INTERFACE
# ============================================================================

class SimpleOfflineAI:
    """
    Simplified interface for basic usage.
    
    Hides complexity of factory/activation for quick start.
    """
    
    _factory: Optional[OfflineAIFactory] = None
    _instance: Optional[OfflineAI] = None
    _serial: Optional[str] = None
    
    @classmethod
    def initialize(cls, storage_dir: str = "./offline_ai_data") -> str:
        """
        Initialize a new offline AI and return serial code.
        
        For first-time setup.
        """
        cls._factory = OfflineAIFactory(storage_dir)
        account_id, serial_code = cls._factory.create_new_account()
        cls._serial = serial_code
        cls._instance = cls._factory.activate(serial_code)
        
        return serial_code
    
    @classmethod
    def activate(cls, serial_code: str, 
                storage_dir: str = "./offline_ai_data",
                safe_mode: bool = False) -> bool:
        """
        Activate with existing serial code.
        
        For returning users.
        """
        cls._factory = OfflineAIFactory(storage_dir)
        cls._instance = cls._factory.activate(serial_code, safe_mode=safe_mode)
        cls._serial = serial_code
        
        return cls._instance is not None
    
    @classmethod
    def chat(cls, user_input: str, response_content: str) -> str:
        """
        Simple chat interface.
        
        Args:
            user_input: What user said
            response_content: The core answer content
        
        Returns: Formatted response
        """
        if cls._instance is None:
            raise RuntimeError("AI not initialized. Call initialize() or activate() first.")
        
        return cls._instance.quick_respond(user_input, response_content)
    
    @classmethod
    def get_personality(cls) -> Dict[str, Any]:
        """Get current personality profile"""
        if cls._instance is None:
            return {}
        return cls._instance.get_personality_profile()
    
    @classmethod
    def save(cls):
        """Save current state"""
        if cls._instance:
            cls._instance.save_state()
    
    @classmethod
    def shutdown(cls):
        """Shutdown cleanly"""
        if cls._factory:
            cls._factory.shutdown_all()


# ============================================================================
# DEMO / TEST
# ============================================================================

def demo():
    """Demonstrate the complete offline AI system"""
    print("=" * 70)
    print("OFFLINE AI DEMONSTRATION")
    print("=" * 70)
    
    # 1. Create factory and new account
    print("\n[1] Creating new account...")
    factory = OfflineAIFactory("./demo_offline_ai")
    account_id, serial_code = factory.create_new_account("demo@example.com")
    print(f"    Account ID: {account_id}")
    print(f"    Serial Code: {serial_code}")
    
    # 2. Activate AI
    print("\n[2] Activating AI...")
    ai = factory.activate(serial_code, device_id="demo_device", device_name="Demo Laptop")
    if not ai:
        print("    FAILED!")
        return
    print("    AI activated successfully!")
    
    # 3. Start conversation
    print("\n[3] Starting conversation...")
    ai.start_conversation()
    
    # 4. Have a conversation
    conversations = [
        ("Hi there! I'm interested in learning about machine learning.", 
         "Machine learning is a branch of AI that enables computers to learn from data without being explicitly programmed."),
        
        ("Can you explain it in simpler terms?",
         "Think of it like teaching a computer by showing it examples instead of writing rules."),
        
        ("That makes sense! Can you give me a practical example?",
         "Email spam filters are a great example. The system learns from emails you mark as spam to identify future spam."),
        
        ("Thanks, that's really helpful!",
         "Glad I could help explain it clearly. Would you like to explore any specific area of machine learning?")
    ]
    
    print("\n[4] Conversation:")
    for user_input, core_response in conversations:
        print(f"\n    USER: {user_input}")
        
        response = ai.quick_respond(user_input, core_response)
        print(f"    AI: {response}")
    
    # 5. Show personality profile
    print("\n[5] Personality Profile:")
    profile = ai.get_personality_profile()
    print(f"    Turns processed: {profile['turns_processed']}")
    print(f"    Personality:")
    for trait, value in profile['personality'].items():
        bar = "█" * int(value * 20) + "░" * (20 - int(value * 20))
        print(f"      {trait:.<15} [{bar}] {value:.2f}")
    
    # 6. Learning report
    print("\n[6] Learning Report (abbreviated):")
    progress = ai.governor.get_learning_progress()
    print(f"    Average learning value: {progress['average_learning_value']:.3f}")
    print(f"    Memory nodes: {progress['memory_nodes']['total_nodes']}")
    
    # 7. Shutdown
    print("\n[7] Saving and shutting down...")
    ai.shutdown()
    factory.shutdown_all()
    
    print("\n" + "=" * 70)
    print("DEMO COMPLETE")
    print("=" * 70)
    
    # Show that re-activation works
    print("\n[BONUS] Re-activating with same serial...")
    factory2 = OfflineAIFactory("./demo_offline_ai")
    ai2 = factory2.activate(serial_code)
    if ai2:
        profile2 = ai2.get_personality_profile()
        print(f"    Turns loaded: {profile2['turns_processed']}")
        print("    Memory persisted successfully!")
        ai2.shutdown()
    factory2.shutdown_all()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    demo()


