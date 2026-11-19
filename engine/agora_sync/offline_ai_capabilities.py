#!/usr/bin/env python3
"""
Offline AI Capabilities Module
==============================
Agora AI Platform - Phase 1

Generates stable capability manifests for device AI identity.
Tracks module versions and hashes for delta sync and verification.

Components:
- CapabilityManifest: Identity of the AI's capability layer
- ModuleHasher: Hash each shareable section for delta sync
- SpecializationProfile: Learning gain multipliers per domain
"""

import json
import hashlib
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================================
# SPECIALIZATION DEFINITIONS
# ============================================================================

class SpecializationType(Enum):
    """13 base aptitudes; ordered birth pairs and behavior create 52 profiles."""
    # Creative Domain
    STORYTELLER = "storyteller"      # Narrative, creative expression
    POET = "poet"                    # Linguistic artistry
    MUSICIAN = "musician"            # Audio pattern mastery
    ARTIST = "artist"                # Visual interpretation
    
    # Analytical Domain
    ANALYST = "analyst"              # Pattern recognition, data
    LOGICIAN = "logician"            # Reasoning, deduction
    PHILOSOPHER = "philosopher"      # Abstract thinking
    
    # Social Domain
    COMPANION = "companion"          # Default - balanced
    MENTOR = "mentor"                # Teaching, guidance
    LISTENER = "listener"            # Empathy, understanding
    
    # Technical Domain
    BUILDER = "builder"              # System construction
    EXPLORER = "explorer"            # Discovery, experimentation
    GUARDIAN = "guardian"            # Safety, protection


