"""
Reasoning Engine for Harare City Council LLM Gateway v5.5
Provides multi-step and chain-of-thought reasoning for complex queries.
"""

import logging
import json
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ReasoningEngine:
    """
    Handles advanced reasoning for complex questions:
    - Multi-step reasoning: breaks question into sub-questions, retrieves answers, synthesizes.
    - Chain-of-thought reasoning: generates step-by-step reasoning trace and final answer.
    """

    def __init__(self, llama_client, rag_client):
        self.llama = llama_client
        self.rag = rag_client
        logger.info("Reasoning Engine initialized")

    async def reason(self, question: str, context: str = "") -> Dict[str, Any]:
        """
        Multi-step reasoning:
        1. Break question into sub-questions.
        2. Retrieve answer for each sub-question (using RAG).
        3. Synthesize final answer.
        """
        # Step 1: Analyse – break into sub-questions
        sub_questions = await self.llama.analyse_question(question)
        if not sub_questions or sub_questions == [question]:
            # Fallback to single RAG query
            logger.info("No sub-questions generated, using single RAG query")
            rag_response = await self.rag.query(question, context=context)
            return {
                "answer": rag_response.get("answer", ""),
                "sources": rag_response.get("sources", []),
                "sub_answers": []
            }

        logger.info(f"Multi-step: broke into {len(sub_questions)} sub-questions: {sub_questions}")

        # Step 2: Retrieve answers for each sub-question
        sub_answers = []
        all_sources = []
        for i, sq in enumerate(sub_questions):
            logger.info(f"Retrieving for sub-question {i+1}: {sq}")
            rag_response = await self.rag.query(sq, context=context)
            answer_text = rag_response.get("answer", "No information found.")
            sub_answers.append(f"Q{i+1}: {sq}\nA: {answer_text}")
            all_sources.extend(rag_response.get("sources", []))

        # Step 3: Synthesize final answer from sub-answers
        synthesized = await self.llama.synthesise_answers(sub_answers)
        if not synthesized:
            # Fallback: just join them
            synthesized = "\n\n".join(sub_answers)

        return {
            "answer": synthesized,
            "sources": all_sources,
            "sub_answers": sub_answers
        }

    async def chain_of_thought(self, question: str, context: str = "") -> Dict[str, Any]:
        """
        Chain-of-thought reasoning:
        1. Generate step-by-step reasoning trace using LLM.
        2. Extract final answer from the trace.
        3. (Optional) Retrieve additional facts if needed.
        """
        # Step 1: Generate reasoning trace
        reasoning_trace = await self.llama.chain_of_thought_reasoning(question, context)

        # Step 2: Parse the trace to extract the final answer.
        # Look for markers like "Final answer:", "Answer:", etc.
        answer = ""
        reasoning = reasoning_trace

        markers = ["Final answer:", "Answer:", "Therefore,", "In conclusion,"]
        lower_trace = reasoning_trace.lower()
        for marker in markers:
            pos = lower_trace.find(marker.lower())
            if pos != -1:
                # Extract from that point to the end
                answer = reasoning_trace[pos + len(marker):].strip()
                # Remove the marker from reasoning if we want to keep trace separate
                reasoning = reasoning_trace[:pos].strip()
                break

        if not answer:
            # If no marker, assume the whole trace is the answer
            answer = reasoning_trace
            reasoning = ""

        # Step 3: If answer is empty, fallback to simple RAG
        if not answer:
            logger.warning("Chain-of-thought produced no answer, falling back to RAG")
            rag_response = await self.rag.query(question, context=context)
            answer = rag_response.get("answer", "")
            sources = rag_response.get("sources", [])
        else:
            # Optionally, we could retrieve sources based on the reasoning,
            # but for simplicity we return empty sources for now.
            sources = []

        return {
            "answer": answer,
            "reasoning": reasoning,
            "sources": sources
        }

    async def decompose_and_retrieve(self, question: str, context: str = "") -> List[Dict[str, Any]]:
        """Decompose a complex question into sub-questions and retrieve documents for each."""
        sub_questions = await self.llama.analyse_question(question)
        if not sub_questions:
            return []

        all_docs = []
        seen_ids = set()
        for sq in sub_questions:
            rag_response = await self.rag.query(sq, context=context)
            for doc in rag_response.get("sources", []):
                doc_id = doc.get("id")
                if doc_id and doc_id not in seen_ids:
                    seen_ids.add(doc_id)
                    all_docs.append(doc)
        return all_docs

    async def verify_and_refine(self, question: str, answer: str, sources: List[Dict]) -> Dict[str, Any]:
        """Use self-critique to verify answer completeness and refine if needed."""
        verification = await self.llama.verify_answer(question, answer, sources)
        if verification.get("complete", True):
            return {"answer": answer, "sources": sources, "needs_more": False}

        missing = verification.get("missing_info", [])
        if missing:
            logger.info(f"Answer incomplete, missing: {missing}")
            return {
                "answer": answer + f"\n\nI'm missing information about: {', '.join(missing[:2])}. Could you provide more details?",
                "sources": sources,
                "needs_more": True,
                "missing_info": missing
            }
        return {"answer": answer, "sources": sources, "needs_more": False}