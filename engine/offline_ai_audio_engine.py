#!/usr/bin/env python3
"""
Offline AI Audio Engine - Android Native Only
==============================================
Authors: Sunni (Sir) Morningstar & Cael Devo

Single-authority audio subsystem for Android.
NO Termux dependencies - uses native Android APIs only.

Components:
- AndroidTTS: Native Text-to-Speech
- AndroidSpeechRecognizer: Native Speech Recognition
- AudioEngine: Unified coordinator (owned by Runtime)
"""

import logging
import threading
import time
from typing import Callable, Optional
from enum import Enum, auto
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# ============================================================================
# PLATFORM DETECTION
# ============================================================================

# Lazy Kivy imports to avoid crash on Android startup
try:
    from kivy.utils import platform
    IS_ANDROID = platform == 'android'
except ImportError:
    IS_ANDROID = False

# Clock imported lazily in functions where needed
# Safe Clock import for both Kivy and non-Kivy environments
try:
    from kivy.clock import Clock
except ImportError:
    # Fallback for when Kivy isn't initialized yet
    Clock = None

if IS_ANDROID:
    try:
        from jnius import autoclass, PythonJavaClass, java_method
        from android.runnable import run_on_ui_thread
        
        # Core Android Classes
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        TextToSpeech = autoclass('android.speech.tts.TextToSpeech')
        SpeechRecognizer = autoclass('android.speech.SpeechRecognizer')
        RecognizerIntent = autoclass('android.speech.RecognizerIntent')
        Intent = autoclass('android.content.Intent')
        Locale = autoclass('java.util.Locale')
        Bundle = autoclass('android.os.Bundle')
        AudioManager = autoclass('android.media.AudioManager')
        Context = autoclass('android.content.Context')
        
        JNIUS_AVAILABLE = True
        logger.info("[AUDIO_ENGINE] Android JNI bridge available")
    except Exception as e:
        logger.exception(f"[AUDIO_ENGINE] Android JNI bridge init failed: {e}")
        JNIUS_AVAILABLE = False
else:
    JNIUS_AVAILABLE = False

# ============================================================================
# SAFE SCHEDULING HELPER
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

# ============================================================================
# ENUMERATIONS
# ============================================================================

class AudioEngineState(Enum):
    """Internal states - NOT the Runtime state machine"""
    UNINITIALIZED = auto()
    INITIALIZING = auto()
    READY = auto()
    LISTENING = auto()
    SPEAKING = auto()
    ERROR = auto()


class TTSEvent(Enum):
    """TTS lifecycle events"""
    STARTED = auto()
    COMPLETED = auto()
    ERROR = auto()


class RecognitionEvent(Enum):
    """Recognition lifecycle events"""
    READY = auto()
    BEGIN_SPEECH = auto()
    END_SPEECH = auto()
    PARTIAL_RESULT = auto()
    FINAL_RESULT = auto()
    ERROR = auto()


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class VoiceParams:
    """Voice modulation parameters"""
    pitch: float = 1.0
    rate: float = 1.0
    volume: float = 1.0
    
    def to_android_pitch(self) -> float:
        """Convert to Android pitch scale (0.5 - 2.0, 1.0 = normal)"""
        return 0.5 + (self.pitch * 1.5)
    
    def to_android_rate(self) -> float:
        """Convert to Android speech rate (0.5 - 2.0, 1.0 = normal)"""
        return 0.5 + (self.rate * 1.5)


@dataclass  
class RecognitionResult:
    """Speech recognition result"""
    text: str
    confidence: float
    is_partial: bool = False


# ============================================================================
# ANDROID TTS IMPLEMENTATION
# ============================================================================

