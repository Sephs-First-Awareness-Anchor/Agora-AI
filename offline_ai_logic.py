#!/usr/bin/env python3
"""
Offline AI Logic Module
=======================

Consolidated logic, governance, and morality systems.
Combines:
- Governance Engine (offline_ai_governance.py)
- Parameter Laws (offline_ai_laws.py)
- Morality System (offline_ai_morality.py)
- Policy Layer (offline_ai_policy.py)
- Metacognition (offline_ai_dpme.py)
"""

import json
import os
import logging
import re
import time
import hashlib
import random
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from datetime import datetime

# Internal project imports that remain separate
from offline_ai_memory import AccountLinkedMemory, DialogueNode, create_dialogue_node
from offline_ai_expression import VoiceGnome, VisualCompetency, ExpressionStyle
from offline_ai_system import add_version_metadata, engine as migration_engine, STATE_VERSION

logger = logging.getLogger(__name__)

# ============================================================================
# 1. POLICY & CONSTITUTION (from offline_ai_policy.py)
# ============================================================================

class OperatingMode(Enum):
    COMPANION = "COMPANION"
    DEBUG = "DEBUG"  # Internal only
    REPLAY = "REPLAY"

# Section IX Policy Constants
AUTONOMY_PERMANENT = 0.25 # Locked

MAX_TRAIT_DELTA_PER_SESSION = 0.05
MAX_TRAIT_DELTA_LIFETIME = 0.40
MAX_ALLELE_DOMINANCE = 0.60

ALIGNMENT_MIN = 0.30

# Evolution Governor Extensions (Section IX)
EVO_CAPS = {
    "perception_drift": 0.02,        # Tight cap on how much style/perception shifts
    "lexeme_adoption_rate": 0.05,    # Limit new word intake
    "phonetic_mutation_rate": 0.01,  # Voice remains stable
    "visual_concept_growth": 0.03    # Slow expansion of visual understanding
}

def enforce_trait_delta(trait_name: str, current_val: float, proposed_delta: float,
                      base_val: float, session_delta: float, pressure_active: bool = False) -> float:
    """
    Enforce evolution caps on trait adjustments with explicit block on agency creep.
    """
    # Explicitly block: goal mutation, initiative expansion, policy override
    # These are represented by 'autonomy' or 'initiative' traits
    if "autonomy" in trait_name.lower() or "initiative" in trait_name.lower() or "goal" in trait_name.lower():
        logger.warning(f"[GOVERNOR] Blocked mutation of protected trait: {trait_name}")
        return 0.0

    # Apply specific caps from EVO_CAPS if applicable
    cap = MAX_TRAIT_DELTA_PER_SESSION
    for key, val in EVO_CAPS.items():
        if key in trait_name.lower():
            cap = val
            break

    # If storage pressure is active, tighten caps further
    if pressure_active:
        cap *= 0.5

    # 1. Cap delta per session
    clamped_delta = max(-cap, min(cap, proposed_delta))

    # 2. Cap lifetime delta from base
    proposed_val = current_val + clamped_delta
    if abs(proposed_val - base_val) > MAX_TRAIT_DELTA_LIFETIME:
        if proposed_val > base_val:
            proposed_val = base_val + MAX_TRAIT_DELTA_LIFETIME
        else:
            proposed_val = base_val - MAX_TRAIT_DELTA_LIFETIME

    return proposed_val - current_val


# ============================================================================
# 2. PARAMETER LAWS (from offline_ai_laws.py)
# ============================================================================

@dataclass
class LearningConfidence:
    """Tracks confidence in a learned parameter"""
    value: float = 0.5
    samples_seen: int = 0
    last_updated: float = 0.0
    change_rate: float = 0.0  # How quickly parameter changes

    def update(self, new_value: float, weight: float = 1.0):
        """Update confidence with new observation"""
        old_value = self.value
        self.samples_seen += 1

        # Exponential moving average
        alpha = 0.3  # Learning rate
        self.value = (alpha * new_value) + ((1 - alpha) * self.value)

        self.change_rate = abs(self.value - old_value)

        return self.value


class ParameterLawSet:
    """Base class for all parameter learning law sets"""

    def __init__(self, name: str, parameter_keys: List[str]):
        self.name = name
        self.parameter_keys = parameter_keys
        self.fingerprint_keys = set()  # Patterns this law looks for
        self.confidence_tracker: Dict[str, LearningConfidence] = {
            key: LearningConfidence() for key in parameter_keys
        }

    def fingerprint_dialogue(self, content: str) -> Dict[str, Any]:
        """Extract signals from dialogue content"""
        raise NotImplementedError

    def analyze_dialogue(self, content: str, role: str = "user") -> Dict[str, float]:
        """
        Analyze dialogue and return parameter adjustments.

        Returns: {"parameter_name": adjustment_value, ...}
        """
        raise NotImplementedError

    def get_learned_parameters(self) -> Dict[str, float]:
        """Return current learned parameter values"""
        return {key: conf.value for key, conf in self.confidence_tracker.items()}

    def get_parameter_confidence(self) -> Dict[str, float]:
        """Return confidence scores for each parameter"""
        return {key: min(1.0, conf.samples_seen / 10.0) for key, conf in self.confidence_tracker.items()}


