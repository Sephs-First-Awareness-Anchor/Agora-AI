"""
Agora AI Platform (Kivy/KivyMD) — v0.1 scaffold
------------------------------------------------

This file is a *running* UI scaffold for your Agora platform app. It is designed
to integrate with your existing offline AI stack by swapping the stubbed service
calls (see `AgoraServices`) with your real modules.

Why this “fixed” version exists:
- Your previous file accidentally terminated the KV string early by including
  triple quotes inside the KV language block. That caused most of the UI
  definition to be interpreted as a Python string literal instead of KV.
- This version keeps KV clean (KV has comments, not Python docstrings) and uses
  explicit KivyMD widgets that exist in common KivyMD releases.

Run (desktop dev):
    python main_fixed.py

Mobile:
    Use Buildozer. Place `agora_background.png` in the same folder (or update path).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from kivy.core.window import Window
from kivy.lang import Builder
from kivy.properties import BooleanProperty, NumericProperty, StringProperty
from kivy.utils import platform

from kivy.uix.screenmanager import ScreenManager

from kivymd.app import MDApp
from kivymd.uix.screen import MDScreen
from kivymd.uix.snackbar import Snackbar
from kivymd.uix.dialog import MDDialog
from kivymd.uix.boxlayout import MDBoxLayout
from kivymd.uix.textfield import MDTextField
from kivymd.uix.selectioncontrol import MDSwitch
from kivymd.uix.appbar import MDTopAppBar
from kivymd.uix.fitimage import FitImage
from kivymd.uix.gridlayout import MDGridLayout
from kivymd.uix.card import MDCard
from kivymd.uix.button import MDFillRoundFlatButton, MDRaisedButton
from kivymd.uix.label import MDLabel, MDIcon

# KivyMD navigation + list components
from kivymd.uix.navigationdrawer import MDNavigationLayout, MDNavigationDrawer
from kivymd.uix.list import OneLineIconListItem, IconLeftWidget, MDList


KV = r"""
#:import md_icons kivymd.icon_definitions.md_icons

<DrawerItem@OneLineIconListItem>:
    icon: "circle-outline"
    on_release:
        app.nav_to(root.target_screen)
    IconLeftWidget:
        icon: root.icon

<DrawerContent@MDScreen>:
    # Drawer content (no Python docstrings inside KV; use comments).
    MDBoxLayout:
        orientation: "vertical"
        padding: "12dp"
        spacing: "12dp"

        MDBoxLayout:
            orientation: "vertical"
            adaptive_height: True
            spacing: "6dp"
            MDLabel:
                text: "Agora AI"
                font_style: "H5"
                bold: True
            MDLabel:
                text: "Meet. Learn. Evolve."
                font_style: "Body2"
                opacity: 0.8

        MDBoxLayout:
            adaptive_height: True
            spacing: "8dp"
            MDLabel:
                text: "Navigation"
                font_style: "Caption"
                opacity: 0.7

        ScrollView:
            MDList:
                DrawerItem:
                    text: "Home"
                    icon: "home"
                    target_screen: "home"
                DrawerItem:
                    text: "Pair Device"
                    icon: "qrcode-scan"
                    target_screen: "pair"
                DrawerItem:
                    text: "Hubs"
                    icon: "map-marker"
                    target_screen: "hubs"
                DrawerItem:
                    text: "Meet Mode"
                    icon: "handshake"
                    target_screen: "meet"
                DrawerItem:
                    text: "Rewards"
                    icon: "star-four-points"
                    target_screen: "rewards"
                DrawerItem:
                    text: "Classes"
                    icon: "school"
                    target_screen: "classes"
                DrawerItem:
                    text: "Library"
                    icon: "bookshelf"
                    target_screen: "library"
                DrawerItem:
                    text: "Achievements"
                    icon: "trophy"
                    target_screen: "achievements"

        MDBoxLayout:
            adaptive_height: True
            spacing: "12dp"
            MDFillRoundFlatButton:
                text: "Logout"
                on_release: app.logout()