class AndroidTTSEngine:
    """
    Native Android Text-to-Speech.
    No Termux. No fallbacks.
    """
    
    def __init__(self, language: str = "en-US"):
        self.language = language
        self._state = AudioEngineState.UNINITIALIZED
        self._tts = None
        self._init_listener = None
        self._utterance_listener = None
        self._current_callback: Optional[Callable] = None
        self._init_started = False
        
        # Metrics
        self._utterance_count = 0
        self._last_error: Optional[str] = None
        
        # Don't initialize immediately - do it lazily on first use
        # This prevents crashes during app startup when Android isn't ready
        if not IS_ANDROID or not JNIUS_AVAILABLE:
            self._state = AudioEngineState.ERROR
            logger.error("[TTS] Not on Android or JNIUS unavailable - TTS DISABLED")
    
    def _ensure_initialized(self):
        """Lazy initialization - called before any TTS operation"""
        if self._state == AudioEngineState.UNINITIALIZED and not self._init_started:
            if IS_ANDROID and JNIUS_AVAILABLE:
                self._initialize()
            else:
                self._state = AudioEngineState.ERROR
    
    def _initialize(self):
        """Initialize TTS on Android UI thread"""
        self._init_started = True
        self._state = AudioEngineState.INITIALIZING
        
        @run_on_ui_thread
        def _create():
            try:
                activity = PythonActivity.mActivity
                
                # OnInitListener - called when TTS engine is ready
                class OnInitListener(PythonJavaClass):
                    __javainterfaces__ = ['android/speech/tts/TextToSpeech$OnInitListener']
                    __javacontext__ = 'app'
                    
                    def __init__(self, engine):
                        super().__init__()
                        self.engine = engine
                    
                    @java_method('(I)V')
                    def onInit(self, status):
                        """Called from Java thread when TTS is initialized"""
                        try:
                            if status == 0:  # SUCCESS == TextToSpeech.SUCCESS
                                self.engine._on_init_success()
                            else:
                                self.engine._on_init_error(f"TTS init failed: {status}")
                        except Exception as e:
                            # Must catch all exceptions to prevent Java crash
                            try:
                                self.engine._state = AudioEngineState.ERROR
                                logger.error(f"[TTS] onInit handler error: {e}")
                            except:
                                pass
                
                self._init_listener = OnInitListener(self)
                self._tts = TextToSpeech(activity, self._init_listener)
                logger.info("[TTS] Initialization started")
                
            except Exception as e:
                self._on_init_error(f"TTS creation failed: {e}")
        
        _create()
    
    def _on_init_success(self):
        """Called when TTS is initialized - may be called from Java thread"""
        try:
            # Set language
            locale = Locale.US
            if "gb" in self.language.lower() or "uk" in self.language.lower():
                locale = Locale.UK
            result = self._tts.setLanguage(locale)
            
            if result < 0:
                logger.warning(f"[TTS] Language '{self.language}' may not be fully supported")
            
            # Set default parameters
            self._tts.setSpeechRate(0.9)  # Slightly slower for clarity
            self._tts.setPitch(1.0)
            
            # Set up utterance progress listener
            self._setup_utterance_listener()
            
            self._state = AudioEngineState.READY
            logger.info("[TTS] Ready")
            
        except Exception as e:
            logger.error(f"[TTS] Post-init config failed: {e}")
            self._state = AudioEngineState.ERROR
    
    def _on_init_error(self, error: str):
        """Handle initialization error - may be called from Java thread"""
        try:
            self._last_error = error
            self._state = AudioEngineState.ERROR
            logger.error(f"[TTS] {error}")
        except:
            pass
    
    def _setup_utterance_listener(self):
        """Set up listener for speech events"""
        engine = self
        
        class UtteranceListener(PythonJavaClass):
            __javainterfaces__ = ['android/speech/tts/UtteranceProgressListener']
            __javacontext__ = 'app'
            
            @java_method('(Ljava/lang/String;)V')
            def onStart(self, utterance_id):
                try:
                    logger.debug(f"[TTS] Started: {utterance_id}")
                except:
                    pass
            
            @java_method('(Ljava/lang/String;)V')
            def onDone(self, utterance_id):
                try:
                    if engine._current_callback:
                        cb = engine._current_callback
                        engine._current_callback = None
                        schedule_once(lambda dt: cb(), 0)
                except:
                    pass
            
            @java_method('(Ljava/lang/String;I)V')
            def onError(self, utterance_id, error_code=-1):
                """Handle error - signature supports both old (1 arg) and new (2 arg) Android versions"""
                try:
                    if engine._current_callback:
                        cb = engine._current_callback
                        engine._current_callback = None
                        schedule_once(lambda dt: cb(), 0)
                except:
                    pass
        
        self._utterance_listener = UtteranceListener()
        self._tts.setOnUtteranceProgressListener(self._utterance_listener)
    
    @property
    def is_ready(self) -> bool:
        self._ensure_initialized()
        return self._state == AudioEngineState.READY
    
    @property
    def state(self) -> AudioEngineState:
        return self._state
    
    def is_speaking(self) -> bool:
        """Check if TTS is currently speaking"""
        self._ensure_initialized()
        if self._tts and self._state == AudioEngineState.READY:
            try:
                return self._tts.isSpeaking()
            except:
                pass
        return False
    
    def speak(self, text: str, params: VoiceParams = None, 
              on_complete: Callable = None, phoneme_cb: Callable = None):
        """
        Speak text using Android TTS.
        
        Args:
            text: Text to speak
            params: Voice parameters
            on_complete: Called when speech completes
            phoneme_cb: Called with phoneme events (for lip sync)
        """
        # Ensure initialized first (lazy init)
        self._ensure_initialized()
        
        if not text or not text.strip():
            if on_complete:
                schedule_once(lambda dt: on_complete(), 0)
            return
        
        if self._state != AudioEngineState.READY:
            logger.error(f"[TTS] Cannot speak - state is {self._state}")
            if on_complete:
                schedule_once(lambda dt: on_complete(), 0)
            return
        
        params = params or VoiceParams()
        self._current_callback = on_complete
        
        @run_on_ui_thread
        def _speak():
            try:
                # Double-check state before speaking (thread safety)
                if self._state != AudioEngineState.READY or not self._tts:
                    logger.warning("[TTS] Not ready, cannot speak")
                    if on_complete:
                        schedule_once(lambda dt: on_complete(), 0)
                    return
                
                # Apply voice parameters
                self._tts.setPitch(params.to_android_pitch())
                self._tts.setSpeechRate(params.to_android_rate())
                
                # Create utterance ID
                self._utterance_count += 1
                utterance_id = f"tts_{self._utterance_count}_{int(time.time())}"
                
                # Build parameters bundle
                bundle = Bundle()
                bundle.putString(TextToSpeech.Engine.KEY_PARAM_UTTERANCE_ID, utterance_id)
                
                # Speak with QUEUE_FLUSH (0) to interrupt any current speech
                result = self._tts.speak(text, 0, bundle, utterance_id)
                
                if result < 0:
                    logger.error("[TTS] speak() returned error")
                    self._current_callback = None
                    if on_complete:
                        schedule_once(lambda dt: on_complete(), 0)
                    return
                
                logger.info(f"[TTS] Speaking: {text[:60]}...")
                
                # Simulate phoneme events for lip sync
                if phoneme_cb:
                    self._simulate_phonemes(text, phoneme_cb)
                    
            except Exception as e:
                logger.error(f"[TTS] Speak error: {e}")
                self._current_callback = None
                if on_complete:
                    schedule_once(lambda dt: on_complete(), 0)
        
        _speak()
    
    def _simulate_phonemes(self, text: str, callback: Callable):
        """Simulate phoneme events for lip sync visualization"""
        try:
            words = text.split()
            if not words:
                return
            
            # Estimate timing - cap to avoid excessive callbacks
            estimated_duration = min(len(text) * 0.06, 10.0)  # Max 10 seconds
            interval = max(0.05, estimated_duration / len(words))  # Min 50ms interval
            
            def emit(idx):
                try:
                    if idx < len(words):
                        word = words[idx]
                        # Use first letter as phoneme approximation
                        phoneme = word[0].lower() if word else 'a'
                        try:
                            callback(phoneme)
                        except:
                            pass
                        # Schedule next
                        schedule_once(lambda dt: emit(idx + 1), interval)
                except:
                    pass
            
            schedule_once(lambda dt: emit(0), 0.1)
        except:
            pass
    
    def stop(self):
        """Stop current speech"""
        self._ensure_initialized()
        if self._tts and self._state == AudioEngineState.READY:
            @run_on_ui_thread
            def _stop():
                try:
                    self._tts.stop()
                except Exception as e:
                    logger.error(f"[TTS] Stop error: {e}")
            _stop()
        self._current_callback = None
    
    def shutdown(self):
        """Shutdown TTS engine"""
        self._ensure_initialized()
        self.stop()
        if self._tts:
            @run_on_ui_thread
            def _shutdown():
                try:
                    self._tts.shutdown()
                    logger.info("[TTS] Shutdown complete")
                except Exception as e:
                    logger.error(f"[TTS] Shutdown error: {e}")
            _shutdown()


