#!/usr/bin/env python3
"""
Offline AI Pack Sanitizer
==========================
Agora AI Platform - Phase 1

Enforces the privacy boundary for capability pack exchange.
Ensures no personal data (transcripts, episodic memory, biometrics,
raw sensor data) ever leaves the device through sync packs.

Only distilled, non-personal capability growth artifacts may be exported:
- Distilled tags
- Promoted concept deltas
- Template deltas
- Wisdom summaries (no exemplars)
- Aggregate counters

This module is the final gate before any pack payload is serialized
for transmission. It operates defensively: anything not explicitly
allowed is stripped.
"""

import re
import copy
import json
import hashlib
import logging
import time
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ============================================================================
# FIELD CLASSIFICATION
# ============================================================================

# Fields/patterns that MUST NEVER leave the device.
# Matched against dict keys at any nesting depth.
PROHIBITED_FIELD_PATTERNS: Set[str] = {
    # Transcripts and conversation content
    "transcript",
    "transcripts",
    "transcript_text",
    "raw_transcript",
    "conversation_log",
    "chat_log",
    "chat_history",
    "message_text",
    "message_content",
    "user_message",
    "assistant_message",
    "dialogue",
    "utterance",
    "utterances",

    # Episodic memory
    "episodic_memory",
    "episodic_memories",
    "episode",
    "episodes",
    "episodic_buffer",
    "memory_content",
    "memory_text",
    "memory_narrative",
    "personal_memory",
    "autobiographical",
    "recall_buffer",

    # Biometrics -- face
    "face_vector",
    "face_vectors",
    "face_embedding",
    "face_embeddings",
    "face_encoding",
    "face_encodings",
    "faceprint",
    "face_print",
    "face_template",
    "facial_landmarks",
    "face_descriptor",
    "face_recognition_data",
    "face_id",
    "face_mesh",

    # Biometrics -- voice
    "voice_fingerprint",
    "voice_print",
    "voiceprint",
    "voice_embedding",
    "voice_vector",
    "speaker_embedding",
    "speaker_vector",
    "speaker_id_vector",
    "voice_biometric",
    "voice_id",

    # Biometrics -- other
    "biometric",
    "biometrics",
    "biometric_data",
    "iris_template",
    "fingerprint_data",
    "gait_signature",

    # Raw sensor data
    "raw_audio",
    "raw_audio_bytes",
    "audio_buffer",
    "audio_samples",
    "audio_pcm",
    "audio_wav",
    "audio_frames",
    "raw_image",
    "raw_images",
    "image_bytes",
    "image_data",
    "image_buffer",
    "image_pixels",
    "raw_video",
    "video_frames",
    "video_buffer",
    "video_bytes",
    "camera_frame",
    "camera_frames",
    "sensor_data",
    "raw_sensor",
    "raw_sensor_data",
    "accelerometer",
    "gyroscope",
    "depth_map",
    "point_cloud",
    "lidar_data",

    # PII carriers
    "user_identifier",
    "user_name",
    "user_email",
    "user_phone",
    "user_address",
    "user_location",
    "gps_coordinates",
    "geolocation",
    "ip_address",
    "mac_address",
    "device_serial",
    "ssn",
    "password",
    "credential",
    "credentials",
    "auth_token",
    "access_token",
    "refresh_token",
    "api_key",
    "secret_key",
}

# Regex patterns for detecting prohibited content in string values
PROHIBITED_VALUE_PATTERNS: List[re.Pattern] = [
    re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),  # Email
    re.compile(r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b'),                      # Phone (US)
    re.compile(r'\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b'),                      # SSN-like
    re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b'),                 # IPv4
]

