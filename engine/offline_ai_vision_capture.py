#!/usr/bin/env python3
"""
Offline AI Vision Capture - Android Camera Module
==================================================
Authors: Sunni (Sir) Morningstar & Cael Devo

Native Android Camera2 API integration for the Offline AI.
Provides:
- Camera preview and capture
- Face detection
- Image processing pipeline
- Integration with VisionManager

This module is owned by the Runtime and provides visual input
to the AI's vision system.
"""

import logging

from .agora_scheduling import schedule_once as _shared_schedule_once
import threading
import time
from typing import Callable, Optional, Dict, Any
from enum import Enum, auto
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Safe Kivy imports for Android startup
try:
    from kivy.clock import Clock
    from kivy.utils import platform
except ImportError:
    Clock = None
    platform = None

# ============================================================================
# PLATFORM DETECTION
# ============================================================================

IS_ANDROID = (platform == 'android') if platform else False

# Safe scheduling helper
def schedule_once(callback, delay=0):
    """Safely schedule a callback using Clock or threading fallback.

    Accepts both ``lambda: ...`` and Kivy-style ``lambda dt: ...``.
    """
    _shared_schedule_once(callback, delay)

if IS_ANDROID:
    try:
        from jnius import autoclass, PythonJavaClass, java_method, cast
        from android.runnable import run_on_ui_thread
        
        # Android Camera2 API
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        CameraManager = autoclass('android.hardware.camera2.CameraManager')
        CameraDevice = autoclass('android.hardware.camera2.CameraDevice')
        CameraCharacteristics = autoclass('android.hardware.camera2.CameraCharacteristics')
        CameraCaptureSession = autoclass('android.hardware.camera2.CameraCaptureSession')
        CaptureRequest = autoclass('android.hardware.camera2.CaptureRequest')
        ImageReader = autoclass('android.media.ImageReader')
        ImageFormat = autoclass('android.graphics.ImageFormat')
        Surface = autoclass('android.view.Surface')
        Size = autoclass('android.util.Size')
        
        # Face detection (may be unavailable on some devices/API levels)
        try:
            FaceDetector = autoclass('android.media.FaceDetector')
        except Exception as e:
            FaceDetector = None
            logger.warning(f"[VISION_CAPTURE] FaceDetector unavailable: {e}")
        

        # Image processing
        Bitmap = autoclass('android.graphics.Bitmap')
        BitmapFactory = autoclass('android.graphics.BitmapFactory')
        Matrix = autoclass('android.graphics.Matrix')
        
        JNIUS_AVAILABLE = True
        logger.info("[VISION_CAPTURE] Android Camera2 API available")
    except Exception as e:
        logger.exception(f"[VISION_CAPTURE] Android Camera2/JNI init failed: {e}")
        JNIUS_AVAILABLE = False
else:
    JNIUS_AVAILABLE = False


# ============================================================================
# ENUMERATIONS
# ============================================================================

class CameraState(Enum):
    """Camera operational states"""
    UNINITIALIZED = auto()
    INITIALIZING = auto()
    READY = auto()
    PREVIEW = auto()
    CAPTURING = auto()
    ERROR = auto()


class DetectionType(Enum):
    """Types of visual detection available"""
    FACE = "face"
    MOTION = "motion"
    OBJECT = "object"


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class FaceDetection:
    """Detected face data"""
    x: float  # Normalized 0-1
    y: float
    width: float
    height: float
    confidence: float
    has_smile: bool = False
    left_eye_open: bool = True
    right_eye_open: bool = True


@dataclass
class VisionFrame:
    """Processed vision frame"""
    timestamp: float
    width: int
    height: int
    faces: list
    motion_detected: bool
    dominant_color: tuple
    brightness: float


# ============================================================================
# ANDROID CAMERA IMPLEMENTATION
# ============================================================================

