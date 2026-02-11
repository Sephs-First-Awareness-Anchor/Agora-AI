#!/usr/bin/env python3
"""
Offline AI Library System
=========================
Unified evolution + modular compression for all modalities.

Key features:
- All modalities use same template/hybrid evolution as language
- Compressed modules (≤25MB each) for GitHub compatibility
- AI-navigable: query, decompress, edit, recompress
- Automatic chunking for large datasets
"""

import os
import json
import gzip
import logging
import hashlib
import time
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set, Union
from dataclasses import dataclass, field, asdict
from collections import defaultdict
from enum import Enum
import io

logger = logging.getLogger(__name__)

# ============================================================================
# CONSTANTS
# ============================================================================

MAX_MODULE_SIZE_MB = 25
MAX_MODULE_SIZE_BYTES = MAX_MODULE_SIZE_MB * 1024 * 1024
COMPRESSION_LEVEL = 9  # Maximum compression

# Modality types for evolution
class Modality(Enum):
    LANGUAGE = "language"
    EXPRESSION = "expression"
    AUDIO = "audio"
    VISION = "vision"
    MEMORY = "memory"
    METACOGNITION = "metacognition"

# ============================================================================
# CORE EVOLUTION CLASSES (Unified across all modalities)
# ============================================================================

@dataclass
class EvolutionTemplate:
    """Template that can evolve across any modality"""
    id: str
    modality: str  # 'language', 'expression', 'audio', 'vision'
    category: str  # e.g., 'greeting', 'animation', 'phoneme', 'percept'
    pattern: str   # The template pattern with {slots}
    slots: Dict[str, str] = field(default_factory=dict)  # slot_name -> type
    
    # Evolution metadata
    usage_count: int = 0
    success_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    
    # Quality metrics
    coherence: float = 0.5  # 0-1, how well-formed
    stability: float = 0.0  # Increases with reinforcement
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "modality": self.modality,
            "category": self.category,
            "pattern": self.pattern,
            "slots": self.slots,
            "usage_count": self.usage_count,
            "success_count": self.success_count,
            "created_at": self.created_at,
            "last_used": self.last_used,
            "coherence": self.coherence,
            "stability": self.stability
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EvolutionTemplate':
        t = cls(
            id=data["id"],
            modality=data["modality"],
            category=data["category"],
            pattern=data["pattern"],
            slots=data.get("slots", {}),
            usage_count=data.get("usage_count", 0),
            success_count=data.get("success_count", 0),
            created_at=data.get("created_at", time.time()),
            last_used=data.get("last_used", time.time()),
            coherence=data.get("coherence", 0.5),
            stability=data.get("stability", 0.0)
        )
        return t

@dataclass
class HybridIntent:
    """Hybrid intent formed from co-occurring primitives"""
    id: str
    components: Tuple[str, str]  # The two parent intents
    modality: str
    
    # Evolution metadata
    occurrence_count: int = 0
    coherence: float = 0.0
    created_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "components": list(self.components),
            "modality": self.modality,
            "occurrence_count": self.occurrence_count,
            "coherence": self.coherence,
            "created_at": self.created_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'HybridIntent':
        return cls(
            id=data["id"],
            components=tuple(data["components"]),
            modality=data["modality"],
            occurrence_count=data.get("occurrence_count", 0),
            coherence=data.get("coherence", 0.0),
            created_at=data.get("created_at", time.time())
        )

