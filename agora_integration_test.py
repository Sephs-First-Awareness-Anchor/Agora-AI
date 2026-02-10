#!/usr/bin/env python3
"""
Agora AI Platform - Integration Test
====================================

Tests for the Agora AI Platform implementation:
- Capability manifest generation
- Sync protocol (export/import/validate/sandbox/commit)
- Ledger (exchange logging, credits, lockout)
- Runtime extensions (docking, syncing, post-sync)
- Library extensions (export/import with sanitization)
"""

import unittest
import json
import time
import tempfile
import shutil
from pathlib import Path

# Import Agora modules
from offline_ai_capabilities import (
    SpecializationType, SpecializationProfile, ModuleVersion,
    CapabilityManifest, ModuleHasher, CapabilityManager,
    create_default_specialization, get_learning_budget
)

from offline_ai_sync_protocol import (
    PackOrigin, SyncMode, SelectionPolicy, ValidationResult,
    CapabilityArtifact, CapabilityPack, PackSanitizer,
    ImportReport, SandboxResult, SyncProtocol
)

from offline_ai_agora_ledger import (
    EventType, ExchangeCategory, LibraryType,
    ExchangeEvent, PartnerLockout, LibraryEntry,
    AgoraLedger, create_ledger_for_ai
)

from offline_ai_runtime_agora import (
    AgoraRuntimeState, LingerProof, AgoraRuntimeExtension,
    extend_runtime_with_agora, ProximityDetector
)

from offline_ai_library_extension import (
    MergePolicy, SliceType, ShareableSlice, MergeReport,
    LibrarySanitizer, LibraryExtension, create_library_extension
)


# ============================================================================
# MOCK AI FOR TESTING
# ============================================================================

class MockAI:
    """Mock AI instance for testing."""
    
    def __init__(self):
        self.device_id = "test_device_001"
        self.account_id = "test_account_001"
        self.serial_code = "KO-TEST-12345"
        
        # Mock subsystems
        self.language = MockLanguage()
        self.lexicon = MockLexicon()
        self.governor = MockGovernor()
        self.vision = MockVision()
        self.audio = MockAudio()


class MockLanguage:
    """Mock language system."""
    
    def __init__(self):
        self.intent_evolution = MockIntentEvolution()


class MockIntentEvolution:
    """Mock intent evolution."""
    
    def __init__(self):
        self.evo = MockEvolution()


class MockEvolution:
    """Mock evolution."""
    
    def __init__(self):
        self.template_learner = MockTemplateLearner()
        self.evolution_registry = MockEvolutionRegistry()
        self.concepts = {}


class MockTemplateLearner:
    """Mock template learner."""
    
    def __init__(self):
        self.templates = {
            "language": {
                "greeting": ["Hello {name}!", "Hi there!"],
                "question": ["What is {topic}?", "How does {thing} work?"]
            }
        }


class MockEvolutionRegistry:
    """Mock evolution registry."""
    
    def __init__(self):
        self.hybrids = {
            "GREET_QUESTION_HYBRID": ("GREET", "QUESTION")
        }
        self.co_occurrence_counts = {
            ("GREET", "QUESTION"): 15
        }


class MockLexicon:
    """Mock lexicon."""
    
    def __init__(self):
        self.entries = {}


class MockGovernor:
    """Mock governor."""
    
    def __init__(self):
        self.params = {
            "voice_gnome": {
                "pitch": 0.5,
                "rate": 0.6,
                "warmth": 0.7,
                "prosody": 0.5,
                "salience": 0.4,
                "hesitation": 0.2
            }
        }
    
    def get_personalized_parameters(self):
        return self.params


class MockVision:
    """Mock vision system."""
    
    def __init__(self):
        self.focus = 0.6
        self.motion_sensitivity = 0.5
        self.recognition_threshold = 0.7
        self.detail_orientation = 0.4


class MockAudio:
    """Mock audio system."""
    
    def __init__(self):
        self.sensitivity = 0.5
        self.voice_isolation = 0.6
        self.emotion_detection = 0.5


class MockRuntime:
    """Mock runtime for testing."""
    
    def __init__(self):
        self.ai = MockAI()
        self.state = "idle"
    
    def _speak_text(self, text):
        pass


# ============================================================================
# TEST CASES
# ============================================================================

