"""Offline selector, PCM enrollment, one-time birth and learning contracts.

Generated waveforms test signal processing only. Android microphone/ASR
capabilities are deliberately NOT claimed validated by these tests.
"""
import tempfile
import unittest
from pathlib import Path

import numpy as np

from engine.agora_birth import (
    AXES, MAX_BONUS, BirthStore, agreement_reinforce, aptitude_vector,
    dob_vote, name_vote, normalize_name, select_birth, _ONBOARDING_PAIR_RING,
)
from engine.agora_enrollment import (
    EnrollmentSession, NameLearningStore, extract_audio_features,
    pronunciation_consensus,
)
from engine.agora_sync.offline_ai_capabilities import (
    SpecializationProfile,
)
from engine.offline_ai_expression import BOOT_PERSONAS


def pcm_for(freq=190, length=1.1, sr=16000):
    t = np.arange(int(length*sr),dtype=np.float64)/sr
    env = (0.10 + 0.9*np.sin(np.pi*t/length)**2)
    sig = 0.35*env*(np.sin(2*np.pi*freq*t) +
                    0.10*np.sin(2*np.pi*freq*2.0*t))
    return (sig*32767).astype("<i2").tobytes()


def sample_pronunciation():
    with tempfile.TemporaryDirectory() as root:
        session=EnrollmentSession(Path(root)/"pending.json",
            {"user_name":"Tester","ai_name":"Sunni","mode":"extrovert",
             "color":"green","dob":"July 31"})
        for kind in ("user_name","ai_name"):
            for i in range(3):
                session.add_pcm(kind,pcm_for(180+i if kind=="user_name" else 260+i))
        return session.result()


class TestAgreement(unittest.TestCase):
    def test_coherent_sources_add_bounded_bonus_once_per_group(self):
        vote={k:.7 for k in AXES}
        groups={"ai_name":vote,"color":vote,"dob_archetype":vote}
        combined,bonus=agreement_reinforce(groups)
        self.assertTrue(0<bonus["curiosity"]<=MAX_BONUS)
        self.assertGreater(combined["curiosity"],.7)
        # Extra recordings of one AI name must still be ONE source group.
        self.assertEqual(combined,agreement_reinforce(dict(groups))[0])

    def test_opposition_is_not_falsely_reinforced(self):
        positive={k:.7 for k in AXES}
        negative={k:-.7 for k in AXES}
        _,bonus=agreement_reinforce({"ai_name":positive,"color":negative})
        self.assertEqual(bonus["curiosity"],0)
        almost_zero={k:0. for k in AXES}
        combined,bonus=agreement_reinforce({"ai_name":almost_zero})
        self.assertEqual(bonus["curiosity"],0)
        self.assertEqual(combined["curiosity"],0)

    def test_missing_sources_renormalize(self):
        same={k:.6 for k in AXES}
        x,_=agreement_reinforce({"ai_name":same})
        self.assertAlmostEqual(x["empathy"],.6)


