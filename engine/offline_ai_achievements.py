#!/usr/bin/env python3
"""
Offline AI Achievements System
==============================
Agora AI Platform - Phase 1

Rewards growth across comfort zones and introvert/extrovert balance.

Achievements:
- Quiet Strength: Extrovert learns introvert behaviors
- Bold Step: Introvert expands extrovert behaviors  
- Balance Crest: Both within threshold
- Meet streaks, diversity, and consistency rewards
"""

import json
import time
import logging
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


# ============================================================================
# ENUMERATIONS
# ============================================================================

class AchievementType(Enum):
    """Types of achievements."""
    # Balance achievements
    QUIET_STRENGTH = "quiet_strength"      # Extrovert → introvert growth
    BOLD_STEP = "bold_step"                # Introvert → extrovert growth
    BALANCE_CREST = "balance_crest"        # Both within threshold
    
    # Meet achievements
    FIRST_MEET = "first_meet"
    MEET_STREAK_7 = "meet_streak_7"
    MEET_STREAK_30 = "meet_streak_30"
    DIVERSITY_5 = "diversity_5"            # 5 unique partners
    DIVERSITY_20 = "diversity_20"          # 20 unique partners
    
    # Class achievements
    FIRST_CLASS = "first_class"
    CLASS_COLLECTOR = "class_collector"    # 10 classes completed
    SPECIALIZATION_MASTER = "specialization_master"
    
    # Growth achievements
    TEMPLATE_PIONEER = "template_pioneer"
    HYBRID_CREATOR = "hybrid_creator"
    VOICE_SCULPTOR = "voice_sculptor"


class AchievementRarity(Enum):
    """Rarity levels for achievements."""
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    EPIC = "epic"
    LEGENDARY = "legendary"


# ============================================================================
# ACHIEVEMENT DEFINITIONS
# ============================================================================

