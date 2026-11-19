"""Headless Kivy smoke checks for real companion and onboarding callbacks.

Run under xvfb. These exercise widgets and callback dispatch, not Android I/O.
"""
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from kivy.clock import Clock

from app.ui.screens.companion import CompanionScreen
from app.ui.screens.onboarding import OnboardingScreen
from app.ui.screens.name_enrollment import NameEnrollmentScreen


class FakeRuntime:
    def __init__(self, screen):
        self.screen = screen
        self.received = []
        self.listening_requests = 0

    def _process_text_input(self, message):
        self.received.append(message)
        self.screen._show_speech("A learned response to: " + message, is_ai=True)

    def enable_listening(self):
        self.listening_requests += 1
        return True


class TestLiveCompanionScreen(unittest.TestCase):
    def setUp(self):
        self.screen = CompanionScreen(name="companion")
        Clock.tick()
        self.assertTrue(hasattr(self.screen, "text_input"))
        self.runtime = FakeRuntime(self.screen)
        self.screen.runtime = self.runtime

    def test_send_reaches_runtime_and_renders_its_actual_reply(self):
        before = len(self.screen.chat_container.children)
        self.screen.text_input.text = "Deeni likes the garden"
        self.screen._send_message()
        Clock.tick()
        self.assertEqual(self.runtime.received, ["Deeni likes the garden"])
        self.assertEqual(self.screen.text_input.text, "")
        self.assertEqual(len(self.screen.chat_container.children), before + 2)

    def test_microphone_button_targets_runtime(self):
        self.screen._start_listening()
        self.assertTrue(self.screen.is_listening)
        self.assertEqual(self.runtime.listening_requests, 1)
        self.screen._stop_listening()
        self.assertFalse(self.screen.is_listening)

    def test_on_enter_activates_once_with_first_boot(self):
        app = SimpleNamespace(
            serial_code="test-serial",
            _ai_activated=False,
            _first_boot_pending=True,
            _activate_ai=Mock(),
        )
        with patch("app.ui.screens.companion.App.get_running_app", return_value=app):
            self.screen.on_enter()
        app._activate_ai.assert_called_once_with(first_boot=True)
        self.assertFalse(app._first_boot_pending)


class TestRestoredOnboarding(unittest.TestCase):
    def test_name_color_mode_and_user_data_reach_app(self):
        screen = OnboardingScreen(name="onboarding")
        screen.ai_name_input.text = "Sunni"
        screen._next_from_welcome()
        self.assertEqual(screen.ai_name, "Sunni")
        screen._select_color("green")
        screen._show_step(2)
        screen.mode_toggle._select("extrovert")
        screen._next_from_mode()
        screen.user_name_input.text = "Tester"
        screen.birthday_input.text = "July 31"
        receiver = SimpleNamespace(begin_name_enrollment=Mock(),
                                   finish_name_enrollment=Mock())
        with patch("app.ui.screens.onboarding.App.get_running_app", return_value=receiver):
            screen._next_from_user()
            # Voice comes before the meeting screen; don't commit here.
            self.assertEqual(screen.current_step, 3)
            receiver.begin_name_enrollment.assert_called_once_with(
                user_name="Tester", ai_name="Sunni", favorite_color="green",
                mode="extrovert", birthday="July 31")
            screen._show_step(4)
            screen._complete_onboarding()
        receiver.finish_name_enrollment.assert_called_once_with()


class TestVoiceBeforeMeeting(unittest.TestCase):
    def test_enrollment_finishes_by_showing_meeting_screen_not_birth(self):
        screen = NameEnrollmentScreen(name="name_enrollment")
        intro = Mock()
        manager = SimpleNamespace(current="name_enrollment")
        session = SimpleNamespace(
            data={"samples":{"user_name":[1,2,3],"ai_name":[1,2,3]},
                  "identity":{"ai_name":"Poedex","user_name":"Sunni"}},
            next_target=lambda:None,
            ready=lambda:True)
        app = SimpleNamespace(
            get_pending_enrollment=lambda:session,
            onboarding_screen=SimpleNamespace(_show_step=intro),
            screen_manager=manager)
        with patch("app.ui.screens.name_enrollment.App.get_running_app", return_value=app):
            screen.refresh()
            self.assertFalse(screen.finish_button.disabled)
            screen.finish()
        intro.assert_called_once_with(4)
        self.assertEqual(manager.current, "onboarding")

    def test_recording_error_wraps_in_readable_status(self):
        screen = NameEnrollmentScreen(name="name_enrollment")
        session = SimpleNamespace(
            data={"samples":{"user_name":[],"ai_name":[]},
                  "identity":{"ai_name":"Poedex","user_name":"Sunni"}},
            next_target=lambda:"user_name")
        app = SimpleNamespace(get_pending_enrollment=lambda:session)
        with patch("app.ui.screens.name_enrollment.App.get_running_app", return_value=app):
            screen._capture_finished("Microphone permission denied")
        self.assertIn("Microphone error", screen.status.text)
        self.assertIn("permission", screen.status.text)


if __name__ == "__main__":
    unittest.main()