# Fields that are explicitly SAFE to export
ALLOWED_FIELD_PATTERNS: Set[str] = {
    # Distilled tags
    "tags",
    "distilled_tags",
    "tag_id",
    "tag_name",
    "tag_weight",
    "tag_confidence",
    "tag_category",
    "tag_vector",

    # Promoted concept deltas
    "concept_delta",
    "concept_deltas",
    "promoted_concepts",
    "concept_id",
    "concept_name",
    "concept_weight",
    "concept_coherence",
    "concept_stability",

    # Template deltas
    "template_delta",
    "template_deltas",
    "template_id",
    "template_pattern",
    "template_slots",
    "template_category",
    "template_modality",
    "template_stability",
    "template_coherence",
    "template_usage_count",
    "template_success_count",

    # Hybrid deltas
    "hybrid_delta",
    "hybrid_deltas",
    "hybrid_id",
    "hybrid_name",
    "hybrid_components",
    "hybrid_coherence",
    "hybrid_occurrence_count",

    # Wisdom summaries (no exemplars)
    "wisdom_summary",
    "wisdom_summaries",
    "wisdom_id",
    "wisdom_domain",
    "wisdom_principle",
    "wisdom_confidence",
    "wisdom_counter",
    "wisdom_abstract",

    # Aggregate counters
    "aggregate_counters",
    "counter_id",
    "counter_name",
    "counter_value",
    "session_count",
    "total_observations",
    "usage_count",
    "success_count",
    "occurrence_count",
    "interaction_count",

    # Structural / metadata keys
    "schema_version",
    "modality",
    "family",
    "category",
    "artifact_id",
    "artifact_type",
    "origin",
    "transferable",
    "confidence",
    "created_at",
    "updated_at",
    "version",
    "content_hash",
    "pack_hash",
    "signature",

    # Safe style parameters (non-biometric)
    "pitch",
    "rate",
    "warmth",
    "prosody",
    "salience",
    "hesitation",
    "focus",
    "motion_sensitivity",
    "recognition_threshold",
    "detail_orientation",
    "sensitivity",
    "voice_isolation",
    "emotion_detection",

    # Evolution engine safe fields
    "pattern",
    "slots",
    "components",
    "embedding",
    "intent_map",
    "co_occurrence",
    "frequency",
    "stability",
    "coherence",
    "gain_vector",
}


# ============================================================================
# PACK SANITIZER
# ============================================================================

