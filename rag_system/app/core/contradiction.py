import logging
import re
from typing import List, Dict, Any, Tuple
from collections import defaultdict
from datetime import datetime

logger = logging.getLogger(__name__)

class ContradictionDetector:
    """
    Detects contradictions among retrieved chunks based on numeric values and entity mentions.
    Uses simple heuristics: if two sources give different numbers for the same entity, flag.
    Resolution: recency (last_updated) and authority_confidence.
    """

    def __init__(self):
        # Patterns to extract numbers with context
        self.number_pattern = re.compile(
            r'(\d+(?:\.\d+)?)\s*(ZWL|\$|percent|%|days?|weeks?|months?|years?)?',
            re.IGNORECASE
        )
        # Common entities that might have conflicting values
        self.entity_patterns = {
            "fee": re.compile(r'fee(?:\s+amount)?\s*(?::|is|=)?\s*', re.IGNORECASE),
            "cost": re.compile(r'cost\s*(?::|is|=)?\s*', re.IGNORECASE),
            "time": re.compile(r'(processing|waiting|lead)\s+time\s*(?::|is|=)?\s*', re.IGNORECASE),
            "duration": re.compile(r'duration\s*(?::|is|=)?\s*', re.IGNORECASE),
            "deadline": re.compile(r'deadline\s*(?::|is|=)?\s*', re.IGNORECASE),
        }

    def detect(self, chunks: List[Dict]) -> List[Dict[str, Any]]:
        """
        Input: list of chunks (each with text, metadata, score)
        Output: list of contradiction objects
        """
        if len(chunks) < 2:
            return []

        contradictions = []
        # Group chunks by rough topic using simple keyword matching
        # For each entity type, collect all numeric claims
        claims_by_entity = defaultdict(list)

        for chunk in chunks:
            text = chunk["text"]
            metadata = chunk["metadata"]
            doc_id = metadata.get("document_id", "unknown")
            version = metadata.get("version", 1)
            last_updated = metadata.get("last_updated")
            authority = float(metadata.get("authority_confidence", 0.5))

            # Find all numbers with context
            for match in self.number_pattern.finditer(text):
                value = float(match.group(1))
                unit = match.group(2) or ""
                # Look for entity type before the number
                preceding_text = text[max(0, match.start()-50):match.start()]
                entity_type = self._identify_entity(preceding_text)
                if entity_type:
                    claims_by_entity[entity_type].append({
                        "value": value,
                        "unit": unit,
                        "doc_id": doc_id,
                        "version": version,
                        "last_updated": last_updated,
                        "authority": authority,
                        "text_snippet": text[match.start():match.end()+50]
                    })

        # For each entity, check for conflicting values
        for entity, claims in claims_by_entity.items():
            if len(claims) < 2:
                continue
            # Group claims by value (within tolerance)
            value_groups = defaultdict(list)
            for claim in claims:
                # Round to 2 decimals for comparison
                rounded = round(claim["value"], 2)
                value_groups[rounded].append(claim)

            if len(value_groups) > 1:
                # Contradiction found
                # Resolve: pick the claim with highest (authority, recency)
                resolved_claim = self._resolve_contradiction(claims)
                contradiction = {
                    "topic": entity,
                    "conflicting_sources": [c["doc_id"] for c in claims],
                    "resolution": f"Value: {resolved_claim['value']} {resolved_claim['unit']}",
                    "resolution_basis": "authority and recency",
                    "resolved_value": resolved_claim["value"],
                    "resolved_unit": resolved_claim["unit"],
                    "resolved_source": resolved_claim["doc_id"]
                }
                contradictions.append(contradiction)

        return contradictions

    def _identify_entity(self, text: str) -> str:
        """Identify entity type based on preceding text."""
        text_lower = text.lower()
        for entity, pattern in self.entity_patterns.items():
            if pattern.search(text_lower):
                return entity
        return None

    def _resolve_contradiction(self, claims: List[Dict]) -> Dict:
        """
        Resolve conflicting claims by picking the one with highest authority,
        then most recent last_updated.
        """
        # Sort by authority desc, then last_updated desc (if available)
        def sort_key(claim):
            auth = claim.get("authority", 0)
            date_str = claim.get("last_updated", "1970-01-01")
            try:
                date_val = datetime.fromisoformat(date_str).timestamp()
            except:
                date_val = 0
            return (auth, date_val)

        sorted_claims = sorted(claims, key=sort_key, reverse=True)
        return sorted_claims[0]