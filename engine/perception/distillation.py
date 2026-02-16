#!/usr/bin/env python3
"""
Perception Distillation Engine
================================
Agora AI Platform - Offline Engine

Converts mature baseline builder structures into compact tag/prior
representations, prunes redundant low-level nodes, and enforces concept
floors to prevent catastrophic forgetting.

Trigger:
    Domain maturity >= 0.80 (from MaturityTracker.should_distill).

Actions:
    1. Convert baseline builder structures into tags/priors.
    2. Prune redundant low-level nodes.
    3. Preserve: concept centroids, hybrid graph, tags and minimal
       reconstruction hints, lineage pointers.
    4. Enforce concept floors per domain.

Vision tag types:
    - shape_compactness_bin
    - dominant_hue_band
    - edge_orientation_signature
    - motion_signature

Audio tag types:
    - concept centroids/radii
    - rhythm templates
    - tags/priors
"""

import math
import time
import logging
import hashlib
from typing import Any, Dict, List, Optional, Tuple

from .maturity import MaturityTracker, DISTILLATION_MATURITY_THRESHOLD

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

# Vision tag type identifiers
VISION_TAG_SHAPE_COMPACTNESS = "shape_compactness_bin"
VISION_TAG_DOMINANT_HUE = "dominant_hue_band"
VISION_TAG_EDGE_ORIENTATION = "edge_orientation_signature"
VISION_TAG_MOTION = "motion_signature"

VISION_TAG_TYPES = [
    VISION_TAG_SHAPE_COMPACTNESS,
    VISION_TAG_DOMINANT_HUE,
    VISION_TAG_EDGE_ORIENTATION,
    VISION_TAG_MOTION,
]

# Audio tag type identifiers
AUDIO_TAG_CENTROID = "concept_centroid"
AUDIO_TAG_RADIUS = "concept_radius"
AUDIO_TAG_RHYTHM = "rhythm_template"
AUDIO_TAG_PRIOR = "audio_prior"

AUDIO_TAG_TYPES = [
    AUDIO_TAG_CENTROID,
    AUDIO_TAG_RADIUS,
    AUDIO_TAG_RHYTHM,
    AUDIO_TAG_PRIOR,
]

# Shape compactness bin boundaries
# Compactness = 4 * pi * area / perimeter^2, range [0, 1]
COMPACTNESS_BINS = [
    (0.00, 0.25, "elongated"),
    (0.25, 0.50, "irregular"),
    (0.50, 0.75, "rounded"),
    (0.75, 1.01, "compact"),
]

# Hue band boundaries (degrees on a 360 colour wheel)
HUE_BANDS = [
    (0, 30, "red"),
    (30, 60, "orange"),
    (60, 90, "yellow"),
    (90, 150, "green"),
    (150, 210, "cyan"),
    (210, 270, "blue"),
    (270, 330, "purple"),
    (330, 360, "red"),
]

# Default prune cap when no explicit cap is supplied
DEFAULT_PRUNE_CAP = 200

# Minimum confidence threshold below which a concept is a prune candidate
PRUNE_CONFIDENCE_THRESHOLD = 0.35


# ============================================================================
# TAG GENERATION HELPERS
# ============================================================================

def _tag_id(tag_type: str, source_id: str) -> str:
    """Generate a deterministic tag ID from type and source."""
    digest = hashlib.sha256(f"{tag_type}:{source_id}".encode()).hexdigest()[:12]
    return f"tag_{tag_type}_{digest}"


def _classify_compactness(compactness: float) -> str:
    """Bin a compactness value into a human-readable category."""
    for lo, hi, label in COMPACTNESS_BINS:
        if lo <= compactness < hi:
            return label
    return "unknown"


def _classify_hue(hue_degrees: float) -> str:
    """Bin a hue value (0-360) into a colour band."""
    hue_degrees = hue_degrees % 360.0
    for lo, hi, label in HUE_BANDS:
        if lo <= hue_degrees < hi:
            return label
    return "unknown"


def _quantize_orientation(angles: List[float], num_bins: int = 8) -> List[int]:
    """
    Quantize a list of edge orientation angles into a histogram signature.

    Args:
        angles:   List of angles in degrees [0, 180).
        num_bins: Number of histogram bins.

    Returns:
        Histogram as a list of counts.
    """
    bin_width = 180.0 / num_bins
    histogram = [0] * num_bins
    for angle in angles:
        idx = min(int(angle / bin_width), num_bins - 1)
        histogram[idx] += 1
    return histogram


