"""
Circuit breaker – tracks failure rate and opens circuit when threshold exceeded.
"""

import time
from collections import deque


class CircuitBreaker:
    def __init__(self, config):
        self.threshold = config["circuit_breaker"]["failure_threshold"]
        self.cooldown = config["circuit_breaker"]["cooldown_minutes"] * 60
        self.failures = deque(maxlen=100)
        self.state = "closed"
        self.last_failure = 0

    def record_failure(self):
        self.failures.append(time.time())
        self.last_failure = time.time()
        self._update_state()

    def record_success(self):
        self.failures.append(time.time())
        self._update_state()

    def _update_state(self):
        now = time.time()
        recent_failures = [t for t in self.failures if now - t < 60]
        if len(recent_failures) / 100 >= self.threshold:
            self.state = "open"
        elif self.state == "open" and now - self.last_failure > self.cooldown:
            self.state = "half_open"

    def is_open(self) -> bool:
        return self.state == "open"