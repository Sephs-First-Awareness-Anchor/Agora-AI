#!/usr/bin/env python3
"""
Offline AI Hub Discovery
========================
Agora AI Platform - Phase 1

Manages Agora "meeting places" (hubs) for real-world companion exchanges.

Features:
- Curated hub list per location
- Hub caching for offline use
- GPS radius validation
- Safety tags and metadata
- Hub proposals and voting (future)
"""

import json
import math
import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMERATIONS
# ============================================================================

class HubStatus(Enum):
    """Status of a hub."""
    ACTIVE = "active"
    PENDING = "pending"      # Under review
    CLOSED = "closed"
    SEASONAL = "seasonal"    # Only certain times


class SafetyTag(Enum):
    """Safety characteristics of a hub."""
    WELL_LIT = "well_lit"
    PUBLIC = "public"
    CAMERA_PRESENCE = "camera_presence"
    STAFFED = "staffed"
    EMERGENCY_ACCESS = "emergency_access"


class HubType(Enum):
    """Type of hub location."""
    PARK = "park"
    LIBRARY = "library"
    PLAZA = "plaza"
    CAFE = "cafe"
    COMMUNITY_CENTER = "community_center"
    UNIVERSITY = "university"
    SHOPPING_AREA = "shopping_area"
    TRANSPORT_HUB = "transport_hub"
    OTHER = "other"


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class GeoLocation:
    """Geographic coordinates."""
    latitude: float
    longitude: float
    accuracy: Optional[float] = None  # GPS accuracy in meters
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "accuracy": self.accuracy
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GeoLocation':
        return cls(
            latitude=data["latitude"],
            longitude=data["longitude"],
            accuracy=data.get("accuracy")
        )
    
    def distance_to(self, other: 'GeoLocation') -> float:
        """
        Calculate distance to another location in meters.
        Uses Haversine formula.
        """
        R = 6371000  # Earth's radius in meters
        
        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c


@dataclass
class OperatingHours:
    """Operating hours for a hub."""
    day: str  # "monday", "tuesday", etc.
    open_time: str  # "09:00"
    close_time: str  # "18:00"
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "day": self.day,
            "open_time": self.open_time,
            "close_time": self.close_time
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OperatingHours':
        return cls(
            day=data["day"],
            open_time=data["open_time"],
            close_time=data["close_time"]
        )


@dataclass
class Hub:
    """
    An Agora meeting place (hub).
    """
    hub_id: str
    name: str
    address: str
    location: GeoLocation
    hub_type: HubType
    status: HubStatus
    
    # Safety and metadata
    safety_tags: List[SafetyTag] = field(default_factory=list)
    recommended_hours: List[OperatingHours] = field(default_factory=list)
    
    # Platform metadata
    created_by: Optional[str] = None  # user_id or "platform"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    # Community features
    rating: float = 0.0  # 0-5
    review_count: int = 0
    reliability_score: float = 0.0  # Based on successful meets
    
    # Caching
    last_synced: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "hub_id": self.hub_id,
            "name": self.name,
            "address": self.address,
            "location": self.location.to_dict(),
            "hub_type": self.hub_type.value,
            "status": self.status.value,
            "safety_tags": [t.value for t in self.safety_tags],
            "recommended_hours": [h.to_dict() for h in self.recommended_hours],
            "created_by": self.created_by,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "rating": self.rating,
            "review_count": self.review_count,
            "reliability_score": self.reliability_score,
            "last_synced": self.last_synced
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Hub':
        return cls(
            hub_id=data["hub_id"],
            name=data["name"],
            address=data["address"],
            location=GeoLocation.from_dict(data["location"]),
            hub_type=HubType(data.get("hub_type", "other")),
            status=HubStatus(data.get("status", "active")),
            safety_tags=[SafetyTag(t) for t in data.get("safety_tags", [])],
            recommended_hours=[OperatingHours.from_dict(h) for h in data.get("recommended_hours", [])],
            created_by=data.get("created_by"),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            rating=data.get("rating", 0.0),
            review_count=data.get("review_count", 0),
            reliability_score=data.get("reliability_score", 0.0),
            last_synced=data.get("last_synced", time.time())
        )
    
    def is_safe(self) -> bool:
        """Check if hub meets minimum safety criteria."""
        return SafetyTag.PUBLIC in self.safety_tags or SafetyTag.WELL_LIT in self.safety_tags
    
    def get_safety_score(self) -> int:
        """Get safety score (0-5) based on tags."""
        score = 0
        if SafetyTag.PUBLIC in self.safety_tags:
            score += 2
        if SafetyTag.WELL_LIT in self.safety_tags:
            score += 1
        if SafetyTag.CAMERA_PRESENCE in self.safety_tags:
            score += 1
        if SafetyTag.STAFFED in self.safety_tags:
            score += 1
        return score


