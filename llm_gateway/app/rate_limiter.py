"""
Rate limiter – per‑session sliding window.
"""

import time
from collections import defaultdict


class RateLimiter:
    def __init__(self, config):
        self.limit = config["limits"]["requests_per_minute"]
        self.window = 60
        self.records = defaultdict(list)

    def allow(self, key: str) -> bool:
        now = time.time()
        self.records[key] = [t for t in self.records[key] if now - t < self.window]
        if len(self.records[key]) >= self.limit:
            return False
        self.records[key].append(now)
        return True