"""
Intent Analyzer – uses LLM few-shot classification with embedding fallback.
"""

import logging
import numpy as np
from typing import Dict, Any, Optional, List
from .llama_client import LlamaClient
from .embedding_utils import EmbeddingGenerator

logger = logging.getLogger(__name__)

class EnhancedIntentAnalyzer:
    """Uses LLM for intent classification with embedding-based fallback."""

    def __init__(self, llama_client: LlamaClient, embedding_generator: EmbeddingGenerator):
        self.llama = llama_client
        self.embedding_generator = embedding_generator

        # Pre‑compute embeddings for example queries
        self.example_queries = {
            "knowledge_query": [
                "How do I pay my water bill?",
                "Where can I pay my water bill?",
                "I want to settle my water account",
                "Tell me how to pay for water",
                "What are the water payment options?",
                "What is the water connection fee?",
                "How do I apply for a business permit?",
                "What are the clinic hours?",
            ],
            "report_intent": [
                "I want to report a pothole",
                "There is a leaking pipe",
                "I need to report illegal dumping",
                "How can I lodge a complaint about garbage?",
                "Report a burst water pipe",
                "There's a broken street light",
            ],
            "status_check": [
                "HCC-RPT-2026-01452",
                "Check my report status",
                "What's the status of my report?",
                "Track my report",
                "Follow up on my report",
            ],
            "chitchat": [
                "hi", "hello", "hey", "good morning", "good afternoon", "good evening",
                "how are you", "what's up", "howdy", "bye", "goodbye", "thank you", "thanks",
                "what can you do", "who are you", "how old are you", "who made you",
            ],
            "other": [
                "tell me a joke",
                "what's the weather",
                "I like pizza",
                "what is the meaning of life",
            ]
        }

        # Pre‑compute embeddings for all examples
        self.example_embeddings = {}
        if self.embedding_generator.model is not None:
            for intent, queries in self.example_queries.items():
                embeddings = self.embedding_generator.encode(queries)
                if embeddings is not None:
                    self.example_embeddings[intent] = embeddings
                else:
                    self.example_embeddings[intent] = None
        else:
            self.example_embeddings = None
            logger.warning("Embedding generator not available, fallback disabled")

    async def analyze(self, message: str, context: Optional[Dict] = None) -> Dict[str, Any]:
        """Return intent analysis with confidence, using LLM first then embedding fallback."""
        # First try LLM
        result = await self.llama.classify_intent(message)
        intent = result["intent"]
        confidence = result["confidence"]

        # If LLM confidence is low or result is invalid, use embedding fallback
        if confidence < 0.7 or intent not in self.example_queries.keys():
            logger.info(f"LLM intent low confidence ({confidence}), trying embedding fallback")
            if self.embedding_generator.model is not None and self.example_embeddings is not None:
                msg_emb = self.embedding_generator.encode(message)
                if msg_emb is not None:
                    best_intent = None
                    best_score = 0.0
                    for intent_name, emb_list in self.example_embeddings.items():
                        if emb_list is None:
                            continue
                        # Compute max similarity with all examples of this intent
                        scores = [self.embedding_generator.similarity(msg_emb[0], ex_emb) for ex_emb in emb_list]
                        max_score = max(scores) if scores else 0
                        if max_score > best_score:
                            best_score = max_score
                            best_intent = intent_name
                    if best_score > 0.75:  # threshold
                        logger.info(f"Embedding fallback selected intent {best_intent} with score {best_score:.2f}")
                        intent = best_intent
                        confidence = best_score
                    else:
                        logger.info(f"Embedding fallback score too low ({best_score:.2f}), keeping LLM result")

        # Add fields expected by main.py
        return {
            "primary_intent": intent,
            "confidence": confidence,
            "secondary_intents": [],
            "emotional_tone": "neutral",
            "urgency_level": 2,
            "requires_clarification": False,
            "clarification_question": None,
            "extracted_entities": {},
            "matched_keywords": [],
            "requires_action": False,
            "is_follow_up": False,
            "context_used": bool(context)
        }

# Global instance will be created in main.py with llama_client and embedding_generator
intent_analyzer = None