#!/usr/bin/env python3
"""
Offline AI Platform Client
==========================
Agora AI Platform - Phase 1

Device-side client for communicating with Agora platform services.

Features:
- Auth service (login, device binding)
- Hub service (fetch hub list)
- Exchange service (log meets, get credits)
- Class service (fetch class packs)
- Progress service (sync manifests, achievements)
- Offline queue for pending operations
"""

import json
import time
import hashlib
import logging
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMERATIONS
# ============================================================================

class PlatformEndpoint(Enum):
    """Platform service endpoints."""
    AUTH = "/auth"
    HUBS = "/hubs"
    EXCHANGE = "/exchange"
    CLASSES = "/classes"
    PROGRESS = "/progress"
    NOTIFICATIONS = "/notifications"


class QueueItemType(Enum):
    """Types of queued operations."""
    EXCHANGE_LOG = "exchange_log"
    MANIFEST_SYNC = "manifest_sync"
    ACHIEVEMENT_SYNC = "achievement_sync"
    HUB_PROPOSAL = "hub_proposal"


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class PlatformCredentials:
    """User credentials for platform authentication."""
    user_id: str
    public_handle: str
    auth_token: str
    refresh_token: str
    expires_at: float
    
    def is_expired(self) -> bool:
        """Check if token is expired."""
        return time.time() >= self.expires_at
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "user_id": self.user_id,
            "public_handle": self.public_handle,
            "auth_token": self.auth_token,
            "refresh_token": self.refresh_token,
            "expires_at": self.expires_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PlatformCredentials':
        return cls(
            user_id=data["user_id"],
            public_handle=data["public_handle"],
            auth_token=data["auth_token"],
            refresh_token=data["refresh_token"],
            expires_at=data["expires_at"]
        )


@dataclass
class DeviceIdentity:
    """Device identity for platform binding."""
    device_id: str
    device_pubkey_id: str
    manifest_hash: str
    last_seen: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "device_pubkey_id": self.device_pubkey_id,
            "manifest_hash": self.manifest_hash,
            "last_seen": self.last_seen
        }


@dataclass
class QueuedOperation:
    """An operation queued for later sync."""
    operation_id: str
    item_type: QueueItemType
    payload: Dict[str, Any]
    created_at: float
    retry_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "item_type": self.item_type.value,
            "payload": self.payload,
            "created_at": self.created_at,
            "retry_count": self.retry_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueuedOperation':
        return cls(
            operation_id=data["operation_id"],
            item_type=QueueItemType(data["item_type"]),
            payload=data["payload"],
            created_at=data["created_at"],
            retry_count=data.get("retry_count", 0)
        )


# ============================================================================
# PLATFORM CLIENT
# ============================================================================