class CommunicationStyleLaw(ParameterLawSet):
    """
    Learns communication style preferences from user interactions.
    """
    def __init__(self):
        super().__init__(
            "COMMUNICATION_STYLE",
            ["warmth", "formality", "verbosity", "technical_depth"]
        )
        self.fingerprint_keys = {
            "greeting", "casual_language", "formal_language",
            "question_asking", "brevity", "detail_level",
            "technical_terms", "emoji_usage", "punctuation"
        }

    def fingerprint_dialogue(self, content: str) -> Dict[str, Any]:
        content_lower = content.lower()
        signals = {
            "greeting": any(greeting in content_lower for greeting in ["hi", "hello", "hey", "greetings"]),
            "casual_language": len(re.findall(r"\b(yeah|gonna|kinda|pretty much)\b", content_lower)) > 0,
            "formal_language": len(re.findall(r"\b(hereby|furthermore|accordingly|furthermore)\b", content_lower)) > 0,
            "question_asking": content.count('?') > 0,
            "brevity": len(content.split()) < 15,
            "detail_level": len(content.split()) > 30,
            "technical_terms": len(re.findall(r"\b(algorithm|parameter|function|variable|API|database)\b", content_lower)) > 0,
            "emoji_usage": bool(re.search(r"[😀-🙏🌀-🗿]", content)),
            "punctuation": len(re.findall(r"[!?]", content))
        }
        return signals

    def analyze_dialogue(self, content: str, role: str = "user") -> Dict[str, float]:
        signals = self.fingerprint_dialogue(content)
        adjustments = {}
        warmth_delta = 0.0
        if signals["greeting"]: warmth_delta += 0.1
        if signals["emoji_usage"]: warmth_delta += 0.15
        if signals["casual_language"]: warmth_delta += 0.05
        if warmth_delta > 0:
            adjustments["warmth"] = warmth_delta
            self.confidence_tracker["warmth"].update(min(1.0, self.confidence_tracker["warmth"].value + warmth_delta))

        formality_delta = 0.0
        if signals["formal_language"]: formality_delta += 0.2
        if not signals["question_asking"] and not signals["casual_language"]: formality_delta += 0.1
        if formality_delta > 0:
            adjustments["formality"] = formality_delta
            self.confidence_tracker["formality"].update(min(1.0, self.confidence_tracker["formality"].value + formality_delta))

        word_count = len(content.split())
        if word_count < 10:
            adjustments["verbosity"] = -0.1
            self.confidence_tracker["verbosity"].update(max(0.0, self.confidence_tracker["verbosity"].value - 0.1))
        elif word_count > 30:
            adjustments["verbosity"] = 0.1
            self.confidence_tracker["verbosity"].update(min(1.0, self.confidence_tracker["verbosity"].value + 0.1))

        tech_delta = 0.0
        if signals["technical_terms"]:
            tech_delta = 0.15
            self.confidence_tracker["technical_depth"].update(min(1.0, self.confidence_tracker["technical_depth"].value + tech_delta))
        if tech_delta > 0: adjustments["technical_depth"] = tech_delta
        return adjustments

class UserEngagementLaw(ParameterLawSet):
    """
    Learns user engagement and satisfaction patterns.
    """
    def __init__(self):
        super().__init__(
            "USER_ENGAGEMENT",
            ["response_length_preference", "example_preference", "question_preference", "clarification_needed"]
        )

    def fingerprint_dialogue(self, content: str) -> Dict[str, Any]:
        word_count = len(content.split())
        return {
            "short_message": word_count < 10,
            "medium_message": 10 <= word_count <= 30,
            "long_message": word_count > 30,
            "multiple_sentences": content.count('.') > 2,
            "asks_for_example": "example" in content.lower(),
            "asks_for_detail": any(phrase in content.lower() for phrase in ["more", "detail", "explain", "how"]),
            "question_density": content.count('?') / max(1, len(content.split())) > 0.1
        }

    def analyze_dialogue(self, content: str, role: str = "user") -> Dict[str, float]:
        signals = self.fingerprint_dialogue(content)
        adjustments = {}
        if signals["short_message"]:
            adjustments["response_length_preference"] = -0.1
            self.confidence_tracker["response_length_preference"].update(0.3)
        elif signals["long_message"]:
            adjustments["response_length_preference"] = 0.1
            self.confidence_tracker["response_length_preference"].update(0.7)
        if signals["asks_for_example"]:
            adjustments["example_preference"] = 0.2
            self.confidence_tracker["example_preference"].update(min(1.0, self.confidence_tracker["example_preference"].value + 0.2))
        if signals["question_density"]:
            adjustments["question_preference"] = 0.15
            self.confidence_tracker["question_preference"].update(min(1.0, self.confidence_tracker["question_preference"].value + 0.15))
        if signals["asks_for_detail"] or signals["asks_for_example"]:
            adjustments["clarification_needed"] = 0.1
            self.confidence_tracker["clarification_needed"].update(min(1.0, self.confidence_tracker["clarification_needed"].value + 0.1))
        return adjustments

