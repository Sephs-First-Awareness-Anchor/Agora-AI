"""Headless check of an actual OfflineAI birth, learned response and persistence."""
import tempfile
import unittest
from pathlib import Path

from engine.agora_birth import BirthStore, select_birth
from tests.test_unified_birth import sample_pronunciation
from engine.offline_ai_core import OfflineAI
from engine.offline_ai_expression import OnboardingProfile


class TestRealEngineCommunication(unittest.TestCase):
    def test_named_companion_initializes_and_generates_a_reply(self):
        with tempfile.TemporaryDirectory() as root:
            birth = OnboardingProfile(
                user_name="Tester", ai_name="Sunni",
                favorite_color="green", mode="extrovert")
            acoustic=sample_pronunciation()
            decision=select_birth(
                "Sunni","extrovert",color="green",dob="July 31",
                ai_pronunciation=acoustic["ai_pronunciation"],
                user_enrollment_complete=True)
            committed=BirthStore(Path(root)/"integration-01").commit(decision)
            birth.birth_record=committed
            ai = OfflineAI(
                account_id="integration-01",
                serial_code="AGORA-INTEGRATION-01",
                storage_dir=root,
                onboarding_profile=birth)
            try:
                composer = ai.response_composer
                self.assertIsNotNone(composer)
                self.assertEqual(
                    (composer.profile.primary.value, composer.profile.secondary.value),
                    (committed["primary"], committed["secondary"]))
                self.assertEqual(committed["persona_key"],
                                 decision.persona_key)
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
