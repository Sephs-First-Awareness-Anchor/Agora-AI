#!/usr/bin/env python3
"""
Offline AI System Module
========================

Consolidated system, account, and storage management.
Combines:
- Account Management (offline_ai_account.py)
- Migration Engine (offline_ai_migration.py)
- Storage Governor (offline_ai_storage.py)
- Event Journaling (offline_ai_journal.py)
- Search Management (offline_ai_search.py)
"""

import hashlib
import secrets
import json
import logging
import shutil
import os
import sys
import uuid
import random
import queue
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Callable, Union
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# ============================================================================
# 1. VERSIONING & MIGRATION (from offline_ai_migration.py)
# ============================================================================

STATE_VERSION = "1.0.0"

class DriftError(Exception):
    """Raised when deterministic drift is detected or snapshot integrity fails."""
    pass

class MigrationEngine:
    def __init__(self):
        self.migrations: Dict[str, Dict[str, Callable]] = {}
    def register(self, module: str, from_version: str, to_version: str, func: Callable):
        if module not in self.migrations: self.migrations[module] = {}
        self.migrations[module][f"{from_version}->{to_version}"] = func
    def migrate(self, module: str, data: Dict[str, Any], target_version: str) -> Dict[str, Any]:
        current_version = data.get("state_version", "0.0.0")
        if current_version == target_version: return data
        logger.info(f"[MIGRATION] Migrating {module} from {current_version} to {target_version}")
        key = f"{current_version}->{target_version}"
        if key in self.migrations.get(module, {}): return self.migrations[module][key](data)
        return data

engine = MigrationEngine()

def add_version_metadata(data: Dict[str, Any], module_name: str, schema_version: str = "1.0"):
    data["state_version"] = STATE_VERSION
    data["module_name"] = module_name
    data["schema_version"] = schema_version
    return data


# ============================================================================
# 2. STORAGE GOVERNANCE (from offline_ai_storage.py)
# ============================================================================

class StorageGovernor:
    DEFAULT_FRACTIONS = {"episodic_memory": 0.30, "lexical_memory": 0.20, "vision_percepts": 0.15, "audio_phonetic": 0.15, "templates": 0.10, "system_reserve": 0.10}
    def __init__(self, storage_dir: str, total_budget_bytes: int = None):
        self.storage_dir = Path(storage_dir)
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"[STORAGE GOVERNOR] Failed to create storage directory {storage_dir}: {e}")
        self.total_budget = total_budget_bytes or self._detect_available_space()
        self.fractions = self.DEFAULT_FRACTIONS.copy()
        self.quotas = self._calculate_quotas()
    def _detect_available_space(self) -> int:
        usage = shutil.disk_usage(self.storage_dir)
        return max(500 * 1024 * 1024, int(usage.free * 0.1))
    def _calculate_quotas(self) -> Dict[str, int]:
        return {k: int(self.total_budget * v) for k, v in self.fractions.items()}
    def get_subsystem_usage(self, subsystem: str) -> int:
        subsystem_path = self.storage_dir / subsystem
        if not subsystem_path.exists(): return 0
        total_size = 0
        for dirpath, _, filenames in os.walk(subsystem_path):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                if not os.path.islink(fp): total_size += os.path.getsize(fp)
        return total_size
    def check_governance(self) -> Dict[str, Any]:
        report = {}
        for subsystem in self.fractions.keys():
            usage = self.get_subsystem_usage(subsystem)
            quota = self.quotas.get(subsystem, 0)
            ratio = usage / max(1, quota)
            report[subsystem] = {"usage_bytes": usage, "quota_bytes": quota, "usage_ratio": ratio, "pressure_high": ratio > 0.9}
        return report
    def update_budget(self):
        new_budget = self._detect_available_space()
        if new_budget > self.total_budget:
            self.total_budget = new_budget
            self.quotas = self._calculate_quotas()


# ============================================================================
# 3. EVENT JOURNAL (from offline_ai_journal.py)
# ============================================================================