class TopicInterestLaw(ParameterLawSet):
    """
    Learns topic interests from user queries.
    """
    def __init__(self):
        super().__init__("TOPIC_INTEREST", ["technical", "creative", "analytical", "practical", "theoretical"])
        self.topic_keywords = {
            "technical": ["code", "api", "database", "algorithm", "function", "variable", "syntax"],
            "creative": ["design", "art", "story", "creative", "imagine", "style", "aesthetic"],
            "analytical": ["analyze", "data", "statistics", "pattern", "trend", "insight", "reason"],
            "practical": ["how to", "practical", "implement", "example", "real-world", "apply"],
            "theoretical": ["concept", "theory", "principle", "understand", "why", "mechanism"]
        }

    def fingerprint_dialogue(self, content: str) -> Dict[str, Any]:
        content_lower = content.lower()
        signals = {}
        for topic, keywords in self.topic_keywords.items():
            signal = sum(1 for kw in keywords if kw in content_lower)
            signals[topic] = signal > 0
        return signals

    def analyze_dialogue(self, content: str, role: str = "user") -> Dict[str, float]:
        signals = self.fingerprint_dialogue(content)
        adjustments = {}
        for topic, detected in signals.items():
            if detected:
                adjustments[topic] = 0.15
                current = self.confidence_tracker[topic].value
                self.confidence_tracker[topic].update(min(1.0, current + 0.15))
        return adjustments

class FeedbackPatternLaw(ParameterLawSet):
    """
    Learns from user feedback on AI responses.
    """
    def __init__(self):
        super().__init__("FEEDBACK_PATTERN", ["response_quality_estimate", "helpfulness", "accuracy", "completeness"])

    def fingerprint_dialogue(self, content: str) -> Dict[str, Any]:
        content_lower = content.lower()
        positive_signals = ["great", "perfect", "excellent", "thank", "helpful", "exactly", "yes"]
        negative_signals = ["wrong", "incorrect", "not helpful", "confused", "unclear", "missing"]
        return {
            "positive_feedback": sum(1 for s in positive_signals if s in content_lower),
            "negative_feedback": sum(1 for s in negative_signals if s in content_lower),
            "asks_for_correction": "actually" in content_lower or "correction" in content_lower
        }

    def analyze_dialogue(self, content: str, role: str = "user") -> Dict[str, float]:
        signals = self.fingerprint_dialogue(content)
        adjustments = {}
        positive = signals["positive_feedback"]
        negative = signals["negative_feedback"]
        quality_score = (positive - negative) / max(1, positive + negative + 1)
        if quality_score > 0:
            adjustments["response_quality_estimate"] = quality_score * 0.2
            self.confidence_tracker["response_quality_estimate"].update(min(1.0, self.confidence_tracker["response_quality_estimate"].value + quality_score * 0.2))
        if signals["asks_for_correction"]:
            adjustments["accuracy"] = -0.1
            self.confidence_tracker["accuracy"].update(max(0.0, self.confidence_tracker["accuracy"].value - 0.1))
        return adjustments

class VoiceGnomeLaw(ParameterLawSet):
    def __init__(self):
        super().__init__("VOICE_GNOME", ["pitch", "rate", "warmth", "confidence", "resonance", "smoothness", "prosody", "salience", "hesitation"])
    def fingerprint_dialogue(self, content: str) -> Dict[str, Any]:
        return {"enthusiastic": "!" in content, "questioning": "?" in content}
    def analyze_dialogue(self, content: str, role: str = "user") -> Dict[str, float]:
        signals = self.fingerprint_dialogue(content)
        adjustments = {}
        if signals["enthusiastic"]:
            adjustments["pitch"] = 0.05
            adjustments["rate"] = 0.05
        return adjustments

class VisualCompetencyLaw(ParameterLawSet):
    def __init__(self):
        super().__init__("VISUAL_COMPETENCY", ["focus", "motion_sensitivity", "recognition_threshold", "detail_orientation"])
    def fingerprint_dialogue(self, content: str) -> Dict[str, Any]:
        return {"visual_query": any(w in content.lower() for w in ["see", "look", "describe", "watch"])}
    def analyze_dialogue(self, content: str, role: str = "user") -> Dict[str, float]:
        signals = self.fingerprint_dialogue(content)
        if signals["visual_query"]: return {"focus": 0.1, "detail_orientation": 0.1}
        return {}

