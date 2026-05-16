from typing import List, Dict, Any
from datetime import datetime, date

class ConfidenceScorer:
    """
    Computes composite confidence score based on retrieval relevance,
    freshness, authority, and consensus.
    """

    def __init__(self):
        self.freshness_weight = 0.2
        self.authority_weight = 0.3
        self.relevance_weight = 0.5
        self.consensus_bonus = 0.1

    def compute(self, chunks: List[Dict], query: str) -> float:
        if not chunks:
            return 0.0

        # Average relevance score of top chunks
        relevance = sum(c.get("score", 0.0) for c in chunks) / len(chunks)

        # Freshness: based on valid_to proximity and last_updated recency
        today = date.today()
        freshness_scores = []
        for c in chunks:
            # Days left component
            valid_to_str = c["metadata"].get("valid_to")
            days_left_score = 0.5
            if valid_to_str:
                try:
                    valid_to = date.fromisoformat(valid_to_str)
                    days_left = (valid_to - today).days
                    days_left_score = min(1.0, max(0.0, days_left / 90.0))
                except:
                    pass

            # Last updated recency component
            last_updated_str = c["metadata"].get("last_updated")
            recency_score = 0.5
            if last_updated_str:
                try:
                    last_updated = date.fromisoformat(last_updated_str.split('T')[0])  # handle datetime
                    days_since_update = (today - last_updated).days
                    recency_score = max(0.0, 1.0 - days_since_update / 365.0)  # linear decay over 1 year
                except:
                    pass

            # Combine (equal weight)
            freshness_scores.append(0.6 * days_left_score + 0.4 * recency_score)

        avg_freshness = sum(freshness_scores) / len(freshness_scores)

        # Authority: use metadata authority_confidence
        authority_scores = [float(c["metadata"].get("authority_confidence", 0.5)) for c in chunks]
        avg_authority = sum(authority_scores) / len(authority_scores)

        # Consensus: if multiple sources agree (placeholder – we assume agreement)
        consensus = 1.0

        composite = (
            self.relevance_weight * relevance +
            self.freshness_weight * avg_freshness +
            self.authority_weight * avg_authority +
            (consensus * self.consensus_bonus if consensus > 0.8 else 0)
        )
        return min(1.0, max(0.0, composite))