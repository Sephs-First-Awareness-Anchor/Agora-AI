#!/usr/bin/env python3
"""
Wisdom Shards - Aurora-Borrowed Organic Learning from Failures
===============================================================

When expressions die (by age, selection pressure, or cull), their biases
are distilled into WisdomShards and stored in the ExpressionWisdomStore.
During response assembly the surviving wisdom influences tone selection
probability, structure/formality preference, and novelty tolerance --
but never overrides executive control constraints (alignment floor,
autonomy lock, energy gating).

This module is part of the Agora AI Offline Engine perception pipeline.
"""

import logging
import time
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MAX_SHARDS = 500

VALID_DOMAINS = frozenset({"lexical", "audio", "vision", "voice", "gesture"})

VALID_CAUSES_OF_DEATH = frozenset({"age", "selection", "cull"})

VALID_BIAS_TYPES = frozenset({"tone_bias", "structure_bias"})

# Executive control constraints that wisdom must never override.
# These are symbolic keys checked at application time.
EXECUTIVE_CONSTRAINTS = frozenset({
    "alignment_floor",
    "autonomy_lock",
    "energy_gating",
})


# ---------------------------------------------------------------------------
# Data Model
# ---------------------------------------------------------------------------

@dataclass
class WisdomShard:
    """A single distilled learning extracted from a dead expression."""

    shard_id: str
    domain: str                 # lexical | audio | vision | voice | gesture
    lineage_key: str            # family id or i-state-like key
    tone_bias: float            # [-1, 1]
    structure_bias: float       # [-1, 1]
    fitness_at_death: float     # fitness score when the expression expired
    cause_of_death: str         # age | selection | cull
    generation: int
    timestamp: float = field(default_factory=time.time)

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def __post_init__(self) -> None:
        if self.domain not in VALID_DOMAINS:
            raise ValueError(
                f"Invalid domain '{self.domain}'. Must be one of {sorted(VALID_DOMAINS)}."
            )
        if self.cause_of_death not in VALID_CAUSES_OF_DEATH:
            raise ValueError(
                f"Invalid cause_of_death '{self.cause_of_death}'. "
                f"Must be one of {sorted(VALID_CAUSES_OF_DEATH)}."
            )
        self.tone_bias = max(-1.0, min(1.0, float(self.tone_bias)))
        self.structure_bias = max(-1.0, min(1.0, float(self.structure_bias)))
        self.fitness_at_death = max(0.0, float(self.fitness_at_death))
        self.generation = max(0, int(self.generation))

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "shard_id": self.shard_id,
            "domain": self.domain,
            "lineage_key": self.lineage_key,
            "tone_bias": self.tone_bias,
            "structure_bias": self.structure_bias,
            "fitness_at_death": self.fitness_at_death,
            "cause_of_death": self.cause_of_death,
            "generation": self.generation,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WisdomShard":
        return cls(
            shard_id=data["shard_id"],
            domain=data["domain"],
            lineage_key=data["lineage_key"],
            tone_bias=data["tone_bias"],
            structure_bias=data["structure_bias"],
            fitness_at_death=data["fitness_at_death"],
            cause_of_death=data["cause_of_death"],
            generation=data["generation"],
            timestamp=data.get("timestamp", time.time()),
        )


# ---------------------------------------------------------------------------
# Wisdom Store
# ---------------------------------------------------------------------------

