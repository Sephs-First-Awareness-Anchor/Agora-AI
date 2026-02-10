#!/usr/bin/env python3
"""
Pretrained Library Loader
=========================
Loads compressed pretrained data from pretrained_library/ into AI managers.

This module handles first-boot loading of pretrained:
- Lexicon (language understanding)
- Audio (phonetic patterns, voice templates, sound concepts)
- Vision (visual percepts, concepts)

The pretrained data was created through training exposure and compressed
into ≤25MB gzip modules for distribution with the APK.
"""

import os
import json
import gzip
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Find the pretrained library relative to this file
SCRIPT_DIR = Path(__file__).parent
DEFAULT_LIBRARY_PATH = SCRIPT_DIR / "pretrained_library"


def get_library_path() -> Optional[Path]:
    """Get path to pretrained library, checking multiple locations."""
    # Check relative to script (bundled with app)
    if DEFAULT_LIBRARY_PATH.exists():
        return DEFAULT_LIBRARY_PATH

    # Check current working directory
    cwd_path = Path.cwd() / "pretrained_library"
    if cwd_path.exists():
        return cwd_path

    return None


def decompress_module(module_path: Path) -> Optional[Dict[str, Any]]:
    """Decompress a gzip module and return the data."""
    try:
        data_file = module_path / "data.json.gz"
        if not data_file.exists():
            # Check for chunks
            chunks = list(module_path.glob("chunk_*.json.gz"))
            if chunks:
                # Merge chunks
                merged = {"entries": {}, "candidates": {}}
                for chunk_file in sorted(chunks):
                    with gzip.open(chunk_file, 'rt', encoding='utf-8') as f:
                        chunk_data = json.load(f)
                    if "entries" in chunk_data:
                        merged["entries"].update(chunk_data["entries"])
                    if "candidates" in chunk_data:
                        merged["candidates"].update(chunk_data["candidates"])
                    # Also merge other keys
                    for key in chunk_data:
                        if key not in ["entries", "candidates"]:
                            merged[key] = chunk_data[key]
                return merged
            return None

        with gzip.open(data_file, 'rt', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[PRETRAINED] Failed to decompress {module_path}: {e}")
        return None


def load_library_manifest(library_path: Path) -> Optional[Dict[str, Any]]:
    """Load the library manifest."""
    manifest_path = library_path / "library_manifest.json"
    if not manifest_path.exists():
        return None

    try:
        with open(manifest_path, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"[PRETRAINED] Failed to load manifest: {e}")
        return None


def load_pretrained_lexicon(library_path: Path = None) -> Optional[Dict[str, Any]]:
    """
    Load pretrained lexicon data.

    Returns dict with 'candidates' and 'entries' keys.
    """
    if library_path is None:
        library_path = get_library_path()

    if not library_path:
        logger.info("[PRETRAINED] No pretrained library found")
        return None

    # Find lexicon modules (prefer the larger pretrained_base one)
    lexicon_modules = [
        library_path / "language" / "pretrained_base_lexicon_state",
        library_path / "language" / "chatgpt_pretrained_lexicon_state",
    ]

    merged = {"entries": {}, "candidates": {}}
    loaded_count = 0

    for module_path in lexicon_modules:
        if module_path.exists():
            data = decompress_module(module_path)
            if data:
                # Merge entries (pretrained_base takes precedence)
                if "entries" in data:
                    for word, entry in data["entries"].items():
                        if word not in merged["entries"]:
                            merged["entries"][word] = entry

                # Merge candidates
                if "candidates" in data:
                    for word, candidate in data["candidates"].items():
                        if word not in merged["candidates"]:
                            merged["candidates"][word] = candidate

                loaded_count += 1
                logger.info(f"[PRETRAINED] Loaded lexicon from {module_path.name}: "
                           f"{len(data.get('entries', {}))} entries, "
                           f"{len(data.get('candidates', {}))} candidates")

    if loaded_count == 0:
        return None

    logger.info(f"[PRETRAINED] Total lexicon: {len(merged['entries'])} entries, "
               f"{len(merged['candidates'])} candidates")
    return merged


def load_pretrained_audio(library_path: Path = None) -> Dict[str, Any]:
    """
    Load pretrained audio data.

    Returns dict with audio state, sound concepts, voice profiles.
    """
    if library_path is None:
        library_path = get_library_path()

    if not library_path:
        return {}

    result = {}

    # Audio state
    audio_state_path = library_path / "audio" / "pretrained_base_audio_state"
    if audio_state_path.exists():
        data = decompress_module(audio_state_path)
        if data:
            result["audio_state"] = data
            logger.info(f"[PRETRAINED] Loaded audio state")

    # Sound concept state
    sound_path = library_path / "audio" / "pretrained_base_sound_concept_state"
    if sound_path.exists():
        data = decompress_module(sound_path)
        if data:
            result["sound_concepts"] = data
            logger.info(f"[PRETRAINED] Loaded sound concepts: "
                       f"{len(data.get('concepts', {}))} concepts")

    # Voice profiles
    voice_path = library_path / "audio" / "pretrained_base_voice_profiles"
    if voice_path.exists():
        data = decompress_module(voice_path)
        if data:
            result["voice_profiles"] = data
            logger.info(f"[PRETRAINED] Loaded voice profiles: "
                       f"{len(data.get('profiles', {}))} profiles")

    return result


def load_pretrained_vision(library_path: Path = None) -> Optional[Dict[str, Any]]:
    """
    Load pretrained vision data.

    Returns dict with visual percepts and concepts.
    """
    if library_path is None:
        library_path = get_library_path()

    if not library_path:
        return None

    # Vision modules would be in library_path / "vision" / ...
    # Currently we don't have vision pretrained data, but structure is ready
    vision_path = library_path / "vision"
    if not vision_path.exists():
        return None

    # Future: load vision modules similar to lexicon/audio
    return None


def inject_pretrained_into_lexicon(lexicon_manager, pretrained_data: Dict[str, Any]):
    """
    Inject pretrained data into a LexiconManager instance.

    Only injects if the manager is empty (first boot).
    """
    if not pretrained_data:
        return False

    # Check if lexicon is empty (only base anchors)
    if len(lexicon_manager.entries) > 50:  # More than base anchors
        logger.info("[PRETRAINED] Lexicon already has data, skipping injection")
        return False

    # Import the classes needed for reconstruction
    from offline_ai_expression import LexemeEntry, LexicalCandidate

    injected_entries = 0
    injected_candidates = 0

    # Inject entries
    for word, entry_data in pretrained_data.get("entries", {}).items():
        if word not in lexicon_manager.entries:
            try:
                lexicon_manager.entries[word] = LexemeEntry.from_dict(entry_data)
                injected_entries += 1
            except Exception as e:
                logger.warning(f"[PRETRAINED] Failed to inject entry '{word}': {e}")

    # Inject candidates
    for word, cand_data in pretrained_data.get("candidates", {}).items():
        if word not in lexicon_manager.candidates:
            try:
                lexicon_manager.candidates[word] = LexicalCandidate.from_dict(cand_data)
                injected_candidates += 1
            except Exception as e:
                logger.warning(f"[PRETRAINED] Failed to inject candidate '{word}': {e}")

    logger.info(f"[PRETRAINED] Injected {injected_entries} entries, "
               f"{injected_candidates} candidates into lexicon")

    # Save the injected state
    lexicon_manager.save_state()

    return True


def inject_pretrained_into_audio(audio_manager, pretrained_data: Dict[str, Any]):
    """
    Inject pretrained audio data into AudioManager instance.
    """
    if not pretrained_data:
        return False

    from offline_ai_expression import (
        AudioPerceptTemplate, PhoneticLexemeTemplate,
        VoiceIntentTemplate, PhoneticMemory
    )

    injected = False

    # Audio state (percepts, phonetic_lexemes, voice_templates)
    audio_state = pretrained_data.get("audio_state", {})
    if audio_state:
        for k, v in audio_state.get("percepts", {}).items():
            if k not in audio_manager.percepts:
                try:
                    audio_manager.percepts[k] = AudioPerceptTemplate.from_dict(v)
                    injected = True
                except:
                    pass

        for k, v in audio_state.get("phonetic_lexemes", {}).items():
            if k not in audio_manager.phonetic_lexemes:
                try:
                    audio_manager.phonetic_lexemes[k] = PhoneticLexemeTemplate.from_dict(v)
                    injected = True
                except:
                    pass

        for k, v in audio_state.get("voice_templates", {}).items():
            if k not in audio_manager.voice_templates:
                try:
                    audio_manager.voice_templates[k] = VoiceIntentTemplate.from_dict(v)
                    injected = True
                except:
                    pass

        if "phonetic_memory" in audio_state:
            try:
                audio_manager.phonetic_memory = PhoneticMemory.from_dict(
                    audio_state["phonetic_memory"]
                )
                injected = True
            except:
                pass

    # Sound concepts
    sound_data = pretrained_data.get("sound_concepts", {})
    if sound_data and hasattr(audio_manager, 'sound_concept_memory'):
        scm = audio_manager.sound_concept_memory
        for concept_id, concept_data in sound_data.get("concepts", {}).items():
            if concept_id not in scm.concepts:
                scm.concepts[concept_id] = concept_data
                injected = True

        for grounding in sound_data.get("groundings", []):
            if grounding not in scm.groundings:
                scm.groundings.append(grounding)
                injected = True

    if injected:
        logger.info("[PRETRAINED] Injected pretrained audio data")
        audio_manager.save_state()

    return injected


def load_all_pretrained(ai_instance):
    """
    Load all pretrained data into an AI instance.

    Call this during AI initialization when the account is new.

    Args:
        ai_instance: The OfflineAI instance to inject into
    """
    library_path = get_library_path()
    if not library_path:
        logger.info("[PRETRAINED] No pretrained library available")
        return False

    logger.info(f"[PRETRAINED] Loading from {library_path}")

    loaded_any = False

    # Load and inject lexicon
    if hasattr(ai_instance, 'lexicon') and ai_instance.lexicon:
        lexicon_data = load_pretrained_lexicon(library_path)
        if lexicon_data:
            if inject_pretrained_into_lexicon(ai_instance.lexicon, lexicon_data):
                loaded_any = True

    # Load and inject audio
    if hasattr(ai_instance, 'audio') and ai_instance.audio:
        audio_data = load_pretrained_audio(library_path)
        if audio_data:
            if inject_pretrained_into_audio(ai_instance.audio, audio_data):
                loaded_any = True

    # Vision (future)
    # vision_data = load_pretrained_vision(library_path)
    # if vision_data and hasattr(ai_instance, 'vision'):
    #     inject_pretrained_into_vision(ai_instance.vision, vision_data)

    if loaded_any:
        logger.info("[PRETRAINED] Successfully loaded pretrained data")

    return loaded_any


# Quick test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("Testing pretrained loader...")

    library_path = get_library_path()
    print(f"Library path: {library_path}")

    if library_path:
        manifest = load_library_manifest(library_path)
        print(f"Manifest: {manifest}")

        lexicon = load_pretrained_lexicon(library_path)
        if lexicon:
            print(f"Lexicon entries: {len(lexicon.get('entries', {}))}")
            print(f"Lexicon candidates: {len(lexicon.get('candidates', {}))}")

        audio = load_pretrained_audio(library_path)
        print(f"Audio data keys: {audio.keys()}")
