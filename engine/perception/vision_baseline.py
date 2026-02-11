#!/usr/bin/env python3
"""
Vision Baseline -- Offline AI Perception Pipeline
====================================================
Authors: Sunni (Sir) Morningstar & Cael Devo

Deterministic, efficient vision representation (no random placeholders).
Learns primitives -> clusters -> hybrids -> object-like structures.
Eventually distills baseline builders into tags as maturity increases.

Feature vector: vision.features.v1, length 57
    [0:12]  H histogram (12 bins)
    [12:18] S histogram (6 bins)
    [18:24] V histogram (6 bins)
    [24]    edge density
    [25:33] orientation histogram (8 bins)
    [33:51] shape proxy (6 components x 3 features)
    [51:55] motion (energy, density, bbox_area_ratio, bbox_aspect)
    [55:57] symmetry (horizontal error, vertical error)
"""

from __future__ import annotations

import gzip
import json
import logging
import math
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

from .feature_schemas import (
    FEATURE_VERSION,
    FEATURE_DIM,
    H_BINS,
    S_BINS,
    V_BINS,
    HSV_TOTAL,
    HSV_H_SLICE,
    HSV_S_SLICE,
    HSV_V_SLICE,
    EDGE_OFFSET,
    EDGE_DENSITY_IDX,
    ORIENT_HIST_SLICE,
    EDGE_TOTAL,
    SHAPE_OFFSET,
    SHAPE_K,
    SHAPE_FEATURES_PER_COMP,
    SHAPE_TOTAL,
    SHAPE_SLICE,
    MOTION_OFFSET,
    MOTION_ENERGY_IDX,
    MOTION_DENSITY_IDX,
    MOTION_BBOX_AREA_IDX,
    MOTION_BBOX_ASPECT_IDX,
    MOTION_TOTAL,
    SYMMETRY_OFFSET,
    HORIZ_SYM_IDX,
    VERT_SYM_IDX,
    SYMMETRY_TOTAL,
    BASELINE_CLASSES,
    THRESH_LOW_LIGHT_V,
    THRESH_BRIGHT_V,
    THRESH_HIGH_MOTION_ENERGY,
    THRESH_HIGH_MOTION_DENSITY,
    THRESH_LOW_MOTION_ENERGY,
    THRESH_LOW_MOTION_DENSITY,
    THRESH_HIGH_EDGE,
    THRESH_LOW_EDGE,
    THRESH_WARM_SUM,
    THRESH_COOL_SUM,
    THRESH_HIGH_SYM,
    THRESH_LOW_SYM,
    WARM_H_BINS,
    COOL_H_BINS,
    CONCEPT_SIMILARITY_THRESHOLD,
    CONCEPT_ALPHA_MIN,
    CONCEPT_ALPHA_MAX,
    CONCEPT_ALPHA_BASE,
    CONCEPT_PROMOTION_USAGE,
    CONCEPT_PROMOTION_SESSIONS,
    CONCEPT_PROMOTION_CONFIDENCE,
    CANDIDATE_CAP,
    CONCEPT_FLOOR,
    HYBRID_CO_OCCURRENCE_WINDOW,
    HYBRID_PROMOTION_COUNT,
    HYBRID_COHERENCE_THRESHOLD,
    HYBRID_MAX_DEPTH,
    HYBRID_NPMI_WEIGHT,
    HYBRID_LIFT_WEIGHT,
    HYBRID_ROLLING_WINDOW,
    DISTILLATION_MATURITY_THRESHOLD,
    SHARD_MAX_BYTES,
    DISTILL_TAG_FAMILIES,
    FRAME_SMALL_W,
    FRAME_SMALL_H,
    VISION_CONCEPTS_DIR,
    VISION_HYBRIDS_DIR,
    VISION_TAGS_DIR,
)

logger = logging.getLogger(__name__)

# ============================================================================
# SMALL HELPERS
# ============================================================================

_EPS = 1e-9


def _clamp(lo: float, hi: float, v: float) -> float:
    return max(lo, min(hi, v))


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, v))