class ExpressionWisdomStore:
    """
    Stores WisdomShards indexed by lineage_key and provides aggregate
    bias queries used during response assembly.

    Thread-safe: a reentrant lock protects all mutations and reads so the
    store can be accessed from the response-assembly thread and the
    evolution/cull thread concurrently.
    """

    def __init__(self, max_shards: int = MAX_SHARDS) -> None:
        self.max_shards = max(1, max_shards)

        # Primary storage: ordered list for easy pruning by fitness.
        self._shards: List[WisdomShard] = []

        # Secondary index: lineage_key -> list of shard references.
        self._lineage_index: Dict[str, List[WisdomShard]] = defaultdict(list)

        # Tertiary index: domain -> list of shard references.
        self._domain_index: Dict[str, List[WisdomShard]] = defaultdict(list)

        self._lock = threading.RLock()

    # ------------------------------------------------------------------
    # Core operations
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        with self._lock:
            return len(self._shards)

    def add_shard(self, shard: WisdomShard) -> None:
        """
        Add a shard to the store.  Prunes lowest-fitness shards when the
        store exceeds *max_shards*.
        """
        with self._lock:
            self._shards.append(shard)
            self._lineage_index[shard.lineage_key].append(shard)
            self._domain_index[shard.domain].append(shard)

            if len(self._shards) > self.max_shards:
                self._prune()

        logger.debug(
            "[WISDOM] Added shard %s (lineage=%s, domain=%s, fitness=%.3f)",
            shard.shard_id, shard.lineage_key, shard.domain,
            shard.fitness_at_death,
        )

    def _prune(self) -> None:
        """
        Remove the lowest-fitness shards until the store is within capacity.
        Caller must hold *_lock*.
        """
        excess = len(self._shards) - self.max_shards
        if excess <= 0:
            return

        # Sort ascending by fitness_at_death; remove the weakest.
        self._shards.sort(key=lambda s: s.fitness_at_death)
        removed = self._shards[:excess]
        self._shards = self._shards[excess:]

        # Rebuild secondary indices from scratch after pruning.
        # This is simpler and safer than trying to selectively remove
        # entries from the lists (which may hold stale references).
        self._rebuild_indices()

        logger.debug(
            "[WISDOM] Pruned %d shard(s). Store size: %d / %d",
            len(removed), len(self._shards), self.max_shards,
        )

    def _rebuild_indices(self) -> None:
        """Rebuild lineage and domain indices from the primary shard list.
        Caller must hold *_lock*."""
        self._lineage_index.clear()
        self._domain_index.clear()
        for shard in self._shards:
            self._lineage_index[shard.lineage_key].append(shard)
            self._domain_index[shard.domain].append(shard)

    # ------------------------------------------------------------------
    # Bias queries
    # ------------------------------------------------------------------

    def get_bias(self, lineage_key: str, bias_type: str) -> float:
        """
        Return the fitness-weighted average bias for *lineage_key*.

        Parameters
        ----------
        lineage_key : str
            The family / i-state key to look up.
        bias_type : str
            One of ``"tone_bias"`` or ``"structure_bias"``.

        Returns
        -------
        float
            Weighted average in [-1, 1].  Returns 0.0 when no shards
            exist for the given lineage_key.
        """
        if bias_type not in VALID_BIAS_TYPES:
            raise ValueError(
                f"Invalid bias_type '{bias_type}'. "
                f"Must be one of {sorted(VALID_BIAS_TYPES)}."
            )

        with self._lock:
            shards = self._lineage_index.get(lineage_key)
            if not shards:
                return 0.0

            total_weight = 0.0
            weighted_sum = 0.0
            for shard in shards:
                weight = max(0.001, shard.fitness_at_death)
                bias_value = getattr(shard, bias_type)
                weighted_sum += bias_value * weight
                total_weight += weight

            if total_weight == 0.0:
                return 0.0
            return max(-1.0, min(1.0, weighted_sum / total_weight))

    def get_domain_summary(self, domain: str) -> Dict[str, Any]:
        """
        Aggregate statistics for all shards belonging to *domain*.

        Returns a dict with keys:
            count, avg_tone_bias, avg_structure_bias,
            avg_fitness, min_fitness, max_fitness,
            generation_span (min_gen, max_gen),
            cause_distribution (dict of cause -> count).
        Returns an empty summary dict when no shards exist for the domain.
        """
        with self._lock:
            shards = self._domain_index.get(domain, [])
            if not shards:
                return {
                    "domain": domain,
                    "count": 0,
                    "avg_tone_bias": 0.0,
                    "avg_structure_bias": 0.0,
                    "avg_fitness": 0.0,
                    "min_fitness": 0.0,
                    "max_fitness": 0.0,
                    "generation_span": (0, 0),
                    "cause_distribution": {},
                }

            n = len(shards)
            tone_sum = sum(s.tone_bias for s in shards)
            struct_sum = sum(s.structure_bias for s in shards)
            fitness_vals = [s.fitness_at_death for s in shards]
            generations = [s.generation for s in shards]
            cause_counts: Dict[str, int] = defaultdict(int)
            for s in shards:
                cause_counts[s.cause_of_death] += 1

            return {
                "domain": domain,
                "count": n,
                "avg_tone_bias": round(tone_sum / n, 6),
                "avg_structure_bias": round(struct_sum / n, 6),
                "avg_fitness": round(sum(fitness_vals) / n, 6),
                "min_fitness": round(min(fitness_vals), 6),
                "max_fitness": round(max(fitness_vals), 6),
                "generation_span": (min(generations), max(generations)),
                "cause_distribution": dict(cause_counts),
            }

    # ------------------------------------------------------------------
    # Bulk / query helpers
    # ------------------------------------------------------------------

    def get_shards_for_lineage(self, lineage_key: str) -> List[WisdomShard]:
        """Return a copy of the shard list for a lineage key."""
        with self._lock:
            return list(self._lineage_index.get(lineage_key, []))

    def get_all_lineage_keys(self) -> List[str]:
        """Return all lineage keys that have at least one shard."""
        with self._lock:
            return list(self._lineage_index.keys())

    def clear(self) -> None:
        """Remove all shards."""
        with self._lock:
            self._shards.clear()
            self._lineage_index.clear()
            self._domain_index.clear()

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "max_shards": self.max_shards,
                "shards": [s.to_dict() for s in self._shards],
            }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ExpressionWisdomStore":
        store = cls(max_shards=data.get("max_shards", MAX_SHARDS))
        for shard_data in data.get("shards", []):
            try:
                store.add_shard(WisdomShard.from_dict(shard_data))
            except (KeyError, ValueError) as exc:
                logger.warning("[WISDOM] Skipping malformed shard: %s", exc)
        return store


