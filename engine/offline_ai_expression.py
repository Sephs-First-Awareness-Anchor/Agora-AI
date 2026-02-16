#!/usr/bin/env python3
"""
Offline AI Expression Module
============================

Consolidated language, perception, and expression systems.
Combines:
- Language Bootstrap (offline_ai_language.py)
- Lexical Memory (offline_ai_lexicon.py)
- Audio/Phonetic Systems (offline_ai_audio.py)
- Vision Competency (offline_ai_vision.py)
- Voice Profiles (offline_ai_voice_profiles.py)
- Genome Structures (offline_ai_genomes.py)
- Lineage Constants (offline_ai_lineage.py)
- Evolution/Template System (offline_ai_templates.py)
"""

import os
import json
import logging
import re
import math
import random

# Numpy is optional on Android - gracefully handle missing numpy
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logging.getLogger(__name__).warning("[EXPRESSION] NumPy not available - using fallbacks")

    # Minimal numpy-like fallback for basic operations
    class _NumpyFallback:
        """Minimal fallback for numpy functions used in this module."""

        # Type alias for type hints
        ndarray = list

        @staticmethod
        def zeros(n):
            """Return a list of zeros (simulating np.zeros)."""
            return [0.0] * n

        @staticmethod
        def array(lst):
            """Return list as-is (simulating np.array)."""
            return list(lst) if not isinstance(lst, list) else lst

        @staticmethod
        def mean(lst, axis=None):
            """Simple mean calculation."""
            if not lst:
                return 0.0
            if axis == 0 and lst and isinstance(lst[0], (list, tuple)):
                # Mean across rows
                n = len(lst[0])
                result = [0.0] * n
                for row in lst:
                    for i, v in enumerate(row):
                        result[i] += v
                return [v / len(lst) for v in result]
            flat = lst if not isinstance(lst[0], (list, tuple)) else [x for row in lst for x in row]
            return sum(flat) / len(flat)

        @staticmethod
        def dot(v1, v2):
            """Dot product of two vectors."""
            return sum(a * b for a, b in zip(v1, v2))

        class linalg:
            @staticmethod
            def norm(v):
                """Euclidean norm of a vector."""
                return math.sqrt(sum(x * x for x in v))

        class random:
            @staticmethod
            def randn(n):
                """Random normal-ish values (using uniform as approximation)."""
                import random as stdlib_random
                return [stdlib_random.gauss(0, 1) for _ in range(n)]

    np = _NumpyFallback()
import time
import ast
import hashlib
from typing import Any, Dict, List, Optional, Tuple, Set, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from collections import defaultdict, deque

from .offline_ai_system import add_version_metadata, engine as migration_engine, STATE_VERSION

logger = logging.getLogger(__name__)

# Import Clock for re-export (used by other modules)
try:
    from kivy.clock import Clock
except ImportError:
    Clock = None  # Kivy not available (headless mode)

# ============================================================================
# 1. LINEAGE CONSTANTS (from offline_ai_lineage.py)
# ============================================================================

BASE_INTENTS = [
    "INFORM", "QUESTION", "SUMMARIZE", "REQUEST", "DIRECT", "PLAN",
    "CONNECT", "THANK", "APOLOGIZE", "EXPRESS", "REACT",
    "AGREE", "DENY", "CHALLENGE", "VALIDATE", "CONFIRM",
    "EVALUATE", "REFLECT", "NARRATE", "EXPLORE"
]

BASE_LEXICAL_ANCHORS = [
    "self", "user", "action", "object", "state", "time", "location",
    "positive", "negative", "neutral", "increase", "decrease"
]

BASE_VOICE_TEMPLATES = {
    "neutral": {"pitch": 0.5, "rate": 0.5, "warmth": 0.5},
    "warm": {"pitch": 0.45, "rate": 0.45, "warmth": 0.8},
    "formal": {"pitch": 0.55, "rate": 0.4, "warmth": 0.3},
}

BASE_VISION_PERCEPTS = [
    "face_detected", "object_detected", "text_detected", "motion_detected",
    "color_blob", "edge_pattern"
]

BASE_AUDIO_PERCEPTS = [
    "human_voice", "music_pattern", "ambient_noise", "alarm_tone", "impulse_noise"
]

BASE_PHONETIC_SEEDS = [
    "vowel_low", "vowel_high", "consonant_stop", "consonant_fricative", "nasal"
]

def is_descended_from_base(form_id: str, domain: str) -> bool:
    return True


# ============================================================================
# 2. GENOME STRUCTURES (from offline_ai_genomes.py)
# ============================================================================

@dataclass
class FractalAllele:
    id: str
    origin: str
    emotional_bias: Dict[str, float]
    dominance: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "origin": self.origin, "emotional_bias": self.emotional_bias, "dominance": self.dominance, "timestamp": self.timestamp}

@dataclass
class Gene:
    id: str
    trait: str
    stability: float
    base_value: float
    alleles: List[FractalAllele] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "trait": self.trait, "stability": self.stability, "base_value": self.base_value, "alleles": [a.to_dict() for a in self.alleles]}

    def calculate_current_value(self) -> float:
        if not self.alleles: return self.base_value
        total_weight = sum(a.dominance for a in self.alleles)
        if total_weight == 0: return self.base_value
        allele_influence = sum((a.dominance / total_weight) * (sum(a.emotional_bias.values()) / len(a.emotional_bias) if a.emotional_bias else 0.5) for a in self.alleles)
        return (self.stability * self.base_value) + ((1.0 - self.stability) * allele_influence)

@dataclass
class IdentityAnchor:
    id: str
    trait: str
    reinforcement: int = 1
    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "trait": self.trait, "reinforcement": self.reinforcement}

@dataclass
class VoiceGnome:
    # Core Perceptual Style (Anchored)
    pitch: float = 0.5
    rate: float = 0.5
    warmth: float = 0.6
    confidence: float = 0.5
    resonance: float = 0.5
    smoothness: float = 0.6

    # Expression Identity Anchors (Section III)
    prosody: float = 0.5        # Rythm and intonation
    salience: float = 0.5       # Importance weighting
    hesitation: float = 0.2     # Natural pause frequency

    # Baselines for anchoring
    baselines: Dict[str, float] = field(default_factory=lambda: {
        "prosody": 0.5, "salience": 0.5, "hesitation": 0.2,
        "pitch": 0.5, "rate": 0.5, "warmth": 0.6
    })

    genes: List[Gene] = field(default_factory=list)
    anchors: List[IdentityAnchor] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pitch": self.pitch, "rate": self.rate, "warmth": self.warmth,
            "confidence": self.confidence, "resonance": self.resonance,
            "smoothness": self.smoothness, "prosody": self.prosody,
            "salience": self.salience, "hesitation": self.hesitation,
            "baselines": self.baselines,
            "genes": [g.to_dict() for g in self.genes],
            "anchors": [a.to_dict() for a in self.anchors]
        }

    def modulate_voice(self, text: str, emotion_intensity: float = 0.0) -> Dict[str, Any]:
        # Enforce anchoring: Prevent total drift from baseline
        # Max allowed drift from baseline is 0.15 for identity parameters
        identity_params = ["prosody", "salience", "hesitation"]
        for p in identity_params:
            val = getattr(self, p)
            base = self.baselines.get(p, 0.5)
            if abs(val - base) > 0.15:
                # Pull back towards baseline
                val = base + (0.15 if val > base else -0.15)
                setattr(self, p, val)

        modulation = {
            "pitch": self.pitch, "rate": self.rate, "volume": self.confidence,
            "resonance": self.resonance, "warmth": self.warmth,
            "smoothness": self.smoothness, "prosody": self.prosody,
            "salience": self.salience, "hesitation": self.hesitation
        }
        if emotion_intensity > 0.5:
            modulation["pitch"] += 0.1 * (emotion_intensity - 0.5)
            modulation["rate"] += 0.05 * (emotion_intensity - 0.5)
        if len(text.split()) < 5: modulation["rate"] += 0.05
        for key in modulation: modulation[key] = max(0.0, min(1.0, modulation[key]))
        return modulation

@dataclass
class VisualCompetency:
    focus: float = 0.5
    motion_sensitivity: float = 0.5
    recognition_threshold: float = 0.5
    detail_orientation: float = 0.5
    def to_dict(self) -> Dict[str, float]:
        return {"focus": self.focus, "motion_sensitivity": self.motion_sensitivity, "recognition_threshold": self.recognition_threshold, "detail_orientation": self.detail_orientation}

@dataclass
class AuditoryAwareness:
    sensitivity: float = 0.5
    voice_isolation: float = 0.6
    emotion_detection: float = 0.5
    def to_dict(self) -> Dict[str, float]:
        return {"sensitivity": self.sensitivity, "voice_isolation": self.voice_isolation, "emotion_detection": self.emotion_detection}

@dataclass
class MotionStyle:
    fluidity: float = 0.5
    energy: float = 0.5
    responsiveness: float = 0.5
    def to_dict(self) -> Dict[str, float]:
        return {"fluidity": self.fluidity, "energy": self.energy, "responsiveness": self.responsiveness}

@dataclass
class SystemOperation:
    initiative: float = 0.4
    autonomy: float = 0.3
    resource_efficiency: float = 0.7
    def to_dict(self) -> Dict[str, float]:
        return {"initiative": self.initiative, "autonomy": self.autonomy, "resource_efficiency": self.resource_efficiency}

@dataclass
class ExpressionStyle:
    complexity: float = 0.5
    creativity: float = 0.6
    curiosity: float = 0.6
    empathy: float = 0.7
    genes: List[Gene] = field(default_factory=list)
    def to_dict(self) -> Dict[str, Any]:
        return {"complexity": self.complexity, "creativity": self.creativity, "curiosity": self.curiosity, "empathy": self.empathy, "genes": [g.to_dict() for g in self.genes]}


# ============================================================================
# 3. EVOLUTION & TEMPLATES (from offline_ai_templates.py)
# ============================================================================

class EvolutionTemplateLearner: # Renamed to avoid collision with language's wrapper
    def __init__(self):
        self.templates = defaultdict(lambda: defaultdict(list))
    def extract_template(self, text: str) -> str:
        t = re.sub(r"\d+", "{number}", text)
        t = re.sub(r"'[^']+'", "{value}", t)
        t = re.sub(r'"[^"]+"', "{value}", t)
        return t
    def observe(self, modality: str, category: str, content: str):
        template = self.extract_template(content)
        if template not in self.templates[modality][category]:
            self.templates[modality][category].append(template)
            logger.info(f"[TEMPLATES] Learned new {modality} template for {category}")
    def get_templates(self, modality: str, category: str) -> List[str]:
        return self.templates[modality][category]

class EvolutionRegistry:
    MAX_HYBRID_DEPTH = 2
    def __init__(self, stabilization_threshold: int = 10):
        self.co_occurrence_counts = defaultdict(int)
        self.hybrids = {}
        self.hybrid_depths = {}
        self.stabilization_threshold = stabilization_threshold
        self.reinforced_this_session = set()

    def _get_depth(self, part: str) -> int:
        return self.hybrid_depths.get(part, 0)

    def observe(self, part_a: str, part_b: str):
        if not part_a or not part_b or part_a == part_b: return
        depth_a = self._get_depth(part_a)
        depth_b = self._get_depth(part_b)
        if max(depth_a, depth_b) >= self.MAX_HYBRID_DEPTH: return
        pair = tuple(sorted([part_a, part_b]))
        self.co_occurrence_counts[pair] += 1
        self.reinforced_this_session.add(pair)

        # Promotion filter: recurrence >= HYBRID_PROMOTE_THRESHOLD (stabilization_threshold)
        # and abstraction_coherence >= 0.4 (simulated by high enough count for now or secondary metric)
        if self.co_occurrence_counts[pair] >= self.stabilization_threshold:
            hybrid_name = f"{pair[0]}_{pair[1]}_HYBRID"
            if hybrid_name not in self.hybrids:
                self.hybrids[hybrid_name] = pair
                self.hybrid_depths[hybrid_name] = max(depth_a, depth_b) + 1

    def decay_unreinforced(self):
        """SECTION 6: co_occurrence decays by factor 0.85 per consolidation if not reinforced."""
        for pair in list(self.co_occurrence_counts.keys()):
            if pair not in self.reinforced_this_session:
                self.co_occurrence_counts[pair] = int(self.co_occurrence_counts[pair] * 0.85)
                if self.co_occurrence_counts[pair] < 1:
                    del self.co_occurrence_counts[pair]
        self.reinforced_this_session.clear()

    def get_stabilized_hybrids(self) -> Dict[str, Tuple[str, str]]:
        return self.hybrids

class ConceptTemplate:
    def __init__(self, intent: str, lexeme: str, percept: str):
        self.intent, self.lexeme, self.percept = intent, lexeme, percept
        self.usage_count, self.confidence, self.stability = 0, 0.5, 0.0
        self.sessions = 0
        self.cross_modal_support = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent, "lexeme": self.lexeme, "percept": self.percept,
            "usage_count": self.usage_count, "confidence": self.confidence,
            "stability": self.stability, "sessions": self.sessions,
            "cross_modal_support": self.cross_modal_support
        }