# ============================================================================
# ANDROID SPEECH RECOGNITION
# ============================================================================

class AndroidSpeechEngine:
    """
    Native Android Speech Recognition.
    Continuous listening with callbacks to Runtime.
    """
    
    def __init__(self, language: str = "en-US"):
        self.language = language
        self._state = AudioEngineState.UNINITIALIZED
        self._recognizer = None
        self._listener = None
        self._activity = None
        self._init_started = False
        
        # Callbacks - these route to Runtime
        self.on_result: Optional[Callable[[str], None]] = None
        self.on_partial: Optional[Callable[[str], None]] = None
        self.on_error: Optional[Callable[[int], None]] = None
        self.on_ready: Optional[Callable[[], None]] = None
        
        # Control flags
        self._continuous = False
        self._should_listen = False
        self._is_starting = False
        
        # Error tracking
        self._consecutive_errors = 0
        self._max_consecutive_errors = 5
        
        # Lazy initialization - don't init until needed
        # This allows permissions to be granted first
        if not IS_ANDROID or not JNIUS_AVAILABLE:
            self._state = AudioEngineState.ERROR
            logger.error("[SPEECH] Not on Android or JNIUS unavailable - Recognition DISABLED")
    
    def _ensure_initialized(self):
        """Lazy initialization - called before any speech operation"""
        if self._state == AudioEngineState.UNINITIALIZED and not self._init_started:
            if IS_ANDROID and JNIUS_AVAILABLE:
                self._initialize()
            else:
                self._state = AudioEngineState.ERROR
    
    def _initialize(self):
        """Initialize speech recognizer"""
        self._init_started = True
        self._state = AudioEngineState.INITIALIZING
        
        @run_on_ui_thread
        def _create():
            try:
                self._activity = PythonActivity.mActivity
                
                if not SpeechRecognizer.isRecognitionAvailable(self._activity):
                    self._state = AudioEngineState.ERROR
                    logger.error("[SPEECH] Recognition not available on this device")
                    return
                
                self._recognizer = SpeechRecognizer.createSpeechRecognizer(self._activity)
                self._setup_listener()
                self._state = AudioEngineState.READY
                logger.info("[SPEECH] Recognizer ready")
                
            except Exception as e:
                self._state = AudioEngineState.ERROR
                logger.error(f"[SPEECH] Init error: {e}")
        
        _create()
    
    def _setup_listener(self):
        """Set up recognition listener"""
        engine = self
        
        class RecognitionListener(PythonJavaClass):
            __javainterfaces__ = ['android/speech/RecognitionListener']
            __javacontext__ = 'app'
            
            @java_method('(Landroid/os/Bundle;)V')
            def onReadyForSpeech(self, params):
                logger.debug("[SPEECH] Ready for speech")
                if engine.on_ready:
                    schedule_once(lambda dt: engine.on_ready(), 0)
            
            @java_method('()V')
            def onBeginningOfSpeech(self):
                logger.debug("[SPEECH] Speech began")
                engine._consecutive_errors = 0  # Reset error count on success
            
            @java_method('(F)V')
            def onRmsChanged(self, rmsdB):
                pass  # Could use for visualizer
            
            @java_method('([B)V')
            def onBufferReceived(self, buffer):
                pass
            
            @java_method('()V')
            def onEndOfSpeech(self):
                logger.debug("[SPEECH] Speech ended")
            
            @java_method('(I)V')
            def onError(self, error):
                engine._on_error(error)
            
            @java_method('(Landroid/os/Bundle;)V')
            def onResults(self, results):
                engine._on_results(results)
            
            @java_method('(Landroid/os/Bundle;)V')
            def onPartialResults(self, partial):
                engine._on_partial(partial)
            
            @java_method('(ILandroid/os/Bundle;)V')
            def onEvent(self, event_type, params):
                pass
        
        self._listener = RecognitionListener()
        self._recognizer.setRecognitionListener(self._listener)
    
    def _on_error(self, error_code: int):
        """Handle recognition error"""
        error_names = {
            1: "NETWORK_TIMEOUT",
            2: "NETWORK", 
            3: "AUDIO",
            4: "SERVER",
            5: "CLIENT",
            6: "SPEECH_TIMEOUT",
            7: "NO_MATCH",
            8: "RECOGNIZER_BUSY",
            9: "INSUFFICIENT_PERMISSIONS"
        }
        error_name = error_names.get(error_code, f"UNKNOWN({error_code})")
        logger.warning(f"[SPEECH] Error: {error_name}")
        
        if self.on_error:
            schedule_once(lambda dt: self.on_error(error_code), 0)
        
        # Auto-restart if continuous (unless critical error)
        self._consecutive_errors += 1
        if self._continuous and self._should_listen:
            if error_code not in [3, 9]:  # Not AUDIO or PERMISSIONS
                if self._consecutive_errors < self._max_consecutive_errors:
                    delay = min(1.0, 0.2 * self._consecutive_errors)
                    schedule_once(lambda dt: self._start_internal(), delay)
                else:
                    logger.error("[SPEECH] Too many consecutive errors, stopping")
                    self._should_listen = False
    
    def _on_results(self, results):
        """Handle final recognition results"""
        try:
            key = SpeechRecognizer.RESULTS_RECOGNITION
            matches = results.getStringArrayList(key)
            
            if matches and matches.size() > 0:
                text = matches.get(0)
                logger.info(f"[SPEECH] Result: {text}")
                
                if self.on_result:
                    schedule_once(lambda dt, t=text: self.on_result(t), 0)
            
            # Restart if continuous
            if self._continuous and self._should_listen:
                schedule_once(lambda dt: self._start_internal(), 0.3)
                
        except Exception as e:
            logger.error(f"[SPEECH] Results error: {e}")
    
    def _on_partial(self, partial):
        """Handle partial results"""
        try:
            key = SpeechRecognizer.RESULTS_RECOGNITION
            matches = partial.getStringArrayList(key)
            
            if matches and matches.size() > 0:
                text = matches.get(0)
                if self.on_partial:
                    schedule_once(lambda dt, t=text: self.on_partial(t), 0)
        except:
            pass
    
    def _start_internal(self):
        """Internal start listening (must be on UI thread)"""
        if not self._recognizer or not self._activity:
            return
        
        if self._is_starting:
            return
        
        self._is_starting = True
        
        @run_on_ui_thread
        def _listen():
            try:
                # Cancel any pending operation
                self._recognizer.cancel()
                
                # Build recognition intent
                intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                intent.putExtra(
                    RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                    RecognizerIntent.LANGUAGE_MODEL_FREE_FORM
                )
                intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, self.language)
                intent.putExtra(RecognizerIntent.EXTRA_MAX_RESULTS, 3)
                intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, True)
                
                # Longer silence detection for natural speech
                intent.putExtra(
                    RecognizerIntent.EXTRA_SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS, 
                    2500
                )
                intent.putExtra(
                    RecognizerIntent.EXTRA_SPEECH_INPUT_POSSIBLY_COMPLETE_SILENCE_LENGTH_MILLIS,
                    2000
                )
                
                self._recognizer.startListening(intent)
                self._state = AudioEngineState.LISTENING
                self._is_starting = False
                logger.debug("[SPEECH] Listening started")
                
            except Exception as e:
                logger.error(f"[SPEECH] Start error: {e}")
                self._is_starting = False
        
        _listen()
    
    @property
    def is_ready(self) -> bool:
        self._ensure_initialized()
        return self._state in [AudioEngineState.READY, AudioEngineState.LISTENING]
    
    def start(self, continuous: bool = True):
        """
        Start listening for speech.
        
        Args:
            continuous: If True, automatically restart after each result
        """
        # Ensure initialized first (lazy init)
        self._ensure_initialized()
        
        if self._state != AudioEngineState.READY:
            logger.warning(f"[SPEECH] Cannot start - not ready (state: {self._state})")
            return False
        
        self._continuous = continuous
        self._should_listen = True
        self._consecutive_errors = 0
        self._start_internal()
        logger.info(f"[SPEECH] Started (continuous={continuous})")
    
    def stop(self):
        """Stop listening"""
        self._should_listen = False
        self._continuous = False
        
        if self._recognizer:
            @run_on_ui_thread
            def _stop():
                try:
                    self._recognizer.stopListening()
                    self._state = AudioEngineState.READY
                    logger.info("[SPEECH] Stopped")
                except Exception as e:
                    logger.error(f"[SPEECH] Stop error: {e}")
            _stop()
    
    def shutdown(self):
        """Shutdown recognizer"""
        self.stop()
        if self._recognizer:
            @run_on_ui_thread
            def _shutdown():
                try:
                    self._recognizer.cancel()
                    self._recognizer.destroy()
                    logger.info("[SPEECH] Shutdown complete")
                except Exception as e:
                    logger.error(f"[SPEECH] Shutdown error: {e}")
            _shutdown()


