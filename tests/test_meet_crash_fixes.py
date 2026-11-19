#!/usr/bin/env python3
"""
Agora AI - Meet button crash regressions
========================================

Authored by Sunni (Sir) Morningstar and Cael Devo.

Pressing Meet closed the app on a phone. Causes covered here:
- every spoken reply finished through a callback that was scheduled as
  ``lambda dt: ...`` but called with no argument, raising inside the clock
- creating the first entity used ``uuid`` without importing it
- an uncaught clock error closed the app instead of being recorded
- Android's sandbox refuses hard links, so committing the birth record failed
"""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from kivy.base import ExceptionManager

from engine.agora_scheduling import call_scheduled
from engine.offline_ai_audio_engine import schedule_once as audio_schedule_once
from engine.offline_ai_runtime import schedule_once as runtime_schedule_once
from engine.offline_ai_vision_capture import schedule_once as vision_schedule_once


class TestScheduledCallbacks(unittest.TestCase):
    def test_both_callback_forms_run(self):
        seen = []
        call_scheduled(lambda: seen.append("plain"), 0.1)
        call_scheduled(lambda dt: seen.append(("dt", dt)), 0.1)
        call_scheduled(lambda dt, t="x": seen.append(t), 0.1)
        call_scheduled(lambda *a: seen.append(a), 0.1)
        self.assertEqual(seen, ["plain", ("dt", 0.1), "x", (0.1,)])

    def test_engine_helpers_accept_dt_lambdas_on_the_clock(self):
        from kivy.clock import Clock
        seen = []
        for helper in (audio_schedule_once, runtime_schedule_once, vision_schedule_once):
            helper(lambda dt: seen.append("dt"), 0)
            helper(lambda: seen.append("plain"), 0)
        Clock.tick()
        Clock.tick()
        self.assertEqual(sorted(seen), ["dt"] * 3 + ["plain"] * 3)


class TestFirstEntity(unittest.TestCase):
    def test_new_entity_gets_a_memory_id(self):
        from app.entity_manager import EntityIdentity
        entity = EntityIdentity(user_id="tester")
        self.assertTrue(entity.memory_id.startswith("MEM-"))


class TestBirthCommitOnAndroid(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_commit_works_when_hard_links_are_refused(self):
        from engine.agora_birth import BirthStore, select_birth
        first = select_birth(ai_name="Poedex", mode="introvert", require_audio=False)
        other = select_birth(ai_name="Zed", mode="extrovert", require_audio=False)
        refused = PermissionError(13, "Permission denied")
        with mock.patch("engine.agora_birth.os.link", side_effect=refused):
            committed = BirthStore(self.tmp).commit(first)
            again = BirthStore(self.tmp).commit(other)
        self.assertEqual(committed["primary"], first.primary)
        self.assertEqual(again, BirthStore(self.tmp).read())
        self.assertEqual(again["mode"], "introvert")
        self.assertEqual([p.name for p in self.tmp.iterdir()], ["birth_record.json"])


class TestCrashGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_uncaught_error_is_logged_and_app_keeps_running(self):
        from app.crash_guard import AgoraCrashGuard, CRASH_LOG_NAME

        class FakeApp:
            popups = []
            def _show_error_popup(self, message, title=""):
                self.popups.append(message)

        guard = AgoraCrashGuard(FakeApp(), self.tmp)
        try:
            raise TypeError("callback missing dt")
        except TypeError as error:
            verdict = guard.handle_exception(error)
        self.assertEqual(verdict, ExceptionManager.PASS)
        log = (self.tmp / CRASH_LOG_NAME).read_text(encoding="utf-8")
        self.assertIn("callback missing dt", log)


if __name__ == "__main__":
    unittest.main()
