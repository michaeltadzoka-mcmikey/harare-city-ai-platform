"""
Response Formatter - Simplified for citizen-friendly responses.
No technical templates, no source citations, no validity dates.
Clean, direct answers only.
"""

import logging
import re
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)

class ResponseFormatter:
    """
    Simple response formatter - just returns the answer cleanly.
    All templates and source formatting have been removed.
    """

    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        logger.info("Response Formatter initialized (simplified citizen-friendly mode)")

    def format_response(
        self,
        rag_payload: Dict[str, Any],
        confidence_band: str,
        presentation_directives: Optional[Dict] = None
    ) -> str:
        """
        Return clean answer without any technical formatting.
        
        Args:
            rag_payload: Contains 'answer' field with the raw response
            confidence_band: Not used - kept for API compatibility
            presentation_directives: Not used - kept for API compatibility
        
        Returns:
            Clean, citizen-friendly answer string
        """
        # Get the answer from payload
        answer = rag_payload.get("answer", "")
        
        if not answer:
            return self.tiered_fallback("no_data")
        
        # Clean up any remaining technical artifacts
        answer = self._clean_answer(answer)
        
        # Ensure answer ends with proper punctuation
        if answer and answer[-1] not in '.!?':
            answer += '.'
        
        return answer

    def tiered_fallback(self, cause: str) -> str:
        """
        Return a simple, friendly fallback message.
        
        Args:
            cause: Reason for fallback (no_data, system_issue, low_confidence, default)
        
        Returns:
            User-friendly fallback message
        """
        messages = {
            "no_data": "I don't have that information yet. Please contact the Harare City Council directly for assistance.",
            "system_issue": "I'm having trouble connecting right now. Please try again in a moment.",
            "low_confidence": "I'm not completely sure about this information. Please verify with the council.",
            "default": "I couldn't answer that question. Please try rephrasing or contact the council directly."
        }
        return messages.get(cause, messages["default"])

    def _clean_answer(self, answer: str) -> str:
        """
        Remove any remaining technical artifacts from the answer.
        
        Removes:
        - Source lines (Source: DOC-001)
        - Department citations (— Water Department)
        - Emoji badges (✅, ✔️, ⚠️)
        - Confidence statements
        - Multiple blank lines
        """
        # Remove source attribution lines
        answer = re.sub(r'\n*Source:.*?\n', '\n', answer, flags=re.IGNORECASE)
        answer = re.sub(r'\n*— .*?\(.*?\)', '', answer)
        answer = re.sub(r'\n*— [A-Za-z\s]+$', '', answer, flags=re.MULTILINE)
        
        # Remove emoji badges and their accompanying text
        answer = re.sub(r'✅.*?\n', '\n', answer)
        answer = re.sub(r'✔️.*?\n', '\n', answer)
        answer = re.sub(r'⚠️.*?\n', '\n', answer)
        
        # Remove confidence statements
        answer = re.sub(r'\*Verified from official.*?\*', '', answer)
        answer = re.sub(r'\*Based on council.*?\*', '', answer)
        answer = re.sub(r'\(Note:.*?\)', '', answer)
        
        # Remove any lingering document IDs
        answer = re.sub(r'[A-Z]{2,}-[A-Z]{3,}-\d{3,}', '', answer)
        
        # Clean up multiple blank lines
        answer = re.sub(r'\n\s*\n\s*\n+', '\n\n', answer)
        
        # Remove leading/trailing whitespace
        answer = answer.strip()
        
        return answer

    def add_validity_warning(
        self, 
        response: str, 
        freshness_confidence: float, 
        valid_until: Optional[str]
    ) -> str:
        """
        No validity warnings - return response as-is.
        Citizens don't need to know about document expiry dates.
        """
        return response

    def add_contradiction_disclosure(
        self, 
        response: str, 
        contradictions: List[Dict]
    ) -> str:
        """
        No contradiction disclosures - return response as-is.
        The LLM should handle contradictions internally.
        """
        return response
    
    def format_simple_answer(self, answer: str) -> str:
        """
        Ultra-simple formatting for direct answers.
        Use this for override responses and fast-path replies.
        """
        return self._clean_answer(answer)


# Global instance
response_formatter = ResponseFormatter()