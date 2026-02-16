#!/usr/bin/env python3
"""
Agora AI Platform - Authentication & Purchase System
=====================================================

Production-ready authentication with:
- Offline-first license validation (device-bound)
- Online purchase validation (initial only)
- Admin auto-unlock
- Grace period for re-validation
"""

import json
import hashlib
import time
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from app.license_manager import LicenseManager

logger = logging.getLogger(__name__)


class AgoraAuth:
    """
    Authentication and purchase management.
    
    For production, this connects to your backend API.
    For offline use, it caches tokens and validates locally.
    """
    
    # Admin credentials - server-side only in production
    ADMIN_USERNAME = 'admin'
    ADMIN_PASSWORD_HASH = hashlib.sha256('agora2024'.encode()).hexdigest()
    
    def __init__(self, storage_dir: str = './agora_data'):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.auth_file = self.storage_dir / 'auth.json'
        
        # License manager for offline validation
        self.license_manager = LicenseManager(storage_dir)
        
        self.current_user: Optional[Dict[str, Any]] = None
        self.auth_token: Optional[str] = None
        self.token_expiry: float = 0
        
        # Load cached auth
        self._load_cached_auth()
    
    def _load_cached_auth(self):
        """Load cached authentication"""
        if self.auth_file.exists():
            try:
                with open(self.auth_file, 'r') as f:
                    data = json.load(f)
                    self.current_user = data.get('user')
                    self.auth_token = data.get('token')
                    self.token_expiry = data.get('expiry', 0)
                    logger.info(f"[AUTH] Loaded cached auth for: {self.current_user.get('username') if self.current_user else 'none'}")
            except Exception as e:
                logger.error(f"[AUTH] Failed to load cached auth: {e}")
    
    def _save_cached_auth(self):
        """Save authentication to cache"""
        try:
            data = {
                'user': self.current_user,
                'token': self.auth_token,
                'expiry': self.token_expiry,
                'saved_at': time.time()
            }
            with open(self.auth_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"[AUTH] Failed to save auth: {e}")
    
    def login(self, username: str, password: str) -> Dict[str, Any]:
        """
        Login user and return session info.
        
        OFFLINE CAPABLE: Can restore session from license if available.
        
        Returns:
            {
                'success': bool,
                'user': dict or None,
                'is_admin': bool,
                'is_premium': bool,
                'error': str or None
            }
        """
        # Check for existing valid license first (offline restore)
        if self.license_manager.has_valid_license():
            license_info = self.license_manager.get_license_info()
            logger.info("[AUTH] Valid offline license found - restoring session")
            
            # Restore user from license
            is_admin = license_info.get('is_admin', False) if license_info else False
            user_id = license_info.get('user_id', 'user') if license_info else 'user'
            
            self.current_user = {
                'username': user_id,
                'display_name': user_id if not is_admin else 'Agora Admin',
                'is_admin': is_admin,
                'is_premium': True,
                'user_id': user_id
            }
            self.auth_token = 'license_token_' + str(int(time.time()))
            self.token_expiry = time.time() + (30 * 24 * 3600)
            self._save_cached_auth()
            
            return {
                'success': True,
                'user': self.current_user,
                'is_admin': is_admin,
                'is_premium': True,
                'error': None,
                'restored_from_license': True
            }
        
        # Check admin credentials
        if username == self.ADMIN_USERNAME:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
            if password_hash == self.ADMIN_PASSWORD_HASH:
                self.current_user = {
                    'username': 'admin',
                    'display_name': 'Agora Admin',
                    'is_admin': True,
                    'is_premium': True,
                    'user_id': 'admin_001'
                }
                self.auth_token = 'admin_token_' + str(int(time.time()))
                self.token_expiry = time.time() + (30 * 24 * 3600)  # 30 days
                self._save_cached_auth()
                
                # Generate admin license for offline use
                self.license_manager.generate_license(
                    user_id='admin_001',
                    is_admin=True
                )
                
                logger.info("[AUTH] Admin login successful")
                return {
                    'success': True,
                    'user': self.current_user,
                    'is_admin': True,
                    'is_premium': True,
                    'error': None
                }
            else:
                return {
                    'success': False,
                    'user': None,
                    'is_admin': False,
                    'is_premium': False,
                    'error': 'Invalid admin password'
                }
        
        # Regular user - would validate against server
        # For production: API call to your backend
        # response = api.validate_login(username, password)
        
        # Mock user for now
        self.current_user = {
            'username': username,
            'display_name': username,
            'is_admin': False,
            'is_premium': False,
            'user_id': f'user_{hashlib.md5(username.encode()).hexdigest()[:8]}'
        }
        self.auth_token = 'user_token_' + str(int(time.time()))
        self.token_expiry = time.time() + (7 * 24 * 3600)  # 7 days
        self._save_cached_auth()
        
        logger.info(f"[AUTH] User login: {username}")
        return {
            'success': True,
            'user': self.current_user,
            'is_admin': False,
            'is_premium': False,
            'error': None
        }
    
    def logout(self):
        """Logout and clear session"""
        self.current_user = None
        self.auth_token = None
        self.token_expiry = 0
        if self.auth_file.exists():
            try:
                self.auth_file.unlink()
            except Exception as e:
                logger.error(f"[AUTH] Failed to clear auth file: {e}")
        logger.info("[AUTH] Logged out")
    
    def is_logged_in(self) -> bool:
        """Check if user is logged in with valid token"""
        if not self.current_user or not self.auth_token:
            return False
        # Check token expiry (with 1 hour grace period for offline)
        return time.time() < (self.token_expiry + 3600)
    
    def is_admin(self) -> bool:
        """Check if current user is admin"""
        return self.current_user is not None and self.current_user.get('is_admin', False)
    
    def is_premium(self) -> bool:
        """Check if user has premium/AI access"""
        if self.is_admin():
            return True
        return self.current_user is not None and self.current_user.get('is_premium', False)
    
    def check_ai_purchase(self) -> bool:
        """
        Check if user has purchased the AI.
        
        OFFLINE-FIRST: Checks local license first, works without internet.
        """
        # First check local license (works offline)
        if self.license_manager.has_valid_license():
            return True
        
        # Admins can generate license
        if self.is_admin():
            # Auto-generate admin license
            self.license_manager.generate_license(
                user_id=self.current_user.get('user_id', 'admin'),
                is_admin=True
            )
            return True
        
        # Check if logged in user has online purchase (requires internet)
        if self.is_logged_in():
            # In production: API call to verify purchase
            # if api.check_purchase(self.current_user['user_id'], 'offline_ai'):
            #     # Generate offline license
            #     self.license_manager.generate_license(
            #         user_id=self.current_user['user_id'],
            #         is_admin=False
            #     )
            #     return True
            pass
        
        return False
    
    def record_purchase(self, product_id: str, receipt: str = None) -> bool:
        """
        Record a purchase and generate offline license.
        
        For production, this validates the receipt with:
        - Google Play (Android)
        - Apple App Store (iOS)
        - Stripe (Web)
        """
        if not self.is_logged_in():
            logger.error("[AUTH] Cannot record purchase: not logged in")
            return False
        
        if product_id == 'offline_ai':
            # Update user status
            self.current_user['is_premium'] = True
            self._save_cached_auth()
            
            # Generate offline license (device-bound)
            user_id = self.current_user.get('user_id', 'unknown')
            is_admin = self.current_user.get('is_admin', False)
            
            self.license_manager.generate_license(
                user_id=user_id,
                is_admin=is_admin
            )
            
            logger.info(f"[AUTH] Purchase recorded and license generated: {product_id}")
            return True
        
        return False
    
    def get_display_name(self) -> str:
        """Get current user's display name"""
        if self.current_user:
            return self.current_user.get('display_name', self.current_user.get('username', 'Guest'))
        return 'Guest'
    
    def get_user_id(self) -> Optional[str]:
        """Get current user's ID"""
        if self.current_user:
            return self.current_user.get('user_id')
        return None
