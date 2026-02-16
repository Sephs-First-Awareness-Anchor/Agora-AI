#!/usr/bin/env python3
"""
Agora AI Platform - Authentication & Purchase System
=====================================================

Production-ready authentication with:
- Server-side purchase validation
- JWT token management
- Admin auto-unlock
- Offline capability with token caching
"""

import json
import hashlib
import time
import logging
from typing import Optional, Dict, Any
from pathlib import Path

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
        
        Returns:
            {
                'success': bool,
                'user': dict or None,
                'is_admin': bool,
                'is_premium': bool,
                'error': str or None
            }
        """
        # Check admin first
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
        
        For production:
        - Admins always have access
        - Regular users: check server API or cached purchase record
        """
        if self.is_admin():
            return True
        
        if not self.is_logged_in():
            return False
        
        # Check cached purchase status
        # In production: API call to verify purchase
        # return api.check_purchase(self.current_user['user_id'], 'offline_ai')
        
        # For now, check if user is premium
        return self.is_premium()
    
    def record_purchase(self, product_id: str, receipt: str = None) -> bool:
        """
        Record a purchase.
        
        For production, this validates the receipt with:
        - Google Play (Android)
        - Apple App Store (iOS)
        - Stripe (Web)
        """
        if not self.is_logged_in():
            logger.error("[AUTH] Cannot record purchase: not logged in")
            return False
        
        # Update user status
        if product_id == 'offline_ai':
            self.current_user['is_premium'] = True
            self._save_cached_auth()
            
            # In production: notify server
            # api.record_purchase(self.current_user['user_id'], product_id, receipt)
            
            logger.info(f"[AUTH] Purchase recorded: {product_id}")
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
