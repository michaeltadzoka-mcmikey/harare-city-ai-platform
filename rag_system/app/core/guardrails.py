"""
Domain Guardrails - Ensures RAG only returns Harare municipal content
"""
import re
from typing import List, Dict, Tuple, Any

class DomainGuardrails:
    """Ensures RAG only returns Harare municipal content."""

    HARARE_REQUIRED_TERMS = [
        "harare", "city of harare", "harare city", "harare municipal",
        "harare council", "zimbabwe", "local authority", "city council"
    ]

    SERVICE_CATEGORIES = {
        "business": ["business", "permit", "license", "registration", "company", "enterprise"],
        "infrastructure": ["water", "electricity", "road", "street", "pothole", "drainage", "sewage"],
        "waste": ["waste", "garbage", "rubbish", "collection", "refuse", "recycling"],
        "health": ["clinic", "hospital", "health", "sanitation", "hygiene", "cleanliness"],
        "housing": ["housing", "property", "rates", "valuation", "building", "construction"],
        "transport": ["transport", "bus", "taxi", "zupco", "traffic", "parking"],
        "finance": ["bill", "payment", "fee", "charge", "rate", "tax", "revenue"],
        "governance": ["bylaw", "regulation", "policy", "procedure", "requirement", "standard"]
    }

    NON_DOMAIN_PENALTIES = {
        "politics": 0.8,
        "entertainment": 0.7,
        "sports": 0.6,
        "religion": 0.7,
        "personal": 0.6,
        "technical": 0.5,
        "commercial": 0.4
    }

    def filter_results(self, query: str, chunks: List[Dict]) -> Tuple[List[Dict], Dict[str, Any]]:
        """Filter chunks to ensure domain relevance."""
        filtered_chunks = []
        filtering_stats = {
            "total_chunks": len(chunks),
            "removed_non_domain": 0,
            "removed_low_relevance": 0,
            "kept_chunks": 0
        }

        for chunk in chunks:
            chunk_text = chunk.get("text", "").lower()
            chunk_score = chunk.get("score", 0)

            # Check 1: Must have Harare context
            has_harare_context = self._has_harare_context(chunk_text)

            # Check 2: Must be service-related
            is_service_related = self._is_service_related(chunk_text, query)

            # Check 3: Penalty for non-domain content
            non_domain_penalty = self._calculate_non_domain_penalty(chunk_text)

            # Check 4: Minimum relevance score
            is_relevant = chunk_score >= 0.3

            if (has_harare_context and is_service_related and
                non_domain_penalty < 0.5 and is_relevant):
                filtered_chunks.append(chunk)
                filtering_stats["kept_chunks"] += 1
            else:
                if not has_harare_context:
                    filtering_stats["removed_non_domain"] += 1
                elif not is_relevant:
                    filtering_stats["removed_low_relevance"] += 1

        return filtered_chunks, filtering_stats

    def _has_harare_context(self, text: str) -> bool:
        """Check if text mentions Harare or Zimbabwe."""
        for term in self.HARARE_REQUIRED_TERMS:
            if term in text:
                return True

        # Also check for council-related terms in context
        council_terms = ["council", "municipal", "local government", "authority"]
        if any(term in text for term in council_terms):
            # Check if there's geographic context
            geographic_terms = ["city", "town", "urban", "suburb", "district"]
            if any(term in text for term in geographic_terms):
                return True

        return False

    def _is_service_related(self, text: str, query: str) -> bool:
        """Check if text is related to municipal services."""
        query_lower = query.lower()

        # Check if query matches any service category
        for category, keywords in self.SERVICE_CATEGORIES.items():
            if any(keyword in query_lower for keyword in keywords):
                # Text should also contain related keywords
                if any(keyword in text for keyword in keywords):
                    return True

        # If no specific category matched, check general service terms
        general_service_terms = ["service", "department", "office", "facility", "center"]
        if any(term in text for term in general_service_terms):
            return True

        return False

    def _calculate_non_domain_penalty(self, text: str) -> float:
        """Calculate penalty for non-domain content."""
        penalty = 0.0

        # Define topic keywords
        topic_keywords = {
            "politics": ["election", "vote", "party", "campaign", "politician"],
            "entertainment": ["movie", "music", "celebrity", "show", "concert"],
            "sports": ["football", "soccer", "cricket", "game", "match", "tournament"],
            "religion": ["church", "prayer", "worship", "religious", "faith"],
            "personal": ["dating", "relationship", "family", "personal"],
            "technical": ["programming", "software", "computer", "code", "algorithm"],
            "commercial": ["buy", "sell", "shop", "store", "product", "market"]
        }

        for topic, penalty_value in self.NON_DOMAIN_PENALTIES.items():
            if topic in topic_keywords:
                if any(keyword in text for keyword in topic_keywords[topic]):
                    penalty = max(penalty, penalty_value)

        return penalty