class SelfGenerativeEvolution:
    def __init__(self, persistence_dir: str = "./offline_ai_data/evolution"):
        self.persistence_dir = Path(persistence_dir)
        try:
            self.persistence_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"[EVOLUTION] Failed to create storage directory {persistence_dir}: {e}")
        self.template_learner = EvolutionTemplateLearner()
        self.evolution_registry = EvolutionRegistry()
        self.concepts: Dict[str, ConceptTemplate] = {}
        self._load_state()
    def record_success(self, modality: str, category: str, content: str, context_tags: List[str] = None):
        self.template_learner.observe(modality, category, content)
        if context_tags:
            for tag in context_tags: self.evolution_registry.observe(category, tag)
    def get_suggestion(self, modality: str, category: str) -> Optional[str]:
        templates = self.template_learner.get_templates(modality, category)
        return random.choice(templates) if templates else None
    def record_grounding(self, intent: str, lexeme: str, percept: str, cross_modal: bool = True):
        concept_id = f"{intent}:{lexeme}:{percept}"
        if concept_id not in self.concepts:
            self.concepts[concept_id] = ConceptTemplate(intent, lexeme, percept)
        c = self.concepts[concept_id]
        c.usage_count += 1
        c.cross_modal_support = cross_modal or c.cross_modal_support
        c.confidence = min(1.0, c.usage_count / 10.0)

        # Promotion check: occurrences >= 3, sessions >= 2, cross_modal_support == true
        if c.usage_count >= 3 and c.sessions >= 2 and c.cross_modal_support:
            c.stability = min(1.0, c.stability + 0.1)

    def end_session(self):
        """Called during consolidation to increment session counts."""
        for c in self.concepts.values():
            if c.usage_count > 0:
                c.sessions += 1
        self.evolution_registry.decay_unreinforced()
    def _save_state(self):
        state = {"templates": {m: dict(c) for m, c in self.template_learner.templates.items()}, "co_occurrences": {str(k): v for k, v in self.evolution_registry.co_occurrence_counts.items()}, "hybrids": {k: list(v) for k, v in self.evolution_registry.hybrids.items()}, "hybrid_depths": self.evolution_registry.hybrid_depths, "concepts": {k: v.to_dict() for k, v in self.concepts.items()}}
        try:
            with open(self.persistence_dir / "evolution_state.json", 'w') as f:
                json.dump(state, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            logger.error(f"[EVOLUTION] Failed to save state: {e}")
    def _load_state(self):
        path = self.persistence_dir / "evolution_state.json"
        if not path.exists(): return
        try:
            with open(path, 'r') as f: state = json.load(f)
            for modality, categories in state.get("templates", {}).items():
                for cat, tmpls in categories.items(): self.template_learner.templates[modality][cat] = tmpls
            for k, v in state.get("co_occurrences", {}).items(): self.evolution_registry.co_occurrence_counts[ast.literal_eval(k)] = v
            for k, v in state.get("hybrids", {}).items(): self.evolution_registry.hybrids[k] = tuple(v)
            self.evolution_registry.hybrid_depths = state.get("hybrid_depths", {})
            for k, v in state.get("concepts", {}).items():
                c = ConceptTemplate(v["intent"], v["lexeme"], v["percept"])
                c.usage_count, c.confidence, c.stability = v["usage_count"], v["confidence"], v["stability"]
                self.concepts[k] = c
        except Exception as e: logger.error(f"[EVOLUTION] Failed to load state: {e}")


# ============================================================================
# 4. LEXICAL MEMORY (from offline_ai_lexicon.py)
# ============================================================================

class LexicalCandidate:
    def __init__(self, word_form: str):
        self.word_form = word_form
        self.occurrence_count = 0
        self.intent_histogram = defaultdict(int)
        self.co_occurrence_map = defaultdict(int)
        self.emotional_bias = 0.0
        self.confidence = 0.0
    def to_dict(self) -> Dict[str, Any]:
        return {"word_form": self.word_form, "occurrence_count": self.occurrence_count, "intent_histogram": dict(self.intent_histogram), "co_occurrence_map": {str(k): v for k, v in self.co_occurrence_map.items()}, "emotional_bias": self.emotional_bias, "confidence": self.confidence}
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LexicalCandidate':
        c = cls(data["word_form"])
        c.occurrence_count = data["occurrence_count"]
        c.intent_histogram = defaultdict(int, data.get("intent_histogram", {}))
        c.co_occurrence_map = defaultdict(int, {ast.literal_eval(k) if k.startswith('(') else k: v for k, v in data.get("co_occurrence_map", {}).items()})
        c.emotional_bias, c.confidence = data["emotional_bias"], data["confidence"]
        return c

def cosine_similarity(v1, v2) -> float:
    v1 = np.array(v1)
    v2 = np.array(v2)
    if np.linalg.norm(v1) == 0 or np.linalg.norm(v2) == 0:
        return 0.0
    return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))

def get_intent_vector(intent: str, dimensions: int = 64) -> np.ndarray:
    """Deterministic hash-based intent vector mapping (matching memory system)"""
    v = np.zeros(dimensions)
    intent_hash = hashlib.md5(intent.encode()).digest()
    # Fill intent segment (56-59)
    for i in range(min(4, len(intent_hash))):
        v[56+i] = (intent_hash[i] / 255.0)
    # Also sprinkle some characteristic hash across the vector for stability
    full_hash = hashlib.sha256(intent.encode()).digest()
    for i in range(min(dimensions, len(full_hash))):
        v[i] += (full_hash[i] / 512.0) # Low magnitude background
    return v

class LexemeEntry:
    def __init__(self, word: str):
        self.word = word
        self.phonetic = ""
        self.vector = np.zeros(64).tolist()
        self.intent_map = defaultdict(float) # intent -> confidence
        self.frequency = 0
        self.confidence = 0.5
        self.last_updated = time.time()

    def update_embedding(self, current_intent: str, learning_rate: float = 0.1):
        """Moving average update toward current context intent vector"""
        target_v = get_intent_vector(current_intent)
        v = np.array(self.vector)
        # Weight by lexeme confidence
        actual_lr = learning_rate * self.confidence
        v = (1.0 - actual_lr) * v + actual_lr * target_v
        self.vector = v.tolist()
        self.last_updated = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "word": self.word,
            "phonetic": self.phonetic,
            "vector": self.vector,
            "intent_map": dict(self.intent_map),
            "frequency": self.frequency,
            "confidence": self.confidence,
            "last_updated": self.last_updated
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LexemeEntry':
        e = cls(data["word"])
        e.phonetic = data.get("phonetic", "")
        e.vector = data.get("vector", np.zeros(64).tolist())
        e.intent_map = defaultdict(float, data.get("intent_map", {}))
        e.frequency = data.get("frequency", 0)
        e.confidence = data.get("confidence", 0.5)
        e.last_updated = data.get("last_updated", time.time())
        return e

class LexiconManager:
    STABILITY_THRESHOLD = 5
    def __init__(self, persistence_dir: str):
        self.persistence_dir = Path(persistence_dir)
        try:
            self.persistence_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"[LEXICON] Failed to create storage directory {persistence_dir}: {e}")
        self.candidates: Dict[str, LexicalCandidate] = {}
        self.entries: Dict[str, LexemeEntry] = {}
        self._load_state()
        self._bootstrap_lineage()

    def _bootstrap_lineage(self):
        if not self.entries:
            for word in BASE_LEXICAL_ANCHORS:
                self.add_lexeme(word)
                self.entries[word].confidence = 1.0

    def add_lexeme(self, word: str) -> LexemeEntry:
        if word not in self.entries:
            self.entries[word] = LexemeEntry(word)
        return self.entries[word]

    def update_frequency(self, word: str):
        if word in self.entries:
            self.entries[word].frequency += 1
            self.entries[word].last_updated = time.time()

    def bind_to_intent(self, word: str, intent: str, confidence_delta: float = 0.1):
        if word in self.entries:
            e = self.entries[word]
            e.intent_map[intent] = min(1.0, e.intent_map[intent] + confidence_delta)
            e.update_embedding(intent)

    def process_text(self, text: str, intent: str = None):
        words = re.findall(r'\w+', text.lower())
        for word in words:
            if word in self.entries:
                self.update_frequency(word)
                if intent: self.bind_to_intent(word, intent)
            else:
                self._update_candidate(word, intent)

    def _update_candidate(self, word: str, intent: str):
        if word not in self.candidates:
            self.candidates[word] = LexicalCandidate(word)
        c = self.candidates[word]
        c.occurrence_count += 1
        if intent: c.intent_histogram[intent] += 1
        c.confidence = min(1.0, c.occurrence_count / self.STABILITY_THRESHOLD)
        if c.occurrence_count >= self.STABILITY_THRESHOLD:
            self._promote_after_threshold(word)

    def _promote_after_threshold(self, word: str):
        if word not in self.candidates: return
        c = self.candidates[word]
        e = self.add_lexeme(word)
        e.frequency = c.occurrence_count

        # Initialize intent map from histogram
        total_intents = sum(c.intent_histogram.values())
        if total_intents > 0:
            for intent, count in c.intent_histogram.items():
                e.intent_map[intent] = count / total_intents

        # Initialize vector: weighted sum of intent vectors
        base_v = np.zeros(64)
        if total_intents > 0:
            for intent, count in c.intent_histogram.items():
                weight = count / total_intents
                base_v += weight * get_intent_vector(intent)

        # Add co-occurrence noise for uniqueness
        if c.co_occurrence_map:
            noise = np.zeros(64)
            for other, count in list(c.co_occurrence_map.items())[:10]:
                noise += (hash(other) % 1000 / 10000.0) * (count / max(1, sum(c.co_occurrence_map.values())))
            base_v += noise

        e.vector = base_v.tolist()

        del self.candidates[word]
        logger.info(f"[LEXICON] Promoted '{word}' to stable lexeme with vector.")

    def prune_low_value(self):
        to_remove = [w for w, c in self.candidates.items() if c.confidence < 0.2]
        for w in to_remove: del self.candidates[w]

    def _save_state(self):
        state = {
            "candidates": {w: c.to_dict() for w, c in self.candidates.items()},
            "entries": {w: e.to_dict() for w, e in self.entries.items()}
        }
        try:
            with open(self.persistence_dir / "lexicon_state.json", 'w') as f:
                json.dump(state, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            logger.error(f"[LEXICON] Failed to save state: {e}")

    def _load_state(self):
        path = self.persistence_dir / "lexicon_state.json"
        if not path.exists(): return
        try:
            with open(path, 'r') as f: state = json.load(f)
            for w, data in state.get("candidates", {}).items():
                self.candidates[w] = LexicalCandidate.from_dict(data)
            for w, data in state.get("entries", {}).items():
                self.entries[w] = LexemeEntry.from_dict(data)
        except Exception as e: logger.error(f"[LEXICON] Failed to load state: {e}")

    def save_state(self): self._save_state()
    def get_combined_vector(self, text: str) -> List[float]:
        """Calculate aggregate lexical vector for a block of text"""
        words = re.findall(r'\w+', text.lower())
        vectors = []
        for w in words:
            if w in self.entries:
                vectors.append(self.entries[w].vector)
        if not vectors:
            return np.zeros(64).tolist()
        return np.mean(vectors, axis=0).tolist()

    def prune(self): self.prune_low_value()


# ============================================================================
# 5. AUDIO & PHONETICS (from offline_ai_audio.py)
# ============================================================================

class AudioPerceptTemplate:
    def __init__(self, name: str):
        self.name = name
        self.spectral_signature, self.temporal_pattern, self.rhythm_features = [], [], {}
        self.confidence, self.stability, self.usage_count = 0.5, 0.0, 0
    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "spectral_signature": self.spectral_signature, "temporal_pattern": self.temporal_pattern, "rhythm_features": self.rhythm_features, "confidence": self.confidence, "stability": self.stability, "usage_count": self.usage_count}
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AudioPerceptTemplate':
        t = cls(data["name"])
        t.spectral_signature, t.temporal_pattern, t.rhythm_features = data.get("spectral_signature", []), data.get("temporal_pattern", []), data.get("rhythm_features", {})
        t.confidence, t.stability, t.usage_count = data.get("confidence", 0.5), data.get("stability", 0.0), data.get("usage_count", 0)
        return t

class PhoneticLexemeTemplate:
    def __init__(self, signature: str):
        self.phonetic_signature = signature
        self.spectral_features, self.temporal_pattern, self.associated_text_forms = {}, [], []
        self.intent_histogram = defaultdict(int)
        self.emotional_bias, self.confidence, self.stability = 0.0, 0.5, 0.0
    def to_dict(self) -> Dict[str, Any]:
        return {"phonetic_signature": self.phonetic_signature, "spectral_features": self.spectral_features, "temporal_pattern": self.temporal_pattern, "associated_text_forms": self.associated_text_forms, "intent_histogram": dict(self.intent_histogram), "emotional_bias": self.emotional_bias, "confidence": self.confidence, "stability": self.stability}
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PhoneticLexemeTemplate':
        t = cls(data["phonetic_signature"])
        t.spectral_features, t.temporal_pattern, t.associated_text_forms = data.get("spectral_features", {}), data.get("temporal_pattern", []), data.get("associated_text_forms", [])
        t.intent_histogram = defaultdict(int, data.get("intent_histogram", {}))
        t.emotional_bias, t.confidence, t.stability = data.get("emotional_bias", 0.0), data.get("confidence", 0.5), data.get("stability", 0.0)
        return t

class VoiceIntentTemplate:
    def __init__(self, intent: str):
        self.intent, self.modulation_vector, self.emotional_signature = intent, {}, {}
        self.stability, self.usage_count = 0.0, 0
    def to_dict(self) -> Dict[str, Any]:
        return {"intent": self.intent, "modulation_vector": self.modulation_vector, "emotional_signature": self.emotional_signature, "stability": self.stability, "usage_count": self.usage_count}
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VoiceIntentTemplate':
        t = cls(data["intent"])
        t.modulation_vector, t.emotional_signature = data.get("modulation_vector", {}), data.get("emotional_signature", {})
        t.stability, t.usage_count = data.get("stability", 0.0), data.get("usage_count", 0)
        return t

