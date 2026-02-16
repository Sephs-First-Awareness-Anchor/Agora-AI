#!/usr/bin/env python3
"""
Feature Schemas for Vision and Audio Perception Pipelines
==========================================================
Authors: Sunni (Sir) Morningstar & Cael Devo

Canonical definitions of feature vector schemas used by the Agora AI
perception subsystem.  Every extractor and downstream consumer references
these schemas so that vector layout, index ranges, validation rules,
and metadata are maintained in a single source of truth.

Schemas defined
---------------
* ``vision.features.v1``  --  57-element vision feature vector
* ``audio.features.v1``   --  20-element audio feature vector

Each schema is exposed as:

1. Module-level constants for vector length and slice ranges.
2. A frozen ``FeatureFamily`` dataclass mapping human-readable family names
   to their index slices inside the flat vector.
3. Frozen schema dataclasses (``VisionFeatureSchema``, ``AudioFeatureSchema``)
   aggregating families, parameters, and lookup helpers.
4. Validation functions that verify length and value-range constraints.

Vision Feature Schema: vision.features.v1
------------------------------------------
Fixed vector length: 57

* **HSV histograms (24):** H bins=12, S bins=6, V bins=6, each normalised.
* **Edges + orientation (9):** grayscale, Sobel X/Y 3x3, magnitude +
  orientation, edge_density (1), orientation histogram bins=8 (8).
* **Shape proxy via connected components (18):** edge mask thresholded,
  connected-component labelling on 64x64 (BFS), top K=6 components by area.
  Per component: area_ratio, bbox_aspect, compactness = area/(perimeter^2+eps).
  Padded to 6 components.
* **Motion (4):** diff = abs(curr_gray - prev_gray), motion_energy = mean(diff),
  motion_density = frac(diff > 0.08), motion_bbox_area_ratio, motion_bbox_aspect.
* **Symmetry (2):** horizontal symmetry error, vertical symmetry error.
* **Metadata (not in vector):** mean V (lighting proxy), frame timestamp.

Audio Feature Schema: audio.features.v1
-----------------------------------------
Fixed vector length: 20

Per 1.0 s buffer with window N=1024, hop H=512, Hann window, FFT via
``np.fft.rfft``:

1. RMS energy (1)
2. ZCR (1)
3. Spectral centroid (1)
4. Spectral bandwidth (1)
5. Spectral rolloff 85% (1)
6. Spectral flux mean (1)
7. Harmonicity proxy via autocorrelation peak ratio (1)
8. Onset density proxy (1)
9. Chroma-lite 12-bin distribution (12)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Numpy with graceful fallback
# ---------------------------------------------------------------------------
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False
    logger.warning(
        "[FEATURE_SCHEMAS] NumPy not available -- "
        "validation will use pure-Python fallback"
    )

    class _NumpyFallback:
        """Minimal shim so downstream code can reference ``np`` safely."""

        float32 = float
        float64 = float
        ndarray = list

        @staticmethod
        def asarray(obj, dtype=None):
            """Return *obj* as a plain list (fallback)."""
            if isinstance(obj, list):
                return obj
            return list(obj)

        @staticmethod
        def zeros(n):
            """Return a list of *n* zeros."""
            return [0.0] * n

        @staticmethod
        def array(lst):
            """Return a list copy of *lst*."""
            return list(lst) if not isinstance(lst, list) else lst[:]

        @staticmethod
        def isnan(x):
            """Check for NaN without numpy."""
            try:
                return x != x
            except TypeError:
                return False

        @staticmethod
        def isinf(x):
            """Check for Inf without numpy."""
            try:
                return abs(x) == float("inf")
            except (TypeError, OverflowError):
                return False

    np = _NumpyFallback()  # type: ignore[assignment]


# ============================================================================
# MODULE-LEVEL VECTOR LENGTH CONSTANTS
# ============================================================================

VISION_FEATURE_LENGTH: int = 57
"""Fixed length of the ``vision.features.v1`` vector."""

AUDIO_FEATURE_LENGTH: int = 20
"""Fixed length of the ``audio.features.v1`` vector."""


# ============================================================================
# FEATURE FAMILY DESCRIPTOR
# ============================================================================

@dataclass(frozen=True)
class FeatureFamily:
    """A named slice of a feature vector.

    Parameters
    ----------
    name:
        Human-readable family name (e.g. ``"hsv_histograms"``).
    start:
        Start index (inclusive) in the flat vector.
    stop:
        Stop index (exclusive) in the flat vector.
    description:
        Short prose description of this family.
    value_min:
        Expected minimum value for elements in this family.
    value_max:
        Expected maximum value for elements in this family.
    """

    name: str
    start: int
    stop: int
    description: str = ""
    value_min: float = 0.0
    value_max: float = 1.0

    # -- derived helpers -----------------------------------------------------

    @property
    def length(self) -> int:
        """Number of elements spanned by this family."""
        return self.stop - self.start

    @property
    def slice(self) -> slice:
        """A ``slice`` object suitable for indexing into arrays/lists."""
        return slice(self.start, self.stop)

    @property
    def indices(self) -> Tuple[int, ...]:
        """Tuple of individual indices covered by this family."""
        return tuple(range(self.start, self.stop))

    def extract(self, vector: Sequence[float]) -> Sequence[float]:
        """Return the sub-vector corresponding to this family."""
        return vector[self.start : self.stop]

    def validate_range(
        self,
        vector: Sequence[float],
        *,
        tolerance: float = 1e-6,
    ) -> List[str]:
        """Check that every element in this family lies within bounds.

        Returns a list of human-readable error strings (empty == OK).
        """
        errors: List[str] = []
        sub = self.extract(vector)
        for offset, val in enumerate(sub):
            idx = self.start + offset
            if np.isnan(val) or np.isinf(val):
                errors.append(
                    f"[{self.name}] index {idx}: non-finite value ({val})"
                )
                continue
            if val < self.value_min - tolerance:
                errors.append(
                    f"[{self.name}] index {idx}: "
                    f"value {val:.6f} < min {self.value_min}"
                )
            if val > self.value_max + tolerance:
                errors.append(
                    f"[{self.name}] index {idx}: "
                    f"value {val:.6f} > max {self.value_max}"
                )
        return errors

    def __repr__(self) -> str:
        return (
            f"FeatureFamily({self.name!r}, [{self.start}:{self.stop}], "
            f"len={self.length})"
        )


# ============================================================================
# VISION FEATURE SCHEMA  --  vision.features.v1
# ============================================================================
#
# Layout (57 elements total):
#   [0 : 24]  HSV histograms  (H=12 + S=6 + V=6, each normalised)
#   [24: 33]  Edges + orientation
#   [33: 51]  Shape proxy via connected components (top K=6, 3 per comp)
#   [51: 55]  Motion features
#   [55: 57]  Symmetry features
#
# Metadata (NOT in the vector): mean_v (lighting proxy), frame_timestamp
# ============================================================================

FEATURE_VERSION = "vision.features.v1"
FEATURE_DIM = 57

# --- HSV histograms (24) ---
H_BINS = 12
S_BINS = 6
V_BINS = 6
HSV_TOTAL = H_BINS + S_BINS + V_BINS  # 24

HSV_H_SLICE = slice(0, H_BINS)                        # [0:12]
HSV_S_SLICE = slice(H_BINS, H_BINS + S_BINS)          # [12:18]
HSV_V_SLICE = slice(H_BINS + S_BINS, HSV_TOTAL)       # [18:24]

# --- Edges + orientation (9) ---
EDGE_OFFSET = HSV_TOTAL                                # 24
EDGE_DENSITY_IDX = EDGE_OFFSET                         # 24
ORIENT_HIST_SLICE = slice(EDGE_OFFSET + 1, EDGE_OFFSET + 9)  # [25:33]
EDGE_TOTAL = 9

# --- Shape proxy via connected components (18) ---
SHAPE_OFFSET = EDGE_OFFSET + EDGE_TOTAL                # 33
SHAPE_K = 6
SHAPE_FEATURES_PER_COMP = 3  # area_ratio, bbox_aspect, compactness
SHAPE_TOTAL = SHAPE_K * SHAPE_FEATURES_PER_COMP        # 18
SHAPE_SLICE = slice(SHAPE_OFFSET, SHAPE_OFFSET + SHAPE_TOTAL)  # [33:51]

# --- Motion (4) ---
MOTION_OFFSET = SHAPE_OFFSET + SHAPE_TOTAL             # 51
MOTION_ENERGY_IDX = MOTION_OFFSET                      # 51
MOTION_DENSITY_IDX = MOTION_OFFSET + 1                 # 52
MOTION_BBOX_AREA_IDX = MOTION_OFFSET + 2               # 53
MOTION_BBOX_ASPECT_IDX = MOTION_OFFSET + 3             # 54
MOTION_TOTAL = 4

# --- Symmetry (2) ---
SYMMETRY_OFFSET = MOTION_OFFSET + MOTION_TOTAL         # 55
HORIZ_SYM_IDX = SYMMETRY_OFFSET                        # 55
VERT_SYM_IDX = SYMMETRY_OFFSET + 1                     # 56
SYMMETRY_TOTAL = 2

assert SYMMETRY_OFFSET + SYMMETRY_TOTAL == FEATURE_DIM, (
    f"Feature dim mismatch: expected {FEATURE_DIM}, "
    f"got {SYMMETRY_OFFSET + SYMMETRY_TOTAL}"
)

# ============================================================================
# VISION FEATURE FAMILIES (FeatureFamily descriptors)
# ============================================================================

VISION_HSV_HISTOGRAMS = FeatureFamily(
    name="hsv_histograms",
    start=0,
    stop=HSV_TOTAL,
    description=(
        "Normalised HSV histograms: H bins=12 [0:12], "
        "S bins=6 [12:18], V bins=6 [18:24]."
    ),
    value_min=0.0,
    value_max=1.0,
)

VISION_EDGES_ORIENTATION = FeatureFamily(
    name="edges_orientation",
    start=EDGE_OFFSET,
    stop=EDGE_OFFSET + EDGE_TOTAL,
    description=(
        "Edge and orientation features: edge_density (1), "
        "orientation histogram bins=8 (8).  Sobel 3x3 kernels.  "
        "Grayscale, Sobel X/Y, magnitude + orientation derived."
    ),
    value_min=0.0,
    value_max=1.0,
)

VISION_SHAPE_PROXY = FeatureFamily(
    name="shape_proxy",
    start=SHAPE_OFFSET,
    stop=SHAPE_OFFSET + SHAPE_TOTAL,
    description=(
        "Shape proxy via connected-component analysis on a thresholded "
        "edge mask (64x64).  BFS labelling, top K=6 components by area. "
        "Per component (3 values): area_ratio, bbox_aspect, "
        "compactness = area / (perimeter**2 + eps).  "
        "Padded to 6 components => 18 values."
    ),
    value_min=0.0,
    value_max=1.0,
)

VISION_MOTION = FeatureFamily(
    name="motion",
    start=MOTION_OFFSET,
    stop=MOTION_OFFSET + MOTION_TOTAL,
    description=(
        "Frame-to-frame motion: diff = abs(curr_gray - prev_gray). "
        "motion_energy = mean(diff), motion_density = frac(diff > 0.08), "
        "motion_bbox_area_ratio, motion_bbox_aspect."
    ),
    value_min=0.0,
    value_max=1.0,
)

VISION_SYMMETRY = FeatureFamily(
    name="symmetry",
    start=SYMMETRY_OFFSET,
    stop=SYMMETRY_OFFSET + SYMMETRY_TOTAL,
    description=(
        "Symmetry error features: horizontal symmetry error (1), "
        "vertical symmetry error (1).  Lower => more symmetric."
    ),
    value_min=0.0,
    value_max=1.0,
)

# Ordered tuple for iteration
VISION_FAMILIES: Tuple[FeatureFamily, ...] = (
    VISION_HSV_HISTOGRAMS,
    VISION_EDGES_ORIENTATION,
    VISION_SHAPE_PROXY,
    VISION_MOTION,
    VISION_SYMMETRY,
)

# Quick lookup by name
VISION_FAMILY_MAP: Dict[str, FeatureFamily] = {
    f.name: f for f in VISION_FAMILIES
}

# Additional vision schema parameters
VISION_HSV_H_BINS: int = H_BINS
VISION_HSV_S_BINS: int = S_BINS
VISION_HSV_V_BINS: int = V_BINS
VISION_HSV_H_RANGE: slice = HSV_H_SLICE
VISION_HSV_S_RANGE: slice = HSV_S_SLICE
VISION_HSV_V_RANGE: slice = HSV_V_SLICE

VISION_SHAPE_GRID_SIZE: int = 64
VISION_SHAPE_TOP_K: int = SHAPE_K
VISION_SHAPE_FEATURES_PER_COMPONENT: int = SHAPE_FEATURES_PER_COMP

VISION_SOBEL_KSIZE: int = 3
VISION_ORIENTATION_HIST_BINS: int = 8

VISION_MOTION_THRESHOLD: float = 0.08


@dataclass(frozen=True)
class VisionFeatureMetadata:
    """Out-of-vector metadata accompanying a ``vision.features.v1`` vector.

    These values are useful for normalisation or context but are not part of
    the fixed-length feature vector itself.

    Attributes
    ----------
    mean_v : float
        Mean V channel value (lighting proxy), range [0, 1].
    frame_timestamp : float
        POSIX timestamp (seconds) at which the frame was captured.
        ``0.0`` if unavailable.
    """

    mean_v: float = 0.0
    frame_timestamp: float = 0.0


@dataclass(frozen=True)
class VisionFeatureSchema:
    """Canonical description of the ``vision.features.v1`` schema.

    This object is intended to be used as a singleton reference.  It
    aggregates every parameter needed to produce or consume a vision
    feature vector.
    """

    schema_name: str = "vision.features.v1"
    vector_length: int = VISION_FEATURE_LENGTH
    families: Tuple[FeatureFamily, ...] = VISION_FAMILIES
    hsv_h_bins: int = VISION_HSV_H_BINS
    hsv_s_bins: int = VISION_HSV_S_BINS
    hsv_v_bins: int = VISION_HSV_V_BINS
    sobel_ksize: int = VISION_SOBEL_KSIZE
    orientation_hist_bins: int = VISION_ORIENTATION_HIST_BINS
    shape_grid_size: int = VISION_SHAPE_GRID_SIZE
    shape_top_k: int = VISION_SHAPE_TOP_K
    shape_features_per_component: int = VISION_SHAPE_FEATURES_PER_COMPONENT
    motion_threshold: float = VISION_MOTION_THRESHOLD

    def family(self, name: str) -> FeatureFamily:
        """Look up a feature family by name.

        Raises ``KeyError`` if *name* is not a recognised family.
        """
        return VISION_FAMILY_MAP[name]

    def describe(self) -> str:
        """Return a multi-line human-readable layout description."""
        lines = [
            f"Schema: {self.schema_name}",
            f"Vector length: {self.vector_length}",
            "",
        ]
        for fam in self.families:
            lines.append(
                f"  [{fam.start:>2}:{fam.stop:>2}]  "
                f"{fam.name:<22s}  ({fam.length} values)  "
                f"range [{fam.value_min}, {fam.value_max}]"
            )
        return "\n".join(lines)


# Module-level singleton
VISION_SCHEMA = VisionFeatureSchema()


# ============================================================================
# AUDIO FEATURE SCHEMA  --  audio.features.v1
# ============================================================================
#
# Layout (20 elements total):
#   [0]       RMS energy
#   [1]       Zero-crossing rate (ZCR)
#   [2]       Spectral centroid
#   [3]       Spectral bandwidth
#   [4]       Spectral rolloff (85%)
#   [5]       Spectral flux mean
#   [6]       Harmonicity proxy (autocorrelation peak ratio)
#   [7]       Onset density proxy
#   [8 : 20]  Chroma-lite 12-bin distribution
#
# Per 1.0 s buffer, window N=1024, hop H=512, Hann window, FFT via
# np.fft.rfft.
# ============================================================================

AUDIO_FEATURE_VERSION = "audio.features.v1"

AUDIO_RMS_ENERGY = FeatureFamily(
    name="rms_energy",
    start=0,
    stop=1,
    description="Root-mean-square energy of the buffer.",
    value_min=0.0,
    value_max=1.0,
)

AUDIO_ZCR = FeatureFamily(
    name="zcr",
    start=1,
    stop=2,
    description="Zero-crossing rate, normalised to [0, 1].",
    value_min=0.0,
    value_max=1.0,
)

AUDIO_SPECTRAL_CENTROID = FeatureFamily(
    name="spectral_centroid",
    start=2,
    stop=3,
    description="Spectral centroid, normalised to [0, 1] relative to Nyquist.",
    value_min=0.0,
    value_max=1.0,
)

AUDIO_SPECTRAL_BANDWIDTH = FeatureFamily(
    name="spectral_bandwidth",
    start=3,
    stop=4,
    description="Spectral bandwidth, normalised to [0, 1] relative to Nyquist.",
    value_min=0.0,
    value_max=1.0,
)

AUDIO_SPECTRAL_ROLLOFF = FeatureFamily(
    name="spectral_rolloff",
    start=4,
    stop=5,
    description="Spectral rolloff at 85%, normalised to [0, 1].",
    value_min=0.0,
    value_max=1.0,
)

AUDIO_SPECTRAL_FLUX = FeatureFamily(
    name="spectral_flux",
    start=5,
    stop=6,
    description="Mean spectral flux across frames in the buffer.",
    value_min=0.0,
    value_max=1.0,
)

AUDIO_HARMONICITY = FeatureFamily(
    name="harmonicity",
    start=6,
    stop=7,
    description=(
        "Harmonicity proxy: ratio of the dominant autocorrelation peak "
        "to the zero-lag peak.  Higher => more periodic / harmonic."
    ),
    value_min=0.0,
    value_max=1.0,
)

AUDIO_ONSET_DENSITY = FeatureFamily(
    name="onset_density",
    start=7,
    stop=8,
    description=(
        "Onset density proxy: fraction of frames whose spectral flux "
        "exceeds a threshold, normalised to [0, 1]."
    ),
    value_min=0.0,
    value_max=1.0,
)

AUDIO_CHROMA_LITE = FeatureFamily(
    name="chroma_lite",
    start=8,
    stop=20,
    description=(
        "12-bin chroma distribution (C, C#, D, ..., B).  Each bin is the "
        "normalised energy in that pitch class.  Sums to ~1.0."
    ),
    value_min=0.0,
    value_max=1.0,
)

# Ordered tuple for iteration
AUDIO_FAMILIES: Tuple[FeatureFamily, ...] = (
    AUDIO_RMS_ENERGY,
    AUDIO_ZCR,
    AUDIO_SPECTRAL_CENTROID,
    AUDIO_SPECTRAL_BANDWIDTH,
    AUDIO_SPECTRAL_ROLLOFF,
    AUDIO_SPECTRAL_FLUX,
    AUDIO_HARMONICITY,
    AUDIO_ONSET_DENSITY,
    AUDIO_CHROMA_LITE,
)

# Quick lookup by name
AUDIO_FAMILY_MAP: Dict[str, FeatureFamily] = {
    f.name: f for f in AUDIO_FAMILIES
}

# Audio extraction parameters
AUDIO_BUFFER_DURATION: float = 1.0   # seconds
AUDIO_WINDOW_N: int = 1024
AUDIO_HOP_H: int = 512
AUDIO_ROLLOFF_PERCENTILE: float = 0.85
AUDIO_CHROMA_BINS: int = 12

# Audio index convenience constants
AUDIO_RMS_IDX: int = 0
AUDIO_ZCR_IDX: int = 1
AUDIO_CENTROID_IDX: int = 2
AUDIO_BANDWIDTH_IDX: int = 3
AUDIO_ROLLOFF_IDX: int = 4
AUDIO_FLUX_IDX: int = 5
AUDIO_HARMONICITY_IDX: int = 6
AUDIO_ONSET_IDX: int = 7
AUDIO_CHROMA_OFFSET: int = 8
AUDIO_CHROMA_SLICE: slice = slice(8, 20)


@dataclass(frozen=True)
class AudioFeatureSchema:
    """Canonical description of the ``audio.features.v1`` schema.

    This object is intended to be used as a singleton reference.  It
    aggregates every parameter needed to produce or consume an audio
    feature vector.
    """

    schema_name: str = "audio.features.v1"
    vector_length: int = AUDIO_FEATURE_LENGTH
    families: Tuple[FeatureFamily, ...] = AUDIO_FAMILIES
    buffer_duration: float = AUDIO_BUFFER_DURATION
    window_n: int = AUDIO_WINDOW_N
    hop_h: int = AUDIO_HOP_H
    rolloff_percentile: float = AUDIO_ROLLOFF_PERCENTILE
    chroma_bins: int = AUDIO_CHROMA_BINS

    def family(self, name: str) -> FeatureFamily:
        """Look up a feature family by name.

        Raises ``KeyError`` if *name* is not a recognised family.
        """
        return AUDIO_FAMILY_MAP[name]

    def describe(self) -> str:
        """Return a multi-line human-readable layout description."""
        lines = [
            f"Schema: {self.schema_name}",
            f"Vector length: {self.vector_length}",
            f"Buffer: {self.buffer_duration}s, "
            f"window={self.window_n}, hop={self.hop_h}, Hann, np.fft.rfft",
            "",
        ]
        for fam in self.families:
            lines.append(
                f"  [{fam.start:>2}:{fam.stop:>2}]  "
                f"{fam.name:<22s}  ({fam.length} values)  "
                f"range [{fam.value_min}, {fam.value_max}]"
            )
        return "\n".join(lines)


# Module-level singleton
AUDIO_SCHEMA = AudioFeatureSchema()


# ============================================================================
# BASELINE VISION CLASSES  (multi-label, deterministic thresholds)
# ============================================================================

BASELINE_CLASSES = [
    "low_light",
    "bright",
    "high_motion",
    "low_motion",
    "high_edge",
    "low_edge",
    "warm_palette",
    "cool_palette",
    "high_symmetry",
    "low_symmetry",
]

# Threshold constants (referenced by VisionBaselineClassifier)
THRESH_LOW_LIGHT_V = 0.25
THRESH_BRIGHT_V = 0.75
THRESH_HIGH_MOTION_ENERGY = 0.12
THRESH_HIGH_MOTION_DENSITY = 0.18
THRESH_LOW_MOTION_ENERGY = 0.03
THRESH_LOW_MOTION_DENSITY = 0.05
THRESH_HIGH_EDGE = 0.18
THRESH_LOW_EDGE = 0.05
THRESH_WARM_SUM = 0.45
THRESH_COOL_SUM = 0.45
THRESH_HIGH_SYM = 0.12
THRESH_LOW_SYM = 0.35

# H-bin groupings for palette classification (12-bin hue histogram)
# bin  0 = 0-30  deg  (red/orange)
# bin  1 = 30-60 deg  (orange/yellow)
# bin  2 = 60-90 deg  (yellow/green)
# bin  3 = 90-120 deg (green)
# bin  4 = 120-150 deg (green/cyan)
# bin  5 = 150-180 deg (cyan)
# bin  6 = 180-210 deg (cyan/blue)
# bin  7 = 210-240 deg (blue)
# bin  8 = 240-270 deg (blue/purple)
# bin  9 = 270-300 deg (purple/magenta)
# bin 10 = 300-330 deg (magenta/red)
# bin 11 = 330-360 deg (red)
WARM_H_BINS = [0, 1, 2, 10, 11]   # red, orange, yellow, magenta-red, red
COOL_H_BINS = [4, 5, 6, 7, 8]     # green-cyan, cyan, cyan-blue, blue, blue-purple

# ============================================================================
# VISION CONCEPT CLUSTERING CONSTANTS
# ============================================================================

CONCEPT_SIMILARITY_THRESHOLD = 0.92
CONCEPT_ALPHA_MIN = 0.02
CONCEPT_ALPHA_MAX = 0.15
CONCEPT_ALPHA_BASE = 0.10
CONCEPT_PROMOTION_USAGE = 12
CONCEPT_PROMOTION_SESSIONS = 3
CONCEPT_PROMOTION_CONFIDENCE = 0.55
CANDIDATE_CAP = 60
CONCEPT_FLOOR = 20

# ============================================================================
# VISION HYBRID CONSTANTS
# ============================================================================

HYBRID_CO_OCCURRENCE_WINDOW = 10  # consecutive frames
HYBRID_PROMOTION_COUNT = 8
HYBRID_COHERENCE_THRESHOLD = 0.35
HYBRID_MAX_DEPTH = 2
HYBRID_NPMI_WEIGHT = 0.6
HYBRID_LIFT_WEIGHT = 0.4
HYBRID_ROLLING_WINDOW = 1000

# ============================================================================
# DISTILLATION CONSTANTS
# ============================================================================

DISTILLATION_MATURITY_THRESHOLD = 0.80
SHARD_MAX_BYTES = 25 * 1024 * 1024  # 25 MB

# Distillation tag families
DISTILL_TAG_FAMILIES = [
    "shape_compactness_bin",
    "dominant_hue_band",
    "edge_orientation_signature",
    "motion_signature",
]

# ============================================================================
# DOWNSAMPLED FRAME SIZE
# ============================================================================

FRAME_SMALL_W = 64
FRAME_SMALL_H = 64

# ============================================================================
# PERSISTENCE PATHS (relative to library root)
# ============================================================================

VISION_CONCEPTS_DIR = "library/vision/concepts"
VISION_HYBRIDS_DIR = "library/vision/hybrids"
VISION_TAGS_DIR = "library/vision/tags"


# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def _coerce_to_sequence(vector: Any) -> Sequence[float]:
    """Normalise *vector* to a plain sequence of floats.

    Accepts numpy arrays, lists, tuples, or any iterable of numbers.

    Raises
    ------
    TypeError
        If *vector* cannot be converted.
    """
    if HAS_NUMPY and isinstance(vector, np.ndarray):
        return vector.tolist()
    if isinstance(vector, (list, tuple)):
        return vector
    # Last-resort: try to iterate
    try:
        return list(vector)
    except TypeError as exc:
        raise TypeError(
            f"Cannot coerce {type(vector).__name__} to a feature sequence"
        ) from exc


class ValidationResult:
    """Container for feature-vector validation output.

    Attributes
    ----------
    valid : bool
        ``True`` when no errors were found.
    errors : list[str]
        Human-readable error descriptions.  Empty when valid.
    warnings : list[str]
        Non-fatal observations (e.g. many zeros).
    """

    __slots__ = ("valid", "errors", "warnings")

    def __init__(
        self,
        errors: Optional[List[str]] = None,
        warnings: Optional[List[str]] = None,
    ) -> None:
        self.errors: List[str] = errors or []
        self.warnings: List[str] = warnings or []
        self.valid: bool = len(self.errors) == 0

    def __bool__(self) -> bool:
        """Allow ``if result:`` style checks."""
        return self.valid

    def __repr__(self) -> str:
        return (
            f"ValidationResult(valid={self.valid}, "
            f"errors={len(self.errors)}, warnings={len(self.warnings)})"
        )

    def summary(self) -> str:
        """Return a concise multi-line summary string."""
        parts = [f"Valid: {self.valid}"]
        for err in self.errors:
            parts.append(f"  ERROR: {err}")
        for wrn in self.warnings:
            parts.append(f"  WARNING: {wrn}")
        return "\n".join(parts)


def validate_vision_features(
    vector: Any,
    *,
    strict: bool = True,
    tolerance: float = 1e-6,
) -> ValidationResult:
    """Validate a ``vision.features.v1`` vector.

    Parameters
    ----------
    vector:
        The feature vector to validate.  May be a numpy array, list, or
        tuple of numeric values.
    strict:
        If ``True`` (default), out-of-range values are treated as errors.
        If ``False``, they are reported as warnings instead.
    tolerance:
        Additive tolerance applied when comparing against value bounds.

    Returns
    -------
    ValidationResult
        Object whose ``.valid`` flag indicates pass/fail and whose
        ``.errors`` / ``.warnings`` lists give detail.
    """
    errors: List[str] = []
    warnings: List[str] = []

    try:
        seq = _coerce_to_sequence(vector)
    except TypeError as exc:
        return ValidationResult(errors=[str(exc)])

    # -- Length check ---------------------------------------------------------
    if len(seq) != VISION_FEATURE_LENGTH:
        errors.append(
            f"Expected vector length {VISION_FEATURE_LENGTH}, "
            f"got {len(seq)}"
        )
        return ValidationResult(errors=errors, warnings=warnings)

    # -- Per-family range checks ---------------------------------------------
    for fam in VISION_FAMILIES:
        range_issues = fam.validate_range(seq, tolerance=tolerance)
        if strict:
            errors.extend(range_issues)
        else:
            warnings.extend(range_issues)

    # -- Heuristic warnings --------------------------------------------------
    zero_count = sum(1 for v in seq if abs(v) < tolerance)
    if zero_count == VISION_FEATURE_LENGTH:
        warnings.append("All elements are zero -- possible null extraction")
    elif zero_count > VISION_FEATURE_LENGTH * 0.8:
        warnings.append(
            f"{zero_count}/{VISION_FEATURE_LENGTH} elements are zero "
            f"({100 * zero_count / VISION_FEATURE_LENGTH:.0f}%) "
            "-- possibly degenerate"
        )

    return ValidationResult(errors=errors, warnings=warnings)


def validate_audio_features(
    vector: Any,
    *,
    strict: bool = True,
    tolerance: float = 1e-6,
) -> ValidationResult:
    """Validate an ``audio.features.v1`` vector.

    Parameters
    ----------
    vector:
        The feature vector to validate.  May be a numpy array, list, or
        tuple of numeric values.
    strict:
        If ``True`` (default), out-of-range values are treated as errors.
        If ``False``, they are reported as warnings instead.
    tolerance:
        Additive tolerance applied when comparing against value bounds.

    Returns
    -------
    ValidationResult
        Object whose ``.valid`` flag indicates pass/fail and whose
        ``.errors`` / ``.warnings`` lists give detail.
    """
    errors: List[str] = []
    warnings: List[str] = []

    try:
        seq = _coerce_to_sequence(vector)
    except TypeError as exc:
        return ValidationResult(errors=[str(exc)])

    # -- Length check ---------------------------------------------------------
    if len(seq) != AUDIO_FEATURE_LENGTH:
        errors.append(
            f"Expected vector length {AUDIO_FEATURE_LENGTH}, "
            f"got {len(seq)}"
        )
        return ValidationResult(errors=errors, warnings=warnings)

    # -- Per-family range checks ---------------------------------------------
    for fam in AUDIO_FAMILIES:
        range_issues = fam.validate_range(seq, tolerance=tolerance)
        if strict:
            errors.extend(range_issues)
        else:
            warnings.extend(range_issues)

    # -- Heuristic warnings --------------------------------------------------
    zero_count = sum(1 for v in seq if abs(v) < tolerance)
    if zero_count == AUDIO_FEATURE_LENGTH:
        warnings.append(
            "All elements are zero -- possible silence or null extraction"
        )
    elif zero_count > AUDIO_FEATURE_LENGTH * 0.8:
        warnings.append(
            f"{zero_count}/{AUDIO_FEATURE_LENGTH} elements are zero "
            f"({100 * zero_count / AUDIO_FEATURE_LENGTH:.0f}%) "
            "-- possibly degenerate"
        )

    return ValidationResult(errors=errors, warnings=warnings)


# ============================================================================
# CONVENIENCE HELPERS
# ============================================================================

def empty_vision_vector() -> List[float]:
    """Return a zero-initialised vision feature vector (length 57)."""
    return [0.0] * VISION_FEATURE_LENGTH


def empty_audio_vector() -> List[float]:
    """Return a zero-initialised audio feature vector (length 20)."""
    return [0.0] * AUDIO_FEATURE_LENGTH


def schema_for(name: str) -> Union[VisionFeatureSchema, AudioFeatureSchema]:
    """Look up a schema singleton by its canonical name.

    Parameters
    ----------
    name:
        One of ``"vision.features.v1"`` or ``"audio.features.v1"``.

    Raises
    ------
    KeyError
        If *name* does not match a known schema.
    """
    _registry: Dict[str, Union[VisionFeatureSchema, AudioFeatureSchema]] = {
        VISION_SCHEMA.schema_name: VISION_SCHEMA,
        AUDIO_SCHEMA.schema_name: AUDIO_SCHEMA,
    }
    try:
        return _registry[name]
    except KeyError:
        raise KeyError(
            f"Unknown feature schema {name!r}.  "
            f"Known schemas: {list(_registry.keys())}"
        ) from None


# ============================================================================
# SELF-TEST (run with ``python -m engine.perception.feature_schemas``)
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print(VISION_SCHEMA.describe())
    print()
    print(AUDIO_SCHEMA.describe())
    print("=" * 60)

    # Quick smoke tests
    v = empty_vision_vector()
    assert len(v) == VISION_FEATURE_LENGTH
    res = validate_vision_features(v)
    assert res.valid, res.summary()
    print(f"Vision zero-vector validation: {res}")

    a = empty_audio_vector()
    assert len(a) == AUDIO_FEATURE_LENGTH
    res = validate_audio_features(a)
    assert res.valid, res.summary()
    print(f"Audio  zero-vector validation: {res}")

    # Bad length
    res = validate_vision_features([0.0] * 10)
    assert not res.valid
    print(f"Vision bad-length validation:  {res}")

    res = validate_audio_features([0.0] * 5)
    assert not res.valid
    print(f"Audio  bad-length validation:  {res}")

    # Out-of-range (strict)
    bad_v = empty_vision_vector()
    bad_v[0] = 2.0  # HSV histogram bin > 1.0
    res = validate_vision_features(bad_v)
    assert not res.valid
    print(f"Vision out-of-range (strict):  {res}")

    # Out-of-range (lenient)
    res = validate_vision_features(bad_v, strict=False)
    assert res.valid  # errors become warnings
    assert len(res.warnings) > 0
    print(f"Vision out-of-range (lenient): {res}")

    bad_a = empty_audio_vector()
    bad_a[0] = -0.5  # RMS energy < 0
    res = validate_audio_features(bad_a)
    assert not res.valid
    print(f"Audio  out-of-range (strict):  {res}")

    # Schema lookup
    assert schema_for("vision.features.v1") is VISION_SCHEMA
    assert schema_for("audio.features.v1") is AUDIO_SCHEMA

    # Family lookups
    assert VISION_SCHEMA.family("hsv_histograms") is VISION_HSV_HISTOGRAMS
    assert AUDIO_SCHEMA.family("chroma_lite") is AUDIO_CHROMA_LITE

    # Family extraction
    sample_v = list(range(57))
    hsv_sub = VISION_HSV_HISTOGRAMS.extract(sample_v)
    assert list(hsv_sub) == list(range(24))

    print("\nAll self-tests passed.")
