#!/usr/bin/env python3
"""
Offline AI Response Composer
============================
Authors: Sunni (Sir) Morningstar & Cael Devo

Turns what the companion has learned into what it says.

The engine already learns a great deal from its user: stable lexemes bound to
intents, word/percept groundings from the camera, phonetic lexemes from the
user's voice, and reply templates from dialogue. Before this module none of it
reached the spoken reply, which came from a fixed list of lines per intent.

This module implements the Expression Pipeline from the Offline Engine Spec
(section 2.2):

    1. Assembly           - candidate replies built from learned material
    2. Expression Ecology - variants scored and selected; losers culled
    3. Pressure Evaluation- coherence-first scoring (spec 8.2 / 8.4 ramp)
    4. Voice Genome       - per-AI variation profile shapes selection
    5. Output

Culled variants are distilled into WisdomShards (spec section 7) so the
companion's selection drifts toward what works for its own user.

Every AI gets its own AIVariationProfile: a specialization pair plus a random
ability multiplier per learning domain and small personality offsets, drawn
once from a seed tied to the account and then persisted. Two companions that
hear the same things therefore grow into different speakers.

The engine stays UI-agnostic: nothing here imports app/ or Kivy.
"""

import hashlib
import json
import logging
import random
import re
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .agora_sync.offline_ai_capabilities import (
    DEFAULT_GAIN_MULTIPLIERS,
    SpecializationProfile,
    SpecializationType,
)
from .perception.wisdom import ExpressionWisdomStore, WisdomShard

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

LEARNING_DOMAINS = ("lexical", "memory", "expression", "voice", "visual", "audio")
PERSONALITY_TRAITS = ("warmth", "formality", "curiosity", "assertiveness", "empathy", "precision")

# Random ability multiplier range per domain (applied on top of specialization gains)
ABILITY_MULTIPLIER_RANGE = (0.85, 1.15)
# Personality offset range applied to the base voice genome
PERSONALITY_OFFSET_RANGE = (-0.10, 0.10)

# Spec 8.4: coherence-before-meaning ramp
LEXICAL_MATURITY_THRESHOLD = 0.65
LEXICAL_MATURITY_SATURATION = 200   # stable content lexemes for full maturity

# Association memory
ASSOCIATION_DECAY = 0.97            # per observed turn, for pairs not seen
ASSOCIATION_MIN_STRENGTH = 2.0      # co-occurrence strength before recall is used
MAX_ASSOCIATIONS_PER_WORD = 24

# User phrasebook (learning the user's own way of speaking)
PHRASE_MAX_WORDS = 5
PHRASE_PROMOTION_COUNT = 2

# Template learning
TEMPLATE_SUCCESS_THRESHOLD = 0.65
TEMPLATE_CATEGORY_SUFFIX = "reply"

# Ecology
RECENT_OUTPUT_WINDOW = 8
MOVE_FITNESS_LR = 0.2

# Words that carry structure rather than topic. The lexicon promotes every word
# it hears, so topic selection filters these and also anything the user says
# under too many different intents (a data-driven function-word test).
FUNCTION_WORDS = frozenset("""
a an the and or but so if then than that this these those there here it its it's
i i'm im me my mine we us our you your yours he him his she her they them their
is am are was were be been being do does did doing have has had having will would
can could should shall may might must not no yes to of in on at by for with from
about as into over under up down out off just very really too also again what
when where why how who whom which some any all each every more most much many
like get got go going went come came make made know think want say said tell
told thing things one ones lot well oh ok okay hey hi hello thanks thank please
""".split())

# Intent families. Hybrid intents resolve to the families of their two bases.
INTENT_FAMILY = {
    "CONNECT": "social", "THANK": "social", "APOLOGIZE": "social",
    "EXPRESS": "emotional", "REACT": "emotional",
    "QUESTION": "inquiry", "EVALUATE": "inquiry", "VALIDATE": "inquiry",
    "INFORM": "sharing", "NARRATE": "sharing", "REFLECT": "sharing", "EXPLORE": "sharing",
    "AGREE": "agreement", "CONFIRM": "agreement",
    "DENY": "disagreement", "CHALLENGE": "disagreement",
    "REQUEST": "action", "DIRECT": "action", "PLAN": "action", "SUMMARIZE": "action",
}

