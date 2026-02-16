#!/usr/bin/env python3
"""
Android-Friendly Device Identification
======================================

Privacy-compliant device identification that won't trigger security warnings.
Uses Android-recommended methods instead of sensitive identifiers.
"""

import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class AndroidFriendlyDevice:
    """
    Privacy-friendly device identification.
    
    AVOIDS:
    - ANDROID_ID (flagged as sensitive)
    - MAC address (restricted on Android 10+)
    - IMEI (requires dangerous permission)
    
    USES:
    - App-specific generated ID (stored securely)
    - Hardware characteristics (non-sensitive)
    - Installation-specific tokens
    """
    
    def __init__(self, storage_dir: str = './agora_data'):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.device_id_file = self.storage_dir / '.device_id'
        
        self._device_id = None
    
    def get_device_id(self) -> str:
        """
        Get or create device identifier.
        
        This creates a stable ID that:
        - Persists across app restarts
        - Survives app updates
        - Is unique per device + app installation
        - Doesn't use sensitive system identifiers
        """
        if self._device_id:
            return self._device_id
        
        # Try to load existing ID
        if self.device_id_file.exists():
            try:
                with open(self.device_id_file, 'r') as f:
                    self._device_id = f.read().strip()
                if self._device_id:
                    return self._device_id
            except Exception as e:
                logger.warning(f"[DEVICE] Could not read device ID: {e}")
        
        # Generate new ID using non-sensitive characteristics
        self._device_id = self._generate_device_id()
        
        # Save for persistence
        try:
            with open(self.device_id_file, 'w') as f:
                f.write(self._device_id)
        except Exception as e:
            logger.error(f"[DEVICE] Could not save device ID: {e}")
        
        return self._device_id
    
    def _generate_device_id(self) -> str:
        """
        Generate device ID from non-sensitive characteristics.
        """
        import os
        import sys
        import time
        
        components = []
        
        # Use hardware info that's not considered sensitive
        # These are visible to any app and don't require permissions
        try:
            import platform
            # CPU architecture (non-sensitive)
            components.append(platform.machine())
            # Platform (Android/Linux)
            components.append(platform.system())
        except:
            pass
        
        # App-specific path (unique per installation)
        try:
            components.append(os.path.abspath(self.storage_dir))
        except:
            pass
        
        # Random seed for uniqueness
        import uuid
        components.append(uuid.uuid4().hex[:16])
        
        # Timestamp (installation time)
        components.append(str(int(time.time())))
        
        # Combine and hash
        combined = '|'.join(filter(None, components))
        device_id = hashlib.sha256(combined.encode()).hexdigest()[:32]
        
        logger.info(f"[DEVICE] Generated new device ID: {device_id[:8]}...")
        return device_id
    
    def get_device_name(self) -> str:
        """
        Get device name safely.
        Avoids JNI calls that could trigger security warnings.
        """
        import platform
        import os
        
        # Use platform info instead of JNI
        try:
            if 'ANDROID_ARGUMENT' in os.environ:
                return "Android Device"
        except:
            pass
        
        return f"{platform.system()} Device"
    
    def clear_device_id(self):
        """Clear device ID (for reset/transfer)"""
        if self.device_id_file.exists():
            try:
                self.device_id_file.unlink()
            except:
                pass
        self._device_id = None