class PlatformClient:
    """
    Client for Agora platform services.
    
    Handles:
    - Authentication
    - Hub discovery
    - Exchange logging
    - Class pack retrieval
    - Progress sync
    - Offline operation queue
    """
    
    def __init__(self, 
                 base_url: str = "https://api.agora-ai.example.com",
                 persistence_dir: str = "./offline_ai_data/platform"):
        self.base_url = base_url
        self.persistence_dir = Path(persistence_dir)
        self.persistence_dir.mkdir(parents=True, exist_ok=True)
        
        # Credentials
        self.credentials: Optional[PlatformCredentials] = None
        
        # Device identity
        self.device_identity: Optional[DeviceIdentity] = None
        
        # Offline queue
        self.pending_queue: List[QueuedOperation] = []
        
        # Platform public key (for verifying class packs)
        self.platform_pubkey: Optional[str] = None
        
        # Callbacks
        self.on_auth_success: Optional[Callable] = None
        self.on_sync_complete: Optional[Callable] = None
        
        # Load state
        self._load_state()
        
        logger.info("[PLATFORM CLIENT] Initialized")
    
    # ========================================================================
    # AUTHENTICATION
    # ========================================================================
    
    def login(self, 
              email: str = None,
              phone: str = None,
              password: str = None,
              privacy_mode: bool = False) -> bool:
        """
        Login to Agora platform.
        
        Args:
            email: Email for login
            phone: Phone for login
            password: Password
            privacy_mode: Use minimal profile
            
        Returns:
            True if login successful
        """
        # In production: make HTTP request to auth service
        # For MVP: simulate successful login
        
        user_id = f"user_{hashlib.sha256((email or phone).encode()).hexdigest()[:16]}"
        
        self.credentials = PlatformCredentials(
            user_id=user_id,
            public_handle=f"user_{user_id[:8]}" if privacy_mode else email.split('@')[0],
            auth_token=f"token_{int(time.time())}",
            refresh_token=f"refresh_{int(time.time())}",
            expires_at=time.time() + 86400  # 24 hours
        )
        
        self._save_state()
        
        if self.on_auth_success:
            self.on_auth_success(self.credentials)
        
        logger.info(f"[PLATFORM] Logged in as {self.credentials.public_handle}")
        return True
    
    def logout(self):
        """Logout and clear credentials."""
        self.credentials = None
        self._save_state()
        logger.info("[PLATFORM] Logged out")
    
    def is_authenticated(self) -> bool:
        """Check if user is authenticated."""
        if not self.credentials:
            return False
        return not self.credentials.is_expired()
    
    def get_user_id(self) -> Optional[str]:
        """Get current user ID."""
        if self.credentials:
            return self.credentials.user_id
        return None
    
    # ========================================================================
    # DEVICE BINDING
    # ========================================================================
    
    def bind_device(self, 
                    device_id: str,
                    device_pubkey_id: str,
                    manifest_hash: str) -> bool:
        """
        Bind device to platform account.
        
        Called after QR pairing.
        """
        if not self.is_authenticated():
            logger.warning("[PLATFORM] Cannot bind device: not authenticated")
            return False
        
        self.device_identity = DeviceIdentity(
            device_id=device_id,
            device_pubkey_id=device_pubkey_id,
            manifest_hash=manifest_hash,
            last_seen=time.time()
        )
        
        # In production: send to platform
        # response = self._post(PlatformEndpoint.AUTH, "/bind_device", {...})
        
        self._save_state()
        
        logger.info(f"[PLATFORM] Device bound: {device_id[:16]}...")
        return True
    
    def unbind_device(self):
        """Unbind device from account."""
        # In production: notify platform
        self.device_identity = None
        self._save_state()
        logger.info("[PLATFORM] Device unbound")
    
    # ========================================================================
    # HUB SERVICE
    # ========================================================================
    
    def fetch_hubs(self, 
                   latitude: float = None,
                   longitude: float = None,
                   radius_km: float = 10) -> List[Dict[str, Any]]:
        """
        Fetch hub list from platform.
        
        Args:
            latitude: Current latitude
            longitude: Current longitude
            radius_km: Search radius in km
            
        Returns:
            List of hub data
        """
        if not self.is_authenticated():
            logger.warning("[PLATFORM] Cannot fetch hubs: not authenticated")
            return []
        
        # In production: make HTTP request
        # response = self._get(PlatformEndpoint.HUBS, params={...})
        
        # For MVP: return empty (hubs loaded from cache)
        logger.info("[PLATFORM] Fetched hubs")
        return []
    
    def propose_hub(self, 
                    name: str,
                    address: str,
                    latitude: float,
                    longitude: float,
                    hub_type: str) -> Optional[str]:
        """
        Propose a new hub.
        
        Returns:
            Proposal ID if successful
        """
        if not self.is_authenticated():
            return None
        
        proposal_id = f"proposal_{int(time.time() * 1000)}"
        
        # Queue for sync
        self._queue_operation(QueueItemType.HUB_PROPOSAL, {
            "proposal_id": proposal_id,
            "name": name,
            "address": address,
            "latitude": latitude,
            "longitude": longitude,
            "hub_type": hub_type
        })
        
        logger.info(f"[PLATFORM] Hub proposed: {name}")
        return proposal_id
    
    # ========================================================================
    # EXCHANGE SERVICE
    # ========================================================================
    
    def log_exchange(self,
                     partner_hash: str,
                     hub_id: str,
                     timestamp: float,
                     categories_gained: List[str],
                     artifacts_count: int,
                     credits_earned: int) -> bool:
        """
        Log an exchange event to platform.
        
        Stores metadata only (no content).
        """
        if not self.is_authenticated():
            # Queue for later sync
            self._queue_operation(QueueItemType.EXCHANGE_LOG, {
                "partner_hash": partner_hash,
                "hub_id": hub_id,
                "timestamp": timestamp,
                "categories_gained": categories_gained,
                "artifacts_count": artifacts_count,
                "credits_earned": credits_earned
            })
            return False
        
        # In production: send to platform
        # response = self._post(PlatformEndpoint.EXCHANGE, "/log", {...})
        
        logger.info(f"[PLATFORM] Exchange logged: {credits_earned} credits")
        return True
    
    def get_credit_balance(self) -> int:
        """Get current credit balance from platform."""
        if not self.is_authenticated():
            return 0
        
        # In production: fetch from platform
        # response = self._get(PlatformEndpoint.EXCHANGE, "/credits")
        
        return 0
    
    # ========================================================================
    # CLASS SERVICE
    # ========================================================================
    
    def fetch_class_catalog(self) -> List[Dict[str, Any]]:
        """Fetch available classes from platform."""
        if not self.is_authenticated():
            return []
        
        # In production: fetch from platform
        # response = self._get(PlatformEndpoint.CLASSES, "/catalog")
        
        # Return sample classes for MVP
        return [
            {
                "class_id": "class_language_001",
                "name": "Language Nuance Drills",
                "description": "Refine your companion's language patterns",
                "cost": 50,
                "duration_minutes": 30,
                "outputs": ["lexical_patterns", "template_quality"],
                "requirements": {"credits": 50}
            },
            {
                "class_id": "class_phonetic_001",
                "name": "Phonetic Sharpening",
                "description": "Improve voice clarity and articulation",
                "cost": 75,
                "duration_minutes": 20,
                "outputs": ["voice_params"],
                "requirements": {"credits": 75}
            },
            {
                "class_id": "class_conversation_001",
                "name": "Conversational Flow",
                "description": "Enhance dialogue smoothness",
                "cost": 60,
                "duration_minutes": 25,
                "outputs": ["hybrid_intents", "response_patterns"],
                "requirements": {"credits": 60}
            },
            {
                "class_id": "class_visual_001",
                "name": "Visual Competency Practice",
                "description": "Improve visual recognition skills",
                "cost": 80,
                "duration_minutes": 40,
                "outputs": ["vision_params"],
                "requirements": {"credits": 80}
            },
            {
                "class_id": "class_balance_001",
                "name": "Social Balance Training",
                "description": "Develop skills across introvert/extrovert spectrum",
                "cost": 100,
                "duration_minutes": 45,
                "outputs": ["voice_params", "behavior_patterns"],
                "requirements": {"credits": 100, "achievement": "first_meet"}
            }
        ]
    
    def fetch_class_pack(self, class_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch a signed class pack from platform.
        
        Returns:
            Class pack data with platform signature
        """
        if not self.is_authenticated():
            return None
        
        # In production: fetch from platform
        # response = self._get(PlatformEndpoint.CLASSES, f"/{class_id}/pack")
        
        # For MVP: return sample pack
        return {
            "class_id": class_id,
            "schema_version": "1.0",
            "artifacts": [],
            "policy": {
                "origin": "CLASS",
                "transferable": False
            },
            "signature": f"platform_sign_{class_id}",
            "issued_at": time.time()
        }
    
    def complete_class(self, class_id: str) -> bool:
        """Mark a class as completed."""
        if not self.is_authenticated():
            return False
        
        # In production: notify platform
        logger.info(f"[PLATFORM] Class completed: {class_id}")
        return True
    
    # ========================================================================
    # PROGRESS SERVICE
    # ========================================================================
    
    def sync_manifest(self, manifest: Dict[str, Any]) -> bool:
        """
        Sync capability manifest to platform.
        
        Platform stores hash + versions only.
        """
        if not self.is_authenticated():
            # Queue for later
            self._queue_operation(QueueItemType.MANIFEST_SYNC, {
                "manifest_hash": manifest.get("fingerprint"),
                "versions": {
                    "template": manifest.get("template_registry", {}).get("version"),
                    "hybrid": manifest.get("hybrid_registry", {}).get("version"),
                    "voice": manifest.get("voice_genome", {}).get("version"),
                },
                "specialization": manifest.get("specialization")
            })
            return False
        
        # In production: send to platform
        logger.info("[PLATFORM] Manifest synced")
        return True
    
    def sync_achievements(self, achievements: List[Dict[str, Any]]) -> bool:
        """Sync achievements to platform."""
        if not self.is_authenticated():
            self._queue_operation(QueueItemType.ACHIEVEMENT_SYNC, {
                "achievements": achievements
            })
            return False
        
        logger.info(f"[PLATFORM] Synced {len(achievements)} achievements")
        return True
    
    # ========================================================================
    # OFFLINE QUEUE
    # ========================================================================
    
    def _queue_operation(self, item_type: QueueItemType, payload: Dict[str, Any]):
        """Queue an operation for later sync."""
        operation = QueuedOperation(
            operation_id=f"op_{int(time.time() * 1000)}",
            item_type=item_type,
            payload=payload,
            created_at=time.time()
        )
        
        self.pending_queue.append(operation)
        self._save_state()
        
        logger.info(f"[PLATFORM] Queued {item_type.value}: {operation.operation_id}")
    
    def sync_pending_operations(self) -> Dict[str, int]:
        """
        Sync all pending operations to platform.
        
        Returns:
            Dict with sync results (success/failed counts)
        """
        if not self.is_authenticated():
            return {"success": 0, "failed": 0, "pending": len(self.pending_queue)}
        
        success = 0
        failed = 0
        remaining = []
        
        for operation in self.pending_queue:
            try:
                # In production: send to appropriate endpoint
                # self._post(endpoint, path, operation.payload)
                success += 1
                logger.info(f"[PLATFORM] Synced {operation.operation_id}")
            except Exception as e:
                operation.retry_count += 1
                if operation.retry_count < 3:
                    remaining.append(operation)
                else:
                    failed += 1
                    logger.error(f"[PLATFORM] Failed to sync {operation.operation_id}: {e}")
        
        self.pending_queue = remaining
        self._save_state()
        
        if self.on_sync_complete:
            self.on_sync_complete({"success": success, "failed": failed})
        
        return {"success": success, "failed": failed, "pending": len(remaining)}
    
    def get_queue_status(self) -> Dict[str, Any]:
        """Get offline queue status."""
        by_type = {}
        for op in self.pending_queue:
            t = op.item_type.value
            by_type[t] = by_type.get(t, 0) + 1
        
        oldest = min(op.created_at for op in self.pending_queue) if self.pending_queue else None
        
        return {
            "total_pending": len(self.pending_queue),
            "by_type": by_type,
            "oldest_operation": oldest,
            "oldest_age_hours": (time.time() - oldest) / 3600 if oldest else None
        }
    
    # ========================================================================
    # PERSISTENCE
    # ========================================================================
    
    def _save_state(self):
        """Save client state to disk."""
        state = {
            "credentials": self.credentials.to_dict() if self.credentials else None,
            "device_identity": self.device_identity.to_dict() if self.device_identity else None,
            "pending_queue": [op.to_dict() for op in self.pending_queue],
            "platform_pubkey": self.platform_pubkey,
            "saved_at": time.time()
        }
        
        path = self.persistence_dir / "client_state.json"
        try:
            with open(path, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"[PLATFORM] Failed to save state: {e}")
    
    def _load_state(self):
        """Load client state from disk."""
        path = self.persistence_dir / "client_state.json"
        
        if not path.exists():
            return
        
        try:
            with open(path, 'r') as f:
                state = json.load(f)
            
            if state.get("credentials"):
                self.credentials = PlatformCredentials.from_dict(state["credentials"])
            
            if state.get("device_identity"):
                data = state["device_identity"]
                self.device_identity = DeviceIdentity(
                    device_id=data["device_id"],
                    device_pubkey_id=data["device_pubkey_id"],
                    manifest_hash=data["manifest_hash"],
                    last_seen=data["last_seen"]
                )
            
            self.pending_queue = [QueuedOperation.from_dict(op) for op in state.get("pending_queue", [])]
            self.platform_pubkey = state.get("platform_pubkey")
            
            logger.info(f"[PLATFORM] Loaded state: {len(self.pending_queue)} pending ops")
        except Exception as e:
            logger.error(f"[PLATFORM] Failed to load state: {e}")
    
    # ========================================================================
    # UTILITY
    # ========================================================================
    
    def get_status(self) -> Dict[str, Any]:
        """Get full client status."""
        return {
            "authenticated": self.is_authenticated(),
            "user_id": self.get_user_id(),
            "device_bound": self.device_identity is not None,
            "queue": self.get_queue_status(),
            "credentials_expired": self.credentials.is_expired() if self.credentials else None
        }


# ============================================================================
# PLATFORM-SIGNED PACK VERIFIER
# ============================================================================

class PackVerifier:
    """Verifies platform-signed class packs."""
    
    def __init__(self, platform_pubkey: str):
        self.platform_pubkey = platform_pubkey
    
    def verify_class_pack(self, pack: Dict[str, Any]) -> bool:
        """
        Verify a class pack signature.
        
        Returns:
            True if signature is valid
        """
        signature = pack.get("signature", "")
        
        # In production: verify with platform public key
        # For MVP: check if signature starts with expected prefix
        if not signature.startswith("platform_sign_"):
            logger.warning("[PACK] Invalid signature format")
            return False
        
        # Check pack origin
        if pack.get("policy", {}).get("origin") != "CLASS":
            logger.warning("[PACK] Invalid origin")
            return False
        
        logger.info("[PACK] Class pack verified")
        return True
    
    def is_transferable(self, pack: Dict[str, Any]) -> bool:
        """Check if pack content is transferable."""
        policy = pack.get("policy", {})
        
        # Direct class payload is never transferable
        if policy.get("origin") == "CLASS" and not policy.get("transferable", False):
            return False
        
        return True


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def create_platform_client(base_url: str = None,
                            persistence_dir: str = "./offline_ai_data/platform") -> PlatformClient:
    """Create a platform client."""
    return PlatformClient(base_url or "https://api.agora-ai.example.com", persistence_dir)


# Export public API
__all__ = [
    'PlatformEndpoint',
    'QueueItemType',
    'PlatformCredentials',
    'DeviceIdentity',
    'QueuedOperation',
    'PlatformClient',
    'PackVerifier',
    'create_platform_client',
]