# Composition moves and the learning domain that powers each one.
MOVE_DOMAIN = {
    "learned_reply": "lexical",
    "topic_reflection": "expression",
    "association_recall": "memory",
    "grounded_recall": "visual",
    "user_phrase": "voice",
    "curiosity_probe": "audio",
    "seed_line": "expression",
}

# Base weight of each move before fitness, gains and coherence.
MOVE_BASE_WEIGHT = {
    "learned_reply": 1.2,
    "topic_reflection": 1.0,
    "association_recall": 1.3,
    "grounded_recall": 1.3,
    "user_phrase": 1.1,
    "curiosity_probe": 0.8,
    "seed_line": 0.35,
}

# Directed frames. Agora is a directed public product: the frames are authored,
# the slots ({topic}, {assoc}, {percept}, {word}, {name}) are filled only from
# what this companion has learned from its own user.
TOPIC_FRAMES = {
    "social": ["Good to hear from you, {name}. Still thinking about {topic}?",
               "Hey {name}! How's {topic} going?"],
    "emotional": ["That sounds like a lot, {name}. Is it about {topic}?",
                  "I'm here, {name}. Tell me more about {topic}."],
    "inquiry": ["I don't know much about {topic} yet. Tell me about it?",
                "Good question about {topic}. What do you think?"],
    "sharing": ["{Topic} again? Tell me more!",
                "I like hearing about {topic}. What happened next?",
                "So {topic}. What's the best part?"],
    "agreement": ["Right, {topic}. Glad we're on the same page.",
                  "Exactly. {Topic} it is."],
    "disagreement": ["Fair enough. What would you change about {topic}?",
                     "Okay, I hear you on {topic}. What am I missing?"],
    "action": ["I'll keep {topic} in mind. What's the first step?",
               "Let's figure out {topic} together. Where do we start?"],
}

# Intents whose reply shape differs from the rest of their family.
INTENT_TOPIC_FRAMES = {
    "THANK": ["Anytime, {name}. I liked hearing about {topic}.",
              "You're welcome! Tell me more about {topic} sometime."],
    "APOLOGIZE": ["It's okay, {name}. We can come back to {topic} whenever.",
                  "No worries at all. Want to keep going with {topic}?"],
}

ASSOCIATION_FRAMES = {
    "inquiry": ["From what you've told me, {topic} goes with {assoc}.",
                "Last time {topic} came up, you mentioned {assoc}."],
    "default": ["Last time {topic} came up, you mentioned {assoc}. Is that part of it?",
                "{Topic} and {assoc} again! I remember that.",
                "That makes me think of {assoc}. You always bring it up with {topic}."],
}

GROUNDED_FRAMES = [
    "{Topic}! That reminds me of the {percept} I saw.",
    "When you say {topic}, I picture the {percept} from before.",
]

CURIOSITY_FRAMES = [
    "What's {word}? I haven't heard that one before.",
    "{Word}? Tell me what that is.",
    "I'm still learning. What does {word} mean to you?",
]


# ============================================================================
# HELPERS
# ============================================================================

def _tokens(text: str) -> List[str]:
    return re.findall(r"[a-z0-9']+", (text or "").lower())


def _cap(word: str) -> str:
    return word[:1].upper() + word[1:] if word else word


def _base_intents(intent: str) -> List[str]:
    """Resolve a hybrid intent (A_B_HYBRID) to its base intents."""
    if intent and intent.endswith("_HYBRID"):
        parts = intent[: -len("_HYBRID")].split("_")
        return [p for p in parts if p in INTENT_FAMILY] or ["INFORM"]
    return [intent or "INFORM"]


def _families(intent: str) -> List[str]:
    fams = []
    for base in _base_intents(intent):
        fam = INTENT_FAMILY.get(base, "sharing")
        if fam not in fams:
            fams.append(fam)
    return fams


def generalize_reply(text: str, slot_values: Dict[str, str],
                     other_learned: Optional[List[str]] = None) -> Optional[str]:
    """Turn a concrete reply into a reusable template.

    slot_values maps a slot name (topic, assoc, percept) to the learned word that
    filled it. Each word becomes its own slot, keeping a capital where the word was
    capitalised. Returns None when other learned words would stay baked in, since
    such a template only fits the conversation it came from.
    """
    template = text
    for slot, word in sorted(slot_values.items(), key=lambda kv: len(kv[1] or ""), reverse=True):
        if not word:
            continue
        def _slot(m, slot=slot):
            at_start = re.search(r"(^|[.!?]\s+)$", m.string[:m.start()]) is not None
            return "{" + (_cap(slot) if at_start else slot) + "}"
        template = re.sub(rf"\b{re.escape(word)}\b", _slot, template, flags=re.IGNORECASE)
    for word in other_learned or []:
        if word and re.search(rf"\b{re.escape(word)}\b", template, flags=re.IGNORECASE):
            return None
    template = re.sub(r"\b\d+\b", "{number}", template)
    return template


