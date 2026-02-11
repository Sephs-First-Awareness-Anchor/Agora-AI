#!/usr/bin/env python3
"""
Offline AI Sync Protocol
========================
Agora AI Platform - Phase 1

Defines the protocol for exchanging capability packs between devices.
Ensures privacy by only syncing non-personal capability growth artifacts.

Components:
- CapabilityPack: The container for shareable artifacts
- SyncProtocol: Build, validate, sandbox, and commit packs
- Sanitizer: Remove personal data from packs
- Origin tracking: Enforce transfer rules for purchased content
"""

import json
import hashlib
import time
import logging
import re
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMERATIONS
# ============================================================================

class PackOrigin(Enum):
    """Origin type for capability artifacts."""
    SOCIAL = "social"           # From peer exchange
    CLASS = "class"             # From unlocked training class
    PURCHASED = "purchased"     # Direct purchase (non-transferable)
    SYSTEM = "system"           # Built-in/default
    EMERGENT = "emergent"       # Emerged from learning (can transfer)


class SyncMode(Enum):
    """Mode for capability sync."""
    FULL = "full"               # Full capability exchange
    DELTA = "delta"             # Only changed capabilities
    SELECTIVE = "selective"     # User-selected capabilities


class SelectionPolicy(Enum):
    """Policy for selecting what to sync."""
    ALL_SHAREABLE = "all_shareable"
    HIGH_CONFIDENCE_ONLY = "high_confidence_only"
    TEMPLATES_ONLY = "templates_only"
    HYBRIDS_ONLY = "hybrids_only"


class ValidationResult(Enum):
    """Result of pack validation."""
    VALID = "valid"
    INVALID_SCHEMA = "invalid_schema"
    SIZE_EXCEEDED = "size_exceeded"
    FORBIDDEN_CONTENT = "forbidden_content"
    SIGNATURE_FAILED = "signature_failed"
    SANDBOX_FAILED = "sandbox_failed"
    GOVERNOR_VIOLATION = "governor_violation"


class SyncState(Enum):
    """State of a sync session."""
    PENDING = "pending"
    DOCKING = "docking"
    LINGERING = "lingering"
    EXCHANGING = "exchanging"
    VALIDATING = "validating"
    SANDBOXING = "sandboxing"
    COMMITTING = "committing"
    COMPLETED = "completed"
    FAILED = "failed"


# ============================================================================
# CAPABILITY PACK
# ============================================================================

@dataclass
class CapabilityArtifact:
    """Single artifact within a capability pack."""
    artifact_id: str
    artifact_type: str  # "template", "hybrid", "voice_param", "vision_param", "audio_param"
    origin: PackOrigin
    transferable: bool
    content: Dict[str, Any]
    confidence: float = 0.5
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_type": self.artifact_type,
            "origin": self.origin.value,
            "transferable": self.transferable,
            "content": self.content,
            "confidence": self.confidence,
            "created_at": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CapabilityArtifact':
        return cls(
            artifact_id=data["artifact_id"],
            artifact_type=data["artifact_type"],
            origin=PackOrigin(data.get("origin", "emergent")),
            transferable=data.get("transferable", True),
            content=data.get("content", {}),
            confidence=data.get("confidence", 0.5),
            created_at=data.get("created_at", time.time())
        )


