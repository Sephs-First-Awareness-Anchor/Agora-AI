#!/usr/bin/env python3
"""
Agora AI - Learned Response Composer tests
==========================================

Authored by Sunni (Sir) Morningstar and Cael Devo.

Checks that learned language reaches replies:
- per-AI variation profile (specialization pair + ability multipliers) is seeded and persisted
- learned words, associations and name casing show up in composed replies
- feedback trains move fitness and learns reusable reply templates with separate slots
- composer state survives a save and reload
"""

import shutil
import tempfile
import unittest
from pathlib import Path

from engine.offline_ai_expression import LexiconManager, SelfGenerativeEvolution
from engine.offline_ai_response_composer import (
    ABILITY_MULTIPLIER_RANGE, AIVariationProfile, LEARNING_DOMAINS,
    LearnedResponseComposer, generalize_reply,
)

TALK = [
    "my dog Deeni loves the park",
    "the park was sunny and my dog ran",
    "I taught Deeni a new trick at the park",
    "Deeni is a good dog",
    "we walked to the park again",
]


def _seed_lines(intent, user_name):
    return [f"Thanks for sharing that with me, {user_name}."]


class ComposerTestBase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.lexicon = LexiconManager(str(self.tmp / "lexicon"))
        self.evolution = SelfGenerativeEvolution(str(self.tmp / "evolution"))
        self.composer = self._make_composer()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_composer(self, seed_source="test-ai"):
        return LearnedResponseComposer(
            str(self.tmp / "composer"), seed_source=seed_source,
            lexicon=self.lexicon, evolution=self.evolution, seed_lines=_seed_lines,
        )

    def converse(self, turns, satisfaction=0.9):
        replies = []
        for i in range(turns):
            text = TALK[i % len(TALK)]
            self.lexicon.process_text(text, "INFORM")
            self.composer.observe_user_turn("INFORM", text)
            replies.append(self.composer.compose("INFORM", text, "Sunni"))
            self.composer.record_feedback(satisfaction)
        return replies


class TestVariationProfile(unittest.TestCase):
    def test_same_seed_same_profile_different_seed_differs(self):
        a = AIVariationProfile.generate("account-a")
        self.assertEqual(a.to_dict(), AIVariationProfile.generate("account-a").to_dict())
        others = [AIVariationProfile.generate(f"account-{i}").to_dict() for i in range(8)]
        self.assertTrue(any(o != a.to_dict() for o in others))

    def test_multipliers_in_range_for_every_domain(self):
        profile = AIVariationProfile.generate("range-check")
        low, high = ABILITY_MULTIPLIER_RANGE
        for domain in LEARNING_DOMAINS:
            self.assertGreaterEqual(profile.ability_multipliers[domain], low)
            self.assertLessEqual(profile.ability_multipliers[domain], high)
        self.assertNotEqual(profile.primary, profile.secondary)

    def test_profile_persists(self):
        tmp = Path(tempfile.mkdtemp())
        try:
            first = AIVariationProfile.load_or_create(tmp, "persist")
            again = AIVariationProfile.load_or_create(tmp, "a different seed")
            self.assertEqual(first.to_dict(), again.to_dict())
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class TestGeneralizeReply(unittest.TestCase):
    def test_each_learned_word_gets_its_own_slot(self):
        template = generalize_reply(
            "That makes me think of Deeni. You always bring it up with park.",
            {"topic": "park", "assoc": "deeni"})
        self.assertEqual(template, "That makes me think of {assoc}. You always bring it up with {topic}.")

    def test_sentence_start_keeps_capital_slot(self):
        self.assertEqual(generalize_reply("Park again? Tell me more!", {"topic": "park"}),
                         "{Topic} again? Tell me more!")

    def test_rejects_template_with_baked_in_learned_word(self):
        self.assertIsNone(generalize_reply("So park and dog.", {"topic": "park"}, ["dog"]))


class TestLearnedReplies(ComposerTestBase):
    def test_learned_words_reach_replies(self):
        replies = self.converse(30)
        later = " ".join(replies[15:]).lower()
        self.assertTrue(any(w in later for w in ("deeni", "park", "dog")))
        self.assertGreater(len(set(replies)), 5)

    def test_names_keep_the_users_capitals(self):
        replies = self.converse(40)
        for reply in replies:
            self.assertNotRegex(reply, r"(?<![.!?] )(?<!^)\bdeeni\b")

    def test_feedback_learns_reply_templates(self):
        self.converse(30)
        templates = self.evolution.template_learner.get_templates("language", "INFORM_reply")
        self.assertTrue(templates)
        for template in templates:
            self.assertIn("{", template)
            self.assertNotIn("deeni", template.lower())

    def test_thanks_gets_a_thanks_shaped_reply(self):
        self.converse(30)
        text = "thanks for telling me about Deeni"
        self.lexicon.process_text(text, "THANK")
        reply = self.composer.compose("THANK", text, "Sunni")
        self.assertNotIn("Tell me what that is", reply)

    def test_low_satisfaction_lowers_move_fitness(self):
        self.converse(12)
        move = self.composer._last["move"]
        before = self.composer.move_fitness[move]
        self.composer.record_feedback(0.0)
        self.assertLess(self.composer.move_fitness[move], before)

    def test_state_survives_reload(self):
        self.converse(20)
        self.composer.save_state()
        reloaded = self._make_composer(seed_source="ignored after first save")
        self.assertEqual(reloaded.profile.to_dict(), self.composer.profile.to_dict())
        self.assertEqual(reloaded.memory.to_dict(), self.composer.memory.to_dict())
        self.assertEqual(reloaded.move_fitness, self.composer.move_fitness)


if __name__ == "__main__":
    unittest.main()