# ============================================================================
# 1. PER-AI VARIATION PROFILE
# ============================================================================

class AIVariationProfile:
    """
    Specialization pair + random ability multipliers + personality offsets.

    Drawn once per AI from a seed derived from its account id, then persisted,
    so the same companion keeps the same character across restarts while two
    different companions differ.
    """

    FILE_NAME = "variation_profile.json"

    def __init__(self, primary: SpecializationType, secondary: SpecializationType,
                 ability_multipliers: Dict[str, float],
                 personality_offsets: Dict[str, float], seed: str):
        self.primary = primary
        self.secondary = secondary
        self.ability_multipliers = ability_multipliers
        self.personality_offsets = personality_offsets
        self.seed = seed

    @classmethod
    def generate(cls, seed_source: str) -> "AIVariationProfile":
        seed = hashlib.sha256(f"agora-variation:{seed_source}".encode()).hexdigest()
        rng = random.Random(seed)
        roster = list(SpecializationType)
        primary = rng.choice(roster)
        secondary = rng.choice([s for s in roster if s != primary] or roster)
        multipliers = {d: round(rng.uniform(*ABILITY_MULTIPLIER_RANGE), 3) for d in LEARNING_DOMAINS}
        offsets = {t: round(rng.uniform(*PERSONALITY_OFFSET_RANGE), 3) for t in PERSONALITY_TRAITS}
        return cls(primary, secondary, multipliers, offsets, seed)

    @classmethod
    def load_or_create(cls, storage_dir: Path, seed_source: str) -> "AIVariationProfile":
        path = Path(storage_dir) / cls.FILE_NAME
        if path.exists():
            try:
                with open(path, "r") as f:
                    return cls.from_dict(json.load(f))
            except Exception as e:
                logger.error(f"[COMPOSER] Could not load variation profile, regenerating: {e}")
        profile = cls.generate(seed_source)
        profile.save(storage_dir)
        logger.info(f"[COMPOSER] New variation profile: {profile.primary.value}/"
                    f"{profile.secondary.value} multipliers={profile.ability_multipliers}")
        return profile

    def save(self, storage_dir: Path):
        try:
            Path(storage_dir).mkdir(parents=True, exist_ok=True)
            with open(Path(storage_dir) / self.FILE_NAME, "w") as f:
                json.dump(self.to_dict(), f, indent=2)
        except Exception as e:
            logger.error(f"[COMPOSER] Could not save variation profile: {e}")

    def specialization_profile(self) -> SpecializationProfile:
        return SpecializationProfile(primary=self.primary, secondary=self.secondary)

    def gain_vector(self) -> Dict[str, float]:
        """Specialization gains (60/40 blend) scaled by this AI's random multipliers."""
        base = self.specialization_profile().get_gain_vector()
        return {d: round(base.get(d, 1.0) * self.ability_multipliers.get(d, 1.0), 3)
                for d in LEARNING_DOMAINS}

    def apply_personality(self, voice_genome: Dict[str, float]) -> Dict[str, float]:
        """Return a copy of the voice genome nudged by this AI's personality offsets."""
        shaped = dict(voice_genome)
        for trait, offset in self.personality_offsets.items():
            if trait in shaped:
                shaped[trait] = max(0.0, min(1.0, shaped[trait] + offset))
        return shaped

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary": self.primary.value,
            "secondary": self.secondary.value,
            "ability_multipliers": self.ability_multipliers,
            "personality_offsets": self.personality_offsets,
            "seed": self.seed,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AIVariationProfile":
        return cls(
            SpecializationType(data["primary"]),
            SpecializationType(data["secondary"]),
            {d: float(v) for d, v in data.get("ability_multipliers", {}).items()},
            {t: float(v) for t, v in data.get("personality_offsets", {}).items()},
            data.get("seed", ""),
        )


# ============================================================================
# 2. CONVERSATIONAL MEMORY (associations + user phrasebook)
# ============================================================================