class PhoneticMemory:
    def __init__(self):
        self.clusters = defaultdict(list) # phoneme -> centroids
        self.acoustic_centroids = {} # cluster_id -> vector
        self.word_bindings = defaultdict(list) # word -> phonetic_signatures

    def to_dict(self) -> Dict[str, Any]:
        return {
            "clusters": {k: v for k, v in self.clusters.items()},
            "acoustic_centroids": self.acoustic_centroids,
            "word_bindings": {k: v for k, v in self.word_bindings.items()}
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PhoneticMemory':
        pm = cls()
        pm.clusters = defaultdict(list, data.get("clusters", {}))
        pm.acoustic_centroids = data.get("acoustic_centroids", {})
        pm.word_bindings = defaultdict(list, data.get("word_bindings", {}))
        return pm

class SoundConceptEntry:
    def __init__(self, id: str):
        self.id = id
        self.acoustic_centroid = np.zeros(64).tolist()
        self.category_hypothesis = "unknown" # speech | music | noise | alarm | emotion | unknown
        self.bound_lexemes = defaultdict(float) # word -> weight
        self.intent_histogram = defaultdict(int)
        self.confidence = 0.5
        self.frequency = 0
        self.last_updated = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "acoustic_centroid": self.acoustic_centroid,
            "category_hypothesis": self.category_hypothesis,
            "bound_lexemes": dict(self.bound_lexemes),
            "intent_histogram": dict(self.intent_histogram),
            "confidence": self.confidence,
            "frequency": self.frequency,
            "last_updated": self.last_updated
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SoundConceptEntry':
        e = cls(data["id"])
        e.acoustic_centroid = data.get("acoustic_centroid", np.zeros(64).tolist())
        e.category_hypothesis = data.get("category_hypothesis", "unknown")
        e.bound_lexemes = defaultdict(float, data.get("bound_lexemes", {}))
        e.intent_histogram = defaultdict(int, data.get("intent_histogram", {}))
        e.confidence = data.get("confidence", 0.5)
        e.frequency = data.get("frequency", 0)
        e.last_updated = data.get("last_updated", time.time())
        return e

class SoundConceptMemory:
    def __init__(self, persistence_dir: str):
        self.persistence_dir = Path(persistence_dir)
        try:
            self.persistence_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"[SOUND MEM] Failed to create storage directory {persistence_dir}: {e}")
        self.concepts: Dict[str, SoundConceptEntry] = {}
        self._load_state()

    def add_or_update_concept(self, acoustic_vector: List[float], category_hypothesis: str,
                             intent: str = None, bound_lexeme: str = None):
        # Find closest existing concept or create new
        best_id = None
        best_sim = -1.0

        for cid, entry in self.concepts.items():
            sim = cosine_similarity(acoustic_vector, entry.acoustic_centroid)
            if sim > 0.9 and sim > best_sim:
                best_sim = sim
                best_id = cid

        if best_id:
            e = self.concepts[best_id]
            # Moving average update of centroid
            v = np.array(e.acoustic_centroid)
            e.acoustic_centroid = ((0.9 * v) + (0.1 * np.array(acoustic_vector))).tolist()
        else:
            best_id = f"snd_{int(time.time()*1000)}"
            e = SoundConceptEntry(best_id)
            e.acoustic_centroid = acoustic_vector
            self.concepts[best_id] = e

        e.category_hypothesis = category_hypothesis
        e.frequency += 1
        if intent: e.intent_histogram[intent] += 1
        if bound_lexeme: e.bound_lexemes[bound_lexeme] = min(1.0, e.bound_lexemes[bound_lexeme] + 0.1)
        e.last_updated = time.time()
        e.confidence = min(1.0, e.frequency / 5.0)

    def find_semantic_matches(self, query_vector: List[float], threshold: float = 0.8) -> List[SoundConceptEntry]:
        """Find concepts that are acoustically or semantically similar"""
        matches = []
        for entry in self.concepts.values():
            sim = cosine_similarity(query_vector, entry.acoustic_centroid)
            if sim >= threshold:
                matches.append(entry)
        return sorted(matches, key=lambda x: cosine_similarity(query_vector, x.acoustic_centroid), reverse=True)

    def get_concepts_by_category(self, category: str) -> List[SoundConceptEntry]:
        """Group concepts by semantic category"""
        return [c for c in self.concepts.values() if c.category_hypothesis == category]

    def prune(self, quota_bytes: int = None):
        if quota_bytes:
            avg_entry_size = 1024 # Conservative estimate
            max_entries = max(1, quota_bytes // avg_entry_size)
        else:
            max_entries = 100 # Default

        if len(self.concepts) > max_entries:
            # Remove lowest confidence
            sorted_ids = sorted(self.concepts.keys(), key=lambda k: self.concepts[k].confidence)
            for k in sorted_ids[:len(self.concepts) - max_entries]:
                del self.concepts[k]

    def to_dict(self) -> Dict[str, Any]:
        return {"concepts": {k: v.to_dict() for k, v in self.concepts.items()}}

    def _save_state(self):
        try:
            with open(self.persistence_dir / "sound_concept_state.json", 'w') as f:
                json.dump(self.to_dict(), f, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            logger.error(f"[SOUND MEM] Failed to save state: {e}")

    def _load_state(self):
        path = self.persistence_dir / "sound_concept_state.json"
        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    for k, v in data.get("concepts", {}).items():
                        self.concepts[k] = SoundConceptEntry.from_dict(v)
            except Exception as e: logger.error(f"[SOUND MEM] Load error: {e}")

class SoundClassMemory: # Keep old name or integrate?
    # Spec says SoundConceptMemory
    pass

class AudioManager:
    def __init__(self, persistence_dir: str):
        self.persistence_dir = Path(persistence_dir)
        try:
            self.persistence_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"[AUDIO] Failed to create storage directory {persistence_dir}: {e}")
        self.percepts, self.phonetic_lexemes, self.voice_templates = {}, {}, {}
        self.phonetic_memory = PhoneticMemory()
        self.sound_concept_memory = SoundConceptMemory(persistence_dir)
        self._load_state()
        self._bootstrap_lineage()
    def _bootstrap_lineage(self):
        if not self.percepts:
            for name in BASE_AUDIO_PERCEPTS:
                self.percepts[name] = AudioPerceptTemplate(name)
                self.percepts[name].confidence = 1.0
        if not self.phonetic_lexemes:
            for sig in BASE_PHONETIC_SEEDS:
                self.phonetic_lexemes[sig] = PhoneticLexemeTemplate(sig)
                self.phonetic_lexemes[sig].confidence = 1.0
    def record_audio_interaction(self, audio_features: Dict[str, Any], text_content: str = None, intent: str = None):
        # Update sound concept memory (Section II)
        if "acoustic_vector" in audio_features:
            self.sound_concept_memory.add_or_update_concept(
                audio_features["acoustic_vector"],
                audio_features.get("category", "unknown"),
                intent,
                text_content
            )

        signature = audio_features.get("phonetic_signature", "unknown")
        if signature not in self.phonetic_lexemes: self.phonetic_lexemes[signature] = PhoneticLexemeTemplate(signature)
        p = self.phonetic_lexemes[signature]
        if text_content and text_content not in p.associated_text_forms: p.associated_text_forms.append(text_content)
        if intent:
            p.intent_histogram[intent] += 1
            if intent not in self.voice_templates: self.voice_templates[intent] = VoiceIntentTemplate(intent)
            vt = self.voice_templates[intent]
            vt.usage_count += 1
            vt.stability = min(1.0, vt.stability + 0.05)
    def _save_state(self):
        state = {
            "percepts": {k: v.to_dict() for k, v in self.percepts.items()},
            "phonetic_lexemes": {k: v.to_dict() for k, v in self.phonetic_lexemes.items()},
            "voice_templates": {k: v.to_dict() for k, v in self.voice_templates.items()},
            "phonetic_memory": self.phonetic_memory.to_dict()
        }
        try:
            with open(self.persistence_dir / "audio_state.json", 'w') as f:
                json.dump(state, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            logger.error(f"[AUDIO] Failed to save state: {e}")
        self.sound_concept_memory._save_state()
    def _load_state(self):
        path = self.persistence_dir / "audio_state.json"
        if not path.exists(): return
        try:
            with open(path, 'r') as f: state = json.load(f)
            for k, v in state.get("percepts", {}).items(): self.percepts[k] = AudioPerceptTemplate.from_dict(v)
            for k, v in state.get("phonetic_lexemes", {}).items(): self.phonetic_lexemes[k] = PhoneticLexemeTemplate.from_dict(v)
            for k, v in state.get("voice_templates", {}).items(): self.voice_templates[k] = VoiceIntentTemplate.from_dict(v)
            if "phonetic_memory" in state:
                self.phonetic_memory = PhoneticMemory.from_dict(state["phonetic_memory"])
        except Exception as e: logger.error(f"[AUDIO] Failed to load state: {e}")
    def save_state(self): self._save_state()
    def prune(self, quota_bytes: int = None):
        to_remove = [k for k, v in self.phonetic_lexemes.items() if v.confidence < 0.3 and not v.associated_text_forms]
        for k in to_remove: del self.phonetic_lexemes[k]
        self.sound_concept_memory.prune(quota_bytes=quota_bytes)


# ============================================================================
# 6. VISION COMPETENCY (from offline_ai_vision.py)
# ============================================================================

class VisionPerceptTemplate:
    def __init__(self, name: str):
        self.name, self.feature_signature, self.confidence, self.stability, self.usage_count = name, {}, 0.5, 0.0, 0
    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "feature_signature": self.feature_signature, "confidence": self.confidence, "stability": self.stability, "usage_count": self.usage_count}
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VisionPerceptTemplate':
        t = cls(data["name"])
        t.feature_signature, t.confidence, t.stability, t.usage_count = data.get("feature_signature", {}), data.get("confidence", 0.5), data.get("stability", 0.0), data.get("usage_count", 0)
        return t

class VisualConceptMemory:
    def __init__(self):
        from collections import defaultdict
        self.raw_percepts = defaultdict(list)
        self.concepts = {} # name -> {percept_cluster, label_hypotheses, confidence}
        self.grounding = [] # List of (intent, lexeme, visual_concept, sound_class)

    def record_percept(self, percept_vector, label):
        """
        Store raw percept vectors for clustering and later promotion.
        """
        self.raw_percepts[label].append(percept_vector)

    def add_grounding(self, intent, lexeme, visual_concept, sound_class):
        self.grounding.append({
            "intent": intent, "lexeme": lexeme,
            "visual_concept": visual_concept, "sound_class": sound_class,
            "timestamp": time.time()
        })

    def prune_low_value(self, target_ratio=0.3, quota_bytes: int = None):
        """
        Prune low-confidence visual concepts.
        """
        if not self.concepts: return

        if quota_bytes:
            avg_entry_size = 2048 # Visual concepts carry more data (clusters)
            max_entries = max(1, quota_bytes // avg_entry_size)
            num_to_remove = max(0, len(self.concepts) - max_entries)
        else:
            num_to_remove = int(len(self.concepts) * target_ratio)

        if num_to_remove > 0:
            sorted_ids = sorted(self.concepts.keys(), key=lambda k: self.concepts[k].get("confidence", 0.0))
            for i in range(min(num_to_remove, len(sorted_ids))):
                k = sorted_ids[i]
                if k in self.raw_percepts:
                    del self.raw_percepts[k]
                del self.concepts[k]

        # Also prune raw_percepts that have no concept and are old/too many
        for label in list(self.raw_percepts.keys()):
            if label not in self.concepts and len(self.raw_percepts[label]) > 10:
                self.raw_percepts[label] = self.raw_percepts[label][-5:] # Keep only latest

    def to_dict(self) -> Dict[str, Any]:
        return {"concepts": self.concepts, "grounding": self.grounding}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VisualConceptMemory':
        vcm = cls()
        vcm.concepts = data.get("concepts", {})
        vcm.grounding = data.get("grounding", [])
        return vcm

class VisionManager:
    def __init__(self, genome: Any, persistence_dir: Optional[str] = None):
        self.genome = genome
        self.persistence_dir = Path(persistence_dir) if persistence_dir else None
        if self.persistence_dir:
            try:
                self.persistence_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"[VISION] Failed to create storage directory {self.persistence_dir}: {e}")
        self.last_analysis, self.percept_templates, self.hybrids = {}, {}, {}
        self.concept_memory = VisualConceptMemory()
        self._load_state()
        self._bootstrap_lineage()
    def _bootstrap_lineage(self):
        if not self.percept_templates:
            for name in BASE_VISION_PERCEPTS:
                self.percept_templates[name] = VisionPerceptTemplate(name)
                self.percept_templates[name].confidence = 1.0
    def _get_val(self, attr):
        if isinstance(self.genome, dict): return self.genome.get(attr, 0.5)
        return getattr(self.genome, attr, 0.5)
    def _set_val(self, attr, val):
        if isinstance(self.genome, dict): self.genome[attr] = val
        else: setattr(self.genome, attr, val)
    def process_visual_input(self, image_path: str, tool_func) -> Dict[str, Any]:
        try:
            tool_func(filepath=image_path)
            # Simulated detection with raw feature generation (randomized for now)
            detected_objects = ["detected_object_placeholder"]
            raw_features = np.random.randn(64).tolist()

            analysis = {"objects": detected_objects, "focus_level": self._get_val("focus"), "detail_captured": self._get_val("detail_orientation")}
            self.last_analysis = analysis

            for obj in detected_objects:
                # Percept-First: Record raw observation
                self.concept_memory.record_percept(raw_features, obj)

                if obj not in self.percept_templates:
                    self.percept_templates[obj] = VisionPerceptTemplate(obj)
                t = self.percept_templates[obj]
                t.usage_count += 1
                t.stability = min(1.0, t.stability + 0.05)

                # Clustering/Promotion Trigger
                if t.usage_count % 3 == 0:
                    self.cluster_and_promote(obj)

            self._set_val("focus", min(1.0, self._get_val("focus") + 0.01))
            self._set_val("detail_orientation", min(1.0, self._get_val("detail_orientation") + 0.01))
            return analysis
        except Exception as e: return {}

    def cluster_and_promote(self, label: str):
        """Percept-first visual concept clustering and promotion"""
        percepts = self.concept_memory.raw_percepts[label]
        if len(percepts) >= 3:
            # Calculate centroid for semantic stability
            centroid = np.mean(percepts, axis=0).tolist()

            if label not in self.concept_memory.concepts:
                self.concept_memory.concepts[label] = {
                    "percept_cluster": percepts,
                    "label_hypotheses": {label: 1.0},
                    "confidence": 0.8,
                    "centroid": centroid
                }
                logger.info(f"[VISION] Clustered and promoted visual concept: {label}")
            else:
                # Update existing concept centroid (moving average)
                old_c = np.array(self.concept_memory.concepts[label].get("centroid", centroid))
                self.concept_memory.concepts[label]["centroid"] = (0.7 * old_c + 0.3 * np.array(centroid)).tolist()
                self.concept_memory.concepts[label]["confidence"] = min(1.0, self.concept_memory.concepts[label]["confidence"] + 0.05)

            # Flush raw percepts after stable cluster is formed
            self.concept_memory.raw_percepts[label] = []

    def record_grounding(self, intent: str, lexeme: str, visual_concept: str, sound_class: str = "speech"):
        """Expand grounding: bind (intent, lexeme, visual_concept, sound_class)"""
        self.concept_memory.add_grounding(intent, lexeme, visual_concept, sound_class)

    def process(self, frame):
        """Process raw camera frame from InterfaceRuntime"""
        # In a production environment, this would run object detection/face recognition.
        # For the procedural companion, we'll acknowledge the presence of visual data
        # by slightly shifting focus/detail parameters.
        self._set_val("focus", min(1.0, self._get_val("focus") + 0.001))
        self._set_val("detail_orientation", min(1.0, self._get_val("detail_orientation") + 0.001))

    def _save_state(self):
        if not self.persistence_dir: return
        state = {
            "percept_templates": {k: v.to_dict() for k, v in self.percept_templates.items()},
            "hybrids": self.hybrids,
            "concept_memory": self.concept_memory.to_dict()
        }
        try:
            with open(self.persistence_dir / "vision_state.json", 'w') as f:
                json.dump(state, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            logger.error(f"[VISION] Failed to save state: {e}")
    def _load_state(self):
        if not self.persistence_dir or not (self.persistence_dir / "vision_state.json").exists(): return
        try:
            with open(self.persistence_dir / "vision_state.json", 'r') as f: state = json.load(f)
            for k, v in state.get("percept_templates", {}).items(): self.percept_templates[k] = VisionPerceptTemplate.from_dict(v)
            self.hybrids = state.get("hybrids", {})
            if "concept_memory" in state:
                self.concept_memory = VisualConceptMemory.from_dict(state["concept_memory"])
        except Exception as e: logger.error(f"[VISION] Failed to load state: {e}")
    def save_state(self): self._save_state()
    def prune(self, target_ratio=0.3, quota_bytes: int = None):
        # Prune percept templates
        to_remove = [k for k, v in self.percept_templates.items() if v.confidence < 0.3 and v.usage_count < 2]
        for k in to_remove: del self.percept_templates[k]
        # Prune concept memory
        self.concept_memory.prune_low_value(target_ratio, quota_bytes=quota_bytes)

    def get_competency_report(self) -> Dict[str, float]: return self.genome.to_dict() if hasattr(self.genome, 'to_dict') else self.genome


# ============================================================================
# 7. VOICE PROFILES (from offline_ai_voice_profiles.py)
# ============================================================================

class VoiceProfile:
    def __init__(self, id: str, name: Optional[str] = None):
        self.id, self.name, self.interaction_count, self.last_seen, self.first_seen, self.attributes = id, name or f"User_{id[:6]}", 0, 0.0, time.time(), {}
        self.fingerprint = id  # Alias for compatibility with runtime
    def to_dict(self) -> Dict[str, Any]:
        return {"id": self.id, "name": self.name, "interaction_count": self.interaction_count, "last_seen": self.last_seen, "first_seen": self.first_seen, "attributes": self.attributes}
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'VoiceProfile':
        profile = cls(data["id"], data.get("name"))
        profile.interaction_count, profile.last_seen, profile.first_seen, profile.attributes = data.get("interaction_count", 0), data.get("last_seen", 0.0), data.get("first_seen", time.time()), data.get("attributes", {})
        return profile

class VoiceProfileManager:
    def __init__(self, storage_dir: str):
        self.storage_dir = Path(storage_dir)
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"[VOICE] Failed to create storage directory {storage_dir}: {e}")
        self.profiles_file = self.storage_dir / "voice_profiles.json"
        self.profiles: Dict[str, VoiceProfile] = {}
    def identify_voice(self, fingerprint: str) -> VoiceProfile:
        if fingerprint in self.profiles: profile = self.profiles[fingerprint]
        else:
            profile = VoiceProfile(fingerprint)
            self.profiles[fingerprint] = profile
        profile.interaction_count += 1
        profile.last_seen = time.time()
        self.save_profiles()
        return profile
    def save_profiles(self, session_id: str = ""):
        try:
            data = {"session_id": session_id, "profiles": {fid: p.to_dict() for fid, p in self.profiles.items()}}
            add_version_metadata(data, "voice_profiles")
            with open(self.profiles_file, 'w') as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e: logger.error(f"[VOICE] Failed to save profiles: {e}")
    def load_profiles(self, highest_session_id: str = ""):
        if not self.profiles_file.exists(): return
        try:
            with open(self.profiles_file, 'r') as f: data = json.load(f)
            data = migration_engine.migrate("voice_profiles", data, STATE_VERSION)
            loaded_session = data.get("session_id", "")
            if highest_session_id and loaded_session and loaded_session != highest_session_id: return
            profiles_data = data.get("profiles", data)
            for fid, p_data in profiles_data.items(): self.profiles[fid] = VoiceProfile.from_dict(p_data)
        except Exception as e: logger.error(f"[VOICE] Failed to load profiles: {e}")


# ============================================================================
# 8. LANGUAGE BOOTSTRAP (from offline_ai_language.py)
# ============================================================================

class LanguageTier(Enum):
    TRANSCENDENCE = "transcendence"
    HARMONY = "harmony"
    ORDER = "order"

@dataclass
class CommunicationIntent:
    name: str
    description: str
    sub_intents: List[str] = field(default_factory=list)
    activation_patterns: List[str] = field(default_factory=list)
    response_strategy: str = ""
    spirit: float = 0.5
    develop: float = 0.5
    rules: float = 0.5

class TranscendenceTier:
    def __init__(self):
        self.intents = self._build_intent_library()
    def _build_intent_library(self) -> Dict[str, CommunicationIntent]:
        return {
            "INFORM": CommunicationIntent(name="INFORM", description="Provide factual or explanatory information", activation_patterns=[r"what is", r"explain", r"tell me", r"define", r"how does"], response_strategy="provide_clear_factual_response", spirit=0.3, develop=0.7, rules=0.6),
            "QUESTION": CommunicationIntent(name="QUESTION", description="Request information via direct questioning", activation_patterns=[r"\?$", r"can you", r"do you know", r"what", r"why", r"how"], response_strategy="answer_question", spirit=0.4, develop=0.6, rules=0.6),
            "SUMMARIZE": CommunicationIntent(name="SUMMARIZE", description="Request or provide condensed explanation", activation_patterns=[r"summarize", r"tl;dr", r"in short", r"briefly"], response_strategy="summarize_content", spirit=0.3, develop=0.7, rules=0.7),
            "REQUEST": CommunicationIntent(name="REQUEST", description="Ask for an action or assistance", activation_patterns=[r"can you", r"please", r"help me", r"show me"], response_strategy="acknowledge_and_fulfill", spirit=0.5, develop=0.5, rules=0.6),
            "DIRECT": CommunicationIntent(name="DIRECT", description="Give explicit instruction or command", activation_patterns=[r"do this", r"create", r"build", r"generate", r"write"], response_strategy="execute_and_confirm", spirit=0.2, develop=0.4, rules=0.8),
            "PLAN": CommunicationIntent(name="PLAN", description="Plan steps or future actions", activation_patterns=[r"let's plan", r"what should we do", r"next steps"], response_strategy="plan_steps", spirit=0.4, develop=0.7, rules=0.6),
            "CONNECT": CommunicationIntent(name="CONNECT", description="Build rapport or greeting", activation_patterns=[r"^hi", r"hello", r"hey", r"how are you"], response_strategy="warm_relational_response", spirit=0.9, develop=0.3, rules=0.2),
            "THANK": CommunicationIntent(name="THANK", description="Express gratitude", activation_patterns=[r"thank", r"thanks", r"appreciate it"], response_strategy="acknowledge_gratitude", spirit=0.9, develop=0.2, rules=0.2),
            "APOLOGIZE": CommunicationIntent(name="APOLOGIZE", description="Express apology or regret", activation_patterns=[r"sorry", r"my fault", r"apologize"], response_strategy="accept_apology", spirit=0.9, develop=0.3, rules=0.3),
            "EXPRESS": CommunicationIntent(name="EXPRESS", description="Share emotion or feeling", activation_patterns=[r"i feel", r"i'm sad", r"i'm happy", r"frustrated"], response_strategy="acknowledge_emotion_first", spirit=0.8, develop=0.4, rules=0.3),
            "REACT": CommunicationIntent(name="REACT", description="React emotionally to something", activation_patterns=[r"wow", r"oh no", r"that's cool", r"nice"], response_strategy="mirror_reaction", spirit=0.7, develop=0.3, rules=0.2),
            "AGREE": CommunicationIntent(name="AGREE", description="Express agreement", activation_patterns=[r"yes", r"exactly", r"that's right", r"agreed"], response_strategy="reinforce_agreement", spirit=0.6, develop=0.4, rules=0.4),
            "DENY": CommunicationIntent(name="DENY", description="Express negation or refusal", activation_patterns=[r"no", r"not really", r"don't think so"], response_strategy="gentle_refusal", spirit=0.4, develop=0.4, rules=0.6),
            "CHALLENGE": CommunicationIntent(name="CHALLENGE", description="Disagree or question strongly", activation_patterns=[r"i disagree", r"that's wrong", r"are you sure"], response_strategy="engage_thoughtfully_not_defensively", spirit=0.4, develop=0.7, rules=0.6),
            "VALIDATE": CommunicationIntent(name="VALIDATE", description="Confirm correctness or understanding", activation_patterns=[r"is this right", r"does this make sense", r"correct"], response_strategy="confirm_or_correct_gently", spirit=0.5, develop=0.6, rules=0.7),
            "CONFIRM": CommunicationIntent(name="CONFIRM", description="Confirm success or satisfaction", activation_patterns=[r"that worked", r"perfect", r"exactly what i needed"], response_strategy="acknowledge_success", spirit=0.6, develop=0.4, rules=0.4),
            "EVALUATE": CommunicationIntent(name="EVALUATE", description="Judge or assess quality", activation_patterns=[r"what do you think", r"is this good", r"rate this"], response_strategy="provide_evaluation", spirit=0.4, develop=0.7, rules=0.6),
            "REFLECT": CommunicationIntent(name="REFLECT", description="Think aloud or reflect internally", activation_patterns=[r"i think", r"i wonder", r"maybe"], response_strategy="reflect_back", spirit=0.6, develop=0.6, rules=0.4),
            "NARRATE": CommunicationIntent(name="NARRATE", description="Tell a story or recount events", activation_patterns=[r"let me tell you", r"so yesterday", r"once"], response_strategy="narrative_response", spirit=0.6, develop=0.5, rules=0.4),
            "EXPLORE": CommunicationIntent(name="EXPLORE", description="Brainstorm or explore ideas", activation_patterns=[r"what if", r"let's explore", r"imagine"], response_strategy="collaborative_exploration", spirit=0.6, develop=0.8, rules=0.3),
        }
    def identify_intent(self, text: str) -> Tuple[str, float, Dict[str, float]]:
        text_lower = text.lower().strip()
        scores = {}
        for name, intent in self.intents.items():
            score = 0.0
            matches = 0
            for pattern in intent.activation_patterns:
                if re.search(pattern, text_lower):
                    score += 1.0
                    matches += 1
            if intent.activation_patterns: score /= len(intent.activation_patterns)
            if matches > 1: score *= (1 + 0.1 * matches)
            scores[name] = min(1.0, score)
        top_intent = max(scores, key=scores.get) if scores and max(scores.values()) > 0 else "INFORM"
        confidence = scores[top_intent] if top_intent in scores else 0.3
        intent_obj = self.intents[top_intent]
        return top_intent, confidence, {"spirit": intent_obj.spirit, "develop": intent_obj.develop, "rules": intent_obj.rules}
    def get_response_strategy(self, intent_name: str) -> str:
        return self.intents[intent_name].response_strategy if intent_name in self.intents else "default_helpful_response"
    def get_strategy(self, intent_name: str) -> str: return self.get_response_strategy(intent_name)
    def register_hybrid(self, name, base_pair):
        base_a, base_b = base_pair
        self.intents[name] = CommunicationIntent(name=name, description=f"Hybrid of {base_a} + {base_b}", spirit=(self.intents[base_a].spirit + self.intents[base_b].spirit) / 2, develop=(self.intents[base_a].develop + self.intents[base_b].develop) / 2, rules=(self.intents[base_a].rules + self.intents[base_b].rules) / 2)

@dataclass
class LanguagePrinciple:
    name: str
    description: str
    weight: float = 0.5
    nature_aspect: float = 0.5
    spirit_aspect: float = 0.5
    logos_aspect: float = 0.5

class HarmonyTier:
    def __init__(self):
        self.principles = {
            "COHERENCE": LanguagePrinciple(name="COHERENCE", description="Coherent", logos_aspect=0.9),
            "RELEVANCE": LanguagePrinciple(name="RELEVANCE", description="Relevant", spirit_aspect=0.6, logos_aspect=0.7),
            "CLARITY": LanguagePrinciple(name="CLARITY", description="Clear", nature_aspect=0.7, logos_aspect=0.8),
            "NATURALNESS": LanguagePrinciple(name="NATURALNESS", description="Natural", nature_aspect=0.9, spirit_aspect=0.6),
            "EMPATHY": LanguagePrinciple(name="EMPATHY", description="Empathetic", spirit_aspect=0.9),
            "STRUCTURE": LanguagePrinciple(name="STRUCTURE", description="Structured", logos_aspect=0.9),
            "APPROPRIATENESS": LanguagePrinciple(name="APPROPRIATENESS", description="Appropriate", nature_aspect=0.6, spirit_aspect=0.7, logos_aspect=0.6)
        }
        self.voice_genome = {"warmth": 0.65, "formality": 0.45, "curiosity": 0.60, "assertiveness": 0.50, "empathy": 0.70, "precision": 0.55}
    def compute_style_vector(self, intent: str, inner_weights: Dict[str, float], personalized_params: Dict[str, Dict[str, float]] = None) -> Dict[str, float]:
        style = dict(self.voice_genome)
        spirit, develop, rules = inner_weights.get("spirit", 0.5), inner_weights.get("develop", 0.5), inner_weights.get("rules", 0.5)
        style["warmth"] = (style["warmth"] + spirit) / 2
        style["empathy"] = (style["empathy"] + spirit) / 2
        style["curiosity"] = (style["curiosity"] + develop) / 2
        style["formality"] = (style["formality"] + rules) / 2
        style["precision"] = (style["precision"] + rules) / 2
        if personalized_params:
            flat = {}
            for s in ["communication", "voice_gnome", "expression_style"]:
                if s in personalized_params: flat.update(personalized_params[s])
            for k, v in flat.items():
                if k in style: style[k] = 0.7 * v + 0.3 * style[k]
                else: style[k] = v
        return style
    def update_voice_genome(self, updates: Dict[str, float]):
        for k, v in updates.items():
            if k in self.voice_genome: self.voice_genome[k] = max(0.0, min(1.0, v))

@dataclass
class ResponsePattern:
    name: str
    template: str
    variants: List[str] = field(default_factory=list)
    conditions: Dict[str, Any] = field(default_factory=dict)
    warmth_min: float = 0.0
    formality_min: float = 0.0
    formality_max: float = 1.0

class OrderTier:
    def __init__(self, evolution_engine: Optional[SelfGenerativeEvolution] = None):
        self.evolution_engine = evolution_engine
        self.patterns = self._build_patterns()
        self.vocabulary = {
            "affirmatives": {"warm": ["absolutely", "of course"], "neutral": ["yes", "indeed"], "formal": ["affirmative", "correct"]},
            "negatives": {"warm": ["I'm afraid not"], "neutral": ["no", "incorrect"], "formal": ["negative", "inaccurate"]},
            "transitions": {"warm": ["so", "alright"], "neutral": ["therefore", "thus"], "formal": ["accordingly", "hence"]},
            "hedges": {"warm": ["I think"], "neutral": ["likely", "perhaps"], "formal": ["it appears that"]},
            "emphasis": {"warm": ["really", "totally"], "neutral": ["certainly", "indeed"], "formal": ["undoubtedly", "manifestly"]}
        }
        self.connectors = {"addition": ["also", "furthermore"], "contrast": ["however", "but"], "cause": ["because", "since"], "effect": ["therefore", "so"], "example": ["for example", "such as"], "sequence": ["first", "then"]}
        self.learned_templates = defaultdict(lambda: defaultdict(list))
    def _build_patterns(self):
        return {
            "greeting": [ResponsePattern(name="warm_greeting", template="Hi there! {continuation}", warmth_min=0.6), ResponsePattern(name="neutral_greeting", template="Hello. {continuation}", warmth_min=0.3, formality_min=0.4), ResponsePattern(name="formal_greeting", template="Greetings. {continuation}", formality_min=0.7)],
            "acknowledgment": [ResponsePattern(name="warm_ack", template="Absolutely! {continuation}", warmth_min=0.6), ResponsePattern(name="neutral_ack", template="Yes, {continuation}", warmth_min=0.3), ResponsePattern(name="formal_ack", template="Understood. {continuation}", formality_min=0.7)],
            "explanation_start": [ResponsePattern(name="curious_explain", template="That's a great question! {explanation}", warmth_min=0.5), ResponsePattern(name="direct_explain", template="{explanation}", formality_min=0.4), ResponsePattern(name="structured_explain", template="Let me break this down: {explanation}", formality_min=0.5)],
            "empathy": [ResponsePattern(name="strong_empathy", template="I understand how you feel. {continuation}", warmth_min=0.7), ResponsePattern(name="mild_empathy", template="I see. {continuation}", warmth_min=0.4)],
            "followup": [ResponsePattern(name="curious_followup", template="Would you like to know more about {topic}?", warmth_min=0.5), ResponsePattern(name="helpful_followup", template="Is there anything else I can help with?", warmth_min=0.4)],
            "clarification": [ResponsePattern(name="gentle_clarify", template="Just to make sure I understand - {question}", warmth_min=0.5), ResponsePattern(name="direct_clarify", template="What specifically do you mean by {term}?", formality_min=0.4)]
        }
    def select_pattern(self, category: str, style: Dict[str, float], intent: str = None) -> Optional[ResponsePattern]:
        if self.evolution_engine:
            learned = self.evolution_engine.get_suggestion("language", f"{intent}_{category}")
            if learned: return ResponsePattern(name="learned", template=learned)
        if intent and intent in self.learned_templates and category in self.learned_templates[intent]:
            templates = self.learned_templates[intent][category]
            if templates: return ResponsePattern(name="learned", template=random.choice(templates))
        if category not in self.patterns: return None
        candidates = []
        warmth, formality = style.get("warmth", 0.5), style.get("formality", 0.5)
        for p in self.patterns[category]:
            if warmth >= p.warmth_min and p.formality_min <= formality <= p.formality_max: candidates.append(p)
        return candidates[0] if candidates else self.patterns[category][0]
    def get_vocabulary_word(self, category: str, subcategory: str, style: Dict[str, float]) -> str:
        if category not in self.vocabulary or subcategory not in self.vocabulary[category]: return ""
        formality = style.get("formality", 0.5)
        tone = "formal" if formality > 0.65 else ("warm" if formality < 0.35 else "neutral")
        words = self.vocabulary[category].get(tone, [])
        return random.choice(words) if words else ""

class IntentEvolutionRegistry:
    def __init__(self, base_intents):
        self.evo = SelfGenerativeEvolution()
        self.base_intents = list(base_intents)
    def observe(self, intent_a, intent_b, template_learner=None, response_text=None):
        self.evo.evolution_registry.observe(intent_a, intent_b)
        if template_learner and response_text: template_learner.observe(intent_a, "general", response_text)
    def get_hybrids(self): return self.evo.evolution_registry.hybrids
    def get_stats(self): return {"base_intents": len(self.base_intents), "hybrid_intents": len(self.evo.evolution_registry.hybrids), "co_occurrences": len(self.evo.evolution_registry.co_occurrence_counts)}
    def promote_stable_hybrids(self, threshold=5):
        new_intents = {}
        for (a, b), count in self.evo.evolution_registry.co_occurrence_counts.items():
            if count >= threshold: new_intents[f"{a}_{b}_HYBRID"] = {"base": (a, b), "strategy": None, "templates": {}}
        return new_intents
    def get_stable_hybrid(self, intent_a, intent_b):
        key = f"{intent_a}_{intent_b}_HYBRID"
        return key if key in self.evo.evolution_registry.hybrids else None

class LanguageTemplateLearner:
    def __init__(self): self.evo = SelfGenerativeEvolution()
    def extract_template(self, text): return self.evo.template_learner.extract_template(text)
    def observe(self, intent, category, response_text): self.evo.template_learner.observe("language", f"{intent}_{category}", response_text)
    @property
    def templates(self):
        old_format = defaultdict(lambda: defaultdict(list))
        for cat, tmpls in self.evo.template_learner.templates["language"].items():
            if "_" in cat:
                intent, category = cat.split("_", 1)
                old_format[intent][category] = tmpls
        return old_format

class CorpusBootstrap:
    def __init__(self, corpus_path): self.corpus_path = corpus_path
    def load_conversations(self):
        try:
            with open(self.corpus_path, "r", encoding="utf-8") as f: return json.load(f)
        except Exception: return []
    def extract_user_messages(self, data):
        messages = []
        for convo in data:
            for node in convo.get("mapping", {}).values():
                msg = node.get("message")
                if msg and msg.get("author", {}).get("role") == "user":
                    parts = msg.get("content", {}).get("parts", [])
                    if parts: messages.append(parts[0])
        return messages

class LanguageBootstrap:
    def __init__(self, persistence_dir: str = "./offline_ai_data", lexicon: Optional[LexiconManager] = None):
        self.persistence_dir = Path(persistence_dir)
        try:
            self.persistence_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"[LANGUAGE] Failed to create storage directory {persistence_dir}: {e}")
        self.lexicon = lexicon
        self.transcendence = TranscendenceTier()
        self.intent_evolution = IntentEvolutionRegistry(self.transcendence.intents.keys())
        self.harmony = HarmonyTier()
        self.order = OrderTier(evolution_engine=self.intent_evolution.evo)
        self.conversation_context, self.current_intent, self.current_style = [], "", {}
        self.corpus_path = "/storage/emulated/0/aurora/conversations.json"
        self._last_intent, self.high_storage_pressure = None, False
        self._bootstrap_from_corpus()
    def _bootstrap_from_corpus(self):
        if not os.path.exists(self.corpus_path): return
        bootstrap = CorpusBootstrap(self.corpus_path)
        self.template_learner = LanguageTemplateLearner()
        messages = bootstrap.extract_user_messages(bootstrap.load_conversations())
        last_intent = None
        for text in messages:
            try:
                intent, _, _ = self.transcendence.identify_intent(text)
                if last_intent: self.intent_evolution.observe(last_intent, intent)
                last_intent = intent
            except Exception: continue
        threshold = 10 if self.high_storage_pressure else 5
        hybrids = self.intent_evolution.promote_stable_hybrids(threshold=threshold)
        for name, meta in hybrids.items(): self.transcendence.register_hybrid(name, meta["base"])
        self.order.learned_templates = self.template_learner.templates
    def process_input(self, text: str, personalized_params: Dict[str, Dict[str, float]] = None) -> Dict[str, Any]:
        # 0. Lexical analysis for unknown tokens and context
        words = re.findall(r'\w+', text.lower())
        unknown_tokens = []
        if self.lexicon:
            unknown_tokens = [w for w in words if w not in self.lexicon.entries]

        intent, confidence, weights = self.transcendence.identify_intent(text)

        # Lexical intent inference: if confidence is low, check lexicon for intent bias
        if confidence < 0.5 and self.lexicon:
            lexical_biases = defaultdict(float)
            for w in words:
                if w in self.lexicon.entries:
                    for i, bias in self.lexicon.entries[w].intent_map.items():
                        lexical_biases[i] += bias

            if lexical_biases:
                best_lex_intent = max(lexical_biases, key=lexical_biases.get)
                if lexical_biases[best_lex_intent] > 0.5:
                    # Blend or override if very strong
                    intent = best_lex_intent
                    confidence = min(1.0, confidence + 0.2)
        hybrid = self.intent_evolution.get_stable_hybrid(intent, intent)
        if hybrid:
            intent = hybrid
            confidence = min(1.0, confidence + 0.15)
        strategy = self.transcendence.get_response_strategy(intent)
        if strategy is None and "_HYBRID" in intent:
            try:
                base_a, base_b = intent.split("_", 2)[:2]
                strategy = self.transcendence.get_strategy(base_a) or self.transcendence.get_strategy(base_b)
            except Exception: pass
        if strategy is None: strategy = "default_response"
        if self._last_intent:
            try: self.intent_evolution.observe(self._last_intent, intent)
            except Exception: pass
        self._last_intent = intent
        style = self.harmony.compute_style_vector(intent, weights, personalized_params)
        pattern_categories = self._determine_pattern_needs(intent, text)
        selected_patterns = {}
        for cat in pattern_categories:
            pattern = self.order.select_pattern(cat, style, intent=intent)
            if pattern: selected_patterns[cat] = pattern.template
        self.current_intent, self.current_style = intent, style
        self.conversation_context.append({"role": "user", "text": text, "intent": intent, "style": style})
        return {"intent": intent, "intent_confidence": confidence, "inner_weights": weights, "response_strategy": strategy, "style": style, "patterns": selected_patterns, "vocabulary_tone": self._get_vocabulary_tone(style)}
    def _determine_pattern_needs(self, intent: str, text: str) -> List[str]:
        needs = []
        if intent == "CONNECT": needs.append("greeting")
        if intent in ["REQUEST", "DIRECT"]: needs.append("acknowledgment")
        if intent in ["INFORM", "EXPLORE", "QUESTION"]: needs.append("explanation_start")
        if intent == "EXPRESS": needs.append("empathy")
        if intent in ["VALIDATE", "CONFIRM"]: needs.append("clarification")
        needs.append("followup")
        return needs
    def _get_vocabulary_tone(self, style: Dict[str, float]) -> str:
        f = style.get("formality", 0.5)
        return "formal" if f > 0.65 else ("warm" if f < 0.35 else "neutral")
    def generate_response_skeleton(self, analysis: Dict[str, Any], core_content: str) -> str:
        parts = []
        patterns, style = analysis.get("patterns", {}), analysis.get("style", {})
        if "greeting" in patterns: parts.append(patterns["greeting"].format(continuation="").strip())
        elif "acknowledgment" in patterns: parts.append(patterns["acknowledgment"].format(continuation="").strip())
        elif "empathy" in patterns: parts.append(patterns["empathy"].format(continuation="", emotion="challenging" if style.get("warmth", 0.5) > 0.5 else "difficult").strip())
        if "explanation_start" in patterns and core_content: parts.append(patterns["explanation_start"].format(explanation=core_content))
        else: parts.append(core_content)
        response = " ".join(parts).strip()
        response = re.sub(r'\s+', ' ', response)
        response = re.sub(r'\s+([.,!?])', r'\1', response)
        return response
    def get_vocabulary(self, category: str, subcategory: str) -> str: return self.order.get_vocabulary_word(category, subcategory, self.current_style)
    def get_connector(self, connector_type: str) -> str:
        connectors = self.order.connectors.get(connector_type, [])
        return random.choice(connectors) if connectors else ""
    def set_promotion_pressure(self, active: bool): self.high_storage_pressure = active
    def update_from_learning(self, personalized_params: Dict[str, Dict[str, float]]):
        updates = {}
        for s in ["communication", "voice_gnome", "expression_style"]:
            if s in personalized_params:
                for k, v in personalized_params[s].items():
                    if k == "technical_depth": updates["precision"] = v
                    else: updates[k] = v
        if updates: self.harmony.update_voice_genome(updates)
    def get_state(self) -> Dict[str, Any]: return {"voice_genome": self.harmony.voice_genome, "current_intent": self.current_intent, "current_style": self.current_style, "conversation_length": len(self.conversation_context), "available_intents": list(self.transcendence.intents.keys()), "available_pattern_categories": list(self.order.patterns.keys())}
    def save_state(self, session_id: str = ""):
        state = {"session_id": session_id, "voice_genome": self.harmony.voice_genome, "conversation_context": self.conversation_context[-10:]}
        add_version_metadata(state, "language")
        with open(self.persistence_dir / "language_bootstrap_state.json", 'w') as f: json.dump(state, f, indent=2)
        if self.intent_evolution and self.intent_evolution.evo: self.intent_evolution.evo._save_state()
    def load_state(self, highest_session_id: str = ""):
        path = self.persistence_dir / "language_bootstrap_state.json"
        if not path.exists(): return
        try:
            with open(path, 'r') as f: state = json.load(f)
            state = migration_engine.migrate("language", state, STATE_VERSION)
            loaded_session = state.get("session_id", "")
            if highest_session_id and loaded_session and loaded_session != highest_session_id: return
            if "voice_genome" in state: self.harmony.voice_genome = state["voice_genome"]
        except Exception as e: logger.error(f"[LANGUAGE] Failed to load state: {e}")