class PackSanitizer:
    """
    Enforces the privacy boundary for outgoing capability packs.

    Operating principle: deny by default. Only fields whose keys appear
    in ALLOWED_FIELDS (or pass the allow-list check) survive. Everything
    else is stripped silently and logged.

    Usage::

        sanitizer = PackSanitizer()
        clean_pack = sanitizer.sanitize(raw_pack_data)
        is_clean, violations = sanitizer.validate_clean(clean_pack)
        assert is_clean
    """

    # Class-level field sets (can be extended at runtime via subclass)
    PROHIBITED_FIELDS: Set[str] = PROHIBITED_FIELD_PATTERNS
    ALLOWED_FIELDS: Set[str] = ALLOWED_FIELD_PATTERNS

    # Size limits for individual values to prevent data exfiltration
    # via oversized allowed fields.
    MAX_STRING_VALUE_LENGTH: int = 10_000
    MAX_LIST_LENGTH: int = 5_000
    MAX_EMBEDDING_DIMS: int = 1024

    def __init__(
        self,
        extra_prohibited: Optional[Set[str]] = None,
        extra_allowed: Optional[Set[str]] = None,
        strict: bool = True,
    ):
        """
        Args:
            extra_prohibited: Additional field names to prohibit.
            extra_allowed: Additional field names to allow.
            strict: If True, unknown keys (not in allowed or prohibited)
                    are stripped. If False, unknown keys pass through
                    *only if* their values contain no prohibited patterns.
        """
        self._prohibited = set(self.PROHIBITED_FIELDS)
        self._allowed = set(self.ALLOWED_FIELDS)
        if extra_prohibited:
            self._prohibited |= extra_prohibited
        if extra_allowed:
            self._allowed |= extra_allowed
        self._strict = strict
        self._strip_log: List[str] = []

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------

    def sanitize(self, pack_data: dict) -> dict:
        """
        Remove all prohibited fields from *pack_data* (deep copy).

        Returns a new dict that is safe to serialize and transmit.
        The original dict is never mutated.
        """
        self._strip_log = []
        cleaned = self._sanitize_dict(copy.deepcopy(pack_data), path="")

        if self._strip_log:
            logger.info(
                "[SANITIZER] Stripped %d prohibited entries: %s",
                len(self._strip_log),
                ", ".join(self._strip_log[:20]),
            )

        return cleaned

    def validate_clean(self, pack_data: dict) -> Tuple[bool, List[str]]:
        """
        Check whether *pack_data* is already clean.

        Returns:
            (is_clean, violations) where violations lists every
            prohibited key or value pattern found.
        """
        violations: List[str] = []
        self._validate_recursive(pack_data, path="", violations=violations)
        return (len(violations) == 0, violations)

    def strip_biometrics(self, data: dict) -> dict:
        """
        Targeted removal of biometric data only.

        Removes face vectors/embeddings, voice prints, and any other
        biometric fields while leaving everything else intact.
        """
        biometric_keys = {
            k for k in self._prohibited
            if any(
                tag in k
                for tag in (
                    "face", "faceprint", "voice_fingerprint", "voiceprint",
                    "voice_print", "voice_embedding", "voice_vector",
                    "speaker_embedding", "speaker_vector", "speaker_id",
                    "voice_biometric", "voice_id", "biometric", "iris",
                    "fingerprint_data", "gait",
                )
            )
        }
        return self._strip_keys(data, biometric_keys)

    def strip_transcripts(self, data: dict) -> dict:
        """
        Targeted removal of transcript and conversation data only.
        """
        transcript_keys = {
            k for k in self._prohibited
            if any(
                tag in k
                for tag in (
                    "transcript", "conversation", "chat_log", "chat_history",
                    "message_text", "message_content", "user_message",
                    "assistant_message", "dialogue", "utterance",
                )
            )
        }
        return self._strip_keys(data, transcript_keys)

    def strip_raw_sensor(self, data: dict) -> dict:
        """
        Targeted removal of raw sensor data (audio, images, video,
        accelerometer, etc.).
        """
        sensor_keys = {
            k for k in self._prohibited
            if any(
                tag in k
                for tag in (
                    "raw_audio", "audio_buffer", "audio_samples", "audio_pcm",
                    "audio_wav", "audio_frames", "raw_image", "image_bytes",
                    "image_data", "image_buffer", "image_pixels", "raw_video",
                    "video_frames", "video_buffer", "video_bytes",
                    "camera_frame", "sensor_data", "raw_sensor",
                    "accelerometer", "gyroscope", "depth_map", "point_cloud",
                    "lidar",
                )
            )
        }
        return self._strip_keys(data, sensor_keys)

    def summarize_wisdom(self, wisdom_data: dict) -> dict:
        """
        Create a safe wisdom summary from full wisdom data.

        Preserves:
            - domain, principle, confidence, counter, abstract
        Strips:
            - exemplars (concrete episodes that could reveal PII)
            - source_transcripts, source_episodes, quotes
            - any raw supporting evidence
        """
        exemplar_keys = {
            "exemplars", "exemplar", "examples", "example",
            "source_transcripts", "source_episodes", "source_memories",
            "supporting_evidence", "evidence", "quotes", "quote",
            "raw_observations", "observations_raw", "instances",
            "anecdotes", "case_studies", "case_study",
        }

        result: Dict[str, Any] = {}
        for key, value in wisdom_data.items():
            lower_key = key.lower()

            # Drop exemplar-like keys entirely
            if lower_key in exemplar_keys:
                self._strip_log.append(f"wisdom.{key}")
                continue

            # Recursively sanitize nested dicts/lists
            if isinstance(value, dict):
                cleaned_sub = {}
                for sk, sv in value.items():
                    if sk.lower() not in exemplar_keys:
                        cleaned_sub[sk] = self._sanitize_value(sv, f"wisdom.{key}.{sk}")
                if cleaned_sub:
                    result[key] = cleaned_sub
            elif isinstance(value, list):
                # If the list looks like exemplars (list of dicts with
                # narrative-like keys), replace with a count.
                if value and isinstance(value[0], dict) and any(
                    ek in value[0] for ek in ("text", "narrative", "content", "episode")
                ):
                    result[f"{key}_count"] = len(value)
                    self._strip_log.append(f"wisdom.{key}->count")
                else:
                    result[key] = self._sanitize_value(value, f"wisdom.{key}")
            else:
                result[key] = self._sanitize_value(value, f"wisdom.{key}")

        # Ensure an abstract summary exists
        if "wisdom_abstract" not in result and "abstract" not in result:
            domain = result.get("wisdom_domain", result.get("domain", "general"))
            principle = result.get("wisdom_principle", result.get("principle", ""))
            confidence = result.get("wisdom_confidence", result.get("confidence", 0.0))
            result["wisdom_abstract"] = (
                f"Wisdom in domain '{domain}': "
                f"{principle[:200] if principle else 'no principle recorded'} "
                f"(confidence={confidence})"
            )

        return result

    def get_strip_log(self) -> List[str]:
        """Return the log of fields stripped in the last sanitize() call."""
        return list(self._strip_log)

    # ------------------------------------------------------------------
    # INTERNAL HELPERS
    # ------------------------------------------------------------------

    def _is_prohibited_key(self, key: str) -> bool:
        """Check if a key matches any prohibited pattern."""
        lower = key.lower()
        # Exact match
        if lower in self._prohibited:
            return True
        # Substring match (catches e.g. "user_face_vector_data")
        for pattern in self._prohibited:
            if pattern in lower:
                return True
        return False

    def _is_allowed_key(self, key: str) -> bool:
        """Check if a key is explicitly allowed."""
        lower = key.lower()
        if lower in self._allowed:
            return True
        for pattern in self._allowed:
            if pattern in lower:
                return True
        return False

    def _contains_prohibited_value(self, value: str) -> bool:
        """Check if a string value contains prohibited patterns (PII)."""
        for pattern in PROHIBITED_VALUE_PATTERNS:
            if pattern.search(value):
                return True
        return False

    def _sanitize_dict(self, data: dict, path: str) -> dict:
        """Recursively sanitize a dictionary."""
        result: Dict[str, Any] = {}
        for key, value in data.items():
            full_path = f"{path}.{key}" if path else key

            # Always strip prohibited keys
            if self._is_prohibited_key(key):
                self._strip_log.append(full_path)
                continue

            # In strict mode, only keep explicitly allowed keys (or dicts/lists
            # that may contain allowed sub-keys).
            if self._strict and not self._is_allowed_key(key):
                # Allow nested dicts and lists through so we can recurse
                if isinstance(value, dict):
                    sanitized_sub = self._sanitize_dict(value, full_path)
                    if sanitized_sub:
                        result[key] = sanitized_sub
                    continue
                elif isinstance(value, list):
                    sanitized_list = self._sanitize_list(value, full_path)
                    if sanitized_list:
                        result[key] = sanitized_list
                    continue
                else:
                    # Scalar value with unknown key in strict mode -- drop it
                    self._strip_log.append(full_path)
                    continue

            # Sanitize the value itself
            result[key] = self._sanitize_value(value, full_path)

        return result

    def _sanitize_list(self, data: list, path: str) -> list:
        """Sanitize a list, recursing into nested structures."""
        result: List[Any] = []
        for i, item in enumerate(data):
            item_path = f"{path}[{i}]"
            if isinstance(item, dict):
                sanitized = self._sanitize_dict(item, item_path)
                if sanitized:
                    result.append(sanitized)
            elif isinstance(item, list):
                sanitized = self._sanitize_list(item, item_path)
                if sanitized:
                    result.append(sanitized)
            elif isinstance(item, str):
                if not self._contains_prohibited_value(item):
                    result.append(self._clamp_string(item))
                else:
                    self._strip_log.append(item_path)
            else:
                result.append(item)

            # Enforce list length limit
            if len(result) >= self.MAX_LIST_LENGTH:
                break

        return result

    def _sanitize_value(self, value: Any, path: str) -> Any:
        """Sanitize a single value."""
        if isinstance(value, dict):
            return self._sanitize_dict(value, path)
        elif isinstance(value, list):
            # Embedding vectors: clamp dimensions
            if value and isinstance(value[0], (int, float)):
                return value[: self.MAX_EMBEDDING_DIMS]
            return self._sanitize_list(value, path)
        elif isinstance(value, str):
            if self._contains_prohibited_value(value):
                self._strip_log.append(path)
                return "[REDACTED]"
            return self._clamp_string(value)
        elif isinstance(value, bytes):
            # Binary data is never safe to export directly
            self._strip_log.append(path)
            return None
        else:
            return value

    def _clamp_string(self, text: str) -> str:
        """Clamp string length to prevent data exfiltration."""
        if len(text) > self.MAX_STRING_VALUE_LENGTH:
            return text[: self.MAX_STRING_VALUE_LENGTH] + "...[truncated]"
        return text

    def _strip_keys(self, data: dict, keys_to_strip: Set[str]) -> dict:
        """
        Generic deep-strip: remove any dict key whose lowercased name
        appears in *keys_to_strip*. Returns a deep copy.
        """
        result: Dict[str, Any] = {}
        for key, value in data.items():
            lower_key = key.lower()
            if lower_key in keys_to_strip:
                continue
            # Substring check
            if any(pat in lower_key for pat in keys_to_strip):
                continue

            if isinstance(value, dict):
                cleaned = self._strip_keys(value, keys_to_strip)
                if cleaned:
                    result[key] = cleaned
            elif isinstance(value, list):
                result[key] = self._strip_keys_list(value, keys_to_strip)
            else:
                result[key] = value
        return result

    def _strip_keys_list(self, data: list, keys_to_strip: Set[str]) -> list:
        """Strip prohibited keys from list elements."""
        result: List[Any] = []
        for item in data:
            if isinstance(item, dict):
                cleaned = self._strip_keys(item, keys_to_strip)
                if cleaned:
                    result.append(cleaned)
            elif isinstance(item, list):
                result.append(self._strip_keys_list(item, keys_to_strip))
            else:
                result.append(item)
        return result

    def _validate_recursive(
        self, data: Any, path: str, violations: List[str]
    ) -> None:
        """Recursively validate that no prohibited content remains."""
        if isinstance(data, dict):
            for key, value in data.items():
                full_path = f"{path}.{key}" if path else key
                if self._is_prohibited_key(key):
                    violations.append(
                        f"Prohibited key '{key}' at {full_path}"
                    )
                self._validate_recursive(value, full_path, violations)
        elif isinstance(data, list):
            for i, item in enumerate(data):
                self._validate_recursive(item, f"{path}[{i}]", violations)
        elif isinstance(data, str):
            if self._contains_prohibited_value(data):
                violations.append(
                    f"Prohibited value pattern at {path}"
                )
        elif isinstance(data, bytes):
            violations.append(
                f"Raw bytes at {path} (binary data must not be exported)"
            )


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================

def sanitize_pack(pack_data: dict, strict: bool = True) -> dict:
    """One-shot sanitize a pack dict."""
    return PackSanitizer(strict=strict).sanitize(pack_data)


def validate_pack_clean(pack_data: dict) -> Tuple[bool, List[str]]:
    """One-shot validation."""
    return PackSanitizer().validate_clean(pack_data)


def quick_strip_all_personal(data: dict) -> dict:
    """Strip biometrics, transcripts, and sensor data in one pass."""
    sanitizer = PackSanitizer()
    data = sanitizer.strip_biometrics(data)
    data = sanitizer.strip_transcripts(data)
    data = sanitizer.strip_raw_sensor(data)
    return data


# ============================================================================
# EXPORT
# ============================================================================

__all__ = [
    'PackSanitizer',
    'PROHIBITED_FIELD_PATTERNS',
    'PROHIBITED_VALUE_PATTERNS',
    'ALLOWED_FIELD_PATTERNS',
    'sanitize_pack',
    'validate_pack_clean',
    'quick_strip_all_personal',
]