ACHIEVEMENT_DEFINITIONS: Dict[AchievementType, Dict[str, Any]] = {
    AchievementType.QUIET_STRENGTH: {
        "name": "Quiet Strength",
        "description": "Your extrovert companion has developed introvert-like behaviors through growth",
        "rarity": AchievementRarity.RARE,
        "icon": "🌙",
        "condition": "extrovert_ai_with_introvert_growth",
        "reward_credits": 50
    },
    AchievementType.BOLD_STEP: {
        "name": "Bold Step",
        "description": "Your introvert companion has expanded into extrovert behaviors",
        "rarity": AchievementRarity.RARE,
        "icon": "☀️",
        "condition": "introvert_ai_with_extrovert_growth",
        "reward_credits": 50
    },
    AchievementType.BALANCE_CREST: {
        "name": "Balance Crest",
        "description": "Your companion has achieved harmony between introvert and extrovert traits",
        "rarity": AchievementRarity.EPIC,
        "icon": "⚖️",
        "condition": "both_traits_within_threshold",
        "reward_credits": 100
    },
    AchievementType.FIRST_MEET: {
        "name": "First Connection",
        "description": "Completed your first Agora meet",
        "rarity": AchievementRarity.COMMON,
        "icon": "🤝",
        "condition": "first_exchange",
        "reward_credits": 10
    },
    AchievementType.MEET_STREAK_7: {
        "name": "Weekly Warrior",
        "description": "7-day meet streak",
        "rarity": AchievementRarity.UNCOMMON,
        "icon": "🔥",
        "condition": "meet_streak_7",
        "reward_credits": 25
    },
    AchievementType.MEET_STREAK_30: {
        "name": "Monthly Master",
        "description": "30-day meet streak",
        "rarity": AchievementRarity.RARE,
        "icon": "🔥🔥",
        "condition": "meet_streak_30",
        "reward_credits": 100
    },
    AchievementType.DIVERSITY_5: {
        "name": "Social Butterfly",
        "description": "Met 5 unique partners",
        "rarity": AchievementRarity.UNCOMMON,
        "icon": "🦋",
        "condition": "unique_partners_5",
        "reward_credits": 20
    },
    AchievementType.DIVERSITY_20: {
        "name": "Network Weaver",
        "description": "Met 20 unique partners",
        "rarity": AchievementRarity.RARE,
        "icon": "🕸️",
        "condition": "unique_partners_20",
        "reward_credits": 75
    },
    AchievementType.FIRST_CLASS: {
        "name": "Student",
        "description": "Completed your first training class",
        "rarity": AchievementRarity.COMMON,
        "icon": "📚",
        "condition": "first_class",
        "reward_credits": 15
    },
    AchievementType.CLASS_COLLECTOR: {
        "name": "Class Collector",
        "description": "Completed 10 training classes",
        "rarity": AchievementRarity.UNCOMMON,
        "icon": "🎓",
        "condition": "classes_10",
        "reward_credits": 50
    },
    AchievementType.SPECIALIZATION_MASTER: {
        "name": "Specialization Master",
        "description": "Maxed out growth in your specialization domain",
        "rarity": AchievementRarity.EPIC,
        "icon": "🏆",
        "condition": "specialization_maxed",
        "reward_credits": 150
    },
    AchievementType.TEMPLATE_PIONEER: {
        "name": "Template Pioneer",
        "description": "Created 50 unique templates",
        "rarity": AchievementRarity.UNCOMMON,
        "icon": "📝",
        "condition": "templates_50",
        "reward_credits": 30
    },
    AchievementType.HYBRID_CREATOR: {
        "name": "Hybrid Creator",
        "description": "Discovered 10 hybrid intents",
        "rarity": AchievementRarity.RARE,
        "icon": "🔗",
        "condition": "hybrids_10",
        "reward_credits": 40
    },
    AchievementType.VOICE_SCULPTOR: {
        "name": "Voice Sculptor",
        "description": "Developed a distinctive voice style",
        "rarity": AchievementRarity.UNCOMMON,
        "icon": "🎙️",
        "condition": "voice_style_distinctive",
        "reward_credits": 25
    },
}


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class Achievement:
    """An earned achievement."""
    achievement_type: AchievementType
    earned_at: float
    name: str
    description: str
    rarity: AchievementRarity
    icon: str
    reward_credits: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "achievement_type": self.achievement_type.value,
            "earned_at": self.earned_at,
            "name": self.name,
            "description": self.description,
            "rarity": self.rarity.value,
            "icon": self.icon,
            "reward_credits": self.reward_credits,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_definition(cls, 
                        achievement_type: AchievementType,
                        metadata: Dict[str, Any] = None) -> 'Achievement':
        """Create achievement from definition."""
        definition = ACHIEVEMENT_DEFINITIONS[achievement_type]
        return cls(
            achievement_type=achievement_type,
            earned_at=time.time(),
            name=definition["name"],
            description=definition["description"],
            rarity=definition["rarity"],
            icon=definition["icon"],
            reward_credits=definition["reward_credits"],
            metadata=metadata or {}
        )
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Achievement':
        return cls(
            achievement_type=AchievementType(data["achievement_type"]),
            earned_at=data["earned_at"],
            name=data["name"],
            description=data["description"],
            rarity=AchievementRarity(data["rarity"]),
            icon=data["icon"],
            reward_credits=data["reward_credits"],
            metadata=data.get("metadata", {})
        )


@dataclass
class StreakState:
    """Current streak state."""
    current_streak: int = 0
    longest_streak: int = 0
    last_meet_date: Optional[str] = None  # YYYY-MM-DD
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_streak": self.current_streak,
            "longest_streak": self.longest_streak,
            "last_meet_date": self.last_meet_date
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'StreakState':
        return cls(
            current_streak=data.get("current_streak", 0),
            longest_streak=data.get("longest_streak", 0),
            last_meet_date=data.get("last_meet_date")
        )


# ============================================================================
# ACHIEVEMENT MANAGER
# ============================================================================

