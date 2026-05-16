"""
RAG Client with spell correction, timeout, failure handling, and query rewriting.
"""

import httpx
import logging
import asyncio
from symspellpy import SymSpell
import os

logger = logging.getLogger(__name__)

class RagClient:
    def __init__(self, config):
        self.base_url = config["rag"]["url"]
        self.timeout = config["rag"]["timeout"]
        self.top_k = config["rag"]["top_k"]
        self.min_confidence = config["rag"]["min_confidence"]
        self.sym_spell = SymSpell(max_dictionary_edit_distance=2, prefix_length=7)
        dict_path = "data/spell_dict.txt"
        if os.path.exists(dict_path):
            self.sym_spell.load_dictionary(dict_path, term_index=0, count_index=1)
        self.llama = None  # will be set later by orchestrator

    def _correct_spelling(self, query: str) -> str:
        suggestions = self.sym_spell.lookup(query, verbosity=2, max_edit_distance=2)
        if suggestions and suggestions[0].distance <= 1:
            return suggestions[0].term
        return query

    async def rewrite_query_for_rag(self, user_message: str, memory: dict) -> str:
        """Rewrite the query to include conversation context for better RAG retrieval."""
        history = memory.get('interaction_history', [])
        if len(history) < 2:
            return user_message

        recent = history[-4:]
        history_str = '\n'.join(
            f"{m['role'].upper()}: {m['content']}" for m in recent
        )

        # FIXED: Strict prompt to prevent hallucinations
        prompt = f"""
Given this conversation and the new user message, rewrite the message as a
standalone search query that includes all necessary context.

**Important:** Do NOT add words like "polyclinic", "hospital", "clinic", or any other unrelated terms unless they appear in the conversation. Keep the query factual and directly related to the topic.

Conversation:
{history_str}

New message: {user_message}

Standalone search query (one sentence, include the topic and service name, be concise):
"""
        if not self.llama:
            logger.warning("No LLM for query rewriting, using original")
            return user_message
        rewritten = await self.llama._call_llm(
            [{"role": "user", "content": prompt}], max_tokens=60
        )
        if rewritten:
            logger.info(f"Rewritten query: {rewritten}")
            return rewritten.strip()
        return user_message

    async def query(self, user_message: str, memory: dict = None, location: str = None, context: str = "") -> dict:
        if memory and self.llama:
            search_query = await self.rewrite_query_for_rag(user_message, memory)
        else:
            search_query = user_message

        corrected = self._correct_spelling(search_query)
        if corrected != search_query:
            logger.info(f"Spell corrected: '{search_query}' -> '{corrected}'")
            search_query = corrected

        # Use a lower threshold so weaker‑scoring chunks (like the billing formula)
        # are still included. The gateway's keyword booster will re‑rank them.
        payload = {
            "query": search_query,
            "top_k": self.top_k,
            "threshold": 0.15,           # <-- lowered from 0.3
            "conversation_context": context,
            "context": {"location": {"suburb": location} if location else None}
        }
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.post(f"{self.base_url}/api/v1/query", json=payload)
                if resp.status_code == 200:
                    data = resp.json()
                    if "evidence" not in data:
                        data["evidence"] = []
                    if "sources" not in data:
                        data["sources"] = []
                    data.setdefault("confidence", 0.0)
                    data.setdefault("has_knowledge_gap", False)
                    return data
                else:
                    logger.warning(f"RAG returned {resp.status_code}")
                    return {"error": "rag_error", "has_knowledge_gap": True}
        except httpx.TimeoutException:
            logger.error("RAG query timed out")
            return {"error": "timeout", "has_knowledge_gap": True}
        except Exception as e:
            logger.error(f"RAG query failed: {e}")
            return {"error": str(e), "has_knowledge_gap": True}