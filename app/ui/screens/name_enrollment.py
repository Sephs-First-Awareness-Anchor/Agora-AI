"""Six real spoken-name samples before Agora's first cognitive activation."""
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.clock import Clock


class NameEnrollmentScreen(Screen):
    """Calls the app's one prebirth AudioEngine owner; never records itself."""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation="vertical",padding=28,spacing=16)
        self.add_widget(self.layout)
        self.title_label = Label(text="Teach Agora Your Names", font_size="23sp",
                                 size_hint_y=.18)
        self.instruction = Label(text="", font_size="17sp",
                                 text_size=(300,None),halign="center",
                                 size_hint_y=.34)
        self.progress = Label(text="",font_size="15sp",size_hint_y=.12)
        self.status = Label(text="",font_size="13sp",size_hint_y=.13)
        self.record_button = Button(text="Record name (1.8 seconds)",
                                    size_hint_y=.12)
        self.record_button.bind(on_release=self.record_next)
        self.finish_button = Button(text="Commit this AI's birth",
                                    size_hint_y=.12,disabled=True)
        self.finish_button.bind(on_release=self.finish)
        self.reset_button = Button(text="Delete enrollment and start over",
                                   size_hint_y=.10)
        self.reset_button.bind(on_release=self.reset)
        for w in (self.title_label,self.instruction,self.progress,self.status,
                  self.record_button,self.finish_button,self.reset_button):
            self.layout.add_widget(w)
        self.busy=False

    def on_enter(self, *args):
        self.refresh()

    def refresh(self):
        app=App.get_running_app()
        try:
            session=app.get_pending_enrollment()
        except Exception as e:
            self.status.text=str(e)
            self.record_button.disabled=True
            return
        counts=session.data["samples"]
        user_count=len(counts["user_name"])
        ai_count=len(counts["ai_name"])
        self.progress.text=f"Your name: {user_count}/3    AI name: {ai_count}/3"
        kind=session.next_target()
        if kind is None:
            self.instruction.text="All six recordings captured. You can now create your companion."
            self.record_button.disabled=True
            self.finish_button.disabled=False
        else:
            name=session.data["identity"]["user_name" if kind=="user_name" else "ai_name"]
            who="your name" if kind=="user_name" else "the AI's name"
            self.instruction.text=(
                f"Say {who}:  {name}\n\n"
                "Speak naturally. Each of the three takes can differ slightly. "
                "A usable microphone recording is required for every take.")
            self.record_button.disabled=self.busy
            self.finish_button.disabled=True
        if not self.status.text:
            self.status.text="Recordings are processed locally. Raw audio is not saved."

    def record_next(self, *args):
        if self.busy:
            return
        self.busy=True
        self.record_button.disabled=True
        self.status.text="Listening for your spoken name..."
        App.get_running_app().capture_enrollment_name(self._capture_finished)

    def _capture_finished(self, error=None):
        self.busy=False
        self.status.text=("Please retry: "+str(error)) if error else "Recording accepted."
        self.refresh()

    def finish(self, *args):
        if self.busy:
            return
        self.busy=True
        self.finish_button.disabled=True
        self.status.text="Creating your companion..."
        def do_commit(dt):
            try:
                App.get_running_app().finish_name_enrollment()
            except Exception as exc:
                self.status.text="Could not complete birth: "+str(exc)
                self.busy=False
                self.refresh()
        Clock.schedule_once(do_commit,0)

    def reset(self, *args):
        if self.busy:
            return
        App.get_running_app().reset_name_enrollment()