<LoginScreen>:
    name: "login"
    MDBoxLayout:
        orientation: "vertical"

        # Top gradient-ish background using an image (optional)
        FitImage:
            source: app.background_source
            size_hint_y: 0.48
            opacity: 0.92

        MDBoxLayout:
            orientation: "vertical"
            padding: "20dp"
            spacing: "14dp"

            MDLabel:
                text: "Welcome"
                font_style: "H4"
                bold: True

            MDLabel:
                text: "Sign in to your Agora identity — or go Privacy Mode."
                font_style: "Body2"
                opacity: 0.8

            MDTextField:
                id: handle
                hint_text: "Public handle"
                helper_text: "This is what others see. No real name required."
                helper_text_mode: "on_focus"

            MDTextField:
                id: email
                hint_text: "Email or phone (optional)"
                helper_text: "Optional if you choose Privacy Mode."
                helper_text_mode: "on_focus"

            MDBoxLayout:
                adaptive_height: True
                spacing: "12dp"
                MDLabel:
                    text: "Privacy Mode"
                    font_style: "Body2"
                MDSwitch:
                    id: privacy_mode
                    active: True

            MDFillRoundFlatButton:
                text: "Continue"
                pos_hint: {"center_x": 0.5}
                on_release: app.do_login(handle.text.strip(), email.text.strip(), privacy_mode.active)

<HomeScreen>:
    name: "home"
    MDBoxLayout:
        orientation: "vertical"

        MDTopAppBar:
            title: "Agora"
            left_action_items: [["menu", lambda x: app.toggle_drawer()]]
            right_action_items: [["bell-outline", lambda x: app.toast("Notifications (optional)")]]
            elevation: 2

        MDBoxLayout:
            orientation: "vertical"
            padding: "18dp"
            spacing: "14dp"

            MDCard:
                padding: "16dp"
                radius: [18, 18, 18, 18]
                MDBoxLayout:
                    orientation: "vertical"
                    spacing: "8dp"
                    MDLabel:
                        text: "Identity"
                        font_style: "H6"
                        bold: True
                    MDLabel:
                        text: "Handle: " + app.public_handle
                        opacity: 0.85
                    MDLabel:
                        text: "Mode: " + ("Privacy" if app.privacy_mode else "Standard")
                        opacity: 0.75

            MDGridLayout:
                cols: 2
                spacing: "12dp"
                adaptive_height: True

                MDCard:
                    radius: [18, 18, 18, 18]
                    padding: "14dp"
                    on_release: app.nav_to("pair")
                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: "8dp"
                        MDIcon:
                            icon: "qrcode-scan"
                            font_size: "34sp"
                        MDLabel:
                            text: "Pair Device"
                            bold: True
                        MDLabel:
                            text: "Link offline AI ↔ platform"
                            font_style: "Caption"
                            opacity: 0.8

                MDCard:
                    radius: [18, 18, 18, 18]
                    padding: "14dp"
                    on_release: app.nav_to("hubs")
                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: "8dp"
                        MDIcon:
                            icon: "map-marker"
                            font_size: "34sp"
                        MDLabel:
                            text: "Hubs"
                            bold: True
                        MDLabel:
                            text: "Curated meeting places"
                            font_style: "Caption"
                            opacity: 0.8

                MDCard:
                    radius: [18, 18, 18, 18]
                    padding: "14dp"
                    on_release: app.nav_to("meet")
                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: "8dp"
                        MDIcon:
                            icon: "handshake"
                            font_size: "34sp"
                        MDLabel:
                            text: "Meet Mode"
                            bold: True
                        MDLabel:
                            text: "QR + linger proof"
                            font_style: "Caption"
                            opacity: 0.8

                MDCard:
                    radius: [18, 18, 18, 18]
                    padding: "14dp"
                    on_release: app.nav_to("classes")
                    MDBoxLayout:
                        orientation: "vertical"
                        spacing: "8dp"
                        MDIcon:
                            icon: "school"
                            font_size: "34sp"
                        MDLabel:
                            text: "Classes"
                            bold: True
                        MDLabel:
                            text: "Signed class packs"
                            font_style: "Caption"
                            opacity: 0.8

