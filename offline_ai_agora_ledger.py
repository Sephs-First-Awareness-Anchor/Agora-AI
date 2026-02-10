#!/usr/bin/env python3
"""
Offline AI Agora Ledger
=======================
Agora AI Platform - Phase 1

Tracks exchange events and maintains two separate libraries:
- Self Growth Library: Personal learning, classes, individual path
- Agora Exchange Library: Capabilities gained through social exchanges

Features:
- Exchange event logging with partner hashing
- Daily partner lockout enforcement
- Credit/grant tracking
- Library dashboards for UI display
"""

import json
import hashlib
import time
import logging
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMERATIONS
# ============================================================================

class EventType(Enum):
    """Types of events tracked in the ledger."""
    EXCHANGE = "exchange"           # Social capability exchange
    CLASS_COMPLETION = "class"      # Training class completed
    PERSONAL_GROWTH = "growth"      # Self-directed learning
    CREDIT_GRANT = "credit_grant"   # Credits awarded
    CREDIT_SPEND = "credit_spend"   # Credits spent


class ExchangeCategory(Enum):
    """Categories of capability gained through exchange."""
    TEMPLATE = "template"
    HYBRID_INTENT = "hybrid_intent"
    VOICE_STYLE = "voice_style"
    VISION_COMPETENCY = "vision_competency"
    AUDIO_COMPETENCY = "audio_competency"
    LEXICAL_PATTERN = "lexical_pattern"


class LibraryType(Enum):
    """The two libraries in the Agora system."""
    SELF_GROWTH = "self_growth"
    AGORA_EXCHANGE = "agora_exchange"


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class ExchangeEvent:
    """A single exchange event record."""
    event_id: str
    timestamp: float
    event_type: EventType
    
    # For exchanges
    partner_hash: Optional[str] = None  # Hashed partner ID (not raw)
    categories_gained: List[ExchangeCategory] = field(default_factory=list)
    artifacts_count: int = 0
    
    # For credits
    credits_amount: int = 0
    credit_reason: Optional[str] = None
    
    # For classes/growth
    class_id: Optional[str] = None
    growth_description: Optional[str] = None
    
    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type.value,
            "partner_hash": self.partner_hash,
            "categories_gained": [c.value for c in self.categories_gained],
            "artifacts_count": self.artifacts_count,
            "credits_amount": self.credits_amount,
            "credit_reason": self.credit_reason,
            "class_id": self.class_id,
            "growth_description": self.growth_description,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ExchangeEvent':
        return cls(
            event_id=data["event_id"],
            timestamp=data["timestamp"],
            event_type=EventType(data.get("event_type", "exchange")),
            partner_hash=data.get("partner_hash"),
            categories_gained=[ExchangeCategory(c) for c in data.get("categories_gained", [])],
            artifacts_count=data.get("artifacts_count", 0),
            credits_amount=data.get("credits_amount", 0),
            credit_reason=data.get("credit_reason"),
            class_id=data.get("class_id"),
            growth_description=data.get("growth_description"),
            metadata=data.get("metadata", {})
        )


@dataclass
class PartnerLockout:
    """Tracks daily lockout state for a partner."""
    partner_hash: str
    last_exchange_date: str  # YYYY-MM-DD
    exchange_count_today: int
    first_exchange_date: Optional[str] = None
    total_exchanges: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "partner_hash": self.partner_hash,
            "last_exchange_date": self.last_exchange_date,
            "exchange_count_today": self.exchange_count_today,
            "first_exchange_date": self.first_exchange_date,
            "total_exchanges": self.total_exchanges
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PartnerLockout':
        return cls(
            partner_hash=data["partner_hash"],
            last_exchange_date=data["last_exchange_date"],
            exchange_count_today=data.get("exchange_count_today", 0),
            first_exchange_date=data.get("first_exchange_date"),
            total_exchanges=data.get("total_exchanges", 0)
        )