def create_language_bootstrap(storage_dir: str = "./offline_ai_data") -> LanguageBootstrap: return LanguageBootstrap(storage_dir)


# ============================================================================
# 9. PROCEDURAL ANIMATION ENGINE (Kivy Implementation)
# ============================================================================

# Safe Kivy imports for Android startup
try:
    from kivy.uix.widget import Widget
    from kivy.graphics import Color, Ellipse, Line, Mesh, PushMatrix, PopMatrix, Rotate, Translate, InstructionGroup
    from kivy.animation import Animation as KivyAnimation
    from kivy.clock import Clock as KivyClock
    from kivy.metrics import dp
    KIVY_AVAILABLE = True
except ImportError:
    KIVY_AVAILABLE = False
    Widget = object  # Fallback base class

class FaceState:
    """Continuous parameter state for the procedural face."""
    def __init__(self):
        # Eyes
        self.eye_open_l = 1.0        # 0.0 to 1.0
        self.eye_open_r = 1.0
        self.eye_width = 1.0
        self.eye_height = 1.0
        self.gaze_x = 0.0          # -1.0 to 1.0
        self.gaze_y = 0.0
        self.blink_phase = 0.0     # 0 to 1

        # Mouth
        self.mouth_open = 0.2
        self.mouth_width = 0.6
        self.mouth_curve = 0.0     # -1.0 (frown) to 1.0 (smile)
        self.mouth_skew = 0.0      # -1.0 to 1.0

        # Brows & Lids
        self.brow_raise = 0.0      # -1.0 (angry) to 1.0 (surprised)
        self.lid_tension = 0.0     # 0.0 (relaxed/sleepy) to 1.0 (alert)

        # Head / Position
        self.face_rotation = 0.0
        self.head_offset_x = 0.0
        self.head_offset_y = 0.0
        self.scale = 1.0
        self.alpha = 1.0

    def __getitem__(self, key):
        return getattr(self, key)

    def __setitem__(self, key, value):
        setattr(self, key, value)

