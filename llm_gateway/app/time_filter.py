"""
Time Filter for Harare Chatbot Gateway v5.3
Enforces temporal validity and freshness with mandatory expiry pre-filtering
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date, timedelta

logger = logging.getLogger(__name__)

class TimeFilter:
    """
    Temporal guardrails system with:
    - Mandatory expiry pre-filtering (documents with valid_to < today are removed)
    - Freshness confidence calculation
    - Missing validity metadata handling
    - Expiry warning generation
    """
    
    def __init__(self, config: Optional[Dict] = None):
        self.config = config or {}
        
        # Thresholds
        self.freshness_warning_threshold = self.config.get(
            "freshness_warning_threshold", 
            0.30
        )
        self.missing_validity_freshness_cap = self.config.get(
            "missing_validity_freshness_cap",
            0.6
        )
        self.display_validity_within_days = self.config.get(
            "display_validity_if_expires_within_days",
            90
        )
        
        logger.info(f"Time Filter initialized (freshness warning < {self.freshness_warning_threshold})")
    
    def filter_expired(
        self, 
        documents: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        MANDATORY: Remove documents with valid_to < today.
        
        This is the first filter applied to ALL retrieved documents.
        No document with an expired validity date should ever reach the LLM.
        
        Args:
            documents: List of documents from RAG
            
        Returns:
            Tuple of (valid_documents, expired_documents)
        """
        today = date.today()
        valid_docs = []
        expired_docs = []
        
        for doc in documents:
            valid_to = doc.get("valid_to")
            
            if not valid_to:
                # No valid_to - apply fallback rules (see normalize_validity)
                valid_docs.append(doc)
                continue
            
            try:
                # Parse valid_to
                if isinstance(valid_to, str):
                    valid_to_date = datetime.fromisoformat(
                        valid_to.replace('Z', '+00:00')
                    ).date()
                elif isinstance(valid_to, date):
                    valid_to_date = valid_to
                else:
                    logger.warning(f"Invalid valid_to format in doc {doc.get('id')}: {valid_to}")
                    valid_docs.append(doc)  # Don't filter malformed dates here
                    continue
                
                # Check if expired
                if valid_to_date < today:
                    logger.info(
                        f"Filtering expired document: {doc.get('title', 'Unknown')} "
                        f"(valid_to: {valid_to_date}, today: {today})"
                    )
                    expired_docs.append(doc)
                else:
                    valid_docs.append(doc)
                    
            except Exception as e:
                logger.error(f"Error parsing valid_to for doc {doc.get('id')}: {e}")
                # Don't filter on parse errors - let it through with warning
                valid_docs.append(doc)
        
        logger.info(
            f"Expiry pre-filter: {len(valid_docs)} valid, "
            f"{len(expired_docs)} expired (removed)"
        )
        
        return valid_docs, expired_docs
    
    def normalize_validity(
        self, 
        documents: List[Dict[str, Any]]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Handle documents with missing validity metadata.
        
        Rules:
        1. If valid_to missing but valid_from present → treat as indefinitely valid
        2. If both missing → cap freshness_confidence at configured limit
        
        Args:
            documents: List of documents (after expiry filter)
            
        Returns:
            Tuple of (processed_documents, list_of_docs_with_missing_validity)
        """
        missing_validity_docs = []
        
        for doc in documents:
            valid_to = doc.get("valid_to")
            valid_from = doc.get("valid_from")
            
            if not valid_to:
                if valid_from:
                    # Indefinitely valid
                    doc["validity_status"] = "indefinite"
                    doc["valid_to_missing"] = True
                    missing_validity_docs.append(doc)
                    logger.debug(
                        f"Document {doc.get('id')} has valid_from but no valid_to - "
                        f"treating as indefinitely valid"
                    )
                else:
                    # Both missing - cap freshness
                    doc["validity_status"] = "unknown"
                    doc["valid_to_missing"] = True
                    doc["valid_from_missing"] = True
                    
                    # Cap freshness confidence
                    original_freshness = doc.get("freshness_confidence", 0.0)
                    if original_freshness > self.missing_validity_freshness_cap:
                        doc["freshness_confidence"] = self.missing_validity_freshness_cap
                        doc["freshness_confidence_capped"] = True
                        logger.warning(
                            f"Document {doc.get('id')} missing both validity dates - "
                            f"capping freshness at {self.missing_validity_freshness_cap}"
                        )
                    missing_validity_docs.append(doc)
        
        return documents, missing_validity_docs
    
    def calculate_freshness_confidence(
        self, 
        doc: Dict[str, Any]
    ) -> float:
        """
        Calculate freshness confidence score.
        
        Args:
            doc: Document with validity dates
            
        Returns:
            Freshness confidence (0-1)
        """
        today = date.today()
        
        # If valid_to is far in the future, high freshness
        # If valid_to is soon or past, low freshness
        valid_to = doc.get("valid_to")
        valid_from = doc.get("valid_from")
        
        if not valid_to:
            # Handle missing valid_to
            if not valid_from:
                # Both missing - return capped value
                return self.missing_validity_freshness_cap
            else:
                # Indefinitely valid - use valid_from for age calculation
                try:
                    valid_from_date = self._parse_date(valid_from)
                    days_old = (today - valid_from_date).days
                    
                    # Decay over time
                    if days_old < 30:
                        return 1.0
                    elif days_old < 180:
                        return 0.9
                    elif days_old < 365:
                        return 0.7
                    else:
                        return 0.5
                except:
                    return 0.6
        
        try:
            valid_to_date = self._parse_date(valid_to)
            days_until_expiry = (valid_to_date - today).days
            
            if days_until_expiry > 365:
                return 1.0
            elif days_until_expiry > 180:
                return 0.9
            elif days_until_expiry > 90:
                return 0.7
            elif days_until_expiry > 30:
                return 0.5
            elif days_until_expiry > 0:
                return 0.3
            else:
                # Should never reach here (expiry filter should have removed)
                return 0.1
                
        except Exception as e:
            logger.warning(f"Error calculating freshness: {e}")
            return 0.5
    
    def should_show_expiry_warning(
        self, 
        doc: Dict[str, Any],
        freshness_confidence: Optional[float] = None
    ) -> bool:
        """
        Determine if expiry warning should be shown.
        
        Args:
            doc: Document
            freshness_confidence: Pre-calculated freshness (optional)
            
        Returns:
            True if warning should be shown
        """
        # Always show if freshness below threshold
        if freshness_confidence is not None:
            if freshness_confidence < self.freshness_warning_threshold:
                return True
        
        # Show if expires soon
        valid_to = doc.get("valid_to")
        if valid_to:
            try:
                valid_to_date = self._parse_date(valid_to)
                days_until_expiry = (valid_to_date - date.today()).days
                
                if days_until_expiry <= self.display_validity_within_days:
                    return True
            except:
                pass
        
        return False
    
    def generate_expiry_warning(
        self, 
        doc: Dict[str, Any]
    ) -> str:
        """
        Generate appropriate expiry warning message.
        
        Args:
            doc: Document
            
        Returns:
            Warning text
        """
        valid_to = doc.get("valid_to")
        
        if not valid_to:
            if doc.get("valid_to_missing") and doc.get("valid_from_missing"):
                return (
                    "⚠️ **This information may be out of date.** "
                    "Validity dates are not available for this document."
                )
            return ""
        
        try:
            valid_to_date = self._parse_date(valid_to)
            days_until_expiry = (valid_to_date - date.today()).days
            
            if days_until_expiry < 0:
                return (
                    f"⚠️ **This information is out of date.** "
                    f"Validity expired on {valid_to_date.strftime('%d %B %Y')}. "
                    f"Please verify with the relevant department."
                )
            elif days_until_expiry <= 30:
                return (
                    f"⚠️ **This information expires soon** "
                    f"(on {valid_to_date.strftime('%d %B %Y')}). "
                    f"Please verify if still current."
                )
            else:
                return (
                    f"**Valid until:** {valid_to_date.strftime('%d %B %Y')}"
                )
        except:
            return "⚠️ **Validity date format error.** Please verify this information."
    
    def _parse_date(self, date_str: Any) -> date:
        """Parse date from various formats."""
        if isinstance(date_str, date):
            return date_str
        if isinstance(date_str, datetime):
            return date_str.date()
        if isinstance(date_str, str):
            # Try ISO format
            try:
                return datetime.fromisoformat(
                    date_str.replace('Z', '+00:00')
                ).date()
            except:
                # Try other common formats
                for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]:
                    try:
                        return datetime.strptime(date_str, fmt).date()
                    except:
                        continue
        
        raise ValueError(f"Cannot parse date: {date_str}")

# Global instance
time_filter = TimeFilter()