#!/usr/bin/env python3
"""
Perception Maturity Metrics & Plateau-Aware Decay
===================================================
Agora AI Platform - Offline Engine

Tracks per-domain and per-family maturity metrics for the perception pipeline.
Computes maturity scores from stability, novelty rate, and compression ratio
to drive plateau-aware decay and distillation decisions.

Maturity Metrics (Per Domain + Per Family):
    novelty_rate       in [0, 1]  -- EMA of new stable concepts per N samples
    stability          in [0, 1]  -- 1 - EMA centroid drift magnitude
    compression_ratio  in (0, 1]  -- ratio of compressed to raw representation size
    maturity_score     in [0, 1]  -- weighted composite

Maturity formula:
    maturity = clamp01(0.55 * stability + 0.35 * (1 - novelty_rate) + 0.10 * compression_ratio)

Plateau-Aware Decay:
    d = d0 * (0.15 + 0.85 * (1 - m))
    High maturity -> slower decay, low maturity -> normal decay.

Baseline Builder Distillation Rule:
    When domain maturity >= 0.80, signal readiness for distillation.
"""

import time
import logging
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

# Maturity formula weights
WEIGHT_STABILITY = 0.55
WEIGHT_NOVELTY = 0.35
WEIGHT_COMPRESSION = 0.10

# EMA smoothing factor (higher = more responsive to recent observations)
DEFAULT_EMA_ALPHA = 0.15

# Sample window for novelty rate calculation
DEFAULT_NOVELTY_WINDOW = 50

# Distillation trigger threshold
DISTILLATION_MATURITY_THRESHOLD = 0.80

# Plateau-aware decay parameters
DECAY_FLOOR = 0.15
DECAY_CEILING = 0.85

# Minimum concept floors per domain to prevent catastrophic forgetting
DEFAULT_CONCEPT_FLOORS = {
    "vision": 10,
    "audio": 8,
    "language": 12,
    "multimodal": 6,
}


# ============================================================================
# HELPERS
# ============================================================================

def _clamp01(x: float) -> float:
    """Clamp a value to the [0, 1] range."""
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _ema_update(current: float, new_value: float, alpha: float) -> float:
    """Exponential moving average update."""
    return alpha * new_value + (1.0 - alpha) * current


# ============================================================================
# PER-FAMILY METRICS
# ============================================================================