class ConversationalMemory:
    """
    What the companion remembers about how its user talks:
    - associations: which learned topic words come up together
    - phrasebook: the user's own short phrasings per intent (greetings, thanks...)
    - recent topics and recent outputs (for continuity and novelty)
    """

    FILE_NAME = "conversation_memory.json"

    def __init__(self):
        self.associations: Dict[str, Dict[str, float]] = defaultdict(dict)
        self.phrasebook: Dict[str, Dict[str, int]] = defaultdict(dict)
        self.recent_topics: deque = deque(maxlen=6)
        self.recent_outputs: deque = deque(maxlen=RECENT_OUTPUT_WINDOW)
        # word -> {"cap": n, "low": n}: how the user writes it mid-sentence
        self.surface_forms: Dict[str, Dict[str, int]] = defaultdict(dict)

    # -- surface forms ------------------------------------------------------
    def observe_surface(self, text: str):
        """Count capitalised vs lower-case use of each word away from sentence starts."""
        for sentence in re.split(r"[.!?]+\s*", text or ""):
            words = re.findall(r"[A-Za-z0-9']+", sentence)
            for w in words[1:]:
                if w.lower() == "i":
                    continue
                key = "cap" if w[:1].isupper() else "low"
                row = self.surface_forms[w.lower()]
                row[key] = row.get(key, 0) + 1

    def display(self, word: str) -> str:
        """The word as the user writes it (names stay capitalised)."""
        row = self.surface_forms.get(word, {})
        return _cap(word) if row.get("cap", 0) > row.get("low", 0) else word

    # -- associations -------------------------------------------------------
    def observe_topics(self, topics: List[str], lexical_gain: float = 1.0):
        seen = set()
        for i, a in enumerate(topics):
            for b in topics[i + 1:]:
                if a == b:
                    continue
                for x, y in ((a, b), (b, a)):
                    self.associations[x][y] = self.associations[x].get(y, 0.0) + lexical_gain
                    seen.add((x, y))
        # decay pairs not reinforced this turn
        for x in list(self.associations.keys()):
            row = self.associations[x]
            for y in list(row.keys()):
                if (x, y) not in seen:
                    row[y] *= ASSOCIATION_DECAY
                    if row[y] < 0.25:
                        del row[y]
            if len(row) > MAX_ASSOCIATIONS_PER_WORD:
                keep = sorted(row.items(), key=lambda kv: kv[1], reverse=True)[:MAX_ASSOCIATIONS_PER_WORD]
                self.associations[x] = dict(keep)
            if not self.associations[x]:
                del self.associations[x]
        for t in topics:
            if t in self.recent_topics:
                self.recent_topics.remove(t)
            self.recent_topics.append(t)

    def strongest_association(self, word: str, exclude: List[str]) -> Optional[Tuple[str, float]]:
        row = self.associations.get(word, {})
        best = [(w, s) for w, s in row.items() if w not in exclude and s >= ASSOCIATION_MIN_STRENGTH]
        if not best:
            return None
        return max(best, key=lambda kv: kv[1])

    # -- phrasebook ---------------------------------------------------------
    def observe_phrase(self, intent: str, text: str):
        words = _tokens(text)
        if not words or len(words) > PHRASE_MAX_WORDS:
            return
        phrase = text.strip()
        if not phrase:
            return
        book = self.phrasebook[intent]
        book[phrase] = book.get(phrase, 0) + 1

    def promoted_phrases(self, intent: str, voice_gain: float = 1.0) -> List[str]:
        needed = max(1, round(PHRASE_PROMOTION_COUNT / max(0.5, voice_gain)))
        return [p for p, n in self.phrasebook.get(intent, {}).items() if n >= needed]

    # -- persistence --------------------------------------------------------
    def to_dict(self) -> Dict[str, Any]:
        return {
            "associations": {k: dict(v) for k, v in self.associations.items()},
            "phrasebook": {k: dict(v) for k, v in self.phrasebook.items()},
            "recent_topics": list(self.recent_topics),
            "surface_forms": {k: dict(v) for k, v in self.surface_forms.items()},
        }

    def load(self, data: Dict[str, Any]):
        self.associations = defaultdict(dict, {k: dict(v) for k, v in data.get("associations", {}).items()})
        self.phrasebook = defaultdict(dict, {k: dict(v) for k, v in data.get("phrasebook", {}).items()})
        self.recent_topics = deque(data.get("recent_topics", []), maxlen=6)
        self.surface_forms = defaultdict(dict, {k: dict(v) for k, v in data.get("surface_forms", {}).items()})