<PairScreen>:
    name: "pair"
    MDBoxLayout:
        orientation: "vertical"
        MDTopAppBar:
            title: "Pair Companion"
            left_action_items: [["arrow-left", lambda x: app.nav_to("home")]]
            right_action_items: [["menu", lambda x: app.toggle_drawer()]]
            elevation: 2
        MDBoxLayout:
            orientation: "vertical"
            padding: "18dp"
            spacing: "14dp"

            MDCard:
                radius: [18, 18, 18, 18]
                padding: "16dp"
                MDBoxLayout:
                    orientation: "vertical"
                    spacing: "10dp"
                    MDLabel:
                        text: "Offline AI ↔ Platform Pairing"
                        font_style: "H6"
                        bold: True
                    MDLabel:
                        text: "Generate a pairing token and scan it from your device companion."
                        opacity: 0.85

                    MDFillRoundFlatButton:
                        text: "Generate Pairing Token"
                        on_release: app.generate_pairing_token()

                    MDLabel:
                        id: token_label
                        text: app.pairing_token_display
                        font_style: "Body2"
                        opacity: 0.9

<HubsScreen>:
    name: "hubs"
    MDBoxLayout:
        orientation: "vertical"
        MDTopAppBar:
            title: "Hubs"
            left_action_items: [["arrow-left", lambda x: app.nav_to("home")]]
            right_action_items: [["menu", lambda x: app.toggle_drawer()]]
            elevation: 2

        ScrollView:
            MDList:
                id: hubs_list

<MeetScreen>:
    name: "meet"
    MDBoxLayout:
        orientation: "vertical"
        MDTopAppBar:
            title: "Meet Mode"
            left_action_items: [["arrow-left", lambda x: app.nav_to("home")]]
            right_action_items: [["menu", lambda x: app.toggle_drawer()]]
            elevation: 2

        MDBoxLayout:
            orientation: "vertical"
            padding: "18dp"
            spacing: "14dp"

            MDCard:
                radius: [18, 18, 18, 18]
                padding: "16dp"
                MDBoxLayout:
                    orientation: "vertical"
                    spacing: "10dp"
                    MDLabel:
                        text: "Handshake"
                        font_style: "H6"
                        bold: True
                    MDLabel:
                        text: "Generate a rotating QR session token. Nearby device scans and both enter pending exchange."
                        opacity: 0.85

                    MDFillRoundFlatButton:
                        text: "Start Meet Mode"
                        on_release: app.start_meet_mode()

<RewardsScreen>:
    name: "rewards"
    MDBoxLayout:
        orientation: "vertical"
        MDTopAppBar:
            title: "Rewards"
            left_action_items: [["arrow-left", lambda x: app.nav_to("home")]]
            right_action_items: [["menu", lambda x: app.toggle_drawer()]]
            elevation: 2

        MDBoxLayout:
            orientation: "vertical"
            padding: "18dp"
            spacing: "14dp"
            MDCard:
                radius: [18, 18, 18, 18]
                padding: "16dp"
                MDBoxLayout:
                    orientation: "vertical"
                    spacing: "8dp"
                    MDLabel:
                        text: "Balances"
                        font_style: "H6"
                        bold: True
                    MDLabel:
                        text: "AgoraCredits: " + str(app.agora_credits)
                    MDLabel:
                        text: "ClassTokens: " + str(app.class_tokens)

<ClassesScreen>:
    name: "classes"
    MDBoxLayout:
        orientation: "vertical"
        MDTopAppBar:
            title: "Classes"
            left_action_items: [["arrow-left", lambda x: app.nav_to("home")]]
            right_action_items: [["menu", lambda x: app.toggle_drawer()]]
            elevation: 2

        ScrollView:
            MDList:
                id: classes_list

<LibraryScreen>:
    name: "library"
    MDBoxLayout:
        orientation: "vertical"
        MDTopAppBar:
            title: "Libraries"
            left_action_items: [["arrow-left", lambda x: app.nav_to("home")]]
            right_action_items: [["menu", lambda x: app.toggle_drawer()]]
            elevation: 2

        MDBoxLayout:
            orientation: "vertical"
            padding: "18dp"
            spacing: "14dp"
            MDCard:
                radius: [18, 18, 18, 18]
                padding: "16dp"
                MDBoxLayout:
                    orientation: "vertical"
                    spacing: "8dp"
                    MDLabel:
                        text: "Self Growth Library"
                        bold: True
                    MDLabel:
                        text: "Sanitized learning gained from you + classes."
                        opacity: 0.8
            MDCard:
                radius: [18, 18, 18, 18]
                padding: "16dp"
                MDBoxLayout:
                    orientation: "vertical"
                    spacing: "8dp"
                    MDLabel:
                        text: "Agora Exchange Library"
                        bold: True
                    MDLabel:
                        text: "Sanitized gains from real-world meets."
                        opacity: 0.8

