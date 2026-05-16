import re
from datetime import datetime, date
from typing import Dict, Any, Tuple, List
from app.config import config

class IngestionValidator:
    HARARE_INDICATORS = ["harare", "city of harare", "harare city council", "municipal", "zimbabwe"]
    MUNICIPAL_TOPICS = ["permit", "license", "business", "registration", "water", "electricity",
                        "rates", "payment", "waste", "garbage", "collection", "refuse", "road",
                        "street", "infrastructure", "maintenance", "clinic", "health", "sanitation",
                        "housing", "property", "valuation", "bylaw", "regulation", "policy"]
    NON_MUNICIPAL_INDICATORS = ["novel", "fiction", "story", "recipe", "cooking", "cuisine",
                                "sports", "football", "cricket", "entertainment", "celebrity",
                                "movie", "personal", "diary", "journal"]

    def validate_document(self, document: Dict[str, Any]) -> Tuple[bool, str, List[str]]:
        metadata = document.get("metadata", {})
        content = document.get("content", "")
        missing = []

        for field in config.REQUIRED_METADATA_FIELDS:
            if field not in metadata or metadata[field] is None or metadata[field] == "":
                missing.append(field)

        if "topic_tags" in metadata and not isinstance(metadata["topic_tags"], list):
            return False, "topic_tags must be a list of strings", missing
        if "related_documents" in metadata and not isinstance(metadata["related_documents"], list):
            return False, "related_documents must be a list of strings", missing
        if "prerequisites" in metadata and not isinstance(metadata["prerequisites"], list):
            return False, "prerequisites must be a list of strings", missing
        if "review_cycle" in metadata and not isinstance(metadata["review_cycle"], str):
            return False, "review_cycle must be a string", missing
        if "cross_service_flag" in metadata and not isinstance(metadata["cross_service_flag"], bool):
            return False, "cross_service_flag must be a boolean", missing

        content_type = metadata.get("content_type")
        if content_type == "pinned_override":
            for field in config.PINNED_GOVERNANCE_FIELDS:
                if field not in metadata or not metadata[field]:
                    missing.append(field)

        if missing:
            return False, f"Missing required fields: {', '.join(missing)}", missing

        try:
            int(metadata.get("version"))
        except (ValueError, TypeError):
            return False, "VERSION must be an integer", missing

        try:
            date.fromisoformat(metadata.get("valid_from"))
            date.fromisoformat(metadata.get("valid_to"))
        except ValueError:
            return False, "valid_from or valid_to not in ISO format (YYYY-MM-DD)", missing

        if content_type in ["service_update", "pinned_override"]:
            valid_to = date.fromisoformat(metadata["valid_to"])
            if valid_to < date.today():
                return False, f"{content_type} must have valid_to >= today", missing

        if metadata.get("content_type") not in config.CONTENT_TYPES:
            return False, f"content_type must be one of {config.CONTENT_TYPES}", missing

        service_area = metadata.get("service_area")
        if not service_area or not isinstance(service_area, str) or not service_area.strip():
            return False, "service_area is required and must be a non‑empty string", missing

        locs = metadata.get("locations")
        if not isinstance(locs, list) and locs != "Council-wide":
            return False, "locations must be a list or 'Council-wide'", missing

        # Domain relevance check (temporarily disabled)
        # if not self._is_harare_relevant(content, metadata):
        #     return False, "Document not relevant to Harare municipal domain", missing

        return True, "Valid", missing

    def _is_harare_relevant(self, content: str, metadata: Dict) -> bool:
        combined = content.lower() + " " + " ".join(str(v) for v in metadata.values()).lower()
        has_harare = any(ind in combined for ind in self.HARARE_INDICATORS)
        has_topic = any(topic in combined for topic in self.MUNICIPAL_TOPICS)
        has_non = any(ind in combined for ind in self.NON_MUNICIPAL_INDICATORS)
        return (has_harare or has_topic) and not has_non

    def get_domain_score(self, content: str) -> float:
        content_lower = content.lower()
        score = 0.0
        harare_count = sum(1 for ind in self.HARARE_INDICATORS if ind in content_lower)
        score += min(harare_count * 0.2, 0.4)
        topic_count = sum(1 for t in self.MUNICIPAL_TOPICS if t in content_lower)
        score += min(topic_count * 0.1, 0.5)
        non_count = sum(1 for n in self.NON_MUNICIPAL_INDICATORS if n in content_lower)
        score -= non_count * 0.2
        return max(0.0, min(1.0, score))

    def suggest_document_category(self, content: str) -> str:
        content_lower = content.lower()
        categories = {
            "business_services": ["business", "permit", "license"],
            "utilities": ["water", "electricity", "bill"],
            "waste_management": ["waste", "garbage", "refuse"],
            "infrastructure": ["road", "street", "pothole"],
            "health_services": ["clinic", "hospital", "health"],
            "housing": ["housing", "property", "rates"],
            "regulations": ["bylaw", "regulation", "policy"]
        }
        scores = {cat: sum(1 for kw in kws if kw in content_lower) for cat, kws in categories.items()}
        if not scores or max(scores.values()) == 0:
            return "general"
        return max(scores, key=scores.get)