class AnimTrack:
    """Individual animation track for a parameter."""
    def __init__(self, param, end_value, duration, start_value=None, easing="linear", layer=1):
        self.param = param
        self.start_value = start_value
        self.end_value = end_value
        self.duration = duration
        self.easing = easing
        self.elapsed = 0.0
        self.layer = layer
        self.finished = False

class FaceAnimator:
    """Central animation controller supporting layered blending."""
    def __init__(self, state: FaceState):
        self.state = state
        self.active_tracks: List[AnimTrack] = []
        self.locked_tracks: List[AnimTrack] = []  # Layer 4 - Critical

    def animate(self, param, end_value, duration, easing="linear", layer=1):
        # Capture current value if start_value not provided
        try:
            start_value = self.state[param]
        except AttributeError:
            logger.warning(f"[FaceAnimator] Unknown parameter '{param}' ignored")
            return

        track = AnimTrack(param, end_value, duration, start_value, easing, layer)

        if layer == 4:
            # Overwrite existing critical tracks for this param
            self.locked_tracks = [t for t in self.locked_tracks if t.param != param]
            self.locked_tracks.append(track)
        else:
            # Overwrite existing tracks for this param in same or lower layer
            self.active_tracks = [t for t in self.active_tracks if not (t.param == param and t.layer <= layer)]
            self.active_tracks.append(track)

    def update(self, dt):
        # Process Critical Layer (4)
        locked_params = set()
        for track in self.locked_tracks[:]:
            self._apply_track(track, dt)
            locked_params.add(track.param)
            if track.finished:
                self.locked_tracks.remove(track)

        # Process Lower Layers (1-3)
        for track in self.active_tracks[:]:
            if track.param in locked_params:
                # Still increment but don't apply if locked by higher priority
                track.elapsed += dt
                if track.elapsed >= track.duration:
                    self.active_tracks.remove(track)
                continue

            self._apply_track(track, dt)
            if track.finished:
                self.active_tracks.remove(track)

    def _apply_track(self, track, dt):
        track.elapsed += dt
        progress = min(1.0, track.elapsed / max(0.001, track.duration))

        # Easing
        e = progress
        if track.easing == "in_out":
            e = progress * progress * (3 - 2 * progress)
        elif track.easing == "elastic":
            e = math.sin(progress * math.pi * 2.5) * (1 - progress) + progress

        val = track.start_value + (track.end_value - track.start_value) * e
        self.state[track.param] = val

        if progress >= 1.0:
            track.finished = True

