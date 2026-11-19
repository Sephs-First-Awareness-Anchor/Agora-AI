# Agora: 52 birth configurations and live companion integration

This integration branch descends from Agora PR #2 (the learned-response
composer). The composer and its original tests remain included.

## The original A-Z onboarding contract

The original five-step onboarding chooses a name, favorite color,
introvert/extrovert behavior, user name, and birthday. The first character
of the AI name selects one of the 26 `BOOT_PERSONAS` through
`LETTER_PERSONA_MAP` (invalid letters use the original B fallback).
These personas retain their facial affect, intro sequence, and expressive
bias, regardless of behavioral mode.

The **same name-letter selection** determines a frozen specialization pair:
A-M select thirteen ordered primary/secondary pairs, and N-Z select the
same thirteen pairs with priorities reversed. Extrovert and introvert
settings yield 26 configurations each, totaling **52**.

The current thirteen base pairs form a fixed cyclic ring of the 13 existing
`SpecializationType` members. This explicit ring is the initial companion
pairing policy; the user-defined 13 pair meanings can be refined later,
but must be versioned rather than silently randomized.

## Variation and persistence

The first-boot account receives an `AIVariationProfile` with the pair
and mode chosen by onboarding. Its account-specific ability multipliers
and personality offsets are generated only once and persisted; the
birth pairing is deterministic but each individual's development is not.

Old profile files from PR #2 retain their ability multipliers, personality
offsets, and conversational learning data. On first verified onboarding
binding, the random legacy pair is replaced by the name-led pair. Further
unrequested changes to an already bound birth identity are ignored.

The capability manifest now records behavioral mode alongside primary/
secondary and includes it in the identity fingerprint.

## Integrated runtime

1. The original multistep onboarding calls `App.complete_onboarding` and
   stores the account/serial/profile. Returning users skip re-onboarding.
2. `App._activate_ai` constructs the name/mode/color user profile and
   passes it through the factory *before* the core initializes its composer.
3. The companion screen attaches the existing procedural face widget and
   holds one `OfflineAIRuntime`.
4. Typed input uses `runtime._process_text_input`; recognized speech uses
   the same runtime's ASR callback path.
5. `AIRuntimeUIAdapter.set_speaking` delivers actual response text to
   `CompanionScreen._show_speech`, populating the chat transcript.
6. The composer in PR #2 builds learned reply content and the existing
   `OfflineAI.generate_response` handles the rest of the learning loop.
7. Extroverted behavior is no longer erased when the cognitive autonomy
   governor clamps its autonomy limit. Runtime mode and intro persona persist.
8. A topical continuation can alter response selection fitness but cannot
   be treated as *explicit approval* for promoting a reply template.

## Pre-app validation

GitHub Actions runs `.github/workflows/agora-preapp.yml`, checking
Python compilation and the specialization, response-composer, original
Agora integration, and UI contract tests. Locally, with dependencies
installed:

```sh
python -m compileall -q app engine tests
xvfb-run -a python -m unittest -v \
  tests.test_response_composer tests.test_live_app_contract \
  tests.agora_integration_test
```

This is **not** a completed Android device test. Android-specific audio
permissions, ASR callbacks, background processing, TTS sequencing, face
animation and interaction latency require validation on physical hardware.

## Remaining product-level blockers

Authentication and license security remain prototype-level, so do not
treat successful engine/UI checks as approval for public distribution.
The runtime currently processes typed input on the Kivy event loop;
physical-device responsiveness and queueing need measured validation
before production deployment.
