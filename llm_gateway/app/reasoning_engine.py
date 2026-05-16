"""
Enhanced reasoning engine with chain-of-thought support.
"""

import logging
from typing import List, Dict, Any
from .llama_client import LlamaClient
from .rag_client import RagClient

logger = logging.getLogger(__name__)

class ReasoningEngine:
    """Handles multi-step reasoning and chain-of-thought."""

    def __init__(self, llama: LlamaClient, rag: RagClient):
        self.llama = llama
        self.rag = rag

    async def chain_of_thought(self, question: str, context: str = "") -> Dict[str, Any]:
        """
        Perform chain-of-thought reasoning:
        1. Generate reasoning steps.
        2. For steps that require facts, retrieve from RAG.
        3. Synthesize final answer.
        """
        # Step 1: Generate reasoning steps
        steps_text = await self.llama.chain_of_thought_reasoning(question, context)
        # The LLM may output steps and then an answer; we'll parse it.
        # For simplicity, we assume the answer is after "Now provide the final answer:".
        # We'll split on that marker.
        if "final answer:" in steps_text.lower():
            parts = steps_text.lower().split("final answer:", 1)
            reasoning = parts[0]
            answer = parts[1].strip()
        else:
            reasoning = steps_text
            answer = steps_text  # fallback

        # Step 2: Extract any sub-questions that need retrieval
        # For now, we don't parse steps; we just return the generated answer.
        # In a more advanced version, we'd extract sub-questions and call RAG.

        return {
            "answer": answer,
            "reasoning": reasoning,
            "sources": []  # Could add sources if we retrieved
        }