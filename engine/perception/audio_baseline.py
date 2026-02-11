#!/usr/bin/env python3
"""
Audio Baseline - Deterministic Audio Perception Pipeline
=========================================================
Authors: Sunni (Sir) Morningstar & Cael Devo

Deterministic audio representation from PCM buffers.
Learns metrics -> coarse classes -> sound concepts -> structures.
Supports "music specialist" path without external ML.

Feature Schema: audio.features.v1 (Fixed vector length: 20)
Per 1.0s buffer:
  1. RMS energy (1)
  2. ZCR (1)
  3. Spectral centroid (1)
  4. Spectral bandwidth (1)
  5. Spectral rolloff 85% (1)
  6. Spectral flux mean (1)
  7. Harmonicity proxy via autocorrelation peak ratio (1)
  8. Onset density proxy (1)
  9. Chroma-lite 12-bin distribution (12)
Total: 20

Audio Baseline Classes (Multi-label):
  speech_like, music_like, noise_like, alarm_like, silence_like, mechanical_like

Two-Layer Memory:
  SoundClassMemory  - per-class usage over time
  SoundConceptMemory - clusters feature vectors within each class

Music Specialization Path:
  Rhythm templates, reduced promotion thresholds, increased retention.

Audio Hybrids:
  Co-occurring concepts promoted via nPMI + success lift.

Audio Distillation:
  Triggered at audio_maturity >= 0.80. Prunes raw histories, keeps centroids.

Persistence shards:
  library/audio/classes/*.agb
  library/audio/concepts/*.agb
  library/audio/templates/*.agb
  library/audio/hybrids/*.agb
"""

import json
import logging
import math
import os
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

# Numpy with graceful fallback for Android
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

    class _NumpyFallback:
        """Minimal fallback for numpy functions used in audio feature extraction."""
        ndarray = list

        @staticmethod
        def zeros(n):
            if isinstance(n, tuple):
                rows, cols = n
                return [[0.0] * cols for _ in range(rows)]
            return [0.0] * n

        @staticmethod
        def array(lst):
            return list(lst) if not isinstance(lst, list) else lst[:]

        @staticmethod
        def mean(lst, axis=None):
            if not lst:
                return 0.0
            if axis == 0 and lst and isinstance(lst[0], (list, tuple)):
                n = len(lst[0])
                result = [0.0] * n
                for row in lst:
                    for i, v in enumerate(row):
                        result[i] += v
                return [v / len(lst) for v in result]
            if isinstance(lst, (list, tuple)):
                flat = lst
                if flat and isinstance(flat[0], (list, tuple)):
                    flat = [x for row in flat for x in row]
                return sum(flat) / len(flat) if flat else 0.0
            return float(lst)

        @staticmethod
        def sum(lst, axis=None):
            if isinstance(lst, (int, float)):
                return float(lst)
            if isinstance(lst, (list, tuple)):
                if lst and isinstance(lst[0], (list, tuple)):
                    if axis == 0:
                        n = len(lst[0])
                        result = [0.0] * n
                        for row in lst:
                            for i, v in enumerate(row):
                                result[i] += v
                        return result
                    elif axis == 1:
                        return [sum(row) for row in lst]
                    else:
                        return sum(sum(row) for row in lst)
                return sum(lst)
            return float(lst)

        @staticmethod
        def abs(lst):
            if isinstance(lst, (int, float)):
                return abs(lst)
            return [abs(x) for x in lst]

        @staticmethod
        def sqrt(val):
            if isinstance(val, (int, float)):
                return math.sqrt(max(0.0, val))
            return [math.sqrt(max(0.0, x)) for x in val]

        @staticmethod
        def dot(v1, v2):
            return sum(a * b for a, b in zip(v1, v2))

        @staticmethod
        def max(a, b=None):
            if b is None:
                return max(a)
            if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
                return [max(x, y) for x, y in zip(a, b)]
            if isinstance(a, (list, tuple)):
                return [max(x, b) for x in a]
            return max(a, b)

        @staticmethod
        def argmax(lst):
            return max(range(len(lst)), key=lambda i: lst[i])

        @staticmethod
        def log2(val):
            if isinstance(val, (int, float)):
                return math.log2(val) if val > 0 else 0.0
            return [math.log2(x) if x > 0 else 0.0 for x in val]

        @staticmethod
        def exp(val):
            if isinstance(val, (int, float)):
                return math.exp(val)
            return [math.exp(x) for x in val]

        @staticmethod
        def clip(val, low, high):
            if isinstance(val, (int, float)):
                return max(low, min(high, val))
            return [max(low, min(high, x)) for x in val]

        @staticmethod
        def hanning(n):
            return [0.5 * (1.0 - math.cos(2.0 * math.pi * i / (n - 1))) for i in range(n)]

        @staticmethod
        def correlate(a, b, mode="full"):
            """Simplified correlation for 1D signals."""
            na, nb = len(a), len(b)
            if mode == "full":
                out_len = na + nb - 1
                result = [0.0] * out_len
                for i in range(out_len):
                    s = 0.0
                    for j in range(nb):
                        ai = i - j
                        if 0 <= ai < na:
                            s += a[ai] * b[j]
                    result[i] = s
                return result
            return [sum(a_i * b_i for a_i, b_i in zip(a, b))]

        @staticmethod
        def diff(lst):
            return [lst[i + 1] - lst[i] for i in range(len(lst) - 1)]

        class linalg:
            @staticmethod
            def norm(v):
                if isinstance(v, (int, float)):
                    return abs(v)
                return math.sqrt(sum(x * x for x in v))

        class fft:
            @staticmethod
            def rfft(signal):
                """Naive DFT for real signals. Returns complex-like (magnitude) list.
                For production, numpy is strongly preferred."""
                n = len(signal)
                out_len = n // 2 + 1
                result_real = [0.0] * out_len
                result_imag = [0.0] * out_len
                for k in range(out_len):
                    for t in range(n):
                        angle = 2.0 * math.pi * k * t / n
                        result_real[k] += signal[t] * math.cos(angle)
                        result_imag[k] -= signal[t] * math.sin(angle)
                # Return as list of complex-like tuples for magnitude computation
                return [(result_real[k], result_imag[k]) for k in range(out_len)]

        class random:
            @staticmethod
            def randn(n):
                import random as _rng
                return [_rng.gauss(0, 1) for _ in range(n)]

    np = _NumpyFallback()

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

FEATURE_SCHEMA_VERSION = "audio.features.v1"
FEATURE_VECTOR_LENGTH = 20

# FFT parameters for 1.0s buffer
WINDOW_SIZE = 1024  # N
HOP_SIZE = 512      # H
DEFAULT_SAMPLE_RATE = 44100

# Audio baseline class names
AUDIO_CLASSES = [
    "silence_like",
    "noise_like",
    "speech_like",
    "music_like",
    "alarm_like",
    "mechanical_like",
]

# Classification thresholds
SILENCE_RMS_THRESHOLD = 0.02
NOISE_ZCR_THRESHOLD = 0.20
NOISE_HARMONICITY_CEILING = 0.15
SPEECH_RMS_LOW = 0.04
SPEECH_RMS_HIGH = 0.35
SPEECH_ZCR_LOW = 0.05
SPEECH_ZCR_HIGH = 0.18
SPEECH_HARMONICITY_LOW = 0.15
SPEECH_HARMONICITY_HIGH = 0.55
SPEECH_CENTROID_LOW = 300.0
SPEECH_CENTROID_HIGH = 3000.0
MUSIC_HARMONICITY_THRESHOLD = 0.45
MUSIC_CHROMA_ENTROPY_THRESHOLD = 3.2  # bits; low => tonal
MUSIC_ONSET_DENSITY_LOW = 0.10
ALARM_BANDWIDTH_CEILING = 500.0
ALARM_FLUX_SPIKE_RATIO = 2.5

# Concept memory
SIMILARITY_MATCH_THRESHOLD = 0.93
CONCEPT_PROMOTION_USAGE = 14
CONCEPT_PROMOTION_SESSIONS = 3
CONCEPT_PROMOTION_CONFIDENCE = 0.55
DEFAULT_CANDIDATE_CAP = 80
DEFAULT_CONCEPT_FLOOR = 20

# Hybrid promotion
HYBRID_PROMOTION_COUNT = 10
HYBRID_COHERENCE_THRESHOLD = 0.35
HYBRID_MAX_DEPTH = 2

# EMA smoothing for class confidence
EMA_ALPHA = 0.15

