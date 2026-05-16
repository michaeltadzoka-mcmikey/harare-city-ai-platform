from typing import Dict, Any, List, Set
from datetime import date
from app.core.index import VectorIndex
from app.config import config

class CoverageScorer:
    """
    Computes Service Coverage Score (SCS) for departments/service areas.
    Includes location completeness factor.
    """

    def __init__(self, index: VectorIndex):
        self.index = index
        # Weights from spec
        self.weights = {
            "policy": 1.5,
            "procedure": 1.5,
            "fee_schedule": 1.0,
            "faq": 1.0,
            "emergency": 2.0,
            "contact_directory": 0.5
        }
        self.total_weight = sum(self.weights.values())

    def compute_scs(self, department: str, service_area: str) -> float:
        """
        SCS = (weighted content type presence) * (1 - expired_ratio) * location_completeness
        """
        # Query active collection for documents with given department and service_area
        where = {
            "$and": [
                {"department": {"$eq": department}},
                {"service_area": {"$eq": service_area}}
            ]
        }
        results = self.index.active_collection.get(
            where=where,
            include=["metadatas"]
        )
        docs = results["metadatas"] if results["metadatas"] else []

        # 1. Weighted content type presence
        content_types_present = set(d.get("content_type") for d in docs if d.get("content_type"))
        numerator = sum(self.weights.get(ct, 0) for ct in content_types_present)
        content_score = numerator / self.total_weight if self.total_weight > 0 else 0

        # 2. Expired penalty
        today = date.today().isoformat()
        expired_count = sum(1 for d in docs if d.get("valid_to", "9999-12-31") < today)
        total_docs = len(docs)
        expired_ratio = expired_count / max(1, total_docs)
        expired_factor = 1 - expired_ratio

        # 3. Location completeness ratio
        location_factor = self._compute_location_completeness(docs, service_area)

        scs = content_score * expired_factor * location_factor
        return round(min(1.0, scs), 3)

    def _compute_location_completeness(self, docs: List[Dict], service_area: str) -> float:
        """
        Compute the ratio of suburbs/wards that have at least one location-specific document
        for this service area. Uses config.SUBURBS.
        """
        all_suburbs = config.SUBURBS
        # Count distinct suburbs covered by documents (excluding "Council-wide")
        covered_suburbs = set()
        for doc in docs:
            locations = doc.get("locations", [])
            if isinstance(locations, list):
                for loc in locations:
                    if loc != "Council-wide" and loc in all_suburbs:
                        covered_suburbs.add(loc)
        if not all_suburbs:
            return 1.0
        return len(covered_suburbs) / len(all_suburbs)