class FamilyMetrics:
    """
    Maturity metrics for a single concept family within a domain.

    A family is a subcategory (e.g. 'edge_shapes' within the 'vision' domain,
    or 'phonetic_vowels' within the 'audio' domain).
    """

    __slots__ = (
        "domain", "family", "novelty_rate", "stability",
        "compression_ratio", "maturity_score", "_total_samples",
        "_new_concepts_ema", "_drift_ema", "_compression_ema",
        "_ema_alpha", "_novelty_window", "_last_updated",
    )

    def __init__(self, domain: str, family: str,
                 ema_alpha: float = DEFAULT_EMA_ALPHA,
                 novelty_window: int = DEFAULT_NOVELTY_WINDOW):
        self.domain = domain
        self.family = family

        # Public metrics -- all start at neutral values
        self.novelty_rate: float = 0.5
        self.stability: float = 0.5
        self.compression_ratio: float = 1.0
        self.maturity_score: float = 0.0

        # Internal accumulators
        self._total_samples: int = 0
        self._new_concepts_ema: float = 0.5
        self._drift_ema: float = 0.5
        self._compression_ema: float = 1.0

        # Configuration
        self._ema_alpha: float = ema_alpha
        self._novelty_window: int = max(1, novelty_window)
        self._last_updated: float = time.time()

    # ------------------------------------------------------------------
    # UPDATE
    # ------------------------------------------------------------------

    def update(self, new_concepts_count: int, total_samples: int,
               centroid_drift: float, compression_ratio: float) -> float:
        """
        Ingest a new observation and recompute maturity.

        Args:
            new_concepts_count: Number of new stable concepts in the latest batch.
            total_samples:      Total samples processed so far in the window.
            centroid_drift:     Magnitude of centroid movement (0 = no drift).
            compression_ratio:  Current compression ratio in (0, 1].

        Returns:
            Updated maturity_score.
        """
        self._total_samples = total_samples

        # -- Novelty rate: fraction of new concepts per window --
        window = max(1, min(total_samples, self._novelty_window))
        raw_novelty = _clamp01(new_concepts_count / window)
        self._new_concepts_ema = _ema_update(
            self._new_concepts_ema, raw_novelty, self._ema_alpha
        )
        self.novelty_rate = _clamp01(self._new_concepts_ema)

        # -- Stability: 1 - EMA of centroid drift magnitude --
        clamped_drift = _clamp01(centroid_drift)
        self._drift_ema = _ema_update(
            self._drift_ema, clamped_drift, self._ema_alpha
        )
        self.stability = _clamp01(1.0 - self._drift_ema)

        # -- Compression ratio: EMA --
        clamped_cr = _clamp01(compression_ratio) if compression_ratio <= 1.0 else 1.0
        # Ensure strictly > 0
        clamped_cr = max(1e-6, clamped_cr)
        self._compression_ema = _ema_update(
            self._compression_ema, clamped_cr, self._ema_alpha
        )
        self.compression_ratio = _clamp01(self._compression_ema)

        # -- Maturity composite --
        self.maturity_score = _clamp01(
            WEIGHT_STABILITY * self.stability
            + WEIGHT_NOVELTY * (1.0 - self.novelty_rate)
            + WEIGHT_COMPRESSION * self.compression_ratio
        )

        self._last_updated = time.time()
        return self.maturity_score

    # ------------------------------------------------------------------
    # SERIALIZATION
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "family": self.family,
            "novelty_rate": self.novelty_rate,
            "stability": self.stability,
            "compression_ratio": self.compression_ratio,
            "maturity_score": self.maturity_score,
            "_total_samples": self._total_samples,
            "_new_concepts_ema": self._new_concepts_ema,
            "_drift_ema": self._drift_ema,
            "_compression_ema": self._compression_ema,
            "_ema_alpha": self._ema_alpha,
            "_novelty_window": self._novelty_window,
            "_last_updated": self._last_updated,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FamilyMetrics":
        fm = cls(
            domain=data["domain"],
            family=data["family"],
            ema_alpha=data.get("_ema_alpha", DEFAULT_EMA_ALPHA),
            novelty_window=data.get("_novelty_window", DEFAULT_NOVELTY_WINDOW),
        )
        fm.novelty_rate = data.get("novelty_rate", 0.5)
        fm.stability = data.get("stability", 0.5)
        fm.compression_ratio = data.get("compression_ratio", 1.0)
        fm.maturity_score = data.get("maturity_score", 0.0)
        fm._total_samples = data.get("_total_samples", 0)
        fm._new_concepts_ema = data.get("_new_concepts_ema", 0.5)
        fm._drift_ema = data.get("_drift_ema", 0.5)
        fm._compression_ema = data.get("_compression_ema", 1.0)
        fm._last_updated = data.get("_last_updated", time.time())
        return fm

    def __repr__(self) -> str:
        return (
            f"FamilyMetrics(domain={self.domain!r}, family={self.family!r}, "
            f"maturity={self.maturity_score:.3f}, stability={self.stability:.3f}, "
            f"novelty={self.novelty_rate:.3f}, compression={self.compression_ratio:.3f})"
        )


# ============================================================================
# MATURITY TRACKER
# ============================================================================