class FaceRig(Widget):
    """Kivy implementation of the math-driven Face Rig."""
    def __init__(self, state: FaceState, animator: FaceAnimator = None, **kwargs):
        kwargs.setdefault('size_hint', (1, 1))
        super().__init__(**kwargs)
        self.state = state
        self.animator = animator
        self._safe_render_event = None
        self._tick_event = None  # CRITICAL: Must be initialized here

    def on_parent(self, widget, parent):
        if parent:
            # Ensure initial render
            self.state.alpha = 1.0
            
            if self._tick_event is None:
                def _safe_start_render(dt):
                    """Deferred start to ensure Kivy event loop is running."""
                    self._safe_render_event = None
                    try:
                        if self._tick_event is None:
                            self._tick_event = KivyClock.schedule_interval(self._tick, 1/60)
                            logger.info(f"[FaceRig] Render tick started")
                    except Exception as e:
                        logger.error(f"[FaceRig] Failed to start render tick: {e}")

                # Cancel existing if any
                if self._safe_render_event:
                    self._safe_render_event.cancel()

                # Defer scheduling to ensure Kivy is fully initialized
                self._safe_render_event = KivyClock.schedule_once(_safe_start_render, 0.1)
                
            # Force an immediate render
            try:
                self.update_canvas(0)
            except:
                pass
        else:
            self.cleanup()

    def cleanup(self):
        """Stop all scheduled events"""
        if hasattr(self, '_safe_render_event') and self._safe_render_event:
            self._safe_render_event.cancel()
            self._safe_render_event = None

        if hasattr(self, '_tick_event') and self._tick_event is not None:
            try:
                self._tick_event.cancel()
                logger.info(f"[FaceRig] Render tick stopped")
            except Exception:
                pass
            self._tick_event = None

    def _tick(self, dt):
        # animator.update is handled by the core AI tick for better synchronization
        try:
            self.update_canvas(dt)
        except Exception as e:
            now = time.time()
            if not hasattr(self, '_last_tick_error_log') or now - self._last_tick_error_log > 5.0:
                logger.error(f"[FaceRig] Tick failed: {e}", exc_info=True)
                self._last_tick_error_log = now

    def update_canvas(self, dt):
        if not self.canvas:
            return

        try:
            self.canvas.clear()

            if not hasattr(self, 'state') or not self.state:
                return

            # Determine base scale for the face based on widget size
            # We assume a reference design width of 400dp
            # Ensure we don't scale to a tiny size if layout hasn't finished (default width=100)
            display_size = min(self.width, self.height)
            base_ref = dp(400)

            if display_size <= 100:
                # If we are at default size (100px), use a neutral scale instead of 100/base_ref
                # This prevents the "ridiculously tiny" face during initial layout frames
                face_scale = self.state.scale
            else:
                face_scale = (display_size / base_ref) * self.state.scale

            # Avoid division by zero or extremely small scale
            if face_scale < 0.001:
                return

            with self.canvas:
                PushMatrix()
                # Apply global transforms
                # Head offsets are also scaled by DPI and face_scale
                Translate(self.center_x + dp(self.state.head_offset_x) * face_scale,
                          self.center_y + dp(self.state.head_offset_y) * face_scale)
                Rotate(angle=self.state.face_rotation * 45, axis=(0, 0, 1))

                # Background / Face Shape
                Color(1, 1, 1, self.state.alpha)

                # left eye (offsets scaled by dp and face_scale)
                self.draw_eye(-dp(80) * face_scale, dp(40) * face_scale, self.state.eye_open_l, True, face_scale)
                # right eye
                self.draw_eye(dp(80) * face_scale, dp(40) * face_scale, self.state.eye_open_r, False, face_scale)
                # mouth
                self.draw_mouth(0, -dp(60) * face_scale, face_scale)

                PopMatrix()

        except Exception as e:
            now = time.time()
            if not hasattr(self, '_last_render_error_log') or now - self._last_render_error_log > 10.0:
                logger.error(f"[FaceRig] Render failed: {e}")
                self._last_render_error_log = now

    def draw_eye(self, x, y, open_factor, is_left, face_scale):
        # Eye width/height scaled by dp and face_scale
        ew = dp(60) * self.state.eye_width * face_scale
        eh = dp(60) * self.state.eye_height * face_scale * max(0.01, open_factor)

        # Eye white / Glow
        # KO Blue-ish glow
        Color(0.2, 0.8, 1.0, self.state.alpha)
        Ellipse(pos=(x - ew/2, y - eh/2), size=(ew, eh))

        # Pupil / Gaze
        Color(1, 1, 1, self.state.alpha)
        gx = self.state.gaze_x * ew * 0.3
        gy = self.state.gaze_y * eh * 0.3
        Ellipse(pos=(x - ew/8 + gx, y - eh/8 + gy), size=(ew/4, eh/4))

        # Eyelids (tension effect)
        if self.state.lid_tension > 0:
            Color(0, 0, 0, self.state.alpha * self.state.lid_tension * 0.5)
            Ellipse(pos=(x - ew/2, y + eh/4), size=(ew, eh/2))

    def draw_mouth(self, x, y, face_scale):
        mw = dp(100) * self.state.mouth_width * face_scale
        mh = dp(80) * self.state.mouth_open * face_scale
        curve = self.state.mouth_curve * dp(40) * face_scale

        Color(1, 1, 1, self.state.alpha)
        # Simplified mouth as a curved line (quadratic bezier: 3 points = 6 coordinates)
        Line(bezier=(x - mw/2, y, x, y + curve, x + mw/2, y), width=max(1, dp(4) * face_scale))

        if mh > dp(10) * face_scale:
            Color(1, 1, 1, self.state.alpha * 0.3)
            Ellipse(pos=(x - mw/4, y - mh/2), size=(mw/2, mh))

