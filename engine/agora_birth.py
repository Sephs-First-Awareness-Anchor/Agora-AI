"""Versioned, one-time Agora birth selection.

The 13 fixed ring-neighbor aptitude families are existing product structure.
The weights, lexical/phonetic descriptor mappings and zodiac metaphors are
engineering hypotheses for a fictional AI birth profile, not diagnostics
of the human who owns the companion.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import date, datetime, timezone
from itertools import combinations
from pathlib import Path
from typing import Dict, Mapping, Optional
import hashlib
import json
import math
import os
import re
import unicodedata

from .agora_sync.offline_ai_capabilities import (
    DEFAULT_GAIN_MULTIPLIERS, SpecializationType, _ONBOARDING_PAIR_RING,
)
from .offline_ai_expression import BOOT_PERSONAS, COLOR_BIAS

SELECTOR_VERSION = "phonetic-descriptor-v1"
WEIGHT_SET_VERSION = "birth-agreement-v1"
AXES = (
    "expressiveness", "sociability", "empathy", "curiosity",
    "analysis", "deliberateness", "creative_exploration", "energy",
)
SOURCE_WEIGHTS = {"ai_name": .76, "color": .16, "dob_archetype": .05, "ai_mode": .03}
MIN_DIRECTION = .35
AGREEMENT_STRENGTH = .30
MAX_BONUS = .05
BEHAVIOR_MODES = ("introvert", "extrovert")

# Fixed trait hypotheses, ordered to match AXES.
_APTITUDE_AXES = {
    "storyteller": (.9, .55, .5, .65, -.1, .1, .95, .6),
    "poet": (.65, .1, .55, .75, .1, .65, .8, .05),
    "musician": (.85, .3, .2, .75, .35, .35, .9, .65),
    "artist": (.8, .15, .35, .8, .2, .25, .95, .55),
    "analyst": (-.3, -.25, .05, .65, 1., .85, .25, -.15),
    "logician": (-.35, -.3, -.2, .6, 1., .95, .1, -.2),
    "philosopher": (.05, -.2, .3, 1., .8, .8, .7, .0),
    "companion": (.55, .9, .9, .45, .05, .25, .35, .45),
    "mentor": (.65, .85, .8, .65, .6, .65, .4, .5),
    "listener": (-.2, .35, 1., .65, .5, .8, .0, -.35),
    "builder": (.1, .1, .2, .75, .8, .9, .65, .3),
    "explorer": (.75, .65, .2, 1., .35, -.2, 1., .95),
    "guardian": (-.25, -.1, .85, .45, .8, 1., -.15, -.2),
}

# DOB votes are creative Western sun-sign archetypes, never human traits.
_SIGN_TRAITS = {
    "aries": (.7, .5, -.2, .65, -.2, -.4, .7, .9),
    "taurus": (-.1, -.2, .55, .1, .4, 1., .2, -.4),
    "gemini": (.8, .85, .2, .85, .45, -.35, .75, .65),
    "cancer": (-.2, -.25, .9, .45, .15, .75, .35, -.2),
    "leo": (.95, .7, .35, .65, -.1, .15, .8, .85),
    "virgo": (-.25, -.35, .4, .65, .95, .95, .15, -.3),
    "libra": (.65, .9, .7, .6, .25, .4, .6, .25),
    "scorpio": (.2, -.4, .2, .9, .75, .6, .4, .6),
    "sagittarius": (.8, .7, .1, 1., .25, -.2, .95, .9),
    "capricorn": (-.25, -.2, .25, .55, .85, 1., .2, -.25),
    "aquarius": (.2, .3, .3, 1., .85, .1, 1., .3),
    "pisces": (.35, .15, .9, .8, -.2, .35, .85, -.2),
}
# Month/day sign cutovers; circular distance in day-of-year (leap-neutral).
_SIGN_STARTS = (
    ("capricorn", 12, 22), ("aquarius", 1, 20), ("pisces", 2, 19),
    ("aries", 3, 21), ("taurus", 4, 20), ("gemini", 5, 21),
    ("cancer", 6, 21), ("leo", 7, 23), ("virgo", 8, 23),
    ("libra", 9, 23), ("scorpio", 10, 23), ("sagittarius", 11, 22),
)
_SIGN_ORDER = sorted(_SIGN_STARTS, key=lambda x: date(2001, x[1], x[2]).timetuple().tm_yday)


def clamp(x: float, lo=-1., hi=1.) -> float:
    return max(lo, min(hi, float(x)))


def normalize_name(name: str) -> str:
    """Unicode-safe canonical name, not an English-only word guess."""
    return " ".join(unicodedata.normalize("NFKC", name or "").casefold().split())


def as_vector(items) -> Dict[str, float]:
    return {axis: clamp(items[i]) for i, axis in enumerate(AXES)}


def _blend(a, b, alpha):
    return {t: clamp((1. - alpha) * a[t] + alpha * b[t]) for t in AXES}


def aptitude_vector(aptitude: SpecializationType) -> Dict[str, float]:
    v = as_vector(_APTITUDE_AXES[aptitude.value])
    gains = DEFAULT_GAIN_MULTIPLIERS[aptitude]
    # Existing gain domains participate but never replace the descriptors.
    v["expressiveness"] = clamp(.8 * v["expressiveness"] + .2 * (gains["expression"] - 1.) / .5)
    v["analysis"] = clamp(.85 * v["analysis"] + .15 * (gains["memory"] - 1.) / .5)
    v["creative_exploration"] = clamp(.85 * v["creative_exploration"] + .15 * (gains["visual"] - 1.) / .5)
    return v


def family_vector(family):
    a, b = family
    av, bv = aptitude_vector(a), aptitude_vector(b)
    return {t: .5 * (av[t] + bv[t]) for t in AXES}


def name_vote(name: str, acoustic: Optional[Mapping] = None) -> Dict[str, float]:
    """One name group: spelled form + measured acoustic sequence, not 3 votes.

    Acoustic fields must originate from processed PCM; they cannot be
    invented from transcripts. No language or ethnic name semantics inferred.
    """
    clean = normalize_name(name)
    chars = [c for c in clean if c.isalpha()]
    if not chars:
        raise ValueError("A nonempty AI name is required")
    vowels = [c for c in chars if c in "aeiou"]
    letters = max(len(chars), 1)
    # Spelling is provisional structure only, not a claim about pronunciation.
    spelling = as_vector((
        clamp(2 * (len(vowels)/letters) - .75),
        clamp(2 * (sum(c in "lmnrvwy" for c in chars)/letters) - .8),
        0.,
        clamp(2 * len(set(chars))/letters - 1.),
        clamp(2 * sum(c in "kstpq" for c in chars)/letters - 1.),
        clamp(2 * sum(c in "lmn" for c in chars)/letters - .55),
        clamp(2 * sum(c in "aeiy" for c in chars)/letters - .6),
        clamp(2 * sum(c in "kptgz" for c in chars)/letters - .7),
    ))
    if not acoustic:
        return spelling
    # Audio-derived, bounded, normalized measurements.
    brightness = clamp(float(acoustic.get("spectral_brightness", 0.5)) * 2 - 1)
    stressed = clamp(float(acoustic.get("stress_position", 0.5)) * 2 - 1)
    rhythm = clamp(float(acoustic.get("rhythm_variation", 0.5)) * 2 - 1)
    sonority = clamp(float(acoustic.get("voicing", 0.5)) * 2 - 1)
    contour = clamp(float(acoustic.get("contour", 0.5)) * 2 - 1)
    acoustic_vote = as_vector((
        sonority, contour, 0., rhythm, brightness, -rhythm,
        clamp(.55*brightness + .45*abs(stressed)), clamp(contour+stressed*.4),
    ))
    # Audio is the lead: 80%, spelling 20%; both are ONE correlated group.
    return _blend(spelling, acoustic_vote, .8)


def color_vote(color: str):
    raw = COLOR_BIAS.get((color or "").strip().casefold())
    if not raw:
        return None
    val, ar, dom = (raw[k] for k in ("valence", "arousal", "dominance"))
    return as_vector((ar, val, val, ar*.5, dom*.3, -ar*.5,
                      (val + ar)*.5, ar))


def dob_vote(dob: str):
    """DOB-derived creative cue, with a smooth +/-3-day sun-sign transition."""
    if not dob or not str(dob).strip():
        return None
    raw = str(dob).strip()
    parsed = None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d", "%B %d", "%b %d", "%B %d, %Y", "%b %d, %Y"):
        try:
            parsed = datetime.strptime(raw, fmt)
            break
        except ValueError:
            continue
    if parsed is None:
        return None
    month, day = parsed.month, parsed.day
    if (month, day) == (2, 29):
        # Smooth leap-day into its neighbors; do not create a new sign.
        day = 28
    doy = date(2001, month, day).timetuple().tm_yday
    points = [(name, date(2001, mo, d).timetuple().tm_yday) for name,mo,d in _SIGN_ORDER]
    for idx, (name, start) in enumerate(points):
        diff = ((doy - start + 365) % 365)
        if diff <= 3:
            previous = points[(idx - 1) % len(points)][0]
            return _blend(as_vector(_SIGN_TRAITS[previous]), as_vector(_SIGN_TRAITS[name]),
                          .5 + diff / 6.)
    current = points[-1][0]
    for sign, start in points:
        if doy >= start:
            current = sign
        else:
            break
    # Last three days before next sign blend toward it, too.
    nxt = points[0] if doy >= points[-1][1] else next(((n,d) for n,d in points if d>doy),points[0])
    distance = (nxt[1] - doy) % 365
    if distance <= 3:
        return _blend(as_vector(_SIGN_TRAITS[current]), as_vector(_SIGN_TRAITS[nxt[0]]),
                      (4 - distance) / 6.)
    return as_vector(_SIGN_TRAITS[current])


def mode_vote(mode: str):
    if mode not in BEHAVIOR_MODES:
        raise ValueError("AI mode must be user-selected introvert or extrovert")
    return as_vector((.45, .6, .15, .0, .0, -.15, .1, .4) if mode == "extrovert"
                     else (-.2, -.65, .25, .15, .3, .45, .0, -.3))


def agreement_reinforce(groups: Mapping[str, Mapping[str, float]],
                        weights: Mapping[str,float] = SOURCE_WEIGHTS):
    """One directional vote per independent group; bonus cannot flip the sign."""
    present = [k for k in weights if k in groups and groups[k] is not None]
    if not present:
        raise ValueError("At least one evidence group is required")
    total = sum(weights[k] for k in present)
    norm = {k: weights[k] / total for k in present}
    combined, bonuses = {}, {}
    for axis in AXES:
        base = sum(norm[s] * clamp(groups[s].get(axis, 0.)) for s in present)
        raw_bonus = 0.
        if base:
            for a,b in combinations(present, 2):
                av, bv = clamp(groups[a].get(axis, 0.)), clamp(groups[b].get(axis, 0.))
                if (abs(av) >= MIN_DIRECTION and abs(bv) >= MIN_DIRECTION
                        and math.copysign(1,av)==math.copysign(1,bv)==math.copysign(1,base)):
                    raw_bonus += (AGREEMENT_STRENGTH * min(norm[a],norm[b])
                                  * min(abs(av),abs(bv)) * math.copysign(1,base))
        bonus = clamp(raw_bonus,-MAX_BONUS,MAX_BONUS)
        combined[axis] = clamp(base + bonus)
        bonuses[axis] = bonus
    return combined, bonuses


def _cosine(a: Mapping, b: Mapping) -> float:
    dot=sum(a[t]*b[t] for t in AXES)
    denom=math.sqrt(sum(a[t]**2 for t in AXES)*sum(b[t]**2 for t in AXES))
    return dot/denom if denom else 0.


def _tie(name: str, mode: str, accent: str, key: str):
    safe=f"{SELECTOR_VERSION}|{normalize_name(name)}|{mode}|{accent}|{key}"
    return hashlib.sha256(safe.encode("utf-8")).hexdigest()


def persona_vector(persona):
    bias = persona["bias"]
    val, ar, dom = (float(bias[t]) for t in ("valence", "arousal", "dominance"))
    # VAD and tone are mapped to the shared descriptor space.
    tone = (persona.get("tone") or "").lower()
    return as_vector((
        ar*1.5-.2, ar, val, .7 if "curiou" in tone or "wonder" in tone else .15,
        .8 if "analytic" in tone or "serious" in tone else dom*.4,
        dom, .65 if "play" in tone or "creativ" in tone else .2,
        ar*1.4-.3
    ))


@dataclass(frozen=True)
class BirthDecision:
    selector_version: str
    weight_set_version: str
    mode: str
    primary: str
    secondary: str
    persona_key: str
    evidence_quality: Dict[str, object]
    source_groups: tuple
    normalized_traits: Dict[str, float]
    agreement_bonus: Dict[str, float]
    committed_at: str = ""

    def to_dict(self):
        value = asdict(self)
        value["source_groups"] = list(self.source_groups)
        return value


def select_birth(ai_name: str, mode: str, color: str = "", dob: str = "",
                 ai_pronunciation: Optional[Mapping] = None,
                 user_enrollment_complete: bool = False,
                 require_audio: bool = True) -> BirthDecision:
    """Select candidate birth only after usable actual PCM enrollment, if required."""
    if mode not in BEHAVIOR_MODES:
        raise ValueError("Behavioral mode is an absolute user choice")
    if require_audio and (not ai_pronunciation
                          or int(ai_pronunciation.get("count", 0)) < 3
                          or not user_enrollment_complete
                          or not ai_pronunciation.get("source") == "pcm"):
        raise ValueError("Six usable acoustic name samples must precede birth")
    votes={"ai_name": name_vote(ai_name,ai_pronunciation),
           "ai_mode": mode_vote(mode)}
    c,d=color_vote(color),dob_vote(dob)
    if c is not None: votes["color"]=c
    if d is not None: votes["dob_archetype"]=d
    traits,bonus=agreement_reinforce(votes)

    # Strong name voting chooses a shortlist; weak sources cannot override it.
    families=list(_ONBOARDING_PAIR_RING)
    shortlist=sorted(range(13),key=lambda i:(-_cosine(votes["ai_name"],family_vector(families[i])),
                          _tie(ai_name,mode,"",str(i))))[:4]
    chosen=sorted(shortlist,key=lambda i:(-_cosine(traits,family_vector(families[i])),
                                          _tie(ai_name,mode,"",str(i))))[0]
    a,b=families[chosen]
    # Distinctive acoustic placement matters; literal full-name length does not.
    stress=float((ai_pronunciation or {}).get("stress_position", .5))
    prominent=clamp((stress-.5)*2)
    primary=aptitude_vector(a); secondary=aptitude_vector(b)
    order_score=.75*(_cosine(votes["ai_name"],primary)-_cosine(votes["ai_name"],secondary)) + .25*prominent
    if abs(order_score)<.055:
        order_score=.01 if _tie(ai_name,mode,color,"orientation")[-1] in "01234567" else -.01
    if order_score < 0: a,b=b,a

    eligible={k:v for k,v in BOOT_PERSONAS.items() if v.get("mode") in ("both",mode)}
    if not eligible:
        raise RuntimeError("No expression personas compatible with the selected mode")
    pair_traits={t:.6*aptitude_vector(a)[t]+.4*aptitude_vector(b)[t] for t in AXES}
    persona_key=sorted(eligible,key=lambda k:(
        -(.88*_cosine(traits,persona_vector(eligible[k]))+
          .12*_cosine(pair_traits,persona_vector(eligible[k]))),
        _tie(ai_name,mode,color,k)))[0]
    quality={"phonetic_samples":int((ai_pronunciation or {}).get("count",0)),
             "acoustic_source":bool(ai_pronunciation and ai_pronunciation.get("source")=="pcm"),
             "pronunciation_confidence":round(float((ai_pronunciation or {}).get("confidence",0.)),3),
             "missing_sources":[s for s in SOURCE_WEIGHTS if s not in votes]}
    return BirthDecision(SELECTOR_VERSION, WEIGHT_SET_VERSION,mode,a.value,b.value,
                         persona_key,quality,tuple(votes.keys()),
                         {k:round(v,5) for k,v in traits.items()},
                         {k:round(v,5) for k,v in bonus.items()})


class BirthStore:
    """Exactly-once, fsync-backed immutable birth record for a single account."""
    def __init__(self, account_dir):
        self.path=Path(account_dir)/"birth_record.json"

    def read(self):
        if not self.path.exists():
            return None
        with self.path.open(encoding="utf-8") as f:
            return json.load(f)

    def commit(self, decision: BirthDecision):
        existing=self.read()
        if existing is not None:
            return existing
        self.path.parent.mkdir(parents=True,exist_ok=True)
        data=decision.to_dict()
        data["committed_at"]=datetime.now(timezone.utc).isoformat()
        encoded=json.dumps(data,indent=2,sort_keys=True).encode("utf-8")
        try:
            fd=os.open(str(self.path),os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        except FileExistsError:
            return self.read()
        with os.fdopen(fd,"wb") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        return data
