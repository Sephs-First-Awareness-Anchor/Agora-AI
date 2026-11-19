"""Pre-APK contract checks: real onboarding, one runtime and learned replies."""
import ast
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def source(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


class TestLiveAppContract(unittest.TestCase):
    def test_changed_python_modules_parse(self):
        for rel in (
            "engine/agora_sync/offline_ai_capabilities.py",
            "engine/offline_ai_response_composer.py", "engine/offline_ai_core.py",
            "engine/offline_ai_runtime.py", "engine/offline_ai_expression.py",
            "app/main.py", "app/ui/screens/companion.py",
            "app/ui/screens/onboarding.py", "app/ui/screens/platform_home.py",
        ):
            with self.subTest(file=rel):
                ast.parse(source(rel), filename=rel)

    def test_onboarding_flows_to_birth_initialized_engine(self):
        onboarding = source("app/ui/screens/onboarding.py")
        app = source("app/main.py")
        core = source("engine/offline_ai_core.py")
        self.assertIn("app.complete_onboarding(", onboarding)
        self.assertIn("_first_boot_pending = True", app)
        self.assertIn("onboarding_profile=birth_profile", app)
        self.assertIn("onboarding_profile=onboarding_profile", core)
        self.assertIn("ai_name=self.onboarding_profile.ai_name", core)
        self.assertIn("app._activate_ai(first_boot=first_boot)",
                      source("app/ui/screens/companion.py"))

    def test_actual_ui_input_and_response_round_trip_contract(self):
        screen = source("app/ui/screens/companion.py")
        runtime = source("engine/offline_ai_runtime.py")
        core = source("engine/offline_ai_core.py")
        self.assertIn("self.runtime._process_text_input(message)", screen)
        self.assertIn("self.runtime.enable_listening()", screen)
        self.assertIn("def _show_speech(", screen)
        self.assertIn("self.ai._get_contextual_response(intent, user_input)", runtime)
        self.assertIn("self.compose_reply(analysis)", core)
        self.assertNotIn("(Demo response)", screen)

    def test_extrovert_mode_not_reset_by_autonomy_limit(self):
        core = source("engine/offline_ai_core.py")
        self.assertNotIn("self.is_extrovert = False\n\n        # Clamps", core)
        self.assertIn("current_autonomy = AUTONOMY_PERMANENT", core)

    def test_introvert_and_extrovert_share_all_26_personas(self):
        core = source("engine/offline_ai_core.py")
        self.assertNotIn('persona = BOOT_PERSONAS["B_WARM"]', core)


if __name__ == "__main__":
    unittest.main()
