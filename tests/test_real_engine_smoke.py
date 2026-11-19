"""Headless check of an actual OfflineAI birth, learned response and persistence."""
import tempfile
import unittest
from pathlib import Path

from engine.agora_sync.offline_ai_capabilities import onboarding_specialization
from engine.offline_ai_core import OfflineAI
from engine.offline_ai_expression import OnboardingProfile


class TestRealEngineCommunication(unittest.TestCase):
    def test_named_companion_initializes_and_generates_a_reply(self):
        with tempfile.TemporaryDirectory() as root:
            birth = OnboardingProfile(
                user_name="Tester", ai_name="Sunni",
                favorite_color="green", mode="extrovert")
            ai = OfflineAI(
                account_id="integration-01",
                serial_code="AGORA-INTEGRATION-01",
                storage_dir=root,
                onboarding_profile=birth)
            try:
                composer = ai.response_composer
                self.assertIsNotNone(composer)
                pair = onboarding_specialization("Sunni", "extrovert")
                self.assertEqual((composer.profile.primary, composer.profile.secondary),
                                 (pair.primary, pair.secondary))
                self.assertEqual(composer.profile.behavior_mode, "extrovert")
                ai.set_mode(extrovert=True)
                analysis = ai.process_input("My dog Deeni loves the garden today")
                self.assertFalse(analysis.get("ignored", False))
                reply = ai.compose_reply(analysis)
                self.assertIsInstance(reply, str)
                self.assertTrue(reply.strip())
                expressed = ai.generate_response(analysis, reply)
                final_text = expressed.get("text", "") if isinstance(expressed, dict) else expressed
                self.assertTrue(final_text.strip())
                self.assertTrue(ai.is_extrovert)
                self.assertEqual(ai.user_name, "Tester")
            finally:
                ai.shutdown()

            saved = Path(root) / "integration-01" / "composer" / "variation_profile.json"
            self.assertTrue(saved.exists())


if __name__ == "__main__":
    unittest.main()