# Canonical 52 birth configurations: 13 original ordered pairs, 13 reversed
# pairs, and introverted/extroverted behavior for each. A–Z naming mirrors
# LETTER_PERSONA_MAP in offline_ai_expression.py.
# Frozen explicit order ensures new enum entries do not silently move births.
_ONBOARDING_PAIR_RING = (
    (SpecializationType.STORYTELLER, SpecializationType.POET),
    (SpecializationType.POET, SpecializationType.MUSICIAN),
    (SpecializationType.MUSICIAN, SpecializationType.ARTIST),
    (SpecializationType.ARTIST, SpecializationType.ANALYST),
    (SpecializationType.ANALYST, SpecializationType.LOGICIAN),
    (SpecializationType.LOGICIAN, SpecializationType.PHILOSOPHER),
    (SpecializationType.PHILOSOPHER, SpecializationType.COMPANION),
    (SpecializationType.COMPANION, SpecializationType.MENTOR),
    (SpecializationType.MENTOR, SpecializationType.LISTENER),
    (SpecializationType.LISTENER, SpecializationType.BUILDER),
    (SpecializationType.BUILDER, SpecializationType.EXPLORER),
    (SpecializationType.EXPLORER, SpecializationType.GUARDIAN),
    (SpecializationType.GUARDIAN, SpecializationType.STORYTELLER),
)
ONBOARDING_SPECIALIZATION_PAIRS = {
    letter: (_ONBOARDING_PAIR_RING[i] if i < 13
             else tuple(reversed(_ONBOARDING_PAIR_RING[i - 13])))
    for i, letter in enumerate("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
}


def onboarding_letter(ai_name: str) -> str:
    """Use the original first-letter selection, with B as fallback."""
    name = (ai_name or "").strip()
    letter = name[0].upper() if name else "B"
    return letter if letter in ONBOARDING_SPECIALIZATION_PAIRS else "B"


def onboarding_specialization(ai_name: str, mode: str) -> "SpecializationProfile":
    """One of 26 pairs x two modes; no randomized birth specialization."""
    if mode not in ("introvert", "extrovert"):
        raise ValueError("Onboarding mode must be introvert or extrovert")
    primary, secondary = ONBOARDING_SPECIALIZATION_PAIRS[onboarding_letter(ai_name)]
    return SpecializationProfile(primary, secondary, behavior_mode=mode)


# Default learning gain multipliers per specialization
DEFAULT_GAIN_MULTIPLIERS: Dict[SpecializationType, Dict[str, float]] = {
    SpecializationType.STORYTELLER: {
        "lexical": 1.4, "memory": 1.2, "expression": 1.5,
        "voice": 1.1, "visual": 0.9, "audio": 1.0
    },
    SpecializationType.POET: {
        "lexical": 1.5, "memory": 1.1, "expression": 1.4,
        "voice": 1.2, "visual": 0.8, "audio": 1.0
    },
    SpecializationType.MUSICIAN: {
        "lexical": 0.9, "memory": 1.2, "expression": 1.2,
        "voice": 1.3, "visual": 0.9, "audio": 1.5
    },
    SpecializationType.ARTIST: {
        "lexical": 0.9, "memory": 1.1, "expression": 1.3,
        "voice": 0.9, "visual": 1.5, "audio": 1.0
    },
    SpecializationType.ANALYST: {
        "lexical": 1.2, "memory": 1.4, "expression": 0.9,
        "voice": 0.8, "visual": 1.2, "audio": 0.9
    },
    SpecializationType.LOGICIAN: {
        "lexical": 1.3, "memory": 1.3, "expression": 0.9,
        "voice": 0.8, "visual": 1.0, "audio": 0.8
    },
    SpecializationType.PHILOSOPHER: {
        "lexical": 1.4, "memory": 1.3, "expression": 1.1,
        "voice": 1.0, "visual": 0.9, "audio": 0.9
    },
    SpecializationType.COMPANION: {
        "lexical": 1.1, "memory": 1.1, "expression": 1.1,
        "voice": 1.1, "visual": 1.1, "audio": 1.1
    },
    SpecializationType.MENTOR: {
        "lexical": 1.3, "memory": 1.2, "expression": 1.2,
        "voice": 1.2, "visual": 1.0, "audio": 1.0
    },
    SpecializationType.LISTENER: {
        "lexical": 1.1, "memory": 1.3, "expression": 1.0,
        "voice": 1.0, "visual": 1.1, "audio": 1.3
    },
    SpecializationType.BUILDER: {
        "lexical": 1.1, "memory": 1.2, "expression": 1.0,
        "voice": 0.9, "visual": 1.2, "audio": 0.9
    },
    SpecializationType.EXPLORER: {
        "lexical": 1.1, "memory": 1.1, "expression": 1.1,
        "voice": 1.0, "visual": 1.3, "audio": 1.1
    },
    SpecializationType.GUARDIAN: {
        "lexical": 0.9, "memory": 1.2, "expression": 0.9,
        "voice": 1.0, "visual": 1.3, "audio": 1.1
    },
}


@dataclass
class SpecializationProfile:
    """Learning gain multipliers for a specialization pair."""
    primary: SpecializationType
    secondary: SpecializationType
    behavior_mode: str = "introvert"

    def get_gain_vector(self) -> Dict[str, float]:
        """Compute combined gain vector from primary and secondary."""
        primary_gains = DEFAULT_GAIN_MULTIPLIERS.get(self.primary, {})
        secondary_gains = DEFAULT_GAIN_MULTIPLIERS.get(self.secondary, {})
        
        combined = {}
        all_domains = set(primary_gains.keys()) | set(secondary_gains.keys())
        
        for domain in all_domains:
            # Primary contributes 60%, secondary 40%
            p_gain = primary_gains.get(domain, 1.0)
            s_gain = secondary_gains.get(domain, 1.0)
            combined[domain] = round((p_gain * 0.6) + (s_gain * 0.4), 2)
        
        return combined
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary": self.primary.value,
            "secondary": self.secondary.value,
            "behavior_mode": self.behavior_mode,
            "gain_vector": self.get_gain_vector()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SpecializationProfile':
        return cls(
            primary=SpecializationType(data.get("primary", "companion")),
            secondary=SpecializationType(data.get("secondary", "companion")),
            behavior_mode=data.get("behavior_mode", "introvert")
        )


# ============================================================================
# CAPABILITY MANIFEST
# ============================================================================

@dataclass
class ModuleVersion:
    """Version info for a capability module."""
    name: str
    version: str
    schema_hash: str  # Hash of the module's schema
    content_hash: str  # Hash of actual content
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "schema_hash": self.schema_hash,
            "content_hash": self.content_hash,
            "timestamp": self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModuleVersion':
        return cls(
            name=data["name"],
            version=data["version"],
            schema_hash=data["schema_hash"],
            content_hash=data["content_hash"],
            timestamp=data.get("timestamp", time.time())
        )


@dataclass
class CapabilityManifest:
    """
    Complete capability identity for an AI instance.
    Used for delta sync and verification.
    """
    # Identity
    device_id: str
    account_id: str
    serial_code: str
    
    # Module versions
    template_registry: ModuleVersion
    hybrid_registry: ModuleVersion
    voice_genome: ModuleVersion
    vision_competency: ModuleVersion
    audio_competency: ModuleVersion
    policy_version: ModuleVersion
    
    # Specialization
    specialization: SpecializationProfile
    
    # Metadata
    manifest_version: str = "1.0"
    created_at: float = field(default_factory=time.time)
    
    def compute_fingerprint(self) -> str:
        """Compute unique fingerprint of this manifest."""
        data = {
            "device_id": self.device_id,
            "template": self.template_registry.content_hash,
            "hybrid": self.hybrid_registry.content_hash,
            "voice": self.voice_genome.content_hash,
            "vision": self.vision_competency.content_hash,
            "audio": self.audio_competency.content_hash,
            "policy": self.policy_version.content_hash,
            "spec": f"{self.specialization.primary.value}_{self.specialization.secondary.value}_{self.specialization.behavior_mode}"
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:32]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "manifest_version": self.manifest_version,
            "device_id": self.device_id,
            "account_id": self.account_id,
            "serial_code": self.serial_code,
            "fingerprint": self.compute_fingerprint(),
            "template_registry": self.template_registry.to_dict(),
            "hybrid_registry": self.hybrid_registry.to_dict(),
            "voice_genome": self.voice_genome.to_dict(),
            "vision_competency": self.vision_competency.to_dict(),
            "audio_competency": self.audio_competency.to_dict(),
            "policy_version": self.policy_version.to_dict(),
            "specialization": self.specialization.to_dict(),
            "created_at": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CapabilityManifest':
        return cls(
            device_id=data["device_id"],
            account_id=data["account_id"],
            serial_code=data["serial_code"],
            template_registry=ModuleVersion.from_dict(data["template_registry"]),
            hybrid_registry=ModuleVersion.from_dict(data["hybrid_registry"]),
            voice_genome=ModuleVersion.from_dict(data["voice_genome"]),
            vision_competency=ModuleVersion.from_dict(data["vision_competency"]),
            audio_competency=ModuleVersion.from_dict(data["audio_competency"]),
            policy_version=ModuleVersion.from_dict(data["policy_version"]),
            specialization=SpecializationProfile.from_dict(data["specialization"]),
            manifest_version=data.get("manifest_version", "1.0"),
            created_at=data.get("created_at", time.time())
        )


# ============================================================================
# MODULE HASHER
# ============================================================================

class ModuleHasher:
    """Generates content hashes for capability modules."""
    
    @staticmethod
    def hash_template_registry(templates: Dict[str, Any]) -> str:
        """Hash template registry content."""
        # Sort for deterministic hashing
        sorted_data = json.dumps(templates, sort_keys=True)
        return hashlib.sha256(sorted_data.encode()).hexdigest()[:16]
    
    @staticmethod
    def hash_hybrid_registry(hybrids: Dict[str, Any]) -> str:
        """Hash hybrid intent registry."""
        # Convert tuple keys to strings for JSON serialization
        serializable = {}
        for key, value in hybrids.items():
            if isinstance(key, tuple):
                serializable[str(key)] = value
            elif isinstance(value, dict):
                serializable[key] = {}
                for k, v in value.items():
                    if isinstance(k, tuple):
                        serializable[key][str(k)] = v
                    else:
                        serializable[key][k] = v
            else:
                serializable[key] = value
        sorted_data = json.dumps(serializable, sort_keys=True)
        return hashlib.sha256(sorted_data.encode()).hexdigest()[:16]
    
    @staticmethod
    def hash_voice_genome(voice_gnome: Dict[str, Any]) -> str:
        """Hash voice genome (non-biometric features only)."""
        # Only hash style parameters, never voiceprint
        safe_params = {
            "pitch": voice_gnome.get("pitch", 0.5),
            "rate": voice_gnome.get("rate", 0.5),
            "warmth": voice_gnome.get("warmth", 0.5),
            "prosody": voice_gnome.get("prosody", 0.5),
            "salience": voice_gnome.get("salience", 0.5),
            "hesitation": voice_gnome.get("hesitation", 0.2),
        }
        return hashlib.sha256(json.dumps(safe_params, sort_keys=True).encode()).hexdigest()[:16]
    
    @staticmethod
    def hash_vision_competency(vision: Dict[str, Any]) -> str:
        """Hash vision competency (non-faceprint features)."""
        safe_params = {
            "focus": vision.get("focus", 0.5),
            "motion_sensitivity": vision.get("motion_sensitivity", 0.5),
            "recognition_threshold": vision.get("recognition_threshold", 0.5),
            "detail_orientation": vision.get("detail_orientation", 0.5),
        }
        return hashlib.sha256(json.dumps(safe_params, sort_keys=True).encode()).hexdigest()[:16]
    
    @staticmethod
    def hash_audio_competency(audio: Dict[str, Any]) -> str:
        """Hash audio competency (non-voiceprint features)."""
        safe_params = {
            "sensitivity": audio.get("sensitivity", 0.5),
            "voice_isolation": audio.get("voice_isolation", 0.6),
            "emotion_detection": audio.get("emotion_detection", 0.5),
        }
        return hashlib.sha256(json.dumps(safe_params, sort_keys=True).encode()).hexdigest()[:16]
    
    @staticmethod
    def hash_policy(policy: Dict[str, Any]) -> str:
        """Hash policy configuration."""
        sorted_data = json.dumps(policy, sort_keys=True)
        return hashlib.sha256(sorted_data.encode()).hexdigest()[:16]


# ============================================================================
# CAPABILITY MANAGER
# ============================================================================

class CapabilityManager:
    """
    Manages capability manifests for an AI instance.
    Generates manifests from AI state and persists them.
    """
    
    def __init__(self, ai_instance: Any, persistence_dir: str = "./offline_ai_data/capabilities"):
        self.ai = ai_instance
        self.persistence_dir = Path(persistence_dir)
        self.persistence_dir.mkdir(parents=True, exist_ok=True)
        self._current_manifest: Optional[CapabilityManifest] = None
        
    def generate_manifest(self, specialization: Optional[SpecializationProfile] = None) -> CapabilityManifest:
        """Generate current capability manifest from AI state."""
        hasher = ModuleHasher()
        
        # Extract data from AI
        ai = self.ai
        
        # Template registry
        template_data = {}
        if hasattr(ai, 'language') and ai.language:
            if hasattr(ai.language, 'intent_evolution'):
                evo = ai.language.intent_evolution
                if hasattr(evo, 'evo'):
                    template_data = {
                        "templates": getattr(evo.evo.template_learner, 'templates', {}),
                        "hybrids": getattr(evo.evo.evolution_registry, 'hybrids', {}),
                    }
        
        # Hybrid registry
        hybrid_data = {}
        if hasattr(ai, 'language') and ai.language:
            if hasattr(ai.language, 'intent_evolution'):
                evo = ai.language.intent_evolution
                if hasattr(evo, 'evo'):
                    hybrid_data = {
                        "co_occurrences": getattr(evo.evo.evolution_registry, 'co_occurrence_counts', {}),
                        "hybrids": getattr(evo.evo.evolution_registry, 'hybrids', {}),
                        "concepts": {k: v.to_dict() for k, v in getattr(evo.evo, 'concepts', {}).items()}
                    }
        
        # Voice genome
        voice_data = {}
        if hasattr(ai, 'governor') and ai.governor:
            params = ai.governor.get_personalized_parameters()
            voice_data = params.get("voice_gnome", {})
        
        # Vision competency
        vision_data = {}
        if hasattr(ai, 'vision') and ai.vision:
            vision_data = {
                "focus": getattr(ai.vision, 'focus', 0.5),
                "motion_sensitivity": getattr(ai.vision, 'motion_sensitivity', 0.5),
                "recognition_threshold": getattr(ai.vision, 'recognition_threshold', 0.5),
                "detail_orientation": getattr(ai.vision, 'detail_orientation', 0.5),
            }
        
        # Audio competency
        audio_data = {}
        if hasattr(ai, 'audio') and ai.audio:
            audio_data = {
                "sensitivity": getattr(ai.audio, 'sensitivity', 0.5),
                "voice_isolation": getattr(ai.audio, 'voice_isolation', 0.6),
                "emotion_detection": getattr(ai.audio, 'emotion_detection', 0.5),
            }
        
        # Policy
        policy_data = {
            "autonomy_permanent": 0.25,
            "max_trait_delta_session": 0.05,
            "max_trait_delta_lifetime": 0.40,
        }
        
        # Default specialization if none provided: the AI's own, else companion
        if specialization is None:
            specialization = getattr(ai, 'specialization', None)
        if specialization is None:
            specialization = SpecializationProfile(
                primary=SpecializationType.COMPANION,
                secondary=SpecializationType.COMPANION
            )
        
        manifest = CapabilityManifest(
            device_id=getattr(ai, 'device_id', 'unknown'),
            account_id=getattr(ai, 'account_id', 'unknown'),
            serial_code=getattr(ai, 'serial_code', 'unknown'),
            template_registry=ModuleVersion(
                name="template_registry",
                version="1.0",
                schema_hash=hasher.hash_template_registry({"schema": "v1"}),
                content_hash=hasher.hash_template_registry(template_data)
            ),
            hybrid_registry=ModuleVersion(
                name="hybrid_registry",
                version="1.0",
                schema_hash=hasher.hash_hybrid_registry({"schema": "v1"}),
                content_hash=hasher.hash_hybrid_registry(hybrid_data)
            ),
            voice_genome=ModuleVersion(
                name="voice_genome",
                version="1.0",
                schema_hash=hasher.hash_voice_genome({"schema": "v1"}),
                content_hash=hasher.hash_voice_genome(voice_data)
            ),
            vision_competency=ModuleVersion(
                name="vision_competency",
                version="1.0",
                schema_hash=hasher.hash_vision_competency({"schema": "v1"}),
                content_hash=hasher.hash_vision_competency(vision_data)
            ),
            audio_competency=ModuleVersion(
                name="audio_competency",
                version="1.0",
                schema_hash=hasher.hash_audio_competency({"schema": "v1"}),
                content_hash=hasher.hash_audio_competency(audio_data)
            ),
            policy_version=ModuleVersion(
                name="policy",
                version="1.0",
                schema_hash=hasher.hash_policy({"schema": "v1"}),
                content_hash=hasher.hash_policy(policy_data)
            ),
            specialization=specialization
        )
        
        self._current_manifest = manifest
        return manifest
    
    def save_manifest(self, manifest: Optional[CapabilityManifest] = None):
        """Persist manifest to disk."""
        if manifest is None:
            manifest = self._current_manifest
        
        if manifest is None:
            logger.warning("[CAPABILITIES] No manifest to save")
            return
        
        path = self.persistence_dir / f"{manifest.device_id}_manifest.json"
        try:
            with open(path, 'w') as f:
                json.dump(manifest.to_dict(), f, indent=2)
            logger.info(f"[CAPABILITIES] Manifest saved: {path}")
        except Exception as e:
            logger.error(f"[CAPABILITIES] Failed to save manifest: {e}")
    
    def load_manifest(self, device_id: str) -> Optional[CapabilityManifest]:
        """Load manifest from disk."""
        path = self.persistence_dir / f"{device_id}_manifest.json"
        if not path.exists():
            return None
        
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            manifest = CapabilityManifest.from_dict(data)
            self._current_manifest = manifest
            return manifest
        except Exception as e:
            logger.error(f"[CAPABILITIES] Failed to load manifest: {e}")
            return None
    
    def compute_delta(self, other_manifest: CapabilityManifest) -> Dict[str, Any]:
        """Compute delta between this manifest and another."""
        if self._current_manifest is None:
            return {"error": "No current manifest"}
        
        current = self._current_manifest
        delta = {
            "template_changed": current.template_registry.content_hash != other_manifest.template_registry.content_hash,
            "hybrid_changed": current.hybrid_registry.content_hash != other_manifest.hybrid_registry.content_hash,
            "voice_changed": current.voice_genome.content_hash != other_manifest.voice_genome.content_hash,
            "vision_changed": current.vision_competency.content_hash != other_manifest.vision_competency.content_hash,
            "audio_changed": current.audio_competency.content_hash != other_manifest.audio_competency.content_hash,
            "policy_changed": current.policy_version.content_hash != other_manifest.policy_version.content_hash,
        }
        delta["any_changed"] = any(delta.values())
        return delta
    
    def get_current_manifest(self) -> Optional[CapabilityManifest]:
        """Get the current manifest."""
        return self._current_manifest


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def create_default_specialization(primary: str = "companion", 
                                   secondary: str = "companion") -> SpecializationProfile:
    """Create a specialization profile from string names."""
    try:
        p = SpecializationType(primary.lower())
    except ValueError:
        p = SpecializationType.COMPANION
    
    try:
        s = SpecializationType(secondary.lower())
    except ValueError:
        s = SpecializationType.COMPANION
    
    return SpecializationProfile(primary=p, secondary=s)


def get_learning_budget(gain_vector: Dict[str, float], 
                        base_budget: float = 1.0) -> Dict[str, float]:
    """
    Convert gain vector to learning budget allocation.
    Budget is distributed according to gain multipliers.
    """
    total_gain = sum(gain_vector.values())
    if total_gain == 0:
        return {domain: base_budget / len(gain_vector) for domain in gain_vector}
    
    return {
        domain: (gain / total_gain) * base_budget * gain
        for domain, gain in gain_vector.items()
    }


# Export public API
__all__ = [
    'SpecializationType',
    'SpecializationProfile',
    'ModuleVersion',
    'CapabilityManifest',
    'ModuleHasher',
    'CapabilityManager',
    'create_default_specialization',
    'get_learning_budget',
    'DEFAULT_GAIN_MULTIPLIERS',
]