@dataclass
class LexicalEntry:
    """Unified lexical entry for any modality"""
    id: str
    modality: str
    form: str  # The actual word/pattern/parameter
    
    # Semantic embeddings (modality-specific interpretation)
    embedding: List[float] = field(default_factory=lambda: [0.0] * 64)
    
    # Intent bindings
    intent_map: Dict[str, float] = field(default_factory=dict)
    
    # Co-occurrence with other entries
    co_occurrence: Dict[str, int] = field(default_factory=dict)
    
    # Metadata
    frequency: int = 0
    confidence: float = 0.5
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "modality": self.modality,
            "form": self.form,
            "embedding": self.embedding,
            "intent_map": self.intent_map,
            "co_occurrence": self.co_occurrence,
            "frequency": self.frequency,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "last_updated": self.last_updated
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LexicalEntry':
        return cls(
            id=data["id"],
            modality=data["modality"],
            form=data["form"],
            embedding=data.get("embedding", [0.0] * 64),
            intent_map=data.get("intent_map", {}),
            co_occurrence=data.get("co_occurrence", {}),
            frequency=data.get("frequency", 0),
            confidence=data.get("confidence", 0.5),
            created_at=data.get("created_at", time.time()),
            last_updated=data.get("last_updated", time.time())
        )

# ============================================================================
# UNIFIED EVOLUTION ENGINE
# ============================================================================

