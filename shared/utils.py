#!/usr/bin/env python3
"""
Agora AI Platform - Shared Utilities
======================================
Authors: Sunni (Sir) Morningstar & Cael Devo

Pure-function utility helpers used across the on-device engine,
platform backend, and sync protocol.

All functions are stateless and safe to call from any thread.
NumPy is optional; every function provides a pure-Python fallback
so the module works on Android builds that ship without NumPy.
"""

import hashlib
import hmac
import json
import math
import time
import uuid
from datetime import datetime, timezone
from typing import Any, List, Sequence, Union

# ---------------------------------------------------------------------------
# Optional NumPy import (mirrors engine/offline_ai_core.py pattern)
# ---------------------------------------------------------------------------
try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    np = None  # type: ignore[assignment]
    _HAS_NUMPY = False


# ============================================================================
# NUMERIC HELPERS
# ============================================================================

def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp *value* to the closed interval [min_val, max_val].

    >>> clamp(1.5, 0.0, 1.0)
    1.0
    >>> clamp(-0.3, 0.0, 1.0)
    0.0
    """
    return max(min_val, min(max_val, float(value)))


def clamp01(value: float) -> float:
    """Clamp *value* to the closed interval [0.0, 1.0].

    >>> clamp01(2.7)
    1.0
    >>> clamp01(-0.1)
    0.0
    """
    return clamp(value, 0.0, 1.0)


def ema_update(current: float, new_value: float, alpha: float) -> float:
    """Return an exponential-moving-average update.

    result = current * (1 - alpha) + new_value * alpha

    *alpha* is clamped to [0, 1] for safety.

    >>> round(ema_update(0.5, 1.0, 0.1), 4)
    0.55
    """
    alpha = clamp01(alpha)
    return current * (1.0 - alpha) + new_value * alpha


# ============================================================================
# VECTOR / LINEAR-ALGEBRA HELPERS
# ============================================================================

def cosine_similarity(
    a: Union[Sequence[float], Any],
    b: Union[Sequence[float], Any],
) -> float:
    """Cosine similarity between two equal-length vectors.

    Uses NumPy when available; falls back to pure Python otherwise.
    Returns 0.0 for zero-length or zero-magnitude vectors.

    >>> round(cosine_similarity([1, 0, 0], [0, 1, 0]), 4)
    0.0
    >>> round(cosine_similarity([1, 2, 3], [1, 2, 3]), 4)
    1.0
    """
    if _HAS_NUMPY:
        a_arr = np.asarray(a, dtype=np.float64)
        b_arr = np.asarray(b, dtype=np.float64)
        norm_a = np.linalg.norm(a_arr)
        norm_b = np.linalg.norm(b_arr)
        if norm_a == 0.0 or norm_b == 0.0:
            return 0.0
        return float(np.dot(a_arr, b_arr) / (norm_a * norm_b))

    # Pure-Python fallback
    if len(a) != len(b) or len(a) == 0:
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    mag_a = math.sqrt(sum(x * x for x in a))
    mag_b = math.sqrt(sum(x * x for x in b))
    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0
    return dot / (mag_a * mag_b)


def l2_normalize(vector: Union[Sequence[float], Any]) -> Union[List[float], Any]:
    """Return the L2-normalised copy of *vector*.

    Uses NumPy when available; returns a plain list otherwise.
    A zero-magnitude vector is returned unchanged.

    >>> l2_normalize([3, 4])  # doctest: +SKIP
    [0.6, 0.8]
    """
    if _HAS_NUMPY:
        arr = np.asarray(vector, dtype=np.float64)
        norm = np.linalg.norm(arr)
        if norm == 0.0:
            return arr
        return arr / norm

    # Pure-Python fallback
    norm = math.sqrt(sum(x * x for x in vector))
    if norm == 0.0:
        return list(vector)
    return [x / norm for x in vector]


# ============================================================================
# HASHING & CRYPTOGRAPHIC HELPERS
# ============================================================================

def sha256_hash(data: bytes) -> str:
    """Return the hex-encoded SHA-256 digest of *data*.

    >>> sha256_hash(b"hello")[:8]
    '2cf24dba'
    """
    return hashlib.sha256(data).hexdigest()


def partner_hash(partner_pubkey: bytes, daily_salt: bytes) -> str:
    """Privacy-preserving partner identifier for daily lockout checks.

    Uses HMAC-SHA256 keyed with the daily salt so the same partner
    produces a different hash each day, preventing long-term tracking.

    >>> len(partner_hash(b"pk_example", b"salt_20250101"))
    64
    """
    return hmac.new(daily_salt, partner_pubkey, hashlib.sha256).hexdigest()


def derive_daily_salt(device_secret: bytes) -> bytes:
    """Derive a deterministic daily salt from *device_secret*.

    The salt changes every UTC calendar day, ensuring that partner
    hashes are unlinkable across days.

    Returns raw 32 bytes (use ``.hex()`` if a string is needed).
    """
    day_str = datetime.now(timezone.utc).strftime("%Y-%m-%d").encode("ascii")
    return hmac.new(device_secret, day_str, hashlib.sha256).digest()


# ============================================================================
# IDENTIFIERS & TIMESTAMPS
# ============================================================================

def generate_uuid() -> str:
    """Return a new random UUID v4 as a lowercase hex string with dashes.

    >>> len(generate_uuid())
    36
    """
    return str(uuid.uuid4())


def timestamp_now() -> float:
    """Return the current UNIX timestamp as a float (seconds since epoch).

    >>> isinstance(timestamp_now(), float)
    True
    """
    return time.time()


def date_stamp() -> str:
    """Return today's date in YYYY-MM-DD format (UTC).

    >>> import re; bool(re.match(r"\\d{4}-\\d{2}-\\d{2}", date_stamp()))
    True
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


# ============================================================================
# SERIALISATION HELPERS
# ============================================================================

def safe_json_dumps(obj: Any) -> str:
    """Canonical JSON serialisation suitable for hashing.

    * Keys are sorted.
    * Separators have no trailing whitespace.
    * Encoding is UTF-8.
    * Non-ASCII characters are preserved (``ensure_ascii=False``).
    * ``default`` handler converts unknown types to their string repr.

    >>> safe_json_dumps({"b": 2, "a": 1})
    '{"a":1,"b":2}'
    """
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
