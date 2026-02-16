#!/usr/bin/env python3
"""
DPME Post-Response Comparison + Coherence-First Policy
=======================================================

After every emitted response the CoherenceScorer computes a composite
coherence score from lexical continuity, structural validity, and
affect congruence.  When the score falls below a configurable threshold
the system generates a DPMESuggestion -- a bounded parameter delta --
and applies it immediately so subsequent responses benefit from the
correction.

The CoherencePolicy implements the "Coherence Before Meaning" ramp:
while lexical maturity is low, coherence bias dominates; once the
maturity threshold is crossed, emotional nuance weight is gradually
ramped up.

This module is part of the Agora AI Offline Engine perception pipeline.
"""

import logging
import math
import re
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants / tunables
# ---------------------------------------------------------------------------

# Default coherence threshold below which a DPME correction is triggered.
DEFAULT_COHERENCE_THRESHOLD = 0.55

# Maximum absolute delta a single suggestion may propose.
MAX_SUGGESTION_DELTA = 0.10

# Lexical maturity threshold that divides the "coherence-first" phase
# from the "emotional nuance ramp" phase.
MATURITY_THRESHOLD = 0.65

# Weight bounds for the coherence-first ramp.
COHERENCE_WEIGHT_HIGH = 0.85
COHERENCE_WEIGHT_LOW = 0.35
NUANCE_WEIGHT_LOW = 0.10
NUANCE_WEIGHT_HIGH = 0.60

# Sub-score component weights for the composite coherence score.
LEXICAL_CONTINUITY_WEIGHT = 0.40
STRUCTURE_VALIDITY_WEIGHT = 0.35
AFFECT_CONGRUENCE_WEIGHT = 0.25


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class DPMESuggestion:
    """
    A single parameter-adjustment suggestion generated when
    coherence drops below threshold.
    """
    suggestion_id: str
    timestamp: float = field(default_factory=time.time)
    parameter_name: str = ""
    delta: float = 0.0
    reason: str = ""
    coherence_score_at_trigger: float = 0.0
    applied: bool = False

    def __post_init__(self) -> None:
        # Enforce bounded delta.
        self.delta = max(-MAX_SUGGESTION_DELTA, min(MAX_SUGGESTION_DELTA, self.delta))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "suggestion_id": self.suggestion_id,
            "timestamp": self.timestamp,
            "parameter_name": self.parameter_name,
            "delta": self.delta,
            "reason": self.reason,
            "coherence_score_at_trigger": self.coherence_score_at_trigger,
            "applied": self.applied,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DPMESuggestion":
        return cls(
            suggestion_id=data["suggestion_id"],
            timestamp=data.get("timestamp", time.time()),
            parameter_name=data.get("parameter_name", ""),
            delta=data.get("delta", 0.0),
            reason=data.get("reason", ""),
            coherence_score_at_trigger=data.get("coherence_score_at_trigger", 0.0),
            applied=data.get("applied", False),
        )


# ---------------------------------------------------------------------------
# Coherence Scorer
# ---------------------------------------------------------------------------