class TestCapabilities(unittest.TestCase):
    """Test capability manifest system."""
    
    def test_specialization_profile(self):
        """Test specialization profile creation."""
        profile = SpecializationProfile(
            primary=SpecializationType.STORYTELLER,
            secondary=SpecializationType.LISTENER
        )
        
        gains = profile.get_gain_vector()
        self.assertIn("lexical", gains)
        self.assertIn("memory", gains)
        self.assertIn("expression", gains)
        
        # Storyteller should have high lexical gain
        self.assertGreater(gains["lexical"], 1.0)
    
    def test_capability_manifest(self):
        """Test capability manifest generation."""
        spec = SpecializationProfile(
            primary=SpecializationType.COMPANION,
            secondary=SpecializationType.COMPANION
        )
        
        manifest = CapabilityManifest(
            device_id="test_device",
            account_id="test_account",
            serial_code="TEST-123",
            template_registry=ModuleVersion("template", "1.0", "abc123", "def456"),
            hybrid_registry=ModuleVersion("hybrid", "1.0", "ghi789", "jkl012"),
            voice_genome=ModuleVersion("voice", "1.0", "mno345", "pqr678"),
            vision_competency=ModuleVersion("vision", "1.0", "stu901", "vwx234"),
            audio_competency=ModuleVersion("audio", "1.0", "yza567", "bcd890"),
            policy_version=ModuleVersion("policy", "1.0", "efg123", "hij456"),
            specialization=spec
        )
        
        fingerprint = manifest.compute_fingerprint()
        self.assertEqual(len(fingerprint), 32)
        
        # Test serialization
        data = manifest.to_dict()
        self.assertEqual(data["device_id"], "test_device")
        
        # Test deserialization
        restored = CapabilityManifest.from_dict(data)
        self.assertEqual(restored.device_id, "test_device")
    
    def test_capability_manager(self):
        """Test capability manager."""
        ai = MockAI()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = CapabilityManager(ai, persistence_dir=tmpdir)
            
            spec = SpecializationProfile(
                primary=SpecializationType.ANALYST,
                secondary=SpecializationType.EXPLORER
            )
            
            manifest = manager.generate_manifest(specialization=spec)
            self.assertIsNotNone(manifest)
            self.assertEqual(manifest.device_id, "test_device_001")
            
            # Save and load
            manager.save_manifest(manifest)
            loaded = manager.load_manifest("test_device_001")
            self.assertIsNotNone(loaded)


class TestSyncProtocol(unittest.TestCase):
    """Test sync protocol."""
    
    def test_capability_pack(self):
        """Test capability pack creation."""
        pack = CapabilityPack(
            sender_device_id="device_a",
            sender_account_id="account_a",
            sender_fingerprint="abc123"
        )
        
        artifact = CapabilityArtifact(
            artifact_id="test_001",
            artifact_type="template",
            origin=PackOrigin.EMERGENT,
            transferable=True,
            content={"template": "Hello {name}!"},
            confidence=0.8
        )
        pack.artifacts.append(artifact)
        
        # Test signing
        pack.sign("device_key")
        self.assertTrue(pack.verify_signature())
        
        # Test serialization
        data = pack.to_dict()
        self.assertEqual(data["manifest"]["sender_device_id"], "device_a")
        
        # Test deserialization
        restored = CapabilityPack.from_dict(data)
        self.assertEqual(len(restored.artifacts), 1)
    
    def test_pack_sanitizer(self):
        """Test pack sanitizer."""
        artifact = CapabilityArtifact(
            artifact_id="test_001",
            artifact_type="template",
            origin=PackOrigin.EMERGENT,
            transferable=True,
            content={
                "template": "Hello John Smith!",
                "email": "john@example.com",
                "phone": "555-123-4567"
            }
        )
        
        sanitized = PackSanitizer.sanitize_artifact(artifact)
        content = sanitized.content
        
        # PII should be redacted
        self.assertNotIn("John Smith", content["template"])
        self.assertNotIn("john@example.com", str(content))
        self.assertNotIn("555-123-4567", str(content))
    
    def test_sync_protocol_export(self):
        """Test sync protocol export."""
        ai = MockAI()
        protocol = SyncProtocol(ai)
        
        pack = protocol.export_capability_pack(
            mode=SyncMode.FULL,
            selection=SelectionPolicy.ALL_SHAREABLE
        )
        
        self.assertIsNotNone(pack)
        self.assertEqual(pack.sender_device_id, "test_device_001")
        self.assertTrue(len(pack.artifacts) > 0)
        
        # All artifacts should be transferable
        for artifact in pack.artifacts:
            self.assertTrue(artifact.transferable)
    
    def test_sync_protocol_validate(self):
        """Test sync protocol validation."""
        ai = MockAI()
        protocol = SyncProtocol(ai)
        
        # Valid pack
        pack = protocol.export_capability_pack()
        result = protocol.validate_pack(pack)
        self.assertEqual(result, ValidationResult.VALID)
        
        # Invalid schema
        invalid_pack = CapabilityPack(schema_version="2.0")
        result = protocol.validate_pack(invalid_pack)
        self.assertEqual(result, ValidationResult.INVALID_SCHEMA)


