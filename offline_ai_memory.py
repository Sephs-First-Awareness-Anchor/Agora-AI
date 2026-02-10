#!/usr/bin/env python3
"""
Offline AI Memory System
========================

Account-linked persistent memory with delta logging and hierarchical compression.
Stripped down from dimensional_memory_constant for pure learning/personalization.

No consciousness geometry. Pure compression and pattern storage.
"""

import threading
import queue
import json
import time
import os
import uuid
import logging
import math
from dataclasses import dataclass, field

# Numpy is optional on Android - gracefully handle missing numpy
try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

    class _NumpyFallback:
        """Minimal fallback for numpy functions."""
        ndarray = list  # Type alias for type hints
        @staticmethod
        def zeros(n):
            return [0.0] * n
        @staticmethod
        def array(lst):
            return list(lst) if not isinstance(lst, list) else lst
        @staticmethod
        def mean(lst, axis=None):
            if not lst:
                return 0.0
            if axis == 0 and lst and isinstance(lst[0], (list, tuple)):
                n = len(lst[0])
                result = [0.0] * n
                for row in lst:
                    for i, v in enumerate(row):
                        result[i] += v
                return [v / len(lst) for v in result]
            return sum(lst) / len(lst)
        @staticmethod
        def dot(v1, v2):
            return sum(a * b for a, b in zip(v1, v2))
        class linalg:
            @staticmethod
            def norm(v):
                return math.sqrt(sum(x * x for x in v))
        class random:
            @staticmethod
            def randn(n):
                import random
                return [random.gauss(0, 1) for _ in range(n)]

    np = _NumpyFallback()
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from collections import defaultdict
from offline_ai_expression import IdentityAnchor
from offline_ai_system import add_version_metadata, engine as migration_engine, STATE_VERSION

# ============================================================================
# CONFIGURATION
# ============================================================================

LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(level=logging.INFO, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# ============================================================================
# 1. ADVANCED MEMORY COMPRESSION (PCA & ELLIPSOID SEEDS)
# ============================================================================

class PCAProjector:
    """
    Linear dimensionality reduction for memory nodes.
    y = Wx
    """
    def __init__(self, input_dim: int = 64, latent_dim: int = 16):
        self.input_dim = input_dim
        self.latent_dim = latent_dim
        # Global orthogonal projection matrix (initialized once or slowly evolving)
        self.W = np.linalg.qr(np.random.randn(input_dim, latent_dim))[0].T

    def compress(self, x: np.ndarray) -> np.ndarray:
        return self.W @ x

    def reconstruct(self, y: np.ndarray) -> np.ndarray:
        return self.W.T @ y

    def to_dict(self) -> Dict:
        return {"W": self.W.tolist(), "input_dim": self.input_dim, "latent_dim": self.latent_dim}

    @classmethod
    def from_dict(cls, data: Dict) -> 'PCAProjector':
        p = cls(data["input_dim"], data["latent_dim"])
        p.W = np.array(data["W"])
        return p

class GaussianEllipsoidSeed:
    """
    Level 2 Compression: Ellipsoid representation of a cluster.
    Stores (μ, Q_r, Λ_r)
    """
    def __init__(self, id: str, dimensions: int, top_r: int = 4):
        self.id = id
        self.dimensions = dimensions
        self.top_r = top_r
        self.centroid = np.zeros(dimensions)
        self.eigenvectors = np.eye(dimensions)[:, :top_r]
        self.eigenvalues = np.zeros(top_r)
        self.n = 0
        self.timestamp = time.time()
        self.reliability = 0.0
        self.sessions_survived = 0

    def fit(self, vectors: List[np.ndarray]):
        if not vectors: return
        self.n = len(vectors)
        stacked = np.vstack(vectors)
        self.centroid = np.mean(stacked, axis=0)

        if self.n > 1:
            cov = np.cov(stacked, rowvar=False)
            # Handle 1D case from np.cov
            if cov.ndim == 0:
                cov = np.array([[cov]])

            vals, vecs = np.linalg.eigh(cov)
            # Sort descending
            idx = np.argsort(vals)[::-1]
            self.eigenvalues = vals[idx[:self.top_r]]
            self.eigenvectors = vecs[:, idx[:self.top_r]]
        else:
            self.eigenvalues = np.zeros(self.top_r)
            self.eigenvectors = np.eye(self.dimensions)[:, :self.top_r]

        self.reliability = min(1.0, self.n / 10.0)
        self.timestamp = time.time()

    def sample(self, num_samples: int = 1) -> List[np.ndarray]:
        samples = []
        for _ in range(num_samples):
            # z ~ N(0, Λ_r)
            z = np.random.normal(0, np.sqrt(np.maximum(self.eigenvalues, 1e-8)))
            # x_hat = μ + Q_r z
            x_hat = self.centroid + self.eigenvectors @ z
            samples.append(x_hat)
        return samples

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "centroid": self.centroid.tolist(),
            "eigenvectors": self.eigenvectors.tolist(),
            "eigenvalues": self.eigenvalues.tolist(),
            "n": self.n,
            "reliability": self.reliability,
            "sessions_survived": self.sessions_survived,
            "timestamp": self.timestamp
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'GaussianEllipsoidSeed':
        s = cls(data["id"], len(data["centroid"]), len(data["eigenvalues"]))
        s.centroid = np.array(data["centroid"])
        s.eigenvectors = np.array(data["eigenvectors"])
        s.eigenvalues = np.array(data["eigenvalues"])
        s.n = data["n"]
        s.reliability = data["reliability"]
        s.sessions_survived = data.get("sessions_survived", 0)
        s.timestamp = data["timestamp"]
        return s


# ============================================================================
# 2. CORE DATA STRUCTURES
# ============================================================================

@dataclass
class EmotionShard:
    id: str
    primary_emotion: str
    intensity: float
    valence: float
    cp: Tuple[float, float, float]
    timestamp: float = field(default_factory=time.time)

@dataclass
class ImpressionSeed:
    id: str
    emotion_profile: Dict[str, float]
    cp_center: Tuple[float, float, float]
    reliability: float
    shard_ids: List[str]
    timestamp: float = field(default_factory=time.time)

@dataclass
class GhostRelic:
    id: str
    seed_ids: List[str]
    cp_trajectory: List[Tuple[float, float, float]]
    timestamp: float = field(default_factory=time.time)

@dataclass
class DialogueNode:
    """
    Represents a single turn in conversation or interaction.
    
    This is the atomic unit of learning for offline AI.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    account_id: str = ""
    turn_number: int = 0
    timestamp: float = field(default_factory=time.time)
    
    # Dialogue content
    role: str = "user"  # "user" or "assistant"
    content: str = ""
    
    # Context
    context_tags: List[str] = field(default_factory=list)
    dimension_links: List[str] = field(default_factory=list)
    
    # Personalization
    parameter_adjustments: Dict[str, float] = field(default_factory=dict)
    user_feedback: Dict[str, Any] = field(default_factory=dict)
    
    # Learning signal
    relevance_score: float = 0.5
    satisfaction_score: float = 0.5
    learning_value: float = 0.0
    sessions_survived: int = 0
    reinforcement: int = 0
    anchor_linked: bool = False
    
    # Impression links
    shard_id: Optional[str] = None
    lexical_vector: List[float] = field(default_factory=list)

    last_modified: float = field(default_factory=time.time)
    parent_node_id: Optional[str] = None
    child_node_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "account_id": self.account_id,
            "turn_number": self.turn_number,
            "timestamp": self.timestamp,
            "role": self.role,
            "content": self.content,
            "context_tags": self.context_tags,
            "dimension_links": self.dimension_links,
            "parameter_adjustments": self.parameter_adjustments,
            "user_feedback": self.user_feedback,
            "relevance_score": self.relevance_score,
            "satisfaction_score": self.satisfaction_score,
            "learning_value": self.learning_value,
            "sessions_survived": self.sessions_survived,
            "reinforcement": self.reinforcement,
            "anchor_linked": self.anchor_linked,
            "shard_id": self.shard_id,
            "lexical_vector": self.lexical_vector,
            "last_modified": self.last_modified,
            "parent_node_id": self.parent_node_id,
            "child_node_ids": self.child_node_ids
        }

    @staticmethod
    def from_dict(data: Dict) -> 'DialogueNode':
        node = DialogueNode()
        for key, value in data.items():
            if hasattr(node, key):
                setattr(node, key, value)
        return node

    def modify(self, updates: Dict[str, Any] = None) -> bool:
        """Modify node and return True if changed"""
        if not updates:
            return False
        
        modified = False
        for key, value in updates.items():
            if hasattr(self, key) and getattr(self, key) != value:
                setattr(self, key, value)
                modified = True
        
        if modified:
            self.last_modified = time.time()
        
        return modified


# ============================================================================
# 2. MEMORY STORAGE WITH DELTA LOGGING
# ============================================================================

class AccountLinkedMemory:
    """
    Core memory system for a single account.
    
    Features:
    - Account-based isolation
    - Delta logging for compression
    - Hierarchical node relationships
    - Fast concept/dimension lookups
    """
    
    def __init__(self, account_id: str, storage_dir: str = "./offline_ai_data"):
        self.account_id = account_id
        self.storage_dir = Path(storage_dir)
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"[MEMORY] Failed to create storage directory {storage_dir}: {e}")
        
        # Account-specific files
        self.account_base_file = self.storage_dir / account_id / "memory_base.json"
        self.account_delta_file = self.storage_dir / account_id / "memory_delta.log"
        try:
            self.account_base_file.parent.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"[MEMORY] Failed to create account directory {self.account_base_file.parent}: {e}")
        
        # In-memory state
        self.nodes: Dict[str, DialogueNode] = {}
        self.archived_nodes: Dict[str, Dict] = {} # node_id -> compressed_vector
        self.shards: Dict[str, EmotionShard] = {}
        self.seeds: Dict[str, GaussianEllipsoidSeed] = {}
        self.relics: Dict[str, GhostRelic] = {}
        self.identity_anchors: Dict[str, IdentityAnchor] = {}

        # New compression system
        self.input_dim = 64
        self.latent_dim = 16
        self.projector = PCAProjector(self.input_dim, self.latent_dim)

        self.concept_index: Dict[str, str] = {}  # concept_key -> node_id
        self.dimension_index: Dict[str, List[str]] = {}  # dimension -> [node_ids]
        self.turn_counter: int = 0
        
        # Live save queue
        self.save_queue = queue.Queue()
        self._save_thread_active = threading.Event()
        self._merge_thread_active = threading.Event()
        
        # Statistics
        self.total_interactions_loaded = 0
        self.last_merge_time = 0.0
        self.high_storage_pressure = False
        self.metadata: Dict[str, Any] = {}
        
        # Load existing state
        self._load_from_base()
        
        # Start background threads
        self._start_save_thread()
        self._start_merge_thread()
        
        logger.info(f"[ACCOUNT {account_id}] Memory initialized. "
                   f"Loaded {len(self.nodes)} nodes.")

    def _load_from_base(self, highest_session_id: str = ""):
        """Load account state from base file"""
        if not self.account_base_file.exists():
            logger.info(f"[ACCOUNT {self.account_id}] No existing base file. Starting fresh.")
            return
        
        try:
            with open(self.account_base_file, 'r') as f:
                data = json.load(f)
            
            # Section IV: Migration
            data = migration_engine.migrate("memory", data, STATE_VERSION)

            # Session Commit Barrier
            loaded_session = data.get("session_id", "")
            if highest_session_id and loaded_session and loaded_session != highest_session_id:
                logger.warning(f"[MEMORY] Session mismatch. Loaded: {loaded_session}, Expected: {highest_session_id}. Rolling back.")
                return

            self.turn_counter = data.get('turn_counter', 0)
            self.metadata = data.get('metadata', {})
            # Ensure session_token is in metadata if it was in root
            if "session_token" in data:
                self.metadata["session_token"] = data["session_token"]
            if "session_issued_at" in data:
                self.metadata["session_issued_at"] = data["session_issued_at"]

            loaded_nodes = data.get('nodes', {})
            self.archived_nodes = data.get('archived_nodes', {})
            
            # Load Projector
            if 'projector' in data:
                self.projector = PCAProjector.from_dict(data['projector'])

            # Load Seeds
            if 'seeds' in data:
                for sid, s_data in data['seeds'].items():
                    self.seeds[sid] = GaussianEllipsoidSeed.from_dict(s_data)

            for node_id, node_data in loaded_nodes.items():
                node = DialogueNode.from_dict(node_data)
                self.nodes[node_id] = node
                self._update_indices(node)
            
            self.total_interactions_loaded = len(self.nodes) + len(self.archived_nodes)
            logger.info(f"[ACCOUNT {self.account_id}] Loaded {len(self.nodes)} nodes, {len(self.archived_nodes)} archived, and {len(self.seeds)} seeds.")
        except Exception as e:
            logger.error(f"[ACCOUNT {self.account_id}] Failed to load base: {e}")

    def _update_indices(self, node: DialogueNode):
        """Update concept and dimension indices"""
        # Concept indexing
        concept_key = f"{node.role}_{node.turn_number}"
        self.concept_index[concept_key] = node.id
        
        # Dimension indexing
        for dim in node.dimension_links:
            if dim not in self.dimension_index:
                self.dimension_index[dim] = []
            if node.id not in self.dimension_index[dim]:
                self.dimension_index[dim].append(node.id)

    def add_node(self, node: DialogueNode) -> bool:
        """Add a new dialogue node to memory"""
        if node.account_id != self.account_id:
            node.account_id = self.account_id
        
        if node.id in self.nodes:
            logger.warning(f"[ACCOUNT {self.account_id}] Node {node.id} exists. Overwriting.")
        
        node.turn_number = self.turn_counter
        self.turn_counter += 1
        
        self.nodes[node.id] = node
        self._update_indices(node)
        
        # Queue for save
        self.save_queue.put(('add', node))
        
        logger.debug(f"[ACCOUNT {self.account_id}] Added node {node.id} (turn {node.turn_number})")
        return True

    def modify_node(self, node_id: str, updates: Dict[str, Any]) -> bool:
        """Modify existing node"""
        if node_id not in self.nodes:
            logger.error(f"[ACCOUNT {self.account_id}] Node {node_id} not found.")
            return False
        
        node = self.nodes[node_id]
        was_modified = node.modify(updates)
        
        if was_modified:
            self._update_indices(node)
            self.save_queue.put(('modify', node))
            logger.debug(f"[ACCOUNT {self.account_id}] Modified node {node_id}")
        
        return was_modified

    def get_node(self, node_id: str) -> Optional[DialogueNode]:
        """Retrieve a node by ID"""
        return self.nodes.get(node_id)

    def find_nodes_by_dimension(self, dimension: str) -> List[DialogueNode]:
        """Find all nodes with a specific dimension tag"""
        node_ids = self.dimension_index.get(dimension, [])
        return [self.nodes[nid] for nid in node_ids if nid in self.nodes]

    def get_conversation_chain(self, start_node_id: str) -> List[DialogueNode]:
        """Get a conversation thread following parent/child links"""
        chain = []
        current_id = start_node_id
        
        while current_id and current_id in self.nodes:
            chain.append(self.nodes[current_id])
            current_node = self.nodes[current_id]
            
            # Follow parent chain backwards
            if current_node.parent_node_id:
                current_id = current_node.parent_node_id
            else:
                break
        
        return list(reversed(chain))

    def link_nodes(self, parent_id: str, child_id: str) -> bool:
        """Create parent-child relationship between nodes"""
        if parent_id not in self.nodes or child_id not in self.nodes:
            logger.error(f"[ACCOUNT {self.account_id}] Cannot link: nodes not found.")
            return False
        
        parent_node = self.nodes[parent_id]
        child_node = self.nodes[child_id]
        
        # Two-way linking
        if child_id not in parent_node.child_node_ids:
            parent_node.child_node_ids.append(child_id)
        
        child_node.parent_node_id = parent_id
        
        # Queue for save
        self.save_queue.put(('modify', parent_node))
        self.save_queue.put(('modify', child_node))
        
        logger.debug(f"[ACCOUNT {self.account_id}] Linked {parent_id} -> {child_id}")
        return True

    def get_stats(self) -> Dict[str, Any]:
        """Get memory statistics"""
        return {
            'account_id': self.account_id,
            'total_nodes': len(self.nodes),
            'total_turns': self.turn_counter,
            'dimension_count': len(self.dimension_index),
            'concept_count': len(self.concept_index),
            'save_queue_size': self.save_queue.qsize(),
            'last_merge_time': self.last_merge_time
        }

    def retrieve_context(self, query_vector: np.ndarray, k: int = 5,
                        alpha: float = 0.4, beta: float = 0.2,
                        gamma: float = 0.2, delta: float = 0.2,
                        epsilon: float = 0.1, tau: float = 86400.0) -> List[DialogueNode]:
        """
        Memory Retrieval Attention Engine (Section VI).

        Scoring: α * cosine + β * reliability + γ * exp(−age/τ) + δ * emotional_similarity − ε * entropy_penalty
        """
        scores = []
        current_time = time.time()

        # We search both live nodes and archived nodes if possible,
        # but for now we focus on live nodes for full context
        for node in self.nodes.values():
            node_vector = self._extract_vector(node)

            # 1. Cosine similarity
            norm_q = np.linalg.norm(query_vector)
            norm_n = np.linalg.norm(node_vector)
            if norm_q > 0 and norm_n > 0:
                cosine_sim = np.dot(query_vector, node_vector) / (norm_q * norm_n)
            else:
                cosine_sim = 0.0

            # 2. Reliability (from node or seed)
            reliability = node.relevance_score # Simplified
            if node.shard_id and node.shard_id in self.shards:
                 # If associated with a seed, could use seed reliability
                 pass

            # 3. Age decay
            age = current_time - node.timestamp
            time_factor = math.exp(-age / tau)

            # 4. Emotional similarity (δ)
            # Use valence and intensity from vector indices 32, 33
            q_valence, q_intensity = query_vector[32], query_vector[33]
            n_valence, n_intensity = node_vector[32], node_vector[33]
            emotional_sim = 1.0 - (abs(q_valence - n_valence) + abs(q_intensity - n_intensity)) / 2.0

            # 5. Entropy penalty (ε)
            # Simplified: use a default or based on turn frequency
            entropy_penalty = 0.0 # This would ideally come from the entropic regulator

            # Final Score
            score = (alpha * cosine_sim +
                     beta * reliability +
                     gamma * time_factor +
                     delta * emotional_sim -
                     epsilon * entropy_penalty)

            scores.append((score, node))

        # Sort by score descending
        scores.sort(key=lambda x: x[0], reverse=True)
        return [node for score, node in scores[:k]]

    # ========================================================================
    # BACKGROUND THREADS FOR DELTA LOGGING & PERSISTENCE
    # ========================================================================

    def _start_save_thread(self):
        """Background thread that writes to delta log"""
        self._save_thread_active.set()
        thread = threading.Thread(target=self._save_worker, daemon=True)
        thread.start()
        logger.info(f"[ACCOUNT {self.account_id}] Save thread started")

    def _save_worker(self):
        """Continuously process save queue"""
        while self._save_thread_active.is_set():
            try:
                operation, node = self.save_queue.get(timeout=1)
                self._write_to_delta_log(operation, node)
            except queue.Empty:
                pass
            except Exception as e:
                logger.error(f"[ACCOUNT {self.account_id}] Save error: {e}")

    def _write_to_delta_log(self, operation: str, node: DialogueNode):
        """Append operation to delta log"""
        try:
            delta_entry = {
                'timestamp': time.time(),
                'operation': operation,
                'node_id': node.id,
                'node_data': node.to_dict()
            }
            
            with open(self.account_delta_file, 'a') as f:
                f.write(json.dumps(delta_entry) + '\n')
            
            logger.debug(f"[ACCOUNT {self.account_id}] Delta: {operation} {node.id}")
        except Exception as e:
            logger.error(f"[ACCOUNT {self.account_id}] Delta write failed: {e}")

    def _start_merge_thread(self):
        """Background thread that periodically merges delta log into base"""
        self._merge_thread_active.set()
        thread = threading.Thread(target=self._merge_worker, daemon=True)
        thread.start()
        logger.info(f"[ACCOUNT {self.account_id}] Merge thread started")

    def _merge_worker(self):
        """Periodically merge delta log into base file (every 30 seconds)"""
        while self._merge_thread_active.is_set():
            try:
                time.sleep(30)
                self.merge_delta_log()
            except Exception as e:
                logger.error(f"[ACCOUNT {self.account_id}] Merge error: {e}")

    def _extract_vector(self, node: DialogueNode) -> np.ndarray:
        """Map node properties to 64D space for PCA compression"""
        v = np.zeros(self.input_dim)

        # 1. Text hashing (32-dim)
        import hashlib
        content_hash = hashlib.sha256(node.content.encode()).digest()
        for i in range(min(32, len(content_hash))):
            v[i] = (content_hash[i] / 255.0) - 0.5

        # 2. Emotion & Style (16-dim)
        if node.shard_id and node.shard_id in self.shards:
            shard = self.shards[node.shard_id]
            v[32] = shard.valence
            v[33] = shard.intensity
            if len(shard.cp) >= 3:
                v[34] = shard.cp[0]
                v[35] = shard.cp[1]
                v[36] = shard.cp[2]
        else:
            v[32] = node.relevance_score
            v[33] = node.satisfaction_score
            v[34] = node.learning_value

        # Style
        v[40] = node.parameter_adjustments.get("warmth", 0.5)
        v[41] = node.parameter_adjustments.get("formality", 0.5)
        v[42] = node.parameter_adjustments.get("precision", 0.5)

        # 3. Temporal & Structural (8-dim)
        v[48] = min(1.0, len(node.content) / 1000)
        v[49] = min(1.0, len(node.child_node_ids) / 10)
        v[50] = np.exp(-(time.time() - node.timestamp) / 86400)
        v[51] = (node.turn_number % 100) / 100.0

        # 4. Intent & Reserved (8-dim)
        # Hash intent if tags exist
        if node.context_tags:
            intent_hash = hashlib.md5(node.context_tags[0].encode()).digest()
            for i in range(min(4, len(intent_hash))):
                v[56+i] = (intent_hash[i] / 255.0)

        # 5. Lexical Integration (Section I)
        if hasattr(node, 'lexical_vector') and node.lexical_vector and len(node.lexical_vector) == self.input_dim:
            # Blend lexical semantics into the turn vector
            v = 0.6 * v + 0.4 * np.array(node.lexical_vector)

        return v

    def decode_vector(self, v: np.ndarray) -> Dict[str, Any]:
        """Decode a 64D vector back into human-readable components"""
        # Note: Text hashing (0-31) is lossy and cannot be fully reversed

        decoded = {
            "valence": v[32],
            "intensity": v[33],
            "cp": (v[34], v[35], v[36]),
            "warmth": v[40],
            "formality": v[41],
            "precision": v[42],
            "content_length_est": v[48] * 1000,
            "temporal_decay_factor": v[50]
        }
        return decoded

    def create_shard(self, node_id: str, emotion: str, intensity: float, valence: float, cp: Tuple[float, float, float]) -> str:
        shard_id = f"shard_{int(time.time()*1000)}"
        shard = EmotionShard(id=shard_id, primary_emotion=emotion, intensity=intensity, valence=valence, cp=cp)
        self.shards[shard_id] = shard
        if node_id in self.nodes:
            self.nodes[node_id].shard_id = shard_id
        return shard_id

    def form_seeds(self, additional_vectors: List[np.ndarray] = None):
        # Level 2 Compression: Cluster PCA-compressed nodes into seeds
        if not self.nodes and not additional_vectors: return

        # Group nodes/vectors by category
        clusters = defaultdict(list)
        node_samples = defaultdict(list) # To track original nodes for anchors

        for node in self.nodes.values():
            intent = node.context_tags[0] if node.context_tags else "unknown"
            latent = self.projector.compress(self._extract_vector(node))
            clusters[intent].append(latent)
            node_samples[intent].append(node)

        # Process additional vectors (e.g. from Lexical Memory)
        if additional_vectors:
            for v in additional_vectors:
                latent = self.projector.compress(v)
                clusters["lexical_pool"].append(latent)

        for category, latent_vectors in clusters.items():
            if len(latent_vectors) < 3: continue

            seed_id = f"seed_{category}_{int(time.time())}"
            seed = GaussianEllipsoidSeed(seed_id, self.latent_dim)
            seed.fit(latent_vectors)
            self.seeds[seed_id] = seed

            # Form identity anchors for very reliable patterns (from nodes only)
            if seed.reliability > 0.8 and category in node_samples:
                primary_emo = "neutral"
                sample_node = node_samples[category][0]
                if sample_node.shard_id and sample_node.shard_id in self.shards:
                    primary_emo = self.shards[sample_node.shard_id].primary_emotion

                anchor_id = f"anchor_{category}_{primary_emo}"
                if anchor_id not in self.identity_anchors:
                    self.identity_anchors[anchor_id] = IdentityAnchor(
                        id=anchor_id,
                        trait=f"{category}_{primary_emo}",
                        reinforcement=1
                    )
                else:
                    self.identity_anchors[anchor_id].reinforcement += 1

    def set_pruning_pressure(self, active: bool):
        """Enable/disable high pruning pressure (Section II)"""
        self.high_storage_pressure = active

    def erosion_pass(self):
        """
        SECTION 5 — EROSION PASS (LIVE MEMORY ONLY)
        Algorithm:
        - Merge duplicate nodes (distance < DUP_EPS)
        - Delete weak nodes (low sessions AND low reinforcement)
        - Intent coherence check
        """
        DUP_EPS = 0.02
        LOW_REINFORCE = 2
        LOW_SURVIVE_SESSIONS = 2
        COHERENCE_MIN = 0.35

        if not self.nodes:
            return

        logger.info(f"[MEMORY] Starting erosion pass on {len(self.nodes)} nodes.")

        # 1. Deduplication (Merge similar nodes)
        node_ids = list(self.nodes.keys())
        to_delete = set()

        for i in range(len(node_ids)):
            id_i = node_ids[i]
            if id_i in to_delete: continue
            node_i = self.nodes[id_i]
            v_i = self.projector.compress(self._extract_vector(node_i))

            for j in range(i + 1, len(node_ids)):
                id_j = node_ids[j]
                if id_j in to_delete: continue
                node_j = self.nodes[id_j]
                v_j = self.projector.compress(self._extract_vector(node_j))

                dist = np.linalg.norm(v_i - v_j)
                if dist < DUP_EPS:
                    # Merge node_j into node_i
                    node_i.reinforcement += node_j.reinforcement
                    node_i.learning_value = (node_i.learning_value + node_j.learning_value) / 2
                    to_delete.add(id_j)
                    logger.debug(f"[MEMORY] Merged duplicate node {id_j} into {id_i}")

        for nid in to_delete:
            del self.nodes[nid]

        # 2. Pruning weak nodes & Intent Coherence
        node_ids = list(self.nodes.keys())
        for nid in node_ids:
            node = self.nodes[nid]
            if node.anchor_linked:
                continue

            # Survival check
            if node.sessions_survived < LOW_SURVIVE_SESSIONS and node.reinforcement < LOW_REINFORCE:
                del self.nodes[nid]
                logger.debug(f"[MEMORY] Eroded weak node {nid}")
                continue

            # Intent coherence
            intent = node.context_tags[0] if node.context_tags else "unknown"
            # Find matching seed for centroid comparison
            matching_seed = None
            for seed in self.seeds.values():
                if f"seed_{intent}" in seed.id:
                    matching_seed = seed
                    break

            if matching_seed:
                latent = self.projector.compress(self._extract_vector(node))
                norm_l = np.linalg.norm(latent)
                norm_c = np.linalg.norm(matching_seed.centroid)
                if norm_l > 0 and norm_c > 0:
                    similarity = np.dot(latent, matching_seed.centroid) / (norm_l * norm_c)
                else:
                    similarity = 0.0

                if similarity < COHERENCE_MIN:
                    # Retag or decay
                    logger.debug(f"[MEMORY] Node {nid} failed intent coherence ({similarity:.2f} < {COHERENCE_MIN})")
                    node.relevance_score *= 0.8
                    node.learning_value *= 0.8

        logger.info(f"[MEMORY] Erosion pass complete. {len(self.nodes)} nodes remaining.")

    def merge_delta_log(self, session_id: str = ""):
        """Merge delta log into base file for compression"""
        if not self.account_delta_file.exists() and not self.nodes:
            return
        
        try:
            # Hierarchical Memory Pyramid Step:
            # Level 0 (Raw) -> Level 1 (PCA Archived)
            # Section II: Adaptive Limits - reduce max live nodes under pressure
            max_live_nodes = 20 if self.high_storage_pressure else 50
            if len(self.nodes) > max_live_nodes:
                sorted_nodes = sorted(self.nodes.values(), key=lambda x: x.turn_number)
                to_archive = sorted_nodes[:-max_live_nodes]
                for node in to_archive:
                    vector = self._extract_vector(node)
                    latent = self.projector.compress(vector)
                    self.archived_nodes[node.id] = {
                        "latent_vector": latent.tolist(),
                        "turn_number": node.turn_number,
                        "role": node.role,
                        "timestamp": node.timestamp
                    }
                    del self.nodes[node.id]
                logger.info(f"[ACCOUNT {self.account_id}] Archived {len(to_archive)} nodes to Level 1 (PCA).")

            # Build current state
            state = {
                'session_id': session_id,
                'account_id': self.account_id,
                'turn_counter': self.turn_counter,
                'metadata': self.metadata,
                'nodes': {nid: node.to_dict() for nid, node in self.nodes.items()},
                'archived_nodes': self.archived_nodes,
                'seeds': {sid: s.to_dict() for sid, s in self.seeds.items()},
                'projector': self.projector.to_dict(),
                'last_merge_timestamp': time.time()
            }
            add_version_metadata(state, "memory")
            
            # Write to temp file first (atomic write)
            temp_file = self.account_base_file.with_suffix('.tmp')
            with open(temp_file, 'w') as f:
                json.dump(state, f, indent=2)
            
            # Atomic rename
            temp_file.replace(self.account_base_file)
            
            # Clear delta log
            self.account_delta_file.unlink(missing_ok=True)
            
            self.last_merge_time = time.time()
            logger.info(f"[ACCOUNT {self.account_id}] Merged delta log. "
                       f"{len(self.nodes)} nodes compressed.")
        except Exception as e:
            logger.error(f"[ACCOUNT {self.account_id}] Merge failed: {e}")

    def to_dict(self) -> Dict[str, Any]:
        """Return a serializable representation of the current state"""
        return {
            'account_id': self.account_id,
            'turn_counter': self.turn_counter,
            'metadata': self.metadata,
            'nodes': {nid: node.to_dict() for nid, node in self.nodes.items()},
            'archived_nodes': self.archived_nodes,
            'seeds': {sid: s.to_dict() for sid, s in self.seeds.items()},
            'projector': self.projector.to_dict()
        }

    def shutdown(self):
        """Graceful shutdown"""
        logger.info(f"[ACCOUNT {self.account_id}] Shutting down...")
        
        self._save_thread_active.clear()
        self._merge_thread_active.clear()
        
        # Final merge
        self.merge_delta_log()
        
        logger.info(f"[ACCOUNT {self.account_id}] Shutdown complete")


# ============================================================================
# 3. MULTI-ACCOUNT MEMORY MANAGER
# ============================================================================

class MemoryManager:
    """
    Manages multiple account memories.
    
    Keeps account memories separate but allows queries across accounts
    for the teaching platform.
    """
    
    def __init__(self, storage_dir: str = "./offline_ai_data"):
        self.storage_dir = Path(storage_dir)
        try:
            self.storage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error(f"[MEMORY MANAGER] Failed to create storage directory {storage_dir}: {e}")
        self.accounts: Dict[str, AccountLinkedMemory] = {}
        
        logger.info(f"[MEMORY MANAGER] Initialized at {self.storage_dir}")

    def get_or_create_account(self, account_id: str) -> AccountLinkedMemory:
        """Get existing account memory or create new one"""
        if account_id not in self.accounts:
            self.accounts[account_id] = AccountLinkedMemory(
                account_id, 
                str(self.storage_dir)
            )
            logger.info(f"[MEMORY MANAGER] Created new account: {account_id}")
        
        return self.accounts[account_id]

    def get_account(self, account_id: str) -> Optional[AccountLinkedMemory]:
        """Get account memory if exists"""
        return self.accounts.get(account_id)

    def list_accounts(self) -> List[str]:
        """List all account IDs"""
        return list(self.accounts.keys())

    def get_global_stats(self) -> Dict[str, Any]:
        """Statistics across all accounts"""
        total_nodes = sum(len(acc.nodes) for acc in self.accounts.values())
        total_interactions = sum(acc.turn_counter for acc in self.accounts.values())
        
        return {
            'total_accounts': len(self.accounts),
            'total_nodes_all_accounts': total_nodes,
            'total_interactions_all_accounts': total_interactions,
            'accounts': {aid: acc.get_stats() for aid, acc in self.accounts.items()}
        }

    def shutdown_all(self):
        """Shutdown all accounts gracefully"""
        logger.info("[MEMORY MANAGER] Shutting down all accounts...")
        for account in self.accounts.values():
            account.shutdown()
        logger.info("[MEMORY MANAGER] All accounts shut down")


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def create_dialogue_node(account_id: str, role: str, content: str, 
                        context_tags: List[str] = None) -> DialogueNode:
    """Factory function to create dialogue nodes"""
    return DialogueNode(
        account_id=account_id,
        role=role,
        content=content,
        context_tags=context_tags or []
    )


if __name__ == "__main__":
    # Quick test
    mem = MemoryManager("./test_memory")
    acc1 = mem.get_or_create_account("user_001")
    
    # Add some dialogue
    node1 = create_dialogue_node("user_001", "user", "Hello, who are you?")
    acc1.add_node(node1)
    
    node2 = create_dialogue_node("user_001", "assistant", "I'm Claude.")
    acc1.add_node(node2)
    
    acc1.link_nodes(node1.id, node2.id)
    
    print("Stats:", acc1.get_stats())
    print("Conversation:", [n.content for n in acc1.get_conversation_chain(node2.id)])
    
    time.sleep(2)  # Wait for background threads
    mem.shutdown_all()
