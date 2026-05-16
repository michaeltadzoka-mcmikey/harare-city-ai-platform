"""
Explainability module – generates source citations.
"""

import logging
from typing import List, Dict
from .llama_client import LlamaClient

logger = logging.getLogger(__name__)

class ExplainabilityGenerator:
    """Generates a one-sentence explanation of sources."""
    
    def __init__(self, llama: LlamaClient):
        self.llama = llama
    
    async def generate(self, sources: List[Dict]) -> str:
        """Return a string like 'This information comes from ...'."""
        if not sources:
            return ""
        # Try LLM first
        explanation = await self.llama.generate_explanation(sources)
        if explanation:
            return explanation
        # Fallback to simple template
        titles = []
        for s in sources[:2]:
            title = s.get("title", "Unknown")
            date = s.get("valid_from", "")[:10] if s.get("valid_from") else ""
            if date:
                titles.append(f"{title} ({date})")
            else:
                titles.append(title)
        if len(sources) > 2:
            titles.append(f"and {len(sources)-2} more")
        return f"This information comes from {', '.join(titles)}."