# ============================================================================
# 3. THE COMPOSER
# ============================================================================

class Variant:
    __slots__ = ("move", "text", "weight", "coherence", "topic", "slots")

    def __init__(self, move: str, text: str, topic: str = "", slots: Optional[Dict[str, str]] = None):
        self.move, self.text, self.topic = move, text, topic
        self.slots = dict(slots or {})
        self.weight, self.coherence = 0.0, 0.0


class LearnedResponseComposer:
    """
    Builds the reply content from the companion's learned state.

    Wiring (set by OfflineAI):
        lexicon         - LexiconManager (stable lexemes, intent maps)
        evolution       - SelfGenerativeEvolution (template learner, groundings)
        audio           - AudioManager (phonetic lexemes from the user's voice)
        vision          - VisionManager (visual concepts) - optional
        seed_lines      - callable(intent, user_name) -> list of directed fallback lines
    """

    def __init__(self, storage_dir: str, seed_source: str, lexicon=None, evolution=None,
                 audio=None, vision=None,
                 seed_lines: Optional[Callable[[str, str], List[str]]] = None,
                 rng: Optional[random.Random] = None):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.lexicon = lexicon
        self.evolution = evolution
        self.audio = audio
        self.vision = vision
        self.seed_lines = seed_lines
        self.rng = rng or random.Random()

        self.profile = AIVariationProfile.load_or_create(self.storage_dir, seed_source)
        self.memory = ConversationalMemory()
        self.wisdom = ExpressionWisdomStore()
        self.move_fitness: Dict[str, float] = {m: 0.5 for m in MOVE_BASE_WEIGHT}
        self.generation = 0

        self._last: Optional[Dict[str, Any]] = None   # last chosen variant + context
        self._load_state()

    # ------------------------------------------------------------------
    # Learned-state readers
    # ------------------------------------------------------------------
    def lexical_maturity(self) -> float:
        if not self.lexicon:
            return 0.0
        content = [w for w in self.lexicon.entries if w not in FUNCTION_WORDS]
        return min(1.0, len(content) / LEXICAL_MATURITY_SATURATION)

    def _is_topic_word(self, word: str) -> bool:
        if len(word) < 3 or word in FUNCTION_WORDS or word.isdigit():
            return False
        if not self.lexicon or word not in self.lexicon.entries:
            return False
        entry = self.lexicon.entries[word]
        # Data-driven function-word test: spread evenly across many intents
        intents = [v for v in entry.intent_map.values() if v > 0]
        return not (len(intents) >= 5 and max(intents) < 0.35)

    def topics_in(self, text: str) -> List[str]:
        """Learned (stable) content words in the text, most salient first."""
        seen, topics = set(), []
        for w in _tokens(text):
            if w not in seen and self._is_topic_word(w):
                seen.add(w)
                topics.append(w)
        if not self.lexicon:
            return topics

        def salience(w):
            e = self.lexicon.entries[w]
            assoc = sum(self.memory.associations.get(w, {}).values())
            return e.frequency + 0.5 * assoc
        return sorted(topics, key=salience, reverse=True)

    def unknown_words(self, text: str) -> List[str]:
        if not self.lexicon:
            return []
        return [w for w in _tokens(text)
                if len(w) >= 4 and w not in FUNCTION_WORDS and not w.isdigit()
                and w not in self.lexicon.entries
                and self.lexicon.candidates.get(w) is not None
                and self.lexicon.candidates[w].occurrence_count <= 1]

    def grounded_percept(self, topic: str) -> Optional[str]:
        if not self.evolution:
            return None
        best, best_conf = None, 0.0
        for concept in getattr(self.evolution, "concepts", {}).values():
            if concept.lexeme == topic and concept.confidence > best_conf:
                best, best_conf = concept.percept, concept.confidence
        return best if best_conf >= 0.2 else None

    def learned_templates(self, intent: str) -> List[str]:
        if not self.evolution:
            return []
        out = []
        for base in [intent] + _base_intents(intent):
            out.extend(self.evolution.template_learner.get_templates(
                "language", f"{base}_{TEMPLATE_CATEGORY_SUFFIX}"))
        return list(dict.fromkeys(out))

    def user_phrases(self, intent: str) -> List[str]:
        gain = self.profile.gain_vector().get("voice", 1.0)
        phrases = []
        for base in _base_intents(intent):
            phrases.extend(self.memory.promoted_phrases(base, gain))
        # Phonetic lexemes learned from the user's voice carry their text forms
        if self.audio is not None:
            for lex in getattr(self.audio, "phonetic_lexemes", {}).values():
                if not lex.associated_text_forms or not lex.intent_histogram:
                    continue
                top_intent = max(lex.intent_histogram, key=lex.intent_histogram.get)
                if top_intent in _base_intents(intent) and lex.intent_histogram[top_intent] >= PHRASE_PROMOTION_COUNT:
                    phrases.extend(t for t in lex.associated_text_forms
                                   if 0 < len(_tokens(t)) <= PHRASE_MAX_WORDS)
        return list(dict.fromkeys(phrases))

    # ------------------------------------------------------------------
    # 1. Assembly
    # ------------------------------------------------------------------
    def _assemble(self, intent: str, user_text: str, user_name: str) -> List[Variant]:
        variants: List[Variant] = []
        fams = _families(intent)
        topics = self.topics_in(user_text)
        # Continuity: fall back to the most recent topic if this turn has none
        topic = topics[0] if topics else (self.memory.recent_topics[-1] if self.memory.recent_topics else "")
        slots = {"name": user_name or "friend"}
        shown = self.memory.display
        assoc = self.memory.strongest_association(topic, exclude=topics + [topic]) if topic else None
        percept = self.grounded_percept(topic) if topic else None

        def fill(frame: str, **extra) -> Optional[str]:
            values = dict(slots)
            for key, val in extra.items():
                values[key] = shown(val) if key in ("topic", "assoc", "word") else val
            for key in list(values.keys()):
                values[_cap(key)] = _cap(str(values[key]))
            try:
                text = frame.format(**values)
            except (KeyError, IndexError, ValueError):
                return None
            return None if "{" in text else text

        # learned_reply: templates learned from dialogue / successful turns
        learned_slots = {"topic": topic}
        if assoc:
            learned_slots["assoc"] = assoc[0]
        if percept:
            learned_slots["percept"] = percept.replace("_", " ")
        for tmpl in self.learned_templates(intent):
            if "{number}" in tmpl:
                continue
            if re.search(r"\{[Tt]opic\}", tmpl) and not topic:
                continue
            text = fill(tmpl, **learned_slots)
            if text:
                used = {k: v for k, v in learned_slots.items() if re.search(r"\{%s\}" % k, tmpl, re.IGNORECASE)}
                variants.append(Variant("learned_reply", re.sub(r"\s+", " ", text).strip(), topic, used))

        if topic:
            frame_sets = [INTENT_TOPIC_FRAMES[b] for b in _base_intents(intent) if b in INTENT_TOPIC_FRAMES]
            frame_sets = frame_sets or [TOPIC_FRAMES.get(fam, []) for fam in fams]
            for frames in frame_sets:
                for frame in frames:
                    text = fill(frame, topic=topic)
                    if text:
                        variants.append(Variant("topic_reflection", text, topic, {"topic": topic}))

            # Recall moves need this turn to be about the topic, not just the last one
            if assoc and topics:
                frames = ASSOCIATION_FRAMES["inquiry"] if "inquiry" in fams else ASSOCIATION_FRAMES["default"]
                for frame in frames:
                    text = fill(frame, topic=topic, assoc=assoc[0])
                    if text:
                        variants.append(Variant("association_recall", text, topic,
                                                {"topic": topic, "assoc": assoc[0]}))

            if percept and topics:
                for frame in GROUNDED_FRAMES:
                    text = fill(frame, topic=topic, percept=percept.replace("_", " "))
                    if text:
                        variants.append(Variant("grounded_recall", text, topic,
                                                {"topic": topic, "percept": percept.replace("_", " ")}))

        for phrase in self.user_phrases(intent):
            variants.append(Variant("user_phrase", phrase, topic))

        for word in self.unknown_words(user_text)[:2]:
            for frame in CURIOSITY_FRAMES:
                text = fill(frame, word=word)
                if text:
                    variants.append(Variant("curiosity_probe", text, word))

        if self.seed_lines:
            for line in self.seed_lines(_base_intents(intent)[0], slots["name"]):
                variants.append(Variant("seed_line", line, ""))

        return variants

    # ------------------------------------------------------------------
    # 3. Pressure evaluation (coherence first, spec 8.2)
    # ------------------------------------------------------------------
    def coherence(self, variant: Variant, user_text: str, affect_valence: float) -> float:
        text = variant.text
        words = _tokens(text)
        # lexical continuity: does the reply touch what the user said / the topic
        user_words = {w for w in _tokens(user_text) if w not in FUNCTION_WORDS}
        overlap = len(user_words & set(words))
        continuity = 1.0 if overlap else (0.7 if variant.topic else 0.45)
        # structure validity: basic grammar heuristics
        structure = 1.0
        if not text[:1].isupper():
            structure -= 0.25
        if text[-1:] not in ".!?":
            structure -= 0.25
        if not (2 <= len(words) <= 30):
            structure -= 0.4
        if re.search(r"\b(\w+) \1\b", text.lower()):
            structure -= 0.3
        # affect congruence: no cheerleading when the user is low
        congruence = 1.0
        if affect_valence < -0.2 and text.count("!") >= 1:
            congruence -= 0.4
        return max(0.0, min(1.0, 0.4 * continuity + 0.35 * structure + 0.25 * congruence))

    # ------------------------------------------------------------------
    # 2 + 4. Expression ecology shaped by the variation profile
    # ------------------------------------------------------------------
    def compose(self, intent: str, user_text: str, user_name: str = "friend",
                style: Optional[Dict[str, float]] = None,
                affect_valence: float = 0.0) -> Optional[str]:
        variants = self._assemble(intent, user_text, user_name)
        if not variants:
            return None

        gains = self.profile.gain_vector()
        maturity = self.lexical_maturity()
        # Spec 8.4: coherence weight high until lexical maturity reaches threshold
        if maturity < LEXICAL_MATURITY_THRESHOLD:
            coherence_power = 2.0
        else:
            coherence_power = 2.0 - (maturity - LEXICAL_MATURITY_THRESHOLD) / (1 - LEXICAL_MATURITY_THRESHOLD)
        curiosity = (style or {}).get("curiosity", 0.5)
        recent = set(self.memory.recent_outputs)

        for v in variants:
            lineage = f"{_base_intents(intent)[0]}:{v.move}"
            tone = self.wisdom.get_bias(lineage, "tone_bias")
            v.coherence = self.coherence(v, user_text, affect_valence)
            weight = MOVE_BASE_WEIGHT[v.move]
            weight *= gains.get(MOVE_DOMAIN[v.move], 1.0)
            weight *= 0.5 + self.move_fitness.get(v.move, 0.5)
            weight *= v.coherence ** coherence_power
            weight *= 1.0 + 0.3 * tone
            if v.move == "curiosity_probe":
                weight *= 0.5 + curiosity
                if any(f in ("social", "emotional") for f in _families(intent)):
                    weight *= 0.2
            if v.text in recent:
                weight *= 0.15          # novelty pressure
            v.weight = max(1e-6, weight)

        chosen = self.rng.choices(variants, weights=[v.weight for v in variants], k=1)[0]
        self._cull(intent, variants, chosen)
        self.generation += 1
        self.memory.recent_outputs.append(chosen.text)
        self._last = {"intent": intent, "move": chosen.move, "text": chosen.text,
                      "topic": chosen.topic, "slots": chosen.slots, "user_text": user_text}
        return chosen.text

    def _cull(self, intent: str, variants: List[Variant], chosen: Variant):
        """Distil the strongest losing lineages into wisdom shards (spec section 7)."""
        top = max(v.weight for v in variants)
        losers = {}
        for v in variants:
            if v is chosen:
                continue
            best = losers.get(v.move)
            if best is None or v.weight > best.weight:
                losers[v.move] = v
        for v in losers.values():
            fitness = v.weight / top if top else 0.0
            try:
                self.wisdom.add_shard(WisdomShard(
                    shard_id=f"ws_{self.generation}_{v.move}",
                    domain="lexical",
                    lineage_key=f"{_base_intents(intent)[0]}:{v.move}",
                    tone_bias=(fitness - 0.5) * 0.4,
                    structure_bias=(v.coherence - 0.5),
                    fitness_at_death=fitness,
                    cause_of_death="selection",
                    generation=self.generation,
                ))
            except Exception as e:
                logger.debug(f"[COMPOSER] Wisdom shard skipped: {e}")

    # ------------------------------------------------------------------
    # Learning hooks
    # ------------------------------------------------------------------
    def observe_user_turn(self, intent: str, user_text: str):
        """Learn from the user's turn. Also scores the previous reply implicitly."""
        if self._last is not None:
            self._last["implicit"] = self._implicit_satisfaction(intent, user_text)
            if self._last["implicit"] is not None:
                self.record_feedback(self._last["implicit"])
        gains = self.profile.gain_vector()
        self.memory.observe_surface(user_text)
        topics = self.topics_in(user_text)
        self.memory.observe_topics(topics, lexical_gain=gains.get("memory", 1.0))
        for base in _base_intents(intent):
            if INTENT_FAMILY.get(base) in ("social", "agreement", "emotional"):
                self.memory.observe_phrase(base, user_text)

    def _implicit_satisfaction(self, intent: str, user_text: str) -> Optional[float]:
        last = self._last or {}
        bases = _base_intents(intent)
        if any(b in ("CHALLENGE", "DENY") for b in bases) or re.search(r"\bwhat\?$|\bhuh\b|doesn't make sense", user_text.lower()):
            return 0.3
        topic = last.get("topic")
        if topic and topic in _tokens(user_text):
            return 0.75
        if len(_tokens(user_text)) >= 4:
            return 0.6
        return None

    def record_feedback(self, satisfaction: float):
        """Feedback on the last reply: adjusts move fitness and learns successful templates."""
        if not self._last:
            return
        move = self._last["move"]
        old = self.move_fitness.get(move, 0.5)
        self.move_fitness[move] = round(old + MOVE_FITNESS_LR * (satisfaction - old), 4)
        if (satisfaction >= TEMPLATE_SUCCESS_THRESHOLD and self.evolution
                and move not in ("seed_line", "curiosity_probe")):
            slot_values = dict(self._last.get("slots") or {})
            filled = set(slot_values.values())
            others = [w for w in self.topics_in(self._last.get("user_text", "")) if w not in filled]
            template = generalize_reply(self._last["text"], slot_values, others)
            if template and "{" in template:
                base = _base_intents(self._last["intent"])[0]
                self.evolution.template_learner.observe("language", f"{base}_{TEMPLATE_CATEGORY_SUFFIX}", template)
        self._last["feedback"] = satisfaction

    def ingest_dialogue_pair(self, user_intent: str, user_text: str, reply_text: str):
        """Corpus bootstrap: learn a reply template for the user's intent."""
        if not self.evolution or not reply_text:
            return
        words = _tokens(reply_text)
        if not (2 <= len(words) <= 30):
            return
        topics = self.topics_in(user_text)
        template = generalize_reply(reply_text.strip(), {"topic": topics[0]} if topics else {}, topics[1:])
        if not template:
            return
        self.evolution.template_learner.observe("language", f"{user_intent}_{TEMPLATE_CATEGORY_SUFFIX}", template)

    # ------------------------------------------------------------------
    # Persistence + introspection
    # ------------------------------------------------------------------
    def save_state(self):
        state = {
            "memory": self.memory.to_dict(),
            "move_fitness": self.move_fitness,
            "generation": self.generation,
            "wisdom": self.wisdom.to_dict(),
        }
        try:
            with open(self.storage_dir / ConversationalMemory.FILE_NAME, "w") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"[COMPOSER] Failed to save state: {e}")

    def _load_state(self):
        path = self.storage_dir / ConversationalMemory.FILE_NAME
        if not path.exists():
            return
        try:
            with open(path, "r") as f:
                state = json.load(f)
            self.memory.load(state.get("memory", {}))
            self.move_fitness.update(state.get("move_fitness", {}))
            self.generation = int(state.get("generation", 0))
            if state.get("wisdom"):
                self.wisdom = ExpressionWisdomStore.from_dict(state["wisdom"])
        except Exception as e:
            logger.error(f"[COMPOSER] Failed to load state: {e}")

    def get_stats(self) -> Dict[str, Any]:
        return {
            "specialization": f"{self.profile.primary.value}/{self.profile.secondary.value}",
            "gain_vector": self.profile.gain_vector(),
            "lexical_maturity": round(self.lexical_maturity(), 3),
            "associations": sum(len(v) for v in self.memory.associations.values()),
            "user_phrases": sum(len(v) for v in self.memory.phrasebook.values()),
            "move_fitness": dict(self.move_fitness),
            "wisdom_shards": self.wisdom.size,
            "generation": self.generation,
        }


__all__ = [
    "AIVariationProfile",
    "ConversationalMemory",
    "LearnedResponseComposer",
    "generalize_reply",
]
