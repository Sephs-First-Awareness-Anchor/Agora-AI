"""Six PCM name samples, before the final meeting/introduction screen."""
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock
from kivy.metrics import dp


class NameEnrollmentScreen(Screen):
    """A readable small-screen enrollment UI; the app owns audio capture."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.busy = False
        root = BoxLayout(
            orientation="vertical",
            padding=[dp(18), dp(16), dp(18), dp(18)],
            spacing=dp(12),
        )
        self.add_widget(root)
        self.layout = root

        scroll = ScrollView(
            size_hint=(1, 1), do_scroll_x=False, bar_width=dp(4),
        )
        content = BoxLayout(
            orientation="vertical", size_hint_y=None,
            padding=[dp(6), dp(18), dp(6), dp(18)], spacing=dp(22),
        )
        content.bind(minimum_height=content.setter("height"))
        scroll.add_widget(content)
        root.add_widget(scroll)

        self.title_label = Label(
            text="Teach Agora Your Names", font_size="23sp", bold=True,
            halign="center", valign="middle", size_hint_y=None,
            height=dp(68),
        )
        self.instruction = Label(
            text="", font_size="17sp", halign="center", valign="middle",
            size_hint_y=None, height=dp(130),
        )
        self.progress = Label(
            text="", font_size="15sp", halign="center",
            size_hint_y=None, height=dp(45),
        )
        self.status = Label(
            text="", font_size="14sp", halign="center", valign="middle",
            color=(.78, .85, .98, 1), size_hint_y=None, height=dp(68),
        )
        for label in (
            self.title_label, self.instruction, self.progress, self.status,
        ):
            content.add_widget(label)
            label.bind(width=lambda widget, width: setattr(
                widget, "text_size", (max(60, width - dp(12)), None)))
        self.instruction.bind(
            texture_size=lambda widget, size: setattr(
                widget, "height", max(dp(130), size[1] + dp(22))))
        self.status.bind(
            texture_size=lambda widget, size: setattr(
                widget, "height", max(dp(68), size[1] + dp(18))))

        # Sticky actions remain available even when the text wraps.
        actions = BoxLayout(
            orientation="vertical", spacing=dp(10),
            size_hint_y=None, height=dp(184),
        )
        self.record_button = Button(
            text="Record name (1.8 seconds)", font_size="16sp",
            size_hint_y=None, height=dp(54),
            background_normal="", background_color=(.18, .48, .86, 1),
        )
        self.record_button.bind(on_release=self.record_next)
        self.finish_button = Button(
            text="Continue to introduction", font_size="16sp",
            size_hint_y=None, height=dp(54), disabled=True,
            background_normal="", background_color=(.2, .58, .36, 1),
        )
        self.finish_button.bind(on_release=self.finish)
        self.reset_button = Button(
            text="Start enrollment over", font_size="14sp",
            size_hint_y=None, height=dp(46),
        )
        self.reset_button.bind(on_release=self.reset)
        for widget in (self.record_button, self.finish_button, self.reset_button):
            actions.add_widget(widget)
        root.add_widget(actions)

    def on_enter(self, *args):
        self.refresh()

    def refresh(self):
        app = App.get_running_app()
        try:
            session = app.get_pending_enrollment()
        except Exception as error:
            self.status.text = f"Enrollment unavailable: {error}"
            self.record_button.disabled = True
            self.finish_button.disabled = True
            return

        counts = session.data["samples"]
        self.progress.text = (
            f"Your name  {len(counts['user_name'])}/3"
            f"     AI name  {len(counts['ai_name'])}/3"
        )
        target = session.next_target()
        if target is None:
            ai_name = session.data["identity"]["ai_name"]
            self.instruction.text = (
                f"Both names are recorded!\n"
                f"Next, you'll meet {ai_name}."
            )
            self.record_button.disabled = True
            self.finish_button.disabled = self.busy
        else:
            name = session.data["identity"][target]
            who = "your name" if target == "user_name" else "your AI's name"
            number = len(counts[target]) + 1
            self.instruction.text = (
                f"Say {who}:\n{name}\n\n"
                f"Recording {number} of 3. Speak naturally."
            )
            self.record_button.disabled = self.busy
            self.finish_button.disabled = True
        if not self.status.text:
            self.status.text = "Recordings stay on this device. Raw audio is not saved."

    def record_next(self, *args):
        if self.busy:
            return
        self.busy = True
        self.record_button.disabled = True
        self.status.text = "Listening... say the name clearly."
        App.get_running_app().capture_enrollment_name(self._capture_finished)

    def _capture_finished(self, error=None):
        self.busy = False
        self.status.text = (
            f"Microphone error: {error}\nCheck microphone permission and try again."
            if error else "Recording accepted. Thank you!"
        )
        self.refresh()

    def finish(self, *args):
        """Voice enrollment precedes the final Ready to Meet screen."""
        if self.busy:
            return
        app = App.get_running_app()
        if not app.get_pending_enrollment().ready():
            self.status.text = "All six recordings are required first."
            return
        app.onboarding_screen._show_step(4)
        app.screen_manager.current = "onboarding"

    def reset(self, *args):
        if not self.busy:
            App.get_running_app().reset_name_enrollment()
