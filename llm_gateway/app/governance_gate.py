"""
Governance gate – blocks out‑of‑scope and custom blocklisted content.
"""

import logging

logger = logging.getLogger(__name__)


class GovernanceGate:
    def __init__(self, config):
        self.blocklist = set()
        self._load_blocklist(config["governance"].get("blocklist_path", "config/blocklist.txt"))

    def _load_blocklist(self, path):
        try:
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        self.blocklist.add(line.lower())
        except Exception as e:
            logger.warning(f"Could not load blocklist: {e}")

    def check(self, message: str) -> str:
        if any(phrase in message.lower() for phrase in self.blocklist):
            return "I cannot answer that. Please contact the council directly for assistance."
        return None