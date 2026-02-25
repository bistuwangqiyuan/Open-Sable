"""
Memory management for Open-Sable - ChromaDB for vectors + JSON for structured data.
Structured memory is encrypted at rest using Fernet symmetric encryption.
"""

import base64
import hashlib
import logging
import json
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import chromadb

logger = logging.getLogger(__name__)


def _derive_key(secret: str) -> bytes:
    """Derive a 32-byte (URL-safe base64) Fernet key from an arbitrary secret string."""
    raw = hashlib.sha256(secret.encode()).digest()
    return base64.urlsafe_b64encode(raw)


class MemoryManager:
    """Manages both vector and structured memory.

    Structured memory (data/memory.json) is encrypted at rest using Fernet.
    The encryption key is derived from the MEMORY_SECRET env var (or a default).
    """

    def __init__(self, config):
        self.config = config
        self.vector_db = None
        self.collection = None
        self.structured_memory_path = Path("./data/memory.json")
        self.structured_memory = {}

        # Encryption setup — Fernet is an optional dependency
        self._fernet = None
        try:
            from cryptography.fernet import Fernet
            secret = os.environ.get("MEMORY_SECRET") or getattr(config, "memory_secret", None) or "opensable-default-key"
            self._fernet = Fernet(_derive_key(secret))
            logger.debug("Memory encryption enabled (Fernet)")
        except ImportError:
            logger.info("cryptography package not installed — memory stored in plaintext. pip install cryptography to enable encryption.")

    async def initialize(self):
        """Initialize memory systems"""
        # Create data directory
        self.config.vector_db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB with new API
        self.vector_db = chromadb.PersistentClient(path=str(self.config.vector_db_path))

        self.collection = self.vector_db.get_or_create_collection(
            name="opensable_memory", metadata={"description": "User interactions and context"}
        )

        # Load structured memory (handles encrypted, plaintext, or missing)
        if self.structured_memory_path.exists():
            raw = self.structured_memory_path.read_bytes()
            loaded = False

            # Try decrypting first (encrypted file)
            if self._fernet and raw:
                try:
                    decrypted = self._fernet.decrypt(raw)
                    self.structured_memory = json.loads(decrypted)
                    loaded = True
                except Exception:
                    pass  # Not encrypted yet — fall through to plaintext

            # Try plaintext JSON (legacy / migration path)
            if not loaded:
                try:
                    self.structured_memory = json.loads(raw)
                    loaded = True
                    # Re-save encrypted to migrate the file
                    if self._fernet:
                        self._save_structured_memory()
                        logger.info("Migrated plaintext memory.json to encrypted format")
                except (json.JSONDecodeError, UnicodeDecodeError):
                    logger.warning("Could not read memory.json — starting fresh")

            if not loaded:
                self.structured_memory = {}
                self._save_structured_memory()
        else:
            self.structured_memory = {}
            self._save_structured_memory()

        logger.info("Memory systems initialized")

    async def store(self, user_id: str, content: str, metadata: Optional[Dict] = None):
        """Store a memory"""
        memory_id = f"{user_id}_{datetime.now().timestamp()}"

        # Store in vector DB for semantic search
        self.collection.add(
            ids=[memory_id],
            documents=[content],
            metadatas=[
                {"user_id": user_id, "timestamp": datetime.now().isoformat(), **(metadata or {})}
            ],
        )

        # Store in structured memory
        if user_id not in self.structured_memory:
            self.structured_memory[user_id] = {
                "preferences": {},
                "interactions": [],
                "metadata": {},
            }

        self.structured_memory[user_id]["interactions"].append(
            {
                "id": memory_id,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {},
            }
        )

        # Limit interactions to prevent bloat
        max_interactions = 100
        if len(self.structured_memory[user_id]["interactions"]) > max_interactions:
            self.structured_memory[user_id]["interactions"] = self.structured_memory[user_id][
                "interactions"
            ][-max_interactions:]

        self._save_structured_memory()
        logger.debug(f"Stored memory for user {user_id}")

    async def recall(self, user_id: str, query: str, n_results: int = 5) -> List[Dict]:
        """Recall relevant memories using semantic search"""
        try:
            results = self.collection.query(
                query_texts=[query], n_results=n_results, where={"user_id": user_id}
            )

            memories = []
            if results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    memories.append(
                        {
                            "content": doc,
                            "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                            "distance": (
                                results["distances"][0][i] if results.get("distances") else None
                            ),
                        }
                    )

            return memories
        except Exception as e:
            logger.error(f"Failed to recall memories: {e}")
            return []

    async def get_user_preferences(self, user_id: str) -> Dict:
        """Get user preferences"""
        if user_id in self.structured_memory:
            return self.structured_memory[user_id].get("preferences", {})
        return {}

    async def set_user_preference(self, user_id: str, key: str, value: Any):
        """Set a user preference"""
        if user_id not in self.structured_memory:
            self.structured_memory[user_id] = {
                "preferences": {},
                "interactions": [],
                "metadata": {},
            }

        self.structured_memory[user_id]["preferences"][key] = value
        self._save_structured_memory()

    async def cleanup_old_memories(self):
        """Remove memories older than retention period"""
        cutoff_date = datetime.now() - timedelta(days=self.config.memory_retention_days)

        for user_id in list(self.structured_memory.keys()):
            interactions = self.structured_memory[user_id]["interactions"]
            filtered = [
                i for i in interactions if datetime.fromisoformat(i["timestamp"]) > cutoff_date
            ]
            self.structured_memory[user_id]["interactions"] = filtered

        self._save_structured_memory()
        logger.info(f"Cleaned up memories older than {self.config.memory_retention_days} days")

    def _save_structured_memory(self):
        """Save structured memory to disk (encrypted if cryptography is available)."""
        self.structured_memory_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.structured_memory, indent=2).encode()
        if self._fernet:
            payload = self._fernet.encrypt(payload)
        self.structured_memory_path.write_bytes(payload)

    async def close(self):
        """Cleanup on shutdown"""
        self._save_structured_memory()
        logger.info("Memory manager closed")
