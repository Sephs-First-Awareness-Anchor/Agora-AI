"""Regression checks for the November Android screenshots.

Mocks verify the PyJNIus/AudioRecord interop contract. Real-device
microphone and Android 17 behavior are still hardware acceptance gates.
"""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from kivy.clock import Clock
from app.ui.screens.login import LoginScreen
from app.ui.screens.onboarding import OnboardingScreen
from engine import offline_ai_audio_engine as audio


class TestResponsiveScreens(unittest.TestCase):
    def test_login_form_fits_actual_card_and_signup_expands(self):
        screen = LoginScreen(name="login")
        Clock.tick()
        card = screen.user_input.parent.parent
        self.assertEqual(screen.confirm_container.height, 0)
        Clock.tick()
        self.assertGreaterEqual(card.height + 1, card.minimum_height)
        original_height = card.height
        screen._set_mode("signup")
        Clock.tick()
        self.assertEqual(screen.confirm_container.height, 85)
        self.assertGreaterEqual(card.height, original_height)

    def test_color_step_does_not_address_user_as_ai(self):
        screen = OnboardingScreen(name="onboarding")
        screen.ai_name_input.text = "Poedex"
        screen._next_from_welcome()
        labels = [
            child.text for child in screen.content.children
            if hasattr(child,"text")
        ]
        self.assertTrue(any("Pick your favorite color" in t for t in labels))
        self.assertFalse(any("Hi, Poedex" in t for t in labels))
        self.assertEqual(screen.current_step, 1)

    def test_onboarding_has_scrollable_content(self):
        screen = OnboardingScreen(name="onboarding")
        self.assertTrue(hasattr(screen,"scroll"))
        self.assertFalse(screen.scroll.do_scroll_x)
        self.assertIs(screen.content.parent, screen.scroll)


class MockByteBuffer:
    def __init__(self, capacity):
        self.content = bytearray(capacity)
        self.cursor = 0

    @classmethod
    def allocateDirect(cls, capacity):
        return cls(capacity)

    def clear(self):
        self.cursor = 0

    def position(self, position):
        self.cursor = position

    def get(self, target, start, count):
        target[start:start + count] = self.content[self.cursor:self.cursor + count]
        self.cursor += count


class MockRecorder:
    STATE_INITIALIZED = 1
    RECORDSTATE_RECORDING = 3
    READ_BLOCKING = 0

    @staticmethod
    def getMinBufferSize(sr, channel, fmt):
        return 1024

    def __init__(self, source, sr, channel, fmt, size):
        self.released = False

    def getState(self):
        return self.STATE_INITIALIZED

    def getRecordingState(self):
        return self.RECORDSTATE_RECORDING

    def startRecording(self):
        pass

    def read(self, buf, length, mode):
        # Real bytearray interop, no synthetic transcript-derived signature.
        buf.content[:length] = b"\x20\x12" * (length // 2)
        return length

    def stop(self):
        pass

    def release(self):
        self.released = True


class TestAndroidPCMBridge(unittest.TestCase):
    def test_direct_bytebuffer_capture_does_not_import_jarray(self):
        classes = {
            "android.media.AudioRecord": MockRecorder,
            "android.media.AudioFormat": SimpleNamespace(
                CHANNEL_IN_MONO=16, ENCODING_PCM_16BIT=2),
            "android.media.MediaRecorder$AudioSource": SimpleNamespace(MIC=1),
            "java.nio.ByteBuffer": MockByteBuffer,
        }
        jnius = SimpleNamespace(autoclass=lambda name: classes[name])
        engine = audio.AudioEngine.__new__(audio.AudioEngine)
        engine.stop_listening = lambda: None
        with patch.object(audio, "IS_ANDROID", True), \
                patch.object(audio, "JNIUS_AVAILABLE", True), \
                patch.dict(sys.modules, {"jnius":jnius}):
            pcm=engine.capture_name_pcm(duration_seconds=.5)
        self.assertEqual(len(pcm), 16000)
        self.assertEqual(pcm[:6], b"\x20\x12\x20\x12\x20\x12")

    def test_build_targets_android_16_and_keeps_old_minimum(self):
        spec=(Path(__file__).resolve().parents[1]/"buildozer.spec").read_text()
        self.assertIn("android.api = 36",spec)
        self.assertIn("android.minapi = 26",spec)
        self.assertIn("p4a.branch = v2026.05.09",spec)


if __name__ == "__main__":
    unittest.main()