class AndroidCameraCapture:
    """
    Android Camera2 implementation.
    
    Handles camera lifecycle, preview, and capture.
    Works with the Runtime for coordinated access.
    """
    
    def __init__(self, facing: str = "front"):
        """
        Args:
            facing: "front" or "back" camera
        """
        self.facing = facing
        self.state = CameraState.UNINITIALIZED
        
        # Android objects
        self._camera_manager = None
        self._camera_id = None
        self._camera_device = None
        self._image_reader = None
        self._capture_session = None
        self._surface = None
        
        # Callbacks
        self.on_frame: Optional[Callable[[VisionFrame], None]] = None
        self.on_face_detected: Optional[Callable[[list], None]] = None
        
        # Frame processing
        self._last_frame_time = 0
        self._frame_interval = 1.0 / 15  # 15 FPS max
        self._frame_count = 0
        
        # Thread safety
        self._lock = threading.Lock()
        
        if IS_ANDROID and JNIUS_AVAILABLE:
            self._initialize()
        else:
            self.state = CameraState.ERROR
            logger.error("[CAMERA] Not available - not on Android or JNIUS missing")
    
    def _initialize(self):
        """Initialize camera manager and find camera"""
        try:
            self.state = CameraState.INITIALIZING
            
            activity = PythonActivity.mActivity
            self._camera_manager = activity.getSystemService('camera')
            
            # Find camera
            camera_ids = self._camera_manager.getCameraIdList()
            
            for cid in camera_ids:
                characteristics = self._camera_manager.getCameraCharacteristics(cid)
                facing_lens = characteristics.get(CameraCharacteristics.LENS_FACING)
                
                # LENS_FACING_FRONT = 0, LENS_FACING_BACK = 1
                if self.facing == "front" and facing_lens == 0:
                    self._camera_id = cid
                    break
                elif self.facing == "back" and facing_lens == 1:
                    self._camera_id = cid
                    break
            
            if not self._camera_id:
                # Fallback to first available
                self._camera_id = camera_ids[0] if len(camera_ids) > 0 else None
            
            if self._camera_id:
                logger.info(f"[CAMERA] Found camera: {self._camera_id}")
                self.state = CameraState.READY
            else:
                logger.error("[CAMERA] No camera found")
                self.state = CameraState.ERROR
                
        except Exception as e:
            logger.error(f"[CAMERA] Init error: {e}")
            self.state = CameraState.ERROR
    
    def start_preview(self, surface=None):
        """
        Start camera preview.
        
        Args:
            surface: Optional Surface to render preview to
        """
        if self.state not in [CameraState.READY, CameraState.PREVIEW]:
            logger.error(f"[CAMERA] Cannot start preview from state {self.state}")
            return False
        
        try:
            # Create image reader for frame capture
            self._image_reader = ImageReader.newInstance(
                640, 480,  # Resolution
                ImageFormat.YUV_420_888,
                2  # Max images
            )
            
            # Set up image available listener
            self._setup_image_listener()
            
            # Open camera
            handler = None  # Use main thread handler
            
            class StateCallback(PythonJavaClass):
                __javainterfaces__ = ['android/hardware/camera2/CameraDevice$StateCallback']
                __javacontext__ = 'app'
                
                def __init__(self, capture):
                    super().__init__()
                    self.capture = capture
                
                @java_method('(Landroid/hardware/camera2/CameraDevice;)V')
                def onOpened(self, camera):
                    self.capture._on_camera_opened(camera)
                
                @java_method('(Landroid/hardware/camera2/CameraDevice;)V')
                def onDisconnected(self, camera):
                    self.capture._on_camera_disconnected(camera)
                
                @java_method('(Landroid/hardware/camera2/CameraDevice;I)V')
                def onError(self, camera, error):
                    self.capture._on_camera_error(camera, error)
            
            callback = StateCallback(self)
            
            @run_on_ui_thread
            def _open():
                self._camera_manager.openCamera(self._camera_id, callback, handler)
            
            _open()
            
            self.state = CameraState.PREVIEW
            logger.info("[CAMERA] Preview starting...")
            return True
            
        except Exception as e:
            logger.error(f"[CAMERA] Start preview error: {e}")
            self.state = CameraState.ERROR
            return False
    
    def _setup_image_listener(self):
        """Set up image available listener"""
        camera = self
        
        class ImageListener(PythonJavaClass):
            __javainterfaces__ = ['android/media/ImageReader$OnImageAvailableListener']
            __javacontext__ = 'app'
            
            def __init__(self):
                super().__init__()
            
            @java_method('(Landroid/media/ImageReader;)V')
            def onImageAvailable(self, reader):
                camera._process_image(reader)
        
        listener = ImageListener()
        self._image_reader.setOnImageAvailableListener(listener, None)
    
    def _on_camera_opened(self, camera):
        """Called when camera is opened"""
        logger.info("[CAMERA] Device opened")
        self._camera_device = camera
        
        # Create capture session
        surfaces = [self._image_reader.getSurface()]
        
        class SessionCallback(PythonJavaClass):
            __javainterfaces__ = ['android/hardware/camera2/CameraCaptureSession$StateCallback']
            __javacontext__ = 'app'
            
            def __init__(self, capture):
                super().__init__()
                self.capture = capture
            
            @java_method('(Landroid/hardware/camera2/CameraCaptureSession;)V')
            def onConfigured(self, session):
                self.capture._on_session_configured(session)
            
            @java_method('(Landroid/hardware/camera2/CameraCaptureSession;)V')
            def onConfigureFailed(self, session):
                logger.error("[CAMERA] Session configuration failed")
        
        callback = SessionCallback(self)
        
        @run_on_ui_thread
        def _create_session():
            self._camera_device.createCaptureSession(surfaces, callback, None)
        
        _create_session()
    
    def _on_session_configured(self, session):
        """Called when capture session is ready"""
        logger.info("[CAMERA] Capture session ready")
        self._capture_session = session
        
        # Build capture request
        request_builder = self._camera_device.createCaptureRequest(CameraDevice.TEMPLATE_PREVIEW)
        request_builder.addTarget(self._image_reader.getSurface())
        
        # Set auto-focus
        request_builder.set(CaptureRequest.CONTROL_AF_MODE, 
                          CaptureRequest.CONTROL_AF_MODE_CONTINUOUS_PICTURE)
        
        # Start repeating capture
        @run_on_ui_thread
        def _start_capture():
            try:
                self._capture_session.setRepeatingRequest(
                    request_builder.build(),
                    None,  # No capture callback for now
                    None
                )
                logger.info("[CAMERA] Preview active")
            except Exception as e:
                logger.error(f"[CAMERA] Capture error: {e}")
        
        _start_capture()
    
    def _on_camera_disconnected(self, camera):
        """Handle camera disconnection"""
        logger.warning("[CAMERA] Disconnected")
        self.state = CameraState.ERROR
    
    def _on_camera_error(self, camera, error):
        """Handle camera error"""
        logger.error(f"[CAMERA] Error: {error}")
        self.state = CameraState.ERROR
    
    def _process_image(self, reader):
        """Process captured image"""
        now = time.time()
        if now - self._last_frame_time < self._frame_interval:
            return  # Throttle FPS
        
        self._last_frame_time = now
        self._frame_count += 1
        
        try:
            image = reader.acquireLatestImage()
            if not image:
                return
            
            # Get image data
            width = image.getWidth()
            height = image.getHeight()
            
            # Process planes (YUV format)
            # For now, simplified processing
            
            # Create vision frame
            frame = VisionFrame(
                timestamp=now,
                width=width,
                height=height,
                faces=[],  # Would run face detection here
                motion_detected=False,
                dominant_color=(0.5, 0.5, 0.5),
                brightness=0.5
            )
            
            # Notify callback
            if self.on_frame:
                schedule_once(lambda: self.on_frame(frame), 0)
            
            # Close image
            image.close()
            
        except Exception as e:
            logger.error(f"[CAMERA] Image processing error: {e}")
    
    def stop_preview(self):
        """Stop camera preview"""
        try:
            if self._capture_session:
                @run_on_ui_thread
                def _stop():
                    self._capture_session.stopRepeating()
                    self._capture_session.close()
                _stop()
                self._capture_session = None
            
            if self._camera_device:
                @run_on_ui_thread
                def _close():
                    self._camera_device.close()
                _close()
                self._camera_device = None
            
            if self._image_reader:
                self._image_reader.close()
                self._image_reader = None
            
            self.state = CameraState.READY
            logger.info("[CAMERA] Preview stopped")
            
        except Exception as e:
            logger.error(f"[CAMERA] Stop error: {e}")
    
    def capture_photo(self) -> Optional[bytes]:
        """
        Capture a single photo.
        Returns JPEG bytes or None.
        """
        # TODO: Implement still capture
        logger.info("[CAMERA] Photo capture not yet implemented")
        return None
    
    def get_status(self) -> Dict[str, Any]:
        """Get camera status"""
        return {
            "state": self.state.name,
            "facing": self.facing,
            "camera_id": self._camera_id,
            "frame_count": self._frame_count,
            "fps": 1.0 / self._frame_interval if self._frame_interval > 0 else 0
        }


