# Agora AI Platform Implementation

This document describes the implementation of the Agora AI Platform for the KO Companion offline AI ecosystem.

## Overview

Agora AI is an offline-first AI companion ecosystem that rewards real-world human interaction by allowing two companions to exchange non-personal capability growth artifacts.

### Core Promise
- **AI works offline** - Core functionality requires no internet
- **Platform coordinates** - Social exchange + incentives via optional online layer
- **Privacy-first** - Never syncs memories, transcripts, or personal data

## Architecture

### Two-Half System

```
┌─────────────────────────────────────────────────────────────┐
│                    AGORA AI PLATFORM                         │
├──────────────────────────┬──────────────────────────────────┤
│   Device Companion       │   Agora Platform App             │
│   (Offline)              │   (Online-Optional)              │
│                          │                                  │
│   • AI Runtime           │   • Identity Management          │
│   • Capability Sync      │   • QR Handshake                 │
│   • Local Learning       │   • Rewards/Credits              │
│   • Expression Engine    │   • Hub Discovery                │
│   • Hub Manager          │   • Class Marketplace            │
│   • Achievement System   │   • Achievements                 │
└──────────────────────────┴──────────────────────────────────┘
```

## Device-Side Modules

### 1. `offline_ai_capabilities.py`
**Purpose**: Capability manifest and module hashing

**Key Components**:
- `SpecializationType` - 13 specializations (Storyteller, Analyst, Companion, etc.)
- `SpecializationProfile` - Learning gain multipliers per domain
- `CapabilityManifest` - Complete capability identity for delta sync
- `ModuleHasher` - Hash each shareable section
- `CapabilityManager` - Generate and persist manifests

**Usage**:
```python
from offline_ai_capabilities import (
    SpecializationType, SpecializationProfile, CapabilityManager
)

# Create specialization
spec = SpecializationProfile(
    primary=SpecializationType.STORYTELLER,
    secondary=SpecializationType.LISTENER
)

# Generate manifest
manager = CapabilityManager(ai_instance)
manifest = manager.generate_manifest(specialization=spec)
print(manifest.compute_fingerprint())
```

### 2. `offline_ai_sync_protocol.py`
**Purpose**: Sync protocol for capability pack exchange

**Key Components**:
- `CapabilityPack` - Container for shareable artifacts
- `CapabilityArtifact` - Single artifact with origin/transferable flags
- `PackOrigin` - SOCIAL, CLASS, PURCHASED, SYSTEM, EMERGENT
- `SyncProtocol` - Build, validate, sandbox, commit packs
- `PackSanitizer` - Remove personal data

**Usage**:
```python
from offline_ai_sync_protocol import (
    SyncProtocol, SyncMode, SelectionPolicy, ValidationResult
)

# Create protocol
protocol = SyncProtocol(ai_instance, governor)

# Export pack
pack = protocol.export_capability_pack(
    mode=SyncMode.FULL,
    selection=SelectionPolicy.ALL_SHAREABLE
)

# Import pack
report = protocol.import_capability_pack(received_pack)
if report.success:
    print(f"Imported {report.artifacts_imported} artifacts")
```

### 3. `offline_ai_agora_ledger.py`
**Purpose**: Two-library logging with daily lockout

**Key Components**:
- `AgoraLedger` - Central ledger for all Agora interactions
- `ExchangeEvent` - Logged exchange events
- `PartnerLockout` - Daily exchange limit enforcement
- `LibraryEntry` - Entries in Self Growth / Agora Exchange libraries

**Usage**:
```python
from offline_ai_agora_ledger import AgoraLedger, ExchangeCategory

# Create ledger
ledger = AgoraLedger(account_id)

# Log exchange
event = ledger.log_exchange(
    partner_id="partner_device",
    categories_gained=[ExchangeCategory.TEMPLATE, ExchangeCategory.HYBRID_INTENT],
    artifacts_count=5,
    credits_earned=15
)

# Check lockout
can_exchange, reason = ledger.can_exchange_with("partner_device")

# Get libraries
self_growth = ledger.get_self_growth_library()
agora_exchange = ledger.get_agora_exchange_library()
```

### 4. `offline_ai_runtime_agora.py`
**Purpose**: Runtime extensions for Agora sync states