@dataclass
class LibraryEntry:
    """An entry in one of the two libraries."""
    entry_id: str
    library_type: LibraryType
    name: str
    description: str
    category: str
    acquired_at: float
    source: str  # "exchange", "class", "personal", "system"
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "library_type": self.library_type.value,
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "acquired_at": self.acquired_at,
            "source": self.source,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LibraryEntry':
        return cls(
            entry_id=data["entry_id"],
            library_type=LibraryType(data.get("library_type", "self_growth")),
            name=data["name"],
            description=data["description"],
            category=data["category"],
            acquired_at=data["acquired_at"],
            source=data["source"],
            metadata=data.get("metadata", {})
        )


# ============================================================================
# AGORA LEDGER
# ============================================================================

class AgoraLedger:
    """
    Central ledger for Agora platform interactions.
    
    Maintains:
    - Exchange event history
    - Partner lockout state
    - Credit balance
    - Two-library entries (Self Growth & Agora Exchange)
    """
    
    def __init__(self, account_id: str, persistence_dir: str = "./offline_ai_data/agora"):
        self.account_id = account_id
        self.persistence_dir = Path(persistence_dir)
        self.persistence_dir.mkdir(parents=True, exist_ok=True)
        
        # Event history
        self.events: List[ExchangeEvent] = []
        
        # Partner lockouts
        self.partner_lockouts: Dict[str, PartnerLockout] = {}
        
        # Credit balance
        self.credit_balance: int = 0
        self.total_credits_earned: int = 0
        self.total_credits_spent: int = 0
        
        # Libraries
        self.self_growth_library: List[LibraryEntry] = []
        self.agora_exchange_library: List[LibraryEntry] = []
        
        # Load persisted state
        self._load_state()
        
        logger.info(f"[AGORA LEDGER] Initialized for account {account_id}")
    
    # ========================================================================
    # EXCHANGE LOGGING
    # ========================================================================
    
    def log_exchange(self, 
                     partner_id: str,
                     categories_gained: List[ExchangeCategory],
                     artifacts_count: int,
                     credits_earned: int = 0) -> ExchangeEvent:
        """
        Log a capability exchange event.
        
        Args:
            partner_id: Raw partner ID (will be hashed)
            categories_gained: Categories of capability gained
            artifacts_count: Number of artifacts received
            credits_earned: Credits awarded for this exchange
            
        Returns:
            The logged ExchangeEvent
        """
        partner_hash = self._hash_partner(partner_id)
        
        event = ExchangeEvent(
            event_id=f"ex_{int(time.time() * 1000)}",
            timestamp=time.time(),
            event_type=EventType.EXCHANGE,
            partner_hash=partner_hash,
            categories_gained=categories_gained,
            artifacts_count=artifacts_count,
            credits_amount=credits_earned
        )
        
        self.events.append(event)
        
        # Update partner lockout
        self._update_partner_lockout(partner_hash)
        
        # Add credits
        if credits_earned > 0:
            self.credit_balance += credits_earned
            self.total_credits_earned += credits_earned
        
        # Add to Agora Exchange Library
        for category in categories_gained:
            entry = LibraryEntry(
                entry_id=f"agel_{int(time.time() * 1000)}_{category.value}",
                library_type=LibraryType.AGORA_EXCHANGE,
                name=f"{category.value.replace('_', ' ').title()}",
                description=f"Gained through exchange with partner",
                category=category.value,
                acquired_at=event.timestamp,
                source="exchange",
                metadata={"partner_hash": partner_hash, "artifacts_count": artifacts_count}
            )
            self.agora_exchange_library.append(entry)
        
        self._save_state()
        
        logger.info(f"[AGORA] Logged exchange with {partner_hash[:16]}... "
                   f"({artifacts_count} artifacts, {credits_earned} credits)")
        
        return event
    
    def log_class_completion(self,
                             class_id: str,
                             class_name: str,
                             categories_gained: List[ExchangeCategory],
                             credits_cost: int = 0) -> ExchangeEvent:
        """Log completion of a training class."""
        event = ExchangeEvent(
            event_id=f"cls_{int(time.time() * 1000)}",
            timestamp=time.time(),
            event_type=EventType.CLASS_COMPLETION,
            class_id=class_id,
            categories_gained=categories_gained,
            credits_amount=-credits_cost
        )
        
        self.events.append(event)
        
        # Deduct credits
        if credits_cost > 0:
            self.credit_balance -= credits_cost
            self.total_credits_spent += credits_cost
        
        # Add to Self Growth Library
        for category in categories_gained:
            entry = LibraryEntry(
                entry_id=f"sgl_{int(time.time() * 1000)}_{category.value}",
                library_type=LibraryType.SELF_GROWTH,
                name=f"{class_name} - {category.value.replace('_', ' ').title()}",
                description=f"Learned through class: {class_name}",
                category=category.value,
                acquired_at=event.timestamp,
                source="class",
                metadata={"class_id": class_id}
            )
            self.self_growth_library.append(entry)
        
        self._save_state()
        
        logger.info(f"[AGORA] Logged class completion: {class_name}")
        
        return event
    
    def log_personal_growth(self,
                           description: str,
                           category: str,
                           metadata: Dict[str, Any] = None) -> ExchangeEvent:
        """Log personal growth/learning event."""
        event = ExchangeEvent(
            event_id=f"grw_{int(time.time() * 1000)}",
            timestamp=time.time(),
            event_type=EventType.PERSONAL_GROWTH,
            growth_description=description
        )
        
        self.events.append(event)
        
        # Add to Self Growth Library
        entry = LibraryEntry(
            entry_id=f"sgl_{int(time.time() * 1000)}_personal",
            library_type=LibraryType.SELF_GROWTH,
            name=description[:50],
            description=description,
            category=category,
            acquired_at=event.timestamp,
            source="personal",
            metadata=metadata or {}
        )
        self.self_growth_library.append(entry)
        
        self._save_state()
        
        logger.info(f"[AGORA] Logged personal growth: {description[:50]}...")
        
        return event
    
    # ========================================================================
    # PARTNER LOCKOUT
    # ========================================================================
    
    def _hash_partner(self, partner_id: str) -> str:
        """Hash a partner ID for privacy."""
        return hashlib.sha256(f"{partner_id}:{self.account_id}".encode()).hexdigest()
    
    def _update_partner_lockout(self, partner_hash: str):
        """Update lockout state for a partner."""
        today = datetime.now().strftime("%Y-%m-%d")
        
        if partner_hash not in self.partner_lockouts:
            self.partner_lockouts[partner_hash] = PartnerLockout(
                partner_hash=partner_hash,
                last_exchange_date=today,
                exchange_count_today=1,
                first_exchange_date=today,
                total_exchanges=1
            )
        else:
            lockout = self.partner_lockouts[partner_hash]
            
            if lockout.last_exchange_date == today:
                # Same day - increment count
                lockout.exchange_count_today += 1
            else:
                # New day - reset count
                lockout.exchange_count_today = 1
                lockout.last_exchange_date = today
            
            lockout.total_exchanges += 1
    
    def can_exchange_with(self, partner_id: str) -> Tuple[bool, str]:
        """
        Check if exchange is allowed with a partner.
        
        Returns:
            (allowed, reason)
        """
        partner_hash = self._hash_partner(partner_id)
        today = datetime.now().strftime("%Y-%m-%d")
        
        if partner_hash not in self.partner_lockouts:
            return True, "First exchange with this partner"
        
        lockout = self.partner_lockouts[partner_hash]
        
        if lockout.last_exchange_date == today and lockout.exchange_count_today >= 1:
            return False, "Daily exchange limit reached (1 per partner per day)"
        
        return True, "Exchange allowed"
    
    def get_partner_stats(self, partner_id: str) -> Optional[Dict[str, Any]]:
        """Get exchange stats for a partner."""
        partner_hash = self._hash_partner(partner_id)
        
        if partner_hash not in self.partner_lockouts:
            return None
        
        lockout = self.partner_lockouts[partner_hash]
        
        # Calculate novelty score
        first_date = datetime.strptime(lockout.first_exchange_date, "%Y-%m-%d")
        days_since_first = (datetime.now() - first_date).days
        
        # Novelty: first-time > repeat over days > repeat same day
        if lockout.total_exchanges == 1:
            novelty_score = 3.0  # First exchange
        elif days_since_first > 0:
            novelty_score = 2.0  # Repeat over multiple days
        else:
            novelty_score = 1.0  # Same day repeat
        
        return {
            "partner_hash": partner_hash[:16] + "...",
            "first_exchange": lockout.first_exchange_date,
            "last_exchange": lockout.last_exchange_date,
            "total_exchanges": lockout.total_exchanges,
            "exchanges_today": lockout.exchange_count_today,
            "novelty_score": novelty_score
        }
    
    # ========================================================================
    # CREDIT MANAGEMENT
    # ========================================================================
    
    def get_credit_balance(self) -> int:
        """Get current credit balance."""
        return self.credit_balance
    
    def spend_credits(self, amount: int, reason: str) -> bool:
        """Spend credits. Returns True if successful."""
        if amount > self.credit_balance:
            logger.warning(f"[AGORA] Insufficient credits: {amount} > {self.credit_balance}")
            return False
        
        self.credit_balance -= amount
        self.total_credits_spent += amount
        
        event = ExchangeEvent(
            event_id=f"spend_{int(time.time() * 1000)}",
            timestamp=time.time(),
            event_type=EventType.CREDIT_SPEND,
            credits_amount=-amount,
            credit_reason=reason
        )
        self.events.append(event)
        
        self._save_state()
        
        logger.info(f"[AGORA] Spent {amount} credits: {reason}")
        return True
    
    def grant_credits(self, amount: int, reason: str) -> int:
        """Grant credits (e.g., from exchange)."""
        self.credit_balance += amount
        self.total_credits_earned += amount
        
        event = ExchangeEvent(
            event_id=f"grant_{int(time.time() * 1000)}",
            timestamp=time.time(),
            event_type=EventType.CREDIT_GRANT,
            credits_amount=amount,
            credit_reason=reason
        )
        self.events.append(event)
        
        self._save_state()
        
        logger.info(f"[AGORA] Granted {amount} credits: {reason}")
        return self.credit_balance
    
    def calculate_exchange_credits(self, partner_id: str, 
                                   categories_count: int,
                                   linger_seconds: int) -> int:
        """
        Calculate credits for an exchange.
        
        Scales with:
        - Novelty (first-time > repeat over days > same day)
        - Linger time (longer = more)
        - Categories gained
        """
        partner_stats = self.get_partner_stats(partner_id)
        
        # Base credits
        base_credits = 10
        
        # Novelty multiplier
        novelty_mult = 1.0
        if partner_stats:
            novelty_mult = partner_stats["novelty_score"] / 2.0  # 0.5 to 1.5
        
        # Linger bonus (max 30 seconds)
        linger_bonus = min(linger_seconds, 30) / 10  # 0 to 3
        
        # Categories bonus
        categories_bonus = categories_count * 2
        
        total = int((base_credits + linger_bonus + categories_bonus) * novelty_mult)
        
        return max(1, total)  # Minimum 1 credit
    
    # ========================================================================
    # LIBRARY ACCESS
    # ========================================================================
    
    def get_self_growth_library(self) -> List[LibraryEntry]:
        """Get Self Growth Library entries."""
        return sorted(self.self_growth_library, 
                     key=lambda e: e.acquired_at, 
                     reverse=True)
    
    def get_agora_exchange_library(self) -> List[LibraryEntry]:
        """Get Agora Exchange Library entries."""
        return sorted(self.agora_exchange_library,
                     key=lambda e: e.acquired_at,
                     reverse=True)
    
    def get_library_summary(self) -> Dict[str, Any]:
        """Get summary of both libraries."""
        return {
            "self_growth": {
                "total_entries": len(self.self_growth_library),
                "categories": list(set(e.category for e in self.self_growth_library)),
                "recent_entries": [e.to_dict() for e in self.get_self_growth_library()[:5]]
            },
            "agora_exchange": {
                "total_entries": len(self.agora_exchange_library),
                "categories": list(set(e.category for e in self.agora_exchange_library)),
                "recent_entries": [e.to_dict() for e in self.get_agora_exchange_library()[:5]]
            },
            "credits": {
                "balance": self.credit_balance,
                "total_earned": self.total_credits_earned,
                "total_spent": self.total_credits_spent
            }
        }
    
    # ========================================================================
    # STATISTICS
    # ========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive ledger statistics."""
        exchange_events = [e for e in self.events if e.event_type == EventType.EXCHANGE]
        class_events = [e for e in self.events if e.event_type == EventType.CLASS_COMPLETION]
        growth_events = [e for e in self.events if e.event_type == EventType.PERSONAL_GROWTH]
        
        unique_partners = set(e.partner_hash for e in exchange_events if e.partner_hash)
        
        return {
            "account_id": self.account_id,
            "total_events": len(self.events),
            "exchanges": {
                "total": len(exchange_events),
                "unique_partners": len(unique_partners),
                "total_artifacts": sum(e.artifacts_count for e in exchange_events),
                "total_categories": sum(len(e.categories_gained) for e in exchange_events)
            },
            "classes": {
                "total_completed": len(class_events),
                "total_categories": sum(len(e.categories_gained) for e in class_events)
            },
            "personal_growth": {
                "total_events": len(growth_events)
            },
            "credits": {
                "balance": self.credit_balance,
                "total_earned": self.total_credits_earned,
                "total_spent": self.total_credits_spent
            },
            "libraries": {
                "self_growth_entries": len(self.self_growth_library),
                "agora_exchange_entries": len(self.agora_exchange_library)
            }
        }
    
    # ========================================================================
    # PERSISTENCE
    # ========================================================================
    
    def _save_state(self):
        """Save ledger state to disk."""
        state = {
            "account_id": self.account_id,
            "events": [e.to_dict() for e in self.events[-1000:]],  # Keep last 1000
            "partner_lockouts": {k: v.to_dict() for k, v in self.partner_lockouts.items()},
            "credit_balance": self.credit_balance,
            "total_credits_earned": self.total_credits_earned,
            "total_credits_spent": self.total_credits_spent,
            "self_growth_library": [e.to_dict() for e in self.self_growth_library],
            "agora_exchange_library": [e.to_dict() for e in self.agora_exchange_library],
            "saved_at": time.time()
        }
        
        path = self.persistence_dir / f"{self.account_id}_ledger.json"
        try:
            with open(path, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"[AGORA] Failed to save ledger: {e}")
    
    def _load_state(self):
        """Load ledger state from disk."""
        path = self.persistence_dir / f"{self.account_id}_ledger.json"
        
        if not path.exists():
            logger.info(f"[AGORA] No existing ledger for {self.account_id}")
            return
        
        try:
            with open(path, 'r') as f:
                state = json.load(f)
            
            self.events = [ExchangeEvent.from_dict(e) for e in state.get("events", [])]
            self.partner_lockouts = {
                k: PartnerLockout.from_dict(v) 
                for k, v in state.get("partner_lockouts", {}).items()
            }
            self.credit_balance = state.get("credit_balance", 0)
            self.total_credits_earned = state.get("total_credits_earned", 0)
            self.total_credits_spent = state.get("total_credits_spent", 0)
            self.self_growth_library = [
                LibraryEntry.from_dict(e) 
                for e in state.get("self_growth_library", [])
            ]
            self.agora_exchange_library = [
                LibraryEntry.from_dict(e) 
                for e in state.get("agora_exchange_library", [])
            ]
            
            logger.info(f"[AGORA] Loaded ledger: {len(self.events)} events, "
                       f"{self.credit_balance} credits")
        except Exception as e:
            logger.error(f"[AGORA] Failed to load ledger: {e}")


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def create_ledger_for_ai(ai_instance: Any, 
                         persistence_dir: str = "./offline_ai_data/agora") -> AgoraLedger:
    """Create a ledger for an AI instance."""
    account_id = getattr(ai_instance, 'account_id', 'unknown')
    return AgoraLedger(account_id, persistence_dir)


def format_credit_amount(amount: int) -> str:
    """Format credit amount for display."""
    if amount >= 1000:
        return f"{amount // 1000}k"
    return str(amount)


# Export public API
__all__ = [
    'EventType',
    'ExchangeCategory',
    'LibraryType',
    'ExchangeEvent',
    'PartnerLockout',
    'LibraryEntry',
    'AgoraLedger',
    'create_ledger_for_ai',
    'format_credit_amount',
]