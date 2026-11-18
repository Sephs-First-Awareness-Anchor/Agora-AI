#!/usr/bin/env python3
"""
Offline AI Library Extension
============================
Agora AI Platform - Phase 1

Extends the library system with Agora sync capabilities:
- Export shareable slices with sanitization
- Import shareable slices with merge policies
- Redaction of sensitive tokens
- Delta sync support
"""

import json
import re
import time
import logging
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMERATIONS
# ============================================================================

class MergePolicy(Enum):
    """Policy for merging imported slices."""
    REPLACE = "replace"           # Replace existing with imported
    MERGE = "merge"               # Merge, preferring higher confidence
    APPEND_ONLY = "append_only"   # Only add new entries
    CONSERVATIVE = "conservative" # Only merge if confidence > 0.8


class SliceType(Enum):
    """Types of shareable slices."""
    TEMPLATES = "templates"
    HYBRIDS = "hybrids"
    LEXICAL = "lexical"
    VOICE_PARAMS = "voice_params"
    VISION_PARAMS = "vision_params"
    AUDIO_PARAMS = "audio_params"
    REGISTRY_IMPROVEMENTS = "registry_improvements"


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class ShareableSlice:
    """A sanitized, shareable slice of the library."""
    slice_type: SliceType
    content: Dict[str, Any]
    source_fingerprint: str
    created_at: float = field(default_factory=time.time)
    confidence_threshold: float = 0.5
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "slice_type": self.slice_type.value,
            "content": self.content,
            "source_fingerprint": self.source_fingerprint,
            "created_at": self.created_at,
            "confidence_threshold": self.confidence_threshold
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ShareableSlice':
        return cls(
            slice_type=SliceType(data.get("slice_type", "templates")),
            content=data.get("content", {}),
            source_fingerprint=data.get("source_fingerprint", ""),
            created_at=data.get("created_at", time.time()),
            confidence_threshold=data.get("confidence_threshold", 0.5)
        )


@dataclass
class MergeReport:
    """Report from a merge operation."""
    success: bool
    entries_added: int
    entries_updated: int
    entries_rejected: int
    conflicts: List[str] = field(default_factory=list)
    details: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "entries_added": self.entries_added,
            "entries_updated": self.entries_updated,
            "entries_rejected": self.entries_rejected,
            "conflicts": self.conflicts,
            "details": self.details
        }


# ============================================================================
# SANITIZER
# ============================================================================

class LibrarySanitizer:
    """
    Sanitizes library content for sharing.
    Removes personal data and sensitive information.
    """
    
    # Patterns that might indicate personal information
    PII_PATTERNS = [
        (r'\b[A-Z][a-z]+\s[A-Z][a-z]+\b', '[NAME]'),  # Full names
        (r'\b\d{3}-\d{3}-\d{4}\b', '[PHONE]'),  # Phone numbers
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]'),  # Emails
        (r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[IP]'),  # IP addresses
    ]
    
    # Sensitive words to redact
    SENSITIVE_WORDS = {
        'name', 'address', 'phone', 'email', 'password', 'ssn',
        'social', 'birthday', 'birthdate', 'location', 'home', 'work',
        'username', 'login', 'account', 'secret', 'private'
    }
    
    # Fields to remove entirely
    FORBIDDEN_FIELDS = {
        'user_id', 'account_id', 'device_id', 'session_id',
        'transcript', 'chat_log', 'memory_content', 'personal_note',
        'face_vector', 'face_embedding', 'voice_fingerprint', 'biometric',
        'raw_audio', 'raw_video', 'image_data'
    }
    
    @classmethod
    def sanitize(cls, data: Any, depth: int = 0, max_depth: int = 10) -> Any:
        """
        Recursively sanitize data.
        
        Args:
            data: Data to sanitize
            depth: Current recursion depth
            max_depth: Maximum recursion depth
            
        Returns:
            Sanitized data
        """
        if depth > max_depth:
            return data
        
        if isinstance(data, dict):
            result = {}
            for key, value in data.items():
                # Skip forbidden fields
                if key.lower() in cls.FORBIDDEN_FIELDS:
                    continue
                
                # Sanitize key
                clean_key = cls._sanitize_string(key)
                
                # Recursively sanitize value
                clean_value = cls.sanitize(value, depth + 1, max_depth)
                
                result[clean_key] = clean_value
            return result
        
        elif isinstance(data, list):
            return [cls.sanitize(item, depth + 1, max_depth) for item in data]
        
        elif isinstance(data, str):
            return cls._sanitize_string(data)
        
        else:
            return data
    
    @classmethod
    def _sanitize_string(cls, text: str) -> str:
        """Sanitize a string."""
        # Apply PII patterns
        for pattern, replacement in cls.PII_PATTERNS:
            text = re.sub(pattern, replacement, text)
        
        # Redact sensitive words
        words = text.split()
        redacted = []
        for word in words:
            clean = word.lower().strip('.,!?;:()[]{}"\'')
            if clean in cls.SENSITIVE_WORDS:
                redacted.append('[REDACTED]')
            else:
                redacted.append(word)
        
        return ' '.join(redacted)
    
    @classmethod
    def redact_sensitive_tokens(cls, text: str) -> str:
        """Redact sensitive tokens from text."""
        return cls._sanitize_string(text)
    
    @classmethod
    def is_safe_to_share(cls, data: Any) -> bool:
        """Check if data is safe to share."""
        data_str = json.dumps(data).lower()
        
        # Check for forbidden patterns
        for field in cls.FORBIDDEN_FIELDS:
            if field in data_str:
                return False
        
        return True


