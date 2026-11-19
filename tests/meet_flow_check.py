#!/usr/bin/env python3
"""
Agora AI - end-to-end Meet flow check
=====================================

Authored by Sunni (Sir) Morningstar and Cael Devo.

Runs the real app headless (under xvfb) through the path a new owner
takes: six name recordings, the Meet button, activation of the born AI,
and three typed messages. Exits non-zero if anything raises, activation
fails, or no reply reaches the chat. Mock audio stands in for the phone's
microphone and speech engines, and hard links are refused as on Android.

Usage: KIVY_NO_ARGS=1 xvfb-run -a python tests/meet_flow_check.py
"""

import math
import os
import random
import struct
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("KIVY_NO_ARGS", "1")
os.environ["HOME"] = tempfile.mkdtemp(prefix="agora-meet-")

from kivy.base import ExceptionHandler, ExceptionManager  # noqa: E402
from kivy.clock import Clock  # noqa: E402

import engine.agora_birth  # noqa: E402
from app.main import KOCompanionApp  # noqa: E402


def _android_refuses_hard_links(*args, **kwargs):
    raise PermissionError(13, "Permission denied")


# Behave like the phone: Android's app sandbox refuses hard links.
engine.agora_birth.os.link = _android_refuses_hard_links

MESSAGES = ["hi, my dog Deeni loves the park",
            "the park was sunny today",
            "thanks for listening"]
UI_TEXT = ("Send", "Tap to Speak", "Delete local voice-learning data")
problems = []


def voiced_pcm(seed, seconds=1.8, rate=16000):
    """A short voiced tone with an envelope, shaped like a spoken name."""
    rnd = random.Random(seed)
    f0 = 120 + 40 * rnd.random()
    out = bytearray()
    for i in range(int(seconds * rate)):
        t = i / rate
        env = 0.0 if t < .25 or t > 1.5 else math.sin(math.pi * (t - .25) / 1.25)
        f = f0 * (1 + .1 * math.sin(2 * math.pi * 3 * t))
        v = env * (.5 * math.sin(2 * math.pi * f * t) + .25 * math.sin(4 * math.pi * f * t))
        v += .01 * rnd.uniform(-1, 1)
        out += struct.pack("<h", max(-32767, min(32767, int(v * 20000))))
    return bytes(out)


class RecordEverything(ExceptionHandler):
    def handle_exception(self, exception):
        problems.append("".join(traceback.format_exception(exception)))
        return ExceptionManager.PASS


class MeetFlow(KOCompanionApp):
    def on_start(self):
        super().on_start()
        ExceptionManager.add_handler(RecordEverything())
        Clock.schedule_once(self.enroll_and_meet, 1.0)

    def _show_error_popup(self, message, title="Error"):
        problems.append(f"popup [{title}]: {message}")

    def enroll_and_meet(self, dt):
        try:
            self.begin_name_enrollment(user_name="Sunni", ai_name="Poedex",
                                       favorite_color="blue", mode="introvert",
                                       birthday="03/28/1990")
            session = self.get_pending_enrollment()
            for i in range(6):
                session.add_pcm(session.next_target(), voiced_pcm(i))
            self.screen_manager.current = "onboarding"
            self.screen_manager.get_screen("onboarding")._complete_onboarding()
        except Exception:
            problems.append(traceback.format_exc())
        Clock.schedule_once(self.chat, 3.0)

    def chat(self, dt):
        if not getattr(self, "_ai_activated", False):
            problems.append("AI was not activated after Meet")
        companion = self.screen_manager.get_screen("companion")
        for message in MESSAGES:
            companion.text_input.text = message
            companion._send_message()
        Clock.schedule_once(self.finish, 6.0)

    def finish(self, dt):
        companion = self.screen_manager.get_screen("companion")
        texts = [w.text for w in companion.walk()
                 if isinstance(getattr(w, "text", None), str) and w.text]
        last_sent = texts.index(MESSAGES[-1]) if MESSAGES[-1] in texts else -1
        replies = [t for t in texts[last_sent + 1:] if t not in UI_TEXT]
        print("Chat after Meet:", texts)
        if last_sent < 0 or not replies:
            problems.append("No AI reply reached the chat")
        self.stop()


if __name__ == "__main__":
    try:
        MeetFlow().run()
    except Exception:
        problems.append(traceback.format_exc())
    if problems:
        print("MEET FLOW FAILED")
        for problem in problems:
            print(problem)
        sys.exit(1)
    print("MEET FLOW OK")
