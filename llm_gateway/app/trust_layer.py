"""
Trust layer – simplified for citizen-friendly responses.
No source attribution or confidence badges - citizens don't need them.
"""

import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

class TrustLayer:
    """Simplified trust layer that returns answers as-is."""
    
    def apply_source_attribution(self, answer: str, sources: list) -> str:
        """
        Return answer without source attribution.
        Citizens don't need to see document IDs or department names.
        """
        return answer

    def apply_trust_layer(self, answer: str, confidence: float) -> str:
        """
        Return answer without confidence badges.
        No emojis or verification messages needed.
        """
        return answer
    
    def validate_answer(self, answer: str, sources: List[Dict]) -> bool:
        """Simple validation - just check if answer exists."""
        return bool(answer and len(answer.strip()) > 10)


# Global instance
trust_layer = TrustLayer()