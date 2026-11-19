"""
Agora AI - shared main-thread scheduling helper
===============================================

Authored by Sunni (Sir) Morningstar and Cael Devo.

Audio, vision and runtime code schedule callbacks written both as
``lambda: ...`` and as Kivy-style ``lambda dt: ...``. Calling a ``dt``
callback with no argument raises inside the Kivy clock, and on Android an
uncaught clock error closes the app. This helper passes ``dt`` only to
callbacks that require it, so both forms are safe.
"""

import inspect
import threading

try:
    from kivy.clock import Clock
except Exception:  # pragma: no cover - engine used without Kivy
    Clock = None

_POSITIONAL = (inspect.Parameter.POSITIONAL_ONLY,
               inspect.Parameter.POSITIONAL_OR_KEYWORD)


def _wants_dt(callback) -> bool:
    try:
        params = inspect.signature(callback).parameters.values()
    except (TypeError, ValueError):
        return False
    for param in params:
        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            return True
        if param.kind in _POSITIONAL and param.default is inspect.Parameter.empty:
            return True
    return False


def call_scheduled(callback, dt=0.0):
    """Invoke a scheduled callback with ``dt`` only if it requires one."""
    return callback(dt) if _wants_dt(callback) else callback()


def schedule_once(callback, delay=0):
    """Run ``callback`` once on the Kivy clock, or on a timer without Kivy."""
    if Clock is not None:
        Clock.schedule_once(lambda dt: call_scheduled(callback, dt), delay)
    else:
        timer = threading.Timer(delay, call_scheduled, args=(callback, delay))
        timer.daemon = True
        timer.start()
