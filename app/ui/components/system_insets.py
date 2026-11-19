"""
Agora AI - Android system bar insets
====================================

Authored by Sunni (Sir) Morningstar and Cael Devo.

Apps that target Android 15 or newer are drawn edge to edge, so the status
bar and the navigation bar sit on top of the app's own window. Kivy does
not pad for them, which left the Back and Continue buttons under the
navigation bar. These helpers read the bar heights (in pixels) and keep a
layout padded clear of them.
"""

import logging

from kivy.clock import Clock
from kivy.core.window import Window
from kivy.utils import platform as kivy_platform

logger = logging.getLogger(__name__)


def read_system_insets():
    """Return ``(top, bottom)`` system bar heights in pixels (0, 0 off Android)."""
    if kivy_platform != "android":
        return (0, 0)
    try:
        from jnius import autoclass
        activity = autoclass("org.kivy.android.PythonActivity").mActivity
        insets = activity.getWindow().getDecorView().getRootWindowInsets()
        if insets is not None:
            try:
                bar_type = autoclass("android.view.WindowInsets$Type")
                bars = insets.getInsets(bar_type.systemBars())
                return (int(bars.top), int(bars.bottom))
            except Exception:
                return (int(insets.getSystemWindowInsetTop()),
                        int(insets.getSystemWindowInsetBottom()))
        resources = activity.getResources()

        def dimen(name):
            res_id = resources.getIdentifier(name, "dimen", "android")
            return int(resources.getDimensionPixelSize(res_id)) if res_id > 0 else 0
        return (dimen("status_bar_height"), dimen("navigation_bar_height"))
    except Exception as error:
        logger.warning("[INSETS] Could not read system bar insets: %s", error)
        return (0, 0)


def keep_clear_of_system_bars(layout):
    """Pad ``layout`` above the navigation bar and below the status bar."""
    def apply(*_):
        top, bottom = read_system_insets()
        layout.padding = [0, top, 0, bottom]

    if kivy_platform == "android":
        # Insets exist only once the window is attached; re-read on resize
        # (rotation, keyboard, gesture vs. button navigation changes).
        Clock.schedule_once(apply, 0)
        Clock.schedule_once(apply, 0.6)
        Window.bind(size=lambda *_: Clock.schedule_once(apply, 0.1))
    return layout