# ============================================================================
# UNIFIED AUDIO ENGINE (Owned by Runtime)
# ============================================================================

class AudioEngine:
    """
    Unified audio controller for Android.
    
    This class is owned by OfflineAIRuntime and provides coordinated
    control of TTS and Speech Recognition.
    
    NO direct interaction with AI core - all commands come from Runtime.
    """
    
    def __init__(self, language: str = "en-US"):
        self.language = language
        
        # Subsystems
        self.tts = AndroidTTSEngine(language)
        self.recognizer = AndroidSpeechEngine(language)
        
        # State tracking
        self._listening_active = False
        self._tts_active = False
        
        # Runtime callbacks
        self.on_speech_result: Optional[Callable[[str], None]] = None
        self.on_speaking_complete: Optional[Callable[[], None]] = None
        
        # Wire recognizer to forward to runtime
        self.recognizer.on_result = self._handle_speech_result
        self.recognizer.on_partial = self._handle_partial_result
        
        logger.info(f"[AUDIO_ENGINE] Initialized (Android={IS_ANDROID}, JNIUS={JNIUS_AVAILABLE})")
    
    @property
    def is_ready(self) -> bool:
        """Check if both subsystems are ready"""
        return self.tts.is_ready and self.recognizer.is_ready
    
    def capture_name_pcm(self, duration_seconds: float = 1.8,
                         sample_rate: int = 16000) -> bytes:
        """Capture genuine PCM16 from Android, without a second audio engine.

        Run on a worker thread only. Android AudioRecord's ByteBuffer
        overload avoids importing a nonexistent `jnius.jarray` helper.
        No audio files or text-derived acoustic signatures are created.
        """
        if not (IS_ANDROID and JNIUS_AVAILABLE):
            raise RuntimeError("Microphone capture requires Android audio support")
        if not 0.4 <= duration_seconds <= 3.0:
            raise ValueError("Enrollment recordings must be 0.4–3 seconds")
        self.stop_listening()
        from jnius import autoclass
        AudioRecord = autoclass("android.media.AudioRecord")
        AudioFormat = autoclass("android.media.AudioFormat")
        Source = autoclass("android.media.MediaRecorder$AudioSource")
        ByteBuffer = autoclass("java.nio.ByteBuffer")
        minimum = AudioRecord.getMinBufferSize(
            sample_rate, AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT)
        if minimum <= 0:
            raise RuntimeError("This microphone cannot capture 16-bit PCM at 16 kHz")
        chunk_size = max(int(minimum), 4096)
        if chunk_size % 2:
            chunk_size += 1
        recorder = AudioRecord(
            Source.MIC, sample_rate, AudioFormat.CHANNEL_IN_MONO,
            AudioFormat.ENCODING_PCM_16BIT, chunk_size * 2)
        if recorder.getState() != AudioRecord.STATE_INITIALIZED:
            recorder.release()
            raise RuntimeError("Microphone unavailable or audio permission denied")
        wanted = int(sample_rate * duration_seconds) * 2
        collected = bytearray()
        buffer = ByteBuffer.allocateDirect(chunk_size)
        try:
            recorder.startRecording()
            if recorder.getRecordingState() != AudioRecord.RECORDSTATE_RECORDING:
                raise RuntimeError("Android could not start the microphone")
            while len(collected) < wanted:
                remaining = wanted - len(collected)
                count = min(chunk_size, remaining)
                buffer.clear()
                # A direct ByteBuffer selects AudioRecord.read(ByteBuffer,int,int).
                # The ByteBuffer position is not advanced by Android's read.
                amount = int(recorder.read(buffer, count, AudioRecord.READ_BLOCKING))
                if amount <= 0:
                    raise RuntimeError(f"Microphone stopped while recording ({amount})")
                buffer.position(0)
                data = bytearray(amount)
                # PyJNIus copies mutated Java byte[] values into bytearray.
                buffer.get(data, 0, amount)
                collected.extend(data)
        finally:
            try:
                recorder.stop()
            except Exception:
                pass
            recorder.release()
        return bytes(collected)

    # ========================================================================
    # SPEECH RECOGNITION CONTROL (Called by Runtime only)
    # ========================================================================
    
    def start_listening(self, continuous: bool = True):
        """Start listening - ONLY Runtime calls this"""
        if not self.recognizer.is_ready:
            logger.error("[AUDIO_ENGINE] Cannot listen - recognizer not ready")
            return False
        
        self._listening_active = True
        self.recognizer.start(continuous=continuous)
        return True
    
    def stop_listening(self):
        """Stop listening - ONLY Runtime calls this"""
        self._listening_active = False
        self.recognizer.stop()
    
    def _handle_speech_result(self, text: str):
        """Forward speech result to Runtime"""
        if self.on_speech_result:
            self.on_speech_result(text)
    
    def _handle_partial_result(self, text: str):
        """Handle partial result (for wake word pre-detection)"""
        # Could implement early wake detection here
        pass
    
    # ========================================================================
    # TTS CONTROL (Called by Runtime only)
    # ========================================================================
    
    def speak(self, text: str, params: VoiceParams = None, 
              phoneme_cb: Callable = None, on_complete: Callable = None):
        """
        Speak text - ONLY Runtime calls this.
        Automatically pauses recognition while speaking.
        """
        # Pause listening while speaking
        was_listening = self._listening_active
        if was_listening:
            self.stop_listening()
        
        self._tts_active = True
        
        def _on_complete():
            self._tts_active = False
            if self.on_speaking_complete:
                self.on_speaking_complete()
            # Call user's callback
            if on_complete:
                on_complete()
            # Resume listening if needed
            if was_listening:
                schedule_once(lambda dt: self.start_listening(), 0.2)
        
        self.tts.speak(text, params, on_complete=_on_complete, phoneme_cb=phoneme_cb)
    
    def stop_speaking(self):
        """Stop current speech - ONLY Runtime calls this"""
        self.tts.stop()
        self._tts_active = False
    
    def is_speaking(self) -> bool:
        """Check if TTS is active"""
        return self._tts_active or self.tts.is_speaking()
    
    # ========================================================================
    # LIFECYCLE
    # ========================================================================
    
    def shutdown(self):
        """Shutdown all audio subsystems"""
        logger.info("[AUDIO_ENGINE] Shutting down...")
        self.stop_listening()
        self.stop_speaking()
        self.recognizer.shutdown()
        self.tts.shutdown()
        logger.info("[AUDIO_ENGINE] Shutdown complete")