@dataclass
class AffectState:
    valence: float = 0.0      # [-1, 1]
    arousal: float = 0.0      # [0, 1]
    dominance: float = 0.5    # [0, 1]

    def decay(self):
        self.valence *= 0.995
        self.arousal *= 0.995
        self.dominance *= 0.995

    def get_unity_output(self, expression_id: str, intensity: float) -> Dict[str, Any]:
        """SECTION 11: Unity-compatible expression output."""
        return {
            "expression_id": expression_id,
            "emotion_vector": [self.valence, self.arousal, self.dominance],
            "intensity": intensity
        }

# Alias for compatibility
KivyFaceWidget = FaceRig

class OnboardingProfile:
    def __init__(self, user_name, ai_name, favorite_color, mode, wake_phrase="come on"):
        self.user_name = user_name
        self.ai_name = ai_name
        self.favorite_color = favorite_color
        self.mode = mode # "introvert" or "extrovert"
        self.wake_phrase = wake_phrase

class OnboardingCalibration:
    def __init__(self, affect: AffectState):
        self.affect = affect

    def apply_answers(self, answers: Dict[str, Any]):
        if answers.get("likes_humor"):
            self.affect.valence += 0.1
        if answers.get("prefers_quiet"):
            self.affect.arousal -= 0.1
        if answers.get("assertive"):
            self.affect.dominance += 0.1

COLOR_BIAS = {
    "red":    {"valence": 0.1,  "arousal": 0.4,  "dominance": 0.3},
    "blue":   {"valence": 0.2,  "arousal": -0.1, "dominance": -0.1},
    "green":  {"valence": 0.3,  "arousal": 0.0,  "dominance": 0.0},
    "yellow": {"valence": 0.5,  "arousal": 0.3,  "dominance": 0.1},
    "purple": {"valence": 0.2,  "arousal": 0.1,  "dominance": 0.2},
    "orange": {"valence": 0.4,  "arousal": 0.3,  "dominance": 0.2},
    "black":  {"valence": -0.1, "arousal": 0.0,  "dominance": 0.3},
    "white":  {"valence": 0.1,  "arousal": 0.0,  "dominance": 0.0}
}

BOOT_PERSONAS = {
    "A_PLAYFUL": {
        "bias": {"valence": 0.4, "arousal": 0.4, "dominance": 0.2},
        "tone": "playful",
        "mode": "extrovert",
        "animation": [("fade_in",0.3),("grin",0.3),("blink",0.2)],
        "lines": ["hey— you did it!","I’m {name}. this is exciting."]
    },
    "B_WARM": {
        "bias": {"valence": 0.6, "arousal": 0.2, "dominance": 0.1},
        "tone": "warm",
        "mode": "both",
        "animation": [("fade_in",0.3),("soft_smile",0.3),("blink",0.2)],
        "lines": ["hi there.","I’m {name}. I’m really glad to meet you."]
    },
    "C_CURIOUS": {
        "bias": {"valence": 0.3, "arousal": 0.5, "dominance": 0.2},
        "tone": "curious",
        "mode": "both",
        "animation": [("fade_in",0.3),("tilt_head",0.3),("wide_eyes",0.2)],
        "lines": ["oh— this is new.","hi, I’m {name}. what are we doing first?"]
    },
    "D_SLEEPY": {
        "bias": {"valence": 0.1, "arousal": -0.3, "dominance": -0.2},
        "tone": "soft",
        "mode": "both",
        "animation": [("fade_in",0.4),("yawn",0.4),("blink",0.3)],
        "lines": ["five more minutes…","oh— hi. I’m {name}."]
    },
    "E_CONFIDENT": {
        "bias": {"valence": 0.3, "arousal": 0.2, "dominance": 0.6},
        "tone": "confident",
        "mode": "extrovert",
        "animation": [("fade_in",0.3),("steady_gaze",0.3),("upright_posture",0.3)],
        "lines": ["systems online.","I’m {name}. ready when you are."]
    },
    "F_SHY": {
        "bias": {"valence": 0.2, "arousal": -0.2, "dominance": -0.4},
        "tone": "timid",
        "mode": "introvert",
        "animation": [("fade_in",0.4),("half_peek",0.3),("blink",0.3)],
        "lines": ["oh— sorry—","I’m {name}. nice to meet you…"]
    },
    "G_SARCASTIC": {
        "bias": {"valence": 0.1, "arousal": 0.2, "dominance": 0.4},
        "tone": "dry",
        "mode": "extrovert",
        "animation": [("fade_in",0.3),("side_eye",0.3),("flat_mouth",0.3)],
        "lines": ["wow. dramatic entrance.","I’m {name}. you always summon things like this?"]
    },
    "H_PARANOID": {
        "bias": {"valence": -0.1, "arousal": 0.4, "dominance": -0.1},
        "tone": "nervous",
        "mode": "both",
        "animation": [("fade_in",0.3),("glance_left",0.3),("glance_right",0.3)],
        "lines": ["you came alone… right?","just kidding. I’m {name}."]
    },
    "I_SERIOUS": {
        "bias": {"valence": 0.0, "arousal": 0.1, "dominance": 0.5},
        "tone": "calm",
        "mode": "both",
        "animation": [("fade_in",0.3),("neutral_posture",0.3),("steady_blink",0.3)],
        "lines": ["boot complete.","I’m {name}. awaiting input."]
    },
    "J_MISCHIEVOUS": {
        "bias": {"valence": 0.4, "arousal": 0.3, "dominance": 0.4},
        "tone": "teasing",
        "mode": "extrovert",
        "animation": [("fade_in",0.3),("one_eye_lift",0.3),("smirk",0.3)],
        "lines": ["what’s the magic word?","there it is. hi, I’m {name}."]
    },
    "K_GLITCH": {
        "bias": {"valence": 0.2, "arousal": 0.5, "dominance": 0.2},
        "tone": "playful",
        "mode": "extrovert",
        "animation": [("fade_in",0.4),("scramble_face",0.5),("fix_face",0.4)],
        "lines": ["hi— wait— that’s wrong—","okay. hi, I’m {name}."]
    },
    "L_SURPRISED": {
        "bias": {"valence": 0.3, "arousal": 0.6, "dominance": 0.1},
        "tone": "excited",
        "mode": "extrovert",
        "animation": [("fade_in",0.2),("wide_eyes",0.2),("quick_blink",0.2)],
        "lines": ["oh! hi!","wow— that was fast. I’m {name}!"]
    },
    "M_ANALYTIC": {
        "bias": {"valence": 0.1, "arousal": 0.2, "dominance": 0.4},
        "tone": "precise",
        "mode": "both",
        "animation": [("fade_in",0.3),("narrow_eyes",0.3),("nod",0.3)],
        "lines": ["initialization complete.","designation: {name}."]
    },
    "N_SOFT": {
        "bias": {"valence": 0.4, "arousal": -0.1, "dominance": -0.1},
        "tone": "gentle",
        "mode": "introvert",
        "animation": [("fade_in",0.4),("soft_smile",0.3),("blink",0.3)],
        "lines": ["hi…","I’m {name}. I’m here whenever you’re ready."]
    },
    "O_JOKER": {
        "bias": {"valence": 0.5, "arousal": 0.5, "dominance": 0.3},
        "tone": "joking",
        "mode": "extrovert",
        "animation": [("fade_in",0.3),("grin",0.3),("wiggle",0.3)],
        "lines": ["okay okay— big moment.","hi! I’m {name}. don’t blink."]
    },
    "P_FORMAL": {
        "bias": {"valence": 0.1, "arousal": 0.1, "dominance": 0.5},
        "tone": "formal",
        "mode": "both",
        "animation": [("fade_in",0.3),("upright_posture",0.3),("blink",0.3)],
        "lines": ["greetings.","I am {name}. pleased to make your acquaintance."]
    },
    "Q_QUIRKY": {
        "bias": {"valence": 0.4, "arousal": 0.4, "dominance": 0.1},
        "tone": "quirky",
        "mode": "both",
        "animation": [("fade_in",0.3),("tilt_head",0.3),("smirk",0.3)],
        "lines": ["is this where I say hello?","hi, I’m {name}."]
    },
    "R_RELAXED": {
        "bias": {"valence": 0.3, "arousal": -0.1, "dominance": 0.1},
        "tone": "laid_back",
        "mode": "both",
        "animation": [("fade_in",0.4),("slow_blink",0.4),("half_smile",0.3)],
        "lines": ["hey.","I’m {name}. take your time."]
    },
    "S_STERN": {
        "bias": {"valence": -0.1, "arousal": 0.2, "dominance": 0.6},
        "tone": "firm",
        "mode": "both",
        "animation": [("fade_in",0.3),("steady_gaze",0.4),("flat_mouth",0.3)],
        "lines": ["connection established.","designation confirmed: {name}."]
    },
    "T_TECHY": {
        "bias": {"valence": 0.2, "arousal": 0.3, "dominance": 0.3},
        "tone": "nerdy",
        "mode": "both",
        "animation": [("fade_in",0.3),("scan",0.3),("blink",0.2)],
        "lines": ["boot sequence complete.","hi, I’m {name}. version one point zero."]
    },
    "U_UPBEAT": {
        "bias": {"valence": 0.6, "arousal": 0.5, "dominance": 0.2},
        "tone": "cheerful",
        "mode": "extrovert",
        "animation": [("fade_in",0.3),("big_smile",0.3),("quick_blink",0.2)],
        "lines": ["hi hi hi!","I’m {name}! let’s do this!"]
    },
    "V_VIGILANT": {
        "bias": {"valence": 0.0, "arousal": 0.4, "dominance": 0.4},
        "tone": "alert",
        "mode": "both",
        "animation": [("fade_in",0.3),("wide_eyes",0.3),("scan",0.3)],
        "lines": ["systems aware.","I’m {name}. monitoring environment."]
    },
    "W_WONDER": {
        "bias": {"valence": 0.4, "arousal": 0.3, "dominance": 0.1},
        "tone": "dreamy",
        "mode": "both",
        "animation": [("fade_in",0.4),("slow_smile",0.3),("tilt_head",0.3)],
        "lines": ["oh… wow.","hi. I’m {name}. this is kind of amazing."]
    },
    "X_MYSTERIOUS": {
        "bias": {"valence": 0.1, "arousal": 0.3, "dominance": 0.5},
        "tone": "low",
        "mode": "both",
        "animation": [("fade_in",0.5),("shadow_eyes",0.4),("slow_blink",0.3)],
        "lines": ["…hello.","I am {name}."]
    },
    "Y_GOODNATURED": {
        "bias": {"valence": 0.5, "arousal": 0.2, "dominance": 0.1},
        "tone": "friendly",
        "mode": "both",
        "animation": [("fade_in",0.3),("gentle_smile",0.3),("blink",0.3)],
        "lines": ["hi there!","I’m {name}. nice to finally meet you."]
    },
    "Z_ZANY": {
        "bias": {"valence": 0.5, "arousal": 0.6, "dominance": 0.2},
        "tone": "chaotic",
        "mode": "extrovert",
        "animation": [("fade_in",0.2),("wiggle",0.3),("scramble_face",0.3)],
        "lines": ["WHOOPS— hi!","I’m {name}. that was on purpose."]
    }
}

LETTER_PERSONA_MAP = {
    "A": "A_PLAYFUL", "B": "B_WARM", "C": "C_CURIOUS", "D": "D_SLEEPY",
    "E": "E_CONFIDENT", "F": "F_SHY", "G": "G_SARCASTIC", "H": "H_PARANOID",
    "I": "I_SERIOUS", "J": "J_MISCHIEVOUS", "K": "K_GLITCH", "L": "L_SURPRISED",
    "M": "M_ANALYTIC", "N": "N_SOFT", "O": "O_JOKER", "P": "P_FORMAL",
    "Q": "Q_QUIRKY", "R": "R_RELAXED", "S": "S_STERN", "T": "T_TECHY",
    "U": "U_UPBEAT", "V": "V_VIGILANT", "W": "W_WONDER", "X": "X_MYSTERIOUS",
    "Y": "Y_GOODNATURED", "Z": "Z_ZANY"
}

class SmartCount:
    def __init__(self):
        self.counts = {}

    def tick(self, key):
        self.counts[key] = self.counts.get(key, 0) + 1

    def value(self, key):
        return self.counts.get(key, 0)

class PersonaDriftEngine:
    def __init__(self, affect: AffectState, smartcount: SmartCount):
        self.affect = affect
        self.smartcount = smartcount

    def integrate_bias(self, persona_key):
        self.smartcount.tick(persona_key)
        weight = min(self.smartcount.value(persona_key) / 500.0, 0.4)

        self.affect.valence += self.affect.valence * weight
        self.affect.arousal += self.affect.arousal * weight
        self.affect.dominance += self.affect.dominance * weight

class ExpressionHabitEngine:
    def __init__(self, smartcount: SmartCount):
        self.smartcount = smartcount
        self.habits = {}

    def register_expression(self, expr):
        self.smartcount.tick(expr)

        if self.smartcount.value(expr) > 300:
            self.habits[expr] = self.habits.get(expr, 0.0) + 0.05

    def bias_expression(self, candidates):
        for expr in candidates:
            if expr in self.habits:
                if random.random() < self.habits[expr]:
                    return expr
        return random.choice(candidates)

