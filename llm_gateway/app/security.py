"""
Security gate for prompt injection and out‑of‑scope topics.
"""

import re
import logging

logger = logging.getLogger(__name__)


class SecurityGate:
    def __init__(self, config):
        self.blocklist = set()
        self.out_of_scope = config["governance"].get("out_of_scope_keywords", ["politics", "election", "president", "religion"])
        self._load_blocklist(config["governance"].get("blocklist_path", "config/blocklist.txt"))

        self.injection_patterns = [
            r"ignore (previous|all|above) instructions?",
            r"disregard (previous|all|above) instructions?",
            r"you are now",
            r"act as",
            r"pretend (you are|to be)",
            r"new instructions?:",
            r"system:",
            r"assistant:"
        ]
        self.compiled = [re.compile(p, re.IGNORECASE) for p in self.injection_patterns]

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
        # Prompt injection
        for pattern in self.compiled:
            if pattern.search(message):
                logger.warning(f"Injection attempt: {message[:100]}")
                return "I'm sorry, I can't process that request. Please rephrase your question."

        # Out‑of‑scope keywords
        if any(kw in message.lower() for kw in self.out_of_scope):
            return "I'm here to help with Harare City Council services only. For other topics, please contact the relevant authority."

        # Custom blocklist
        if any(phrase in message.lower() for phrase in self.blocklist):
            return "I cannot answer that. Please contact the council directly for assistance."

        return None