@dataclass
class CapabilityPack:
    """
    Complete capability pack for device-to-device exchange.
    
    Structure:
    - manifest.json: Schema version, module hashes, sender public key ID
    - payload.bin: Shareable structures (artifacts)
    - policy.json: What the pack claims it contains + limits
    - signature.sig: Cryptographic signature
    """
    # Manifest
    schema_version: str = "1.0"
    sender_device_id: str = ""
    sender_account_id: str = ""
    sender_fingerprint: str = ""
    timestamp: float = field(default_factory=time.time)
    
    # Payload
    artifacts: List[CapabilityArtifact] = field(default_factory=list)
    
    # Policy
    max_size_bytes: int = 25 * 1024 * 1024  # 25MB max
    allowed_types: List[str] = field(default_factory=lambda: [
        "template", "hybrid", "voice_param", "vision_param", "audio_param",
        "registry_improvement"
    ])
    forbidden_patterns: List[str] = field(default_factory=lambda: [
        "memory_content", "transcript", "chat_log", "user_identifier",
        "face_vector", "face_embedding", "voice_fingerprint", "biometric"
    ])
    
    # Signature (simplified - in production, use proper crypto)
    signature: str = ""
    
    def compute_hash(self) -> str:
        """Compute content hash for signing."""
        data = {
            "schema_version": self.schema_version,
            "sender_device_id": self.sender_device_id,
            "timestamp": self.timestamp,
            "artifact_count": len(self.artifacts),
            "artifact_hashes": [self._hash_artifact(a) for a in self.artifacts]
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    
    def _hash_artifact(self, artifact: CapabilityArtifact) -> str:
        """Hash a single artifact."""
        return hashlib.sha256(
            json.dumps(artifact.to_dict(), sort_keys=True).encode()
        ).hexdigest()[:16]
    
    def get_size(self) -> int:
        """Get approximate size in bytes."""
        return len(json.dumps(self.to_dict()).encode())
    
    def sign(self, private_key_id: str = "device_key"):
        """Sign the pack (simplified)."""
        content_hash = self.compute_hash()
        self.signature = f"{private_key_id}:{content_hash[:32]}"
    
    def verify_signature(self) -> bool:
        """Verify pack signature (simplified)."""
        if not self.signature or ":" not in self.signature:
            return False
        # In production: verify against public key
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest": {
                "schema_version": self.schema_version,
                "sender_device_id": self.sender_device_id,
                "sender_account_id": self.sender_account_id,
                "sender_fingerprint": self.sender_fingerprint,
                "timestamp": self.timestamp,
                "pack_hash": self.compute_hash()
            },
            "payload": {
                "artifacts": [a.to_dict() for a in self.artifacts]
            },
            "policy": {
                "max_size_bytes": self.max_size_bytes,
                "allowed_types": self.allowed_types,
                "forbidden_patterns": self.forbidden_patterns
            },
            "signature": self.signature
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CapabilityPack':
        manifest = data.get("manifest", {})
        payload = data.get("payload", {})
        policy = data.get("policy", {})
        
        pack = cls(
            schema_version=manifest.get("schema_version", "1.0"),
            sender_device_id=manifest.get("sender_device_id", ""),
            sender_account_id=manifest.get("sender_account_id", ""),
            sender_fingerprint=manifest.get("sender_fingerprint", ""),
            timestamp=manifest.get("timestamp", time.time()),
            max_size_bytes=policy.get("max_size_bytes", 25 * 1024 * 1024),
            allowed_types=policy.get("allowed_types", []),
            forbidden_patterns=policy.get("forbidden_patterns", []),
            signature=data.get("signature", "")
        )
        
        for artifact_data in payload.get("artifacts", []):
            pack.artifacts.append(CapabilityArtifact.from_dict(artifact_data))
        
        return pack


# ============================================================================
# SANITIZER
# ============================================================================

class PackSanitizer:
    """
    Removes personal data from capability packs.
    Ensures no private information leaks through sync.
    """
    
    # Patterns that might indicate personal information
    PII_PATTERNS = [
        r'\b[A-Z][a-z]+\s[A-Z][a-z]+\b',  # Full names
        r'\b\d{3}-\d{3}-\d{4}\b',  # Phone numbers
        r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Emails
        r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b',  # IP addresses
    ]
    
    # Words that might be personal identifiers
    SENSITIVE_WORDS = {
        "name", "address", "phone", "email", "password", "ssn",
        "social", "birthday", "birthdate", "location", "home", "work"
    }
    
    @classmethod
    def sanitize_artifact(cls, artifact: CapabilityArtifact) -> CapabilityArtifact:
        """Sanitize a single artifact."""
        content = artifact.content.copy()
        
        # Remove any text fields that might contain PII
        content = cls._sanitize_dict(content)
        
        # Create sanitized artifact
        return CapabilityArtifact(
            artifact_id=artifact.artifact_id,
            artifact_type=artifact.artifact_type,
            origin=artifact.origin,
            transferable=artifact.transferable,
            content=content,
            confidence=artifact.confidence,
            created_at=artifact.created_at
        )
    
    @classmethod
    def _sanitize_dict(cls, data: Any) -> Any:
        """Recursively sanitize dictionary content."""
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                # Skip keys that might contain sensitive info
                if any(sw in key.lower() for sw in cls.SENSITIVE_WORDS):
                    continue
                result[key] = cls._sanitize_dict(value)
            return result
        elif isinstance(data, list):
            return [cls._sanitize_dict(item) for item in data]
        elif isinstance(data, str):
            return cls._sanitize_string(data)
        else:
            return data
    
    @classmethod
    def _sanitize_string(cls, text: str) -> str:
        """Sanitize a string by removing PII patterns."""
        for pattern in cls.PII_PATTERNS:
            text = re.sub(pattern, "[REDACTED]", text)
        return text
    
    @classmethod
    def redact_sensitive_tokens(cls, text: str) -> str:
        """Redact potentially sensitive tokens from text."""
        words = text.split()
        redacted = []
        for word in words:
            lower_word = word.lower().strip(".,!?;:")
            if lower_word in cls.SENSITIVE_WORDS:
                redacted.append("[REDACTED]")
            else:
                redacted.append(word)
        return " ".join(redacted)