**Key Components**:
- `AgoraRuntimeState` - Extended states: DOCKING, SYNCING, POST_SYNC
- `LingerProof` - Proof of co-presence
- `AgoraRuntimeExtension` - Runtime extension for Agora capabilities
- `ProximityDetector` - RSSI-based proximity detection

**Usage**:
```python
from offline_ai_runtime_agora import extend_runtime_with_agora

# Extend existing runtime
extension = extend_runtime_with_agora(runtime)

# Start docking
extension.start_docking(
    partner_device_id="partner_001",
    session_id="session_001",
    required_linger=10.0
)

# Update linger
extension.update_linger_rssi(-60)
if extension.confirm_linger():
    extension.start_syncing()
```

### 5. `offline_ai_library_extension.py`
**Purpose**: Library export/import with sanitization

**Key Components**:
- `LibraryExtension` - Export/import shareable slices
- `LibrarySanitizer` - Remove personal data
- `ShareableSlice` - Sanitized slice of library
- `MergePolicy` - REPLACE, MERGE, APPEND_ONLY, CONSERVATIVE

**Usage**:
```python
from offline_ai_library_extension import (
    LibraryExtension, SliceType, MergePolicy
)

# Create extension
ext = LibraryExtension(ai_instance)

# Export slice
slice_obj = ext.export_shareable_slice(
    slice_type=SliceType.TEMPLATES,
    selection_policy="all"
)

# Import slice
report = ext.import_shareable_slice(
    slice_obj,
    merge_policy=MergePolicy.MERGE
)
```

### 6. `offline_ai_hub_discovery.py` (NEW)
**Purpose**: Hub discovery and management for meet locations

**Key Components**:
- `Hub` - Meeting place with safety tags and metadata
- `HubManager` - Cache and discover hubs
- `GeoLocation` - GPS coordinates and distance calculation
- `MeetSession` - Pending meet session with rotating token

**Usage**:
```python
from offline_ai_hub_discovery import create_hub_manager, SafetyTag

# Create manager with sample hubs
manager = create_hub_manager()

# Set current location
manager.set_current_location(GeoLocation(latitude=40.7829, longitude=-73.9654))

# Find nearby hubs
nearby = manager.find_nearby_hubs(radius_meters=5000, min_safety_score=3)

# Create meet session
session = manager.create_meet_session(hub_id, device_id, account_id)
qr_data = manager.get_session_qr_data(session.session_id)

# Check if at hub
if manager.is_at_hub(hub_id, max_distance_meters=100):
    print("Within hub radius - exchange allowed")
```

### 7. `offline_ai_achievements.py` (NEW)
**Purpose**: Achievement system for introvert/extrovert balance

**Key Components**:
- `AchievementType` - QUIET_STRENGTH, BOLD_STEP, BALANCE_CREST, etc.
- `AchievementManager` - Track and award achievements
- `StreakState` - Meet streak tracking

**Achievements**:
| Achievement | Description | Rarity |
|-------------|-------------|--------|
| Quiet Strength | Extrovert → introvert growth | Rare |
| Bold Step | Introvert → extrovert growth | Rare |
| Balance Crest | Both traits within threshold | Epic |
| Weekly Warrior | 7-day meet streak | Uncommon |
| Monthly Master | 30-day meet streak | Rare |
| Social Butterfly | 5 unique partners | Uncommon |
| Network Weaver | 20 unique partners | Rare |

**Usage**:
```python
from offline_ai_achievements import create_achievement_manager

# Create manager
achievements = create_achievement_manager(ai_instance)

# Check balance achievements (call periodically)
new_achievements = achievements.check_balance_achievements()

# Check meet achievements (after exchange)
new_achievements = achievements.check_meet_achievements(partner_id)

# Get stats
stats = achievements.get_stats()
print(f"Total achievements: {stats['total_achievements']}")
print(f"Current streak: {stats['current_streak']}")
```

### 8. `offline_ai_platform_client.py` (NEW)
**Purpose**: Device-platform communication client

**Key Components**:
- `PlatformClient` - Main client for platform services
- `PlatformCredentials` - User authentication
- `DeviceIdentity` - Device binding
- `PackVerifier` - Verify platform-signed class packs

