"""
Simple in‑memory cache with TTL.
"""

import time


class Cache:
    def __init__(self, config):
        self.ttl = config.get("cache_ttl", 300)
        self.store = {}

    async def get(self, key: str):
        entry = self.store.get(key)
        if entry and entry["expires"] > time.time():
            return entry["value"]
        return None

    async def set(self, key: str, value: str, ttl: int = None):
        ttl = ttl or self.ttl
        self.store[key] = {"value": value, "expires": time.time() + ttl}