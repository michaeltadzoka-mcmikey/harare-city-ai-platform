# llm_gateway/app/domain_classifier.py
"""
Domain Classifier for Harare Chatbot
Validates if queries belong to Harare municipal domain before processing
"""

import re
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class DomainClassifier:
    """
    Classifies queries as in-domain or out-of-domain for Harare services.
    
    Purpose:
    - Ensure we only answer Harare-related questions
    - Detect and reject non-municipal queries
    - Provide confidence scores for routing decisions
    """
    
    # Harare service categories with keywords
    HARARE_SERVICE_CATEGORIES = {
        "business_services": [
            "business permit", "trading license", "company registration",
            "shop license", "vendor permit", "street trading", "business license",
            "hawker", "tuck shop", "market stall"
        ],
        "municipal_services": [
            "water bill", "electricity bill", "rates payment", "municipal rates",
            "waste collection", "garbage schedule", "sewage", "refuse",
            "sanitation", "billing", "account", "arrears"
        ],
        "infrastructure": [
            "road repair", "pothole", "street light", "drainage",
            "bridge", "pavement", "sidewalk", "storm drain",
            "manhole", "road maintenance", "traffic light"
        ],
        "health_services": [
            "clinic hours", "hospital", "health center", "vaccination",
            "sanitation", "public health", "toilet", "hygiene",
            "immunization", "medical services"
        ],
        "housing_property": [
            "housing application", "property rates", "building permit",
            "construction", "zoning", "land use", "valuation",
            "council house", "stand", "plot"
        ],
        "complaints_reports": [
            "report issue", "make complaint", "file report",
            "service complaint", "no service", "broken", "not working",
            "lodge complaint", "problem", "issue"
        ],
        "information": [
            "office hours", "contact details", "location", "address",
            "phone number", "email", "website", "department",
            "where can i", "how do i", "requirements"
        ]
    }
    
    # Explicit Harare references
    HARARE_MARKERS = [
        "harare", "city of harare", "harare city", "harare municipal",
        "harare council", "local authority", "city council",
        "municipality", "municipal council"
    ]
    
    # Geographic areas in Harare (for location validation)
    HARARE_LOCATIONS = [
        "mbare", "highfield", "glen norah", "warren park", "dzivarasekwa",
        "budiriro", "hatcliffe", "epworth", "borrowdale", "mount pleasant",
        "avondale", "mabelreign", "marlborough", "greendale", "highlands",
        "msasa", "workington", "southerton", "ardbennie", "waterfalls",
        "CBD", "central business district", "samora machel", "robert mugabe",
        "simon mazorodze", "george silundika", "leopold takawira"
    ]
    
    async def classify_query(
        self, 
        message: str, 
        context: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Classify query with confidence and category.
        
        Args:
            message: User's query
            context: Optional context (conversation history, etc.)
            
        Returns:
            Classification result with confidence, category, and action
        """
        message_lower = message.lower().strip()
        
        # Check for explicit Harare references
        harare_explicit = any(
            marker in message_lower for marker in self.HARARE_MARKERS
        )
        
        # Check for explicit council/municipal references
        council_explicit = any(
            term in message_lower 
            for term in ["council", "municipal", "municipality"]
        )
        
        # Check for Harare location references
        location_explicit = any(
            location in message_lower for location in self.HARARE_LOCATIONS
        )
        
        # Determine service category
        category = "unknown"
        confidence = 0.5  # Default moderate confidence
        matched_keywords = []
        
        for cat, keywords in self.HARARE_SERVICE_CATEGORIES.items():
            for keyword in keywords:
                if keyword in message_lower:
                    category = cat
                    matched_keywords.append(keyword)
                    confidence = 0.8  # Higher confidence for keyword matches
                    break
            if category != "unknown":
                break
        
        # Adjust confidence based on context
        if context:
            last_topic = context.get("last_topic")
            if last_topic == category:
                confidence = min(1.0, confidence + 0.1)
                logger.debug(f"Confidence boosted by context: {confidence}")
        
        # Check if it's a procedural question
        is_procedural = any(
            pattern in message_lower 
            for pattern in [
                "how do i", "where can i", "what do i need",
                "requirements", "how to", "steps to"
            ]
        )
        
        # Final domain decision
        in_domain = self._determine_in_domain(
            harare_explicit=harare_explicit,
            council_explicit=council_explicit,
            location_explicit=location_explicit,
            category=category,
            confidence=confidence,
            is_procedural=is_procedural
        )
        
        result = {
            "in_domain": in_domain,
            "confidence": confidence,
            "category": category,
            "harare_explicit": harare_explicit,
            "council_explicit": council_explicit,
            "location_explicit": location_explicit,
            "is_procedural": is_procedural,
            "matched_keywords": matched_keywords,
            "suggested_action": self._get_suggested_action(in_domain, category)
        }
        
        logger.info(
            f"Domain classification: {'IN' if in_domain else 'OUT'} "
            f"(category: {category}, confidence: {confidence:.2f})"
        )
        
        return result
    
    def _determine_in_domain(
        self,
        harare_explicit: bool,
        council_explicit: bool,
        location_explicit: bool,
        category: str,
        confidence: float,
        is_procedural: bool
    ) -> bool:
        """
        Determine if query is in-domain based on multiple signals.
        
        Args:
            Various classification signals
            
        Returns:
            True if in-domain
        """
        # Strong signals for in-domain
        if harare_explicit or location_explicit:
            return True
        
        # Service category match with reasonable confidence
        if category != "unknown" and confidence >= 0.6:
            return True
        
        # Council/municipal reference with service context
        if council_explicit and category != "unknown":
            return True
        
        # Procedural questions about services (might be in-domain)
        if is_procedural and category != "unknown":
            return True
        
        # Low confidence threshold for ambiguous cases
        if confidence >= 0.4:
            return True  # Give benefit of doubt
        
        return False
    
    def _get_suggested_action(self, in_domain: bool, category: str) -> str:
        """
        Get suggested routing action based on classification.
        
        Args:
            in_domain: Whether query is in-domain
            category: Service category
            
        Returns:
            Suggested action
        """
        if not in_domain:
            return "respond_out_of_domain"
        
        # Route based on category
        category_actions = {
            "business_services": "route_to_rag",
            "municipal_services": "route_to_rag",
            "information": "route_to_rag",
            "complaints_reports": "route_to_rasa",
            "infrastructure": "route_to_rasa",  # For reporting issues
            "health_services": "route_to_rag",
            "housing_property": "route_to_rag"
        }
        
        return category_actions.get(category, "route_to_llm")
    
    def validate_location(self, location: str) -> Dict[str, Any]:
        """
        Validate if a location is in Harare.
        
        Args:
            location: Location string to validate
            
        Returns:
            Validation result
        """
        location_lower = location.lower()
        
        # Check for Harare location markers
        is_harare_location = any(
            loc in location_lower for loc in self.HARARE_LOCATIONS
        )
        
        # Check for general Harare markers
        has_harare_marker = any(
            marker in location_lower for marker in self.HARARE_MARKERS
        )
        
        # Check for street/road indicators (common in Harare)
        has_street_indicator = any(
            indicator in location_lower 
            for indicator in ["ave", "avenue", "street", "road", "drive", "way"]
        )
        
        is_valid = is_harare_location or has_harare_marker or has_street_indicator
        
        return {
            "is_valid": is_valid,
            "is_harare_location": is_harare_location,
            "has_harare_marker": has_harare_marker,
            "has_street_indicator": has_street_indicator,
            "confidence": 0.9 if is_harare_location else (0.7 if has_harare_marker else 0.5)
        }


# Global domain classifier instance
domain_classifier = DomainClassifier()