**Services**:
- Auth Service - Login, device binding
- Hub Service - Fetch hub list, propose hubs
- Exchange Service - Log meets, get credits
- Class Service - Fetch class catalog and packs
- Progress Service - Sync manifests, achievements

**Usage**:
```python
from offline_ai_platform_client import create_platform_client

# Create client
client = create_platform_client()

# Login
client.login(email="user@example.com", password="...")

# Bind device after QR pairing
client.bind_device(device_id, device_pubkey_id, manifest_hash)

# Fetch class catalog
classes = client.fetch_class_catalog()

# Fetch signed class pack
pack = client.fetch_class_pack("class_language_001")

# Verify pack
verifier = PackVerifier(client.platform_pubkey)
if verifier.verify_class_pack(pack):
    # Apply pack to AI
    pass
```

## User Journey

### A. Setup (Onboarding)
1. User creates Agora account (platform app)
   - Email/phone login OR privacy mode (minimal profile)
2. User pairs offline companion via QR
3. Companion exports Capability Manifest to platform
4. Platform stores: manifest hash, specialization, intro seed params

### B. Hub Discovery
1. User opens app → sees curated hub list for their area
2. Hubs cached offline for later use
3. Optional: propose new hubs for community voting

### C. Meet Mode + Handshake
1. User taps "Meet Mode" at a hub
2. App generates rotating session QR:
   - session_token, device_pubkey_id, timestamp, hub_id
3. Other user scans → both enter Pending Exchange
4. Linger proof required:
   - BLE RSSI sampling OR NFC tap
   - Optional: GPS "in hub radius" check

### D. Exchange (Capability Sync)
1. After linger proof:
   - Each device generates Capability Pack
   - Packs exchanged P2P (BLE/Wi-Fi Direct)
2. Each device validates + sandboxes + commits pack

### E. Reward & Logging
1. Platform grants credits (scaled by novelty)
2. Daily sync lockout starts for this partner
3. Libraries updated (Self Growth + Agora Exchange)
4. Achievement checks triggered

### F. Classes (Platform Training)
1. User spends credits to unlock classes
2. Platform generates signed Class Capability Pack
3. Pack marked: origin=CLASS, transferable=false
4. Device applies pack to AI

## Capability Pack Format

### Structure
```json
{
  "manifest": {
    "schema_version": "1.0",
    "sender_device_id": "...",
    "sender_account_id": "...",
    "sender_fingerprint": "...",
    "timestamp": 1234567890,
    "pack_hash": "..."
  },
  "payload": {
    "artifacts": [
      {
        "artifact_id": "...",
        "artifact_type": "template",
        "origin": "emergent",
        "transferable": true,
        "content": {...},
        "confidence": 0.8
      }
    ]
  },
  "policy": {
    "max_size_bytes": 26214400,
    "allowed_types": [...],
    "forbidden_patterns": [...]
  },
  "signature": "device_key:..."
}
```

### Syncable Content
- Evolution templates / hybrid intents / lexical patterns
- Abstracted parameter deltas (bounded):
  - Phonetic adaptation (non-biometric)
  - Prosody style tendencies (non-voiceprint)
  - Visual competency heuristics (non-faceprint)
- Registry improvements: template quality scores, confidence maps

### Never Synced
- Episodic memory content
- Transcripts, chat logs
- User identifiers
- Face vectors / embeddings / biometrics
- Voice fingerprints

## Security & Anti-Abuse

### Poisoning Prevention
- Every pack signed with device key
- Platform classes platform-signed
- Signature verification on import

### Farming Prevention
- Same partner → 1 exchange/day (hard rule)
- Linger proof required (time + proximity)
- Credits scale with novelty:
  - First-time meet > repeat
  - Repeat over days > same day repeat

### Privacy Model
- Agora app stores metadata only (time, partner hash, categories)
- Capability packs never include personal state
- Partner IDs hashed before storage

## Specialization System

### 13 Specializations