# ============================================================================
# SYNC PROTOCOL
# ============================================================================

@dataclass
class ImportReport:
    """Report from importing a capability pack."""
    success: bool
    artifacts_imported: int
    artifacts_rejected: int
    validation_result: ValidationResult
    details: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "artifacts_imported": self.artifacts_imported,
            "artifacts_rejected": self.artifacts_rejected,
            "validation_result": self.validation_result.value,
            "details": self.details
        }


@dataclass
class SandboxResult:
    """Result of sandbox testing."""
    passed: bool
    tests_run: int
    tests_passed: int
    failures: List[str] = field(default_factory=list)


class SyncProtocol:
    """
    Core protocol for capability pack exchange.
    
    Responsibilities:
    - Build capability packs from AI state
    - Validate incoming packs
    - Sandbox test before commit
    - Commit valid packs to AI
    - Enforce "no private data" boundary
    """
    
    def __init__(self, ai_instance: Any, governor: Any = None):
        self.ai = ai_instance
        self.governor = governor
        self.sanitizer = PackSanitizer()
        self._session_state: SyncState = SyncState.PENDING
        self._session_log: List[str] = []
        
    def export_capability_pack(self, 
                               mode: SyncMode = SyncMode.FULL,
                               selection: SelectionPolicy = SelectionPolicy.ALL_SHAREABLE) -> CapabilityPack:
        """
        Build a capability pack from current AI state.
        
        Args:
            mode: Full, delta, or selective sync
            selection: Policy for selecting artifacts
            
        Returns:
            CapabilityPack ready for exchange
        """
        pack = CapabilityPack(
            sender_device_id=getattr(self.ai, 'device_id', 'unknown'),
            sender_account_id=getattr(self.ai, 'account_id', 'unknown'),
            sender_fingerprint=self._get_ai_fingerprint()
        )
        
        # Extract artifacts based on selection policy
        if selection in [SelectionPolicy.ALL_SHAREABLE, SelectionPolicy.TEMPLATES_ONLY]:
            templates = self._extract_templates()
            pack.artifacts.extend(templates)
        
        if selection in [SelectionPolicy.ALL_SHAREABLE, SelectionPolicy.HYBRIDS_ONLY]:
            hybrids = self._extract_hybrids()
            pack.artifacts.extend(hybrids)
        
        if selection == SelectionPolicy.ALL_SHAREABLE:
            voice_params = self._extract_voice_params()
            pack.artifacts.extend(voice_params)
            
            vision_params = self._extract_vision_params()
            pack.artifacts.extend(vision_params)
            
            audio_params = self._extract_audio_params()
            pack.artifacts.extend(audio_params)
        
        # Filter by confidence if requested
        if selection == SelectionPolicy.HIGH_CONFIDENCE_ONLY:
            pack.artifacts = [a for a in pack.artifacts if a.confidence >= 0.7]
        
        # Sanitize all artifacts
        pack.artifacts = [self.sanitizer.sanitize_artifact(a) for a in pack.artifacts]
        
        # Filter non-transferable artifacts
        pack.artifacts = [a for a in pack.artifacts if a.transferable]
        
        # Sign the pack
        pack.sign()
        
        self._log(f"Exported pack with {len(pack.artifacts)} artifacts")
        return pack
    
    def import_capability_pack(self, pack: CapabilityPack) -> ImportReport:
        """
        Import a capability pack into the AI.
        
        Args:
            pack: The capability pack to import
            
        Returns:
            ImportReport with results
        """
        # Step 1: Validate
        validation = self.validate_pack(pack)
        if validation != ValidationResult.VALID:
            return ImportReport(
                success=False,
                artifacts_imported=0,
                artifacts_rejected=len(pack.artifacts),
                validation_result=validation,
                details=[f"Validation failed: {validation.value}"]
            )
        
        # Step 2: Sandbox
        sandbox = self.sandbox_apply(pack)
        if not sandbox.passed:
            return ImportReport(
                success=False,
                artifacts_imported=0,
                artifacts_rejected=len(pack.artifacts),
                validation_result=ValidationResult.SANDBOX_FAILED,
                details=sandbox.failures
            )
        
        # Step 3: Commit
        commit = self.commit(pack)
        
        return ImportReport(
            success=commit,
            artifacts_imported=len(pack.artifacts),
            artifacts_rejected=0,
            validation_result=ValidationResult.VALID,
            details=["Successfully imported pack"]
        )
    
    def validate_pack(self, pack: CapabilityPack) -> ValidationResult:
        """
        Validate a capability pack.
        
        Checks:
        - Schema version compatibility
        - Size limits
        - No forbidden content
        - Signature validity
        """
        # Check schema version
        if pack.schema_version != "1.0":
            return ValidationResult.INVALID_SCHEMA
        
        # Check size
        if pack.get_size() > pack.max_size_bytes:
            return ValidationResult.SIZE_EXCEEDED
        
        # Check for forbidden content
        for artifact in pack.artifacts:
            # Check artifact type
            if artifact.artifact_type not in pack.allowed_types:
                return ValidationResult.FORBIDDEN_CONTENT
            
            # Check content for forbidden patterns
            content_str = json.dumps(artifact.content).lower()
            for pattern in pack.forbidden_patterns:
                if pattern in content_str:
                    return ValidationResult.FORBIDDEN_CONTENT
        
        # Verify signature
        if not pack.verify_signature():
            return ValidationResult.SIGNATURE_FAILED
        
        return ValidationResult.VALID
    
    def sandbox_apply(self, pack: CapabilityPack) -> SandboxResult:
        """
        Test pack application in sandbox.
        
        Tests:
        - Governor caps not exceeded
        - No trait conflicts
        - Safe to apply
        """
        tests_run = 0
        tests_passed = 0
        failures = []
        
        for artifact in pack.artifacts:
            tests_run += 1
            
            # Test governor compliance
            if self.governor and hasattr(self.governor, 'personalized_params'):
                params = self.governor.personalized_params.parameters
                
                # Check if artifact would exceed caps
                if artifact.artifact_type == "voice_param":
                    current_pitch = params.get("voice_gnome", {}).get("pitch", 0.5)
                    new_pitch = artifact.content.get("pitch", current_pitch)
                    if abs(new_pitch - current_pitch) > 0.05:  # Session cap
                        failures.append(f"Voice pitch delta too large: {abs(new_pitch - current_pitch)}")
                        continue
            
            tests_passed += 1
        
        return SandboxResult(
            passed=tests_passed == tests_run,
            tests_run=tests_run,
            tests_passed=tests_passed,
            failures=failures
        )
    
    def commit(self, pack: CapabilityPack) -> bool:
        """
        Commit a validated pack to the AI.
        
        Applies artifacts to appropriate subsystems.
        """
        try:
            for artifact in pack.artifacts:
                self._apply_artifact(artifact)
            
            self._log(f"Committed {len(pack.artifacts)} artifacts")
            return True
        except Exception as e:
            self._log(f"Commit failed: {e}")
            return False
    
    def _apply_artifact(self, artifact: CapabilityArtifact):
        """Apply a single artifact to the AI."""
        if artifact.artifact_type == "template":
            self._apply_template(artifact)
        elif artifact.artifact_type == "hybrid":
            self._apply_hybrid(artifact)
        elif artifact.artifact_type == "voice_param":
            self._apply_voice_param(artifact)
        elif artifact.artifact_type == "vision_param":
            self._apply_vision_param(artifact)
        elif artifact.artifact_type == "audio_param":
            self._apply_audio_param(artifact)
    
    def _apply_template(self, artifact: CapabilityArtifact):
        """Apply a template artifact."""
        if hasattr(self.ai, 'language') and self.ai.language:
            if hasattr(self.ai.language, 'intent_evolution'):
                evo = self.ai.language.intent_evolution
                if hasattr(evo, 'evo') and hasattr(evo.evo.template_learner, 'templates'):
                    modality = artifact.content.get("modality", "language")
                    category = artifact.content.get("category", "general")
                    template = artifact.content.get("template", "")
                    
                    if template:
                        if modality not in evo.evo.template_learner.templates:
                            evo.evo.template_learner.templates[modality] = {}
                        if category not in evo.evo.template_learner.templates[modality]:
                            evo.evo.template_learner.templates[modality][category] = []
                        
                        if template not in evo.evo.template_learner.templates[modality][category]:
                            evo.evo.template_learner.templates[modality][category].append(template)
    
    def _apply_hybrid(self, artifact: CapabilityArtifact):
        """Apply a hybrid intent artifact."""
        if hasattr(self.ai, 'language') and self.ai.language:
            if hasattr(self.ai.language, 'intent_evolution'):
                evo = self.ai.language.intent_evolution
                if hasattr(evo, 'evo') and hasattr(evo.evo.evolution_registry, 'hybrids'):
                    hybrid_name = artifact.content.get("hybrid_name", "")
                    components = artifact.content.get("components", [])
                    
                    if hybrid_name and len(components) == 2:
                        evo.evo.evolution_registry.hybrids[hybrid_name] = tuple(components)
    
    def _apply_voice_param(self, artifact: CapabilityArtifact):
        """Apply voice parameter artifact."""
        if hasattr(self.ai, 'governor') and self.ai.governor:
            params = self.ai.governor.get_personalized_parameters()
            voice_gnome = params.get("voice_gnome", {})
            
            for key, value in artifact.content.items():
                if key in ["pitch", "rate", "warmth", "prosody", "salience", "hesitation"]:
                    voice_gnome[key] = value
    
    def _apply_vision_param(self, artifact: CapabilityArtifact):
        """Apply vision parameter artifact."""
        if hasattr(self.ai, 'vision') and self.ai.vision:
            for key, value in artifact.content.items():
                if hasattr(self.ai.vision, key):
                    setattr(self.ai.vision, key, value)
    
    def _apply_audio_param(self, artifact: CapabilityArtifact):
        """Apply audio parameter artifact."""
        if hasattr(self.ai, 'audio') and self.ai.audio:
            for key, value in artifact.content.items():
                if hasattr(self.ai.audio, key):
                    setattr(self.ai.audio, key, value)
    
    def _extract_templates(self) -> List[CapabilityArtifact]:
        """Extract templates from AI."""
        artifacts = []
        
        if hasattr(self.ai, 'language') and self.ai.language:
            if hasattr(self.ai.language, 'intent_evolution'):
                evo = self.ai.language.intent_evolution
                if hasattr(evo, 'evo') and hasattr(evo.evo.template_learner, 'templates'):
                    for modality, categories in evo.evo.template_learner.templates.items():
                        for category, templates in categories.items():
                            for template in templates:
                                artifact = CapabilityArtifact(
                                    artifact_id=f"template_{modality}_{category}_{hash(template) % 10000}",
                                    artifact_type="template",
                                    origin=PackOrigin.EMERGENT,
                                    transferable=True,
                                    content={
                                        "modality": modality,
                                        "category": category,
                                        "template": template
                                    },
                                    confidence=0.7
                                )
                                artifacts.append(artifact)
        
        return artifacts
    
    def _extract_hybrids(self) -> List[CapabilityArtifact]:
        """Extract hybrid intents from AI."""
        artifacts = []
        
        if hasattr(self.ai, 'language') and self.ai.language:
            if hasattr(self.ai.language, 'intent_evolution'):
                evo = self.ai.language.intent_evolution
                if hasattr(evo, 'evo') and hasattr(evo.evo.evolution_registry, 'hybrids'):
                    for hybrid_name, components in evo.evo.evolution_registry.hybrids.items():
                        artifact = CapabilityArtifact(
                            artifact_id=f"hybrid_{hybrid_name}",
                            artifact_type="hybrid",
                            origin=PackOrigin.EMERGENT,
                            transferable=True,
                            content={
                                "hybrid_name": hybrid_name,
                                "components": list(components)
                            },
                            confidence=0.8
                        )
                        artifacts.append(artifact)
        
        return artifacts
    
    def _extract_voice_params(self) -> List[CapabilityArtifact]:
        """Extract voice parameters from AI."""
        artifacts = []
        
        if hasattr(self.ai, 'governor') and self.ai.governor:
            params = self.ai.governor.get_personalized_parameters()
            voice_gnome = params.get("voice_gnome", {})
            
            # Only extract non-biometric style parameters
            safe_params = {
                k: v for k, v in voice_gnome.items()
                if k in ["pitch", "rate", "warmth", "prosody", "salience", "hesitation"]
            }
            
            if safe_params:
                artifact = CapabilityArtifact(
                    artifact_id=f"voice_params_{int(time.time())}",
                    artifact_type="voice_param",
                    origin=PackOrigin.EMERGENT,
                    transferable=True,
                    content=safe_params,
                    confidence=0.6
                )
                artifacts.append(artifact)
        
        return artifacts
    
    def _extract_vision_params(self) -> List[CapabilityArtifact]:
        """Extract vision parameters from AI."""
        artifacts = []
        
        if hasattr(self.ai, 'vision') and self.ai.vision:
            safe_params = {
                "focus": getattr(self.ai.vision, 'focus', 0.5),
                "motion_sensitivity": getattr(self.ai.vision, 'motion_sensitivity', 0.5),
                "recognition_threshold": getattr(self.ai.vision, 'recognition_threshold', 0.5),
                "detail_orientation": getattr(self.ai.vision, 'detail_orientation', 0.5),
            }
            
            artifact = CapabilityArtifact(
                artifact_id=f"vision_params_{int(time.time())}",
                artifact_type="vision_param",
                origin=PackOrigin.EMERGENT,
                transferable=True,
                content=safe_params,
                confidence=0.6
            )
            artifacts.append(artifact)
        
        return artifacts
    
    def _extract_audio_params(self) -> List[CapabilityArtifact]:
        """Extract audio parameters from AI."""
        artifacts = []
        
        if hasattr(self.ai, 'audio') and self.ai.audio:
            safe_params = {
                "sensitivity": getattr(self.ai.audio, 'sensitivity', 0.5),
                "voice_isolation": getattr(self.ai.audio, 'voice_isolation', 0.6),
                "emotion_detection": getattr(self.ai.audio, 'emotion_detection', 0.5),
            }
            
            artifact = CapabilityArtifact(
                artifact_id=f"audio_params_{int(time.time())}",
                artifact_type="audio_param",
                origin=PackOrigin.EMERGENT,
                transferable=True,
                content=safe_params,
                confidence=0.6
            )
            artifacts.append(artifact)
        
        return artifacts
    
    def _get_ai_fingerprint(self) -> str:
        """Get AI capability fingerprint."""
        # Import here to avoid circular dependency
        try:
            from .offline_ai_capabilities import CapabilityManager
            manager = CapabilityManager(self.ai)
            manifest = manager.generate_manifest()
            return manifest.compute_fingerprint()
        except Exception as e:
            logger.warning(f"Could not generate fingerprint: {e}")
            return "unknown"
    
    def _log(self, message: str):
        """Log to session log."""
        self._session_log.append(f"[{time.time()}] {message}")
        logger.info(f"[SYNC] {message}")
    
    def get_session_log(self) -> List[str]:
        """Get the session log."""
        return self._session_log.copy()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def create_minimal_pack(device_id: str, account_id: str) -> CapabilityPack:
    """Create a minimal empty pack for testing."""
    return CapabilityPack(
        sender_device_id=device_id,
        sender_account_id=account_id
    )


def is_transferable(origin: PackOrigin) -> bool:
    """Check if an origin type is transferable."""
    return origin in [PackOrigin.SOCIAL, PackOrigin.EMERGENT, PackOrigin.SYSTEM]


def mark_purchased_non_transferable(pack: CapabilityPack) -> CapabilityPack:
    """Mark all purchased artifacts as non-transferable."""
    for artifact in pack.artifacts:
        if artifact.origin == PackOrigin.PURCHASED:
            artifact.transferable = False
    return pack


# Export public API
__all__ = [
    'PackOrigin',
    'SyncMode',
    'SelectionPolicy',
    'ValidationResult',
    'SyncState',
    'CapabilityArtifact',
    'CapabilityPack',
    'PackSanitizer',
    'ImportReport',
    'SandboxResult',
    'SyncProtocol',
    'create_minimal_pack',
    'is_transferable',
    'mark_purchased_non_transferable',
]