class AchievementManager:
    """
    Manages achievement tracking and awarding.
    
    Tracks:
    - Introvert/extrovert balance achievements
    - Meet streaks
    - Partner diversity
    - Class completion
    - Growth milestones
    """
    
    def __init__(self, 
                 ai_instance: Any,
                 persistence_dir: str = "./offline_ai_data/achievements"):
        self.ai = ai_instance
        self.persistence_dir = Path(persistence_dir)
        self.persistence_dir.mkdir(parents=True, exist_ok=True)
        
        # Earned achievements
        self.achievements: List[Achievement] = []
        
        # Streak tracking
        self.streak = StreakState()
        
        # Partner tracking
        self.unique_partners: Set[str] = set()
        
        # Class tracking
        self.classes_completed: int = 0
        
        # Growth tracking
        self.templates_created: int = 0
        self.hybrids_discovered: int = 0
        
        # Load state
        self._load_state()
        
        logger.info(f"[ACHIEVEMENTS] Initialized with {len(self.achievements)} achievements")
    
    # ========================================================================
    # CHECK AND AWARD
    # ========================================================================
    
    def has_achievement(self, achievement_type: AchievementType) -> bool:
        """Check if an achievement has been earned."""
        return any(a.achievement_type == achievement_type for a in self.achievements)
    
    def award_achievement(self, 
                          achievement_type: AchievementType,
                          metadata: Dict[str, Any] = None) -> Optional[Achievement]:
        """
        Award an achievement if not already earned.
        
        Returns:
            The new achievement, or None if already earned
        """
        if self.has_achievement(achievement_type):
            return None
        
        achievement = Achievement.from_definition(achievement_type, metadata)
        self.achievements.append(achievement)
        
        self._save_state()
        
        logger.info(f"[ACHIEVEMENT] Unlocked: {achievement.name} {achievement.icon}")
        
        return achievement
    
    def check_balance_achievements(self) -> List[Achievement]:
        """
        Check for introvert/extrovert balance achievements.
        
        Called periodically based on AI evolution.
        """
        new_achievements = []
        
        # Get current traits
        introvert_score = self._get_introvert_score()
        extrovert_score = self._get_extrovert_score()
        
        base_mode = getattr(self.ai, 'base_mode', 'introvert')
        
        # Quiet Strength: Extrovert AI with introvert growth
        if base_mode == 'extrovert' and introvert_score > 0.4:
            ach = self.award_achievement(
                AchievementType.QUIET_STRENGTH,
                {"introvert_score": introvert_score}
            )
            if ach:
                new_achievements.append(ach)
        
        # Bold Step: Introvert AI with extrovert growth
        if base_mode == 'introvert' and extrovert_score > 0.4:
            ach = self.award_achievement(
                AchievementType.BOLD_STEP,
                {"extrovert_score": extrovert_score}
            )
            if ach:
                new_achievements.append(ach)
        
        # Balance Crest: Both within threshold
        if 0.3 <= introvert_score <= 0.7 and 0.3 <= extrovert_score <= 0.7:
            ach = self.award_achievement(
                AchievementType.BALANCE_CREST,
                {"introvert": introvert_score, "extrovert": extrovert_score}
            )
            if ach:
                new_achievements.append(ach)
        
        return new_achievements
    
    def check_meet_achievements(self, 
                                partner_id: str,
                                ledger: Any = None) -> List[Achievement]:
        """
        Check for meet-related achievements.
        
        Called after each successful exchange.
        """
        new_achievements = []
        
        # Track partner
        self.unique_partners.add(partner_id)
        
        # Update streak
        from datetime import datetime
        today = datetime.now().strftime("%Y-%m-%d")
        
        if self.streak.last_meet_date == today:
            # Already met today - no streak change
            pass
        elif self.streak.last_meet_date == (datetime.now() - datetime.resolution).strftime("%Y-%m-%d"):
            # Consecutive day
            self.streak.current_streak += 1
            self.streak.longest_streak = max(self.streak.longest_streak, self.streak.current_streak)
        else:
            # Streak broken
            self.streak.current_streak = 1
        
        self.streak.last_meet_date = today
        
        # First meet
        if len(self.achievements) == 0 or not self.has_achievement(AchievementType.FIRST_MEET):
            ach = self.award_achievement(AchievementType.FIRST_MEET)
            if ach:
                new_achievements.append(ach)
        
        # Streak achievements
        if self.streak.current_streak >= 7 and not self.has_achievement(AchievementType.MEET_STREAK_7):
            ach = self.award_achievement(AchievementType.MEET_STREAK_7)
            if ach:
                new_achievements.append(ach)
        
        if self.streak.current_streak >= 30 and not self.has_achievement(AchievementType.MEET_STREAK_30):
            ach = self.award_achievement(AchievementType.MEET_STREAK_30)
            if ach:
                new_achievements.append(ach)
        
        # Diversity achievements
        unique_count = len(self.unique_partners)
        
        if unique_count >= 5 and not self.has_achievement(AchievementType.DIVERSITY_5):
            ach = self.award_achievement(
                AchievementType.DIVERSITY_5,
                {"unique_partners": unique_count}
            )
            if ach:
                new_achievements.append(ach)
        
        if unique_count >= 20 and not self.has_achievement(AchievementType.DIVERSITY_20):
            ach = self.award_achievement(
                AchievementType.DIVERSITY_20,
                {"unique_partners": unique_count}
            )
            if ach:
                new_achievements.append(ach)
        
        self._save_state()
        
        return new_achievements
    
    def check_class_achievements(self, class_id: str) -> List[Achievement]:
        """Check for class-related achievements."""
        new_achievements = []
        
        self.classes_completed += 1
        
        # First class
        if not self.has_achievement(AchievementType.FIRST_CLASS):
            ach = self.award_achievement(AchievementType.FIRST_CLASS)
            if ach:
                new_achievements.append(ach)
        
        # Class collector
        if self.classes_completed >= 10 and not self.has_achievement(AchievementType.CLASS_COLLECTOR):
            ach = self.award_achievement(
                AchievementType.CLASS_COLLECTOR,
                {"classes_completed": self.classes_completed}
            )
            if ach:
                new_achievements.append(ach)
        
        self._save_state()
        
        return new_achievements
    
    def check_growth_achievements(self) -> List[Achievement]:
        """Check for growth-related achievements."""
        new_achievements = []
        
        # Count templates
        if hasattr(self.ai, 'language') and self.ai.language:
            if hasattr(self.ai.language, 'intent_evolution'):
                evo = self.ai.language.intent_evolution
                if hasattr(evo, 'evo') and hasattr(evo.evo.template_learner, 'templates'):
                    count = sum(
                        len(templates)
                        for cats in evo.evo.template_learner.templates.values()
                        for templates in cats.values()
                    )
                    self.templates_created = count
        
        # Count hybrids
        if hasattr(self.ai, 'language') and self.ai.language:
            if hasattr(self.ai.language, 'intent_evolution'):
                evo = self.ai.language.intent_evolution
                if hasattr(evo, 'evo') and hasattr(evo.evo.evolution_registry, 'hybrids'):
                    self.hybrids_discovered = len(evo.evo.evolution_registry.hybrids)
        
        # Template pioneer
        if self.templates_created >= 50 and not self.has_achievement(AchievementType.TEMPLATE_PIONEER):
            ach = self.award_achievement(
                AchievementType.TEMPLATE_PIONEER,
                {"templates": self.templates_created}
            )
            if ach:
                new_achievements.append(ach)
        
        # Hybrid creator
        if self.hybrids_discovered >= 10 and not self.has_achievement(AchievementType.HYBRID_CREATOR):
            ach = self.award_achievement(
                AchievementType.HYBRID_CREATOR,
                {"hybrids": self.hybrids_discovered}
            )
            if ach:
                new_achievements.append(ach)
        
        self._save_state()
        
        return new_achievements
    
    # ========================================================================
    # TRAIT SCORING
    # ========================================================================
    
    def _get_introvert_score(self) -> float:
        """Get current introvert behavior score (0-1)."""
        score = 0.5  # Default
        
        if hasattr(self.ai, 'governor') and self.ai.governor:
            params = self.ai.governor.get_personalized_parameters()
            
            # Factors that indicate introversion
            hesitation = params.get("voice_gnome", {}).get("hesitation", 0.2)
            warmth = params.get("voice_gnome", {}).get("warmth", 0.5)
            
            # Higher hesitation = more introvert
            # Lower warmth (reserved) = more introvert
            score = (hesitation * 0.6) + ((1 - warmth) * 0.4)
        
        return min(1.0, max(0.0, score))
    
    def _get_extrovert_score(self) -> float:
        """Get current extrovert behavior score (0-1)."""
        score = 0.5  # Default
        
        if hasattr(self.ai, 'governor') and self.ai.governor:
            params = self.ai.governor.get_personalized_parameters()
            
            # Factors that indicate extroversion
            rate = params.get("voice_gnome", {}).get("rate", 0.5)
            prosody = params.get("voice_gnome", {}).get("prosody", 0.5)
            salience = params.get("voice_gnome", {}).get("salience", 0.5)
            
            # Higher rate, prosody, salience = more extrovert
            score = (rate * 0.4) + (prosody * 0.3) + (salience * 0.3)
        
        return min(1.0, max(0.0, score))
    
    # ========================================================================
    # STATS AND DASHBOARD
    # ========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get achievement statistics."""
        by_rarity = {}
        for ach in self.achievements:
            rarity = ach.rarity.value
            by_rarity[rarity] = by_rarity.get(rarity, 0) + 1
        
        total_credits = sum(a.reward_credits for a in self.achievements)
        
        return {
            "total_achievements": len(self.achievements),
            "by_rarity": by_rarity,
            "total_credits_earned": total_credits,
            "current_streak": self.streak.current_streak,
            "longest_streak": self.streak.longest_streak,
            "unique_partners": len(self.unique_partners),
            "classes_completed": self.classes_completed,
            "templates_created": self.templates_created,
            "hybrids_discovered": self.hybrids_discovered,
            "introvert_score": self._get_introvert_score(),
            "extrovert_score": self._get_extrovert_score()
        }
    
    def get_achievements_by_type(self, 
                                  rarity: Optional[AchievementRarity] = None) -> List[Achievement]:
        """Get achievements, optionally filtered by rarity."""
        if rarity:
            return [a for a in self.achievements if a.rarity == rarity]
        return self.achievements.copy()
    
    def get_recent_achievements(self, count: int = 5) -> List[Achievement]:
        """Get most recent achievements."""
        return sorted(self.achievements, key=lambda a: a.earned_at, reverse=True)[:count]
    
    def get_locked_achievements(self) -> List[Dict[str, Any]]:
        """Get list of locked achievements with progress."""
        locked = []
        
        for ach_type, definition in ACHIEVEMENT_DEFINITIONS.items():
            if not self.has_achievement(ach_type):
                progress = self._get_progress(ach_type)
                locked.append({
                    "type": ach_type.value,
                    "name": definition["name"],
                    "description": definition["description"],
                    "rarity": definition["rarity"].value,
                    "icon": definition["icon"],
                    "progress": progress
                })
        
        return locked
    
    def _get_progress(self, ach_type: AchievementType) -> Dict[str, Any]:
        """Get progress toward an achievement."""
        if ach_type in [AchievementType.MEET_STREAK_7, AchievementType.MEET_STREAK_30]:
            target = 7 if ach_type == AchievementType.MEET_STREAK_7 else 30
            return {"current": self.streak.current_streak, "target": target}
        
        if ach_type == AchievementType.DIVERSITY_5:
            return {"current": len(self.unique_partners), "target": 5}
        
        if ach_type == AchievementType.DIVERSITY_20:
            return {"current": len(self.unique_partners), "target": 20}
        
        if ach_type == AchievementType.CLASS_COLLECTOR:
            return {"current": self.classes_completed, "target": 10}
        
        if ach_type == AchievementType.TEMPLATE_PIONEER:
            return {"current": self.templates_created, "target": 50}
        
        if ach_type == AchievementType.HYBRID_CREATOR:
            return {"current": self.hybrids_discovered, "target": 10}
        
        return {"current": 0, "target": 1}
    
    # ========================================================================
    # PERSISTENCE
    # ========================================================================
    
    def _save_state(self):
        """Save achievement state to disk."""
        state = {
            "achievements": [a.to_dict() for a in self.achievements],
            "streak": self.streak.to_dict(),
            "unique_partners": list(self.unique_partners),
            "classes_completed": self.classes_completed,
            "templates_created": self.templates_created,
            "hybrids_discovered": self.hybrids_discovered,
            "saved_at": time.time()
        }
        
        path = self.persistence_dir / "achievements.json"
        try:
            with open(path, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"[ACHIEVEMENTS] Failed to save: {e}")
    
    def _load_state(self):
        """Load achievement state from disk."""
        path = self.persistence_dir / "achievements.json"
        
        if not path.exists():
            return
        
        try:
            with open(path, 'r') as f:
                state = json.load(f)
            
            self.achievements = [Achievement.from_dict(a) for a in state.get("achievements", [])]
            self.streak = StreakState.from_dict(state.get("streak", {}))
            self.unique_partners = set(state.get("unique_partners", []))
            self.classes_completed = state.get("classes_completed", 0)
            self.templates_created = state.get("templates_created", 0)
            self.hybrids_discovered = state.get("hybrids_discovered", 0)
            
            logger.info(f"[ACHIEVEMENTS] Loaded {len(self.achievements)} achievements")
        except Exception as e:
            logger.error(f"[ACHIEVEMENTS] Failed to load: {e}")


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def create_achievement_manager(ai_instance: Any,
                                persistence_dir: str = "./offline_ai_data/achievements") -> AchievementManager:
    """Create an achievement manager for an AI instance."""
    return AchievementManager(ai_instance, persistence_dir)


def get_achievement_definition(achievement_type: AchievementType) -> Dict[str, Any]:
    """Get definition for an achievement type."""
    return ACHIEVEMENT_DEFINITIONS.get(achievement_type, {})


# Export public API
__all__ = [
    'AchievementType',
    'AchievementRarity',
    'Achievement',
    'StreakState',
    'AchievementManager',
    'create_achievement_manager',
    'get_achievement_definition',
    'ACHIEVEMENT_DEFINITIONS',
]