# Music specialization
MUSIC_PROMOTION_DISCOUNT = 0.85   # reduce thresholds by 15%
MUSIC_RETENTION_BOOST = 1.25      # increase retention quota by 25%
MUSIC_RHYTHM_MATURITY_GATE = 0.65

# Distillation
DISTILLATION_MATURITY_GATE = 0.80


# ============================================================================
# FEATURE EXTRACTION
# ============================================================================

def _magnitude_spectrum(fft_result):
    """Compute magnitude spectrum from FFT result, handling both numpy and fallback."""
    if HAS_NUMPY:
        return np.abs(fft_result)
    else:
        # Fallback: fft_result is list of (real, imag) tuples
        return [math.sqrt(r * r + im * im) for r, im in fft_result]


def _apply_window(frame, window):
    """Element-wise multiply frame by window."""
    if HAS_NUMPY:
        return frame * window
    return [f * w for f, w in zip(frame, window)]


def _fft_rfft(signal):
    """Compute rfft using numpy or fallback."""
    if HAS_NUMPY:
        return np.fft.rfft(signal)
    return np.fft.rfft(signal)


def extract_features(pcm_frames: list, sr: int = DEFAULT_SAMPLE_RATE) -> list:
    """
    Extract the audio.features.v1 vector (length 20) from a 1.0s PCM mono buffer.

    Parameters
    ----------
    pcm_frames : list or np.ndarray
        Mono PCM samples (float, range -1.0 to 1.0) for a 1.0s window.
    sr : int
        Sample rate (e.g. 44100).

    Returns
    -------
    list[float]
        Feature vector of length 20.
    """
    if HAS_NUMPY:
        samples = np.asarray(pcm_frames, dtype=np.float64)
    else:
        samples = [float(x) for x in pcm_frames]

    n_samples = len(samples)
    if n_samples == 0:
        return [0.0] * FEATURE_VECTOR_LENGTH

    N = WINDOW_SIZE
    H = HOP_SIZE

    # Pre-compute Hann window
    if HAS_NUMPY:
        window = np.hanning(N)
    else:
        window = np.hanning(N)

    # Collect per-frame spectral data
    freq_bin_hz = sr / N  # Hz per FFT bin
    n_bins = N // 2 + 1

    # Frequency array for centroid / bandwidth / rolloff
    if HAS_NUMPY:
        freqs = np.arange(n_bins) * freq_bin_hz
    else:
        freqs = [k * freq_bin_hz for k in range(n_bins)]

    centroids = []
    bandwidths = []
    rolloffs = []
    flux_values = []
    prev_mag = None
    magnitudes_all = []

    start = 0
    while start + N <= n_samples:
        if HAS_NUMPY:
            frame = samples[start:start + N]
        else:
            frame = samples[start:start + N]

        windowed = _apply_window(frame, window)
        fft_result = _fft_rfft(windowed)
        mag = _magnitude_spectrum(fft_result)
        magnitudes_all.append(mag)

        # Spectral magnitude sum for normalization
        if HAS_NUMPY:
            mag_sum = float(np.sum(mag))
        else:
            mag_sum = sum(mag)

        if mag_sum < 1e-12:
            mag_sum = 1e-12

        # --- Spectral Centroid ---
        if HAS_NUMPY:
            centroid = float(np.sum(freqs * mag) / mag_sum)
        else:
            centroid = sum(f * m for f, m in zip(freqs, mag)) / mag_sum
        centroids.append(centroid)

        # --- Spectral Bandwidth ---
        if HAS_NUMPY:
            bw = float(np.sqrt(np.sum(((freqs - centroid) ** 2) * mag) / mag_sum))
        else:
            bw = math.sqrt(sum((f - centroid) ** 2 * m for f, m in zip(freqs, mag)) / mag_sum)
        bandwidths.append(bw)

        # --- Spectral Rolloff 85% ---
        target = 0.85 * mag_sum
        cumulative = 0.0
        rolloff_freq = freqs[-1] if not HAS_NUMPY else float(freqs[-1])
        for k in range(n_bins):
            if HAS_NUMPY:
                cumulative += float(mag[k])
                fk = float(freqs[k])
            else:
                cumulative += mag[k]
                fk = freqs[k]
            if cumulative >= target:
                rolloff_freq = fk
                break
        rolloffs.append(rolloff_freq)

        # --- Spectral Flux ---
        if prev_mag is not None:
            if HAS_NUMPY:
                diff = mag - prev_mag
                flux = float(np.sum(np.maximum(diff, 0)))
            else:
                flux = sum(max(0.0, m - p) for m, p in zip(mag, prev_mag))
            flux_values.append(flux)
        prev_mag = mag

        start += H

    n_frames = len(centroids)
    if n_frames == 0:
        return [0.0] * FEATURE_VECTOR_LENGTH

    # ---- 1. RMS Energy ----
    if HAS_NUMPY:
        rms = float(np.sqrt(np.mean(samples ** 2)))
    else:
        rms = math.sqrt(sum(x * x for x in samples) / n_samples)

    # ---- 2. Zero-Crossing Rate ----
    if HAS_NUMPY:
        signs = np.sign(samples)
        crossings = np.sum(np.abs(np.diff(signs)) > 0)
        zcr = float(crossings) / (n_samples - 1) if n_samples > 1 else 0.0
    else:
        crossings = 0
        for i in range(1, n_samples):
            if (samples[i] >= 0) != (samples[i - 1] >= 0):
                crossings += 1
        zcr = crossings / (n_samples - 1) if n_samples > 1 else 0.0

    # ---- 3. Spectral Centroid (mean across frames) ----
    spectral_centroid = sum(centroids) / n_frames

    # ---- 4. Spectral Bandwidth (mean) ----
    spectral_bandwidth = sum(bandwidths) / n_frames

    # ---- 5. Spectral Rolloff 85% (mean) ----
    spectral_rolloff = sum(rolloffs) / n_frames

    # ---- 6. Spectral Flux Mean ----
    spectral_flux = sum(flux_values) / len(flux_values) if flux_values else 0.0

    # ---- 7. Harmonicity proxy via autocorrelation peak ratio ----
    harmonicity = _compute_harmonicity(samples, sr, n_samples)

    # ---- 8. Onset Density Proxy ----
    onset_density = _compute_onset_density(flux_values, n_frames)

    # ---- 9. Chroma-lite 12-bin distribution ----
    chroma = _compute_chroma(magnitudes_all, sr, N)

    # Assemble feature vector
    feature_vector = [
        rms,                # 0
        zcr,                # 1
        spectral_centroid,  # 2
        spectral_bandwidth, # 3
        spectral_rolloff,   # 4
        spectral_flux,      # 5
        harmonicity,        # 6
        onset_density,      # 7
    ] + chroma              # 8-19

    assert len(feature_vector) == FEATURE_VECTOR_LENGTH, (
        f"Feature vector length mismatch: {len(feature_vector)} != {FEATURE_VECTOR_LENGTH}"
    )

    return feature_vector


