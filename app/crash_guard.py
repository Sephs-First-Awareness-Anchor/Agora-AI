"""
Agora AI - crash guard
======================

Authored by Sunni (Sir) Morningstar and Cael Devo.

On Android an uncaught error inside a Kivy callback closes the whole app
with no message. This guard records the traceback to ``crash_log.txt`` in
the app's private storage, shows the error once on screen so a tester can
report it, and keeps the app running.
"""

import logging
import threading
import traceback
from datetime import datetime
from pathlib import Path

from kivy.base import ExceptionHandler, ExceptionManager
from kivy.clock import Clock

logger = logging.getLogger(__name__)

CRASH_LOG_NAME = "crash_log.txt"
_MAX_LOG_BYTES = 256 * 1024


class AgoraCrashGuard(ExceptionHandler):
    def __init__(self, app, log_dir):
        super().__init__()
        self.app = app
        self.log_path = Path(log_dir) / CRASH_LOG_NAME if log_dir else None
        self._shown = set()

    def record(self, exc_type, exc, tb, where="main"):
        text = "".join(traceback.format_exception(exc_type, exc, tb))
        logger.error("[CRASH_GUARD] Uncaught error (%s):\n%s", where, text)
        if self.log_path:
            try:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                if self.log_path.exists() and self.log_path.stat().st_size > _MAX_LOG_BYTES:
                    self.log_path.unlink()
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(f"--- {datetime.now().isoformat()} [{where}]\n{text}\n")
            except Exception as log_error:
                logger.warning("[CRASH_GUARD] Could not write crash log: %s", log_error)
        summary = f"{exc_type.__name__}: {exc}"
        if summary not in self._shown:
            self._shown.add(summary)
            Clock.schedule_once(lambda dt: self._show(summary, text), 0)

    def _show(self, summary, text):
        last = [line for line in text.strip().splitlines() if line.strip()][-4:]
        try:
            self.app._show_error_popup(
                "Something went wrong, but the app kept running.\n\n"
                f"{summary}\n\n" + "\n".join(last[:-1]),
                title="Agora error")
        except Exception:
            pass

    def handle_exception(self, exception):
        self.record(type(exception), exception, exception.__traceback__)
        return ExceptionManager.PASS


def install(app, log_dir):
    """Install the guard for the Kivy loop and for background threads."""
    guard = AgoraCrashGuard(app, log_dir)
    ExceptionManager.add_handler(guard)

    def thread_hook(args):
        if args.exc_type is SystemExit:
            return
        guard.record(args.exc_type, args.exc_value, args.exc_traceback,
                     where=getattr(args.thread, "name", "thread"))
    threading.excepthook = thread_hook
    return guard
