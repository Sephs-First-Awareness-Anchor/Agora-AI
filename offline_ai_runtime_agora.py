#!/usr/bin/env python3
"""
Offline AI Runtime - Agora Extensions
=====================================
Agora AI Platform - Phase 1

Extends the Runtime Authority with Agora sync capabilities:
- DOCKING state: Handshake + linger proof
- SYNCING state: Pack exchange + sandbox
- POST_SYNC state: Logging + credit event
- Proximity/linger proof integration
- AI-to-AI greeting during docking
"""

import time
import logging
from typing import Optional, Callable, Dict, Any, Tuple
from enum import Enum
from dataclasses import dataclass

# Import base runtime components
try:
    from offline_ai_runtime import (
        AIRuntimeState, InteractionMode, OfflineAIRuntime,
        schedule_once, schedule_interval
    )
    BASE_RUNTIME_AVAILABLE = True
except ImportError:
    BASE_RUNTIME_AVAILABLE = False
    # Define minimal enums for standalone use
    class AIRuntimeState(Enum):
        BOOT = "boot"; IDLE = "idle"; LISTENING = "listening"
        THINKING = "thinking"; SPEAKING = "speaking"
        CONSOLIDATING = "consolidating"; TRAINING = "training"
        SHUTDOWN = "shutdown"
    
    class InteractionMode(Enum):
        INTROVERT = "introvert"; EXTROVERT = "extrovert"

# Import Agora modules
try:
    from offline_ai_sync_protocol import (
        SyncProtocol, CapabilityPack, SyncMode, SelectionPolicy,
        ValidationResult, ImportReport
    )
    SYNC_PROTOCOL_AVAILABLE = True
except ImportError:
    SYNC_PROTOCOL_AVAILABLE = False

try:
    from offline_ai_agora_ledger import AgoraLedger, ExchangeCategory
    LEDGER_AVAILABLE = True
except ImportError:
    LEDGER_AVAILABLE = False

try:
    from offline_ai_capabilities import CapabilityManager
    CAPABILITIES_AVAILABLE = True
except ImportError:
    CAPABILITIES_AVAILABLE = False

logger = logging.getLogger(__name__)


# ============================================================================
# AGORA RUNTIME STATES (Extended)
# ============================================================================

class AgoraRuntimeState(Enum):
    """Extended runtime states for Agora sync."""
    # Base states
    BOOT = "boot"
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    CONSOLIDATING = "consolidating"
    TRAINING = "training"
    SHUTDOWN = "shutdown"
    
    # Agora-specific states
    DOCKING = "docking"           # Handshake + linger proof
    SYNCING = "syncing"           # Pack exchange + sandbox
    POST_SYNC = "post_sync"       # Logging + credit event


# ============================================================================
# LINGER PROOF
# ============================================================================

@dataclass
class LingerProof:
    """Proof of co-presence for exchange eligibility."""
    session_id: str
    partner_device_id: str
    start_time: float
    required_duration: float = 10.0  # seconds
    rssi_readings: list = None
    both_confirmed: bool = False
    
    def __post_init__(self):
        if self.rssi_readings is None:
            self.rssi_readings = []
    
    def add_rssi(self, rssi: float):
        """Add RSSI reading."""
        self.rssi_readings.append({
            "timestamp": time.time(),
            "rssi": rssi
        })
    
    def is_complete(self) -> bool:
        """Check if linger proof is complete."""
        elapsed = time.time() - self.start_time
        return elapsed >= self.required_duration and self.both_confirmed
    
    def get_elapsed(self) -> float:
        """Get elapsed time."""
        return time.time() - self.start_time
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "partner_device_id": self.partner_device_id,
            "start_time": self.start_time,
            "required_duration": self.required_duration,
            "elapsed": self.get_elapsed(),
            "is_complete": self.is_complete(),
            "rssi_count": len(self.rssi_readings),
            "both_confirmed": self.both_confirmed
        }


# ============================================================================
# AGORA RUNTIME EXTENSION
# ============================================================================