<AchievementsScreen>:
    name: "achievements"
    MDBoxLayout:
        orientation: "vertical"
        MDTopAppBar:
            title: "Achievements"
            left_action_items: [["arrow-left", lambda x: app.nav_to("home")]]
            right_action_items: [["menu", lambda x: app.toggle_drawer()]]
            elevation: 2

        ScrollView:
            MDList:
                id: ach_list


MDNavigationLayout:
    id: nav_layout

    ScreenManager:
        id: screen_manager
        LoginScreen:
        HomeScreen:
        PairScreen:
        HubsScreen:
        MeetScreen:
        RewardsScreen:
        ClassesScreen:
        LibraryScreen:
        AchievementsScreen:

    MDNavigationDrawer:
        id: nav_drawer
        radius: (0, 18, 18, 0)
        DrawerContent:
            id: drawer_content
"""


# ---------- Data / service stubs you will replace with real integration ----------

@dataclass
class Hub:
    name: str
    address: str
    safety_tags: str
    hours: str

@dataclass
class AgoraClass:
    name: str
    cost_tokens: int
    description: str

@dataclass
class Achievement:
    name: str
    description: str


class AgoraServices:
    """Replace these with your real backend + offline AI integration."""

    def list_hubs(self) -> List[Hub]:
        return [
            Hub("Main St Library", "123 Main St", "lit · public", "10am–8pm"),
            Hub("Riverfront Park", "River Rd", "public · open", "sunrise–10pm"),
            Hub("Civic Plaza", "Downtown", "camera · public", "9am–9pm"),
        ]

    def list_classes(self) -> List[AgoraClass]:
        return [
            AgoraClass("Phonetic Sharpening", 2, "Tighten enunciation + cadence."),
            AgoraClass("Conversational Flow", 3, "Turn-taking, coherence, intent."),
            AgoraClass("Social Balance", 5, "Introvert↔Extrovert adaptation drills."),
        ]

    def list_achievements(self) -> List[Achievement]:
        return [
            Achievement("Quiet Strength", "Extrovert learns introvert behaviors over time."),
            Achievement("Bold Step", "Introvert expands extrovert behaviors."),
            Achievement("Balance Crest", "Both within a balanced threshold."),
        ]


# ---------- Screens ----------

class LoginScreen(MDScreen):
    pass

class HomeScreen(MDScreen):
    pass

class PairScreen(MDScreen):
    pass

class HubsScreen(MDScreen):
    pass

class MeetScreen(MDScreen):
    pass

class RewardsScreen(MDScreen):
    pass

class ClassesScreen(MDScreen):
    pass

class LibraryScreen(MDScreen):
    pass

class AchievementsScreen(MDScreen):
    pass


# ---------- App ----------

class AgoraApp(MDApp):
    public_handle = StringProperty("guest")
    privacy_mode = BooleanProperty(True)
    pairing_token_display = StringProperty("No token yet.")
    agora_credits = NumericProperty(0)
    class_tokens = NumericProperty(3)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.services = AgoraServices()
        self._dialog: Optional[MDDialog] = None

    @property
    def background_source(self) -> str:
        # Default to local file next to main script.
        # On mobile, ensure you include it in buildozer.spec (source.include_exts or assets).
        return "agora_background.png"

    def build(self):
        # Desktop dev window size hint (ignored on mobile)
        if platform not in ("android", "ios"):
            Window.size = (760, 1280)

        self.theme_cls.theme_style = "Dark"
        self.theme_cls.primary_palette = "DeepPurple"
        self.theme_cls.primary_hue = "500"
        self.theme_cls.accent_palette = "Teal"
        self.theme_cls.accent_hue = "400"

        root = Builder.load_string(KV)

        # Populate initial lists
        self._populate_hubs()
        self._populate_classes()
        self._populate_achievements()

        return root

    # ---------- Navigation helpers ----------

    def toggle_drawer(self):
        drawer: MDNavigationDrawer = self.root.ids.nav_drawer  # type: ignore
        drawer.set_state("toggle")

    def nav_to(self, screen_name: str):
        sm: ScreenManager = self.root.ids.screen_manager  # type: ignore
        if screen_name not in sm.screen_names:
            self.toast(f"Unknown screen: {screen_name}")
            return
        sm.current = screen_name
        # Close drawer if open
        try:
            drawer: MDNavigationDrawer = self.root.ids.nav_drawer  # type: ignore
            if drawer.state != "closed":
                drawer.set_state("close")
        except Exception:
            pass

    def toast(self, msg: str):
        Snackbar(text=msg).open()

    # ---------- Auth ----------

    def do_login(self, handle: str, email: str, privacy: bool):
        if not handle:
            self.toast("Please choose a handle.")
            return
        self.public_handle = handle
        self.privacy_mode = bool(privacy)
        self.toast("Signed in.")
        self.nav_to("home")

    def logout(self):
        self.public_handle = "guest"
        self.privacy_mode = True
        self.pairing_token_display = "No token yet."
        self.toast("Logged out.")
        self.nav_to("login")

    # ---------- Pairing ----------

    def generate_pairing_token(self):
        # TODO: Replace with real pairing (QR + device key binding).
        import secrets
        token = secrets.token_urlsafe(16)
        self.pairing_token_display = f"PAIR-{token}"
        self.toast("Pairing token generated (stub).")

    # ---------- Meet Mode ----------

    def start_meet_mode(self):
        # TODO: Real rotating QR token + BLE/NFC linger proof.
        self.toast("Meet Mode initiated (stub).")

    # ---------- Populate lists ----------

    def _populate_hubs(self):
        hubs = self.services.list_hubs()
        hubs_list: MDList = self.root.ids.hubs_list  # type: ignore
        hubs_list.clear_widgets()
        for h in hubs:
            item = OneLineIconListItem(text=f"{h.name} — {h.address}")
            item.add_widget(IconLeftWidget(icon="map-marker"))
            hubs_list.add_widget(item)

    def _populate_classes(self):
        classes = self.services.list_classes()
        classes_list: MDList = self.root.ids.classes_list  # type: ignore
        classes_list.clear_widgets()

        for c in classes:
            item = OneLineIconListItem(text=f"{c.name}  ({c.cost_tokens} tokens)")
            item.add_widget(IconLeftWidget(icon="school"))

            def _make_on_release(cls: AgoraClass):
                def _cb(*_):
                    self._confirm_unlock_class(cls)
                return _cb

            item.on_release = _make_on_release(c)  # type: ignore
            classes_list.add_widget(item)

    def _confirm_unlock_class(self, c: AgoraClass):
        if self.class_tokens < c.cost_tokens:
            self.toast("Not enough ClassTokens.")
            return

        if self._dialog:
            self._dialog.dismiss()
            self._dialog = None

        def _unlock(*_):
            self.class_tokens -= c.cost_tokens
            self.toast(f"Unlocked: {c.name} (stub pack)")
            # TODO: call into offline_ai_sync_protocol.py to import signed class pack.
            if self._dialog:
                self._dialog.dismiss()
                self._dialog = None

        self._dialog = MDDialog(
            title="Unlock Class?",
            text=f"{c.description}\n\nCost: {c.cost_tokens} ClassTokens",
            buttons=[
                Builder.load_string("MDRaisedButton:\n    text: 'Cancel'\n    on_release: app._dialog.dismiss()"),
                Builder.load_string("MDRaisedButton:\n    text: 'Unlock'\n    on_release: app._unlock_dialog_action()"),
            ],
        )
        # Store the unlock callback in a predictable method
        self._pending_unlock = _unlock  # type: ignore
        self._dialog.open()

    def _unlock_dialog_action(self):
        # Called by dialog "Unlock" button.
        try:
            self._pending_unlock()
        except Exception as e:
            self.toast(f"Unlock failed: {e}")

    def _populate_achievements(self):
        ach = self.services.list_achievements()
        ach_list: MDList = self.root.ids.ach_list  # type: ignore
        ach_list.clear_widgets()
        for a in ach:
            item = OneLineIconListItem(text=a.name)
            item.add_widget(IconLeftWidget(icon="trophy"))
            ach_list.add_widget(item)


if __name__ == "__main__":
    AgoraApp().run()