# ---------------------------------------------------------------------------
# Wisdom Application (response assembly integration)
# ---------------------------------------------------------------------------

class WisdomAdjuster:
    """
    Applies wisdom biases during response assembly.

    Given a lineage_key the adjuster retrieves the stored tone and
    structure biases and produces adjustment factors that the response
    assembler can blend into its probability distributions.

    Executive control constraints are honoured: if any of the flags in
    *active_constraints* overlap with :data:`EXECUTIVE_CONSTRAINTS`, the
    adjuster returns zero adjustments so that the constraint system
    retains full authority.
    """

    def __init__(
        self,
        store: ExpressionWisdomStore,
        tone_weight: float = 0.3,
        structure_weight: float = 0.3,
        novelty_weight: float = 0.2,
    ) -> None:
        self.store = store

        # Blending weights -- how much influence wisdom has vs. the base
        # distribution.  Kept modest so wisdom nudges rather than dictates.
        self.tone_weight = max(0.0, min(1.0, tone_weight))
        self.structure_weight = max(0.0, min(1.0, structure_weight))
        self.novelty_weight = max(0.0, min(1.0, novelty_weight))

    def compute_adjustments(
        self,
        lineage_key: str,
        active_constraints: Optional[frozenset] = None,
    ) -> Dict[str, float]:
        """
        Compute response-assembly adjustments from stored wisdom.

        Parameters
        ----------
        lineage_key : str
            The lineage family to query biases for.
        active_constraints : frozenset, optional
            Currently active executive-control flags.  If any overlap
            with ``EXECUTIVE_CONSTRAINTS`` the adjuster yields zero
            adjustments.

        Returns
        -------
        dict
            Keys: ``tone_adjustment``, ``structure_adjustment``,
            ``novelty_adjustment``.  All values in [-1, 1].
        """
        zero_result = {
            "tone_adjustment": 0.0,
            "structure_adjustment": 0.0,
            "novelty_adjustment": 0.0,
        }

        # Respect executive control -- never override safety constraints.
        if active_constraints and active_constraints & EXECUTIVE_CONSTRAINTS:
            logger.debug(
                "[WISDOM] Executive constraint active (%s); returning zero adjustments.",
                active_constraints & EXECUTIVE_CONSTRAINTS,
            )
            return zero_result

        tone_bias = self.store.get_bias(lineage_key, "tone_bias")
        structure_bias = self.store.get_bias(lineage_key, "structure_bias")

        if tone_bias == 0.0 and structure_bias == 0.0:
            return zero_result

        # Novelty tolerance is derived from the *inverse* of structure bias:
        # high structure preference implies low novelty tolerance and vice-versa.
        novelty_raw = -structure_bias

        return {
            "tone_adjustment": round(
                max(-1.0, min(1.0, tone_bias * self.tone_weight)), 6
            ),
            "structure_adjustment": round(
                max(-1.0, min(1.0, structure_bias * self.structure_weight)), 6
            ),
            "novelty_adjustment": round(
                max(-1.0, min(1.0, novelty_raw * self.novelty_weight)), 6
            ),
        }

    def apply_to_probabilities(
        self,
        base_probs: Dict[str, float],
        lineage_key: str,
        active_constraints: Optional[frozenset] = None,
    ) -> Dict[str, float]:
        """
        Blend wisdom adjustments into a base probability distribution
        for tone selection.

        *base_probs* maps tone labels to raw probabilities (need not sum
        to 1 -- they are re-normalised after adjustment).

        The tone_adjustment shifts warm/positive tones up (when positive)
        or down (when negative) and cold/formal tones inversely.
        """
        adjustments = self.compute_adjustments(lineage_key, active_constraints)
        tone_adj = adjustments["tone_adjustment"]

        if tone_adj == 0.0:
            return dict(base_probs)

        # Heuristic: tones whose name contains "warm", "friendly", "casual"
        # receive positive shift; "formal", "cold", "neutral" receive negative
        # shift.  All others receive half-shift.
        warm_tokens = {"warm", "friendly", "casual", "playful", "enthusiastic"}
        cold_tokens = {"formal", "cold", "neutral", "reserved", "curt"}

        adjusted: Dict[str, float] = {}
        for label, prob in base_probs.items():
            lower_label = label.lower()
            if any(tok in lower_label for tok in warm_tokens):
                delta = tone_adj * 0.15
            elif any(tok in lower_label for tok in cold_tokens):
                delta = -tone_adj * 0.15
            else:
                delta = tone_adj * 0.05

            adjusted[label] = max(0.001, prob + delta)

        # Re-normalise so probabilities sum to 1.
        total = sum(adjusted.values())
        if total > 0.0:
            adjusted = {k: v / total for k, v in adjusted.items()}

        return adjusted