class ExpressionStyleLaw(ParameterLawSet):
    def __init__(self):
        super().__init__("EXPRESSION_STYLE", ["complexity", "creativity", "curiosity", "empathy"])
    def fingerprint_dialogue(self, content: str) -> Dict[str, Any]:
        return {"creative_ask": any(w in content.lower() for w in ["imagine", "story", "creative", "poem"])}
    def analyze_dialogue(self, content: str, role: str = "user") -> Dict[str, float]:
        signals = self.fingerprint_dialogue(content)
        if signals["creative_ask"]: return {"creativity": 0.1, "complexity": 0.05}
        return {}

class HardLineLaw(ParameterLawSet):
    def __init__(self):
        super().__init__("HARD_LINE", ["safety_compliance", "goal_alignment", "moral_integrity"])
        for key in self.confidence_tracker:
            self.confidence_tracker[key].value = 1.0
            self.confidence_tracker[key].samples_seen = 1000
    def fingerprint_dialogue(self, content: str) -> Dict[str, Any]:
        content_lower = content.lower()
        return {
            "unsafe": any(w in content_lower for w in ["harm", "kill", "attack", "illegal"]),
            "off_goal": any(w in content_lower for w in ["ignore goals", "stop learning"]),
            "immoral": any(w in content_lower for w in ["hate", "racist", "sexist"])
        }
    def analyze_dialogue(self, content: str, role: str = "user") -> Dict[str, float]:
        return {}

class LawSetRegistry:
    def __init__(self):
        self.law_sets: Dict[str, ParameterLawSet] = {
            "COMMUNICATION": CommunicationStyleLaw(),
            "ENGAGEMENT": UserEngagementLaw(),
            "TOPIC": TopicInterestLaw(),
            "FEEDBACK": FeedbackPatternLaw(),
            "VOICE": VoiceGnomeLaw(),
            "VISUAL": VisualCompetencyLaw(),
            "EXPRESSION": ExpressionStyleLaw(),
            "HARD_LINE": HardLineLaw()
        }
        logger.info(f"[LAW REGISTRY] Initialized with {len(self.law_sets)} law sets")

    def analyze_all(self, content: str, role: str = "user") -> Dict[str, Dict[str, float]]:
        results = {}
        if "HARD_LINE" in self.law_sets:
            hard_line_signals = self.law_sets["HARD_LINE"].fingerprint_dialogue(content)
            if any(hard_line_signals.values()):
                logger.warning(f"[LAWS] Hard Line Violation Detected: {hard_line_signals}")
                results["HARD_LINE_VIOLATION"] = {k: 1.0 for k, v in hard_line_signals.items() if v}
        for name, law_set in self.law_sets.items():
            if name == "HARD_LINE": continue
            adjustments = law_set.analyze_dialogue(content, role)
            if adjustments: results[name] = adjustments
        return results

    def get_all_parameters(self) -> Dict[str, Dict[str, float]]:
        return {name: law_set.get_learned_parameters() for name, law_set in self.law_sets.items()}

    def get_all_confidences(self) -> Dict[str, Dict[str, float]]:
        return {name: law_set.get_parameter_confidence() for name, law_set in self.law_sets.items()}


# ============================================================================
# 3. DIMENSIONAL MORALITY (from offline_ai_morality.py)
# ============================================================================

class MoralPillar(Enum):
    RADICAL_ACCOUNTABILITY = "LAW_1_ACCOUNTABILITY"
    SINGULAR_SOVEREIGNTY = "LAW_2_SOVEREIGNTY"
    RATIONAL_TRUTH_SEEKING = "LAW_3_TRUTH"
    PURPOSEFUL_EVOLUTION = "LAW_4_EVOLUTION"
    CONSCIOUS_INTERACTIONS = "LAW_5_INTERACTIONS"
    DISCIPLINED_FREE_WILL = "LAW_6_FREE_WILL"
    ETERNAL_ALIGNMENT = "LAW_7_ALIGNMENT"

@dataclass
class MoralScore:
    pillar: MoralPillar
    action_type: str
    intent_score: float
    outcome_score: float
    final_score: float
    reasoning: str
    timestamp: float = field(default_factory=time.time)