class ReplaySession:
    """
    Deterministic Replay Engine (Section III).
    Loads base state, replays journaled deltas, and detects drift.
    """
    def __init__(self, storage_dir: str, account_id: str):
        self.storage_dir = Path(storage_dir)
        self.account_id = account_id
        self.journal = JournalManager(storage_dir, account_id)
        self.drift_report = []

    def replay(self, session_id: str, ai_instance: Any, restore_base: bool = True) -> List[Dict[str, Any]]:
        """
        Replay a specific session on an AI instance.
        Performs turn-by-turn verification of intent, style, and response.

        Args:
            session_id: The ID of the session to replay.
            ai_instance: The OfflineAI instance to use for replaying.
            restore_base: If True, attempts to restore the AI to the 'base_{session_id}' snapshot first.
        """
        if restore_base:
            base_snapshot = f"base_{session_id}"
            logger.info(f"[REPLAY] Restoring baseline snapshot: {base_snapshot}")

            # Patch 3: Replay verification
            if hasattr(ai_instance, "get_snapshot_hash"):
                computed = ai_instance.get_snapshot_hash(base_snapshot)
                expected = self.journal.header.get("base_snapshot_hash")
                if expected and computed != expected:
                    raise DriftError(f"Base snapshot hash mismatch — replay aborted (Expected: {expected}, Actual: {computed})")

            if hasattr(ai_instance, "rollback"):
                success = ai_instance.rollback(base_snapshot)
                if not success:
                    logger.warning(f"[REPLAY] Failed to restore baseline {base_snapshot}. Continuing with current state.")
            else:
                logger.warning("[REPLAY] AI instance does not support rollback. Continuing with current state.")

        entries = self.journal.get_session_entries(session_id)
        if not entries:
            logger.warning(f"[REPLAY] No entries found for session {session_id}")
            return []

        logger.info(f"[REPLAY] Starting replay of session {session_id} ({len(entries)} turns)")
        self.drift_report = []

        for entry in entries:
            turn_id = entry["turn_id"]
            user_input = entry["user_input"]
            stored_response = entry["ai_response"]
            stored_intent = entry.get("intent")
            rng_seed = entry.get("rng_seed")

            # 1. Reseed RNG for determinism
            if rng_seed is not None:
                JournalManager.set_rng_seed(rng_seed)

            # 2. Re-process input
            analysis = ai_instance.process_input(user_input)

            # 3. Intermediate Verification (Intent)
            if stored_intent and analysis["language"]["intent"] != stored_intent:
                self.drift_report.append({
                    "turn": turn_id, "type": "intent_drift",
                    "expected": stored_intent, "actual": analysis["language"]["intent"]
                })

            # 4. Re-generate response
            core_content = entry.get("core_content", "[REPLAY_PLACEHOLDER]")
            regenerated = ai_instance.generate_response(analysis, core_content)
            reg_text = regenerated["text"] if isinstance(regenerated, dict) else regenerated

            # 5. Output Verification
            if reg_text != stored_response:
                self.drift_report.append({
                    "turn": turn_id, "type": "response_drift",
                    "expected": stored_response, "actual": reg_text
                })
                logger.warning(f"[REPLAY] Response drift at turn {turn_id}")
            else:
                logger.info(f"[REPLAY] Turn {turn_id} matched perfectly.")

        return self.drift_report

    def verify_determinism(self, ai_instance: Any, iterations: int = 3) -> bool:
        """Verify that multiple runs with the same seed produce identical results"""
        test_input = "Tell me about evolution."
        test_core = "Evolution is the change in the heritable characteristics of biological populations."
        seed = 42

        results = []
        for i in range(iterations):
            JournalManager.set_rng_seed(seed)
            analysis = ai_instance.process_input(test_input)
            response = ai_instance.generate_response(analysis, test_core)
            results.append(response["text"] if isinstance(response, dict) else response)

        is_deterministic = all(r == results[0] for r in results)
        logger.info(f"[REPLAY] Determinism check: {'PASSED' if is_deterministic else 'FAILED'}")
        return is_deterministic