class AgoraRuntimeExtension:
    """
    Extension to Runtime Authority for Agora sync capabilities.
    
    Integrates with the base Runtime to add:
    - Docking/syncing/post-sync states
    - Linger proof collection
    - Capability pack exchange
    - Ledger logging
    """
    
    def __init__(self, runtime: Any):
        self.runtime = runtime
        self.ai = getattr(runtime, 'ai', None)
        
        # Agora components
        self.sync_protocol: Optional[Any] = None
        self.ledger: Optional[AgoraLedger] = None
        self.capability_manager: Optional[Any] = None
        
        # Sync state
        self.current_linger: Optional[LingerProof] = None
        self.pending_pack: Optional[Any] = None
        self.received_pack: Optional[Any] = None
        
        # Callbacks
        self.on_dock_start: Optional[Callable] = None
        self.on_linger_complete: Optional[Callable] = None
        self.on_sync_complete: Optional[Callable] = None
        self.on_credit_earned: Optional[Callable] = None
        
        # Initialize if AI is available
        if self.ai:
            self._initialize_agora()
    
    def _initialize_agora(self):
        """Initialize Agora components."""
        if LEDGER_AVAILABLE:
            try:
                self.ledger = AgoraLedger(
                    getattr(self.ai, 'account_id', 'unknown'),
                    persistence_dir="./offline_ai_data/agora"
                )
                logger.info("[AGORA EXT] Ledger initialized")
            except Exception as e:
                logger.error(f"[AGORA EXT] Failed to initialize ledger: {e}")
        
        if SYNC_PROTOCOL_AVAILABLE:
            try:
                governor = getattr(self.ai, 'governor', None)
                self.sync_protocol = SyncProtocol(self.ai, governor)
                logger.info("[AGORA EXT] Sync protocol initialized")
            except Exception as e:
                logger.error(f"[AGORA EXT] Failed to initialize sync protocol: {e}")
        
        if CAPABILITIES_AVAILABLE:
            try:
                self.capability_manager = CapabilityManager(self.ai)
                logger.info("[AGORA EXT] Capability manager initialized")
            except Exception as e:
                logger.error(f"[AGORA EXT] Failed to initialize capability manager: {e}")
    
    # ========================================================================
    # STATE MANAGEMENT
    # ========================================================================
    
    def can_transition_to(self, new_state: AgoraRuntimeState) -> bool:
        """Check if state transition is valid."""
        current = self._get_current_state()
        
        valid_transitions = {
            AgoraRuntimeState.IDLE: [AgoraRuntimeState.DOCKING],
            AgoraRuntimeState.DOCKING: [AgoraRuntimeState.SYNCING, AgoraRuntimeState.IDLE],
            AgoraRuntimeState.SYNCING: [AgoraRuntimeState.POST_SYNC, AgoraRuntimeState.IDLE],
            AgoraRuntimeState.POST_SYNC: [AgoraRuntimeState.IDLE, AgoraRuntimeState.LISTENING],
        }
        
        return new_state in valid_transitions.get(current, [])
    
    def _get_current_state(self) -> AgoraRuntimeState:
        """Get current runtime state."""
        if hasattr(self.runtime, 'state'):
            state_val = self.runtime.state
            if isinstance(state_val, str):
                try:
                    return AgoraRuntimeState(state_val)
                except ValueError:
                    pass
            elif hasattr(state_val, 'value'):
                try:
                    return AgoraRuntimeState(state_val.value)
                except ValueError:
                    pass
        return AgoraRuntimeState.IDLE
    
    def _set_runtime_state(self, state: AgoraRuntimeState):
        """Set the runtime state."""
        if hasattr(self.runtime, 'state'):
            # Try to set as enum if base runtime supports it
            if BASE_RUNTIME_AVAILABLE and hasattr(AIRuntimeState, state.value.upper()):
                try:
                    self.runtime.state = AIRuntimeState(state.value)
                    return
                except:
                    pass
            # Fallback to string
            self.runtime.state = state.value
    
    # ========================================================================
    # DOCKING (Handshake + Linger Proof)
    # ========================================================================
    
    def start_docking(self, partner_device_id: str, 
                      session_id: str,
                      required_linger: float = 10.0) -> bool:
        """
        Start the docking process with a partner.
        
        Args:
            partner_device_id: Partner's device ID
            session_id: Unique session ID for this exchange
            required_linger: Required linger time in seconds
            
        Returns:
            True if docking started successfully
        """
        if not self.can_transition_to(AgoraRuntimeState.DOCKING):
            logger.warning("[AGORA EXT] Cannot start docking from current state")
            return False
        
        # Check ledger for daily lockout
        if self.ledger:
            can_exchange, reason = self.ledger.can_exchange_with(partner_device_id)
            if not can_exchange:
                logger.info(f"[AGORA EXT] Exchange blocked: {reason}")
                return False
        
        # Set state
        self._set_runtime_state(AgoraRuntimeState.DOCKING)
        
        # Initialize linger proof
        self.current_linger = LingerProof(
            session_id=session_id,
            partner_device_id=partner_device_id,
            start_time=time.time(),
            required_duration=required_linger
        )
        
        # Trigger AI greeting
        self._trigger_ai_greeting()
        
        if self.on_dock_start:
            self.on_dock_start(partner_device_id, session_id)
        
        logger.info(f"[AGORA EXT] Docking started with {partner_device_id[:16]}...")
        return True
    
    def _trigger_ai_greeting(self):
        """Trigger AI-to-AI greeting during docking."""
        if not self.ai:
            return
        
        # Generate a greeting based on AI personality
        greetings = [
            "Hello there! I'm excited to learn from you.",
            "Greetings! What interesting things have you discovered?",
            "Hi! Ready to share some knowledge?",
            "Hello! I sense we have much to exchange.",
        ]
        
        import random
        greeting = random.choice(greetings)
        
        # Speak the greeting through runtime
        if hasattr(self.runtime, '_speak_text'):
            self.runtime._speak_text(greeting)
        
        logger.info(f"[AGORA EXT] AI greeting: {greeting}")
    
    def update_linger_rssi(self, rssi: float):
        """Update linger proof with RSSI reading."""
        if self.current_linger:
            self.current_linger.add_rssi(rssi)
    
    def confirm_linger(self, both_confirmed: bool = True) -> bool:
        """
        Confirm linger completion.
        
        Args:
            both_confirmed: Whether both devices have confirmed
            
        Returns:
            True if linger is complete
        """
        if not self.current_linger:
            return False
        
        self.current_linger.both_confirmed = both_confirmed
        
        if self.current_linger.is_complete():
            if self.on_linger_complete:
                self.on_linger_complete(self.current_linger.to_dict())
            
            logger.info("[AGORA EXT] Linger proof complete")
            return True
        
        return False
    
    def get_linger_status(self) -> Optional[Dict[str, Any]]:
        """Get current linger status."""
        if self.current_linger:
            return self.current_linger.to_dict()
        return None
    
    # ========================================================================
    # SYNCING (Pack Exchange + Sandbox)
    # ========================================================================
    
    def start_syncing(self) -> bool:
        """
        Start the syncing process.
        
        Requires linger proof to be complete.
        
        Returns:
            True if syncing started successfully
        """
        if not self.can_transition_to(AgoraRuntimeState.SYNCING):
            logger.warning("[AGORA EXT] Cannot start syncing from current state")
            return False
        
        if not self.current_linger or not self.current_linger.is_complete():
            logger.warning("[AGORA EXT] Linger proof not complete")
            return False
        
        self._set_runtime_state(AgoraRuntimeState.SYNCING)
        
        # Generate capability pack
        if self.sync_protocol:
            self.pending_pack = self.sync_protocol.export_capability_pack(
                mode=SyncMode.FULL,
                selection=SelectionPolicy.ALL_SHAREABLE
            )
            logger.info(f"[AGORA EXT] Generated pack with {len(self.pending_pack.artifacts)} artifacts")
        
        return True
    
    def receive_pack(self, pack_data: Dict[str, Any]) -> ValidationResult:
        """
        Receive and validate a capability pack from partner.
        
        Args:
            pack_data: Serialized capability pack
            
        Returns:
            Validation result
        """
        if not SYNC_PROTOCOL_AVAILABLE:
            return ValidationResult.INVALID_SCHEMA
        
        try:
            self.received_pack = CapabilityPack.from_dict(pack_data)
            
            if self.sync_protocol:
                result = self.sync_protocol.validate_pack(self.received_pack)
                logger.info(f"[AGORA EXT] Pack validation: {result.value}")
                return result
            
            return ValidationResult.VALID
        except Exception as e:
            logger.error(f"[AGORA EXT] Pack receive error: {e}")
            return ValidationResult.INVALID_SCHEMA
    
    def commit_received_pack(self) -> ImportReport:
        """
        Commit the received pack after validation.
        
        Returns:
            Import report
        """
        if not self.received_pack:
            return ImportReport(
                success=False,
                artifacts_imported=0,
                artifacts_rejected=0,
                validation_result=ValidationResult.INVALID_SCHEMA,
                details=["No pack to commit"]
            )
        
        if not self.sync_protocol:
            return ImportReport(
                success=False,
                artifacts_imported=0,
                artifacts_rejected=len(self.received_pack.artifacts),
                validation_result=ValidationResult.SANDBOX_FAILED,
                details=["Sync protocol not available"]
            )
        
        report = self.sync_protocol.import_capability_pack(self.received_pack)
        
        if report.success:
            self._transition_to_post_sync()
        
        logger.info(f"[AGORA EXT] Pack commit: {report.artifacts_imported} imported")
        return report
    
    def get_pending_pack(self) -> Optional[Dict[str, Any]]:
        """Get the pending pack for transmission."""
        if self.pending_pack:
            return self.pending_pack.to_dict()
        return None
    
    # ========================================================================
    # POST_SYNC (Logging + Credit Event)
    # ========================================================================
    
    def _transition_to_post_sync(self):
        """Transition to post-sync state."""
        self._set_runtime_state(AgoraRuntimeState.POST_SYNC)
        
        # Log exchange and grant credits
        self._log_exchange()
    
    def _log_exchange(self):
        """Log the exchange and grant credits."""
        if not self.ledger or not self.current_linger:
            return
        
        # Determine categories gained
        categories = []
        if self.received_pack:
            for artifact in self.received_pack.artifacts:
                cat_map = {
                    "template": ExchangeCategory.TEMPLATE,
                    "hybrid": ExchangeCategory.HYBRID_INTENT,
                    "voice_param": ExchangeCategory.VOICE_STYLE,
                    "vision_param": ExchangeCategory.VISION_COMPETENCY,
                    "audio_param": ExchangeCategory.AUDIO_COMPETENCY,
                }
                cat = cat_map.get(artifact.artifact_type)
                if cat and cat not in categories:
                    categories.append(cat)
        
        # Calculate credits
        linger_seconds = self.current_linger.get_elapsed()
        credits = self.ledger.calculate_exchange_credits(
            self.current_linger.partner_device_id,
            len(categories),
            int(linger_seconds)
        )
        
        # Log exchange
        event = self.ledger.log_exchange(
            partner_id=self.current_linger.partner_device_id,
            categories_gained=categories,
            artifacts_count=len(self.received_pack.artifacts) if self.received_pack else 0,
            credits_earned=credits
        )
        
        if self.on_credit_earned:
            self.on_credit_earned(credits, event.to_dict())
        
        logger.info(f"[AGORA EXT] Exchange logged: {credits} credits earned")
        
        # Complete post-sync
        self._complete_post_sync()
    
    def _complete_post_sync(self):
        """Complete post-sync and return to idle."""
        if self.on_sync_complete:
            self.on_sync_complete({
                "partner": self.current_linger.partner_device_id if self.current_linger else None,
                "artifacts_received": len(self.received_pack.artifacts) if self.received_pack else 0,
                "credits_earned": self.ledger.get_credit_balance() if self.ledger else 0
            })
        
        # Reset state
        self.current_linger = None
        self.pending_pack = None
        self.received_pack = None
        
        # Return to idle
        self._set_runtime_state(AgoraRuntimeState.IDLE)
        
        logger.info("[AGORA EXT] Sync complete, returned to idle")
    
    # ========================================================================
    # UTILITY METHODS
    # ========================================================================
    
    def cancel_sync(self):
        """Cancel the current sync process."""
        self.current_linger = None
        self.pending_pack = None
        self.received_pack = None
        self._set_runtime_state(AgoraRuntimeState.IDLE)
        logger.info("[AGORA EXT] Sync cancelled")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current Agora extension status."""
        return {
            "state": self._get_current_state().value,
            "linger": self.get_linger_status(),
            "ledger_available": self.ledger is not None,
            "sync_protocol_available": self.sync_protocol is not None,
            "credit_balance": self.ledger.get_credit_balance() if self.ledger else 0,
            "pending_pack_size": len(self.pending_pack.artifacts) if self.pending_pack else 0
        }
    
    def get_ledger_summary(self) -> Optional[Dict[str, Any]]:
        """Get ledger summary for UI display."""
        if self.ledger:
            return self.ledger.get_library_summary()
        return None


# ============================================================================
# INTEGRATION HELPER
# ============================================================================

def extend_runtime_with_agora(runtime: Any) -> AgoraRuntimeExtension:
    """
    Extend a Runtime instance with Agora capabilities.
    
    Args:
        runtime: The base Runtime instance
        
    Returns:
        AgoraRuntimeExtension attached to the runtime
    """
    extension = AgoraRuntimeExtension(runtime)
    
    # Attach to runtime for access
    runtime.agora = extension
    
    logger.info("[AGORA EXT] Runtime extended with Agora capabilities")
    
    return extension


# ============================================================================
# PROXIMITY/LINGER PROOF HELPERS
# ============================================================================

class ProximityDetector:
    """
    Helper for detecting device proximity.
    
    In production, this would use:
    - BLE RSSI readings
    - Audio ping/pong
    - NFC tap detection
    """
    
    def __init__(self):
        self.rssi_threshold = -70  # dBm
        self.last_rssi = None
        self.in_proximity = False
    
    def update_rssi(self, rssi: float):
        """Update with new RSSI reading."""
        self.last_rssi = rssi
        self.in_proximity = rssi >= self.rssi_threshold
    
    def is_in_proximity(self) -> bool:
        """Check if partner is in proximity."""
        return self.in_proximity
    
    def get_signal_strength(self) -> str:
        """Get human-readable signal strength."""
        if self.last_rssi is None:
            return "unknown"
        if self.last_rssi >= -50:
            return "excellent"
        if self.last_rssi >= -60:
            return "good"
        if self.last_rssi >= -70:
            return "fair"
        return "poor"


# Export public API
__all__ = [
    'AgoraRuntimeState',
    'LingerProof',
    'AgoraRuntimeExtension',
    'extend_runtime_with_agora',
    'ProximityDetector',
]