class UnifiedEvolutionEngine:
    """
    Single evolution engine that works across all modalities.
    Uses same template learning and hybrid promotion for everything.
    """
    
    HYBRID_PROMOTION_THRESHOLD = 10
    COHERENCE_THRESHOLD = 0.4
    DECAY_FACTOR = 0.85
    MAX_HYBRID_DEPTH = 2
    
    def __init__(self, modality: str):
        self.modality = modality
        
        # Templates organized by category
        self.templates: Dict[str, List[EvolutionTemplate]] = defaultdict(list)
        
        # Hybrids organized by component pairs
        self.hybrids: Dict[str, HybridIntent] = {}
        self.hybrid_depths: Dict[str, int] = {}
        
        # Co-occurrence tracking for hybrid formation
        self.co_occurrences: Dict[Tuple[str, str], int] = defaultdict(int)
        self.reinforced_this_session: Set[Tuple[str, str]] = set()
        
        # Lexical entries
        self.lexicon: Dict[str, LexicalEntry] = {}
        
        # Session tracking
        self.session_count = 0
        
    def observe_template(self, category: str, content: str, context: Dict[str, Any] = None):
        """
        Observe a template occurrence. Extract pattern and store.
        Works for any modality.
        """
        # Extract pattern by slotting values
        pattern = self._extract_pattern(content)
        
        # Check if we already have this pattern
        template_id = hashlib.md5(f"{self.modality}:{category}:{pattern}".encode()).hexdigest()[:16]
        
        existing = None
        for t in self.templates[category]:
            if t.pattern == pattern:
                existing = t
                break
        
        if existing:
            existing.usage_count += 1
            existing.last_used = time.time()
            if context and context.get("success", False):
                existing.success_count += 1
        else:
            # Create new template
            template = EvolutionTemplate(
                id=template_id,
                modality=self.modality,
                category=category,
                pattern=pattern,
                slots=self._extract_slots(pattern),
                usage_count=1,
                success_count=1 if (context and context.get("success")) else 0
            )
            self.templates[category].append(template)
            logger.info(f"[{self.modality.upper()}] Learned new template: {pattern[:50]}...")
    
    def observe_co_occurrence(self, element_a: str, element_b: str):
        """
        Track co-occurrence for hybrid formation.
        Can be intents, templates, animations, phonemes, etc.
        """
        if not element_a or not element_b or element_a == element_b:
            return
            
        # Check hybrid depth
        depth_a = self.hybrid_depths.get(element_a, 0)
        depth_b = self.hybrid_depths.get(element_b, 0)
        
        if max(depth_a, depth_b) >= self.MAX_HYBRID_DEPTH:
            return
            
        # Record co-occurrence
        pair = tuple(sorted([element_a, element_b]))
        self.co_occurrences[pair] += 1
        self.reinforced_this_session.add(pair)
        
        # Check for hybrid promotion
        if self.co_occurrences[pair] >= self.HYBRID_PROMOTION_THRESHOLD:
            self._promote_hybrid(pair, max(depth_a, depth_b) + 1)
    
    def _promote_hybrid(self, pair: Tuple[str, str], depth: int):
        """Promote a co-occurring pair to hybrid status"""
        hybrid_id = f"{pair[0]}_{pair[1]}_HYBRID"
        
        if hybrid_id in self.hybrids:
            return
            
        # Calculate coherence based on occurrence count
        coherence = min(1.0, self.co_occurrences[pair] / 20.0)
        
        hybrid = HybridIntent(
            id=hybrid_id,
            components=pair,
            modality=self.modality,
            occurrence_count=self.co_occurrences[pair],
            coherence=coherence
        )
        
        self.hybrids[hybrid_id] = hybrid
        self.hybrid_depths[hybrid_id] = depth
        
        logger.info(f"[{self.modality.upper()}] Promoted hybrid: {hybrid_id} (coherence={coherence:.2f})")
    
    def add_lexical_entry(self, form: str, embedding: List[float] = None) -> LexicalEntry:
        """Add or get lexical entry"""
        entry_id = f"{self.modality}:{form}"
        
        if entry_id not in self.lexicon:
            self.lexicon[entry_id] = LexicalEntry(
                id=entry_id,
                modality=self.modality,
                form=form,
                embedding=embedding or [0.0] * 64
            )
        
        return self.lexicon[entry_id]
    
    def bind_lexical_to_intent(self, form: str, intent: str, confidence_delta: float = 0.1):
        """Bind a lexical entry to an intent"""
        entry = self.add_lexical_entry(form)
        entry.intent_map[intent] = min(1.0, entry.intent_map.get(intent, 0) + confidence_delta)
        entry.frequency += 1
        entry.last_updated = time.time()
    
    def get_best_template(self, category: str, context: Dict[str, Any] = None) -> Optional[EvolutionTemplate]:
        """Get the best template for a category based on stability and success rate"""
        templates = self.templates.get(category, [])
        if not templates:
            return None
            
        # Score by stability and success rate
        def score(t: EvolutionTemplate) -> float:
            success_rate = t.success_count / max(1, t.usage_count)
            return t.stability * 0.5 + success_rate * 0.5
            
        return max(templates, key=score)
    
    def end_session(self):
        """End session: decay unreinforced, update stability"""
        self.session_count += 1
        
        # Decay unreinforced co-occurrences
        for pair in list(self.co_occurrences.keys()):
            if pair not in self.reinforced_this_session:
                self.co_occurrences[pair] = int(self.co_occurrences[pair] * self.DECAY_FACTOR)
                if self.co_occurrences[pair] < 1:
                    del self.co_occurrences[pair]
        
        self.reinforced_this_session.clear()
        
        # Update template stability
        for category_templates in self.templates.values():
            for template in category_templates:
                if template.usage_count > 0:
                    template.stability = min(1.0, template.stability + 0.05)
    
    def _extract_pattern(self, content: str) -> str:
        """Extract a pattern from content by slotting values"""
        # Slot numbers
        pattern = re.sub(r'\d+', '{number}', content)
        # Slot quoted strings
        pattern = re.sub(r'"[^"]*"', '{text}', pattern)
        pattern = re.sub(r"'[^']*'", '{text}', pattern)
        # Slot hex values
        pattern = re.sub(r'[0-9a-f]{8,}', '{hash}', pattern)
        return pattern
    
    def _extract_slots(self, pattern: str) -> Dict[str, str]:
        """Extract slot names from pattern"""
        slots = {}
        slot_types = {
            '{number}': 'float',
            '{text}': 'str',
            '{hash}': 'str',
            '{value}': 'any'
        }
        for slot, type_name in slot_types.items():
            if slot in pattern:
                slots[slot[1:-1]] = type_name
        return slots
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "modality": self.modality,
            "session_count": self.session_count,
            "templates": {
                cat: [t.to_dict() for t in temps]
                for cat, temps in self.templates.items()
            },
            "hybrids": {k: v.to_dict() for k, v in self.hybrids.items()},
            "hybrid_depths": self.hybrid_depths,
            "co_occurrences": {f"{k[0]}|{k[1]}": v for k, v in self.co_occurrences.items()},
            "lexicon": {k: v.to_dict() for k, v in self.lexicon.items()}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'UnifiedEvolutionEngine':
        """Deserialize from dictionary"""
        engine = cls(data["modality"])
        engine.session_count = data.get("session_count", 0)
        
        # Load templates
        for cat, temps in data.get("templates", {}).items():
            engine.templates[cat] = [EvolutionTemplate.from_dict(t) for t in temps]
        
        # Load hybrids
        for k, v in data.get("hybrids", {}).items():
            engine.hybrids[k] = HybridIntent.from_dict(v)
        
        engine.hybrid_depths = data.get("hybrid_depths", {})
        
        # Load co-occurrences
        for k, v in data.get("co_occurrences", {}).items():
            parts = k.split("|")
            if len(parts) == 2:
                engine.co_occurrences[(parts[0], parts[1])] = v
        
        # Load lexicon
        for k, v in data.get("lexicon", {}).items():
            engine.lexicon[k] = LexicalEntry.from_dict(v)
        
        return engine