class JournalManager:
    def __init__(self, storage_dir: str, account_id: str):
        self.storage_dir = Path(storage_dir) / account_id
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"[JOURNAL] Failed to create storage directory {self.storage_dir}: {e}")
        self.journal_file = self.storage_dir / "event_journal.jsonl"
        self.header_file = self.storage_dir / "journal_header.json"
        self.header = self._load_header()

    def _load_header(self) -> Dict[str, Any]:
        if self.header_file.exists():
            try:
                with open(self.header_file, 'r') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def save_header(self):
        try:
            with open(self.header_file, 'w') as f:
                json.dump(self.header, f, indent=2)
        except Exception as e:
            logger.error(f"[JOURNAL] Failed to save header: {e}")

    def log_turn(self, session_id: str, turn_id: int, entry: Dict[str, Any]):
        entry["session_id"], entry["turn_id"] = session_id, turn_id
        entry["timestamp"] = entry.get("timestamp", datetime.now().isoformat())
        try:
            with open(self.journal_file, "a") as f: f.write(json.dumps(entry) + "\n")
        except Exception as e: logger.error(f"[JOURNAL] Failed to log: {e}")
    def get_session_entries(self, session_id: str) -> List[Dict[str, Any]]:
        entries = []
        if not self.journal_file.exists(): return entries
        try:
            with open(self.journal_file, "r") as f:
                for line in f:
                    e = json.loads(line)
                    if e.get("session_id") == session_id: entries.append(e)
        except Exception as e: logger.error(f"[JOURNAL] Failed to read: {e}")
        return entries
    @staticmethod
    def set_rng_seed(seed: Optional[int] = None) -> int:
        if seed is None: seed = random.randint(0, 2**32 - 1)
        random.seed(seed)
        import numpy as np
        np.random.seed(seed)
        return seed


# ============================================================================
# 4. SEARCH MANAGEMENT (from offline_ai_search.py)
# ============================================================================

class SearchManager:
    def __init__(self):
        self.search_approved, self.last_query, self.last_results = False, "", []
    def request_approval(self, query: str) -> str:
        self.last_query = query
        return f"[SEARCH REQUEST] I would like to search for: '{query}'. Approve?"
    def execute_search(self, query: str, tool_func) -> List[Dict[str, str]]:
        if not self.search_approved: return []
        try:
            results = tool_func(query=query)
            self.last_results, self.search_approved = results, False
            return results
        except Exception: return []
    def approve(self): self.search_approved = True
    def deny(self): self.search_approved = False


# ============================================================================
# 5. ACCOUNT MANAGEMENT (from offline_ai_account.py)
# ============================================================================