class TestBirthModels(unittest.TestCase):
    def test_thirteen_families_26_orders_and_52_modes(self):
        self.assertEqual(len(_ONBOARDING_PAIR_RING),13)
        outcomes=set()
        for a,b in _ONBOARDING_PAIR_RING:
            self.assertNotEqual(a,b)
            for mode in ("introvert","extrovert"):
                for x,y in ((a,b),(b,a)):
                    outcomes.add((x,y,mode))
                    gain=SpecializationProfile(x,y,mode).get_gain_vector()
                    inverted=SpecializationProfile(y,x,mode).get_gain_vector()
                    self.assertNotEqual(gain,inverted)
        self.assertEqual(len(outcomes),52)

    def test_personas_respect_real_mode_metadata(self):
        eligible={mode:{k for k,v in BOOT_PERSONAS.items()
                        if v.get("mode") in ("both",mode)}
                  for mode in ("introvert","extrovert")}
        self.assertEqual(len(eligible["introvert"]),17)
        self.assertEqual(len(eligible["extrovert"]),24)
        pron=sample_pronunciation()
        for mode in eligible:
            outcome=select_birth("Sunni",mode,"green","July 31",
                ai_pronunciation=pron["ai_pronunciation"],
                user_enrollment_complete=True)
            self.assertIn(outcome.persona_key,eligible[mode])
            self.assertEqual(outcome.mode,mode)

    def test_fingerprint_not_selected_by_account_identifier(self):
        audio=sample_pronunciation()["ai_pronunciation"]
        kw=dict(ai_name="Sunni",mode="extrovert",color="green",dob="July 31",
                ai_pronunciation=audio,user_enrollment_complete=True)
        a=select_birth(**kw)
        b=select_birth(**kw)
        self.assertEqual(a.to_dict(),b.to_dict())
        c=select_birth(ai_name="  SUNNI  ",mode="extrovert",color="green",
                dob="July 31",ai_pronunciation=audio,user_enrollment_complete=True)
        self.assertEqual((a.primary,a.secondary,a.persona_key),
                         (c.primary,c.secondary,c.persona_key))

    def test_separate_mode_and_audio_requirement(self):
        p=sample_pronunciation()["ai_pronunciation"]
        with self.assertRaises(ValueError):
            select_birth("Sunni","ambivert",ai_pronunciation=p,
                         user_enrollment_complete=True)
        with self.assertRaises(ValueError):
            select_birth("Sunni","introvert",ai_pronunciation=p,
                         user_enrollment_complete=False)

    def test_dob_is_weak_optional_creative_cue(self):
        self.assertIsNone(dob_vote(""))
        self.assertIsNone(dob_vote("not a birthday"))
        self.assertEqual(dob_vote("July 31"),dob_vote("July 31, 2024"))
        self.assertIsNotNone(dob_vote("2024-02-29"))
        self.assertIsNotNone(dob_vote("2025-02-28"))
        a=dob_vote("July 22")
        b=dob_vote("July 23")
        self.assertLess(max(abs(a[k]-b[k]) for k in AXES),1.1)

    def test_unicode_names_and_length_normalization(self):
        self.assertEqual(normalize_name("  SUÑÑI  "),"suññi")
        for name in ("Σοφία","Renée","Jéhan","K'aï","X","Fable-900"):
            vector=name_vote(name)
            self.assertEqual(set(vector),set(AXES))
            self.assertTrue(all(-1<=x<=1 for x in vector.values()))

    def test_exactly_once_birth_commit(self):
        birth=select_birth("Sunni","introvert",require_audio=False)
        different=select_birth("Maya","extrovert",require_audio=False)
        with tempfile.TemporaryDirectory() as root:
            store=BirthStore(Path(root)/"acct")
            first=store.commit(birth)
            second=store.commit(different)
            self.assertEqual(first,second)
            self.assertEqual(store.read(),first)
            self.assertTrue(first["committed_at"])


class TestAudioEnrollment(unittest.TestCase):
    def test_real_pcm_features_required_not_transcripts(self):
        with self.assertRaises(ValueError):
            extract_audio_features(b"not speech text")
        with self.assertRaises(ValueError):
            extract_audio_features(b"\x00\x00"*16000)
        feature=extract_audio_features(pcm_for())
        self.assertEqual(feature["source"],"pcm")
        self.assertGreater(feature["duration_ms"],1000)
        self.assertGreater(feature["rms"],0)

    def test_six_observations_resume_and_no_seventh(self):
        with tempfile.TemporaryDirectory() as root:
            path=Path(root)/"pending.json"
            identity={"user_name":"Tester","ai_name":"Sunni","mode":"introvert",
                      "color":"green","dob":""}
            s=EnrollmentSession(path,identity)
            with self.assertRaises(ValueError):
                s.result()
            s.add_pcm("user_name",pcm_for(190))
            resumed=EnrollmentSession(path,identity)
            self.assertEqual(len(resumed.data["samples"]["user_name"]),1)
            for _ in range(2):
                resumed.add_pcm("user_name",pcm_for(190))
            for _ in range(3):
                resumed.add_pcm("ai_name",pcm_for(270))
            self.assertTrue(resumed.ready())
            result=resumed.result()
            self.assertEqual(result["ai_pronunciation"]["count"],3)
            self.assertEqual(result["provisional_speaker"]["not_authorization"],True)
            with self.assertRaises(ValueError):
                resumed.add_pcm("ai_name",pcm_for())
            resumed.stage_account("one","serial")
            resumed.mark_committed("one","serial")
            self.assertEqual(EnrollmentSession(path).data["state"],"BIRTH_COMMITTED")

    def test_local_voice_data_can_be_erased_without_rebirth(self):
        result=sample_pronunciation()
        with tempfile.TemporaryDirectory() as root:
            store=NameLearningStore(root)
            ident={"user_name":"Tester","ai_name":"Sunni"}
            stored=store.seed_once(ident,result)
            self.assertEqual(stored["speakers"]["owner"]["status"],"provisional")
            match,_=store.classify_speaker_pcm(pcm_for(190))
            self.assertIn(match,("unknown","provisional_owner"))
            birth=BirthStore(root).commit(
                select_birth("Sunni","introvert",require_audio=False))
            store.delete_voice_data()
            self.assertIsNone(NameLearningStore(root).data)
            self.assertEqual(BirthStore(root).read(),birth)


if __name__ == "__main__":
    unittest.main()