def _compute_centroid_radius(vectors: List[List[float]]) -> Tuple[List[float], float]:
    """
    Compute the centroid and maximum radius for a set of vectors.

    Returns:
        (centroid, radius) where radius is the max Euclidean distance from
        centroid to any member vector.
    """
    if not vectors:
        return [], 0.0

    dim = len(vectors[0])
    centroid = [0.0] * dim
    for v in vectors:
        for i in range(dim):
            centroid[i] += v[i]
    n = len(vectors)
    centroid = [c / n for c in centroid]

    max_dist = 0.0
    for v in vectors:
        dist = math.sqrt(sum((a - b) ** 2 for a, b in zip(v, centroid)))
        max_dist = max(max_dist, dist)

    return centroid, max_dist


# ============================================================================
# DISTILLATION ENGINE
# ============================================================================

class DistillationEngine:
    """
    Converts mature baseline builder structures into compact tag/prior
    representations and prunes redundant low-level data.

    Lifecycle:
        1. check_and_distill() is called during consolidation when
           MaturityTracker.should_distill(domain) returns True.
        2. The engine converts concept data into tags/priors.
        3. Redundant low-level nodes are pruned respecting concept floors.
        4. Centroids, hybrid graphs, lineage pointers, and minimal
           reconstruction hints are preserved.
    """

    def __init__(self):
        # History of distillation runs for observability
        self._history: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # PRIMARY ENTRY POINT
    # ------------------------------------------------------------------

    def check_and_distill(
        self,
        domain: str,
        maturity_tracker: MaturityTracker,
        concepts: Dict[str, Any],
        hybrids: Dict[str, Any],
        concept_floor: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Check maturity and run distillation if the domain is ready.

        Args:
            domain:           Perception domain ("vision", "audio", etc.).
            maturity_tracker: The active MaturityTracker instance.
            concepts:         Dict of concept_id -> concept data.
                              Each concept dict should include at minimum:
                                  - "centroid": list[float]
                                  - "confidence": float
                                  - "lineage": str (optional)
                              Vision concepts may also include:
                                  - "compactness": float
                                  - "dominant_hue": float (degrees)
                                  - "edge_orientations": list[float]
                                  - "motion_vectors": list[list[float]]
                              Audio concepts may also include:
                                  - "acoustic_centroid": list[float]
                                  - "category_hypothesis": str
                                  - "rhythm_pattern": dict
            hybrids:          Hybrid graph entries, kept intact.
            concept_floor:    Minimum concepts to retain. Uses tracker
                              default if None.

        Returns:
            Dict with:
                - "distilled": bool
                - "domain": str
                - "maturity": float
                - "tags": list[dict]              (generated tags)
                - "pruned_count": int             (concepts removed)
                - "retained_count": int           (concepts kept)
                - "preserved_centroids": int      (centroids preserved)
                - "timestamp": float
        """
        maturity = maturity_tracker.get_maturity(domain)
        should = maturity_tracker.should_distill(domain)

        result: Dict[str, Any] = {
            "distilled": False,
            "domain": domain,
            "maturity": maturity,
            "tags": [],
            "pruned_count": 0,
            "retained_count": len(concepts),
            "preserved_centroids": 0,
            "timestamp": time.time(),
        }

        if not should:
            logger.debug(
                f"[DISTILL] Domain '{domain}' maturity {maturity:.3f} "
                f"below threshold {DISTILLATION_MATURITY_THRESHOLD}. Skipping."
            )
            return result

        logger.info(
            f"[DISTILL] Domain '{domain}' maturity {maturity:.3f} >= "
            f"{DISTILLATION_MATURITY_THRESHOLD}. Starting distillation."
        )

        # Resolve concept floor
        floor = concept_floor if concept_floor is not None else (
            maturity_tracker.get_concept_floor(domain)
        )

        # Step 1: Convert concepts into tags/priors
        tags = self.distill_to_tags(concepts)

        # Step 2: Domain-specific distillation
        if domain == "vision":
            tags = self.distill_vision(concepts, hybrids, tags)
        elif domain == "audio":
            tags = self.distill_audio(concepts, hybrids, tags)

        # Step 3: Prune redundant low-level nodes
        prune_keys = self.prune_candidates(concepts, cap=DEFAULT_PRUNE_CAP, floor=floor)
        for key in prune_keys:
            del concepts[key]

        # Step 4: Count preserved centroids
        preserved_centroids = sum(
            1 for c in concepts.values()
            if isinstance(c, dict) and ("centroid" in c or "acoustic_centroid" in c)
        )

        result["distilled"] = True
        result["tags"] = tags
        result["pruned_count"] = len(prune_keys)
        result["retained_count"] = len(concepts)
        result["preserved_centroids"] = preserved_centroids

        # Record in history
        self._history.append(result)

        logger.info(
            f"[DISTILL] Domain '{domain}' distillation complete. "
            f"Tags={len(tags)}, Pruned={len(prune_keys)}, "
            f"Retained={len(concepts)}, Centroids={preserved_centroids}."
        )

        return result

    # ------------------------------------------------------------------
    # TAG GENERATION
    # ------------------------------------------------------------------

    def distill_to_tags(self, concepts: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Convert baseline builder concept structures into a list of tag dicts.

        Each tag dict contains:
            - "id":        Unique tag identifier.
            - "type":      Tag type string.
            - "source_id": ID of the originating concept.
            - "value":     The extracted tag value.
            - "confidence": Inherited from the concept.
            - "timestamp": When the tag was created.

        This is the domain-agnostic pass. Domain-specific enrichment
        happens in distill_vision() and distill_audio().

        Args:
            concepts: Dict of concept_id -> concept data.

        Returns:
            List of tag dicts.
        """
        tags: List[Dict[str, Any]] = []
        now = time.time()

        for concept_id, concept in concepts.items():
            if not isinstance(concept, dict):
                continue

            confidence = concept.get("confidence", 0.5)

            # -- Centroid tag (universal) --
            centroid = concept.get("centroid") or concept.get("acoustic_centroid")
            if centroid and isinstance(centroid, (list, tuple)):
                tags.append({
                    "id": _tag_id("centroid", concept_id),
                    "type": "centroid",
                    "source_id": concept_id,
                    "value": list(centroid),
                    "confidence": confidence,
                    "timestamp": now,
                })

            # -- Lineage pointer (universal) --
            lineage = concept.get("lineage")
            if lineage:
                tags.append({
                    "id": _tag_id("lineage", concept_id),
                    "type": "lineage_pointer",
                    "source_id": concept_id,
                    "value": lineage,
                    "confidence": confidence,
                    "timestamp": now,
                })

            # -- Reconstruction hint --
            # Minimal data needed to reconstruct the concept from the centroid
            label_hypotheses = concept.get("label_hypotheses")
            if label_hypotheses:
                tags.append({
                    "id": _tag_id("reconstruction_hint", concept_id),
                    "type": "reconstruction_hint",
                    "source_id": concept_id,
                    "value": {
                        "label_hypotheses": label_hypotheses,
                        "confidence": confidence,
                    },
                    "confidence": confidence,
                    "timestamp": now,
                })

        return tags

    # ------------------------------------------------------------------
    # DOMAIN-SPECIFIC: VISION
    # ------------------------------------------------------------------

    def distill_vision(
        self,
        concepts: Dict[str, Any],
        hybrids: Dict[str, Any],
        tags: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Vision-specific distillation pass.

        Generates additional tags:
            - shape_compactness_bin
            - dominant_hue_band
            - edge_orientation_signature
            - motion_signature

        Preserves hybrid graph entries and concept centroids.

        Args:
            concepts: Vision concept dict.
            hybrids:  Hybrid graph entries (preserved intact).
            tags:     Tags from the generic distill_to_tags pass.

        Returns:
            Augmented list of tags.
        """
        now = time.time()

        for concept_id, concept in concepts.items():
            if not isinstance(concept, dict):
                continue

            confidence = concept.get("confidence", 0.5)

            # -- Shape compactness bin --
            compactness = concept.get("compactness")
            if compactness is not None:
                bin_label = _classify_compactness(float(compactness))
                tags.append({
                    "id": _tag_id(VISION_TAG_SHAPE_COMPACTNESS, concept_id),
                    "type": VISION_TAG_SHAPE_COMPACTNESS,
                    "source_id": concept_id,
                    "value": {
                        "raw": float(compactness),
                        "bin": bin_label,
                    },
                    "confidence": confidence,
                    "timestamp": now,
                })

            # -- Dominant hue band --
            hue = concept.get("dominant_hue")
            if hue is not None:
                band = _classify_hue(float(hue))
                tags.append({
                    "id": _tag_id(VISION_TAG_DOMINANT_HUE, concept_id),
                    "type": VISION_TAG_DOMINANT_HUE,
                    "source_id": concept_id,
                    "value": {
                        "raw_degrees": float(hue),
                        "band": band,
                    },
                    "confidence": confidence,
                    "timestamp": now,
                })

            # -- Edge orientation signature --
            orientations = concept.get("edge_orientations")
            if orientations and isinstance(orientations, (list, tuple)):
                histogram = _quantize_orientation(orientations)
                tags.append({
                    "id": _tag_id(VISION_TAG_EDGE_ORIENTATION, concept_id),
                    "type": VISION_TAG_EDGE_ORIENTATION,
                    "source_id": concept_id,
                    "value": {
                        "histogram": histogram,
                        "num_edges": len(orientations),
                    },
                    "confidence": confidence,
                    "timestamp": now,
                })

            # -- Motion signature --
            motion_vectors = concept.get("motion_vectors")
            if motion_vectors and isinstance(motion_vectors, (list, tuple)):
                # Compute mean motion vector as the signature
                dim = len(motion_vectors[0]) if motion_vectors else 0
                if dim > 0:
                    mean_motion = [0.0] * dim
                    for mv in motion_vectors:
                        for i in range(dim):
                            mean_motion[i] += mv[i]
                    n = len(motion_vectors)
                    mean_motion = [v / n for v in mean_motion]
                    magnitude = math.sqrt(sum(v * v for v in mean_motion))

                    tags.append({
                        "id": _tag_id(VISION_TAG_MOTION, concept_id),
                        "type": VISION_TAG_MOTION,
                        "source_id": concept_id,
                        "value": {
                            "mean_vector": mean_motion,
                            "magnitude": magnitude,
                            "sample_count": n,
                        },
                        "confidence": confidence,
                        "timestamp": now,
                    })

        # Preserve hybrid graph as tags (so they survive pruning)
        for hybrid_id, hybrid_data in hybrids.items():
            tags.append({
                "id": _tag_id("hybrid_graph", hybrid_id),
                "type": "hybrid_graph",
                "source_id": hybrid_id,
                "value": hybrid_data,
                "confidence": 1.0,
                "timestamp": now,
            })

        return tags

    # ------------------------------------------------------------------
    # DOMAIN-SPECIFIC: AUDIO
    # ------------------------------------------------------------------

    def distill_audio(
        self,
        concepts: Dict[str, Any],
        hybrids: Dict[str, Any],
        tags: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Audio-specific distillation pass.

        Preserves:
            - Concept centroids and radii
            - Rhythm templates
            - Tags/priors

        Args:
            concepts:  Audio concept dict (SoundConceptEntry-compatible dicts).
            hybrids:   Hybrid graph entries (preserved intact).
            tags:      Tags from the generic distill_to_tags pass.

        Returns:
            Augmented list of tags.
        """
        now = time.time()

        # Group acoustic vectors for per-category centroid/radius computation
        category_vectors: Dict[str, List[List[float]]] = {}

        for concept_id, concept in concepts.items():
            if not isinstance(concept, dict):
                continue

            confidence = concept.get("confidence", 0.5)
            category = concept.get("category_hypothesis", "unknown")

            # Collect acoustic centroids by category for cluster summary
            acoustic_centroid = concept.get("acoustic_centroid")
            if acoustic_centroid and isinstance(acoustic_centroid, (list, tuple)):
                category_vectors.setdefault(category, []).append(list(acoustic_centroid))

                # Individual concept centroid tag (if not already created by generic pass)
                centroid_tag_id = _tag_id(AUDIO_TAG_CENTROID, concept_id)
                if not any(t["id"] == centroid_tag_id for t in tags):
                    tags.append({
                        "id": centroid_tag_id,
                        "type": AUDIO_TAG_CENTROID,
                        "source_id": concept_id,
                        "value": list(acoustic_centroid),
                        "confidence": confidence,
                        "timestamp": now,
                    })

            # -- Rhythm template --
            rhythm = concept.get("rhythm_pattern")
            if rhythm and isinstance(rhythm, dict):
                tags.append({
                    "id": _tag_id(AUDIO_TAG_RHYTHM, concept_id),
                    "type": AUDIO_TAG_RHYTHM,
                    "source_id": concept_id,
                    "value": rhythm,
                    "confidence": confidence,
                    "timestamp": now,
                })

            # -- Audio prior from intent histogram --
            intent_histogram = concept.get("intent_histogram")
            if intent_histogram and isinstance(intent_histogram, dict):
                # Normalize into a prior distribution
                total = sum(intent_histogram.values())
                if total > 0:
                    prior = {k: v / total for k, v in intent_histogram.items()}
                    tags.append({
                        "id": _tag_id(AUDIO_TAG_PRIOR, concept_id),
                        "type": AUDIO_TAG_PRIOR,
                        "source_id": concept_id,
                        "value": {
                            "intent_prior": prior,
                            "category": category,
                            "total_observations": total,
                        },
                        "confidence": confidence,
                        "timestamp": now,
                    })

            # -- Bound lexeme associations (reconstruction hint) --
            bound_lexemes = concept.get("bound_lexemes")
            if bound_lexemes and isinstance(bound_lexemes, dict):
                tags.append({
                    "id": _tag_id("audio_lexeme_binding", concept_id),
                    "type": "audio_lexeme_binding",
                    "source_id": concept_id,
                    "value": dict(bound_lexemes),
                    "confidence": confidence,
                    "timestamp": now,
                })

        # Per-category centroid & radius summary tags
        for category, vectors in category_vectors.items():
            if len(vectors) < 2:
                continue
            centroid, radius = _compute_centroid_radius(vectors)
            cat_tag_id = _tag_id(AUDIO_TAG_RADIUS, f"category_{category}")
            tags.append({
                "id": cat_tag_id,
                "type": AUDIO_TAG_RADIUS,
                "source_id": f"category_{category}",
                "value": {
                    "category": category,
                    "centroid": centroid,
                    "radius": radius,
                    "member_count": len(vectors),
                },
                "confidence": 1.0,
                "timestamp": now,
            })

        # Preserve hybrid graph
        for hybrid_id, hybrid_data in hybrids.items():
            hybrid_tag_id = _tag_id("hybrid_graph", hybrid_id)
            if not any(t["id"] == hybrid_tag_id for t in tags):
                tags.append({
                    "id": hybrid_tag_id,
                    "type": "hybrid_graph",
                    "source_id": hybrid_id,
                    "value": hybrid_data,
                    "confidence": 1.0,
                    "timestamp": now,
                })

        return tags

    # ------------------------------------------------------------------
    # PRUNING
    # ------------------------------------------------------------------

    def prune_candidates(
        self,
        candidates: Dict[str, Any],
        cap: int = DEFAULT_PRUNE_CAP,
        floor: int = 0,
    ) -> List[str]:
        """
        Identify concept keys that should be pruned.

        Strategy:
            1. Never prune below the concept floor.
            2. Concepts with confidence below PRUNE_CONFIDENCE_THRESHOLD
               are considered redundant/low-value.
            3. Among eligible concepts, prune the lowest-confidence ones
               until the remaining count is at or below the cap.

        Preserved (never pruned):
            - Concepts with a "centroid" or "acoustic_centroid" key
              AND confidence >= PRUNE_CONFIDENCE_THRESHOLD.
            - Concepts with a "lineage" key.

        Args:
            candidates: Dict of concept_id -> concept data.
            cap:        Maximum concepts to retain.
            floor:      Minimum concepts to retain (concept floor).

        Returns:
            List of concept keys to remove from the dict.
        """
        if len(candidates) <= max(floor, 0):
            return []

        # Score each candidate for prunability
        scored: List[Tuple[str, float, bool]] = []
        for cid, concept in candidates.items():
            if not isinstance(concept, dict):
                scored.append((cid, 0.0, False))
                continue

            confidence = concept.get("confidence", 0.0)
            has_centroid = "centroid" in concept or "acoustic_centroid" in concept
            has_lineage = "lineage" in concept

            # Protected: high-confidence centroids or lineage holders
            protected = (has_lineage or (has_centroid and confidence >= PRUNE_CONFIDENCE_THRESHOLD))
            scored.append((cid, confidence, protected))

        # Separate protected and pruneable
        pruneable = [(cid, conf) for cid, conf, protected in scored if not protected]
        protected_count = len(scored) - len(pruneable)

        # Sort pruneable by confidence ascending (weakest first)
        pruneable.sort(key=lambda x: x[1])

        # Determine how many we can prune
        target_count = min(cap, len(candidates))
        # Ensure we keep at least `floor` concepts total
        target_count = max(target_count, floor)

        num_to_keep = max(0, target_count - protected_count)
        num_to_prune = max(0, len(pruneable) - num_to_keep)

        prune_keys = [cid for cid, _ in pruneable[:num_to_prune]]

        # Safety: ensure we never prune below floor
        if len(candidates) - len(prune_keys) < floor:
            excess = floor - (len(candidates) - len(prune_keys))
            prune_keys = prune_keys[:max(0, len(prune_keys) - excess)]

        return prune_keys

    # ------------------------------------------------------------------
    # OBSERVABILITY
    # ------------------------------------------------------------------

    def get_history(self) -> List[Dict[str, Any]]:
        """Return the distillation run history."""
        return list(self._history)

    def get_last_run(self) -> Optional[Dict[str, Any]]:
        """Return the most recent distillation result, or None."""
        return self._history[-1] if self._history else None

    def __repr__(self) -> str:
        return f"DistillationEngine(runs={len(self._history)})"