class CoherenceScorer:
    """
    Computes a composite coherence score in [0, 1] for a generated response.

    Sub-scores
    ----------
    * **lexical_continuity_score** -- measures how well the response
      re-uses or logically extends vocabulary from the prior context
      rather than introducing entirely disconnected words.
    * **structure_validity_score** -- basic grammar / structural heuristics:
      sentence termination, bracket balance, repeated-word detection.
    * **affect_congruence_score** -- checks whether the emotional tone
      of the response is within the bounds defined by the current
      affect state.
    """

    def __init__(
        self,
        coherence_threshold: float = DEFAULT_COHERENCE_THRESHOLD,
    ) -> None:
        self.coherence_threshold = coherence_threshold

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def score_response(
        self,
        response_text: str,
        context: str,
        affect_state: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """
        Score a response and return a breakdown dict.

        Parameters
        ----------
        response_text : str
            The text just emitted by the AI.
        context : str
            The recent conversational context (prior turns concatenated).
        affect_state : dict, optional
            Keys ``valence`` [-1,1], ``arousal`` [0,1], ``dominance`` [0,1].
            When ``None`` the affect sub-score defaults to 0.5 (neutral).

        Returns
        -------
        dict
            ``lexical_continuity_score``, ``structure_validity_score``,
            ``affect_congruence_score``, ``coherence_score`` (composite).
        """
        lex_score = self._lexical_continuity(response_text, context)
        struct_score = self._structure_validity(response_text)
        affect_score = self._affect_congruence(response_text, affect_state)

        composite = (
            LEXICAL_CONTINUITY_WEIGHT * lex_score
            + STRUCTURE_VALIDITY_WEIGHT * struct_score
            + AFFECT_CONGRUENCE_WEIGHT * affect_score
        )
        composite = max(0.0, min(1.0, composite))

        return {
            "lexical_continuity_score": round(lex_score, 6),
            "structure_validity_score": round(struct_score, 6),
            "affect_congruence_score": round(affect_score, 6),
            "coherence_score": round(composite, 6),
        }

    # ------------------------------------------------------------------
    # Sub-score implementations
    # ------------------------------------------------------------------

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Lowercase whitespace tokenisation with punctuation stripped."""
        return re.findall(r"[a-z0-9]+(?:'[a-z]+)?", text.lower())

    def _lexical_continuity(self, response: str, context: str) -> float:
        """
        Fraction of response tokens that also appear in the context,
        smoothed to avoid penalising naturally novel words too harshly.

        Returns a score in [0, 1].
        """
        if not response or not context:
            return 0.5  # Neutral when no data.

        response_tokens = self._tokenize(response)
        if not response_tokens:
            return 0.5

        context_tokens_set = set(self._tokenize(context))
        if not context_tokens_set:
            return 0.5

        # Count how many response tokens overlap with context vocabulary.
        overlap_count = sum(1 for t in response_tokens if t in context_tokens_set)
        raw_ratio = overlap_count / len(response_tokens)

        # Smooth: perfect overlap (1.0) is suspicious (parrot), so best
        # score is around 0.7-0.9 overlap.  Below 0.2 is disconnected.
        # Use a simple logistic mapping centred at 0.45.
        score = 1.0 / (1.0 + math.exp(-12.0 * (raw_ratio - 0.35)))
        return max(0.0, min(1.0, score))

    def _structure_validity(self, response: str) -> float:
        """
        Grammar / structure heuristics.  Returns a score in [0, 1].

        Checks:
        1. Sentence termination -- response ends with sentence-ending punct.
        2. Bracket / quote balance.
        3. Repeated consecutive words (stuttering).
        4. Minimum length -- very short responses get a small penalty.
        """
        if not response or not response.strip():
            return 0.0

        score = 1.0
        penalties: List[float] = []

        text = response.strip()

        # 1. Sentence termination.
        if text[-1] not in ".!?\"')":
            penalties.append(0.15)

        # 2. Bracket / quote balance.
        bracket_pairs = [("(", ")"), ("[", "]"), ("{", "}")]
        for opener, closer in bracket_pairs:
            if text.count(opener) != text.count(closer):
                penalties.append(0.10)

        # Simple quote balance (even count of each quote type).
        for q in ['"', "'"]:
            count = text.count(q)
            # Odd count means unbalanced (heuristic -- not perfect for
            # apostrophes, but good enough).
            if q == '"' and count % 2 != 0:
                penalties.append(0.10)

        # 3. Repeated consecutive words.
        words = text.lower().split()
        if len(words) >= 2:
            repeat_count = sum(
                1 for a, b in zip(words, words[1:]) if a == b and len(a) > 2
            )
            if repeat_count > 0:
                # Penalty proportional to repetition density.
                penalties.append(min(0.30, repeat_count * 0.08))

        # 4. Minimum length.
        if len(words) < 3:
            penalties.append(0.10)

        # 5. Excessive punctuation density.
        punct_count = sum(1 for ch in text if ch in "!?.,;:-")
        if len(text) > 0:
            punct_density = punct_count / len(text)
            if punct_density > 0.15:
                penalties.append(min(0.20, (punct_density - 0.15) * 2.0))

        score = max(0.0, score - sum(penalties))
        return round(score, 6)

    def _affect_congruence(
        self,
        response: str,
        affect_state: Optional[Dict[str, float]],
    ) -> float:
        """
        Heuristic check that the emotional tone of the response is
        congruent with the current affect bounds.

        Uses a lightweight keyword approach to estimate response valence,
        then compares to the affect state valence.  Returns [0, 1].
        """
        if affect_state is None:
            return 0.5  # Neutral -- no affect information available.

        target_valence = affect_state.get("valence", 0.0)
        target_arousal = affect_state.get("arousal", 0.0)

        # Estimate response valence via keyword matching.
        positive_markers = {
            "happy", "great", "wonderful", "good", "nice", "love", "enjoy",
            "thank", "awesome", "excellent", "glad", "pleased", "kind",
            "beautiful", "fantastic", "perfect", "yes", "sure", "welcome",
        }
        negative_markers = {
            "sorry", "bad", "wrong", "hate", "unfortunately", "sad",
            "terrible", "awful", "problem", "fail", "error", "no",
            "difficult", "hard", "pain", "hurt", "angry", "upset",
        }
        high_arousal_markers = {
            "amazing", "incredible", "wow", "exciting", "urgent",
            "hurry", "quick", "alarm", "surprise", "shock",
        }

        tokens = set(self._tokenize(response))
        pos_count = len(tokens & positive_markers)
        neg_count = len(tokens & negative_markers)
        arousal_count = len(tokens & high_arousal_markers)

        total = pos_count + neg_count
        if total == 0:
            estimated_valence = 0.0
        else:
            estimated_valence = (pos_count - neg_count) / total

        estimated_arousal = min(1.0, arousal_count * 0.25)

        # Distance between estimated and target.
        valence_distance = abs(estimated_valence - target_valence)
        arousal_distance = abs(estimated_arousal - target_arousal)

        # Weighted congruence (valence matters more).
        congruence = 1.0 - (0.7 * valence_distance + 0.3 * arousal_distance)
        return max(0.0, min(1.0, congruence))


# ---------------------------------------------------------------------------
# DPME Correction Engine
# ---------------------------------------------------------------------------

class DPMECorrectionEngine:
    """
    Consumes coherence scores and emits bounded DPMESuggestions when
    the score falls below threshold.  Maintains a persistent log of
    all suggestions for later consolidation.
    """

    def __init__(
        self,
        coherence_threshold: float = DEFAULT_COHERENCE_THRESHOLD,
        max_log_size: int = 200,
    ) -> None:
        self.coherence_threshold = coherence_threshold
        self.max_log_size = max(10, max_log_size)
        self._log: List[DPMESuggestion] = []
        self._suggestion_counter = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def evaluate_and_correct(
        self,
        scores: Dict[str, float],
    ) -> Optional[DPMESuggestion]:
        """
        Given a coherence breakdown dict (from CoherenceScorer), decide
        whether a correction is needed and return a DPMESuggestion if so.

        The suggestion's *delta* is bounded by ``MAX_SUGGESTION_DELTA``
        and its *applied* flag is set to ``True`` to indicate immediate
        application.

        Returns ``None`` when no correction is needed.
        """
        coherence = scores.get("coherence_score", 1.0)
        if coherence >= self.coherence_threshold:
            return None

        # Identify the weakest sub-score and propose a correction.
        sub_scores = {
            "lexical_continuity": scores.get("lexical_continuity_score", 1.0),
            "structure_validity": scores.get("structure_validity_score", 1.0),
            "affect_congruence": scores.get("affect_congruence_score", 1.0),
        }
        weakest_param = min(sub_scores, key=sub_scores.get)  # type: ignore[arg-type]
        weakest_value = sub_scores[weakest_param]

        # Delta: proportional to how far below threshold we are, capped.
        gap = self.coherence_threshold - coherence
        raw_delta = gap * 0.5  # Conservative: half the gap.
        bounded_delta = max(-MAX_SUGGESTION_DELTA, min(MAX_SUGGESTION_DELTA, raw_delta))

        param_map = {
            "lexical_continuity": "communication.precision",
            "structure_validity": "communication.formality",
            "affect_congruence": "communication.warmth",
        }
        target_param = param_map.get(weakest_param, "communication.precision")

        reason = (
            f"Coherence {coherence:.3f} < threshold {self.coherence_threshold:.3f}; "
            f"weakest sub-score: {weakest_param}={weakest_value:.3f}"
        )

        self._suggestion_counter += 1
        suggestion = DPMESuggestion(
            suggestion_id=f"dpme_coh_{self._suggestion_counter}_{int(time.time())}",
            parameter_name=target_param,
            delta=bounded_delta,
            reason=reason,
            coherence_score_at_trigger=coherence,
            applied=True,
        )

        self._record(suggestion)

        logger.info(
            "[COHERENCE] Correction: %s += %.4f (%s)",
            target_param, bounded_delta, reason,
        )

        return suggestion

    # ------------------------------------------------------------------
    # Log management
    # ------------------------------------------------------------------

    def _record(self, suggestion: DPMESuggestion) -> None:
        """Append to the internal log, pruning oldest entries if needed."""
        self._log.append(suggestion)
        if len(self._log) > self.max_log_size:
            self._log = self._log[-self.max_log_size:]

    @property
    def log(self) -> List[DPMESuggestion]:
        """Read-only view of the suggestion log."""
        return list(self._log)

    @property
    def log_size(self) -> int:
        return len(self._log)

    def get_recent_suggestions(self, n: int = 10) -> List[DPMESuggestion]:
        """Return the *n* most recent suggestions."""
        return list(self._log[-n:])

    def get_cumulative_delta(self, parameter_name: str) -> float:
        """Sum of all applied deltas for a given parameter."""
        return sum(
            s.delta for s in self._log
            if s.parameter_name == parameter_name and s.applied
        )

    # ------------------------------------------------------------------
    # Serialisation
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "coherence_threshold": self.coherence_threshold,
            "max_log_size": self.max_log_size,
            "suggestion_counter": self._suggestion_counter,
            "log": [s.to_dict() for s in self._log],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DPMECorrectionEngine":
        engine = cls(
            coherence_threshold=data.get("coherence_threshold", DEFAULT_COHERENCE_THRESHOLD),
            max_log_size=data.get("max_log_size", 200),
        )
        engine._suggestion_counter = data.get("suggestion_counter", 0)
        for entry in data.get("log", []):
            try:
                engine._log.append(DPMESuggestion.from_dict(entry))
            except (KeyError, TypeError) as exc:
                logger.warning("[COHERENCE] Skipping malformed log entry: %s", exc)
        return engine


# ---------------------------------------------------------------------------
# Coherence-First Policy ("Coherence Before Meaning" Ramp)
# ---------------------------------------------------------------------------

class CoherencePolicy:
    """
    Determines the blending weights between coherence-bias and
    emotional-nuance based on current lexical maturity.

    Phase 1 -- lexical_maturity < MATURITY_THRESHOLD:
        coherence_weight  = COHERENCE_WEIGHT_HIGH
        nuance_weight     = NUANCE_WEIGHT_LOW

    Phase 2 -- lexical_maturity >= MATURITY_THRESHOLD:
        coherence_weight ramps down linearly toward COHERENCE_WEIGHT_LOW
        nuance_weight ramps up linearly toward NUANCE_WEIGHT_HIGH
        as maturity rises from MATURITY_THRESHOLD to 1.0.
    """

    def __init__(
        self,
        maturity_threshold: float = MATURITY_THRESHOLD,
        coherence_high: float = COHERENCE_WEIGHT_HIGH,
        coherence_low: float = COHERENCE_WEIGHT_LOW,
        nuance_low: float = NUANCE_WEIGHT_LOW,
        nuance_high: float = NUANCE_WEIGHT_HIGH,
    ) -> None:
        self.maturity_threshold = maturity_threshold
        self.coherence_high = coherence_high
        self.coherence_low = coherence_low
        self.nuance_low = nuance_low
        self.nuance_high = nuance_high

    def get_weights(self, lexical_maturity: float) -> Dict[str, float]:
        """
        Return blending weights for the current maturity level.

        Parameters
        ----------
        lexical_maturity : float
            Value in [0, 1] representing the AI's current lexical
            maturity.  Clamped internally.

        Returns
        -------
        dict
            ``coherence_weight`` and ``nuance_weight``, both in [0, 1].
            Also includes ``phase`` (``"coherence_first"`` or
            ``"nuance_ramp"``).
        """
        maturity = max(0.0, min(1.0, lexical_maturity))

        if maturity < self.maturity_threshold:
            # Phase 1: coherence dominates.
            return {
                "coherence_weight": self.coherence_high,
                "nuance_weight": self.nuance_low,
                "phase": "coherence_first",
            }

        # Phase 2: linear ramp.
        # t goes from 0.0 (at threshold) to 1.0 (at maturity = 1.0).
        range_span = 1.0 - self.maturity_threshold
        if range_span <= 0.0:
            t = 1.0
        else:
            t = (maturity - self.maturity_threshold) / range_span

        coherence_w = self.coherence_high + t * (self.coherence_low - self.coherence_high)
        nuance_w = self.nuance_low + t * (self.nuance_high - self.nuance_low)

        return {
            "coherence_weight": round(max(0.0, min(1.0, coherence_w)), 6),
            "nuance_weight": round(max(0.0, min(1.0, nuance_w)), 6),
            "phase": "nuance_ramp",
        }

    def to_dict(self) -> Dict[str, Any]:
        return {
            "maturity_threshold": self.maturity_threshold,
            "coherence_high": self.coherence_high,
            "coherence_low": self.coherence_low,
            "nuance_low": self.nuance_low,
            "nuance_high": self.nuance_high,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CoherencePolicy":
        return cls(
            maturity_threshold=data.get("maturity_threshold", MATURITY_THRESHOLD),
            coherence_high=data.get("coherence_high", COHERENCE_WEIGHT_HIGH),
            coherence_low=data.get("coherence_low", COHERENCE_WEIGHT_LOW),
            nuance_low=data.get("nuance_low", NUANCE_WEIGHT_LOW),
            nuance_high=data.get("nuance_high", NUANCE_WEIGHT_HIGH),
        )