def _compute_harmonicity(samples, sr: int, n_samples: int) -> float:
    """
    Harmonicity proxy via normalized autocorrelation peak ratio.
    Peak of autocorrelation (excluding lag-0) divided by lag-0 value.
    Search range corresponds to 50 Hz - 4000 Hz fundamental.
    """
    if n_samples < WINDOW_SIZE:
        return 0.0

    # Use a single centered window for autocorrelation
    center = n_samples // 2
    half_n = WINDOW_SIZE // 2
    start_idx = max(0, center - half_n)
    end_idx = min(n_samples, start_idx + WINDOW_SIZE)

    if HAS_NUMPY:
        segment = np.asarray(samples[start_idx:end_idx], dtype=np.float64)
        autocorr = np.correlate(segment, segment, mode='full')
        autocorr = autocorr[len(autocorr) // 2:]  # Keep positive lags only
    else:
        segment = samples[start_idx:end_idx]
        seg_len = len(segment)
        # Compute only positive-lag autocorrelation
        max_lag = seg_len
        autocorr = [0.0] * max_lag
        for lag in range(max_lag):
            s = 0.0
            for i in range(seg_len - lag):
                s += segment[i] * segment[i + lag]
            autocorr[lag] = s

    if len(autocorr) == 0:
        return 0.0

    if HAS_NUMPY:
        r0 = float(autocorr[0])
    else:
        r0 = autocorr[0]

    if r0 < 1e-12:
        return 0.0

    # Search range: 50 Hz to 4000 Hz
    min_lag = max(1, int(sr / 4000))
    max_lag = min(len(autocorr) - 1, int(sr / 50))

    if min_lag >= max_lag:
        return 0.0

    if HAS_NUMPY:
        search_region = autocorr[min_lag:max_lag + 1]
        peak_val = float(np.max(search_region))
    else:
        search_region = autocorr[min_lag:max_lag + 1]
        peak_val = max(search_region) if search_region else 0.0

    harmonicity = peak_val / r0
    return max(0.0, min(1.0, harmonicity))


def _compute_onset_density(flux_values: list, n_frames: int) -> float:
    """
    Onset density proxy: fraction of frames where flux exceeds
    adaptive threshold (mean + 1 std of flux).
    """
    if not flux_values or n_frames == 0:
        return 0.0

    mean_flux = sum(flux_values) / len(flux_values)
    if len(flux_values) > 1:
        variance = sum((f - mean_flux) ** 2 for f in flux_values) / (len(flux_values) - 1)
        std_flux = math.sqrt(variance)
    else:
        std_flux = 0.0

    threshold = mean_flux + std_flux
    onset_count = sum(1 for f in flux_values if f > threshold)
    return onset_count / n_frames


def _compute_chroma(magnitudes_all: list, sr: int, N: int) -> list:
    """
    Chroma-lite: 12-bin distribution by folding magnitude spectrum
    into pitch classes. Returns normalized 12-element list.
    """
    chroma = [0.0] * 12
    n_bins = N // 2 + 1

    for mag in magnitudes_all:
        for k in range(1, n_bins):  # skip DC
            freq = k * sr / N
            if freq < 20.0:
                continue
            # Map frequency to pitch class
            # MIDI note: 12 * log2(freq / 440) + 69
            midi = 12.0 * math.log2(freq / 440.0) + 69.0
            pitch_class = int(round(midi)) % 12
            if HAS_NUMPY:
                chroma[pitch_class] += float(mag[k])
            else:
                chroma[pitch_class] += mag[k]

    # Normalize to sum to 1
    total = sum(chroma)
    if total > 1e-12:
        chroma = [c / total for c in chroma]

    return chroma


def chroma_entropy(chroma: list) -> float:
    """Shannon entropy of a 12-bin chroma distribution (bits)."""
    entropy = 0.0
    for c in chroma:
        if c > 1e-12:
            entropy -= c * math.log2(c)
    return entropy


# ============================================================================
# CLASSIFICATION RULES
# ============================================================================

def classify_audio(feature_vector: list, sr: int = DEFAULT_SAMPLE_RATE) -> Dict[str, float]:
    """
    Deterministic multi-label classification from feature vector.

    Returns dict mapping class name -> confidence (0.0 - 1.0).
    Multiple classes can be active simultaneously.
    """
    rms = feature_vector[0]
    zcr = feature_vector[1]
    centroid = feature_vector[2]
    bandwidth = feature_vector[3]
    _rolloff = feature_vector[4]
    flux = feature_vector[5]
    harmonicity = feature_vector[6]
    onset_density = feature_vector[7]
    chroma_bins = feature_vector[8:20]

    labels: Dict[str, float] = {}

    # --- silence_like ---
    if rms < SILENCE_RMS_THRESHOLD:
        # Confidence scales inversely with RMS
        labels["silence_like"] = 1.0 - (rms / SILENCE_RMS_THRESHOLD)

    # --- noise_like ---
    if zcr > NOISE_ZCR_THRESHOLD and harmonicity < NOISE_HARMONICITY_CEILING:
        noise_conf = min(1.0, (zcr - NOISE_ZCR_THRESHOLD) / 0.15 +
                         (NOISE_HARMONICITY_CEILING - harmonicity) / NOISE_HARMONICITY_CEILING)
        labels["noise_like"] = max(0.0, min(1.0, noise_conf))

    # --- speech_like ---
    if (SPEECH_RMS_LOW <= rms <= SPEECH_RMS_HIGH and
            SPEECH_ZCR_LOW <= zcr <= SPEECH_ZCR_HIGH and
            SPEECH_HARMONICITY_LOW <= harmonicity <= SPEECH_HARMONICITY_HIGH and
            SPEECH_CENTROID_LOW <= centroid <= SPEECH_CENTROID_HIGH):
        # Confidence is product of how centered each param is in its range
        rms_center = 1.0 - abs(rms - (SPEECH_RMS_LOW + SPEECH_RMS_HIGH) / 2) / ((SPEECH_RMS_HIGH - SPEECH_RMS_LOW) / 2)
        zcr_center = 1.0 - abs(zcr - (SPEECH_ZCR_LOW + SPEECH_ZCR_HIGH) / 2) / ((SPEECH_ZCR_HIGH - SPEECH_ZCR_LOW) / 2)
        harm_center = 1.0 - abs(harmonicity - (SPEECH_HARMONICITY_LOW + SPEECH_HARMONICITY_HIGH) / 2) / (
            (SPEECH_HARMONICITY_HIGH - SPEECH_HARMONICITY_LOW) / 2)
        labels["speech_like"] = max(0.0, min(1.0, (rms_center + zcr_center + harm_center) / 3.0))

    # --- music_like ---
    c_entropy = chroma_entropy(chroma_bins)
    music_conf = 0.0
    if harmonicity > MUSIC_HARMONICITY_THRESHOLD:
        music_conf = max(music_conf, (harmonicity - MUSIC_HARMONICITY_THRESHOLD) / (1.0 - MUSIC_HARMONICITY_THRESHOLD))
    if c_entropy < MUSIC_CHROMA_ENTROPY_THRESHOLD and onset_density >= MUSIC_ONSET_DENSITY_LOW:
        tonal_score = 1.0 - (c_entropy / MUSIC_CHROMA_ENTROPY_THRESHOLD)
        music_conf = max(music_conf, tonal_score * 0.7 + min(1.0, onset_density / 0.3) * 0.3)
    if music_conf > 0.0:
        labels["music_like"] = max(0.0, min(1.0, music_conf))

    # --- alarm_like ---
    # Characteristics: stable centroid, low bandwidth, periodic flux spikes
    if bandwidth < ALARM_BANDWIDTH_CEILING and flux > 0:
        # Check for periodicity in flux by comparing max to mean
        # Since we only have the mean flux here, use onset_density as proxy
        if onset_density > 0.15 and onset_density < 0.50:
            alarm_conf = (1.0 - bandwidth / ALARM_BANDWIDTH_CEILING) * 0.5 + onset_density * 0.5
            labels["alarm_like"] = max(0.0, min(1.0, alarm_conf))

    # --- mechanical_like ---
    # Low harmonicity + periodic onset patterns OR low centroid + stable bandwidth
    mech_conf = 0.0
    if harmonicity < NOISE_HARMONICITY_CEILING and onset_density > 0.10:
        mech_conf = max(mech_conf, (1.0 - harmonicity) * 0.4 + onset_density * 0.6)
    if centroid < 800.0 and bandwidth < 600.0 and rms > SILENCE_RMS_THRESHOLD:
        low_cent_score = 1.0 - centroid / 800.0
        low_bw_score = 1.0 - bandwidth / 600.0
        mech_conf = max(mech_conf, (low_cent_score + low_bw_score) / 2.0)
    if mech_conf > 0.0:
        labels["mechanical_like"] = max(0.0, min(1.0, mech_conf))

    return labels


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class ClassStats:
    """Tracks per-class usage over time."""
    class_name: str
    usage_seconds: float = 0.0
    last_seen_ts: float = 0.0
    confidence: float = 0.0
    maturity_score: float = 0.0
    session_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "class_name": self.class_name,
            "usage_seconds": self.usage_seconds,
            "last_seen_ts": self.last_seen_ts,
            "confidence": self.confidence,
            "maturity_score": self.maturity_score,
            "session_count": self.session_count,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ClassStats":
        return cls(
            class_name=data["class_name"],
            usage_seconds=data.get("usage_seconds", 0.0),
            last_seen_ts=data.get("last_seen_ts", 0.0),
            confidence=data.get("confidence", 0.0),
            maturity_score=data.get("maturity_score", 0.0),
            session_count=data.get("session_count", 0),
        )


@dataclass
class SoundConcept:
    """A learned cluster within a class, representing a distinct sound concept."""
    concept_id: str
    class_name: str
    centroid: list  # float[20]
    radius: float = 0.0
    usage_count: int = 0
    session_count: int = 0
    confidence: float = 0.0
    last_seen_ts: float = 0.0
    tags: Dict[str, Any] = field(default_factory=dict)
    maturity_score: float = 0.0
    is_candidate: bool = True  # Candidates until promoted

    def to_dict(self) -> Dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "class_name": self.class_name,
            "centroid": list(self.centroid),
            "radius": self.radius,
            "usage_count": self.usage_count,
            "session_count": self.session_count,
            "confidence": self.confidence,
            "last_seen_ts": self.last_seen_ts,
            "tags": dict(self.tags),
            "maturity_score": self.maturity_score,
            "is_candidate": self.is_candidate,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SoundConcept":
        return cls(
            concept_id=data["concept_id"],
            class_name=data["class_name"],
            centroid=list(data["centroid"]),
            radius=data.get("radius", 0.0),
            usage_count=data.get("usage_count", 0),
            session_count=data.get("session_count", 0),
            confidence=data.get("confidence", 0.0),
            last_seen_ts=data.get("last_seen_ts", 0.0),
            tags=data.get("tags", {}),
            maturity_score=data.get("maturity_score", 0.0),
            is_candidate=data.get("is_candidate", True),
        )


@dataclass
class RhythmTemplate:
    """Stores quantized rhythm pattern from onset detection."""
    template_id: str
    interval_bins: list  # quantized inter-onset intervals
    tempo_estimate_bpm: float = 0.0
    usage_count: int = 0
    session_count: int = 0
    confidence: float = 0.0
    last_seen_ts: float = 0.0
    source_concept_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "template_id": self.template_id,
            "interval_bins": list(self.interval_bins),
            "tempo_estimate_bpm": self.tempo_estimate_bpm,
            "usage_count": self.usage_count,
            "session_count": self.session_count,
            "confidence": self.confidence,
            "last_seen_ts": self.last_seen_ts,
            "source_concept_id": self.source_concept_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RhythmTemplate":
        return cls(
            template_id=data["template_id"],
            interval_bins=list(data["interval_bins"]),
            tempo_estimate_bpm=data.get("tempo_estimate_bpm", 0.0),
            usage_count=data.get("usage_count", 0),
            session_count=data.get("session_count", 0),
            confidence=data.get("confidence", 0.0),
            last_seen_ts=data.get("last_seen_ts", 0.0),
            source_concept_id=data.get("source_concept_id", ""),
        )


@dataclass
class AudioHybrid:
    """Co-occurring audio concept pair promoted to hybrid status."""
    hybrid_id: str
    component_a: str  # concept_id or template_id
    component_b: str  # concept_id or template_id
    component_a_type: str  # "concept", "rhythm_template", "class"
    component_b_type: str  # "concept", "rhythm_template", "class"
    occurrence_count: int = 0
    coherence: float = 0.0
    depth: int = 1
    created_at: float = field(default_factory=time.time)
    last_seen_ts: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hybrid_id": self.hybrid_id,
            "component_a": self.component_a,
            "component_b": self.component_b,
            "component_a_type": self.component_a_type,
            "component_b_type": self.component_b_type,
            "occurrence_count": self.occurrence_count,
            "coherence": self.coherence,
            "depth": self.depth,
            "created_at": self.created_at,
            "last_seen_ts": self.last_seen_ts,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioHybrid":
        return cls(
            hybrid_id=data["hybrid_id"],
            component_a=data["component_a"],
            component_b=data["component_b"],
            component_a_type=data.get("component_a_type", "concept"),
            component_b_type=data.get("component_b_type", "concept"),
            occurrence_count=data.get("occurrence_count", 0),
            coherence=data.get("coherence", 0.0),
            depth=data.get("depth", 1),
            created_at=data.get("created_at", time.time()),
            last_seen_ts=data.get("last_seen_ts", 0.0),
        )


# ============================================================================
# SOUND CLASS MEMORY
# ============================================================================

class SoundClassMemory:
    """
    Layer 1: Tracks per-class usage, confidence, and maturity over time.
    Updated per 1.0s buffer with active class labels.
    """

    def __init__(self):
        self.class_stats: Dict[str, ClassStats] = {}
        for cls_name in AUDIO_CLASSES:
            self.class_stats[cls_name] = ClassStats(class_name=cls_name)
        self._session_active_classes: Set[str] = set()

    def update(self, labels: Dict[str, float], buffer_duration: float = 1.0) -> None:
        """
        Update class stats for a single buffer.

        Parameters
        ----------
        labels : dict
            class_name -> confidence from classify_audio().
        buffer_duration : float
            Duration of the buffer in seconds (default 1.0).
        """
        now = time.time()
        for cls_name, confidence in labels.items():
            if cls_name not in self.class_stats:
                self.class_stats[cls_name] = ClassStats(class_name=cls_name)

            stats = self.class_stats[cls_name]
            stats.usage_seconds += buffer_duration
            stats.last_seen_ts = now
            # EMA on confidence for smoothing
            stats.confidence = stats.confidence * (1.0 - EMA_ALPHA) + confidence * EMA_ALPHA
            self._session_active_classes.add(cls_name)

            # Feed maturity: slow growth toward 1.0 based on usage
            # Maturity grows logarithmically with usage seconds
            stats.maturity_score = min(
                1.0,
                math.log1p(stats.usage_seconds) / math.log1p(3600.0)
            )

    def end_session(self) -> None:
        """Mark session boundary. Increment session_count for classes seen this session."""
        for cls_name in self._session_active_classes:
            if cls_name in self.class_stats:
                self.class_stats[cls_name].session_count += 1
        self._session_active_classes.clear()

    def get_maturity(self, class_name: str) -> float:
        """Get maturity score for a class."""
        stats = self.class_stats.get(class_name)
        return stats.maturity_score if stats else 0.0

    def get_overall_maturity(self) -> float:
        """Average maturity across all classes that have been observed."""
        observed = [s for s in self.class_stats.values() if s.usage_seconds > 0]
        if not observed:
            return 0.0
        return sum(s.maturity_score for s in observed) / len(observed)

    def to_dict(self) -> Dict[str, Any]:
        return {
            cls_name: stats.to_dict()
            for cls_name, stats in self.class_stats.items()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SoundClassMemory":
        mem = cls()
        for cls_name, stats_data in data.items():
            mem.class_stats[cls_name] = ClassStats.from_dict(stats_data)
        return mem


# ============================================================================
# SOUND CONCEPT MEMORY
# ============================================================================

def _cosine_similarity(v1: list, v2: list) -> float:
    """Cosine similarity between two vectors."""
    dot_product = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    if norm1 < 1e-12 or norm2 < 1e-12:
        return 0.0
    return dot_product / (norm1 * norm2)


def _vector_distance(v1: list, v2: list) -> float:
    """Euclidean distance between two vectors."""
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(v1, v2)))