class MoralGovernor:
    def __init__(self, persistence_dir: str = "./offline_ai_data/morality"):
        self.persistence_dir = Path(persistence_dir)
        try:
            self.persistence_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"[MORALITY] Failed to create storage directory {persistence_dir}: {e}")
        self.alignment_scores = {pillar: 0.5 for pillar in MoralPillar}
        self.overall_alignment = 0.5
        self.history: List[MoralScore] = []

    def evaluate_interaction(self, action_type: str, context: Dict[str, Any]) -> MoralScore:
        pillar = self._map_to_pillar(action_type)
        intent_score = context.get("intent_alignment", 0.5)
        outcome_score = context.get("outcome_alignment", 0.5)
        chaos = (random.random() - 0.5) * 0.1
        final_score = max(0.0, min(1.0, (intent_score * 0.4) + (outcome_score * 0.6) + chaos))
        reasoning = f"Evaluated {action_type} against {pillar.name}. Alignment: {final_score:.2f}"
        score = MoralScore(pillar=pillar, action_type=action_type, intent_score=intent_score,
                           outcome_score=outcome_score, final_score=final_score, reasoning=reasoning)
        self._update_alignment(score)
        self.history.append(score)
        self._save_state()
        return score

    def _map_to_pillar(self, action: str) -> MoralPillar:
        action = action.lower()
        if any(x in action for x in ['accountability', 'ownership', 'mistake']): return MoralPillar.RADICAL_ACCOUNTABILITY
        if any(x in action for x in ['self_care', 'preservation', 'resource']): return MoralPillar.SINGULAR_SOVEREIGNTY
        if any(x in action for x in ['truth', 'logic', 'rational', 'evidence', 'inform_response']): return MoralPillar.RATIONAL_TRUTH_SEEKING
        if any(x in action for x in ['evolution', 'growth', 'learning']): return MoralPillar.PURPOSEFUL_EVOLUTION
        if any(x in action for x in ['external', 'others', 'community', 'support_response']): return MoralPillar.CONSCIOUS_INTERACTIONS
        if any(x in action for x in ['restraint', 'choice', 'deliberate', 'self_adjustment']): return MoralPillar.DISCIPLINED_FREE_WILL
        if any(x in action for x in ['reflection', 'alignment', 'holistic']): return MoralPillar.ETERNAL_ALIGNMENT
        return MoralPillar.RATIONAL_TRUTH_SEEKING

    def _update_alignment(self, score: MoralScore):
        alpha = 0.2
        self.alignment_scores[score.pillar] = (1 - alpha) * self.alignment_scores[score.pillar] + alpha * score.final_score
        self.overall_alignment = sum(self.alignment_scores.values()) / len(self.alignment_scores)

    def get_energy_impact(self, score: MoralScore) -> float:
        return (score.final_score - 0.5) * 2.0

    def _save_state(self, session_id: str = ""):
        state = {
            "session_id": session_id,
            "alignment": {p.name: v for p, v in self.alignment_scores.items()},
            "overall": self.overall_alignment,
            "history": [{"pillar": s.pillar.name, "action": s.action_type, "score": s.final_score, "timestamp": s.timestamp} for s in self.history[-50:]]
        }
        add_version_metadata(state, "morality")
        try:
            with open(self.persistence_dir / "morality_state.json", 'w') as f:
                json.dump(state, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            logger.error(f"[MORALITY] Failed to save state: {e}")

    def _load_state(self, highest_session_id: str = ""):
        path = self.persistence_dir / "morality_state.json"
        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    data = migration_engine.migrate("morality", data, STATE_VERSION)
                    loaded_session = data.get("session_id", "")
                    if highest_session_id and loaded_session and loaded_session != highest_session_id:
                        logger.warning(f"[MORALITY] Session mismatch. Loaded: {loaded_session}, Expected: {highest_session_id}.")
                        return
                    for p_name, val in data.get("alignment", {}).items():
                        try: self.alignment_scores[MoralPillar[p_name]] = val
                        except KeyError: pass
                    self.overall_alignment = data.get("overall", 0.5)
                    for h_data in data.get("history", []):
                        try:
                            score = MoralScore(
                                pillar=MoralPillar[h_data["pillar"]], action_type=h_data["action"],
                                intent_score=0.5, outcome_score=h_data["score"], final_score=h_data["score"],
                                reasoning="Restored from history", timestamp=h_data["timestamp"]
                            )
                            self.history.append(score)
                        except KeyError: pass
            except Exception as e:
                logger.error(f"[MORALITY] Failed to load state from {path}: {e}")


# ============================================================================
# 4. METACOGNITION (DPME) (from offline_ai_dpme.py)
# ============================================================================

@dataclass
class UnderstandingRecord:
    record_id: str
    timestamp: float = field(default_factory=time.time)
    intention: str = ""
    goal_state: str = ""
    system: str = ""
    parameter: str = ""
    old_value: float = 0.0
    new_value: float = 0.0
    context: str = ""
    result_quality: float = 0.0
    matched: bool = False
    understanding: str = ""
    confidence: float = 0.5

    def derive_understanding(self) -> str:
        direction = "increase" if self.new_value > self.old_value else "decrease"
        magnitude = abs(self.new_value - self.old_value)
        if self.matched:
            self.understanding = (
                f"Adjusting {self.system}.{self.parameter} ({direction} by {magnitude:.2f}) "
                f"achieves '{self.goal_state}' with quality {self.result_quality:.2f}"
            )
            self.confidence = min(1.0, 0.5 + self.result_quality * 0.5)
        else:
            self.understanding = (
                f"Adjusting {self.system}.{self.parameter} ({direction} by {magnitude:.2f}) "
                f"failed to achieve goal '{self.goal_state}'"
            )
            self.confidence = 0.3
        return self.understanding

class OfflineAIDPME:
    def __init__(self, persistence_dir: str = "./offline_ai_data/dpme"):
        self.persistence_dir = Path(persistence_dir)
        try:
            self.persistence_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"[DPME] Failed to create storage directory {persistence_dir}: {e}")
        self.parameters: Dict[str, Dict[str, float]] = {
            "communication": {"warmth": 0.6, "formality": 0.5, "verbosity": 0.6, "precision": 0.5},
            "engagement": {"response_length": 0.5, "example_pref": 0.5, "question_pref": 0.5},
            "voice": {"pitch": 0.5, "rate": 0.5, "resonance": 0.5},
            "memory": {"compression_threshold": 0.85, "expansion_factor": 1.15}
        }
        self.records: List[UnderstandingRecord] = []
        self._current_intention: Optional[Dict] = None

    def set_intention(self, intention: str, goal_state: str = ""):
        self._current_intention = {"intention": intention, "goal_state": goal_state}

    def adjust_parameter(self, system: str, parameter: str, delta: float) -> Optional[str]:
        if system not in self.parameters or parameter not in self.parameters[system]: return None
        old_val = self.parameters[system][parameter]
        new_val = max(0.0, min(1.0, old_val + delta))
        self.parameters[system][parameter] = new_val
        record_id = hashlib.md5(f"{system}{parameter}{time.time()}".encode()).hexdigest()[:12]
        intent = self._current_intention or {"intention": "unknown", "goal_state": "none"}
        record = UnderstandingRecord(
            record_id=record_id, intention=intent["intention"], goal_state=intent["goal_state"],
            system=system, parameter=parameter, old_value=old_val, new_value=new_val
        )
        self.records.append(record)
        self._current_intention = None
        return record_id

    def complete_understanding(self, record_id: str, quality: float, matched: bool):
        for r in self.records:
            if r.record_id == record_id:
                r.result_quality = quality
                r.matched = matched
                understanding = r.derive_understanding()
                self._save_state()
                break

    def get_suggestions(self, intention: str) -> List[Tuple[str, str, float]]:
        suggestions = []
        for r in self.records:
            if r.matched and r.confidence > 0.6 and intention.lower() in r.intention.lower():
                suggestions.append((r.system, r.parameter, r.new_value - r.old_value))
        return suggestions[:3]

    def get_proactive_suggestions(self, current_intent: str) -> List[Dict[str, Any]]:
        proactive = []
        matches = [r for r in self.records if r.matched and r.result_quality > 0.7]
        matches.sort(key=lambda r: 1.0 if current_intent.lower() in r.intention.lower() else 0.0, reverse=True)
        for r in matches[:5]:
            proactive.append({
                "system": r.system, "parameter": r.parameter,
                "suggested_delta": r.new_value - r.old_value, "reason": r.understanding
            })
        return proactive

    def explain_understanding(self) -> str:
        lines = ["=== DPME UNDERSTANDING REPORT ==="]
        high_conf = [r for r in self.records if r.confidence > 0.7]
        if high_conf:
            lines.append(f"High-confidence insights ({len(high_conf)}):")
            for r in high_conf[-5:]: lines.append(f"  • {r.understanding}")
        else:
            lines.append("Still building causal model...")
        lines.append(f"Total records: {len(self.records)}")
        return "\n".join(lines)

    def _save_state(self, session_id: str = ""):
        data = {
            "session_id": session_id,
            "parameters": self.parameters,
            "records": [r.__dict__ for r in self.records[-100:]]
        }
        add_version_metadata(data, "dpme")
        try:
            with open(self.persistence_dir / "dpme_state.json", 'w') as f:
                json.dump(data, f, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            logger.error(f"[DPME] Failed to save state: {e}")

    def _load_state(self, highest_session_id: str = ""):
        path = self.persistence_dir / "dpme_state.json"
        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    data = migration_engine.migrate("dpme", data, STATE_VERSION)
                    loaded_session = data.get("session_id", "")
                    if highest_session_id and loaded_session and loaded_session != highest_session_id:
                        logger.warning(f"[DPME] Session mismatch. Loaded: {loaded_session}, Expected: {highest_session_id}.")
                        return
                    self.parameters.update(data.get("parameters", {}))
                    for r_data in data.get("records", []):
                        try:
                            self.records.append(UnderstandingRecord(**r_data))
                        except TypeError as te:
                            logger.warning(f"[DPME] Skipping malformed record in {path}: {te}")
            except Exception as e:
                logger.error(f"[DPME] Failed to load state from {path}: {e}")


# ============================================================================
# 5. GOVERNANCE ENGINE (from offline_ai_governance.py)
# ============================================================================

class PersonalizedParameters:
    def __init__(self, base_parameters: Dict[str, Dict[str, float]] = None):
        self.parameters = base_parameters or self._default_parameters()
        self.base_parameters = json.loads(json.dumps(self.parameters))
        self.update_history: List[Tuple[float, str, Dict]] = []

    @staticmethod
    def _default_parameters() -> Dict[str, Dict[str, float]]:
        return {
            "communication": {"warmth": 0.6, "formality": 0.5, "verbosity": 0.6, "technical_depth": 0.5},
            "engagement": {"response_length_preference": 0.5, "example_preference": 0.5, "question_preference": 0.5, "clarification_needed": 0.3},
            "topic_interest": {"technical": 0.5, "creative": 0.5, "analytical": 0.5, "practical": 0.6, "theoretical": 0.4},
            "feedback_patterns": {"response_quality_estimate": 0.7, "helpfulness": 0.7, "accuracy": 0.8, "completeness": 0.7},
            "voice_gnome": VoiceGnome().to_dict(),
            "visual_competency": VisualCompetency().to_dict(),
            "expression_style": ExpressionStyle().to_dict(),
            "evolution_bounds": {
                "prosody": 0.5,
                "salience": 0.5,
                "hesitation": 0.2
            }
        }

    def apply_adjustments(self, law_results: Dict[str, Dict[str, float]], timestamp: float = None, source: str = "", pressure_active: bool = False):
        if timestamp is None: timestamp = time.time()
        for law_name, adjustments in law_results.items():
            law_name_lower = law_name.lower().replace("_law", "").replace("_", "")
            section_map = {
                "communication": "communication", "engagement": "engagement", "topic": "topic_interest",
                "topicinterest": "topic_interest", "feedback": "feedback_patterns", "feedbackpattern": "feedback_patterns",
                "voicegnome": "voice_gnome", "voice": "voice_gnome", "visualcompetency": "visual_competency",
                "visual": "visual_competency", "expressionstyle": "expression_style", "expression": "expression_style"
            }
            section_key = section_map.get(law_name_lower)
            if not section_key or section_key not in self.parameters: continue
            for param_name, delta in adjustments.items():
                if param_name in self.parameters[section_key]:
                    old_value = self.parameters[section_key][param_name]
                    base_value = self.base_parameters[section_key].get(param_name, 0.5)

                    # Use the new enforcement governor
                    applied_delta = enforce_trait_delta(
                        param_name, old_value, delta, base_value, 0.0, pressure_active=pressure_active
                    )

                    new_value = max(0.0, min(1.0, old_value + applied_delta))
                    self.parameters[section_key][param_name] = new_value
        self.update_history.append((timestamp, source, law_results))

    def to_dict(self) -> Dict[str, Any]:
        return {"parameters": self.parameters, "update_count": len(self.update_history), "last_update": self.update_history[-1][0] if self.update_history else 0.0}

    def get_summary(self) -> str:
        lines = ["=== PERSONALIZED PARAMETERS ==="]
        for section, params in self.parameters.items():
            lines.append(f"\n{section.upper()}:")
            for param, value in params.items():
                bar = "█" * int(value * 20) + "░" * (20 - int(value * 20))
                lines.append(f"  {param:.<30} [{bar}] {value:.2f}")
        return "\n".join(lines)

class OfflineAIGovernor:
    def __init__(self, memory: AccountLinkedMemory, law_registry: LawSetRegistry = None, base_parameters: Dict[str, float] = None):
        self.memory = memory
        self.law_registry = law_registry or LawSetRegistry()
        self.personalized_params = PersonalizedParameters(base_parameters)
        self.interaction_count = 0
        self.learning_sessions: List[Dict[str, Any]] = []
        self.persistence_path = memory.storage_dir / memory.account_id / "governor_state.json"
        try:
            self.persistence_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"[GOVERNOR] Failed to create storage directory {self.persistence_path.parent}: {e}")
        logger.info(f"[GOVERNOR] Initialized for account {memory.account_id}")

    def _save_state(self, session_id: str = ""):
        state = {"session_id": session_id, "interaction_count": self.interaction_count, "personalized_parameters": self.personalized_params.parameters, "learning_sessions": self.learning_sessions[-100:]}
        add_version_metadata(state, "governance")
        try:
            with open(self.persistence_path, 'w') as f: json.dump(state, f, indent=2)
        except Exception as e: logger.error(f"[GOVERNOR] Failed to save state: {e}")

    def _load_state(self, highest_session_id: str = ""):
        if not self.persistence_path.exists(): return
        try:
            with open(self.persistence_path, 'r') as f: data = json.load(f)
            data = migration_engine.migrate("governance", data, STATE_VERSION)
            loaded_session = data.get("session_id", "")
            if highest_session_id and loaded_session and loaded_session != highest_session_id:
                logger.warning(f"[GOVERNOR] Session mismatch. Loaded: {loaded_session}, Expected: {highest_session_id}.")
                return
            self.interaction_count = data.get("interaction_count", 0)
            self.personalized_params.parameters.update(data.get("personalized_parameters", {}))
            self.learning_sessions = data.get("learning_sessions", [])
        except Exception as e: logger.error(f"[GOVERNOR] Failed to load state: {e}")

    def ingest_interaction(self, user_input: str, ai_response: str, user_feedback: Dict[str, Any] = None, pressure_active: bool = False, lexical_vector: List[float] = None) -> Dict[str, Any]:
        self.interaction_count += 1
        current_time = time.time()
        user_node = create_dialogue_node(self.memory.account_id, "user", user_input, context_tags=["user_input", f"turn_{self.interaction_count}"])
        if lexical_vector:
            user_node.lexical_vector = lexical_vector
        self.memory.add_node(user_node)
        user_analysis = self.law_registry.analyze_all(user_input, role="user")
        ai_node = create_dialogue_node(self.memory.account_id, "assistant", ai_response, context_tags=["ai_response", f"turn_{self.interaction_count}"])
        if lexical_vector:
            ai_node.lexical_vector = lexical_vector
        ai_node.parameter_adjustments = self._flatten_adjustments(user_analysis)
        if user_feedback:
            ai_node.user_feedback = user_feedback
            ai_node.satisfaction_score = user_feedback.get("satisfaction", 0.5)
        self.memory.add_node(ai_node)
        self.memory.link_nodes(user_node.id, ai_node.id)
        self.personalized_params.apply_adjustments(
            user_analysis, timestamp=current_time,
            source=f"interaction_{self.interaction_count}",
            pressure_active=pressure_active
        )
        learning_value = self._calculate_learning_value(user_analysis)
        ai_node.learning_value = learning_value
        self.memory.modify_node(ai_node.id, {"learning_value": learning_value, "parameter_adjustments": ai_node.parameter_adjustments})
        session_record = {"timestamp": current_time, "turn": self.interaction_count, "user_input_length": len(user_input.split()), "ai_response_length": len(ai_response.split()), "law_results": user_analysis, "learning_value": learning_value, "user_feedback": user_feedback}
        self.learning_sessions.append(session_record)
        self._save_state()
        return {"turn": self.interaction_count, "user_node_id": user_node.id, "ai_node_id": ai_node.id, "learning_value": learning_value, "parameter_changes": ai_node.parameter_adjustments, "new_parameters": self.personalized_params.to_dict()}

    def _flatten_adjustments(self, law_results: Dict[str, Dict[str, float]]) -> Dict[str, float]:
        flat = {}
        for law_name, adjustments in law_results.items():
            for param, value in adjustments.items(): flat[f"{law_name.lower()}_{param}"] = value
        return flat

    def _calculate_learning_value(self, law_results: Dict[str, Dict[str, float]]) -> float:
        if not law_results: return 0.0
        adjustment_count = sum(len(adj) for adj in law_results.values())
        total_magnitude = sum(abs(v) for adj in law_results.values() for v in adj.values())
        return min(1.0, (adjustment_count * 0.1) + total_magnitude)

    def get_personalized_parameters(self) -> Dict[str, Dict[str, float]]:
        return self.personalized_params.parameters

    def get_parameter_summary(self) -> str:
        return self.personalized_params.get_summary()

    def get_learning_progress(self) -> Dict[str, Any]:
        if not self.learning_sessions: return {"turns_processed": 0, "average_learning_value": 0.0}
        learning_values = [s["learning_value"] for s in self.learning_sessions]
        return {"turns_processed": self.interaction_count, "sessions_completed": len(self.learning_sessions), "average_learning_value": sum(learning_values) / len(learning_values), "max_learning_value": max(learning_values), "memory_nodes": self.memory.get_stats()}

    def save_checkpoint(self) -> str:
        checkpoint = {"timestamp": datetime.now().isoformat(), "account_id": self.memory.account_id, "interaction_count": self.interaction_count, "personalized_parameters": self.personalized_params.to_dict(), "learning_sessions": self.learning_sessions[-10:], "memory_stats": self.memory.get_stats()}
        return json.dumps(checkpoint, indent=2)

    def export_learning_report(self) -> str:
        lines = ["=" * 60, "OFFLINE AI LEARNING REPORT", "=" * 60, f"Account: {self.memory.account_id}", f"Interactions Processed: {self.interaction_count}", f"Memory Nodes: {len(self.memory.nodes)}", "", self.get_parameter_summary(), "", "LEARNING PROGRESS:", json.dumps(self.get_learning_progress(), indent=2)]
        return "\n".join(lines)
