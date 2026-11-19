#!/usr/bin/env python3
"""
Agora AI Platform - Entity & Memory Management
===============================================

Manages AI entity identity across devices:
- Entity ID: Unique AI identity (follows user)
- Memory ID: Specific to device/instance
- Device binding prevents duplicate active instances
- Transfer system for moving AI between devices
- Optional: Multi-device sync through platform

ANDROID-FRIENDLY: Uses privacy-compliant device identification
(no ANDROID_ID, MAC address, or sensitive system APIs)
"""

import json
import hashlib
import time
import uuid
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum
from app.android_device import AndroidFriendlyDevice

logger = logging.getLogger(__name__)


class EntityStatus(Enum):
    """Entity activation status"""
    ACTIVE = "active"          # Currently running on this device
    TRANSFERRED = "transferred"  # Moved to another device
    INACTIVE = "inactive"      # Not currently active anywhere
    RESET = "reset"            # Memory was reset


class DeviceBinding:
    """Represents a device binding for an entity"""
    
    def __init__(self, device_fingerprint: str, device_name: str, 
                 activated_at: float = None, last_seen: float = None):
        self.device_fingerprint = device_fingerprint
        self.device_name = device_name
        self.activated_at = activated_at or time.time()
        self.last_seen = last_seen or time.time()
        self.is_active = True
    
    def to_dict(self) -> dict:
        return {
            'device_fingerprint': self.device_fingerprint,
            'device_name': self.device_name,
            'activated_at': self.activated_at,
            'last_seen': self.last_seen,
            'is_active': self.is_active
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'DeviceBinding':
        binding = cls(
            device_fingerprint=data['device_fingerprint'],
            device_name=data['device_name'],
            activated_at=data.get('activated_at'),
            last_seen=data.get('last_seen')
        )
        binding.is_active = data.get('is_active', True)
        return binding


class EntityIdentity:
    """
    Represents an AI entity's identity.
    
    Entity ID: Global identifier for this AI (follows user across devices)
    Memory ID: Device-specific memory instance
    """
    
    def __init__(self, entity_id: str = None, memory_id: str = None,
                 user_id: str = None, created_at: float = None):
        self.entity_id = entity_id or self._generate_entity_id()
        self.memory_id = memory_id or self._generate_memory_id()
        self.user_id = user_id or "anonymous"
        self.created_at = created_at or time.time()
        
        # Device bindings
        self.device_bindings: List[DeviceBinding] = []
        self.active_device_fingerprint: Optional[str] = None
        
        # Status
        self.status = EntityStatus.INACTIVE
        self.transferred_from: Optional[str] = None  # Previous device fingerprint
        self.transfer_history: List[dict] = []
        
        # Multi-device sync (optional)
        self.allow_multi_device = False  # Default: one device at a time
        self.sync_enabled = False
    
    def _generate_entity_id(self) -> str:
        """Generate unique entity ID"""
        # Format: AGR-ENTITY-{timestamp}-{random}
        import uuid
        timestamp = int(time.time())
        random_part = uuid.uuid4().hex[:8].upper()
        return f"AGR-ENTITY-{timestamp}-{random_part}"
    
    def _generate_memory_id(self) -> str:
        """Generate unique memory ID for this device instance"""
        timestamp = int(time.time() * 1000)
        return f"MEM-{timestamp}-{uuid.uuid4().hex[:6].upper()}"
    
    def bind_to_device(self, device_fingerprint: str, device_name: str) -> bool:
        """
        Bind entity to current device.
        
        Returns False if entity is already active on another device
        and multi-device is not enabled.
        """
        # Check if already active elsewhere
        if (self.active_device_fingerprint and 
            self.active_device_fingerprint != device_fingerprint and
            not self.allow_multi_device):
            # Entity is active on another device
            logger.warning(f"[ENTITY] Entity {self.entity_id[:8]}... already active on another device")
            return False
        
        # Create or update device binding
        existing = self._get_device_binding(device_fingerprint)
        if existing:
            existing.last_seen = time.time()
            existing.is_active = True
        else:
            binding = DeviceBinding(device_fingerprint, device_name)
            self.device_bindings.append(binding)
        
        self.active_device_fingerprint = device_fingerprint
        self.status = EntityStatus.ACTIVE
        
        logger.info(f"[ENTITY] Entity {self.entity_id[:8]}... bound to device {device_name}")
        return True
    
    def _get_device_binding(self, fingerprint: str) -> Optional[DeviceBinding]:
        """Get binding for specific device"""
        for binding in self.device_bindings:
            if binding.device_fingerprint == fingerprint:
                return binding
        return None
    
    def transfer_to_new_device(self, new_device_fingerprint: str, 
                               new_device_name: str) -> bool:
        """
        Transfer entity to a new device.
        Invalidates the old device's access.
        """
        old_device = self.active_device_fingerprint
        
        # Mark old device as transferred
        if old_device:
            old_binding = self._get_device_binding(old_device)
            if old_binding:
                old_binding.is_active = False
        
        # Record transfer
        self.transfer_history.append({
            'from_device': old_device,
            'to_device': new_device_fingerprint,
            'transferred_at': time.time()
        })
        
        # Create new memory ID for new device
        self.memory_id = self._generate_memory_id()
        self.transferred_from = old_device
        
        # Bind to new device
        success = self.bind_to_device(new_device_fingerprint, new_device_name)
        if success:
            self.status = EntityStatus.TRANSFERRED
            logger.info(f"[ENTITY] Entity {self.entity_id[:8]}... transferred to {new_device_name}")
        
        return success
    
    def reset_memory(self) -> str:
        """
        Reset entity memory.
        Generates new memory ID, invalidates old memory.
        """
        old_memory = self.memory_id
        self.memory_id = self._generate_memory_id()
        self.status = EntityStatus.RESET
        
        # Clear device bindings except current
        current_device = self.active_device_fingerprint
        self.device_bindings = [
            b for b in self.device_bindings 
            if b.device_fingerprint == current_device
        ]
        
        logger.info(f"[ENTITY] Memory reset: {old_memory[:12]}... -> {self.memory_id[:12]}...")
        return self.memory_id
    
    def clone_for_multi_device(self, new_device_fingerprint: str,
                               new_device_name: str) -> 'EntityIdentity':
        """
        Create a clone of this entity for multi-device use.
        Shares entity ID but has separate memory.
        """
        if not self.allow_multi_device:
            raise ValueError("Multi-device not enabled for this entity")
        
        clone = EntityIdentity(
            entity_id=self.entity_id,  # Same entity
            user_id=self.user_id
        )
        clone.memory_id = self._generate_memory_id()  # Different memory
        clone.allow_multi_device = True
        clone.sync_enabled = self.sync_enabled
        
        # Copy relevant bindings
        clone.device_bindings = [b for b in self.device_bindings]
        
        # Bind to new device
        clone.bind_to_device(new_device_fingerprint, new_device_name)
        
        logger.info(f"[ENTITY] Created clone for multi-device: {new_device_name}")
        return clone
    
    def to_dict(self) -> dict:
        """Serialize to dict"""
        return {
            'entity_id': self.entity_id,
            'memory_id': self.memory_id,
            'user_id': self.user_id,
            'created_at': self.created_at,
            'device_bindings': [b.to_dict() for b in self.device_bindings],
            'active_device_fingerprint': self.active_device_fingerprint,
            'status': self.status.value,
            'transferred_from': self.transferred_from,
            'transfer_history': self.transfer_history,
            'allow_multi_device': self.allow_multi_device,
            'sync_enabled': self.sync_enabled
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'EntityIdentity':
        """Deserialize from dict"""
        entity = cls(
            entity_id=data['entity_id'],
            memory_id=data['memory_id'],
            user_id=data['user_id'],
            created_at=data.get('created_at')
        )
        entity.device_bindings = [
            DeviceBinding.from_dict(b) for b in data.get('device_bindings', [])
        ]
        entity.active_device_fingerprint = data.get('active_device_fingerprint')
        entity.status = EntityStatus(data.get('status', 'inactive'))
        entity.transferred_from = data.get('transferred_from')
        entity.transfer_history = data.get('transfer_history', [])
        entity.allow_multi_device = data.get('allow_multi_device', False)
        entity.sync_enabled = data.get('sync_enabled', False)
        return entity


class EntityManager:
    """
    Manages entity identities and device bindings.
    Ensures one active instance per entity (unless multi-device enabled).
    """
    
    def __init__(self, storage_dir: str = './agora_data'):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.entity_file = self.storage_dir / 'entity_identity.json'
        
        self.current_entity: Optional[EntityIdentity] = None
        
        # Android-friendly device identification
        self._device_helper = AndroidFriendlyDevice(storage_dir)
        
        # Load existing entity
        self._load_entity()
    
    def _get_device_fingerprint(self) -> str:
        """Get device fingerprint (Android-friendly, no sensitive IDs)"""
        return self._device_helper.get_device_id()
    
    def _get_device_name(self) -> str:
        """Get device name (Android-friendly)"""
        return self._device_helper.get_device_name()
    
    def _load_entity(self):
        """Load existing entity from storage"""
        if self.entity_file.exists():
            try:
                with open(self.entity_file, 'r') as f:
                    data = json.load(f)
                self.current_entity = EntityIdentity.from_dict(data)
                logger.info(f"[ENTITY] Loaded entity: {self.current_entity.entity_id[:16]}...")
            except Exception as e:
                logger.error(f"[ENTITY] Failed to load entity: {e}")
    
    def _save_entity(self):
        """Save entity to storage"""
        if self.current_entity:
            try:
                with open(self.entity_file, 'w') as f:
                    json.dump(self.current_entity.to_dict(), f, indent=2)
            except Exception as e:
                logger.error(f"[ENTITY] Failed to save entity: {e}")
    
    def create_new_entity(self, user_id: str = None) -> EntityIdentity:
        """Create new AI entity"""
        self.current_entity = EntityIdentity(user_id=user_id)
        
        # Bind to this device
        device_fp = self._get_device_fingerprint()
        device_name = self._get_device_name()
        self.current_entity.bind_to_device(device_fp, device_name)
        
        self._save_entity()
        logger.info(f"[ENTITY] Created new entity: {self.current_entity.entity_id}")
        
        return self.current_entity
    
    def activate_entity(self) -> Optional[EntityIdentity]:
        """
        Activate entity on this device.
        Returns None if entity is active on another device.
        """
        if not self.current_entity:
            return None
        
        device_fp = self._get_device_fingerprint()
        device_name = self._get_device_name()
        
        # Try to bind to this device
        success = self.current_entity.bind_to_device(device_fp, device_name)
        
        if success:
            self._save_entity()
            return self.current_entity
        else:
            logger.warning("[ENTITY] Cannot activate - entity active on another device")
            return None
    
    def transfer_entity(self, new_device_code: str = None) -> bool:
        """
        Initiate transfer to new device.
        In production, would generate transfer code.
        """
        if not self.current_entity:
            return False
        
        # Generate transfer token
        transfer_token = hashlib.sha256(
            f"{self.current_entity.entity_id}:{time.time()}:transfer".encode()
        ).hexdigest()[:16].upper()
        
        # Mark as ready to transfer
        self.current_entity.status = EntityStatus.INACTIVE
        self._save_entity()
        
        logger.info(f"[ENTITY] Transfer initiated. Token: {transfer_token}")
        return transfer_token
    
    def accept_transfer(self, transfer_token: str, 
                       previous_entity_data: dict) -> Optional[EntityIdentity]:
        """Accept transfer from another device"""
        try:
            # Load transferred entity
            old_entity = EntityIdentity.from_dict(previous_entity_data)
            
            # Perform transfer
            device_fp = self._get_device_fingerprint()
            device_name = self._get_device_name()
            
            if old_entity.transfer_to_new_device(device_fp, device_name):
                self.current_entity = old_entity
                self._save_entity()
                logger.info("[ENTITY] Transfer completed successfully")
                return self.current_entity
            
        except Exception as e:
            logger.error(f"[ENTITY] Transfer failed: {e}")
        
        return None
    
    def reset_entity_memory(self) -> str:
        """Reset entity memory"""
        if not self.current_entity:
            raise ValueError("No entity to reset")
        
        new_memory_id = self.current_entity.reset_memory()
        self._save_entity()
        
        return new_memory_id
    
    def get_entity_info(self) -> Optional[dict]:
        """Get current entity info"""
        if not self.current_entity:
            return None
        
        return {
            'entity_id': self.current_entity.entity_id,
            'memory_id': self.current_entity.memory_id,
            'entity_short': self.current_entity.entity_id[:16] + '...',
            'memory_short': self.current_entity.memory_id[:12] + '...',
            'status': self.current_entity.status.value,
            'device_count': len(self.current_entity.device_bindings),
            'is_active_here': self.current_entity.active_device_fingerprint == self._get_device_fingerprint(),
            'allow_multi_device': self.current_entity.allow_multi_device
        }
    
    def has_active_entity(self) -> bool:
        """Check if there's an active entity"""
        return (self.current_entity is not None and 
                self.current_entity.status == EntityStatus.ACTIVE and
                self.current_entity.active_device_fingerprint == self._get_device_fingerprint())