# ============================================================================
# MODULAR COMPRESSION LIBRARY
# ============================================================================

@dataclass
class ModuleManifest:
    """Manifest for a compressed module"""
    module_id: str
    modality: str
    version: int
    created_at: float
    chunk_count: int = 1
    total_entries: int = 0
    compression_ratio: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "module_id": self.module_id,
            "modality": self.modality,
            "version": self.version,
            "created_at": self.created_at,
            "chunk_count": self.chunk_count,
            "total_entries": self.total_entries,
            "compression_ratio": self.compression_ratio
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModuleManifest':
        return cls(**data)


class ModularLibrary:
    """
    Compressed, navigable library for AI evolution data.
    Each module ≤25MB after compression.
    """
    
    def __init__(self, library_path: str):
        self.library_path = Path(library_path)
        self.library_path.mkdir(parents=True, exist_ok=True)
        
        # Cache for decompressed modules
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._cache_timestamp: Dict[str, float] = {}
        self._cache_duration = 300  # 5 minutes
        
        # Master manifest
        self.manifest_path = self.library_path / "library_manifest.json"
        self.module_index: Dict[str, str] = {}  # module_id -> modality
        self._load_manifest()
    
    def _load_manifest(self):
        """Load the master manifest"""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, 'r') as f:
                    data = json.load(f)
                self.module_index = data.get("modules", {})
            except Exception as e:
                logger.error(f"[LIBRARY] Failed to load manifest: {e}")
                self.module_index = {}
    
    def _save_manifest(self):
        """Save the master manifest"""
        try:
            with open(self.manifest_path, 'w') as f:
                json.dump({
                    "modules": self.module_index,
                    "updated_at": time.time()
                }, f, indent=2)
        except Exception as e:
            logger.error(f"[LIBRARY] Failed to save manifest: {e}")
    
    def list_modules(self, modality: str = None) -> List[Dict[str, Any]]:
        """List available modules, optionally filtered by modality"""
        result = []
        for module_id, mod in self.module_index.items():
            if modality is None or mod == modality:
                manifest = self._load_module_manifest(module_id)
                if manifest:
                    result.append(manifest.to_dict())
        return result
    
    def _load_module_manifest(self, module_id: str) -> Optional[ModuleManifest]:
        """Load manifest for a specific module"""
        manifest_path = self.library_path / module_id / "manifest.json"
        if not manifest_path.exists():
            return None
        try:
            with open(manifest_path, 'r') as f:
                return ModuleManifest.from_dict(json.load(f))
        except Exception as e:
            logger.error(f"[LIBRARY] Failed to load module manifest {module_id}: {e}")
            return None
    
    def save_module(self, module_id: str, modality: str, data: Dict[str, Any],
                    chunk_by: str = None) -> ModuleManifest:
        """
        Save a module with compression. Auto-chunk if >25MB.
        
        Args:
            module_id: Unique identifier for this module
            modality: The modality type
            data: The data to compress
            chunk_by: If set, split data by this key for large datasets
        """
        module_dir = self.library_path / module_id
        module_dir.mkdir(parents=True, exist_ok=True)
        
        # Determine chunking strategy
        json_bytes = json.dumps(data).encode('utf-8')
        uncompressed_size = len(json_bytes)
        
        chunks = []
        
        if uncompressed_size > MAX_MODULE_SIZE_BYTES and chunk_by:
            # Split into chunks
            chunk_data_list = self._split_data(data, chunk_by)
            for i, chunk_data in enumerate(chunk_data_list):
                chunk_id = f"{module_id}_chunk_{i}"
                compressed = self._compress(chunk_data)
                chunk_path = module_dir / f"chunk_{i}.json.gz"
                with open(chunk_path, 'wb') as f:
                    f.write(compressed)
                chunks.append(chunk_path)
        else:
            # Single chunk
            compressed = self._compress(data)
            chunk_path = module_dir / "data.json.gz"
            with open(chunk_path, 'wb') as f:
                f.write(compressed)
            chunks.append(chunk_path)
        
        # Calculate compression ratio
        total_compressed = sum(os.path.getsize(c) for c in chunks)
        compression_ratio = total_compressed / uncompressed_size if uncompressed_size > 0 else 1.0
        
        # Create manifest
        manifest = ModuleManifest(
            module_id=module_id,
            modality=modality,
            version=int(time.time()),
            created_at=time.time(),
            chunk_count=len(chunks),
            total_entries=self._count_entries(data),
            compression_ratio=compression_ratio
        )
        
        # Save manifest
        with open(module_dir / "manifest.json", 'w') as f:
            json.dump(manifest.to_dict(), f, indent=2)
        
        # Update master index
        self.module_index[module_id] = modality
        self._save_manifest()
        
        logger.info(f"[LIBRARY] Saved module {module_id}: {len(chunks)} chunks, "
                   f"ratio={compression_ratio:.2%}")
        
        return manifest
    
    def load_module(self, module_id: str, decompress: bool = True) -> Optional[Dict[str, Any]]:
        """
        Load a module. Returns compressed bytes if decompress=False.
        Uses cache for recently accessed modules.
        """
        # Check cache
        if decompress and module_id in self._cache:
            cache_time = self._cache_timestamp.get(module_id, 0)
            if time.time() - cache_time < self._cache_duration:
                return self._cache[module_id].copy()
        
        module_dir = self.library_path / module_id
        if not module_dir.exists():
            return None
        
        manifest = self._load_module_manifest(module_id)
        if not manifest:
            return None
        
        # Load and decompress chunks
        if manifest.chunk_count == 1:
            chunk_path = module_dir / "data.json.gz"
            with open(chunk_path, 'rb') as f:
                compressed = f.read()
            
            if not decompress:
                return {"_compressed": compressed}
            
            data = self._decompress(compressed)
        else:
            # Multi-chunk
            all_data = []
            for i in range(manifest.chunk_count):
                chunk_path = module_dir / f"chunk_{i}.json.gz"
                with open(chunk_path, 'rb') as f:
                    compressed = f.read()
                
                if not decompress:
                    all_data.append({"_chunk_id": i, "_compressed": compressed})
                else:
                    chunk_data = self._decompress(compressed)
                    all_data.append(chunk_data)
            
            if not decompress:
                return {"_chunks": all_data}
            
            # Merge chunks
            data = self._merge_chunks(all_data)
        
        # Cache if decompressed
        if decompress:
            self._cache[module_id] = data
            self._cache_timestamp[module_id] = time.time()
        
        return data
    
    def query_module(self, module_id: str, query: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Query within a module without full decompression.
        Returns matching entries.
        """
        data = self.load_module(module_id, decompress=True)
        if not data:
            return []
        
        results = []
        
        # Query by key-value pairs
        def matches(item: Dict[str, Any]) -> bool:
            for key, value in query.items():
                if key not in item:
                    return False
                if isinstance(value, dict) and "_gt" in value:
                    if not (isinstance(item[key], (int, float)) and item[key] > value["_gt"]):
                        return False
                elif isinstance(value, dict) and "_lt" in value:
                    if not (isinstance(item[key], (int, float)) and item[key] < value["_lt"]):
                        return False
                elif item[key] != value:
                    return False
            return True
        
        # Search in templates, lexicon, hybrids
        for section in ["templates", "lexicon", "hybrids"]:
            if section in data:
                items = data[section]
                if isinstance(items, dict):
                    items = list(items.values())
                for item in items:
                    if isinstance(item, dict) and matches(item):
                        results.append(item)
        
        return results
    
    def edit_module(self, module_id: str, edits: List[Dict[str, Any]]) -> bool:
        """
        Apply edits to a module and recompress.
        
        Edits format:
        {
            "action": "add" | "update" | "delete",
            "section": "templates" | "lexicon" | "hybrids",
            "id": str,
            "data": dict (for add/update)
        }
        """
        # Load and decompress
        data = self.load_module(module_id, decompress=True)
        if not data:
            return False
        
        # Apply edits
        for edit in edits:
            action = edit.get("action")
            section = edit.get("section")
            item_id = edit.get("id")
            item_data = edit.get("data")
            
            if section not in data:
                continue
            
            if action == "add" or action == "update":
                data[section][item_id] = item_data
            elif action == "delete":
                if item_id in data[section]:
                    del data[section][item_id]
        
        # Get modality from manifest
        manifest = self._load_module_manifest(module_id)
        modality = manifest.modality if manifest else "unknown"
        
        # Recompress and save
        self.save_module(module_id, modality, data)
        
        # Clear cache
        if module_id in self._cache:
            del self._cache[module_id]
        
        logger.info(f"[LIBRARY] Applied {len(edits)} edits to {module_id}")
        return True
    
    def _compress(self, data: Dict[str, Any]) -> bytes:
        """Compress data using gzip"""
        json_bytes = json.dumps(data, separators=(',', ':')).encode('utf-8')
        return gzip.compress(json_bytes, compresslevel=COMPRESSION_LEVEL)
    
    def _decompress(self, compressed: bytes) -> Dict[str, Any]:
        """Decompress gzip data"""
        json_bytes = gzip.decompress(compressed)
        return json.loads(json_bytes.decode('utf-8'))
    
    def _split_data(self, data: Dict[str, Any], key: str) -> List[Dict[str, Any]]:
        """Split data into chunks by key"""
        if key not in data:
            return [data]
        
        items = data[key]
        if not isinstance(items, dict):
            return [data]
        
        # Split items into chunks that will be <25MB each
        items_list = list(items.items())
        chunks = []
        current_chunk = {}
        current_size = 0
        
        for item_id, item_data in items_list:
            item_size = len(json.dumps({item_id: item_data}).encode('utf-8'))
            
            if current_size + item_size > MAX_MODULE_SIZE_BYTES // 2 and current_chunk:
                # Start new chunk
                chunk_data = {k: v for k, v in data.items() if k != key}
                chunk_data[key] = current_chunk
                chunks.append(chunk_data)
                current_chunk = {item_id: item_data}
                current_size = item_size
            else:
                current_chunk[item_id] = item_data
                current_size += item_size
        
        # Add final chunk
        if current_chunk:
            chunk_data = {k: v for k, v in data.items() if k != key}
            chunk_data[key] = current_chunk
            chunks.append(chunk_data)
        
        return chunks
    
    def _merge_chunks(self, chunks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Merge chunks back together"""
        if not chunks:
            return {}
        
        result = {}
        for chunk in chunks:
            for key, value in chunk.items():
                if key not in result:
                    result[key] = value
                elif isinstance(value, dict):
                    if isinstance(result[key], dict):
                        result[key].update(value)
                    else:
                        result[key] = value
        
        return result
    
    def _count_entries(self, data: Dict[str, Any]) -> int:
        """Count total entries in data"""
        count = 0
        for key in ["templates", "lexicon", "hybrids", "co_occurrences"]:
            if key in data:
                if isinstance(data[key], dict):
                    count += len(data[key])
                elif isinstance(data[key], list):
                    count += len(data[key])
        return count


# ============================================================================
# AI LIBRARY INTERFACE
# ============================================================================

class AILibraryInterface:
    """
    High-level interface for the AI to interact with its library.
    Provides natural language-like operations.
    """
    
    def __init__(self, library: ModularLibrary):
        self.library = library
        self.active_modules: Dict[str, Dict[str, Any]] = {}  # module_id -> data
    
    def browse(self, modality: str = None) -> str:
        """
        Browse available modules. Returns a summary.
        AI can call this to see what's available.
        """
        modules = self.library.list_modules(modality)
        
        if not modules:
            return f"No modules found{f' for {modality}' if modality else ''}."
        
        lines = [f"Library contains {len(modules)} modules:"]
        for m in modules:
            lines.append(f"  - {m['module_id']} ({m['modality']}): "
                        f"{m['total_entries']} entries, "
                        f"compressed to {m['compression_ratio']:.0%}")
        
        return "\n".join(lines)
    
    def open(self, module_id: str) -> str:
        """
        Open a module for viewing/editing.
        Loads into memory for fast access.
        """
        data = self.library.load_module(module_id, decompress=True)
        if not data:
            return f"Module {module_id} not found."
        
        self.active_modules[module_id] = data
        
        # Build summary
        sections = []
        for key in ["templates", "lexicon", "hybrids"]:
            if key in data:
                count = len(data[key]) if isinstance(data[key], dict) else len(data[key])
                sections.append(f"{count} {key}")
        
        return f"Opened {module_id}: {', '.join(sections)}. Ready for editing."
    
    def search(self, module_id: str, query: str) -> str:
        """
        Search within a module using simple query language.
        Query format: "key:value" or "key>value" or "key<value"
        """
        if module_id not in self.active_modules:
            result = self.open(module_id)
            if result.startswith("Module"):
                return result
        
        # Parse query
        parsed = {}
        for part in query.split():
            if ":" in part:
                key, value = part.split(":", 1)
                parsed[key] = value
            elif ">" in part:
                key, value = part.split(">", 1)
                parsed[key] = {"_gt": float(value)}
            elif "<" in part:
                key, value = part.split("<", 1)
                parsed[key] = {"_lt": float(value)}
        
        results = self.library.query_module(module_id, parsed)
        
        if not results:
            return f"No results for '{query}' in {module_id}."
        
        lines = [f"Found {len(results)} results for '{query}':"]
        for r in results[:10]:  # Limit to 10
            name = r.get("form", r.get("pattern", r.get("id", "unknown")))[:50]
            lines.append(f"  - {name}")
        
        if len(results) > 10:
            lines.append(f"  ... and {len(results) - 10} more")
        
        return "\n".join(lines)
    
    def add_template(self, module_id: str, category: str, pattern: str) -> str:
        """Add a new template to an open module"""
        if module_id not in self.active_modules:
            return f"Module {module_id} not open. Call open('{module_id}') first."
        
        data = self.active_modules[module_id]
        if "templates" not in data:
            data["templates"] = {}
        
        template_id = hashlib.md5(pattern.encode()).hexdigest()[:16]
        data["templates"][template_id] = {
            "id": template_id,
            "category": category,
            "pattern": pattern,
            "usage_count": 0,
            "stability": 0.0
        }
        
        return f"Added template {template_id} to {category}."
    
    def close(self, module_id: str, save: bool = True) -> str:
        """
        Close a module, optionally saving changes.
        """
        if module_id not in self.active_modules:
            return f"Module {module_id} not open."
        
        if save:
            # Apply changes via edit_module
            data = self.active_modules[module_id]
            self.library.save_module(
                module_id,
                data.get("modality", "unknown"),
                data
            )
            result = f"Saved and closed {module_id}."
        else:
            result = f"Closed {module_id} without saving."
        
        del self.active_modules[module_id]
        return result


# ============================================================================
# INTEGRATION: Multi-Modality Evolution Manager
# ============================================================================

class MultiModalityEvolutionManager:
    """
    Manages evolution engines for all modalities.
    Handles persistence to the modular library.
    """
    
    def __init__(self, library_path: str):
        self.library = ModularLibrary(library_path)
        self.ai_interface = AILibraryInterface(self.library)
        
        # Evolution engines for each modality
        self.engines: Dict[str, UnifiedEvolutionEngine] = {}
        
        # Load existing engines
        self._load_all_engines()
    
    def _load_all_engines(self):
        """Load all saved engines from library"""
        for module_id, modality in self.library.module_index.items():
            if module_id.endswith("_evolution"):
                data = self.library.load_module(module_id, decompress=True)
                if data:
                    self.engines[modality] = UnifiedEvolutionEngine.from_dict(data)
                    logger.info(f"[EVOLUTION] Loaded {modality} engine: "
                               f"{len(self.engines[modality].templates)} categories")
    
    def get_engine(self, modality: str) -> UnifiedEvolutionEngine:
        """Get or create evolution engine for a modality"""
        if modality not in self.engines:
            self.engines[modality] = UnifiedEvolutionEngine(modality)
        return self.engines[modality]
    
    def observe(self, modality: str, category: str, content: str,
                context: Dict[str, Any] = None):
        """
        Observe content for template learning.
        Works for any modality.
        """
        engine = self.get_engine(modality)
        engine.observe_template(category, content, context)
    
    def observe_co_occurrence(self, modality: str, element_a: str, element_b: str):
        """Track co-occurrence for hybrid formation"""
        engine = self.get_engine(modality)
        engine.observe_co_occurrence(element_a, element_b)
    
    def cross_modal_observation(self, modality_a: str, element_a: str,
                                 modality_b: str, element_b: str):
        """
        Track cross-modal co-occurrence (e.g., word + gesture).
        This enables multimodal concept formation.
        """
        # Store in both engines
        key_a = f"{modality_a}:{element_a}"
        key_b = f"{modality_b}:{element_b}"
        
        self.observe_co_occurrence(modality_a, key_a, key_b)
        self.observe_co_occurrence(modality_b, key_b, key_a)
    
    def save_all(self):
        """Save all engines to library"""
        for modality, engine in self.engines.items():
            module_id = f"{modality}_evolution"
            data = engine.to_dict()
            self.library.save_module(module_id, modality, data)
        
        logger.info(f"[EVOLUTION] Saved {len(self.engines)} engines to library")
    
    def end_session(self):
        """End session for all engines and save"""
        for engine in self.engines.values():
            engine.end_session()
        self.save_all()
    
    def get_ai_interface(self) -> AILibraryInterface:
        """Get the AI-facing interface"""
        return self.ai_interface


# ============================================================================
# EXPORT FOR USE
# ============================================================================

__all__ = [
    'EvolutionTemplate',
    'HybridIntent',
    'LexicalEntry',
    'UnifiedEvolutionEngine',
    'ModularLibrary',
    'ModuleManifest',
    'AILibraryInterface',
    'MultiModalityEvolutionManager',
    'Modality',
    'MAX_MODULE_SIZE_MB'
]
