"""
Domain Validator - Validates documents are Harare-related before ingestion
"""
import re
from typing import Dict, Any, Tuple

class DomainValidator:
    """Validates documents belong to Harare municipal domain."""
    
    # Required indicators that document is about Harare
    HARARE_INDICATORS = [
        "harare",
        "city of harare",
        "harare city council",
        "municipal",
        "zimbabwe"
    ]
    
    # Municipal service topics
    MUNICIPAL_TOPICS = [
        "permit", "license", "business", "registration",
        "water", "electricity", "rates", "payment",
        "waste", "garbage", "collection", "refuse",
        "road", "street", "infrastructure", "maintenance",
        "clinic", "health", "sanitation",
        "housing", "property", "valuation",
        "bylaw", "regulation", "policy"
    ]
    
    # Non-domain content that should be rejected
    NON_MUNICIPAL_INDICATORS = [
        "novel", "fiction", "story",
        "recipe", "cooking", "cuisine",
        "sports", "football", "cricket",
        "entertainment", "celebrity", "movie",
        "personal", "diary", "journal"
    ]
    
    def validate_document(self, document: Dict[str, Any]) -> Tuple[bool, str]:
        """
        Validate if document belongs to Harare municipal domain.
        
        Returns:
            (is_valid, reason)
        """
        content = document.get("content", "").lower()
        metadata = document.get("metadata", {})
        
        if not content:
            return False, "Empty document"
        
        # Check 1: Must mention Harare or Zimbabwe
        has_harare_context = any(
            indicator in content 
            for indicator in self.HARARE_INDICATORS
        )
        
        # Check 2: Must be about municipal services
        has_municipal_topic = any(
            topic in content 
            for topic in self.MUNICIPAL_TOPICS
        )
        
        # Check 3: Should not be non-municipal content
        has_non_municipal = any(
            indicator in content 
            for indicator in self.NON_MUNICIPAL_INDICATORS
        )
        
        # Decision logic
        if has_non_municipal:
            return False, "Contains non-municipal content"
        
        if not has_harare_context and not has_municipal_topic:
            return False, "No Harare or municipal context found"
        
        # If it has Harare context OR municipal topics, it's valid
        if has_harare_context or has_municipal_topic:
            return True, "Valid Harare municipal document"
        
        return False, "Insufficient domain relevance"
    
    def get_domain_score(self, content: str) -> float:
        """
        Calculate domain relevance score (0-1).
        
        Higher score = more relevant to Harare municipal domain
        """
        content_lower = content.lower()
        score = 0.0
        
        # Points for Harare mentions
        harare_count = sum(1 for indicator in self.HARARE_INDICATORS if indicator in content_lower)
        score += min(harare_count * 0.2, 0.4)  # Max 0.4 points
        
        # Points for municipal topics
        topic_count = sum(1 for topic in self.MUNICIPAL_TOPICS if topic in content_lower)
        score += min(topic_count * 0.1, 0.5)  # Max 0.5 points
        
        # Penalty for non-municipal content
        non_municipal_count = sum(1 for indicator in self.NON_MUNICIPAL_INDICATORS if indicator in content_lower)
        score -= non_municipal_count * 0.2
        
        return max(0.0, min(1.0, score))
    
    def suggest_document_category(self, content: str) -> str:
        """Suggest which municipal category document belongs to."""
        content_lower = content.lower()
        
        categories = {
            "business_services": ["business", "permit", "license", "registration", "company"],
            "utilities": ["water", "electricity", "bill", "payment", "meter"],
            "waste_management": ["waste", "garbage", "refuse", "collection", "recycling"],
            "infrastructure": ["road", "street", "pothole", "drainage", "bridge"],
            "health_services": ["clinic", "hospital", "health", "sanitation"],
            "housing": ["housing", "property", "rates", "building", "valuation"],
            "regulations": ["bylaw", "regulation", "policy", "law", "standard"]
        }
        
        category_scores = {}
        for category, keywords in categories.items():
            score = sum(1 for keyword in keywords if keyword in content_lower)
            category_scores[category] = score
        
        if not category_scores or max(category_scores.values()) == 0:
            return "general"
        
        return max(category_scores, key=category_scores.get)