class MaturityTracker:
    """
    Central tracker for perception maturity across domains and concept families.

    Maintains per-domain and per-family FamilyMetrics, computes aggregate
    domain maturity, drives plateau-aware decay, and signals distillation
    readiness.
    """

    def __init__(self, ema_alpha: float = DEFAULT_EMA_ALPHA,
                 novelty_window: int = DEFAULT_NOVELTY_WINDOW,
                 concept_floors: Optional[Dict[str, int]] = None):
        """
        Args:
            ema_alpha:      Smoothing factor for EMA updates.
            novelty_window: Sample window for novelty rate calculation.
            concept_floors: Minimum concept counts per domain to prevent
                            catastrophic forgetting. Falls back to defaults.
        """
        # family_key = (domain, family) -> FamilyMetrics
        self._families: Dict[Tuple[str, str], FamilyMetrics] = {}

        # Aggregate domain maturity cache: domain -> float
        self._domain_maturity: Dict[str, float] = {}

        # Configuration
        self._ema_alpha = ema_alpha
        self._novelty_window = novelty_window
        self._concept_floors: Dict[str, int] = dict(DEFAULT_CONCEPT_FLOORS)
        if concept_floors:
            self._concept_floors.update(concept_floors)

    # ------------------------------------------------------------------
    # CORE API
    # ------------------------------------------------------------------

    def update(self, domain: str, family: str,
               new_concepts_count: int, total_samples: int,
               centroid_drift: float, compression_ratio: float) -> float:
        """
        Record an observation for a (domain, family) pair and recompute maturity.

        Args:
            domain:             Perception domain (e.g. "vision", "audio").
            family:             Concept family within the domain.
            new_concepts_count: New stable concepts in the latest batch.
            total_samples:      Total samples processed so far.
            centroid_drift:     Magnitude of centroid movement.
            compression_ratio:  Compression ratio for this family.

        Returns:
            Updated maturity score for the (domain, family) pair.
        """
        key = (domain, family)
        if key not in self._families:
            self._families[key] = FamilyMetrics(
                domain=domain,
                family=family,
                ema_alpha=self._ema_alpha,
                novelty_window=self._novelty_window,
            )

        score = self._families[key].update(
            new_concepts_count, total_samples,
            centroid_drift, compression_ratio,
        )

        # Recompute aggregate domain maturity
        self._recompute_domain_maturity(domain)

        logger.debug(
            f"[MATURITY] {domain}/{family}: maturity={score:.3f} "
            f"(stability={self._families[key].stability:.3f}, "
            f"novelty={self._families[key].novelty_rate:.3f}, "
            f"compression={self._families[key].compression_ratio:.3f})"
        )

        return score

    def get_maturity(self, domain: str, family: Optional[str] = None) -> float:
        """
        Retrieve the maturity score.

        Args:
            domain: Perception domain.
            family: If provided, return family-level maturity.
                    If None, return aggregate domain maturity.

        Returns:
            Maturity score in [0, 1]. Returns 0.0 if the key is not tracked.
        """
        if family is not None:
            key = (domain, family)
            fm = self._families.get(key)
            return fm.maturity_score if fm else 0.0

        return self._domain_maturity.get(domain, 0.0)

    def get_decay_rate(self, domain: str, family: Optional[str] = None,
                       base_decay: float = 0.05) -> float:
        """
        Compute the plateau-aware decay rate.

        Formula: d = d0 * (0.15 + 0.85 * (1 - m))
            - High maturity (m ~ 1) => d ~ d0 * 0.15 (slow decay)
            - Low  maturity (m ~ 0) => d ~ d0 * 1.00 (normal decay)

        Args:
            domain:     Perception domain.
            family:     Optional concept family. Uses domain aggregate if None.
            base_decay: The base decay rate d0.

        Returns:
            Adjusted decay rate.
        """
        m = self.get_maturity(domain, family)
        return base_decay * (DECAY_FLOOR + DECAY_CEILING * (1.0 - m))

    def should_distill(self, domain: str) -> bool:
        """
        Check whether a domain has reached the maturity threshold for
        baseline builder distillation.

        Trigger: domain maturity >= 0.80

        Args:
            domain: Perception domain.

        Returns:
            True if the domain is ready for distillation.
        """
        return self.get_maturity(domain) >= DISTILLATION_MATURITY_THRESHOLD

    def get_concept_floor(self, domain: str) -> int:
        """
        Return the minimum number of concepts that must be preserved for a
        domain to prevent catastrophic forgetting.

        Args:
            domain: Perception domain.

        Returns:
            Concept floor count.
        """
        return self._concept_floors.get(domain, DEFAULT_CONCEPT_FLOORS.get("multimodal", 6))

    # ------------------------------------------------------------------
    # FAMILY ENUMERATION
    # ------------------------------------------------------------------

    def get_families(self, domain: Optional[str] = None) -> List[Tuple[str, str]]:
        """
        List tracked (domain, family) pairs.

        Args:
            domain: If provided, filter to families within this domain.

        Returns:
            List of (domain, family) tuples.
        """
        if domain is not None:
            return [(d, f) for (d, f) in self._families if d == domain]
        return list(self._families.keys())

    def get_family_metrics(self, domain: str, family: str) -> Optional[FamilyMetrics]:
        """Retrieve the FamilyMetrics object for a specific (domain, family)."""
        return self._families.get((domain, family))

    def get_all_metrics(self, domain: Optional[str] = None) -> Dict[str, Any]:
        """
        Return a summary dict of all tracked metrics.

        Args:
            domain: If provided, filter to this domain only.

        Returns:
            Dict with domain aggregates and per-family detail.
        """
        result: Dict[str, Any] = {
            "domain_maturity": dict(self._domain_maturity),
            "families": {},
        }
        for (d, f), fm in self._families.items():
            if domain is not None and d != domain:
                continue
            result["families"][f"{d}/{f}"] = {
                "maturity": fm.maturity_score,
                "stability": fm.stability,
                "novelty_rate": fm.novelty_rate,
                "compression_ratio": fm.compression_ratio,
                "total_samples": fm._total_samples,
            }
        return result

    # ------------------------------------------------------------------
    # DOMAIN MATURITY AGGREGATION
    # ------------------------------------------------------------------

    def _recompute_domain_maturity(self, domain: str) -> None:
        """
        Recompute aggregate maturity for a domain as the weighted mean of
        all families, where the weight is the number of samples processed
        by each family (more data = more authoritative).
        """
        families_in_domain = [
            fm for (d, _), fm in self._families.items() if d == domain
        ]
        if not families_in_domain:
            self._domain_maturity[domain] = 0.0
            return

        total_weight = 0.0
        weighted_sum = 0.0
        for fm in families_in_domain:
            weight = max(1.0, float(fm._total_samples))
            weighted_sum += fm.maturity_score * weight
            total_weight += weight

        self._domain_maturity[domain] = (
            _clamp01(weighted_sum / total_weight) if total_weight > 0 else 0.0
        )

    # ------------------------------------------------------------------
    # SERIALIZATION
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize the entire tracker state to a JSON-safe dict."""
        return {
            "ema_alpha": self._ema_alpha,
            "novelty_window": self._novelty_window,
            "concept_floors": self._concept_floors,
            "domain_maturity": dict(self._domain_maturity),
            "families": {
                f"{d}|{f}": fm.to_dict()
                for (d, f), fm in self._families.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MaturityTracker":
        """Deserialize a MaturityTracker from a dict."""
        tracker = cls(
            ema_alpha=data.get("ema_alpha", DEFAULT_EMA_ALPHA),
            novelty_window=data.get("novelty_window", DEFAULT_NOVELTY_WINDOW),
            concept_floors=data.get("concept_floors"),
        )
        tracker._domain_maturity = dict(data.get("domain_maturity", {}))
        for key_str, fm_data in data.get("families", {}).items():
            parts = key_str.split("|", 1)
            if len(parts) != 2:
                logger.warning(f"[MATURITY] Skipping malformed family key: {key_str}")
                continue
            domain, family = parts
            fm = FamilyMetrics.from_dict(fm_data)
            tracker._families[(domain, family)] = fm
        return tracker

    def __repr__(self) -> str:
        domains = sorted(self._domain_maturity.keys())
        domain_strs = ", ".join(
            f"{d}={self._domain_maturity[d]:.3f}" for d in domains
        )
        return (
            f"MaturityTracker(families={len(self._families)}, "
            f"domains=[{domain_strs}])"
        )
