from typing import List, Dict, Any, Optional
import logging
import json
from datetime import date
from app.core.index import VectorIndex, date_to_int
from app.config import config

logger = logging.getLogger(__name__)

class Retriever:
    def __init__(self, index: VectorIndex):
        self.index = index
        self.location_boost_factor = config.LOCATION_BOOST_FACTOR
        self.service_update_boost = getattr(config, 'SERVICE_UPDATE_BOOST', 1.3)
        self.pinned_override_boost = getattr(config, 'PINNED_OVERRIDE_BOOST', 2.0)

    def retrieve(self, query: str,
                 conversation_context: Optional[str] = None,   # <-- NEW
                 top_k: int = 5,
                 threshold: float = 0.3,
                 location: Optional[str] = None,
                 valid_at: Optional[str] = None,
                 include_archive: bool = False,
                 **kwargs) -> List[Dict[str, Any]]:
        """
        Retrieve chunks, using conversation_context to enhance the query,
        then filter by location, and apply priority boosts.
        Also computes a match_reason for each chunk.
        """
        # Combine query and context if provided
        if conversation_context:
            combined_query = f"{query} [CONTEXT] {conversation_context}"
        else:
            combined_query = query

        # Fetch more than needed for post filtering
        fetch_k = top_k * 5 if location else top_k * 2
        where = None
        if valid_at:
            valid_int = date_to_int(valid_at)
            where = {
                "$and": [
                    {"valid_from_int": {"$lte": valid_int}},
                    {"valid_to_int": {"$gte": valid_int}}
                ]
            }

        # Use search method with combined query
        results = self.index.search(
            combined_query,
            n_results=fetch_k,
            where=where,
            include_archive=include_archive,
            **kwargs
        )
        results = [r for r in results if r["score"] >= threshold]

        # Post filter by location if specified
        if location:
            filtered = []
            for r in results:
                locs_str = r["metadata"].get("locations", "[]")
                try:
                    locs = json.loads(locs_str)
                except Exception:
                    locs = []
                if "Council-wide" in locs or location in locs:
                    filtered.append(r)
            results = filtered

        if not results and location:
            logger.info(f"No location specific results for {location}, falling back to Council-wide")
            fallback_results = self.index.search(
                combined_query,
                n_results=fetch_k,
                where=where,
                include_archive=include_archive,
                **kwargs
            )
            fallback_results = [r for r in fallback_results if r["score"] >= threshold]
            filtered = []
            for r in fallback_results:
                locs_str = r["metadata"].get("locations", "[]")
                try:
                    locs = json.loads(locs_str)
                except:
                    locs = []
                if "Council-wide" in locs:
                    filtered.append(r)
            results = filtered

        # Apply location boost and record reason
        for r in results:
            reason_parts = []
            if location:
                locs_str = r["metadata"].get("locations", "[]")
                try:
                    locs = json.loads(locs_str)
                except:
                    locs = []
                if location in locs:
                    r["score"] *= self.location_boost_factor
                    r["boosted"] = True
                    reason_parts.append(f"location match ({location})")
            # Add semantic similarity info
            reason_parts.append(f"semantic similarity (score {r['score']:.2f})")
            r["match_reason"] = "; ".join(reason_parts)

        # Apply priority boost based on content_type
        results = self._apply_priority_boost(results)

        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def _apply_priority_boost(self, chunks: List[Dict]) -> List[Dict]:
        """Boost scores for service_update and pinned_override documents."""
        for chunk in chunks:
            content_type = chunk["metadata"].get("content_type")
            if content_type == "service_update":
                chunk["score"] *= self.service_update_boost
                chunk["priority_boosted"] = "service_update"
                if "match_reason" in chunk:
                    chunk["match_reason"] += "; boosted as service_update"
            elif content_type == "pinned_override":
                chunk["score"] *= self.pinned_override_boost
                chunk["priority_boosted"] = "pinned_override"
                if "match_reason" in chunk:
                    chunk["match_reason"] += "; boosted as pinned_override"
        return chunks