#!/usr/bin/env python3
"""
Offline AI Dynamics Module
==========================

Consolidated energy and entropic regulators.
Combines:
- Energy Regulator (offline_ai_energy.py)
- Entropic Regulator (offline_ai_entropic.py)
"""

import time
import math
import hashlib
from dataclasses import dataclass, field

# Numpy is optional on Android - gracefully handle missing numpy
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

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
                return math.sqrt(sum(x * x for x in v))
        class random:
            @staticmethod
            def randn(n):
                import random
                return [random.gauss(0, 1) for _ in range(n)]

    np = _NumpyFallback()
from typing import Dict, List, Optional, Tuple, Any
from collections import deque

# ============================================================================
# 1. ENERGY REGULATOR (from offline_ai_energy.py)
# ============================================================================

class OfflineAIEnergyRegulator:
    def __init__(self, budget: float = 100.0, decay_rate: float = 0.05):
        self.total_energy, self.energy_budget, self.decay_rate = 1.0, budget, decay_rate
        self.vitality, self.max_vitality, self.is_alive = 100.0, 100.0, True
        self.presence, self.last_tick = 1.0, time.time()
        self.current_emotion, self.emotion_intensity = "neutral", 0.0
        self.emotion_map = {"joy": 0.8, "curiosity": 0.6, "trust": 0.7, "fear": -0.7, "anger": -0.6, "sadness": -0.8, "neutral": 0.0}
    def inject_energy(self, amount: float):
        self.total_energy = min(self.energy_budget, self.total_energy + amount * self.presence)
    def apply_moral_impact(self, impact: float):
        self.total_energy = max(0.1, min(self.energy_budget, self.total_energy + impact * 10.0))
        self.vitality = max(0.0, min(self.max_vitality, self.vitality + impact * 5.0))
        if self.vitality <= 0: self.is_alive = False
    def process_input_energy(self, text: str):
        energy_gain = len(text.split()) * 0.1
        if "!" in text: energy_gain *= 1.5
        if "?" in text: energy_gain *= 1.2
        self.inject_energy(energy_gain)
        text_lower = text.lower()
        if any(w in text_lower for w in ["happy", "great", "awesome", "yes"]): self.current_emotion = "joy"
        elif any(w in text_lower for w in ["what", "how", "why", "curious"]): self.current_emotion = "curiosity"
        elif any(w in text_lower for w in ["bad", "wrong", "no", "hate"]): self.current_emotion = "anger"
        else: self.current_emotion = "neutral"
        self.emotion_intensity = abs(self.emotion_map.get(self.current_emotion, 0.0))
    def step(self):
        now = time.time()
        dt, self.last_tick = now - self.last_tick, now
        self.total_energy = max(0.1, self.total_energy * (1.0 - self.decay_rate * dt))
        self.presence = min(1.0, self.total_energy / 20.0)
    def get_status(self) -> Dict[str, Any]:
        return {"total_energy": round(self.total_energy, 3), "vitality": round(self.vitality, 3), "is_alive": self.is_alive, "presence": round(self.presence, 3), "emotion": self.current_emotion, "intensity": round(self.emotion_intensity, 3)}


# ============================================================================
# 2. ENTROPIC REGULATOR (from offline_ai_entropic.py)
# ============================================================================

@dataclass
class ShardSignature:
    pattern_id: str
    pattern_class: str
    complexity: float
    generation: int
    timestamp: float = field(default_factory=time.time)
    @staticmethod
    def from_interaction(intent: str, style: Dict[str, float], generation: int) -> 'ShardSignature':
        style_buckets = tuple(round(v * 2) / 2 for v in style.values())
        pattern_id = hashlib.sha256(f"{intent}_{style_buckets}".encode()).hexdigest()[:16]
        return ShardSignature(pattern_id=pattern_id, pattern_class=intent, complexity=style.get("precision", 0.5), generation=generation)

@dataclass
class PatternStats:
    pattern_id: str
    count_total: int = 0
    count_recent: int = 0
    last_seen_generation: int = 0

class PressureField:
    def __init__(self, recent_window: int = 20, time_decay_rate: float = 0.1):
        self.pattern_stats, self.current_generation, self.recent_window, self.time_decay_rate = {}, 0, recent_window, time_decay_rate
        self.new_patterns_per_gen, self.patterns_this_gen = deque(maxlen=50), set()
    def compute_pressure(self, signature: ShardSignature, energy_presence: float = 1.0) -> float:
        if signature.complexity < 0.15: return 0.0
        stats = self.pattern_stats.get(signature.pattern_id)
        if not stats: return 0.0
        recent_density = stats.count_recent / max(1, self.recent_window)
        recency_factor = math.exp(-self.time_decay_rate * max(0, self.current_generation - stats.last_seen_generation))
        avg_new = sum(self.new_patterns_per_gen) / max(1, len(self.new_patterns_per_gen))
        novelty_factor = 1.0 - min(1.0, avg_new / 5.0) * 0.5
        return min(1.0, (0.6 * recent_density + 0.3 * recency_factor + 0.1 * novelty_factor) * signature.complexity * max(0.2, 1.2 - energy_presence))
    def advance_generation(self):
        self.new_patterns_per_gen.append(len(self.patterns_this_gen))
        self.current_generation += 1
        self.patterns_this_gen.clear()
        for stats in self.pattern_stats.values():
            if self.current_generation - stats.last_seen_generation > self.recent_window: stats.count_recent = 0

class OfflineAIEntropicRegulator:
    def __init__(self): self.field = PressureField()
    def ingest_interaction(self, intent: str, style: Dict[str, float]):
        sig = ShardSignature.from_interaction(intent, style, self.field.current_generation)
        if sig.pattern_id not in self.field.pattern_stats:
            self.field.pattern_stats[sig.pattern_id] = PatternStats(pattern_id=sig.pattern_id)
            self.field.patterns_this_gen.add(sig.pattern_id)
        stats = self.field.pattern_stats[sig.pattern_id]
        stats.count_total += 1
        stats.count_recent += 1
        stats.last_seen_generation = self.field.current_generation
    def query_pressure(self, intent: str, style: Dict[str, float], energy_presence: float = 1.0) -> float:
        return self.field.compute_pressure(ShardSignature.from_interaction(intent, style, self.field.current_generation), energy_presence)
    def advance_generation(self): self.field.advance_generation()
    def get_pressure_state(self) -> Dict[str, Any]: return {"current_generation": self.field.current_generation, "total_patterns": len(self.field.pattern_stats), "recent_window": self.field.recent_window}
