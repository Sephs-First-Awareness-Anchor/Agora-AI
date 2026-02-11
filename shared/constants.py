#!/usr/bin/env python3
"""
Agora AI Platform - Shared Constants
=====================================
Authors: Sunni (Sir) Morningstar & Cael Devo

Canonical source of truth for all numeric thresholds, limits, and
configuration constants used across the on-device engine, platform
backend, and sync protocol.

Modules should import from here rather than defining local copies.
"""

# ============================================================================
# VISION CONSTANTS
# ============================================================================

VISION_FEATURE_LENGTH = 57
VISION_FRAME_SIZE = (64, 64)
VISION_SIMILARITY_THRESHOLD = 0.92
VISION_CANDIDATE_CAP = 60
VISION_CONCEPT_FLOOR = 20
VISION_PROMOTION_USAGE = 12
VISION_PROMOTION_SESSIONS = 3
VISION_PROMOTION_CONFIDENCE = 0.55
VISION_HYBRID_CO_OCCUR_THRESHOLD = 8
VISION_HYBRID_COHERENCE_THRESHOLD = 0.35
VISION_HYBRID_MAX_DEPTH = 2
VISION_COHERENCE_WINDOW = 1000

# Vision baseline class thresholds
VISION_LOW_LIGHT_THRESHOLD = 0.25
VISION_BRIGHT_THRESHOLD = 0.75
VISION_HIGH_MOTION_ENERGY = 0.12
VISION_HIGH_MOTION_DENSITY = 0.18
VISION_LOW_MOTION_ENERGY = 0.03
VISION_LOW_MOTION_DENSITY = 0.05
VISION_HIGH_EDGE_THRESHOLD = 0.18
VISION_LOW_EDGE_THRESHOLD = 0.05
VISION_WARM_PALETTE_THRESHOLD = 0.45
VISION_COOL_PALETTE_THRESHOLD = 0.45
VISION_HIGH_SYMMETRY_THRESHOLD = 0.12
VISION_LOW_SYMMETRY_THRESHOLD = 0.35

# ============================================================================
# AUDIO CONSTANTS
# ============================================================================

AUDIO_FEATURE_LENGTH = 20
AUDIO_WINDOW_SIZE = 1024
AUDIO_HOP_SIZE = 512
AUDIO_BUFFER_SECONDS = 1.0
AUDIO_SIMILARITY_THRESHOLD = 0.93
AUDIO_CANDIDATE_CAP = 80
AUDIO_CONCEPT_FLOOR = 20
AUDIO_PROMOTION_USAGE = 14
AUDIO_PROMOTION_SESSIONS = 3
AUDIO_PROMOTION_CONFIDENCE = 0.55
AUDIO_HYBRID_CO_OCCUR_THRESHOLD = 10
AUDIO_HYBRID_COHERENCE_THRESHOLD = 0.35
AUDIO_HYBRID_MAX_DEPTH = 2

# Audio baseline class thresholds
AUDIO_SILENCE_RMS = 0.02
AUDIO_NOISE_ZCR = 0.20
AUDIO_NOISE_HARMONICITY = 0.15
AUDIO_SPEECH_RMS_MIN = 0.04
AUDIO_SPEECH_RMS_MAX = 0.35
AUDIO_SPEECH_ZCR_MIN = 0.05
AUDIO_SPEECH_ZCR_MAX = 0.18
AUDIO_SPEECH_HARMONICITY_MIN = 0.15
AUDIO_SPEECH_HARMONICITY_MAX = 0.55
AUDIO_SPEECH_CENTROID_MIN = 300.0
AUDIO_SPEECH_CENTROID_MAX = 3000.0
AUDIO_MUSIC_HARMONICITY = 0.45

# ============================================================================
# MATURITY & DISTILLATION
# ============================================================================

MATURITY_DISTILL_THRESHOLD = 0.80
MATURITY_STABILITY_WEIGHT = 0.55
MATURITY_NOVELTY_WEIGHT = 0.35
MATURITY_COMPRESSION_WEIGHT = 0.10
PLATEAU_DECAY_FLOOR = 0.15

# ============================================================================
# COHERENCE
# ============================================================================

COHERENCE_THRESHOLD = 0.65
COHERENCE_MATURITY_RAMP = 0.65

# ============================================================================
# WISDOM
# ============================================================================

MAX_WISDOM_SHARDS = 500

# ============================================================================
# STORAGE
# ============================================================================

MAX_SHARD_BYTES = 25 * 1024 * 1024  # 25MB

# ============================================================================
# MUSIC SPECIALIZATION
# ============================================================================

MUSIC_PROMOTION_REDUCTION = 0.15
MUSIC_RETENTION_BOOST = 0.25
MUSIC_RHYTHM_MATURITY_THRESHOLD = 0.65

# ============================================================================
# PACK TYPES
# ============================================================================

PACK_TYPE_CAPABILITY = "capability"
PACK_TYPE_CLASS = "class"
PACK_TYPE_HUB_CACHE = "hub_cache"

# ============================================================================
# ORIGINS
# ============================================================================

ORIGIN_DEVICE = "DEVICE"
ORIGIN_CLASS = "CLASS"
ORIGIN_SOCIAL = "SOCIAL"
ORIGIN_PURCHASED = "PURCHASED"
ORIGIN_SYSTEM = "SYSTEM"
ORIGIN_EMERGENT = "EMERGENT"

# ============================================================================
# MEET MODE
# ============================================================================

MEET_QR_ROTATE_SECONDS = 15
MEET_QR_ACCEPT_WINDOW = 30
MEET_LINGER_DURATION = 30
MEET_LINGER_SAMPLE_HZ = 2
MEET_LINGER_RSSI_THRESHOLD = -70
MEET_LINGER_RSSI_PASS_RATIO = 0.70

# ============================================================================
# SCHEMA VERSIONS
# ============================================================================

SCHEMA_VERSION = "1.0"
ENGINE_VERSION = "0.1.0"