class TestAgoraLedger(unittest.TestCase):
    """Test Agora ledger."""
    
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
    
    def tearDown(self):
        shutil.rmtree(self.tmpdir)
    
    def test_exchange_logging(self):
        """Test exchange event logging."""
        ledger = AgoraLedger("test_account", persistence_dir=self.tmpdir)
        
        event = ledger.log_exchange(
            partner_id="partner_device_001",
            categories_gained=[ExchangeCategory.TEMPLATE, ExchangeCategory.HYBRID_INTENT],
            artifacts_count=5,
            credits_earned=15
        )
        
        self.assertEqual(event.event_type, EventType.EXCHANGE)
        self.assertEqual(event.artifacts_count, 5)
        self.assertEqual(ledger.get_credit_balance(), 15)
    
    def test_partner_lockout(self):
        """Test partner lockout enforcement."""
        ledger = AgoraLedger("test_account", persistence_dir=self.tmpdir)
        
        # First exchange should be allowed
        can_exchange, reason = ledger.can_exchange_with("partner_001")
        self.assertTrue(can_exchange)
        
        # Log an exchange
        ledger.log_exchange(
            partner_id="partner_001",
            categories_gained=[ExchangeCategory.TEMPLATE],
            artifacts_count=3,
            credits_earned=10
        )
        
        # Second exchange same day should be blocked
        can_exchange, reason = ledger.can_exchange_with("partner_001")
        self.assertFalse(can_exchange)
        self.assertIn("limit", reason.lower())
    
    def test_credit_management(self):
        """Test credit management."""
        ledger = AgoraLedger("test_account", persistence_dir=self.tmpdir)
        
        # Grant credits
        balance = ledger.grant_credits(50, "test_grant")
        self.assertEqual(balance, 50)
        
        # Spend credits
        success = ledger.spend_credits(20, "test_purchase")
        self.assertTrue(success)
        self.assertEqual(ledger.get_credit_balance(), 30)
        
        # Try to spend too much
        success = ledger.spend_credits(100, "expensive_purchase")
        self.assertFalse(success)
    
    def test_library_management(self):
        """Test two-library system."""
        ledger = AgoraLedger("test_account", persistence_dir=self.tmpdir)
        
        # Add to Agora Exchange Library
        ledger.log_exchange(
            partner_id="partner_001",
            categories_gained=[ExchangeCategory.TEMPLATE],
            artifacts_count=2,
            credits_earned=10
        )
        
        # Add to Self Growth Library
        ledger.log_class_completion(
            class_id="class_001",
            class_name="Advanced Templates",
            categories_gained=[ExchangeCategory.TEMPLATE],
            credits_cost=5
        )
        
        agora_lib = ledger.get_agora_exchange_library()
        self_growth_lib = ledger.get_self_growth_library()
        
        self.assertEqual(len(agora_lib), 1)
        self.assertEqual(len(self_growth_lib), 1)
        
        # Check summary
        summary = ledger.get_library_summary()
        self.assertEqual(summary["agora_exchange"]["total_entries"], 1)
        self.assertEqual(summary["self_growth"]["total_entries"], 1)


class TestRuntimeExtension(unittest.TestCase):
    """Test runtime Agora extension."""
    
    def test_linger_proof(self):
        """Test linger proof."""
        linger = LingerProof(
            session_id="session_001",
            partner_device_id="partner_001",
            start_time=time.time(),
            required_duration=2.0
        )
        
        # Not complete yet
        self.assertFalse(linger.is_complete())
        
        # Add RSSI readings
        linger.add_rssi(-60)
        linger.add_rssi(-55)
        
        # Wait for duration
        time.sleep(2.1)
        linger.both_confirmed = True
        
        self.assertTrue(linger.is_complete())
    
    def test_runtime_extension_init(self):
        """Test runtime extension initialization."""
        runtime = MockRuntime()
        extension = AgoraRuntimeExtension(runtime)
        
        self.assertIsNotNone(extension)
        self.assertEqual(extension.runtime, runtime)