def _weighted_centroid_update(centroid: list, new_vec: list, count: int) -> list:
    """Incrementally update centroid with a new observation."""
    alpha = 1.0 / (count + 1)
    return [c * (1.0 - alpha) + v * alpha for c, v in zip(centroid, new_vec)]


class SoundConceptMemory:
    """
    Layer 2: Clusters feature vectors within each class into concepts.

    Assignment: similarity >= 0.93 -> update existing concept, else create candidate.
    Promotion: usage_count >= 14, session_count >= 3, confidence >= 0.55.
    Caps: candidate_cap = 80, concept_floor = 20 per class (configurable).
    """

    def __init__(
        self,
        candidate_cap: int = DEFAULT_CANDIDATE_CAP,
        concept_floor: int = DEFAULT_CONCEPT_FLOOR,
        similarity_threshold: float = SIMILARITY_MATCH_THRESHOLD,
    ):
        self.candidate_cap = candidate_cap
        self.concept_floor = concept_floor
        self.similarity_threshold = similarity_threshold

        # Concepts organized by class
        self.concepts: Dict[str, List[SoundConcept]] = defaultdict(list)
        # Current session tracking for session_count updates
        self._session_seen_concepts: Set[str] = set()

    def assign(
        self,
        class_name: str,
        feature_vector: list,
        confidence: float = 0.5,
    ) -> SoundConcept:
        """
        Assign a feature vector to an existing concept or create a candidate.

        Parameters
        ----------
        class_name : str
            The audio class this vector belongs to.
        feature_vector : list
            Feature vector of length 20.
        confidence : float
            Classification confidence for this buffer.

        Returns
        -------
        SoundConcept
            The matched or newly created concept.
        """
        now = time.time()
        class_concepts = self.concepts[class_name]

        # Find best matching concept
        best_concept = None
        best_similarity = -1.0

        for concept in class_concepts:
            sim = _cosine_similarity(feature_vector, concept.centroid)
            if sim > best_similarity:
                best_similarity = sim
                best_concept = concept

        if best_concept is not None and best_similarity >= self.similarity_threshold:
            # Update existing concept
            best_concept.usage_count += 1
            best_concept.last_seen_ts = now
            best_concept.centroid = _weighted_centroid_update(
                best_concept.centroid, feature_vector, best_concept.usage_count
            )
            best_concept.radius = max(
                best_concept.radius,
                _vector_distance(feature_vector, best_concept.centroid),
            )
            # EMA on confidence
            best_concept.confidence = (
                best_concept.confidence * (1.0 - EMA_ALPHA) + confidence * EMA_ALPHA
            )
            # Maturity feeds from usage and session diversity
            best_concept.maturity_score = min(
                1.0,
                math.log1p(best_concept.usage_count) / math.log1p(100.0)
                + 0.2 * min(1.0, best_concept.session_count / 10.0)
            )
            self._session_seen_concepts.add(best_concept.concept_id)
            self._try_promote(best_concept)
            return best_concept
        else:
            # Create candidate
            new_concept = SoundConcept(
                concept_id=f"sc_{class_name}_{uuid.uuid4().hex[:12]}",
                class_name=class_name,
                centroid=list(feature_vector),
                radius=0.0,
                usage_count=1,
                session_count=0,
                confidence=confidence,
                last_seen_ts=now,
                is_candidate=True,
            )
            class_concepts.append(new_concept)
            self._session_seen_concepts.add(new_concept.concept_id)
            self._enforce_caps(class_name)
            return new_concept

    def _try_promote(self, concept: SoundConcept) -> bool:
        """
        Check if a candidate should be promoted to a stable concept.
        """
        if not concept.is_candidate:
            return False  # Already promoted

        usage_req = CONCEPT_PROMOTION_USAGE
        session_req = CONCEPT_PROMOTION_SESSIONS
        confidence_req = CONCEPT_PROMOTION_CONFIDENCE

        if (concept.usage_count >= usage_req and
                concept.session_count >= session_req and
                concept.confidence >= confidence_req):
            concept.is_candidate = False
            logger.info(
                f"[AUDIO_BASELINE] Promoted concept {concept.concept_id} "
                f"(class={concept.class_name}, usage={concept.usage_count}, "
                f"sessions={concept.session_count})"
            )
            return True
        return False

    def _enforce_caps(self, class_name: str) -> None:
        """Enforce candidate cap per class; evict oldest low-confidence candidates."""
        class_concepts = self.concepts[class_name]
        candidates = [c for c in class_concepts if c.is_candidate]

        if len(candidates) <= self.candidate_cap:
            return

        # Sort candidates by confidence ascending, then by last_seen ascending
        candidates.sort(key=lambda c: (c.confidence, c.last_seen_ts))
        n_to_remove = len(candidates) - self.candidate_cap
        to_remove_ids = {c.concept_id for c in candidates[:n_to_remove]}

        self.concepts[class_name] = [
            c for c in class_concepts if c.concept_id not in to_remove_ids
        ]

        logger.debug(
            f"[AUDIO_BASELINE] Evicted {n_to_remove} candidates from {class_name}"
        )

    def end_session(self) -> None:
        """Increment session_count for all concepts seen this session."""
        for class_concepts in self.concepts.values():
            for concept in class_concepts:
                if concept.concept_id in self._session_seen_concepts:
                    concept.session_count += 1
                    self._try_promote(concept)
        self._session_seen_concepts.clear()

    def get_promoted_concepts(self, class_name: str = None) -> List[SoundConcept]:
        """Get all promoted (non-candidate) concepts, optionally filtered by class."""
        result = []
        classes = [class_name] if class_name else list(self.concepts.keys())
        for cn in classes:
            for concept in self.concepts.get(cn, []):
                if not concept.is_candidate:
                    result.append(concept)
        return result

    def get_all_concepts(self, class_name: str = None) -> List[SoundConcept]:
        """Get all concepts (including candidates) for a class."""
        if class_name:
            return list(self.concepts.get(class_name, []))
        result = []
        for class_concepts in self.concepts.values():
            result.extend(class_concepts)
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            cls_name: [c.to_dict() for c in concepts]
            for cls_name, concepts in self.concepts.items()
        }

    @classmethod
    def from_dict(
        cls,
        data: Dict[str, Any],
        candidate_cap: int = DEFAULT_CANDIDATE_CAP,
        concept_floor: int = DEFAULT_CONCEPT_FLOOR,
    ) -> "SoundConceptMemory":
        mem = cls(candidate_cap=candidate_cap, concept_floor=concept_floor)
        for cls_name, concepts_data in data.items():
            mem.concepts[cls_name] = [
                SoundConcept.from_dict(cd) for cd in concepts_data
            ]
        return mem