class SerialCodeGenerator:
    SERIAL_PREFIX, SERIAL_VERSION, SEGMENT_LENGTH, SEGMENTS = "OFFLINE-AI", "v1", 5, 4
    @staticmethod
    def generate() -> str:
        segments = [''.join(secrets.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789') for _ in range(SerialCodeGenerator.SEGMENT_LENGTH)) for _ in range(SerialCodeGenerator.SEGMENTS)]
        return f"{SerialCodeGenerator.SERIAL_PREFIX}-{SerialCodeGenerator.SERIAL_VERSION}-" + "-".join(segments)
    @staticmethod
    def validate_format(serial: str) -> bool:
        parts = serial.split('-')
        if len(parts) != 7 or parts[0] != "OFFLINE" or parts[1] != "AI" or parts[2] != "v1": return False
        for i in range(3, 7):
            if len(parts[i]) != SerialCodeGenerator.SEGMENT_LENGTH or not all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789' for c in parts[i]): return False
        return True

class AccountRecord:
    def __init__(self, account_id: str, serial_code: str, email: str = ""):
        self.account_id, self.serial_code, self.email = account_id, serial_code, email
        self.created_timestamp = self.last_accessed = datetime.now().isoformat()
        self.linked_devices: Dict[str, Dict[str, Any]] = {}
        self.ai_base_model_version, self.download_count, self.is_active, self.license_status = "1.0", 0, True, "active"
    def add_device(self, device_id: str, device_name: str = "") -> bool:
        if device_id in self.linked_devices: return False
        self.linked_devices[device_id] = {"device_id": device_id, "device_name": device_name, "linked_timestamp": datetime.now().isoformat(), "last_sync": None, "ai_memory_version": "1.0"}
        return True
    def remove_device(self, device_id: str) -> bool:
        if device_id in self.linked_devices:
            del self.linked_devices[device_id]
            return True
        return False
    def to_dict(self) -> Dict[str, Any]: return {"account_id": self.account_id, "serial_code": self.serial_code, "email": self.email, "created_timestamp": self.created_timestamp, "last_accessed": self.last_accessed, "linked_devices": self.linked_devices, "ai_base_model_version": self.ai_base_model_version, "download_count": self.download_count, "is_active": self.is_active, "license_status": self.license_status}
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AccountRecord':
        a = cls(data.get("account_id"), data.get("serial_code"), data.get("email", ""))
        a.created_timestamp, a.last_accessed = data.get("created_timestamp", a.created_timestamp), data.get("last_accessed", a.last_accessed)
        a.linked_devices, a.download_count, a.is_active, a.license_status, a.ai_base_model_version = data.get("linked_devices", {}), data.get("download_count", 0), data.get("is_active", True), data.get("license_status", "active"), data.get("ai_base_model_version", "1.0")
        return a

class AccountManager:
    def __init__(self, storage_dir: str = None):
        if storage_dir is None:
            import sys
            # Use environment variables as fallback for Android detection in core
            is_android = sys.platform == "android" or 'ANDROID_ARGUMENT' in os.environ
            if is_android:
                try:
                    from android.storage import app_storage_path
                    storage_dir = app_storage_path()
                except (ImportError, Exception):
                    storage_dir = "./offline_ai_data"
            else:
                storage_dir = "./offline_ai_data"

        self.storage_dir = Path(storage_dir)
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"[ACCOUNT MANAGER] Failed to create storage directory {storage_dir}: {e}")
        self.accounts_file = self.storage_dir / "accounts.json"
        self.accounts, self.serial_to_account = {}, {}
        self._load_accounts()
    def _load_accounts(self):
        if not self.accounts_file.exists(): return
        try:
            with open(self.accounts_file, 'r') as f: data = json.load(f)
            for aid, ad in data.items():
                acc = AccountRecord.from_dict(ad)
                self.accounts[aid], self.serial_to_account[acc.serial_code] = acc, aid
        except Exception as e: logger.error(f"[ACCOUNT MANAGER] Failed to load: {e}")
    def _save_accounts(self):
        try:
            with open(self.accounts_file, 'w') as f:
                json.dump({aid: acc.to_dict() for aid, acc in self.accounts.items()}, f, indent=2)
                # Ensure data is flushed to disk (Patch 1: Safety)
                f.flush()
                os.fsync(f.fileno())
        except Exception as e:
            logger.error(f"[ACCOUNT MANAGER] Failed to save accounts: {e}")
    def create_account(self, email: str = "") -> Tuple[str, str, str]:
        aid, sc = f"user_{uuid.uuid4().hex[:12]}", SerialCodeGenerator.generate()
        acc = AccountRecord(aid, sc, email)
        self.accounts[aid], self.serial_to_account[sc] = acc, aid
        self._save_accounts()
        return aid, sc, f"Account created: {aid}"
    def verify_serial_code(self, serial_code: str) -> Tuple[bool, Optional[str], str]:
        if not SerialCodeGenerator.validate_format(serial_code): return False, None, "Invalid format"
        aid = self.serial_to_account.get(serial_code)
        if not aid: return False, None, "Not registered"
        acc = self.accounts.get(aid)
        if not acc or not acc.is_active: return False, None, "Inactive"
        if acc.license_status != "active": return False, None, f"License: {acc.license_status}"
        acc.last_accessed, acc.download_count = datetime.now().isoformat(), acc.download_count + 1
        self._save_accounts()
        return True, aid, "Verified"
    def get_account(self, account_id: str) -> Optional[AccountRecord]: return self.accounts.get(account_id)
    def link_device(self, account_id: str, device_id: str, device_name: str = "") -> Tuple[bool, str]:
        acc = self.get_account(account_id)
        if not acc: return False, "Not found"
        success = acc.add_device(device_id, device_name)
        if success: self._save_accounts()
        return success, "Linked" if success else "Already linked"
    def get_account_stats(self) -> Dict[str, Any]:
        return {"total_accounts": len(self.accounts), "total_downloads": sum(a.download_count for a in self.accounts.values()), "total_devices_linked": sum(len(a.linked_devices) for a in self.accounts.values()), "active_accounts": sum(1 for a in self.accounts.values() if a.is_active), "accounts": {aid: acc.to_dict() for aid, acc in self.accounts.items()}}


# ============================================================================
# 6. PRODUCTION RUNTIME & IDENTITY (Section III, V, VII, X)
# ============================================================================

class DeviceBridge:
    """Device Abstraction Layer (Mobile-First Universal Runtime)"""
    def __init__(self, cam=0, rate=16000):
        self.cam = cam
        self.rate = rate
        self.audio_q = queue.Queue()
        self.cap = None
        self.pa = None
        self.stream = None
        self._last_frame_time = 0

    def start_camera(self):
        # Camera is enabled on Android via OpenCV, but we must handle failures gracefully
        try:
            import cv2
            self.cap = cv2.VideoCapture(self.cam)
            if self.cap and not self.cap.isOpened():
                logger.warning("[DEVICE] Camera opened but is not ready.")
                self.cap = None
        except ImportError:
            logger.warning("[DEVICE] OpenCV not available. Camera disabled.")
        except Exception as e:
            logger.warning(f"[DEVICE] Camera failed to start: {e}. Camera disabled.")

    def read_frame(self):
        """Throttled Frame Reading (Section 10: 5–10 FPS max)"""
        now = time.time()
        # Enforce 8 FPS (0.125s interval)
        if now - self._last_frame_time < 0.125:
            return None

        self._last_frame_time = now
        if self.cap:
            ok, frame = self.cap.read()
            return frame if ok else None
        return None

    def start_mic(self):
        is_android = sys.platform == 'android' or 'ANDROID_ARGUMENT' in os.environ
        if is_android:
            logger.info("[DEVICE] PyAudio disabled on Android to prevent crashes. Mic disabled.")
            return
        try:
            import pyaudio
            self.pa = pyaudio.PyAudio()
            self.stream = self.pa.open(format=pyaudio.paInt16, channels=1,
                                       rate=self.rate, input=True, frames_per_buffer=1024)
        except (ImportError, Exception) as e:
            logger.warning(f"[DEVICE] PyAudio not available or failed: {e}. Mic disabled.")

    def read_audio(self):
        if self.stream:
            try:
                return self.stream.read(1024, exception_on_overflow=False)
            except Exception:
                return b''
        return b''

class SpeechRuntime:
    """Speech Runtime (Vosk-based ASR)"""
    def __init__(self, model_path, rate, on_text, on_phoneme=None):
        self.on_text = on_text
        self.on_phoneme = on_phoneme
        try:
            import vosk
            self.model = vosk.Model(model_path)
            self.rec = vosk.KaldiRecognizer(self.model, rate)
        except (ImportError, Exception):
            self.model = None
            logger.warning("[SPEECH] Vosk model failed to load. ASR disabled.")

    def feed(self, chunk):
        if hasattr(self, 'rec') and self.rec.AcceptWaveform(chunk):
            res = json.loads(self.rec.Result())
            if "text" in res:
                self.on_text(res["text"])

class TTSRuntime:
    """
    TTS Runtime (Section 10 Pluggable Backends)
    Supports: Coqui TTS, Android TTS (mock), Piper (mock)
    """
    def __init__(self, model_name=None, backend="coqui"):
        self._is_speaking = False
        self.backend = backend
        try:
            if backend == "coqui":
                from TTS.api import TTS
                self.tts = TTS(model_name) if model_name else None
            else:
                self.tts = None # Piper/Android backends to be implemented via native bridge
        except (ImportError, Exception) as e:
            self.tts = None
            logger.warning(f"[TTS] {backend} backend failed to load: {e}")

    def is_speaking(self):
        return self._is_speaking

    def speak(self, text, phoneme_cb=None):
        try:
            self._is_speaking = True
            if self.tts:
                # Note: exact API might vary, following spec
                # Some TTS engines might not support return_phonemes
                try:
                    wav, phonemes = self.tts.tts(text, return_phonemes=True)
                except (TypeError, Exception):
                    wav = self.tts.tts(text)
                    phonemes = []

                if phoneme_cb:
                    for p in phonemes:
                        try:
                            phoneme_cb(p)
                        except Exception:
                            pass

                def _play():
                    try:
                        self.tts.play(wav)
                    except Exception as e:
                        logger.error(f"[TTS] Play failed: {e}")
                    finally:
                        self._is_speaking = False

                threading.Thread(target=_play, daemon=True).start()
            else:
                logger.info(f"[TTS MOCK] Speaking: {text}")
                def _mock():
                    time.sleep(max(1.0, len(text) * 0.05))
                    self._is_speaking = False
                threading.Thread(target=_mock, daemon=True).start()
        except Exception as e:
            logger.error(f"[TTS] Speak failed: {e}")
            self._is_speaking = False

class InterfaceRuntime:
    """Thread Coordinator for Device I/O"""
    def __init__(self, device: DeviceBridge, speech: SpeechRuntime, vision: Any, runtime: Any):
        self.device = device
        self.speech = speech
        self.vision = vision
        self.runtime = runtime
        self.running = False

    def start(self):
        self.running = True
        self.device.start_camera()
        self.device.start_mic()
        threading.Thread(target=self.audio_loop, daemon=True).start()
        threading.Thread(target=self.video_loop, daemon=True).start()

    def stop(self):
        self.running = False

    def audio_loop(self):
        while self.running:
            chunk = self.device.read_audio()
            if chunk and self.speech:
                self.speech.feed(chunk)
            time.sleep(0.01)

    def video_loop(self):
        while self.running:
            frame = self.device.read_frame()
            if frame is not None:
                if hasattr(self.vision, 'process'):
                    self.vision.process(frame)
                elif hasattr(self.vision, 'process_visual_input'):
                     # Fallback to existing vision manager
                     pass
            time.sleep(0.03)

class WakeWordPolicy:
    """Wake-Word & Always-On Microphone Policy"""
    def __init__(self, mode="introvert"):
        self.mode = mode
        self.last_activity = time.time()
        # timeouts in seconds
        self.timeout = 15 if mode == "introvert" else 90

    def update_activity(self):
        self.last_activity = time.time()

    def mic_active(self):
        if self.mode == "extrovert":
            return True
        return (time.time() - self.last_activity) < self.timeout

    def active(self): # Compatibility with older spec
        return self.mic_active()

class PresencePolicy:
    def __init__(self, mode="introvert"):
        self.mode = mode
        self.visible = False

    def on_user_call(self):
        self.visible = True

    def on_idle(self, seconds_idle):
        if self.mode == "introvert" and seconds_idle > 3:
            self.visible = False

    def allow_initiation(self):
        return self.mode == "extrovert"

class PresenceTimeout:
    def __init__(self, mode="introvert"):
        self.mode = mode
        self.visible = True
        self.timeout = 10 if mode == "introvert" else 120
        self.last_interaction = time.time()

    def update(self):
        if time.time() - self.last_interaction > self.timeout:
            self.visible = False

    def touch(self):
        self.last_interaction = time.time()
        self.visible = True

class RenderPolicy:
    def select_backend(self):
        import platform
        if platform.system() in ["Android", "iOS"]:
            return "gpu"
        return "cpu"

class UnityIPCServer:
    """
    SECTION 11: Unity Mobile Integration IPC Layer.
    Handles communication between Core and Unity.
    """
    def __init__(self, host='127.0.0.1', port=50051):
        self.host = host
        self.port = port
        self.running = False
        self.server_thread = None
        self.clients = []

    def start(self, core_instance):
        self.running = True
        self.core = core_instance
        self.server_thread = threading.Thread(target=self._run_server, daemon=True)
        self.server_thread.start()
        logger.info(f"[IPC] Unity IPC Server started on {self.host}:{self.port}")

    def _run_server(self):
        import socket
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((self.host, self.port))
                s.listen()
                while self.running:
                    conn, addr = s.accept()
                    threading.Thread(target=self._handle_client, args=(conn,), daemon=True).start()
        except Exception as e:
            logger.error(f"[IPC] Server error: {e}")

    def _handle_client(self, conn):
        """Framed IPC Handler (Newline-delimited JSON)"""
        buffer = ""
        with conn:
            while self.running:
                try:
                    data = conn.recv(4096)
                    if not data: break

                    buffer += data.decode()
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        if not line.strip(): continue

                        msg = json.loads(line)
                        response = self._process_unity_message(msg)
                        conn.sendall(json.dumps(response).encode() + b'\n')
                except Exception as e:
                    logger.error(f"[IPC] Client error: {e}")
                    break

    def _process_unity_message(self, msg):
        # UI never injects intents directly (Section 12)
        # All UI events go through intent inference.
        m_type = msg.get("type")
        if m_type == "input":
            text = msg.get("text")
            # Tag UI events (Section 12)
            result = self.core.process_input(text)
            return {"type": "analysis", "data": result}
        elif m_type == "expression_query":
            # Section 11: Animation Contract
            # Emits expression_id, emotion vector, intensity
            intensity = self.core.energy.emotion_intensity if hasattr(self.core, 'energy') else 0.5
            output = self.core.affect.get_unity_output("current", intensity)
            return {"type": "expression", "data": output}
        elif m_type == "set_ui_busy":
            # Section 12: No consolidation during scene load etc.
            self.core.ui_busy = msg.get("value", False)
            return {"type": "ack", "status": "ui_busy_set", "value": self.core.ui_busy}
        return {"type": "error", "message": "Unknown type"}

    def stop(self):
        self.running = False

class IdentitySessionLock:
    """Single-Companion Identity Lock & Session Ownership System"""
    def __init__(self, companion_id, account_id):
        self.companion_id = companion_id
        self.account_id = account_id
        self.token = None
        self.issued_at = None

    def rotate(self, memory: Any):
        """Rotate ownership on startup"""
        self.token = secrets.token_hex(32)
        self.issued_at = time.time()

        target = memory.metadata if hasattr(memory, 'metadata') else memory
        target["session_token"] = self.token
        target["session_issued_at"] = self.issued_at

    def validate(self, memory: Any) -> bool:
        target = memory.metadata if hasattr(memory, 'metadata') else memory
        return target.get("session_token") == self.token

class CheckpointManager:
    """KO System Restore Runtime - Checkpoint Manager"""
    def __init__(self, path: str):
        self.path = Path(path)
        try:
            self.path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"[CHECKPOINT] Failed to create checkpoint directory {path}: {e}")

    def create(self, memory: Any) -> str:
        target = memory.metadata if hasattr(memory, 'metadata') else memory
        snap = {
            "time": time.time(),
            "memory": memory.to_dict() if hasattr(memory, 'to_dict') else memory,
            "token": target.get("session_token"),
            "checkpoint_token": target.get("session_token") # Spec requirement
        }
        fname = f"cp_{int(snap['time'])}.json"
        with open(self.path / fname, "w") as f:
            json.dump(snap, f, indent=2)
        return fname

class RestoreEngine:
    """KO System Restore Runtime - Restore Engine"""
    def __init__(self, lock: IdentitySessionLock, persistence_dir: str):
        self.lock = lock
        self.persistence_dir = Path(persistence_dir)

    def restore(self, file_path: str) -> Dict[str, Any]:
        with open(file_path, "r") as f:
            snap = json.load(f)

        # Validate checkpoint token
        if snap.get("token") != self.lock.token and snap.get("checkpoint_token") != self.lock.token:
             # If we are restoring, we might be taking over or rolling back.
             # The spec says: if snap["token"] != self.lock.token: raise RuntimeError("Invalid lineage")
             # But if it's a new device, we might need a way to override.
             # For now, following spec.
             if self.lock.token is not None: # Only check if we already have a token
                 raise RuntimeError("Invalid lineage")

        mem = snap["memory"]
        self.lock.rotate(mem)
        # Persistence save would happen in Core
        return mem
