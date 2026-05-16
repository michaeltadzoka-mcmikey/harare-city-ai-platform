"""
Query Type Classifier for Harare City Council LLM Gateway v5.5
Classifies knowledge queries into factual, policy, procedural, eligibility.
"""

import logging
from typing import Optional
from .llama_client import LlamaClient

logger = logging.getLogger(__name__)

class QueryTypeClassifier:
    """Uses LLM to classify query type, with rule-based fallback."""
    
    def __init__(self, llama_client: LlamaClient):
        self.llama = llama_client
    
    async def classify(self, message: str) -> str:
        """Return one of: factual, policy, procedural, eligibility, other."""
        return await self.llama.classify_query_type(message)