# ============================================================================
# MUSIC SPECIALIZATION PATH
# ============================================================================

class MusicSpecialist:
    """
    Music specialization path: enabled when specialization multipliers
    favor audio/music.

    When active:
    - Reduce promotion thresholds for music_like by 15%
    - Increase retention quota for music concepts by 25%
    - Enable rhythm templates when music_maturity >= 0.65

    Rhythm templates:
    - Onset detection from energy deltas
    - Quantize inter-onset intervals into bins
    - Store RhythmTemplate artifacts
    """

    # Quantization bins for inter-onset intervals (in seconds)
    RHYTHM_BINS = [0.125, 0.167, 0.25, 0.333, 0.5, 0.667, 1.0]

    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.rhythm_templates: Dict[str, RhythmTemplate] = {}
        self._onset_history: List[float] = []  # timestamps of detected onsets

    def apply_specialization(self, concept_memory: SoundConceptMemory) -> None:
        """
        Apply music specialization adjustments to concept memory caps.
        Called when music specialization is active.
        """
        if not self.enabled:
            return
        # Increase retention quota for music_like concepts
        music_concepts = concept_memory.concepts.get("music_like", [])
        promoted_count = sum(1 for c in music_concepts if not c.is_candidate)
        boosted_floor = int(concept_memory.concept_floor * MUSIC_RETENTION_BOOST)
        # Do not evict promoted music concepts below the boosted floor
        if promoted_count < boosted_floor:
            # Already under floor, no action needed
            pass

    def get_promotion_thresholds(self) -> Tuple[int, int, float]:
        """
        Return (usage_count, session_count, confidence) thresholds
        for music_like concepts, reduced by 15% when specialized.
        """
        if self.enabled:
            return (
                int(CONCEPT_PROMOTION_USAGE * MUSIC_PROMOTION_DISCOUNT),
                max(1, int(CONCEPT_PROMOTION_SESSIONS * MUSIC_PROMOTION_DISCOUNT)),
                CONCEPT_PROMOTION_CONFIDENCE * MUSIC_PROMOTION_DISCOUNT,
            )
        return (CONCEPT_PROMOTION_USAGE, CONCEPT_PROMOTION_SESSIONS, CONCEPT_PROMOTION_CONFIDENCE)

    def detect_onsets_from_energy(self, pcm_frames: list, sr: int = DEFAULT_SAMPLE_RATE) -> List[float]:
        """
        Onset detection from energy deltas within a buffer.

        Returns list of onset times (in seconds, relative to buffer start).
        """
        n_samples = len(pcm_frames)
        if n_samples < WINDOW_SIZE:
            return []

        hop = HOP_SIZE
        N = WINDOW_SIZE
        frame_energies = []

        start = 0
        while start + N <= n_samples:
            if HAS_NUMPY:
                frame = np.asarray(pcm_frames[start:start + N], dtype=np.float64)
                energy = float(np.sum(frame ** 2))
            else:
                frame = pcm_frames[start:start + N]
                energy = sum(x * x for x in frame)
            frame_energies.append(energy)
            start += hop

        if len(frame_energies) < 2:
            return []

        # Compute energy deltas
        deltas = [frame_energies[i + 1] - frame_energies[i]
                  for i in range(len(frame_energies) - 1)]

        # Adaptive threshold: mean + 1.5 * std of positive deltas
        positive_deltas = [d for d in deltas if d > 0]
        if not positive_deltas:
            return []

        mean_d = sum(positive_deltas) / len(positive_deltas)
        if len(positive_deltas) > 1:
            var_d = sum((d - mean_d) ** 2 for d in positive_deltas) / (len(positive_deltas) - 1)
            std_d = math.sqrt(var_d)
        else:
            std_d = 0.0

        threshold = mean_d + 1.5 * std_d

        onsets = []
        for i, d in enumerate(deltas):
            if d > threshold:
                onset_time = (i + 1) * hop / sr
                onsets.append(onset_time)

        return onsets

    def build_rhythm_template(
        self,
        onsets: List[float],
        source_concept_id: str = "",
    ) -> Optional[RhythmTemplate]:
        """
        Build a RhythmTemplate from onset times by quantizing
        inter-onset intervals into bins.

        Returns None if fewer than 3 onsets.
        """
        if len(onsets) < 3:
            return None

        # Compute inter-onset intervals
        intervals = [onsets[i + 1] - onsets[i] for i in range(len(onsets) - 1)]

        # Quantize each interval to nearest bin
        quantized = []
        for interval in intervals:
            best_bin = min(self.RHYTHM_BINS, key=lambda b: abs(b - interval))
            quantized.append(best_bin)

        # Estimate tempo from median interval
        sorted_intervals = sorted(intervals)
        median_interval = sorted_intervals[len(sorted_intervals) // 2]
        tempo_bpm = 60.0 / median_interval if median_interval > 0.01 else 0.0

        template_id = f"rt_{uuid.uuid4().hex[:12]}"
        now = time.time()

        template = RhythmTemplate(
            template_id=template_id,
            interval_bins=quantized,
            tempo_estimate_bpm=tempo_bpm,
            usage_count=1,
            session_count=0,
            confidence=0.3,
            last_seen_ts=now,
            source_concept_id=source_concept_id,
        )

        # Check for match with existing templates
        matched = self._match_template(quantized)
        if matched is not None:
            matched.usage_count += 1
            matched.last_seen_ts = now
            matched.confidence = min(1.0, matched.confidence + 0.05)
            return matched

        self.rhythm_templates[template_id] = template
        logger.info(
            f"[AUDIO_BASELINE] New rhythm template {template_id}: "
            f"tempo={tempo_bpm:.1f} BPM, {len(quantized)} intervals"
        )
        return template

    def _match_template(self, quantized_bins: list) -> Optional[RhythmTemplate]:
        """
        Find an existing template matching the quantized bins.
        Match if at least 80% of bins are identical.
        """
        if not quantized_bins:
            return None

        for template in self.rhythm_templates.values():
            existing = template.interval_bins
            # Compare sequences of same length
            min_len = min(len(existing), len(quantized_bins))
            if min_len == 0:
                continue
            matches = sum(
                1 for a, b in zip(existing[:min_len], quantized_bins[:min_len])
                if a == b
            )
            if matches / min_len >= 0.80:
                return template

        return None

    def process_buffer(
        self,
        pcm_frames: list,
        sr: int,
        music_maturity: float,
        source_concept_id: str = "",
    ) -> Optional[RhythmTemplate]:
        """
        Full music specialist processing for a single buffer.
        Only generates rhythm templates if maturity gate is met.
        """
        if not self.enabled:
            return None

        if music_maturity < MUSIC_RHYTHM_MATURITY_GATE:
            return None

        onsets = self.detect_onsets_from_energy(pcm_frames, sr)
        if not onsets:
            return None

        return self.build_rhythm_template(onsets, source_concept_id)

    def end_session(self) -> None:
        """Increment session_count for all templates."""
        for template in self.rhythm_templates.values():
            template.session_count += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "rhythm_templates": {
                tid: t.to_dict() for tid, t in self.rhythm_templates.items()
            },
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MusicSpecialist":
        spec = cls(enabled=data.get("enabled", False))
        for tid, tdata in data.get("rhythm_templates", {}).items():
            spec.rhythm_templates[tid] = RhythmTemplate.from_dict(tdata)
        return spec


# ============================================================================
# AUDIO HYBRID TRACKER
# ============================================================================

class AudioHybridTracker:
    """
    Tracks co-occurring audio concept pairs and promotes hybrids.

    Observed pairs:
    - (music_concept, rhythm_template)
    - (speech_like, phonetic_signature cluster)
    - (alarm_like, periodicity_bin)

    Promotion: count >= 10, coherence >= 0.35 (nPMI + success lift),
    hybrid_depth <= 2.
    """

    def __init__(self):
        self.hybrids: Dict[str, AudioHybrid] = {}
        self.co_occurrences: Dict[Tuple[str, str], int] = defaultdict(int)
        self.component_counts: Dict[str, int] = defaultdict(int)
        self.total_observations: int = 0
        self._session_reinforced: Set[Tuple[str, str]] = set()

    def observe(
        self,
        component_a: str,
        component_b: str,
        component_a_type: str = "concept",
        component_b_type: str = "concept",
    ) -> Optional[AudioHybrid]:
        """
        Observe a co-occurrence of two audio components.

        Returns the promoted AudioHybrid if promotion occurs, else None.
        """
        if not component_a or not component_b or component_a == component_b:
            return None

        # Check depth constraint
        depth_a = self._get_depth(component_a)
        depth_b = self._get_depth(component_b)
        if max(depth_a, depth_b) >= HYBRID_MAX_DEPTH:
            return None

        pair = tuple(sorted([component_a, component_b]))
        self.co_occurrences[pair] += 1
        self.component_counts[component_a] += 1
        self.component_counts[component_b] += 1
        self.total_observations += 1
        self._session_reinforced.add(pair)

        # Check for promotion
        if self.co_occurrences[pair] >= HYBRID_PROMOTION_COUNT:
            coherence = self._compute_coherence(pair)
            if coherence >= HYBRID_COHERENCE_THRESHOLD:
                return self._promote(
                    pair, component_a_type, component_b_type,
                    max(depth_a, depth_b) + 1, coherence
                )

        return None

    def _compute_coherence(self, pair: Tuple[str, str]) -> float:
        """
        Compute coherence via normalized PMI (nPMI) + success lift.

        nPMI = (log(P(a,b) / (P(a) * P(b)))) / (-log(P(a,b)))
        """
        if self.total_observations == 0:
            return 0.0

        count_ab = self.co_occurrences[pair]
        count_a = self.component_counts[pair[0]]
        count_b = self.component_counts[pair[1]]

        p_ab = count_ab / self.total_observations
        p_a = count_a / self.total_observations
        p_b = count_b / self.total_observations

        if p_ab <= 0 or p_a <= 0 or p_b <= 0:
            return 0.0

        pmi = math.log(p_ab / (p_a * p_b))
        neg_log_pab = -math.log(p_ab)

        if neg_log_pab < 1e-12:
            npmi = 1.0
        else:
            npmi = pmi / neg_log_pab

        # Clamp to [0, 1] for coherence
        npmi = max(0.0, min(1.0, npmi))

        # Success lift: higher count relative to promotion threshold adds confidence
        success_lift = min(0.3, (count_ab - HYBRID_PROMOTION_COUNT) * 0.03)
        success_lift = max(0.0, success_lift)

        return min(1.0, npmi * 0.7 + success_lift)

    def _get_depth(self, component_id: str) -> int:
        """Get hybrid depth of a component."""
        for hybrid in self.hybrids.values():
            if hybrid.hybrid_id == component_id:
                return hybrid.depth
        return 0

    def _promote(
        self,
        pair: Tuple[str, str],
        type_a: str,
        type_b: str,
        depth: int,
        coherence: float,
    ) -> AudioHybrid:
        """Promote a co-occurring pair to hybrid status."""
        hybrid_id = f"ah_{pair[0][:8]}_{pair[1][:8]}_{uuid.uuid4().hex[:6]}"

        # Check if already promoted
        for h in self.hybrids.values():
            existing_pair = tuple(sorted([h.component_a, h.component_b]))
            if existing_pair == pair:
                h.occurrence_count = self.co_occurrences[pair]
                h.coherence = coherence
                h.last_seen_ts = time.time()
                return h

        hybrid = AudioHybrid(
            hybrid_id=hybrid_id,
            component_a=pair[0],
            component_b=pair[1],
            component_a_type=type_a,
            component_b_type=type_b,
            occurrence_count=self.co_occurrences[pair],
            coherence=coherence,
            depth=depth,
            last_seen_ts=time.time(),
        )
        self.hybrids[hybrid_id] = hybrid

        logger.info(
            f"[AUDIO_BASELINE] Promoted hybrid {hybrid_id}: "
            f"{pair[0]} + {pair[1]} (coherence={coherence:.3f})"
        )
        return hybrid

    def end_session(self, decay_factor: float = 0.85) -> None:
        """Decay unreinforced co-occurrences."""
        for pair in list(self.co_occurrences.keys()):
            if pair not in self._session_reinforced:
                self.co_occurrences[pair] = int(self.co_occurrences[pair] * decay_factor)
                if self.co_occurrences[pair] < 1:
                    del self.co_occurrences[pair]
        self._session_reinforced.clear()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hybrids": {hid: h.to_dict() for hid, h in self.hybrids.items()},
            "co_occurrences": {
                f"{k[0]}|{k[1]}": v for k, v in self.co_occurrences.items()
            },
            "component_counts": dict(self.component_counts),
            "total_observations": self.total_observations,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioHybridTracker":
        tracker = cls()
        for hid, hdata in data.get("hybrids", {}).items():
            tracker.hybrids[hid] = AudioHybrid.from_dict(hdata)
        for k, v in data.get("co_occurrences", {}).items():
            parts = k.split("|")
            if len(parts) == 2:
                tracker.co_occurrences[(parts[0], parts[1])] = v
        tracker.component_counts = defaultdict(
            int, data.get("component_counts", {})
        )
        tracker.total_observations = data.get("total_observations", 0)
        return tracker


# ============================================================================
# AUDIO DISTILLATION
# ============================================================================

class AudioDistiller:
    """
    Audio distillation: triggered when audio_maturity >= 0.80.

    Actions:
    - Keep only concept centroids/radii, rhythm templates, tags/priors
    - Prune raw window histories, candidate buffers beyond caps
    - Decay slows per maturity rule
    """

    def __init__(self, maturity_gate: float = DISTILLATION_MATURITY_GATE):
        self.maturity_gate = maturity_gate
        self._last_distillation_ts: float = 0.0
        self._distillation_cooldown: float = 300.0  # 5 min minimum between distillations

    def should_distill(self, audio_maturity: float) -> bool:
        """Check if distillation should be triggered."""
        if audio_maturity < self.maturity_gate:
            return False
        now = time.time()
        if now - self._last_distillation_ts < self._distillation_cooldown:
            return False
        return True

    def distill(
        self,
        concept_memory: SoundConceptMemory,
        music_specialist: MusicSpecialist,
        hybrid_tracker: AudioHybridTracker,
        class_memory: SoundClassMemory,
    ) -> Dict[str, int]:
        """
        Perform distillation pass.

        Returns a report of how many items were pruned.
        """
        report = {
            "candidates_pruned": 0,
            "templates_pruned": 0,
            "co_occurrences_pruned": 0,
        }

        now = time.time()
        self._last_distillation_ts = now

        # 1. Prune candidate concepts beyond caps
        for class_name, class_concepts in concept_memory.concepts.items():
            candidates = [c for c in class_concepts if c.is_candidate]
            promoted = [c for c in class_concepts if not c.is_candidate]

            # Ensure promoted concepts meet floor
            floor = concept_memory.concept_floor
            if class_name == "music_like" and music_specialist.enabled:
                floor = int(floor * MUSIC_RETENTION_BOOST)

            # Prune weakest candidates to maintain cap
            if len(candidates) > concept_memory.candidate_cap:
                candidates.sort(key=lambda c: (c.confidence, c.usage_count))
                n_prune = len(candidates) - concept_memory.candidate_cap
                pruned_ids = {c.concept_id for c in candidates[:n_prune]}
                concept_memory.concepts[class_name] = [
                    c for c in class_concepts if c.concept_id not in pruned_ids
                ]
                report["candidates_pruned"] += n_prune

            # Clear detailed tags from promoted concepts (keep essential info)
            for concept in promoted:
                # Keep only structural tags
                essential_keys = {"dominant_chroma", "tempo_range", "source_type"}
                concept.tags = {
                    k: v for k, v in concept.tags.items() if k in essential_keys
                }

        # 2. Prune rhythm templates with very low confidence
        for tid in list(music_specialist.rhythm_templates.keys()):
            template = music_specialist.rhythm_templates[tid]
            if template.usage_count < 3 and template.confidence < 0.2:
                del music_specialist.rhythm_templates[tid]
                report["templates_pruned"] += 1

        # 3. Prune stale co-occurrences from hybrid tracker
        for pair in list(hybrid_tracker.co_occurrences.keys()):
            count = hybrid_tracker.co_occurrences[pair]
            if count < 3:
                del hybrid_tracker.co_occurrences[pair]
                report["co_occurrences_pruned"] += 1

        # 4. Slow decay for high-maturity classes
        for stats in class_memory.class_stats.values():
            if stats.maturity_score >= self.maturity_gate:
                # Halve the effective decay rate by boosting confidence retention
                stats.confidence = min(1.0, stats.confidence * 1.02)

        logger.info(
            f"[AUDIO_BASELINE] Distillation complete: {report}"
        )
        return report


# ============================================================================
# PERSISTENCE
# ============================================================================

class AudioPersistence:
    """
    Handles saving and loading audio baseline data to/from shards.

    Persistence shards:
    - library/audio/classes/*.agb
    - library/audio/concepts/*.agb
    - library/audio/templates/*.agb
    - library/audio/hybrids/*.agb
    """

    def __init__(self, library_root: str = "./library"):
        self.library_root = Path(library_root)
        self.classes_dir = self.library_root / "audio" / "classes"
        self.concepts_dir = self.library_root / "audio" / "concepts"
        self.templates_dir = self.library_root / "audio" / "templates"
        self.hybrids_dir = self.library_root / "audio" / "hybrids"

        # Create directories
        for d in [self.classes_dir, self.concepts_dir,
                  self.templates_dir, self.hybrids_dir]:
            try:
                d.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"[AUDIO_PERSIST] Failed to create directory {d}: {e}")

    def save_classes(self, class_memory: SoundClassMemory) -> bool:
        """Save class memory to shard."""
        return self._write_shard(
            self.classes_dir / "class_stats.agb",
            class_memory.to_dict(),
        )

    def load_classes(self) -> Optional[SoundClassMemory]:
        """Load class memory from shard."""
        data = self._read_shard(self.classes_dir / "class_stats.agb")
        if data is None:
            return None
        return SoundClassMemory.from_dict(data)

    def save_concepts(self, concept_memory: SoundConceptMemory) -> bool:
        """Save concept memory to shard."""
        return self._write_shard(
            self.concepts_dir / "concept_clusters.agb",
            concept_memory.to_dict(),
        )

    def load_concepts(
        self,
        candidate_cap: int = DEFAULT_CANDIDATE_CAP,
        concept_floor: int = DEFAULT_CONCEPT_FLOOR,
    ) -> Optional[SoundConceptMemory]:
        """Load concept memory from shard."""
        data = self._read_shard(self.concepts_dir / "concept_clusters.agb")
        if data is None:
            return None
        return SoundConceptMemory.from_dict(data, candidate_cap, concept_floor)

    def save_templates(self, music_specialist: MusicSpecialist) -> bool:
        """Save music specialist (rhythm templates) to shard."""
        return self._write_shard(
            self.templates_dir / "music_specialist.agb",
            music_specialist.to_dict(),
        )

    def load_templates(self) -> Optional[MusicSpecialist]:
        """Load music specialist from shard."""
        data = self._read_shard(self.templates_dir / "music_specialist.agb")
        if data is None:
            return None
        return MusicSpecialist.from_dict(data)

    def save_hybrids(self, hybrid_tracker: AudioHybridTracker) -> bool:
        """Save hybrid tracker to shard."""
        return self._write_shard(
            self.hybrids_dir / "hybrid_tracker.agb",
            hybrid_tracker.to_dict(),
        )

    def load_hybrids(self) -> Optional[AudioHybridTracker]:
        """Load hybrid tracker from shard."""
        data = self._read_shard(self.hybrids_dir / "hybrid_tracker.agb")
        if data is None:
            return None
        return AudioHybridTracker.from_dict(data)

    def save_all(
        self,
        class_memory: SoundClassMemory,
        concept_memory: SoundConceptMemory,
        music_specialist: MusicSpecialist,
        hybrid_tracker: AudioHybridTracker,
    ) -> bool:
        """Save all audio baseline data."""
        success = True
        success = self.save_classes(class_memory) and success
        success = self.save_concepts(concept_memory) and success
        success = self.save_templates(music_specialist) and success
        success = self.save_hybrids(hybrid_tracker) and success
        if success:
            logger.info("[AUDIO_PERSIST] All audio shards saved successfully")
        return success

    def _write_shard(self, path: Path, data: Dict[str, Any]) -> bool:
        """Write a shard file atomically via temp file + rename."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temp_path = path.with_suffix(".tmp")
            with open(temp_path, "w") as f:
                json.dump(data, f, indent=2)
            temp_path.replace(path)
            return True
        except Exception as e:
            logger.error(f"[AUDIO_PERSIST] Failed to write shard {path}: {e}")
            return False

    def _read_shard(self, path: Path) -> Optional[Dict[str, Any]]:
        """Read a shard file."""
        if not path.exists():
            return None
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[AUDIO_PERSIST] Failed to read shard {path}: {e}")
            return None


# ============================================================================
# AUDIO BASELINE ENGINE (Top-Level Coordinator)
# ============================================================================

class AudioBaselineEngine:
    """
    Top-level coordinator for deterministic audio perception.

    Integrates:
    - Feature extraction (audio.features.v1)
    - Multi-label classification
    - SoundClassMemory (Layer 1)
    - SoundConceptMemory (Layer 2)
    - MusicSpecialist (rhythm templates)
    - AudioHybridTracker (co-occurrence promotion)
    - AudioDistiller (maturity-gated pruning)
    - AudioPersistence (shard I/O)

    Called per 1.0s buffer from offline_ai_audio_engine.py.
    """

    def __init__(
        self,
        sr: int = DEFAULT_SAMPLE_RATE,
        library_root: str = "./library",
        music_specialization: bool = False,
        candidate_cap: int = DEFAULT_CANDIDATE_CAP,
        concept_floor: int = DEFAULT_CONCEPT_FLOOR,
    ):
        self.sr = sr

        # Persistence layer
        self.persistence = AudioPersistence(library_root)

        # Load or create memory layers
        loaded_classes = self.persistence.load_classes()
        self.class_memory = loaded_classes if loaded_classes else SoundClassMemory()

        loaded_concepts = self.persistence.load_concepts(candidate_cap, concept_floor)
        self.concept_memory = (
            loaded_concepts if loaded_concepts
            else SoundConceptMemory(candidate_cap, concept_floor)
        )

        loaded_templates = self.persistence.load_templates()
        self.music_specialist = (
            loaded_templates if loaded_templates
            else MusicSpecialist(enabled=music_specialization)
        )
        if music_specialization:
            self.music_specialist.enabled = True

        loaded_hybrids = self.persistence.load_hybrids()
        self.hybrid_tracker = (
            loaded_hybrids if loaded_hybrids
            else AudioHybridTracker()
        )

        self.distiller = AudioDistiller()

        # Buffer counter for periodic saves
        self._buffer_count: int = 0
        self._save_interval: int = 60  # save every 60 buffers (60 seconds)

        logger.info(
            f"[AUDIO_BASELINE] Engine initialized: sr={sr}, "
            f"music_spec={self.music_specialist.enabled}, "
            f"classes={len(self.class_memory.class_stats)}, "
            f"concepts={sum(len(v) for v in self.concept_memory.concepts.values())}"
        )

    def process_buffer(self, pcm_frames: list) -> Dict[str, Any]:
        """
        Process a single 1.0s PCM buffer through the full pipeline.

        Parameters
        ----------
        pcm_frames : list
            Mono PCM samples (float, range -1.0 to 1.0) for a 1.0s window.

        Returns
        -------
        dict
            Processing result with keys:
            - "features": list[float] (length 20)
            - "labels": dict[str, float] (class -> confidence)
            - "matched_concepts": list[str] (concept IDs)
            - "rhythm_template": str or None (template ID if generated)
            - "hybrid_promoted": str or None (hybrid ID if promoted)
        """
        # 1. Extract features
        features = extract_features(pcm_frames, self.sr)

        # 2. Classify
        labels = classify_audio(features, self.sr)

        # 3. Update class memory
        self.class_memory.update(labels, buffer_duration=1.0)

        # 4. Assign to concepts for each active class
        matched_concepts = []
        for class_name, confidence in labels.items():
            concept = self.concept_memory.assign(class_name, features, confidence)
            matched_concepts.append(concept.concept_id)

            # Apply music specialization thresholds
            if class_name == "music_like" and self.music_specialist.enabled:
                usage_req, session_req, conf_req = self.music_specialist.get_promotion_thresholds()
                if (concept.is_candidate and
                        concept.usage_count >= usage_req and
                        concept.session_count >= session_req and
                        concept.confidence >= conf_req):
                    concept.is_candidate = False
                    logger.info(
                        f"[AUDIO_BASELINE] Music specialist promoted {concept.concept_id}"
                    )

        # 5. Music specialist: rhythm template generation
        rhythm_template_id = None
        if self.music_specialist.enabled and "music_like" in labels:
            music_maturity = self.class_memory.get_maturity("music_like")
            source_id = matched_concepts[0] if matched_concepts else ""
            template = self.music_specialist.process_buffer(
                pcm_frames, self.sr, music_maturity, source_id
            )
            if template is not None:
                rhythm_template_id = template.template_id

        # 6. Observe hybrid co-occurrences
        hybrid_promoted_id = None
        active_components = list(matched_concepts)
        if rhythm_template_id:
            active_components.append(rhythm_template_id)

        # Track pairwise co-occurrences among active components
        for i in range(len(active_components)):
            for j in range(i + 1, len(active_components)):
                comp_a = active_components[i]
                comp_b = active_components[j]
                type_a = "rhythm_template" if comp_a == rhythm_template_id else "concept"
                type_b = "rhythm_template" if comp_b == rhythm_template_id else "concept"
                result = self.hybrid_tracker.observe(comp_a, comp_b, type_a, type_b)
                if result is not None:
                    hybrid_promoted_id = result.hybrid_id

        # 7. Check distillation
        audio_maturity = self.class_memory.get_overall_maturity()
        if self.distiller.should_distill(audio_maturity):
            self.distiller.distill(
                self.concept_memory,
                self.music_specialist,
                self.hybrid_tracker,
                self.class_memory,
            )

        # 8. Periodic persistence
        self._buffer_count += 1
        if self._buffer_count % self._save_interval == 0:
            self.save()

        return {
            "features": features,
            "labels": labels,
            "matched_concepts": matched_concepts,
            "rhythm_template": rhythm_template_id,
            "hybrid_promoted": hybrid_promoted_id,
        }

    def end_session(self) -> None:
        """
        End the current session. Updates session counts, applies decay,
        and persists all data.
        """
        self.class_memory.end_session()
        self.concept_memory.end_session()
        self.music_specialist.end_session()
        self.hybrid_tracker.end_session()

        # Apply music specialization adjustments
        if self.music_specialist.enabled:
            self.music_specialist.apply_specialization(self.concept_memory)

        self.save()
        logger.info("[AUDIO_BASELINE] Session ended and data persisted")

    def save(self) -> bool:
        """Persist all data to shards."""
        return self.persistence.save_all(
            self.class_memory,
            self.concept_memory,
            self.music_specialist,
            self.hybrid_tracker,
        )

    def set_music_specialization(self, enabled: bool) -> None:
        """Enable or disable music specialization path."""
        self.music_specialist.enabled = enabled
        logger.info(f"[AUDIO_BASELINE] Music specialization: {enabled}")

    def get_status(self) -> Dict[str, Any]:
        """Get comprehensive status of the audio baseline engine."""
        total_concepts = sum(
            len(concepts) for concepts in self.concept_memory.concepts.values()
        )
        promoted_concepts = len(self.concept_memory.get_promoted_concepts())
        audio_maturity = self.class_memory.get_overall_maturity()

        return {
            "schema_version": FEATURE_SCHEMA_VERSION,
            "feature_vector_length": FEATURE_VECTOR_LENGTH,
            "sample_rate": self.sr,
            "buffers_processed": self._buffer_count,
            "audio_maturity": round(audio_maturity, 4),
            "class_stats": {
                name: {
                    "usage_seconds": round(stats.usage_seconds, 1),
                    "confidence": round(stats.confidence, 4),
                    "maturity": round(stats.maturity_score, 4),
                    "sessions": stats.session_count,
                }
                for name, stats in self.class_memory.class_stats.items()
                if stats.usage_seconds > 0
            },
            "total_concepts": total_concepts,
            "promoted_concepts": promoted_concepts,
            "rhythm_templates": len(self.music_specialist.rhythm_templates),
            "hybrids": len(self.hybrid_tracker.hybrids),
            "music_specialization": self.music_specialist.enabled,
            "distillation_ready": audio_maturity >= DISTILLATION_MATURITY_GATE,
        }

    def shutdown(self) -> None:
        """Graceful shutdown: persist all data."""
        self.save()
        logger.info("[AUDIO_BASELINE] Shutdown complete")