@dataclass
class MeetSession:
    """A pending meet session at a hub."""
    session_id: str
    hub_id: str
    initiator_device_id: str
    initiator_account_id: str
    timestamp: float
    session_token: str  # Rotating token for QR
    status: str = "pending"  # pending, active, completed, cancelled
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "hub_id": self.hub_id,
            "initiator_device_id": self.initiator_device_id,
            "initiator_account_id": self.initiator_account_id,
            "timestamp": self.timestamp,
            "session_token": self.session_token,
            "status": self.status
        }


# ============================================================================
# HUB MANAGER
# ============================================================================

class HubManager:
    """
    Manages hub discovery and caching.
    
    Works offline after initial sync.
    """
    
    def __init__(self, persistence_dir: str = "./offline_ai_data/hubs"):
        self.persistence_dir = Path(persistence_dir)
        self.persistence_dir.mkdir(parents=True, exist_ok=True)
        
        # Cached hubs
        self.hubs: Dict[str, Hub] = {}
        
        # Current location (set by GPS)
        self.current_location: Optional[GeoLocation] = None
        
        # Active meet sessions
        self.active_sessions: Dict[str, MeetSession] = {}
        
        # Load cached hubs
        self._load_hubs()
        
        logger.info(f"[HUB MANAGER] Initialized with {len(self.hubs)} cached hubs")
    
    # ========================================================================
    # HUB MANAGEMENT
    # ========================================================================
    
    def add_hub(self, hub: Hub):
        """Add or update a hub."""
        self.hubs[hub.hub_id] = hub
        self._save_hubs()
        logger.info(f"[HUB] Added/updated hub: {hub.name}")
    
    def get_hub(self, hub_id: str) -> Optional[Hub]:
        """Get a hub by ID."""
        return self.hubs.get(hub_id)
    
    def remove_hub(self, hub_id: str):
        """Remove a hub."""
        if hub_id in self.hubs:
            del self.hubs[hub_id]
            self._save_hubs()
    
    def list_hubs(self, 
                  status: Optional[HubStatus] = None,
                  hub_type: Optional[HubType] = None) -> List[Hub]:
        """List hubs with optional filtering."""
        result = list(self.hubs.values())
        
        if status:
            result = [h for h in result if h.status == status]
        
        if hub_type:
            result = [h for h in result if h.hub_type == hub_type]
        
        return result
    
    # ========================================================================
    # LOCATION-BASED DISCOVERY
    # ========================================================================
    
    def set_current_location(self, location: GeoLocation):
        """Set current GPS location."""
        self.current_location = location
    
    def find_nearby_hubs(self, 
                         radius_meters: float = 5000,
                         min_safety_score: int = 0) -> List[Tuple[Hub, float]]:
        """
        Find hubs within radius of current location.
        
        Returns:
            List of (hub, distance) tuples, sorted by distance
        """
        if not self.current_location:
            logger.warning("[HUB] No current location set")
            return []
        
        nearby = []
        for hub in self.hubs.values():
            if hub.status != HubStatus.ACTIVE:
                continue
            
            if hub.get_safety_score() < min_safety_score:
                continue
            
            distance = self.current_location.distance_to(hub.location)
            if distance <= radius_meters:
                nearby.append((hub, distance))
        
        # Sort by distance
        nearby.sort(key=lambda x: x[1])
        
        return nearby
    
    def find_hubs_in_radius(self,
                            center: GeoLocation,
                            radius_meters: float) -> List[Hub]:
        """Find all hubs within a radius of a center point."""
        result = []
        for hub in self.hubs.values():
            if hub.status != HubStatus.ACTIVE:
                continue
            distance = center.distance_to(hub.location)
            if distance <= radius_meters:
                result.append(hub)
        return result
    
    def is_at_hub(self, hub_id: str, max_distance_meters: float = 100) -> bool:
        """
        Check if currently at a hub (within max distance).
        Used for enforcing "in hub radius" during meets.
        """
        if not self.current_location:
            return False
        
        hub = self.hubs.get(hub_id)
        if not hub:
            return False
        
        distance = self.current_location.distance_to(hub.location)
        return distance <= max_distance_meters
    
    # ========================================================================
    # MEET SESSIONS
    # ========================================================================
    
    def create_meet_session(self, 
                            hub_id: str,
                            device_id: str,
                            account_id: str) -> MeetSession:
        """Create a new meet session."""
        import hashlib
        
        session_id = f"meet_{int(time.time() * 1000)}"
        
        # Generate rotating session token
        token_data = f"{session_id}:{device_id}:{int(time.time() / 300)}"  # Rotates every 5 min
        session_token = hashlib.sha256(token_data.encode()).hexdigest()[:32]
        
        session = MeetSession(
            session_id=session_id,
            hub_id=hub_id,
            initiator_device_id=device_id,
            initiator_account_id=account_id,
            timestamp=time.time(),
            session_token=session_token
        )
        
        self.active_sessions[session_id] = session
        
        logger.info(f"[HUB] Created meet session: {session_id} at hub {hub_id}")
        
        return session
    
    def get_session_qr_data(self, session_id: str) -> Optional[Dict[str, Any]]:
        """
        Get QR code data for a session.
        
        QR contains:
        - session_token
        - device_public_key_id
        - timestamp
        - hub_id
        """
        session = self.active_sessions.get(session_id)
        if not session:
            return None
        
        return {
            "session_token": session.session_token,
            "device_id": session.initiator_device_id,
            "account_id": session.initiator_account_id,
            "timestamp": session.timestamp,
            "hub_id": session.hub_id
        }
    
    def validate_session_token(self, token: str, hub_id: str) -> bool:
        """Validate a session token for a hub."""
        for session in self.active_sessions.values():
            if session.session_token == token and session.hub_id == hub_id:
                return True
        return False
    
    def complete_session(self, session_id: str):
        """Mark a session as completed."""
        if session_id in self.active_sessions:
            self.active_sessions[session_id].status = "completed"
    
    def cancel_session(self, session_id: str):
        """Cancel a session."""
        if session_id in self.active_sessions:
            self.active_sessions[session_id].status = "cancelled"
    
    # ========================================================================
    # SAMPLE HUBS (Curated List)
    # ========================================================================
    
    def load_sample_hubs(self, city: str = "default"):
        """Load sample curated hubs for a city."""
        sample_hubs = {
            "default": [
                {
                    "hub_id": "hub_park_001",
                    "name": "Central Park - Main Plaza",
                    "address": "Central Park, Main Entrance",
                    "location": {"latitude": 40.7829, "longitude": -73.9654},
                    "hub_type": "park",
                    "status": "active",
                    "safety_tags": ["public", "well_lit", "camera_presence"],
                    "recommended_hours": [
                        {"day": "monday", "open_time": "06:00", "close_time": "22:00"},
                        {"day": "saturday", "open_time": "06:00", "close_time": "23:00"},
                    ]
                },
                {
                    "hub_id": "hub_library_001",
                    "name": "Public Library - Main Branch",
                    "address": "456 Library Ave",
                    "location": {"latitude": 40.7536, "longitude": -73.9832},
                    "hub_type": "library",
                    "status": "active",
                    "safety_tags": ["public", "well_lit", "staffed", "camera_presence"],
                    "recommended_hours": [
                        {"day": "monday", "open_time": "09:00", "close_time": "20:00"},
                        {"day": "sunday", "open_time": "12:00", "close_time": "17:00"},
                    ]
                },
                {
                    "hub_id": "hub_plaza_001",
                    "name": "Town Square Plaza",
                    "address": "Town Square, Center",
                    "location": {"latitude": 40.7580, "longitude": -73.9855},
                    "hub_type": "plaza",
                    "status": "active",
                    "safety_tags": ["public", "well_lit", "camera_presence", "emergency_access"],
                },
                {
                    "hub_id": "hub_cafe_001",
                    "name": "Community Coffee Corner",
                    "address": "789 Cafe Street",
                    "location": {"latitude": 40.7614, "longitude": -73.9776},
                    "hub_type": "cafe",
                    "status": "active",
                    "safety_tags": ["public", "well_lit", "staffed"],
                    "recommended_hours": [
                        {"day": "monday", "open_time": "07:00", "close_time": "21:00"},
                    ]
                },
                {
                    "hub_id": "hub_center_001",
                    "name": "Community Center",
                    "address": "321 Community Blvd",
                    "location": {"latitude": 40.7505, "longitude": -73.9934},
                    "hub_type": "community_center",
                    "status": "active",
                    "safety_tags": ["public", "well_lit", "staffed", "camera_presence", "emergency_access"],
                },
            ]
        }
        
        hubs_data = sample_hubs.get(city, sample_hubs["default"])
        
        for hub_data in hubs_data:
            hub = Hub.from_dict(hub_data)
            hub.created_by = "platform"
            self.add_hub(hub)
        
        logger.info(f"[HUB] Loaded {len(hubs_data)} sample hubs")
    
    # ========================================================================
    # PERSISTENCE
    # ========================================================================
    
    def _save_hubs(self):
        """Save hubs to disk."""
        data = {
            "hubs": {k: v.to_dict() for k, v in self.hubs.items()},
            "saved_at": time.time()
        }
        
        path = self.persistence_dir / "hubs_cache.json"
        try:
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"[HUB] Failed to save hubs: {e}")
    
    def _load_hubs(self):
        """Load hubs from disk."""
        path = self.persistence_dir / "hubs_cache.json"
        
        if not path.exists():
            return
        
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            
            for hub_id, hub_data in data.get("hubs", {}).items():
                self.hubs[hub_id] = Hub.from_dict(hub_data)
            
            logger.info(f"[HUB] Loaded {len(self.hubs)} hubs from cache")
        except Exception as e:
            logger.error(f"[HUB] Failed to load hubs: {e}")
    
    # ========================================================================
    # SYNC (Platform Communication)
    # ========================================================================
    
    def sync_with_platform(self, platform_client: Any) -> bool:
        """
        Sync hubs with platform.
        
        Fetches latest hub list and updates cache.
        """
        try:
            # In production: fetch from platform API
            # hubs_data = platform_client.get_hubs()
            # for hub_data in hubs_data:
            #     hub = Hub.from_dict(hub_data)
            #     hub.last_synced = time.time()
            #     self.add_hub(hub)
            
            logger.info("[HUB] Synced with platform")
            return True
        except Exception as e:
            logger.error(f"[HUB] Sync failed: {e}")
            return False
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get sync status for UI."""
        if not self.hubs:
            return {"status": "empty", "last_sync": None, "hub_count": 0}
        
        last_sync = max(h.last_synced for h in self.hubs.values())
        sync_age_hours = (time.time() - last_sync) / 3600
        
        return {
            "status": "fresh" if sync_age_hours < 24 else "stale",
            "last_sync": last_sync,
            "hub_count": len(self.hubs),
            "sync_age_hours": sync_age_hours
        }


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def create_hub_manager(persistence_dir: str = "./offline_ai_data/hubs") -> HubManager:
    """Create a hub manager with sample hubs."""
    manager = HubManager(persistence_dir)
    
    # Load sample hubs if empty
    if not manager.hubs:
        manager.load_sample_hubs()
    
    return manager


def format_distance(meters: float) -> str:
    """Format distance for display."""
    if meters < 1000:
        return f"{int(meters)}m"
    return f"{meters/1000:.1f}km"


def get_hub_recommendation(manager: HubManager, 
                           preferences: Dict[str, Any] = None) -> Optional[Hub]:
    """
    Get a hub recommendation based on preferences.
    
    Preferences:
    - prefer_type: HubType preference
    - min_safety: Minimum safety score
    - max_distance: Maximum distance in meters
    """
    preferences = preferences or {}
    
    nearby = manager.find_nearby_hubs(
        radius_meters=preferences.get("max_distance", 5000),
        min_safety_score=preferences.get("min_safety", 0)
    )
    
    if not nearby:
        return None
    
    # Filter by type preference
    prefer_type = preferences.get("prefer_type")
    if prefer_type:
        filtered = [(h, d) for h, d in nearby if h.hub_type == prefer_type]
        if filtered:
            nearby = filtered
    
    # Return highest rated within reasonable distance
    nearby.sort(key=lambda x: (x[0].rating, -x[1]), reverse=True)
    
    return nearby[0][0] if nearby else None


# Export public API
__all__ = [
    'HubStatus',
    'SafetyTag',
    'HubType',
    'GeoLocation',
    'OperatingHours',
    'Hub',
    'MeetSession',
    'HubManager',
    'create_hub_manager',
    'format_distance',
    'get_hub_recommendation',
]