# ============================================================================
# LIBRARY EXTENSION
# ============================================================================

class LibraryExtension:
    """
    Extension to the library system for Agora sync.
    
    Provides:
    - Export shareable slices
    - Import shareable slices with merge policies
    - Sanitization
    - Delta sync
    """
    
    def __init__(self, ai_instance: Any):
        self.ai = ai_instance
        self.sanitizer = LibrarySanitizer()
        self._export_history: List[Dict[str, Any]] = []
    
    # ========================================================================
    # EXPORT
    # ========================================================================
    
    def export_shareable_slice(self, 
                               slice_type: SliceType,
                               selection_policy: str = "all",
                               min_confidence: float = 0.5) -> ShareableSlice:
        """
        Export a shareable slice of the library.
        
        Args:
            slice_type: Type of slice to export
            selection_policy: "all", "high_confidence", or "recent"
            min_confidence: Minimum confidence for inclusion
            
        Returns:
            Sanitized shareable slice
        """
        content = self._extract_content(slice_type, selection_policy, min_confidence)
        
        # Sanitize content
        content = self.sanitizer.sanitize(content)
        
        # Get source fingerprint
        fingerprint = self._get_fingerprint()
        
        slice_obj = ShareableSlice(
            slice_type=slice_type,
            content=content,
            source_fingerprint=fingerprint,
            confidence_threshold=min_confidence
        )
        
        # Log export
        self._export_history.append({
            "timestamp": time.time(),
            "slice_type": slice_type.value,
            "content_size": len(json.dumps(content))
        })
        
        logger.info(f"[LIB EXT] Exported {slice_type.value} slice with {len(content)} entries")
        
        return slice_obj
    
    def _extract_content(self, 
                         slice_type: SliceType,
                         selection_policy: str,
                         min_confidence: float) -> Dict[str, Any]:
        """Extract content based on slice type."""
        if slice_type == SliceType.TEMPLATES:
            return self._extract_templates(selection_policy, min_confidence)
        elif slice_type == SliceType.HYBRIDS:
            return self._extract_hybrids(selection_policy, min_confidence)
        elif slice_type == SliceType.LEXICAL:
            return self._extract_lexical(selection_policy, min_confidence)
        elif slice_type == SliceType.VOICE_PARAMS:
            return self._extract_voice_params()
        elif slice_type == SliceType.VISION_PARAMS:
            return self._extract_vision_params()
        elif slice_type == SliceType.AUDIO_PARAMS:
            return self._extract_audio_params()
        elif slice_type == SliceType.REGISTRY_IMPROVEMENTS:
            return self._extract_registry_improvements()
        
        return {}
    
    def _extract_templates(self, selection_policy: str, min_confidence: float) -> Dict[str, Any]:
        """Extract templates."""
        templates = {}
        
        if hasattr(self.ai, 'language') and self.ai.language:
            if hasattr(self.ai.language, 'intent_evolution'):
                evo = self.ai.language.intent_evolution
                if hasattr(evo, 'evo') and hasattr(evo.evo.template_learner, 'templates'):
                    for modality, categories in evo.evo.template_learner.templates.items():
                        templates[modality] = {}
                        for category, template_list in categories.items():
                            # Filter by confidence if available
                            templates[modality][category] = template_list
        
        return {"templates": templates}
    
    def _extract_hybrids(self, selection_policy: str, min_confidence: float) -> Dict[str, Any]:
        """Extract hybrid intents."""
        hybrids = {}
        co_occurrences = {}
        
        if hasattr(self.ai, 'language') and self.ai.language:
            if hasattr(self.ai.language, 'intent_evolution'):
                evo = self.ai.language.intent_evolution
                if hasattr(evo, 'evo'):
                    if hasattr(evo.evo.evolution_registry, 'hybrids'):
                        hybrids = evo.evo.evolution_registry.hybrids
                    if hasattr(evo.evo.evolution_registry, 'co_occurrence_counts'):
                        co_occurrences = {
                            str(k): v 
                            for k, v in evo.evo.evolution_registry.co_occurrence_counts.items()
                        }
        
        return {
            "hybrids": hybrids,
            "co_occurrence_counts": co_occurrences
        }
    
    def _extract_lexical(self, selection_policy: str, min_confidence: float) -> Dict[str, Any]:
        """Extract lexical entries."""
        entries = {}
        
        if hasattr(self.ai, 'lexicon') and self.ai.lexicon:
            if hasattr(self.ai.lexicon, 'entries'):
                for word, entry in self.ai.lexicon.entries.items():
                    if entry.confidence >= min_confidence:
                        entries[word] = {
                            "frequency": entry.frequency,
                            "confidence": entry.confidence,
                            "intent_map": dict(entry.intent_map)
                        }
        
        return {"entries": entries}
    
    def _extract_voice_params(self) -> Dict[str, Any]:
        """Extract voice parameters (non-biometric only)."""
        params = {}
        
        if hasattr(self.ai, 'governor') and self.ai.governor:
            personalized = self.ai.governor.get_personalized_parameters()
            voice_gnome = personalized.get("voice_gnome", {})
            
            # Only include style parameters
            params = {
                k: v for k, v in voice_gnome.items()
                if k in ["pitch", "rate", "warmth", "prosody", "salience", "hesitation"]
            }
        
        return {"voice_params": params}
    
    def _extract_vision_params(self) -> Dict[str, Any]:
        """Extract vision parameters (non-biometric only)."""
        params = {}
        
        if hasattr(self.ai, 'vision') and self.ai.vision:
            params = {
                "focus": getattr(self.ai.vision, 'focus', 0.5),
                "motion_sensitivity": getattr(self.ai.vision, 'motion_sensitivity', 0.5),
                "recognition_threshold": getattr(self.ai.vision, 'recognition_threshold', 0.5),
                "detail_orientation": getattr(self.ai.vision, 'detail_orientation', 0.5),
            }
        
        return {"vision_params": params}
    
    def _extract_audio_params(self) -> Dict[str, Any]:
        """Extract audio parameters (non-biometric only)."""
        params = {}
        
        if hasattr(self.ai, 'audio') and self.ai.audio:
            params = {
                "sensitivity": getattr(self.ai.audio, 'sensitivity', 0.5),
                "voice_isolation": getattr(self.ai.audio, 'voice_isolation', 0.6),
                "emotion_detection": getattr(self.ai.audio, 'emotion_detection', 0.5),
            }
        
        return {"audio_params": params}
    
    def _extract_registry_improvements(self) -> Dict[str, Any]:
        """Extract registry improvements (quality scores, confidence maps)."""
        improvements = {}
        
        if hasattr(self.ai, 'language') and self.ai.language:
            if hasattr(self.ai.language, 'intent_evolution'):
                evo = self.ai.language.intent_evolution
                if hasattr(evo, 'evo'):
                    # Template quality scores
                    if hasattr(evo.evo.template_learner, 'templates'):
                        improvements["template_quality"] = {
                            "count": sum(
                                len(templates) 
                                for cats in evo.evo.template_learner.templates.values() 
                                for templates in cats.values()
                            )
                        }
                    
                    # Hybrid confidence
                    if hasattr(evo.evo.evolution_registry, 'hybrids'):
                        improvements["hybrid_count"] = len(evo.evo.evolution_registry.hybrids)
        
        return improvements
    
    def _get_fingerprint(self) -> str:
        """Get AI capability fingerprint."""
        try:
            from .agora_sync.offline_ai_capabilities import CapabilityManager
            manager = CapabilityManager(self.ai)
            manifest = manager.generate_manifest()
            return manifest.compute_fingerprint()
        except Exception as e:
            logger.warning(f"Could not generate fingerprint: {e}")
            return "unknown"
    
    # ========================================================================
    # IMPORT
    # ========================================================================
    
    def import_shareable_slice(self, 
                               slice_data: ShareableSlice,
                               merge_policy: MergePolicy = MergePolicy.MERGE) -> MergeReport:
        """
        Import a shareable slice with merge policy.
        
        Args:
            slice_data: The slice to import
            merge_policy: How to merge with existing content
            
        Returns:
            Merge report
        """
        if not self.sanitizer.is_safe_to_share(slice_data.content):
            return MergeReport(
                success=False,
                entries_added=0,
                entries_updated=0,
                entries_rejected=0,
                conflicts=["Content failed safety check"]
            )
        
        if slice_data.slice_type == SliceType.TEMPLATES:
            return self._merge_templates(slice_data.content, merge_policy)
        elif slice_data.slice_type == SliceType.HYBRIDS:
            return self._merge_hybrids(slice_data.content, merge_policy)
        elif slice_data.slice_type == SliceType.LEXICAL:
            return self._merge_lexical(slice_data.content, merge_policy)
        elif slice_data.slice_type == SliceType.VOICE_PARAMS:
            return self._merge_voice_params(slice_data.content, merge_policy)
        elif slice_data.slice_type == SliceType.VISION_PARAMS:
            return self._merge_vision_params(slice_data.content, merge_policy)
        elif slice_data.slice_type == SliceType.AUDIO_PARAMS:
            return self._merge_audio_params(slice_data.content, merge_policy)
        elif slice_data.slice_type == SliceType.REGISTRY_IMPROVEMENTS:
            return self._merge_registry_improvements(slice_data.content, merge_policy)
        
        return MergeReport(
            success=False,
            entries_added=0,
            entries_updated=0,
            entries_rejected=0,
            conflicts=["Unknown slice type"]
        )
    
    def _merge_templates(self, content: Dict[str, Any], policy: MergePolicy) -> MergeReport:
        """Merge templates."""
        report = MergeReport(success=True, entries_added=0, entries_updated=0, entries_rejected=0)
        
        if not hasattr(self.ai, 'language') or not self.ai.language:
            report.conflicts.append("Language system not available")
            return report
        
        templates = content.get("templates", {})
        
        for modality, categories in templates.items():
            for category, template_list in categories.items():
                for template in template_list:
                    # Check if template already exists
                    exists = self._template_exists(modality, category, template)
                    
                    if exists and policy == MergePolicy.APPEND_ONLY:
                        report.entries_rejected += 1
                        continue
                    
                    if not exists or policy in [MergePolicy.REPLACE, MergePolicy.MERGE]:
                        self._add_template(modality, category, template)
                        if exists:
                            report.entries_updated += 1
                        else:
                            report.entries_added += 1
        
        return report
    
    def _merge_hybrids(self, content: Dict[str, Any], policy: MergePolicy) -> MergeReport:
        """Merge hybrid intents."""
        report = MergeReport(success=True, entries_added=0, entries_updated=0, entries_rejected=0)
        
        if not hasattr(self.ai, 'language') or not self.ai.language:
            report.conflicts.append("Language system not available")
            return report
        
        hybrids = content.get("hybrids", {})
        
        for hybrid_name, components in hybrids.items():
            exists = self._hybrid_exists(hybrid_name)
            
            if exists and policy == MergePolicy.APPEND_ONLY:
                report.entries_rejected += 1
                continue
            
            if not exists or policy in [MergePolicy.REPLACE, MergePolicy.MERGE]:
                self._add_hybrid(hybrid_name, components)
                if exists:
                    report.entries_updated += 1
                else:
                    report.entries_added += 1
        
        return report
    
    def _merge_lexical(self, content: Dict[str, Any], policy: MergePolicy) -> MergeReport:
        """Merge lexical entries."""
        report = MergeReport(success=True, entries_added=0, entries_updated=0, entries_rejected=0)
        
        if not hasattr(self.ai, 'lexicon') or not self.ai.lexicon:
            report.conflicts.append("Lexicon not available")
            return report
        
        entries = content.get("entries", {})
        
        for word, entry_data in entries.items():
            confidence = entry_data.get("confidence", 0.5)
            
            if policy == MergePolicy.CONSERVATIVE and confidence < 0.8:
                report.entries_rejected += 1
                continue
            
            exists = word in self.ai.lexicon.entries
            
            if exists and policy == MergePolicy.APPEND_ONLY:
                report.entries_rejected += 1
                continue
            
            # Merge intent maps
            if exists and policy == MergePolicy.MERGE:
                existing = self.ai.lexicon.entries[word]
                new_intents = entry_data.get("intent_map", {})
                for intent, conf in new_intents.items():
                    if conf > existing.intent_map.get(intent, 0):
                        existing.intent_map[intent] = conf
                report.entries_updated += 1
            else:
                self._add_lexical_entry(word, entry_data)
                report.entries_added += 1
        
        return report
    
    def _merge_voice_params(self, content: Dict[str, Any], policy: MergePolicy) -> MergeReport:
        """Merge voice parameters."""
        report = MergeReport(success=True, entries_added=0, entries_updated=0, entries_rejected=0)
        
        if not hasattr(self.ai, 'governor') or not self.ai.governor:
            report.conflicts.append("Governor not available")
            return report
        
        params = content.get("voice_params", {})
        personalized = self.ai.governor.get_personalized_parameters()
        voice_gnome = personalized.get("voice_gnome", {})
        
        for key, value in params.items():
            if key in ["pitch", "rate", "warmth", "prosody", "salience", "hesitation"]:
                if policy == MergePolicy.REPLACE:
                    voice_gnome[key] = value
                    report.entries_updated += 1
                elif policy == MergePolicy.MERGE:
                    # Average the values
                    old_val = voice_gnome.get(key, 0.5)
                    voice_gnome[key] = (old_val + value) / 2
                    report.entries_updated += 1
                elif policy == MergePolicy.APPEND_ONLY and key not in voice_gnome:
                    voice_gnome[key] = value
                    report.entries_added += 1
        
        return report
    
    def _merge_vision_params(self, content: Dict[str, Any], policy: MergePolicy) -> MergeReport:
        """Merge vision parameters."""
        report = MergeReport(success=True, entries_added=0, entries_updated=0, entries_rejected=0)
        
        if not hasattr(self.ai, 'vision') or not self.ai.vision:
            report.conflicts.append("Vision not available")
            return report
        
        params = content.get("vision_params", {})
        
        for key, value in params.items():
            if hasattr(self.ai.vision, key):
                if policy == MergePolicy.REPLACE:
                    setattr(self.ai.vision, key, value)
                    report.entries_updated += 1
                elif policy == MergePolicy.MERGE:
                    old_val = getattr(self.ai.vision, key, 0.5)
                    setattr(self.ai.vision, key, (old_val + value) / 2)
                    report.entries_updated += 1
        
        return report
    
    def _merge_audio_params(self, content: Dict[str, Any], policy: MergePolicy) -> MergeReport:
        """Merge audio parameters."""
        report = MergeReport(success=True, entries_added=0, entries_updated=0, entries_rejected=0)
        
        if not hasattr(self.ai, 'audio') or not self.ai.audio:
            report.conflicts.append("Audio not available")
            return report
        
        params = content.get("audio_params", {})
        
        for key, value in params.items():
            if hasattr(self.ai.audio, key):
                if policy == MergePolicy.REPLACE:
                    setattr(self.ai.audio, key, value)
                    report.entries_updated += 1
                elif policy == MergePolicy.MERGE:
                    old_val = getattr(self.ai.audio, key, 0.5)
                    setattr(self.ai.audio, key, (old_val + value) / 2)
                    report.entries_updated += 1
        
        return report
    
    def _merge_registry_improvements(self, content: Dict[str, Any], policy: MergePolicy) -> MergeReport:
        """Merge registry improvements."""
        # Registry improvements are informational, not directly merged
        return MergeReport(
            success=True,
            entries_added=0,
            entries_updated=0,
            entries_rejected=0,
            details=["Registry improvements noted"]
        )
    
    # ========================================================================
    # HELPER METHODS
    # ========================================================================
    
    def _template_exists(self, modality: str, category: str, template: str) -> bool:
        """Check if template exists."""
        if not hasattr(self.ai, 'language') or not self.ai.language:
            return False
        
        try:
            evo = self.ai.language.intent_evolution
            templates = evo.evo.template_learner.templates
            return template in templates.get(modality, {}).get(category, [])
        except:
            return False
    
    def _add_template(self, modality: str, category: str, template: str):
        """Add a template."""
        try:
            evo = self.ai.language.intent_evolution
            if modality not in evo.evo.template_learner.templates:
                evo.evo.template_learner.templates[modality] = {}
            if category not in evo.evo.template_learner.templates[modality]:
                evo.evo.template_learner.templates[modality][category] = []
            if template not in evo.evo.template_learner.templates[modality][category]:
                evo.evo.template_learner.templates[modality][category].append(template)
        except Exception as e:
            logger.error(f"Failed to add template: {e}")
    
    def _hybrid_exists(self, hybrid_name: str) -> bool:
        """Check if hybrid exists."""
        if not hasattr(self.ai, 'language') or not self.ai.language:
            return False
        
        try:
            evo = self.ai.language.intent_evolution
            return hybrid_name in evo.evo.evolution_registry.hybrids
        except:
            return False
    
    def _add_hybrid(self, hybrid_name: str, components: list):
        """Add a hybrid intent."""
        try:
            evo = self.ai.language.intent_evolution
            evo.evo.evolution_registry.hybrids[hybrid_name] = tuple(components)
        except Exception as e:
            logger.error(f"Failed to add hybrid: {e}")
    
    def _add_lexical_entry(self, word: str, entry_data: Dict[str, Any]):
        """Add a lexical entry."""
        try:
            from .offline_ai_expression import LexemeEntry
            entry = LexemeEntry(word)
            entry.frequency = entry_data.get("frequency", 0)
            entry.confidence = entry_data.get("confidence", 0.5)
            entry.intent_map = entry_data.get("intent_map", {})
            self.ai.lexicon.entries[word] = entry
        except Exception as e:
            logger.error(f"Failed to add lexical entry: {e}")
    
    # ========================================================================
    # DELTA SYNC
    # ========================================================================
    
    def compute_delta(self, 
                      local_fingerprint: str,
                      remote_fingerprint: str) -> Dict[str, bool]:
        """
        Compute delta between local and remote fingerprints.
        
        Returns:
            Dict of changed module types
        """
        # In production, this would compare actual content hashes
        # For now, return all changed if fingerprints differ
        return {
            "templates": local_fingerprint != remote_fingerprint,
            "hybrids": local_fingerprint != remote_fingerprint,
            "lexical": local_fingerprint != remote_fingerprint,
            "voice_params": local_fingerprint != remote_fingerprint,
            "vision_params": local_fingerprint != remote_fingerprint,
            "audio_params": local_fingerprint != remote_fingerprint,
        }
    
    def get_export_history(self) -> List[Dict[str, Any]]:
        """Get history of exports."""
        return self._export_history.copy()


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def create_library_extension(ai_instance: Any) -> LibraryExtension:
    """Create a library extension for an AI instance."""
    return LibraryExtension(ai_instance)


def sanitize_for_sharing(data: Any) -> Any:
    """Sanitize data for sharing."""
    return LibrarySanitizer.sanitize(data)


def is_safe_to_share(data: Any) -> bool:
    """Check if data is safe to share."""
    return LibrarySanitizer.is_safe_to_share(data)


# Export public API
__all__ = [
    'MergePolicy',
    'SliceType',
    'ShareableSlice',
    'MergeReport',
    'LibrarySanitizer',
    'LibraryExtension',
    'create_library_extension',
    'sanitize_for_sharing',
    'is_safe_to_share',
]