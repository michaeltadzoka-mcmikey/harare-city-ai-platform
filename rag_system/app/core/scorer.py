from typing import List

class CoverageScorer:
    """
    Determines the coverage level of retrieved evidence.
    """
    
    @staticmethod
    def determine_coverage(evidence: List[dict]) -> str:
        """
        Determine coverage based on the number and quality of evidence.
        
        Args:
            evidence: List of evidence items
        
        Returns:
            Coverage level: "full", "partial", "low", or "none"
        """
        if not evidence:
            return "none"
        
        # Count high-quality evidence (score > 0.7)
        high_quality = sum(1 for e in evidence if e.get("score", 0) > 0.7)
        
        if high_quality >= 3:
            return "full"
        elif high_quality >= 1:
            return "partial"
        else:
            # We have evidence but all low quality
            return "low"