#!/usr/bin/env python3
"""
Agora AI Platform - Offline License Manager
============================================

Offline-first license validation system:
- License bound to device (ANDROID-FRIENDLY, no sensitive IDs)
- Encrypted local storage
- Works 100% offline after initial activation
- Grace period for re-validation
- Admin override capability
"""

import json
import hashlib
import hmac
import time
import logging
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from app.android_device import AndroidFriendlyDevice

logger = logging.getLogger(__name__)


class LicenseManager:
    """
    Manages AI purchase license locally for offline use.
    
    Flow:
    1. First purchase/activation → Online validation → Generate license
    2. License stored encrypted locally, bound to device
    3. Subsequent launches → Validate local license offline
    4. Grace period for periodic re-check (optional)
    """
    
    # Admin unlock key - hardcoded for dev access
    ADMIN_DEVICE_KEY = "AGORA_ADMIN_UNLOCK_v1"
    
    def __init__(self, storage_dir: str = './agora_data'):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.license_file = self.storage_dir / 'ai_license.enc'
        self.meta_file = self.storage_dir / 'license_meta.json'
        
        # Android-friendly device identification (no sensitive IDs)
        self._device_helper = AndroidFriendlyDevice(storage_dir)
        self._device_id = None
        self._cached_license = None
    
    def _get_device_fingerprint(self) -> str:
        """
        Get device fingerprint using Android-friendly method.
        AVOIDS: ANDROID_ID, MAC address, IMEI (flagged as sensitive)
        """
        if self._device_id:
            return self._device_id
        
        self._device_id = self._device_helper.get_device_id()
        return self._device_id
    
    def _derive_key(self, device_id: str) -> bytes:
        """Derive encryption key from device fingerprint"""
        # Use device ID + app secret to create key
        app_secret = "Agora_AI_Offline_v2024"  # App-level secret
        key_material = f"{device_id}:{app_secret}"
        return hashlib.sha256(key_material.encode()).digest()
    
    def _encrypt_license(self, license_data: dict) -> bytes:
        """Encrypt license data using device-bound key"""
        import base64
        device_id = self._get_device_fingerprint()
        key = self._derive_key(device_id)
        
        # Simple XOR encryption with HMAC for integrity
        # In production, use proper crypto like Fernet
        plaintext = json.dumps(license_data).encode()
        encrypted = bytearray()
        
        for i, byte in enumerate(plaintext):
            encrypted.append(byte ^ key[i % len(key)])
        
        # Add HMAC for tamper detection
        mac = hmac.new(key, bytes(encrypted), hashlib.sha256).digest()
        
        return base64.b64encode(mac + bytes(encrypted))
    
    def _decrypt_license(self, encrypted_data: bytes) -> Optional[dict]:
        """Decrypt and validate license"""
        import base64
        device_id = self._get_device_fingerprint()
        key = self._derive_key(device_id)
        
        try:
            data = base64.b64decode(encrypted_data)
            stored_mac = data[:32]
            encrypted = data[32:]
            
            # Verify HMAC
            computed_mac = hmac.new(key, encrypted, hashlib.sha256).digest()
            if not hmac.compare_digest(stored_mac, computed_mac):
                logger.error("[LICENSE] HMAC mismatch - license tampered!")
                return None
            
            # Decrypt
            decrypted = bytearray()
            for i, byte in enumerate(encrypted):
                decrypted.append(byte ^ key[i % len(key)])
            
            license_data = json.loads(bytes(decrypted).decode())
            
            # Verify device binding
            if license_data.get('device_id') != device_id:
                # Check if it's admin key
                if license_data.get('device_id') != self.ADMIN_DEVICE_KEY:
                    logger.error("[LICENSE] Device mismatch - not bound to this device")
                    return None
            
            return license_data
            
        except Exception as e:
            logger.error(f"[LICENSE] Decryption failed: {e}")
            return None
    
    def has_valid_license(self) -> bool:
        """Check if valid offline license exists"""
        if self._cached_license:
            return self._validate_license_data(self._cached_license)
        
        if not self.license_file.exists():
            return False
        
        try:
            with open(self.license_file, 'rb') as f:
                encrypted = f.read()
            
            license_data = self._decrypt_license(encrypted)
            if license_data and self._validate_license_data(license_data):
                self._cached_license = license_data
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"[LICENSE] Failed to check license: {e}")
            return False
    
    def _validate_license_data(self, license_data: dict) -> bool:
        """Validate license data (expiry, etc.)"""
        # Check expiry if present
        expiry = license_data.get('expires_at')
        if expiry:
            if time.time() > expiry:
                logger.warning("[LICENSE] License expired")
                return False
        
        # Check product
        if license_data.get('product') != 'offline_ai':
            return False
        
        # Check grace period for re-validation (optional)
        last_check = license_data.get('last_online_check', 0)
        grace_days = license_data.get('grace_days', 30)
        if time.time() - last_check > (grace_days * 24 * 3600):
            logger.warning("[LICENSE] Grace period exceeded - needs online re-validation")
            # Still allow use but flag for re-check
            license_data['needs_revalidation'] = True
        
        return True
    
    def generate_license(self, user_id: str, is_admin: bool = False, 
                        duration_days: int = 365) -> dict:
        """
        Generate new offline license.
        
        Called after successful online purchase validation.
        """
        device_id = self.ADMIN_DEVICE_KEY if is_admin else self._get_device_fingerprint()
        
        license_data = {
            'product': 'offline_ai',
            'user_id': user_id,
            'device_id': device_id,
            'created_at': time.time(),
            'expires_at': time.time() + (duration_days * 24 * 3600) if duration_days else None,
            'last_online_check': time.time(),
            'grace_days': 30,
            'is_admin': is_admin,
            'version': 1
        }
        
        # Save encrypted
        encrypted = self._encrypt_license(license_data)
        with open(self.license_file, 'wb') as f:
            f.write(encrypted)
        
        # Save metadata (unencrypted, for info only)
        meta = {
            'user_id': user_id,
            'created_at': datetime.now().isoformat(),
            'is_admin': is_admin,
            'has_license': True
        }
        with open(self.meta_file, 'w') as f:
            json.dump(meta, f, indent=2)
        
        self._cached_license = license_data
        logger.info(f"[LICENSE] Generated license for: {user_id} (admin={is_admin})")
        
        return license_data
    
    def revoke_license(self):
        """Revoke/delete license"""
        if self.license_file.exists():
            self.license_file.unlink()
        if self.meta_file.exists():
            self.meta_file.unlink()
        self._cached_license = None
        logger.info("[LICENSE] License revoked")
    
    def update_last_check(self):
        """Update last online check timestamp"""
        if self._cached_license:
            self._cached_license['last_online_check'] = time.time()
            encrypted = self._encrypt_license(self._cached_license)
            with open(self.license_file, 'wb') as f:
                f.write(encrypted)
    
    def needs_revalidation(self) -> bool:
        """Check if license needs online re-validation"""
        if not self._cached_license:
            return False
        return self._cached_license.get('needs_revalidation', False)
    
    def get_license_info(self) -> Optional[dict]:
        """Get human-readable license info"""
        if not self.has_valid_license():
            return None
        
        if self.meta_file.exists():
            try:
                with open(self.meta_file, 'r') as f:
                    return json.load(f)
            except:
                pass
        
        return {'has_license': True}