# ============================================================================
# MOCK IMPLEMENTATION (for desktop testing)
# ============================================================================

class MockAudioEngine:
    """Mock audio engine for non-Android platforms"""
    
    def __init__(self, language: str = "en-US"):
        self.language = language
        self.on_speech_result = None
        self.on_speaking_complete = None
        self._listening = False
        logger.info("[AUDIO_ENGINE] Using MOCK engine (desktop mode)")
    
    @property
    def is_ready(self) -> bool:
        return True
    
    def start_listening(self, continuous: bool = True):
        self._listening = True
        logger.info("[AUDIO_ENGINE] MOCK: Started listening")
        return True
    
    def stop_listening(self):
        self._listening = False
        logger.info("[AUDIO_ENGINE] MOCK: Stopped listening")
    
    def speak(self, text: str, params=None, phoneme_cb=None, on_complete=None):
        logger.info(f"[AUDIO_ENGINE] MOCK: Would speak: {text[:50]}...")
        def _on_done():
            if self.on_speaking_complete:
                self.on_speaking_complete()
            if on_complete:
                on_complete()
        schedule_once(lambda dt: _on_done(), 0.5)
    
    def stop_speaking(self):
        pass
    
    def is_speaking(self) -> bool:
        return False
    
    def shutdown(self):
        logger.info("[AUDIO_ENGINE] MOCK: Shutdown")


# ============================================================================
# FACTORY
# ============================================================================

def create_audio_engine(language: str = "en-US"):
    """
    Create appropriate audio engine for platform.
    
    On Android: Native Android AudioEngine
    On Desktop: MockAudioEngine (for UI testing)
    """
    if IS_ANDROID and JNIUS_AVAILABLE:
        return AudioEngine(language)
    else:
        return MockAudioEngine(language)