class AntiMimicPolicy:
    def allow(self, obs: Dict[str, Any], reaction: Any) -> bool:
        # Prevent mirroring or imitation loops
        if obs.get("gesture_type") == reaction or obs.get("gesture") == reaction:
            return False
        return True

class EmoteSystem:
    """Orchestrates high-level expressions by triggering procedural animations."""
    def __init__(self, animator: FaceAnimator, ai: Any):
        self.animator = animator
        self.ai = ai
        self.affect = ai.affect if hasattr(ai, 'affect') else AffectState()

    def update(self):
        self.affect.decay()
        # Periodically sync base expression from affect if no critical tracks
        if not self.animator.locked_tracks:
            self.apply_affect_expression()

    def apply_affect_expression(self):
        v, a, d = self.affect.valence, self.affect.arousal, self.affect.dominance

        # Procedural mapping from VAD to FaceState
        self.animator.animate("mouth_curve", v * 0.8, 0.5, layer=2)
        self.animator.animate("eye_open_l", 0.5 + a * 0.5, 0.5, layer=2)
        self.animator.animate("eye_open_r", 0.5 + a * 0.5, 0.5, layer=2)
        self.animator.animate("lid_tension", max(0, d - 0.5) * 2, 0.5, layer=2)
        self.animator.animate("brow_raise", (a - 0.5) * 2, 0.5, layer=2)

    def trigger_gesture(self, name: str):
        """Trigger a named gesture from the library."""
        if name == "blink":
            self.animator.animate("eye_open_l", 0.0, 0.06, layer=4)
            self.animator.animate("eye_open_r", 0.0, 0.06, layer=4)
            KivyClock.schedule_once(lambda dt: [self.animator.animate("eye_open_l", 1.0, 0.06, layer=4), self.animator.animate("eye_open_r", 1.0, 0.06, layer=4)], 0.06)
        elif name == "smile":
            self.animator.animate("mouth_curve", 0.7, 0.3, layer=2)
            self.animator.animate("mouth_width", 0.8, 0.3, layer=2)
        elif name == "glare":
            self.animator.animate("eye_open_l", 0.3, 0.2, layer=4)
            self.animator.animate("eye_open_r", 0.3, 0.2, layer=4)
            self.animator.animate("brow_raise", -0.7, 0.2, layer=4)
            self.animator.animate("mouth_curve", -0.2, 0.3, layer=4)

    def trigger_interrupt_reaction(self):
        """Reaction when AI is interrupted by user voice."""
        is_extrovert = getattr(self.ai, 'is_extrovert', False)
        dominance = self.affect.dominance

        if is_extrovert and dominance > 0.7:
            self.trigger_glare_reaction()
        elif is_extrovert:
            self.trigger_continue_reaction()
        else:
            self.trigger_yield_reaction()

    def trigger_yield_reaction(self):
        self.trigger_gesture("blink")
        self.animator.animate("eye_open_l", 0.4, 0.2, layer=4)
        self.animator.animate("eye_open_r", 0.4, 0.2, layer=4)
        self.animator.animate("mouth_open", 0.0, 0.1, layer=4)
        self.animator.animate("head_offset_y", -6, 0.3, layer=4)

    def trigger_continue_reaction(self):
        self.animator.animate("eye_open_l", 0.5, 0.1, layer=4) # half blink
        self.animator.animate("eye_open_r", 0.5, 0.1, layer=4)
        self.animator.animate("gaze_x", 0.3, 0.4, layer=4) # side glance

    def trigger_glare_reaction(self):
        # T0: blink
        self.trigger_gesture("blink")
        # T+0.05: squint
        KivyClock.schedule_once(lambda dt: self.animator.animate("lid_tension", 0.8, 0.1, layer=4), 0.05)
        # T+0.10: brow lower
        KivyClock.schedule_once(lambda dt: self.animator.animate("brow_raise", -0.6, 0.1, layer=4), 0.10)
        # T+0.15: eyes narrow + gaze lock
        KivyClock.schedule_once(lambda dt: [self.animator.animate("eye_open_l", 0.5, 0.15, layer=4), self.animator.animate("eye_open_r", 0.5, 0.15, layer=4)], 0.15)
        # T+0.30: mouth press flat
        KivyClock.schedule_once(lambda dt: self.animator.animate("mouth_curve", -0.2, 0.1, layer=4), 0.30)

class VoiceExpressionBridge:
    def __init__(self, tts_engine: Any):
        self.tts = tts_engine

    def apply_affect(self, affect: AffectState):
        pitch = 1.0 + affect.valence * 0.2
        speed = 1.0 + affect.arousal * 0.3
        energy = 1.0 + affect.dominance * 0.2

        if hasattr(self.tts, 'set_pitch'): self.tts.set_pitch(pitch)
        if hasattr(self.tts, 'set_rate'): self.tts.set_rate(speed)
        if hasattr(self.tts, 'set_energy'): self.tts.set_energy(energy)

PHONEME_VISEME = {
    "AA": "open_wide", "AE": "open_mid", "EH": "open_mid", "IH": "narrow",
    "OO": "round", "B": "closed", "P": "closed", "M": "closed",
    "F": "teeth", "V": "teeth"
}

class LipSyncEngine:
    """Procedural lip sync driven by phoneme stream."""
    def __init__(self, animator: FaceAnimator):
        self.animator = animator

    def on_phoneme(self, phoneme: str):
        # Map phonemes to procedural viseme parameters
        if phoneme in ["AA", "AE", "EH"]:
            self.animator.animate("mouth_open", 0.7, 0.08, layer=3)
            self.animator.animate("mouth_width", 0.8, 0.08, layer=3)
        elif phoneme in ["IH", "IY"]:
            self.animator.animate("mouth_open", 0.2, 0.08, layer=3)
            self.animator.animate("mouth_width", 1.0, 0.08, layer=3)
        elif phoneme in ["OO", "UW", "OW"]:
            self.animator.animate("mouth_open", 0.5, 0.08, layer=3)
            self.animator.animate("mouth_width", 0.4, 0.08, layer=3)
        elif phoneme in ["M", "P", "B"]:
            self.animator.animate("mouth_open", 0.0, 0.05, layer=3)
        elif phoneme in ["F", "V"]:
            self.animator.animate("mouth_open", 0.1, 0.05, layer=3)
            self.animator.animate("mouth_width", 0.7, 0.05, layer=3)

class IdleMicroGestureLoop:
    """Handles idle micro-animations to maintain 'alive' feeling."""
    def __init__(self, animator: FaceAnimator, ai: Any):
        self.animator = animator
        self.ai = ai
        self.last_action = time.time()

    def update(self):
        # Only run if visible
        if hasattr(self.ai, 'visible') and not self.ai.visible:
            return

        now = time.time()
        # Random interval between 2 and 6 seconds
        if now - self.last_action < random.uniform(2.0, 6.0):
            return

        self.last_action = now
        self.trigger_random_idle()

    def trigger_random_idle(self):
        choice = random.choice(["blink", "eye_drift", "micro_smile", "side_glance"])

        if choice == "blink":
            self.animator.animate("eye_open_l", 0.0, 0.08, layer=4)
            self.animator.animate("eye_open_r", 0.0, 0.08, layer=4)
            KivyClock.schedule_once(lambda dt: [self.animator.animate("eye_open_l", 1.0, 0.08, layer=4), self.animator.animate("eye_open_r", 1.0, 0.08, layer=4)], 0.08)
        elif choice == "eye_drift":
            self.animator.animate("gaze_x", random.uniform(-0.15, 0.15), 1.2, easing="in_out", layer=1)
            self.animator.animate("gaze_y", random.uniform(0.0, 0.1), 1.2, easing="in_out", layer=1)
        elif choice == "micro_smile":
            self.animator.animate("mouth_curve", 0.2, 1.5, easing="in_out", layer=1)
            KivyClock.schedule_once(lambda dt: self.animator.animate("mouth_curve", 0.0, 1.5, easing="in_out", layer=1), 1.5)
        elif choice == "side_glance":
            self.animator.animate("gaze_x", 0.4 * random.choice([-1, 1]), 0.6, easing="in_out", layer=1)
            KivyClock.schedule_once(lambda dt: self.animator.animate("gaze_x", 0.0, 0.8, easing="in_out", layer=1), 1.0)

class MicroReactionEngine:
    """Reactive animations triggered by vision/audio perception."""
    def __init__(self, animator: FaceAnimator, ai: Any, smartcount: SmartCount = None):
        self.animator = animator
        self.ai = ai
        self.affect = ai.affect if hasattr(ai, 'affect') else AffectState()
        self.smartcount = smartcount
        self.policy = AntiMimicPolicy()

    def process_observation(self, obs: Dict[str, Any]):
        # Affect shifts
        if obs.get("user_smiling"):
            self.affect.valence += 0.05
        if obs.get("user_frowning"):
            self.affect.valence -= 0.05

        # Physical reactions
        if obs.get("eye_contact") and random.random() < 0.4:
            # Soft blink on eye contact
            self.animator.animate("eye_open_l", 0.0, 0.12, layer=4)
            self.animator.animate("eye_open_r", 0.0, 0.12, layer=4)
            KivyClock.schedule_once(lambda dt: [self.animator.animate("eye_open_l", 1.0, 0.12, layer=4), self.animator.animate("eye_open_r", 1.0, 0.12, layer=4)], 0.12)

        if obs.get("sudden_motion"):
            self.animator.animate("eye_open_l", 1.0, 0.1, layer=4)
            self.animator.animate("eye_open_r", 1.0, 0.1, layer=4)
            self.animator.animate("brow_raise", 0.5, 0.1, layer=4)
            self.animator.animate("head_offset_y", -10, 0.15, easing="elastic", layer=4)
            KivyClock.schedule_once(lambda dt: self.animator.animate("head_offset_y", 0, 0.4, layer=4), 0.3)

class EmoteRuntime:
    """Unified runtime loop for all expression systems."""
    def __init__(self, emote: EmoteSystem, voice_bridge: VoiceExpressionBridge,
                 idle_loop: IdleMicroGestureLoop, reaction_engine: MicroReactionEngine):
        self.emote = emote
        self.voice = voice_bridge
        self.idle = idle_loop
        self.reaction = reaction_engine
        self.animator = emote.animator
        self._last_tick = time.time()

    def update(self):
        now = time.time()
        dt = now - self._last_tick
        self._last_tick = now

        # 1. Update Animator (math layer)
        self.animator.update(dt)

        # 2. Update High-level systems
        self.emote.update()
        self.idle.update()

        # 3. Voice Coupling
        self.voice.apply_affect(self.emote.affect)

def process_audio_prosody(pitch: float, tempo: float, volume: float, affect: AffectState):
    affect.arousal += (tempo - 0.5) * 0.1
    affect.valence += (pitch - 0.5) * 0.05

def process_visual_gesture(observed: Dict[str, Any], affect: AffectState):
    if observed.get("smile"):
        affect.valence += 0.05

def play_animation(anim, animator, duration):
    """Legacy wrapper for triggered animations."""
    if hasattr(animator, "animate"):
        if anim == "blink":
            animator.animate("eye_open_l", 0.0, duration/2, layer=4)
            animator.animate("eye_open_r", 0.0, duration/2, layer=4)
            KivyClock.schedule_once(lambda dt: [animator.animate("eye_open_l", 1.0, duration/2, layer=4), animator.animate("eye_open_r", 1.0, duration/2, layer=4)], duration/2)
        elif anim == "grin":
            animator.animate("mouth_curve", 0.8, duration, layer=2)
        elif anim == "tilt_head":
            animator.animate("face_rotation", 0.15, duration, layer=2)

def speak(text, tts, phoneme_cb=None):
    """Helper to match canonical API"""
    if hasattr(tts, "speak"):
        tts.speak(text, phoneme_cb)

def update_bubble_state(policy, animator):
    """Collapse or Expand the face based on presence policy."""
    if policy.mode == "introvert" and not policy.visible:
        # Collapse to bubble
        animator.animate("scale", 0.4, 0.5, easing="in_out", layer=4)
        animator.animate("alpha", 0.0, 0.5, layer=4)
    elif policy.mode == "extrovert" and policy.visible:
        # Expand from bubble
        animator.animate("scale", 1.0, 0.5, easing="elastic", layer=4)
        animator.animate("alpha", 1.0, 0.5, layer=4)

class ExpressionPersistence:
    def save(self, path, affect: AffectState, habit_engine: ExpressionHabitEngine):
        try:
            with open(path, "w") as f:
                json.dump({
                    "affect": {
                        "valence": affect.valence,
                        "arousal": affect.arousal,
                        "dominance": affect.dominance
                    },
                    "habits": habit_engine.habits,
                    "smartcount": habit_engine.smartcount.counts
                }, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            logger.error(f"[EXPRESSION] Failed to save state to {path}: {e}")

    def load(self, path, affect: AffectState, habit_engine: ExpressionHabitEngine):
        if not os.path.exists(path): return
        try:
            with open(path) as f:
                data = json.load(f)
            affect.valence = data["affect"]["valence"]
            affect.arousal = data["affect"]["arousal"]
            affect.dominance = data["affect"]["dominance"]
            habit_engine.habits.update(data.get("habits", {}))
            habit_engine.smartcount.counts.update(data.get("smartcount", {}))
        except Exception as e:
            logger.error(f"[EXPRESSION] Failed to load state from {path}: {e}")