| Specialization | Lexical | Memory | Expression | Voice | Visual | Audio |
|---------------|---------|--------|------------|-------|--------|-------|
| Storyteller   | 1.4     | 1.2    | 1.5        | 1.1   | 0.9    | 1.0   |
| Poet          | 1.5     | 1.1    | 1.4        | 1.2   | 0.8    | 1.0   |
| Musician      | 0.9     | 1.2    | 1.2        | 1.3   | 0.9    | 1.5   |
| Artist        | 0.9     | 1.1    | 1.3        | 0.9   | 1.5    | 1.0   |
| Analyst       | 1.2     | 1.4    | 0.9        | 0.8   | 1.2    | 0.9   |
| Logician      | 1.3     | 1.3    | 0.9        | 0.8   | 1.0    | 0.8   |
| Philosopher   | 1.4     | 1.3    | 1.1        | 1.0   | 0.9    | 0.9   |
| Companion     | 1.1     | 1.1    | 1.1        | 1.1   | 1.1    | 1.1   |
| Mentor        | 1.3     | 1.2    | 1.2        | 1.2   | 1.0    | 1.0   |
| Listener      | 1.1     | 1.3    | 1.0        | 1.0   | 1.1    | 1.3   |
| Builder       | 1.1     | 1.2    | 1.0        | 0.9   | 1.2    | 0.9   |
| Explorer      | 1.1     | 1.1    | 1.1        | 1.0   | 1.3    | 1.1   |
| Guardian      | 0.9     | 1.2    | 0.9        | 1.0   | 1.3    | 1.1   |

### Combined Gains
Primary contributes 60%, secondary 40%:
```
gain = (primary_gain × 0.6) + (secondary_gain × 0.4)
```

## Integration with Existing Code

### Minimal Changes Required

1. **Runtime Extension** (NEW MODULE)
   - `offline_ai_runtime_agora.py` extends base runtime
   - No modifications to `offline_ai_runtime.py` required

2. **Library Extension** (NEW MODULE)
   - `offline_ai_library_extension.py` adds export/import
   - Works alongside existing `offline_ai_library_system.py`

3. **AI Core Integration**
   ```python
   # In offline_ai_core.py, add to OfflineAI.__init__:
   from offline_ai_agora_ledger import AgoraLedger
   from offline_ai_achievements import create_achievement_manager
   from offline_ai_platform_client import create_platform_client
   
   self.agora_ledger = AgoraLedger(account_id)
   self.achievements = create_achievement_manager(self)
   self.platform_client = create_platform_client()
   ```

4. **App Integration**
   ```python
   # In app.py, extend runtime after creation:
   from offline_ai_runtime_agora import extend_runtime_with_agora
   from offline_ai_hub_discovery import create_hub_manager
   
   self.ai_runtime = create_runtime(...)
   self.agora_extension = extend_runtime_with_agora(self.ai_runtime)
   self.hub_manager = create_hub_manager()
   ```

## Testing

Run integration tests:
```bash
python agora_integration_test.py
```

Tests cover:
- Capability manifest generation
- Sync protocol (export/import/validate/sandbox/commit)
- Ledger (exchange logging, credits, lockout)
- Runtime extensions (docking, syncing, post-sync)
- Library extensions (export/import with sanitization)
- Full exchange workflow

## Phase Roadmap

### Phase 1 (MVP) - IMPLEMENTED
- [x] `offline_ai_sync_protocol.py`
- [x] `offline_ai_capabilities.py`
- [x] `offline_ai_agora_ledger.py`
- [x] Runtime states DOCKING/SYNCING/POST_SYNC
- [x] Library export/import (sanitized)
- [x] Ledger logging + daily lockout
- [x] Capability manifest + module hashing
- [x] `offline_ai_hub_discovery.py`
- [x] `offline_ai_achievements.py`
- [x] `offline_ai_platform_client.py`
- [ ] QR handshake + BLE linger proof (platform app)
- [ ] Platform backend services

### Phase 2 (Rewards + Classes)
- [ ] Credit system UI
- [ ] Class pack signing + delivery
- [ ] Pack origin/transfer rules enforcement
- [ ] Class marketplace
- [ ] Achievement notifications

### Phase 3 (Scaling & Safety)
- [ ] Trust graph / reputation keys
- [ ] Delta packs (smaller syncs)
- [ ] Stronger redaction + test harness
- [ ] Platform app backend
- [ ] Community hub proposals

## License

Part of the KO Companion project.
Authors: Sunni (Sir) Morningstar & Cael Devo