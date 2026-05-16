"""
Enhanced user memory with semantic retrieval, confidence scoring, and privacy controls.
"""

import json
import os
import logging
from datetime import datetime
from sentence_transformers import SentenceTransformer
import numpy as np

logger = logging.getLogger(__name__)


class UserMemory:
    def __init__(self, config):
        self.storage_path = "data/user_profiles.json"
        self.profiles = self._load()
        self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
        self.memory_vectors = {}  # user_id -> list of (embedding, fact_dict)

    def _load(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def _save(self):
        with open(self.storage_path, 'w') as f:
            json.dump(self.profiles, f, indent=2)

    def get_profile(self, user_id: str) -> dict:
        return self.profiles.get(user_id, {})

    def merge_facts(self, user_id: str, facts: dict):
        profile = self.profiles.get(user_id, {})
        current_facts = profile.get("user_facts", {})
        # Add confidence tracking
        for key, value in facts.items():
            current_facts[key] = {
                "value": value,
                "confidence": 0.6 if key in ["name", "location"] else 0.3,
                "last_confirmed": datetime.utcnow().isoformat()
            }
        profile["user_facts"] = current_facts
        profile["last_seen"] = datetime.utcnow().isoformat()
        self.profiles[user_id] = profile
        self._save()
        # Update vector store
        for key, val_dict in current_facts.items():
            text = f"{key}: {val_dict['value']}"
            emb = self.embedder.encode(text)
            self.memory_vectors.setdefault(user_id, []).append((emb, {"fact": key, "value": val_dict['value']}))

    def search_similar(self, user_id: str, query: str, top_k: int = 2) -> list:
        if user_id not in self.memory_vectors:
            return []
        query_emb = self.embedder.encode(query)
        similarities = []
        for emb, mem in self.memory_vectors[user_id]:
            sim = np.dot(query_emb, emb) / (np.linalg.norm(query_emb) * np.linalg.norm(emb) + 1e-8)
            similarities.append((sim, mem))
        similarities.sort(key=lambda x: x[0], reverse=True)
        return [mem for sim, mem in similarities[:top_k]]

    def prune_memory(self, user_id: str, max_age_days: int = 30, min_confidence: float = 0.3):
        if user_id not in self.profiles:
            return
        facts = self.profiles[user_id].get("user_facts", {})
        now = datetime.utcnow()
        to_remove = []
        for key, val_dict in facts.items():
            if isinstance(val_dict, dict):
                age = (now - datetime.fromisoformat(val_dict.get("last_confirmed", now.isoformat()))).days
                if age > max_age_days and val_dict.get("confidence", 0.5) < min_confidence:
                    to_remove.append(key)
        for key in to_remove:
            del facts[key]
        self.profiles[user_id]["user_facts"] = facts
        self._save()
        if user_id in self.memory_vectors:
            self.memory_vectors[user_id] = [(emb, mem) for emb, mem in self.memory_vectors[user_id] if mem["fact"] not in to_remove]