class TestLibraryExtension(unittest.TestCase):
    """Test library extension."""
    
    def test_sanitizer(self):
        """Test library sanitizer."""
        data = {
            "template": "Hello John!",
            "user_id": "user_123",
            "safe_field": "This is safe",
            "transcript": "Private conversation"
        }
        
        sanitized = LibrarySanitizer.sanitize(data)
        
        # Forbidden fields removed
        self.assertNotIn("user_id", sanitized)
        self.assertNotIn("transcript", sanitized)
        
        # PII redacted
        self.assertNotIn("John", sanitized["template"])
        
        # Safe fields preserved
        self.assertEqual(sanitized["safe_field"], "This is safe")
    
    def test_export_slice(self):
        """Test export shareable slice."""
        ai = MockAI()
        ext = LibraryExtension(ai)
        
        slice_obj = ext.export_shareable_slice(
            slice_type=SliceType.TEMPLATES,
            selection_policy="all",
            min_confidence=0.5
        )
        
        self.assertEqual(slice_obj.slice_type, SliceType.TEMPLATES)
        self.assertIn("templates", slice_obj.content)
    
    def test_import_slice(self):
        """Test import shareable slice."""
        ai = MockAI()
        ext = LibraryExtension(ai)
        
        # Create a slice to import
        slice_obj = ShareableSlice(
            slice_type=SliceType.HYBRIDS,
            content={
                "hybrids": {"NEW_HYBRID": ("A", "B")},
                "co_occurrence_counts": {}
            },
            source_fingerprint="test_fingerprint"
        )
        
        report = ext.import_shareable_slice(slice_obj, MergePolicy.APPEND_ONLY)
        
        self.assertTrue(report.success)
        self.assertEqual(report.entries_added, 1)


class TestIntegration(unittest.TestCase):
    """Integration tests for full Agora workflow."""
    
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
    
    def tearDown(self):
        shutil.rmtree(self.tmpdir)
    
    def test_full_exchange_workflow(self):
        """Test complete exchange workflow."""
        # Create two AI instances
        ai_a = MockAI()
        ai_a.device_id = "device_a"
        ai_a.account_id = "account_a"
        
        ai_b = MockAI()
        ai_b.device_id = "device_b"
        ai_b.account_id = "account_b"
        
        # Create ledgers
        ledger_a = AgoraLedger("account_a", persistence_dir=self.tmpdir)
        ledger_b = AgoraLedger("account_b", persistence_dir=self.tmpdir)
        
        # Create sync protocols
        protocol_a = SyncProtocol(ai_a)
        protocol_b = SyncProtocol(ai_b)
        
        # A exports pack
        pack_a = protocol_a.export_capability_pack(
            mode=SyncMode.FULL,
            selection=SelectionPolicy.ALL_SHAREABLE
        )
        
        # B exports pack
        pack_b = protocol_b.export_capability_pack(
            mode=SyncMode.FULL,
            selection=SelectionPolicy.ALL_SHAREABLE
        )
        
        # Exchange packs
        # A receives B's pack
        result_a = protocol_a.validate_pack(pack_b)
        self.assertEqual(result_a, ValidationResult.VALID)
        
        report_a = protocol_a.import_capability_pack(pack_b)
        self.assertTrue(report_a.success)
        
        # B receives A's pack
        result_b = protocol_b.validate_pack(pack_a)
        self.assertEqual(result_b, ValidationResult.VALID)
        
        report_b = protocol_b.import_capability_pack(pack_a)
        self.assertTrue(report_b.success)
        
        # Log exchanges
        ledger_a.log_exchange(
            partner_id="device_b",
            categories_gained=[ExchangeCategory.TEMPLATE],
            artifacts_count=report_a.artifacts_imported,
            credits_earned=15
        )
        
        ledger_b.log_exchange(
            partner_id="device_a",
            categories_gained=[ExchangeCategory.TEMPLATE],
            artifacts_count=report_b.artifacts_imported,
            credits_earned=15
        )
        
        # Verify credits
        self.assertEqual(ledger_a.get_credit_balance(), 15)
        self.assertEqual(ledger_b.get_credit_balance(), 15)
        
        # Verify lockout
        can_exchange, _ = ledger_a.can_exchange_with("device_b")
        self.assertFalse(can_exchange)  # Same day limit


# ============================================================================
# RUN TESTS
# ============================================================================

def run_tests():
    """Run all tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestCapabilities))
    suite.addTests(loader.loadTestsFromTestCase(TestSyncProtocol))
    suite.addTests(loader.loadTestsFromTestCase(TestAgoraLedger))
    suite.addTests(loader.loadTestsFromTestCase(TestRuntimeExtension))
    suite.addTests(loader.loadTestsFromTestCase(TestLibraryExtension))
    suite.addTests(loader.loadTestsFromTestCase(TestIntegration))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_tests()
    exit(0 if success else 1)