# ============================================================================
# VISION PROCESSOR
# ============================================================================

class VisionProcessor:
    """
    Processes vision frames and extracts meaningful information.
    Integrates with the AI's VisionManager.
    """
    
    def __init__(self, vision_manager=None):
        self.vision_manager = vision_manager
        self.frame_history = []
        self.max_history = 30
        
        # Detection settings
        self.detect_faces = True
        self.detect_motion = True
        self.detect_brightness = True
        
        # Callbacks
        self.on_person_present: Optional[Callable[[bool], None]] = None
        self.on_attention_change: Optional[Callable[[bool], None]] = None
        
        # State tracking
        self._person_present = False
        self._attention_detected = False
    
    def process_frame(self, frame: VisionFrame):
        """Process a vision frame"""
        # Add to history
        self.frame_history.append(frame)
        if len(self.frame_history) > self.max_history:
            self.frame_history.pop(0)
        
        # Detect person presence
        person_now = len(frame.faces) > 0 or self._detect_person_heuristic(frame)
        if person_now != self._person_present:
            self._person_present = person_now
            if self.on_person_present:
                self.on_person_present(person_now)
        
        # Update vision manager if available
        if self.vision_manager:
            self._update_vision_manager(frame)
        
        # Log occasionally
        if len(self.frame_history) % 30 == 0:
            logger.debug(f"[VISION] Frame: {frame.width}x{frame.height}, "
                        f"faces={len(frame.faces)}, brightness={frame.brightness:.2f}")
    
    def _detect_person_heuristic(self, frame: VisionFrame) -> bool:
        """Heuristic detection of person presence without ML"""
        # Simple heuristic: motion + bright area
        if len(self.frame_history) < 2:
            return False
        
        prev = self.frame_history[-2]
        brightness_change = abs(frame.brightness - prev.brightness)
        
        # Significant brightness change might indicate presence
        return brightness_change > 0.2
    
    def _update_vision_manager(self, frame: VisionFrame):
        """Update the AI's vision manager with frame data"""
        try:
            # Create visual analysis dict
            analysis = {
                "faces_detected": len(frame.faces),
                "brightness": frame.brightness,
                "motion": frame.motion_detected,
                "timestamp": frame.timestamp
            }
            
            # Add face details
            if frame.faces:
                analysis["primary_face"] = {
                    "x": frame.faces[0].x,
                    "y": frame.faces[0].y,
                    "confidence": frame.faces[0].confidence
                }
            
            # Store in vision manager if it has the method
            if hasattr(self.vision_manager, 'add_frame_analysis'):
                self.vision_manager.add_frame_analysis(analysis)
                
        except Exception as e:
            logger.error(f"[VISION] Update error: {e}")
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of recent vision data"""
        if not self.frame_history:
            return {"status": "no_data"}
        
        recent = self.frame_history[-30:]
        
        return {
            "frames_processed": len(self.frame_history),
            "avg_brightness": sum(f.brightness for f in recent) / len(recent),
            "faces_detected": sum(len(f.faces) for f in recent),
            "person_present": self._person_present,
            "attention_detected": self._attention_detected
        }


# ============================================================================
# UNIFIED VISION CAPTURE (Owned by Runtime)
# ============================================================================

class VisionCapture:
    """
    Unified vision capture system.
    
    Combines camera capture and vision processing.
    Owned by Runtime, provides visual input to AI.
    """
    
    def __init__(self, facing: str = "front", vision_manager=None):
        self.camera = AndroidCameraCapture(facing)
        self.processor = VisionProcessor(vision_manager)
        
        # Wire camera to processor
        self.camera.on_frame = self.processor.process_frame
        
        # Runtime callbacks
        self.on_person_present = None
        self.on_face_detected = None
        
        # Wire processor to runtime
        self.processor.on_person_present = self._on_person_change
        
        self._active = False
        
        logger.info(f"[VISION_CAPTURE] Initialized (facing={facing})")
    
    def _on_person_change(self, present: bool):
        """Forward person detection to runtime"""
        if self.on_person_present:
            self.on_person_present(present)
    
    def start(self) -> bool:
        """Start vision capture"""
        if self._active:
            return True
        
        success = self.camera.start_preview()
        if success:
            self._active = True
            logger.info("[VISION_CAPTURE] Started")
        
        return success
    
    def stop(self):
        """Stop vision capture"""
        if not self._active:
            return
        
        self.camera.stop_preview()
        self._active = False
        logger.info("[VISION_CAPTURE] Stopped")
    
    def is_active(self) -> bool:
        """Check if vision capture is active"""
        return self._active and self.camera.state == CameraState.PREVIEW
    
    def get_summary(self) -> Dict[str, Any]:
        """Get vision summary for AI consumption"""
        return {
            "camera": self.camera.get_status(),
            "processing": self.processor.get_summary()
        }


# ============================================================================
# MOCK IMPLEMENTATION
# ============================================================================

class MockVisionCapture:
    """Mock vision capture for desktop testing"""
    
    def __init__(self, facing: str = "front", vision_manager=None):
        self.facing = facing
        self._active = False
        self.on_person_present = None
        self.on_face_detected = None
        logger.info("[VISION_CAPTURE] Using MOCK (desktop mode)")
    
    def start(self) -> bool:
        self._active = True
        logger.info("[VISION_CAPTURE] MOCK: Started")
        return True
    
    def stop(self):
        self._active = False
        logger.info("[VISION_CAPTURE] MOCK: Stopped")
    
    def is_active(self) -> bool:
        return self._active
    
    def get_summary(self) -> Dict[str, Any]:
        return {
            "camera": {"state": "MOCK"},
            "processing": {"status": "mock_data"}
        }


# ============================================================================
# FACTORY
# ============================================================================

def create_vision_capture(facing: str = "front", vision_manager=None):
    """
    Create appropriate vision capture for platform.
    
    On Android: Native Android Camera2
    On Desktop: Mock
    """
    if IS_ANDROID and JNIUS_AVAILABLE:
        return VisionCapture(facing, vision_manager)
    else:
        return MockVisionCapture(facing, vision_manager)
