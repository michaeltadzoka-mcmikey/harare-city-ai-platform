"""
Contradiction Handler for Harare Chatbot Gateway v5.3
Detects and resolves conflicts between documents using precedence engine
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class ContradictionHandler:
    """
    Detects and resolves contradictions between retrieved documents.

    Uses precedence engine for deterministic conflict resolution.
    """

    def __init__(self, precedence_engine):
        self.precedence_engine = precedence_engine
        logger.info("Contradiction Handler initialized")

    def detect_contradictions(
        self,
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Detect contradictions between documents.

        Documents contradict if they:
        1. Have overlapping scope (same department, location, topic)
        2. Provide conflicting information on the same subject

        Args:
            documents: List of retrieved documents

        Returns:
            List of detected contradictions
        """
        contradictions = []

        # Compare each pair of documents
        for i, doc_a in enumerate(documents):
            for doc_b in documents[i+1:]:
                # Check for potential contradiction
                if self._potentially_contradicts(doc_a, doc_b):
                    # For same-type documents, verify scope overlap
                    if doc_a.get("content_type") == doc_b.get("content_type"):
                        if not self.precedence_engine.scope_overlap(doc_a, doc_b):
                            # No scope overlap, so not a contradiction
                            continue

                    contradiction = {
                        "doc_a_id": doc_a.get("id"),
                        "doc_a_title": doc_a.get("title", "Unknown"),
                        "doc_a_type": doc_a.get("content_type", "unknown"),
                        "doc_b_id": doc_b.get("id"),
                        "doc_b_title": doc_b.get("title", "Unknown"),
                        "doc_b_type": doc_b.get("content_type", "unknown"),
                        "scope_overlap": self.precedence_engine.scope_overlap(doc_a, doc_b),
                        "detected_at": datetime.utcnow().isoformat()
                    }
                    contradictions.append(contradiction)

                    logger.info(
                        f"Contradiction detected: {doc_a.get('title')} vs {doc_b.get('title')}"
                    )

        return contradictions

    def resolve_contradictions(
        self,
        documents: List[Dict[str, Any]],
        contradictions: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Resolve contradictions using precedence engine.

        Args:
            documents: List of documents
            contradictions: List of detected contradictions

        Returns:
            Tuple of (winning_documents, losing_documents)
        """
        if not contradictions:
            return documents, []

        # Track which documents to keep
        doc_ids_to_keep = set(doc.get("id") for doc in documents)
        doc_ids_to_remove = set()

        # Resolution log
        resolutions = []

        # Resolve each contradiction
        for contradiction in contradictions:
            doc_a_id = contradiction["doc_a_id"]
            doc_b_id = contradiction["doc_b_id"]

            # Find the documents
            doc_a = next((d for d in documents if d.get("id") == doc_a_id), None)
            doc_b = next((d for d in documents if d.get("id") == doc_b_id), None)

            if not doc_a or not doc_b:
                continue

            # Use precedence engine to resolve
            winner, resolution_method = self.precedence_engine.resolve_conflict(doc_a, doc_b)

            if resolution_method == "no_conflict_different_scopes":
                # Not actually a conflict - keep both
                continue

            # Determine loser
            loser = doc_b if winner == doc_a else doc_a
            loser_id = loser.get("id")

            # Mark for removal
            if loser_id not in doc_ids_to_remove:
                doc_ids_to_remove.add(loser_id)

                resolutions.append({
                    "winner_id": winner.get("id"),
                    "winner_title": winner.get("title"),
                    "loser_id": loser_id,
                    "loser_title": loser.get("title"),
                    "resolution_method": resolution_method,
                    "scope_overlap": contradiction.get("scope_overlap", True)
                })

                logger.info(
                    f"Resolved: {winner.get('title')} wins over {loser.get('title')} "
                    f"(method: {resolution_method}, scope_overlap: {contradiction.get('scope_overlap', True)})"
                )

        # Filter documents
        winning_docs = [
            doc for doc in documents
            if doc.get("id") not in doc_ids_to_remove
        ]

        losing_docs = [
            doc for doc in documents
            if doc.get("id") in doc_ids_to_remove
        ]

        # Add resolution metadata to contradictions
        for contradiction in contradictions:
            resolution = next(
                (r for r in resolutions
                 if r["winner_id"] == contradiction["doc_a_id"]
                 or r["winner_id"] == contradiction["doc_b_id"]),
                None
            )
            if resolution:
                contradiction.update({
                    "resolved": True,
                    "winner_id": resolution["winner_id"],
                    "winner_title": resolution["winner_title"],
                    "resolution_method": resolution["resolution_method"]
                })

        return winning_docs, losing_docs

    def _potentially_contradicts(
        self,
        doc_a: Dict[str, Any],
        doc_b: Dict[str, Any]
    ) -> bool:
        """
        Check if two documents potentially contradict.

        Simple heuristic: same content_type OR overlapping topic_tags
        """
        # Same type documents may contradict (scope overlap will be checked later)
        if doc_a.get("content_type") == doc_b.get("content_type"):
            return True

        # Check topic overlap
        topics_a = set(doc_a.get("topic_tags", []))
        topics_b = set(doc_b.get("topic_tags", []))

        if topics_a and topics_b and topics_a.intersection(topics_b):
            return True

        return False

    def generate_disclosure_text(
        self,
        contradictions: List[Dict[str, Any]],
        max_show: int = 2
    ) -> str:
        """
        Generate contradiction disclosure text for response.

        Args:
            contradictions: Resolved contradictions
            max_show: Maximum contradictions to display

        Returns:
            Disclosure text
        """
        if not contradictions:
            return ""

        resolved = [c for c in contradictions if c.get("resolved")]

        if not resolved:
            return ""

        disclosure_parts = []

        for contradiction in resolved[:max_show]:
            winner_title = contradiction.get("winner_title", "the latest document")
            loser_title = contradiction.get("loser_title", "an older document")
            method = contradiction.get("resolution_method", "precedence")

            if method == "precedence":
                text = (
                    f"\n\n**Note:** Multiple documents found. "
                    f"Using the higher-authority source: {winner_title}."
                )
            elif method == "newer_version":
                text = (
                    f"\n\n**Note:** {loser_title} has been superseded by "
                    f"{winner_title}."
                )
            elif method == "version_number":
                text = (
                    f"\n\n**Note:** Using the latest version: {winner_title}."
                )
            elif method == "authority_confidence":
                text = (
                    f"\n\n**Note:** Using the most authoritative source: "
                    f"{winner_title}."
                )
            else:
                text = (
                    f"\n\n**Note:** Conflicting information resolved in favour of "
                    f"{winner_title}."
                )

            disclosure_parts.append(text)

        if len(resolved) > max_show:
            disclosure_parts.append(
                f"\n\n**Note:** {len(resolved) - max_show} additional conflict(s) "
                f"were also resolved."
            )

        return "".join(disclosure_parts)

# Global instance will be created when precedence_engine is available
contradiction_handler = None