def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity on L2-normalised vectors (re-normalises internally)."""
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < _EPS or nb < _EPS:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def _l2_normalise(v: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(v)
    if n < _EPS:
        return v
    return v / n


# ============================================================================
# IMAGE UTILITIES  (pure NumPy -- NO OpenCV)
# ============================================================================

def downsample(frame: np.ndarray, target_h: int, target_w: int) -> np.ndarray:
    """Nearest-neighbour downsample *frame* (H, W, C) or (H, W) to (target_h, target_w[, C])."""
    src_h, src_w = frame.shape[0], frame.shape[1]
    row_idx = (np.arange(target_h) * src_h // target_h).astype(np.intp)
    col_idx = (np.arange(target_w) * src_w // target_w).astype(np.intp)
    return frame[np.ix_(row_idx, col_idx)]


def rgb_to_hsv(rgb: np.ndarray) -> np.ndarray:
    """Convert RGB uint8 array (H,W,3) -> HSV float32 array (H,W,3).

    H in [0,360), S in [0,1], V in [0,1].  Manual conversion -- no OpenCV.
    """
    img = rgb.astype(np.float32) / 255.0
    r, g, b = img[..., 0], img[..., 1], img[..., 2]

    cmax = np.maximum(np.maximum(r, g), b)
    cmin = np.minimum(np.minimum(r, g), b)
    delta = cmax - cmin

    # Value
    v = cmax

    # Saturation
    s = np.where(cmax > _EPS, delta / (cmax + _EPS), 0.0)

    # Hue
    h = np.zeros_like(v)
    mask_r = (cmax == r) & (delta > _EPS)
    mask_g = (cmax == g) & (delta > _EPS) & ~mask_r
    mask_b = (delta > _EPS) & ~mask_r & ~mask_g

    h[mask_r] = 60.0 * (((g[mask_r] - b[mask_r]) / (delta[mask_r] + _EPS)) % 6.0)
    h[mask_g] = 60.0 * (((b[mask_g] - r[mask_g]) / (delta[mask_g] + _EPS)) + 2.0)
    h[mask_b] = 60.0 * (((r[mask_b] - g[mask_b]) / (delta[mask_b] + _EPS)) + 4.0)
    h[h < 0] += 360.0

    return np.stack([h, s, v], axis=-1).astype(np.float32)


def rgb_to_gray(rgb: np.ndarray) -> np.ndarray:
    """Luminance conversion (H,W,3 uint8) -> (H,W) float32 in [0,1]."""
    f = rgb.astype(np.float32) / 255.0
    return 0.2989 * f[..., 0] + 0.5870 * f[..., 1] + 0.1140 * f[..., 2]


# ============================================================================
# FEATURE EXTRACTION  (vision.features.v1, length 57)
# ============================================================================

# Pre-built Sobel kernels (3x3)
_SOBEL_X = np.array([[-1, 0, 1],
                      [-2, 0, 2],
                      [-1, 0, 1]], dtype=np.float32)

_SOBEL_Y = np.array([[-1, -2, -1],
                      [ 0,  0,  0],
                      [ 1,  2,  1]], dtype=np.float32)


def _convolve2d(image: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """Simple valid-mode 2-D convolution for small kernels (pure NumPy)."""
    kh, kw = kernel.shape
    ih, iw = image.shape
    oh, ow = ih - kh + 1, iw - kw + 1
    # Use stride tricks for a view-based approach
    strides = image.strides
    shape = (oh, ow, kh, kw)
    strides_out = (strides[0], strides[1], strides[0], strides[1])
    patches = np.lib.stride_tricks.as_strided(image, shape=shape, strides=strides_out)
    return np.einsum("ijkl,kl->ij", patches, kernel)


def _connected_components_bfs(mask: np.ndarray) -> List[List[Tuple[int, int]]]:
    """BFS-based connected component labeling on a boolean 2-D mask.

    Returns a list of components, each component is a list of (row, col) coords.
    """
    h, w = mask.shape
    visited = np.zeros((h, w), dtype=bool)
    components: List[List[Tuple[int, int]]] = []

    for sr in range(h):
        for sc in range(w):
            if mask[sr, sc] and not visited[sr, sc]:
                # BFS
                comp: List[Tuple[int, int]] = []
                queue = deque()
                queue.append((sr, sc))
                visited[sr, sc] = True
                while queue:
                    r, c = queue.popleft()
                    comp.append((r, c))
                    for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                        nr, nc = r + dr, c + dc
                        if 0 <= nr < h and 0 <= nc < w and mask[nr, nc] and not visited[nr, nc]:
                            visited[nr, nc] = True
                            queue.append((nr, nc))
                components.append(comp)
    return components


def _component_features(comp: List[Tuple[int, int]], total_pixels: int) -> Tuple[float, float, float]:
    """Per-component: area_ratio, bbox_aspect, compactness (area / (perimeter^2 + eps))."""
    area = len(comp)
    area_ratio = area / (total_pixels + _EPS)

    rows = [p[0] for p in comp]
    cols = [p[1] for p in comp]
    rmin, rmax = min(rows), max(rows)
    cmin, cmax = min(cols), max(cols)
    bbox_h = rmax - rmin + 1
    bbox_w = cmax - cmin + 1
    bbox_aspect = bbox_w / (bbox_h + _EPS)

    # Approximate perimeter: count border pixels (those with <4 neighbours in comp)
    comp_set = set(comp)
    perimeter = 0
    for (r, c) in comp:
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            if (r + dr, c + dc) not in comp_set:
                perimeter += 1
                break  # count pixel once
    compactness = area / (perimeter * perimeter + _EPS)
    return area_ratio, bbox_aspect, compactness


def extract_features(
    frame_small: np.ndarray,
    prev_frame_small: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Extract the canonical 57-d feature vector (vision.features.v1).

    Parameters
    ----------
    frame_small : np.ndarray
        Downsampled RGB uint8 frame of shape (64, 64, 3).
    prev_frame_small : np.ndarray or None
        Previous downsampled RGB uint8 frame (same shape).  If *None*,
        motion features are zeroed.

    Returns
    -------
    np.ndarray of shape (57,) dtype float64
    """
    vec = np.zeros(FEATURE_DIM, dtype=np.float64)

    h_frame, w_frame = frame_small.shape[:2]
    total_pixels = h_frame * w_frame

    # ------------------------------------------------------------------
    # 1. HSV histograms (24)
    # ------------------------------------------------------------------
    hsv = rgb_to_hsv(frame_small)  # (H,W,3) float32
    h_ch = hsv[..., 0].ravel()  # [0,360)
    s_ch = hsv[..., 1].ravel()  # [0,1]
    v_ch = hsv[..., 2].ravel()  # [0,1]

    h_hist, _ = np.histogram(h_ch, bins=H_BINS, range=(0.0, 360.0))
    s_hist, _ = np.histogram(s_ch, bins=S_BINS, range=(0.0, 1.0))
    v_hist, _ = np.histogram(v_ch, bins=V_BINS, range=(0.0, 1.0))

    h_hist = h_hist.astype(np.float64)
    s_hist = s_hist.astype(np.float64)
    v_hist = v_hist.astype(np.float64)

    h_sum = h_hist.sum() + _EPS
    s_sum = s_hist.sum() + _EPS
    v_sum = v_hist.sum() + _EPS

    vec[HSV_H_SLICE] = h_hist / h_sum
    vec[HSV_S_SLICE] = s_hist / s_sum
    vec[HSV_V_SLICE] = v_hist / v_sum

    # ------------------------------------------------------------------
    # 2. Edges + orientation (9)
    # ------------------------------------------------------------------
    gray = rgb_to_gray(frame_small)  # (64,64) float32 [0,1]
    gx = _convolve2d(gray, _SOBEL_X)  # (62,62)
    gy = _convolve2d(gray, _SOBEL_Y)
    mag = np.sqrt(gx * gx + gy * gy)
    orient = np.arctan2(gy, gx)  # radians in [-pi, pi]

    # Edge density
    edge_thresh = 0.15  # on normalised magnitude
    mag_max = mag.max() + _EPS
    mag_norm = mag / mag_max
    edge_mask_full = mag_norm > edge_thresh
    edge_density = float(edge_mask_full.sum()) / (edge_mask_full.size + _EPS)
    vec[EDGE_DENSITY_IDX] = edge_density

    # Orientation histogram (8 bins over [-pi, pi])
    orient_flat = orient.ravel()
    mag_flat = mag_norm.ravel()
    orient_hist = np.zeros(8, dtype=np.float64)
    bin_edges_orient = np.linspace(-np.pi, np.pi, 9)
    bin_idx = np.digitize(orient_flat, bin_edges_orient) - 1
    bin_idx = np.clip(bin_idx, 0, 7)
    for b in range(8):
        orient_hist[b] = mag_flat[bin_idx == b].sum()
    orient_sum = orient_hist.sum() + _EPS
    orient_hist /= orient_sum
    vec[ORIENT_HIST_SLICE] = orient_hist

    # ------------------------------------------------------------------
    # 3. Shape proxy via connected components (18)
    # ------------------------------------------------------------------
    # Build edge mask at frame_small resolution for CC labeling
    # Pad mag_norm back to 64x64 with zeros
    edge_pad = np.zeros((h_frame, w_frame), dtype=np.float32)
    roff, coff = 1, 1  # convolution shrinks by 1 on each side
    edge_pad[roff: roff + mag_norm.shape[0], coff: coff + mag_norm.shape[1]] = mag_norm
    cc_mask = edge_pad > edge_thresh

    components = _connected_components_bfs(cc_mask)
    # Sort by area descending, take top K
    components.sort(key=len, reverse=True)
    top_components = components[:SHAPE_K]

    for ci, comp in enumerate(top_components):
        ar, ba, cm = _component_features(comp, total_pixels)
        base = SHAPE_OFFSET + ci * SHAPE_FEATURES_PER_COMP
        vec[base] = ar
        vec[base + 1] = ba
        vec[base + 2] = cm
    # Remaining slots (if fewer than K components) stay zero (already initialised).

    # ------------------------------------------------------------------
    # 4. Motion (4)
    # ------------------------------------------------------------------
    if prev_frame_small is not None:
        prev_gray = rgb_to_gray(prev_frame_small)
        diff = np.abs(gray - prev_gray)
        motion_energy = float(diff.mean())
        motion_density = float((diff > 0.08).sum()) / (total_pixels + _EPS)

        # Motion bounding box
        motion_mask = diff > 0.08
        motion_rows, motion_cols = np.where(motion_mask)
        if len(motion_rows) > 0:
            mr_min, mr_max = motion_rows.min(), motion_rows.max()
            mc_min, mc_max = motion_cols.min(), motion_cols.max()
            mb_h = mr_max - mr_min + 1
            mb_w = mc_max - mc_min + 1
            motion_bbox_area_ratio = (mb_h * mb_w) / (total_pixels + _EPS)
            motion_bbox_aspect = mb_w / (mb_h + _EPS)
        else:
            motion_bbox_area_ratio = 0.0
            motion_bbox_aspect = 0.0

        vec[MOTION_ENERGY_IDX] = motion_energy
        vec[MOTION_DENSITY_IDX] = motion_density
        vec[MOTION_BBOX_AREA_IDX] = motion_bbox_area_ratio
        vec[MOTION_BBOX_ASPECT_IDX] = motion_bbox_aspect

    # ------------------------------------------------------------------
    # 5. Symmetry (2)
    # ------------------------------------------------------------------
    # Horizontal symmetry: compare left half and flipped right half
    left = gray[:, : w_frame // 2]
    right_flipped = gray[:, w_frame // 2:][:, ::-1]
    min_w = min(left.shape[1], right_flipped.shape[1])
    horiz_sym_error = float(np.mean(np.abs(left[:, :min_w] - right_flipped[:, :min_w])))

    # Vertical symmetry: compare top half and flipped bottom half
    top = gray[: h_frame // 2, :]
    bot_flipped = gray[h_frame // 2:, :][::-1, :]
    min_h = min(top.shape[0], bot_flipped.shape[0])
    vert_sym_error = float(np.mean(np.abs(top[:min_h, :] - bot_flipped[:min_h, :])))

    vec[HORIZ_SYM_IDX] = horiz_sym_error
    vec[VERT_SYM_IDX] = vert_sym_error

    return vec


# ============================================================================
# BASELINE VISION CLASSIFIER  (deterministic, multi-label)
# ============================================================================

class VisionBaselineClassifier:
    """Deterministic multi-label classifier over the 57-d feature vector."""

    @staticmethod
    def classify(vec: np.ndarray) -> Set[str]:
        """Return set of active baseline class labels."""
        tags: Set[str] = set()

        # --- light / bright ---
        v_hist = vec[HSV_V_SLICE]
        # Approximate mean V from the histogram (bin-centre weighted mean)
        v_bin_centres = np.linspace(1.0 / (2 * V_BINS), 1.0 - 1.0 / (2 * V_BINS), V_BINS)
        mean_v = float(np.dot(v_hist, v_bin_centres))

        if mean_v < THRESH_LOW_LIGHT_V:
            tags.add("low_light")
        if mean_v > THRESH_BRIGHT_V:
            tags.add("bright")

        # --- motion ---
        motion_energy = vec[MOTION_ENERGY_IDX]
        motion_density = vec[MOTION_DENSITY_IDX]
        if motion_energy > THRESH_HIGH_MOTION_ENERGY or motion_density > THRESH_HIGH_MOTION_DENSITY:
            tags.add("high_motion")
        if motion_energy < THRESH_LOW_MOTION_ENERGY and motion_density < THRESH_LOW_MOTION_DENSITY:
            tags.add("low_motion")

        # --- edge ---
        edge_density = vec[EDGE_DENSITY_IDX]
        if edge_density > THRESH_HIGH_EDGE:
            tags.add("high_edge")
        if edge_density < THRESH_LOW_EDGE:
            tags.add("low_edge")

        # --- palette ---
        h_hist = vec[HSV_H_SLICE]
        warm_sum = float(sum(h_hist[b] for b in WARM_H_BINS))
        cool_sum = float(sum(h_hist[b] for b in COOL_H_BINS))
        if warm_sum > THRESH_WARM_SUM:
            tags.add("warm_palette")
        if cool_sum > THRESH_COOL_SUM:
            tags.add("cool_palette")

        # --- symmetry ---
        horiz_sym = vec[HORIZ_SYM_IDX]
        vert_sym = vec[VERT_SYM_IDX]
        if horiz_sym < THRESH_HIGH_SYM and vert_sym < THRESH_HIGH_SYM:
            tags.add("high_symmetry")
        if horiz_sym > THRESH_LOW_SYM or vert_sym > THRESH_LOW_SYM:
            tags.add("low_symmetry")

        return tags


# ============================================================================
# VISION CONCEPT DATACLASS
# ============================================================================

@dataclass
class VisionConcept:
    """A learned vision concept (centroid in 57-d feature space)."""
    concept_id: str
    centroid: np.ndarray  # shape (57,)
    radius: float = 0.0
    usage_count: int = 0
    session_count: int = 0
    last_seen_ts: float = field(default_factory=time.time)
    confidence: float = 0.0
    class_tags: Set[str] = field(default_factory=set)
    baseline_tags: Dict[str, Any] = field(default_factory=dict)
    maturity_score: float = 0.0
    lineage: Dict[str, Any] = field(default_factory=lambda: {
        "parents": [],
        "root_seed": "vision.base",
    })
    # Internal bookkeeping
    _is_candidate: bool = True
    _sessions_seen: Set[str] = field(default_factory=set)

    # -- serialisation -------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "centroid": self.centroid.tolist(),
            "radius": self.radius,
            "usage_count": self.usage_count,
            "session_count": self.session_count,
            "last_seen_ts": self.last_seen_ts,
            "confidence": self.confidence,
            "class_tags": sorted(self.class_tags),
            "baseline_tags": self.baseline_tags,
            "maturity_score": self.maturity_score,
            "lineage": self.lineage,
            "_is_candidate": self._is_candidate,
            "_sessions_seen": sorted(self._sessions_seen),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "VisionConcept":
        c = cls(
            concept_id=d["concept_id"],
            centroid=np.array(d["centroid"], dtype=np.float64),
            radius=d.get("radius", 0.0),
            usage_count=d.get("usage_count", 0),
            session_count=d.get("session_count", 0),
            last_seen_ts=d.get("last_seen_ts", 0.0),
            confidence=d.get("confidence", 0.0),
            class_tags=set(d.get("class_tags", [])),
            baseline_tags=d.get("baseline_tags", {}),
            maturity_score=d.get("maturity_score", 0.0),
            lineage=d.get("lineage", {"parents": [], "root_seed": "vision.base"}),
        )
        c._is_candidate = d.get("_is_candidate", True)
        c._sessions_seen = set(d.get("_sessions_seen", []))
        return c


# ============================================================================
# VISION HYBRID (OBJECT-LIKE EMERGENCE)
# ============================================================================

@dataclass
class VisionHybrid:
    """A co-occurrence based hybrid formed from concept pairs or (concept, tag)."""
    hybrid_id: str
    component_a: str
    component_b: str
    co_occurrence_count: int = 0
    coherence_score: float = 0.0
    depth: int = 1
    created_ts: float = field(default_factory=time.time)
    last_seen_ts: float = field(default_factory=time.time)
    promoted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hybrid_id": self.hybrid_id,
            "component_a": self.component_a,
            "component_b": self.component_b,
            "co_occurrence_count": self.co_occurrence_count,
            "coherence_score": self.coherence_score,
            "depth": self.depth,
            "created_ts": self.created_ts,
            "last_seen_ts": self.last_seen_ts,
            "promoted": self.promoted,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "VisionHybrid":
        return cls(
            hybrid_id=d["hybrid_id"],
            component_a=d["component_a"],
            component_b=d["component_b"],
            co_occurrence_count=d.get("co_occurrence_count", 0),
            coherence_score=d.get("coherence_score", 0.0),
            depth=d.get("depth", 1),
            created_ts=d.get("created_ts", 0.0),
            last_seen_ts=d.get("last_seen_ts", 0.0),
            promoted=d.get("promoted", False),
        )


# ============================================================================
# COHERENCE METRIC  (nPMI + success lift)
# ============================================================================

class CoherenceTracker:
    """Rolling-window coherence metric using nPMI and success lift.

    Maintains observation counts over the last *window_size* observations
    and computes:
        coherence = npmi_weight * nPMI(A,B) + lift_weight * clamp01(lift - 1)
    """

    def __init__(
        self,
        window_size: int = HYBRID_ROLLING_WINDOW,
        npmi_weight: float = HYBRID_NPMI_WEIGHT,
        lift_weight: float = HYBRID_LIFT_WEIGHT,
    ):
        self.window_size = window_size
        self.npmi_weight = npmi_weight
        self.lift_weight = lift_weight

        # Rolling observation buffer: each entry is a frozenset of active labels
        self._observations: deque = deque(maxlen=window_size)
        # Pre-aggregated counts (refreshed periodically)
        self._single_counts: Dict[str, int] = defaultdict(int)
        self._pair_counts: Dict[Tuple[str, str], int] = defaultdict(int)
        self._total: int = 0
        self._dirty = True  # counts need refresh

        # Optional success tracking
        self._success_observations: deque = deque(maxlen=window_size)

    # -- recording -----------------------------------------------------------

    def record(self, active_labels: Set[str], success: bool = False) -> None:
        """Record one observation (the set of labels active in this frame)."""
        frozen = frozenset(active_labels)
        self._observations.append(frozen)
        self._success_observations.append((frozen, success))
        self._dirty = True

    # -- query ---------------------------------------------------------------

    def _refresh_counts(self) -> None:
        if not self._dirty:
            return
        self._single_counts.clear()
        self._pair_counts.clear()
        self._total = len(self._observations)
        for obs in self._observations:
            for label in obs:
                self._single_counts[label] += 1
            items = sorted(obs)
            for i in range(len(items)):
                for j in range(i + 1, len(items)):
                    self._pair_counts[(items[i], items[j])] += 1
        self._dirty = False

    def npmi(self, a: str, b: str) -> float:
        """Normalised pointwise mutual information in [-1, 1]."""
        self._refresh_counts()
        n = self._total
        if n == 0:
            return 0.0
        pa = self._single_counts.get(a, 0) / n
        pb = self._single_counts.get(b, 0) / n
        key = tuple(sorted([a, b]))
        pab = self._pair_counts.get(key, 0) / n
        if pab < _EPS or pa < _EPS or pb < _EPS:
            return 0.0
        pmi = math.log(pab / (pa * pb + _EPS))
        neg_log_pab = -math.log(pab + _EPS)
        if neg_log_pab < _EPS:
            return 0.0
        return pmi / neg_log_pab

    def success_lift(self, a: str, b: str) -> float:
        """P(success | A,B) / P(success)."""
        if not self._success_observations:
            return 1.0
        total = len(self._success_observations)
        success_total = sum(1 for _, s in self._success_observations if s)
        p_success = success_total / (total + _EPS)

        both_count = 0
        both_success = 0
        for obs, s in self._success_observations:
            if a in obs and b in obs:
                both_count += 1
                if s:
                    both_success += 1
        p_success_given_ab = both_success / (both_count + _EPS) if both_count > 0 else 0.0
        if p_success < _EPS:
            return 1.0
        return p_success_given_ab / p_success

    def coherence(self, a: str, b: str) -> float:
        """Combined coherence = npmi_w * nPMI + lift_w * clamp01(lift - 1)."""
        n = self.npmi(a, b)
        lift = self.success_lift(a, b)
        return self.npmi_weight * _clamp01((n + 1.0) / 2.0) + self.lift_weight * _clamp01(lift - 1.0)


# ============================================================================
# VISION CONCEPT CLUSTERING ENGINE
# ============================================================================

class VisionConceptClusterer:
    """Manages vision concepts (candidates and promoted).

    Distance metric: cosine similarity on L2-normalised 57-d vectors.
    Assignment:
        max_sim >= 0.92  -> update existing concept
        else             -> create candidate
    Promotion: usage >= 12, sessions >= 3, confidence >= 0.55
    Caps: candidate_cap=60 (prunable), concept_floor=20 (never prune below)
    """

    def __init__(self, session_id: str = ""):
        self.concepts: Dict[str, VisionConcept] = {}
        self._next_id: int = 0
        self._session_id: str = session_id or f"s_{int(time.time())}"

    # -- core operations -----------------------------------------------------

    def assign(self, vec: np.ndarray, class_tags: Set[str]) -> Tuple[str, bool]:
        """Assign a feature vector to an existing concept or create a candidate.

        Returns (concept_id, is_new).
        """
        norm_vec = _l2_normalise(vec)

        best_id: Optional[str] = None
        best_sim: float = -1.0

        for cid, concept in self.concepts.items():
            sim = _cosine_similarity(norm_vec, concept.centroid)
            if sim > best_sim:
                best_sim = sim
                best_id = cid

        if best_sim >= CONCEPT_SIMILARITY_THRESHOLD and best_id is not None:
            self._update_concept(best_id, norm_vec, class_tags)
            return best_id, False
        else:
            new_id = self._create_candidate(norm_vec, class_tags)
            return new_id, True

    def _update_concept(self, cid: str, norm_vec: np.ndarray, class_tags: Set[str]) -> None:
        c = self.concepts[cid]
        # Adaptive learning rate: alpha = clamp(0.02, 0.15, 0.10*(1 - confidence))
        alpha = _clamp(CONCEPT_ALPHA_MIN, CONCEPT_ALPHA_MAX,
                       CONCEPT_ALPHA_BASE * (1.0 - c.confidence))
        c.centroid = _l2_normalise((1.0 - alpha) * c.centroid + alpha * norm_vec)
        c.usage_count += 1
        c.last_seen_ts = time.time()
        c.class_tags |= class_tags

        # Track session
        c._sessions_seen.add(self._session_id)
        c.session_count = len(c._sessions_seen)

        # Update radius (running max of distance from centroid)
        dist = 1.0 - _cosine_similarity(norm_vec, c.centroid)
        c.radius = max(c.radius, dist)

        # Confidence increases when similarity stays high
        sim = _cosine_similarity(norm_vec, c.centroid)
        if sim > CONCEPT_SIMILARITY_THRESHOLD:
            c.confidence = min(1.0, c.confidence + 0.005)
        else:
            c.confidence = max(0.0, c.confidence - 0.002)

        # Check promotion
        self._maybe_promote(cid)

    def _create_candidate(self, norm_vec: np.ndarray, class_tags: Set[str]) -> str:
        cid = f"vc_{self._next_id:06d}"
        self._next_id += 1
        concept = VisionConcept(
            concept_id=cid,
            centroid=norm_vec.copy(),
            usage_count=1,
            session_count=1,
            last_seen_ts=time.time(),
            confidence=0.0,
            class_tags=set(class_tags),
            _is_candidate=True,
            _sessions_seen={self._session_id},
        )
        self.concepts[cid] = concept
        self._enforce_candidate_cap()
        return cid

    def _maybe_promote(self, cid: str) -> None:
        c = self.concepts[cid]
        if not c._is_candidate:
            return
        if (c.usage_count >= CONCEPT_PROMOTION_USAGE
                and c.session_count >= CONCEPT_PROMOTION_SESSIONS
                and c.confidence >= CONCEPT_PROMOTION_CONFIDENCE):
            c._is_candidate = False
            logger.info(f"[VISION] Concept promoted: {cid} "
                        f"(usage={c.usage_count}, sessions={c.session_count}, "
                        f"conf={c.confidence:.3f})")

    def _enforce_candidate_cap(self) -> None:
        candidates = [c for c in self.concepts.values() if c._is_candidate]
        if len(candidates) <= CANDIDATE_CAP:
            return
        # Prune least-used candidates (keep those with highest usage * confidence)
        candidates.sort(key=lambda c: c.usage_count * (c.confidence + _EPS))
        prune_count = len(candidates) - CANDIDATE_CAP
        for c in candidates[:prune_count]:
            del self.concepts[c.concept_id]
        logger.debug(f"[VISION] Pruned {prune_count} candidate concepts (cap={CANDIDATE_CAP})")

    # -- session management --------------------------------------------------

    def start_session(self, session_id: str) -> None:
        self._session_id = session_id

    # -- maturity computation ------------------------------------------------

    def compute_maturity(self) -> float:
        """Overall vision maturity in [0,1]."""
        promoted = [c for c in self.concepts.values() if not c._is_candidate]
        if not promoted:
            return 0.0
        avg_conf = sum(c.confidence for c in promoted) / len(promoted)
        count_factor = _clamp01(len(promoted) / 50.0)
        session_factor = _clamp01(max(c.session_count for c in promoted) / 10.0) if promoted else 0.0
        return 0.4 * avg_conf + 0.3 * count_factor + 0.3 * session_factor

    # -- query ---------------------------------------------------------------

    def get_promoted(self) -> List[VisionConcept]:
        return [c for c in self.concepts.values() if not c._is_candidate]

    def get_candidates(self) -> List[VisionConcept]:
        return [c for c in self.concepts.values() if c._is_candidate]

    def nearest(self, vec: np.ndarray, top_k: int = 5) -> List[Tuple[str, float]]:
        """Return top_k nearest concept ids and similarities."""
        norm_vec = _l2_normalise(vec)
        scored = []
        for cid, c in self.concepts.items():
            sim = _cosine_similarity(norm_vec, c.centroid)
            scored.append((cid, sim))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    # -- serialisation -------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "concepts": {cid: c.to_dict() for cid, c in self.concepts.items()},
            "_next_id": self._next_id,
            "_session_id": self._session_id,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "VisionConceptClusterer":
        obj = cls()
        obj._next_id = d.get("_next_id", 0)
        obj._session_id = d.get("_session_id", "")
        for cid, cd in d.get("concepts", {}).items():
            obj.concepts[cid] = VisionConcept.from_dict(cd)
        return obj


# ============================================================================
# VISION HYBRID ENGINE  (object-like emergence)
# ============================================================================

class VisionHybridEngine:
    """Observe concept co-occurrences and promote hybrids.

    Pairs observed:
        (concept_A, concept_B) if co-occur within 10 consecutive frames
        (concept, "high_motion") when concept stable during motion
        (palette_tag, shape_proxy_tag) from tags
    Promotion criteria:
        co_occurrence_count >= 8
        coherence_score >= 0.35
        hybrid_depth <= 2
    """

    def __init__(self):
        self.hybrids: Dict[str, VisionHybrid] = {}
        self.coherence_tracker = CoherenceTracker()

        # Rolling buffer for recent concept IDs per frame
        self._recent_concepts: deque = deque(maxlen=HYBRID_CO_OCCURRENCE_WINDOW)
        # Pair counters
        self._pair_counts: Dict[Tuple[str, str], int] = defaultdict(int)
        # Depth map (concept/hybrid -> depth)
        self._depth_map: Dict[str, int] = {}

    def observe_frame(
        self,
        concept_ids: List[str],
        class_tags: Set[str],
        baseline_tags: Dict[str, Any],
    ) -> List[str]:
        """Observe one frame's assigned concepts and tags.

        Returns list of newly promoted hybrid IDs (if any).
        """
        promoted: List[str] = []

        # Record in coherence tracker
        all_labels = set(concept_ids) | class_tags
        self.coherence_tracker.record(all_labels)

        # Pair concepts with each other within the co-occurrence window
        self._recent_concepts.append(set(concept_ids))
        unique_recent: Set[str] = set()
        for frame_set in self._recent_concepts:
            unique_recent |= frame_set

        # Current frame concepts paired with window concepts
        for curr_cid in concept_ids:
            for other_cid in unique_recent:
                if curr_cid >= other_cid:
                    continue  # canonical ordering, avoid self-pairs
                pair = (curr_cid, other_cid)
                self._pair_counts[pair] += 1
                promoted += self._check_promote(pair)

        # Pair concepts with class tags (e.g. concept + "high_motion")
        for cid in concept_ids:
            for tag in class_tags:
                pair = tuple(sorted([cid, tag]))
                self._pair_counts[pair] += 1
                promoted += self._check_promote(pair)

        # Pair palette tags with shape proxy tags from baseline_tags
        palette_tags = {t for t in class_tags if "palette" in t}
        shape_tags = set()
        for key, val in baseline_tags.items():
            if "shape" in key:
                shape_tags.add(f"{key}:{val}" if not isinstance(val, str) else val)
        for pt in palette_tags:
            for st in shape_tags:
                pair = tuple(sorted([pt, st]))
                self._pair_counts[pair] += 1
                promoted += self._check_promote(pair)

        return promoted

    def _check_promote(self, pair: Tuple[str, str]) -> List[str]:
        """Check if a pair should be promoted to hybrid."""
        hid = f"vh_{pair[0]}_{pair[1]}"
        if hid in self.hybrids and self.hybrids[hid].promoted:
            return []

        count = self._pair_counts[pair]
        if count < HYBRID_PROMOTION_COUNT:
            return []

        # Depth check
        depth_a = self._depth_map.get(pair[0], 0)
        depth_b = self._depth_map.get(pair[1], 0)
        new_depth = max(depth_a, depth_b) + 1
        if new_depth > HYBRID_MAX_DEPTH:
            return []

        # Coherence check
        coh = self.coherence_tracker.coherence(pair[0], pair[1])
        if coh < HYBRID_COHERENCE_THRESHOLD:
            return []

        if hid not in self.hybrids:
            self.hybrids[hid] = VisionHybrid(
                hybrid_id=hid,
                component_a=pair[0],
                component_b=pair[1],
                co_occurrence_count=count,
                coherence_score=coh,
                depth=new_depth,
            )
        hybrid = self.hybrids[hid]
        hybrid.co_occurrence_count = count
        hybrid.coherence_score = coh
        hybrid.last_seen_ts = time.time()

        if not hybrid.promoted:
            hybrid.promoted = True
            self._depth_map[hid] = new_depth
            logger.info(f"[VISION] Hybrid promoted: {hid} "
                        f"(count={count}, coherence={coh:.3f}, depth={new_depth})")
            return [hid]
        return []

    def get_promoted_hybrids(self) -> List[VisionHybrid]:
        return [h for h in self.hybrids.values() if h.promoted]

    # -- serialisation -------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hybrids": {hid: h.to_dict() for hid, h in self.hybrids.items()},
            "_pair_counts": {f"{p[0]}|{p[1]}": c for p, c in self._pair_counts.items()},
            "_depth_map": self._depth_map,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "VisionHybridEngine":
        obj = cls()
        for hid, hd in d.get("hybrids", {}).items():
            obj.hybrids[hid] = VisionHybrid.from_dict(hd)
        for key, count in d.get("_pair_counts", {}).items():
            parts = key.split("|", 1)
            if len(parts) == 2:
                obj._pair_counts[(parts[0], parts[1])] = count
        obj._depth_map = d.get("_depth_map", {})
        return obj


# ============================================================================
# VISION DISTILLATION
# ============================================================================

class VisionDistiller:
    """Distill low-level features into tags when maturity is high enough.

    Trigger: vision_maturity >= 0.80
    Actions:
        - Stop retaining per-frame component lists
        - Prune candidate clusters beyond candidate_cap
        - Convert baseline features into tags on higher-order concepts
        - Keep concept centroids + radii, hybrid graph, tags/priors
        - Apply plateau-aware decay
    """

    def __init__(self):
        self._distilled: bool = False
        self._last_maturity: float = 0.0
        self._plateau_counter: int = 0

    @property
    def is_distilled(self) -> bool:
        return self._distilled

    def maybe_distill(
        self,
        clusterer: VisionConceptClusterer,
        hybrid_engine: VisionHybridEngine,
        maturity: float,
    ) -> bool:
        """Check maturity and distill if threshold met.  Returns True if distilled."""
        # Plateau-aware decay: if maturity is stuck, don't re-distill
        if abs(maturity - self._last_maturity) < 0.01:
            self._plateau_counter += 1
        else:
            self._plateau_counter = 0
        self._last_maturity = maturity

        if maturity < DISTILLATION_MATURITY_THRESHOLD:
            return False
        if self._distilled and self._plateau_counter > 5:
            return False  # already distilled and on plateau

        logger.info(f"[VISION] Distillation triggered (maturity={maturity:.3f})")

        # 1. Convert baseline features into tags on promoted concepts
        for concept in clusterer.get_promoted():
            concept.baseline_tags = self._vectorize_to_tags(concept.centroid)
            concept.maturity_score = maturity

        # 2. Prune excess candidates
        candidates = clusterer.get_candidates()
        if len(candidates) > CANDIDATE_CAP:
            candidates.sort(key=lambda c: c.usage_count * (c.confidence + _EPS))
            to_remove = candidates[: len(candidates) - CANDIDATE_CAP]
            for c in to_remove:
                if c.concept_id in clusterer.concepts:
                    del clusterer.concepts[c.concept_id]
            logger.info(f"[VISION] Distillation pruned {len(to_remove)} candidates")

        # 3. Apply plateau-aware decay on all concepts
        for concept in clusterer.concepts.values():
            decay = 0.98 if self._plateau_counter < 3 else 0.95
            concept.confidence *= decay
            concept.confidence = max(0.0, concept.confidence)

        self._distilled = True
        return True

    @staticmethod
    def _vectorize_to_tags(centroid: np.ndarray) -> Dict[str, str]:
        """Convert a centroid vector into distilled tag strings."""
        tags: Dict[str, str] = {}

        # shape_compactness_bin (average compactness across top components)
        comp_values = []
        for i in range(SHAPE_K):
            base = SHAPE_OFFSET + i * SHAPE_FEATURES_PER_COMP
            compactness = centroid[base + 2]
            if compactness > _EPS:
                comp_values.append(compactness)
        if comp_values:
            avg_compact = sum(comp_values) / len(comp_values)
            if avg_compact > 0.1:
                tags["shape_compactness_bin"] = "high"
            elif avg_compact > 0.02:
                tags["shape_compactness_bin"] = "medium"
            else:
                tags["shape_compactness_bin"] = "low"

        # dominant_hue_band
        h_hist = centroid[HSV_H_SLICE]
        dominant_bin = int(np.argmax(h_hist))
        hue_bands = [
            "red", "orange", "yellow", "yellow-green", "green",
            "cyan-green", "cyan", "blue", "blue-purple", "purple",
            "magenta", "red-magenta",
        ]
        if dominant_bin < len(hue_bands):
            tags["dominant_hue_band"] = hue_bands[dominant_bin]

        # edge_orientation_signature (dominant orientation bin)
        orient_hist = centroid[ORIENT_HIST_SLICE]
        dom_orient = int(np.argmax(orient_hist))
        orient_labels = ["E", "ENE", "N", "NNW", "W", "WSW", "S", "SSE"]
        if dom_orient < len(orient_labels):
            tags["edge_orientation_signature"] = orient_labels[dom_orient]

        # motion_signature
        me = centroid[MOTION_ENERGY_IDX]
        md = centroid[MOTION_DENSITY_IDX]
        if me > 0.12 or md > 0.18:
            tags["motion_signature"] = "high"
        elif me < 0.03 and md < 0.05:
            tags["motion_signature"] = "static"
        else:
            tags["motion_signature"] = "moderate"

        return tags


# ============================================================================
# PERSISTENCE  (25 MB shards -- gzip-compressed JSON)
# ============================================================================

class VisionPersistence:
    """Save / load vision state to 25 MB shard files.

    Paths:
        library/vision/concepts/*.agb
        library/vision/hybrids/*.agb
        library/vision/tags/*.agb
    """

    def __init__(self, library_root: str):
        self.library_root = Path(library_root)
        self._concepts_dir = self.library_root / VISION_CONCEPTS_DIR
        self._hybrids_dir = self.library_root / VISION_HYBRIDS_DIR
        self._tags_dir = self.library_root / VISION_TAGS_DIR
        for d in (self._concepts_dir, self._hybrids_dir, self._tags_dir):
            d.mkdir(parents=True, exist_ok=True)

    # -- save ----------------------------------------------------------------

    def save_concepts(self, clusterer: VisionConceptClusterer) -> None:
        data = clusterer.to_dict()
        self._write_shards(self._concepts_dir, "concepts", data)

    def save_hybrids(self, engine: VisionHybridEngine) -> None:
        data = engine.to_dict()
        self._write_shards(self._hybrids_dir, "hybrids", data)

    def save_tags(self, tag_data: Dict[str, Any]) -> None:
        self._write_shards(self._tags_dir, "tags", tag_data)

    # -- load ----------------------------------------------------------------

    def load_concepts(self) -> Optional[VisionConceptClusterer]:
        data = self._read_shards(self._concepts_dir, "concepts")
        if data is None:
            return None
        return VisionConceptClusterer.from_dict(data)

    def load_hybrids(self) -> Optional[VisionHybridEngine]:
        data = self._read_shards(self._hybrids_dir, "hybrids")
        if data is None:
            return None
        return VisionHybridEngine.from_dict(data)

    def load_tags(self) -> Optional[Dict[str, Any]]:
        return self._read_shards(self._tags_dir, "tags")

    # -- internal shard I/O --------------------------------------------------

    def _write_shards(self, directory: Path, prefix: str, data: Dict[str, Any]) -> None:
        """Serialise *data* into <=25 MB gzip shards (.agb files)."""
        raw = json.dumps(data, separators=(",", ":"), default=str).encode("utf-8")
        shard_idx = 0
        offset = 0
        # Compress in chunks that result in shards under the limit
        while offset < len(raw):
            # Use a generous chunk: gzip usually compresses JSON 5-10x
            chunk_size = SHARD_MAX_BYTES * 6  # raw bytes per shard
            chunk = raw[offset: offset + chunk_size]
            compressed = gzip.compress(chunk, compresslevel=9)

            # If still too big, halve the chunk
            while len(compressed) > SHARD_MAX_BYTES and chunk_size > 4096:
                chunk_size //= 2
                chunk = raw[offset: offset + chunk_size]
                compressed = gzip.compress(chunk, compresslevel=9)

            shard_path = directory / f"{prefix}_{shard_idx:04d}.agb"
            with open(shard_path, "wb") as f:
                f.write(compressed)
            offset += len(chunk)
            shard_idx += 1

        # Write a small manifest
        manifest = {
            "prefix": prefix,
            "shard_count": shard_idx,
            "total_raw_bytes": len(raw),
            "timestamp": time.time(),
        }
        manifest_path = directory / f"{prefix}_manifest.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)

        logger.debug(f"[VISION] Saved {shard_idx} shard(s) to {directory}/{prefix}_*.agb")

    def _read_shards(self, directory: Path, prefix: str) -> Optional[Dict[str, Any]]:
        """Read and reassemble shards."""
        manifest_path = directory / f"{prefix}_manifest.json"
        if not manifest_path.exists():
            return None
        try:
            with open(manifest_path, "r") as f:
                manifest = json.load(f)
        except Exception as e:
            logger.error(f"[VISION] Failed to read shard manifest {manifest_path}: {e}")
            return None

        shard_count = manifest.get("shard_count", 0)
        raw_parts: List[bytes] = []
        for i in range(shard_count):
            shard_path = directory / f"{prefix}_{i:04d}.agb"
            if not shard_path.exists():
                logger.error(f"[VISION] Missing shard: {shard_path}")
                return None
            with open(shard_path, "rb") as f:
                compressed = f.read()
            raw_parts.append(gzip.decompress(compressed))

        combined = b"".join(raw_parts)
        try:
            return json.loads(combined.decode("utf-8"))
        except Exception as e:
            logger.error(f"[VISION] Failed to parse shard data for {prefix}: {e}")
            return None


# ============================================================================
# VISION BASELINE PIPELINE  (top-level orchestrator)
# ============================================================================

class VisionBaselinePipeline:
    """End-to-end vision baseline pipeline.

    Usage::

        pipeline = VisionBaselinePipeline(library_root="/data/ai")
        pipeline.start_session("session_001")

        for frame in frames:
            result = pipeline.process_frame(frame, prev_frame)
            prev_frame = frame

        pipeline.end_session()
    """

    def __init__(self, library_root: str = "."):
        self.library_root = library_root

        # Sub-systems
        self.clusterer = VisionConceptClusterer()
        self.hybrid_engine = VisionHybridEngine()
        self.distiller = VisionDistiller()
        self.persistence = VisionPersistence(library_root)
        self.classifier = VisionBaselineClassifier()

        # Frame state
        self._prev_frame_small: Optional[np.ndarray] = None
        self._frame_count: int = 0
        self._session_id: str = ""

        # Try to load persisted state
        self._load_state()

    # -- session lifecycle ---------------------------------------------------

    def start_session(self, session_id: str) -> None:
        """Begin a new session."""
        self._session_id = session_id
        self.clusterer.start_session(session_id)
        self._prev_frame_small = None
        self._frame_count = 0
        logger.info(f"[VISION] Session started: {session_id}")

    def end_session(self) -> Dict[str, Any]:
        """End current session.  Runs distillation check and persists."""
        maturity = self.clusterer.compute_maturity()
        distilled = self.distiller.maybe_distill(
            self.clusterer, self.hybrid_engine, maturity
        )
        self._save_state()
        summary = {
            "session_id": self._session_id,
            "frames_processed": self._frame_count,
            "concepts_total": len(self.clusterer.concepts),
            "concepts_promoted": len(self.clusterer.get_promoted()),
            "hybrids_promoted": len(self.hybrid_engine.get_promoted_hybrids()),
            "maturity": maturity,
            "distilled": distilled,
        }
        logger.info(f"[VISION] Session ended: {self._session_id} | {summary}")
        return summary

    # -- per-frame processing ------------------------------------------------

    def process_frame(
        self,
        frame: np.ndarray,
        prev_frame: Optional[np.ndarray] = None,
    ) -> Dict[str, Any]:
        """Process a single RGB uint8 frame.

        Parameters
        ----------
        frame : np.ndarray
            RGB uint8 array of any resolution.
        prev_frame : np.ndarray or None
            Previous RGB frame.  If None, uses internal cache.

        Returns
        -------
        dict with keys: feature_vec, class_tags, concept_id, is_new_concept,
                        new_hybrids, maturity
        """
        # 1. Downsample
        frame_small = downsample(frame, FRAME_SMALL_H, FRAME_SMALL_W)
        if prev_frame is not None:
            prev_small = downsample(prev_frame, FRAME_SMALL_H, FRAME_SMALL_W)
        else:
            prev_small = self._prev_frame_small

        # 2. Feature extraction
        vec = extract_features(frame_small, prev_small)

        # 3. Baseline classification
        class_tags = self.classifier.classify(vec)

        # 4. Concept assignment
        concept_id, is_new = self.clusterer.assign(vec, class_tags)

        # 5. Build baseline_tags dict for hybrid engine
        baseline_tags: Dict[str, Any] = {}
        # Add shape info from feature vector
        for i in range(SHAPE_K):
            base = SHAPE_OFFSET + i * SHAPE_FEATURES_PER_COMP
            area = vec[base]
            if area > _EPS:
                compact = vec[base + 2]
                if compact > 0.1:
                    baseline_tags[f"shape_comp_{i}"] = "compact"
                elif compact > 0.02:
                    baseline_tags[f"shape_comp_{i}"] = "moderate"
                else:
                    baseline_tags[f"shape_comp_{i}"] = "sparse"

        # 6. Hybrid observation
        new_hybrids = self.hybrid_engine.observe_frame(
            [concept_id], class_tags, baseline_tags,
        )

        # 7. Update internal state
        self._prev_frame_small = frame_small
        self._frame_count += 1

        return {
            "feature_vec": vec,
            "class_tags": class_tags,
            "concept_id": concept_id,
            "is_new_concept": is_new,
            "new_hybrids": new_hybrids,
            "maturity": self.clusterer.compute_maturity(),
        }

    # -- persistence ---------------------------------------------------------

    def _save_state(self) -> None:
        try:
            self.persistence.save_concepts(self.clusterer)
            self.persistence.save_hybrids(self.hybrid_engine)
            # Collect distilled tags
            tag_data: Dict[str, Any] = {}
            for concept in self.clusterer.get_promoted():
                if concept.baseline_tags:
                    tag_data[concept.concept_id] = {
                        "baseline_tags": concept.baseline_tags,
                        "class_tags": sorted(concept.class_tags),
                        "maturity_score": concept.maturity_score,
                    }
            if tag_data:
                self.persistence.save_tags(tag_data)
            logger.debug("[VISION] State saved.")
        except Exception as e:
            logger.error(f"[VISION] Failed to save state: {e}")

    def _load_state(self) -> None:
        try:
            loaded_clusterer = self.persistence.load_concepts()
            if loaded_clusterer is not None:
                self.clusterer = loaded_clusterer
                logger.info(f"[VISION] Loaded {len(self.clusterer.concepts)} concepts from disk.")

            loaded_hybrids = self.persistence.load_hybrids()
            if loaded_hybrids is not None:
                self.hybrid_engine = loaded_hybrids
                logger.info(f"[VISION] Loaded {len(self.hybrid_engine.hybrids)} hybrids from disk.")

            loaded_tags = self.persistence.load_tags()
            if loaded_tags is not None:
                # Re-apply tags to concepts
                for cid, tdata in loaded_tags.items():
                    if cid in self.clusterer.concepts:
                        c = self.clusterer.concepts[cid]
                        c.baseline_tags = tdata.get("baseline_tags", {})
                        c.class_tags = set(tdata.get("class_tags", []))
                        c.maturity_score = tdata.get("maturity_score", 0.0)
                logger.info(f"[VISION] Loaded tags for {len(loaded_tags)} concepts.")
        except Exception as e:
            logger.error(f"[VISION] Failed to load state: {e}")

    # -- observability -------------------------------------------------------

    def get_stats(self) -> Dict[str, Any]:
        promoted = self.clusterer.get_promoted()
        candidates = self.clusterer.get_candidates()
        return {
            "feature_version": FEATURE_VERSION,
            "feature_dim": FEATURE_DIM,
            "total_concepts": len(self.clusterer.concepts),
            "promoted_concepts": len(promoted),
            "candidate_concepts": len(candidates),
            "promoted_hybrids": len(self.hybrid_engine.get_promoted_hybrids()),
            "total_hybrids": len(self.hybrid_engine.hybrids),
            "maturity": self.clusterer.compute_maturity(),
            "distilled": self.distiller.is_distilled,
            "frames_processed": self._frame_count,
            "session_id": self._session_id,
        }


# ============================================================================
# MODULE EXPORTS
# ============================================================================

__all__ = [
    # Image utilities
    "downsample",
    "rgb_to_hsv",
    "rgb_to_gray",
    # Feature extraction
    "extract_features",
    # Baseline classifier
    "VisionBaselineClassifier",
    # Concept clustering
    "VisionConcept",
    "VisionConceptClusterer",
    # Hybrid emergence
    "VisionHybrid",
    "VisionHybridEngine",
    # Coherence
    "CoherenceTracker",
    # Distillation
    "VisionDistiller",
    # Persistence
    "VisionPersistence",
    # Top-level pipeline
    "VisionBaselinePipeline",
]
