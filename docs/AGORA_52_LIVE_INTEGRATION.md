# Agora unified birth and voice enrollment: pre-APK implementation

**Architecture directive:** `AGORA_UNIFIED_BIRTH_AND_VOICE_IMPLEMENTATION_DIRECTIVE.md`
supplied 18 November 2026. PR #3 includes PR #2's learned-response composer
and the original live onboarding/companion repair.

## Product behavior

The 13 existing specialization aptitudes and their 13 ring-neighbor
**unordered** pair families remain canonical. Each family permits the
60/40 and 40/60 orientation, and the user's explicitly selected AI mode
(introvert or extrovert) provides **52** potential birth configurations.

The 26 `BOOT_PERSONAS` are a *separate* expressive dimension. They are
ranked for trait coherence **only within their actual metadata mode**.
Seventeen are introvert-eligible and twenty-four extrovert-eligible.
Personas are not a false A–Z equivalent of the 26 ordered specialization
pairs.

The original first-letter selector remains only as a **legacy compatibility
helper**. New birth uses `engine/agora_birth.py`, with a documented
eight-axis trait vector and constrained shortlist/ordered-pair/persona
choice. Candidate group weights are:
AI name .76, color .16, optional DOB archetype .05, optional mode-soft
preference .03. When an optional group is absent, the remaining weights
are normalized. Same-source phonetic measurements are never counted as
independent agreement votes. An explicit capped +/- .05 directional
bonus reinforces actual cross-group agreement. The mode itself is a hard
user selection; the soft mode vote cannot change it. The DOB group is a
weak *creative archetype*, not evidence of human personality.

The 13 ring pairs are still the existing provisional neighboring-aptitude
families. The new selector chooses among those families from the
measured name cues and other independently supplied evidence; it does
not choose an arbitrary partner from all 13x12 combinations.

## Mandatory enrollment before birth

1. User supplies two **distinct typed names**: their own for address/speaker
   enrollment, and the AI's for one-time birth selection. Also supplies
   the existing favorite color, AI mode, and optional DOB.
2. The app stores `PENDING_ENROLLMENT` before account creation. It then
   requires **three usable PCM takes of the user's name and three of the
   AI's name**, in that order, using `NameEnrollmentScreen`.
3. `AudioEngine.capture_name_pcm` temporarily owns exclusive Android
   `AudioRecord` capture for each short segment, off the UI thread. The
   same audio engine instance is handed to `OfflineAIRuntime` after
   birth. No second continuous microphone loop is created.
4. `engine/agora_enrollment.py` processes local PCM16 with numeric
   RMS/voicing, spectral, stress-location and rhythm measures. Raw PCM
   is discarded; only necessary feature records are persisted. Silence,
   too-short segments, and invalid PCM cannot count as enrollment.
5. Six accepted takes produce one pronunciation consensus per name and
   a conservative, **provisional** speaker feature reference. Three
   repetitions of one name are still one correlated source for birth.
6. `BirthStore.commit` makes a complete, fsynced and atomically linked,
   exactly-once `birth_record.json` per account. The account ID is
   first checkpointed to the pending file to enable interrupted-onboarding
   recovery. Repeating completion cannot replace a saved birth.
7. Only then does `app/main.py` activate the AI and pass the birth record
   to the language-composer and intro-persona paths. New core
   initialization with onboarding identity but no committed birth is
   rejected.
8. Old accounts are explicitly distinguished as `LEGACY_EXISTING`; their
   existing variation state is **not automatically reassigned** based on
   updated names or pronunciation.

## Identity and learning separation

- `birth_record.json`: fixed pair, orientation, mode, expression persona,
  selector version, weights version, source quality and limited trait
  provenance. No birth recalculation after creation.
- `composer/variation_profile.json`: original PR #2's seeded individual
  ability multipliers, offsets and continued learned responses. This
  consumes a committed pair for new accounts and preserves saved state.
- `voice_learning.json`: independently mutable user-name and AI-name
  pronunciation candidates and provisional speaker embeddings. The
  companion UI exposes a confirmed local deletion action that does not
  modify birth or learned conversation history.
- Android `SpeechRecognizer` returns text, not guaranteed PCM. The
  runtime no longer manufactures speaker fingerprints from the clock
  or prosody/phonetics from text hashes. In transcript-only sessions,
  voice identification **abstains** rather than fabricating evidence.

## Validation already possible without a phone

`python -m compileall -q app engine tests`

```sh
xvfb-run -a python -m unittest -v \
  tests.test_response_composer \
  tests.test_live_app_contract \
  tests.test_live_screens \
  tests.test_real_engine_smoke \
  tests.test_unified_birth \
  tests.agora_integration_test
```

The GitHub `agora-preapp.yml` workflow executes the suites automatically.
A synthetic PCM waveform in tests proves feature computation and persistence
contracts, **not** a successful Android capture or reliable voice recognition.

## Unresolved gates before app testing or production claims

1. **Android hardware PCM:** exercise real permissions, `AudioRecord`
   initialization and timely release, repeated recording quality,
   background noise, different accents, phone orientation and relaunch.
   Verify sample rate, byte order, UI thread safety and actual waveform.
2. **Phonetic fidelity:** current PCM features are measured acoustic
   *proxies*, not verified phoneme transcription, accent-sensitive
   alignment or a linguistically calibrated pronunciation recognizer.
   Test and improve stressed sounds/segment alignment with actual names
   before declaring that part complete.
3. **Speaker identity:** six short name utterances only seed a provisional
   reference. API supports local abstention and consented other-speaker
   enrollment, but live voice recognition, known-other rejection metrics,
   false acceptance/rejection and continuous acoustic update have **not**
   been validated. ASR's text-only callback cannot supply those signals.
   Voice confidence never authorizes privileged operations.
4. **Personality inference:** the descriptor map, weights, DOB archetypes,
   and agreement bonus are versioned engineering hypotheses. Quantify
   assignment stability, 13-family reachability across diverse names,
   boundary cases, and cultural/language bias. Do not label personality
   predictions scientifically measured.
5. **End-to-end device lifecycle:** verify the 6-take UI, restart between
   captures, one-time birth, actual face intro, learned replies, and
   no UI stalls in real Android operation.
6. **Production security:** existing prototype authentication/licensing
   requires a separate security pass before public distribution.

**PR #3 stays draft.** Passing software tests make it reviewable; they
do not establish the hardware and acoustic acceptance gates above.
