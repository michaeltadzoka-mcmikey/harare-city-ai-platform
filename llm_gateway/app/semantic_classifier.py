"""
Hybrid intent classifier: LLM-first with embedding fallback.
Uses intent descriptions instead of example lists.
"""

import logging
import json
import re
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class SemanticClassifier:
    INTENT_DESCRIPTIONS = {
        'knowledge_query': (
            'User wants to know facts about a Harare council service, process, fee, rule, '
            'requirement, contact, location, or policy. Examples: asking how to apply, '
            'what something costs, where an office is, how long something takes. '
            'This does NOT include asking what the bot can do or how it works.'
        ),
        'report_intent': (
            'User wants to report a problem or fault. Includes: potholes, burst pipes, '
            'no water, power outage, uncollected waste, broken streetlights, flooding, '
            'any infrastructure issue. Language can be formal or very informal.'
        ),
        'check_report_status': (
            'User wants to know the status of a previously submitted report or complaint.'
        ),
        'chitchat': (
            'Greeting, thanks, small talk, testing the bot, asking what it can do, '
            'asking for help, asking about its capabilities, asking if it is intelligent, '
            'personal questions about the bot. '
            '**Key phrases**: "what can you do", "what services", "help", "what do you know", '
            '"tell me about yourself", "who are you", "can you help me with anything". '
            'Treat any question about the bot itself as chitchat.'
        ),
        'provide_information': (
            'User is giving the bot information it asked for: their name, address, '
            'reference number, contact details, confirmation of a step.'
        ),
        'complaint': (
            'User is expressing frustration, dissatisfaction, or escalating an issue '
            'beyond a simple report. Includes mentions of council staff behaviour.'
        ),
    }

    # Explicit patterns for capability questions (to force chitchat)
    CAPABILITY_PATTERNS = [
        r"\bwhat can you do\b",
        r"\bwhat services\b",
        r"\bwhat do you know\b",
        r"\bhow can you help\b",
        r"\btell me about yourself\b",
        r"\bwho are you\b",
        r"\bwhat is your purpose\b",
        r"\bwhat are you capable of\b",
    ]

    def __init__(self, llama_client, embedding_generator, config):
        self.llama = llama_client
        self.embedding = embedding_generator
        self.config = config

    async def classify(self, message: str, context: str = None) -> Dict[str, Any]:
        """Return intent, confidence, source."""
        # Force chitchat for capability questions
        msg_lower = message.lower()
        for pattern in self.CAPABILITY_PATTERNS:
            if re.search(pattern, msg_lower):
                logger.info(f"Capability pattern matched -> forced chitchat")
                return {"intent": "chitchat", "confidence": 0.99, "source": "forced"}

        desc_str = '\n'.join(
            f'{k}: {v}' for k, v in self.INTENT_DESCRIPTIONS.items()
        )
        prompt = f"""
You are classifying a message from a Harare city council citizen chatbot.

Choose the single best intent from this list:
{desc_str}

**Important:** If the user asks about what the bot can do, or asks for help (e.g., "what can you do", "help", "what services"), the intent is chitchat.

Conversation context: {context or 'None'}
Citizen message: {message}

Return only the intent name, nothing else.
"""
        try:
            result = await self.llama._call_llm(
                [{"role": "user", "content": prompt}],
                max_tokens=10, temperature=0.0
            )
            intent = result.strip().lower()
            if intent in self.INTENT_DESCRIPTIONS:
                logger.info(f"LLM intent classification: {intent}")
                return {"intent": intent, "confidence": 0.95, "source": "llm"}
        except Exception as e:
            logger.warning(f"LLM intent classification failed: {e}")

        # Fallback: embedding-based classification
        if self.embedding and self.embedding.model:
            try:
                msg_emb = self.embedding.encode(message)
                if msg_emb is not None:
                    best_intent = "knowledge_query"
                    best_score = 0.0
                    for intent, desc in self.INTENT_DESCRIPTIONS.items():
                        desc_emb = self.embedding.encode(desc)
                        if desc_emb is not None:
                            sim = self.embedding.similarity(msg_emb[0], desc_emb[0])
                            if sim > best_score:
                                best_score = sim
                                best_intent = intent
                    if best_score > 0.7:
                        logger.info(f"Embedding fallback intent: {best_intent} (score {best_score:.2f})")
                        return {"intent": best_intent, "confidence": best_score, "source": "embedding"}
            except Exception as e:
                logger.warning(f"Embedding fallback failed: {e}")

        # Ultimate fallback
        logger.warning("Intent classification failed, defaulting to knowledge_query")
        return {"intent": "knowledge_query", "confidence": 0.5, "source": "fallback"}