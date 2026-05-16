"""
Precedence Engine for Harare Chatbot Gateway v5.3
Implements deterministic document ranking and conflict resolution
"""

import logging
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class PrecedenceEngine:
    """
    Enforces deterministic document precedence order and conflict resolution.
    
    Key principles:
    - Fixed, immutable precedence order for document types
    - Scope overlap detection for same-type conflicts
    - Date/version-based resolution when types match
    - No statistical scoring for conflict resolution
    """
    
    # IMMUTABLE DOCUMENT PRECEDENCE ORDER
    # Lower number = higher precedence
    # Modification requires full governance review and version increment
    DOCUMENT_PRECEDENCE_ORDER = {
        "emergency_notice": 1,
        "pinned_override": 2,
        "policy": 3,
        "service_update": 4,
        "procedure": 5,
        "fee_schedule": 6,
        "faq": 7,
        "contact_directory": 8
    }
    
    def __init__(self):
        logger.info("Precedence Engine initialized with immutable order")
        
    def get_precedence(self, content_type: str) -> int:
        """
        Get precedence rank for a content type.
        
        Args:
            content_type: Document content type
            
        Returns:
            Integer rank (lower = higher precedence)
        """
        precedence = self.DOCUMENT_PRECEDENCE_ORDER.get(
            content_type.lower(),
            999  # Unknown types get lowest precedence
        )
        
        if precedence == 999:
            logger.warning(f"Unknown content_type: {content_type}, assigning lowest precedence")
        
        return precedence
    
    def sort_by_precedence(self, documents: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Sort documents by precedence order (highest precedence first).
        
        Args:
            documents: List of document dictionaries
            
        Returns:
            Sorted list
        """
        def get_sort_key(doc):
            content_type = doc.get("content_type", "unknown")
            return self.get_precedence(content_type)
        
        sorted_docs = sorted(documents, key=get_sort_key)
        
        logger.debug(
            f"Sorted {len(documents)} documents by precedence: "
            f"{[d.get('content_type') for d in sorted_docs[:3]]}"
        )
        
        return sorted_docs
    
    def scope_overlap(
        self, 
        doc_a: Dict[str, Any], 
        doc_b: Dict[str, Any]
    ) -> bool:
        """
        Check if two documents overlap in scope (department, location, topic).
        
        Args:
            doc_a: First document
            doc_b: Second document
            
        Returns:
            True if scopes overlap (documents conflict)
        """
        # Department overlap
        dept_a = doc_a.get("department", "").lower()
        dept_b = doc_b.get("department", "").lower()
        
        if dept_a and dept_b and dept_a != dept_b:
            logger.debug(f"No scope overlap: different departments ({dept_a} vs {dept_b})")
            return False
        
        # Location overlap
        loc_a = doc_a.get("location_scope", [])
        loc_b = doc_b.get("location_scope", [])
        
        # Normalize to lists
        if isinstance(loc_a, str):
            loc_a = [loc_a] if loc_a != "council-wide" else []
        if isinstance(loc_b, str):
            loc_b = [loc_b] if loc_b != "council-wide" else []
        
        # If either is council-wide (empty list), they overlap
        # If both have specific locations, check for intersection
        if loc_a and loc_b:
            if not set(loc_a).intersection(set(loc_b)):
                logger.debug(f"No scope overlap: different locations ({loc_a} vs {loc_b})")
                return False
        
        # Topic overlap
        topics_a = set(doc_a.get("topic_tags", []))
        topics_b = set(doc_b.get("topic_tags", []))
        
        if topics_a and topics_b:
            if not topics_a.intersection(topics_b):
                logger.debug(f"No scope overlap: different topics ({topics_a} vs {topics_b})")
                return False
        
        logger.debug(f"Scope overlap detected between documents")
        return True
    
    def resolve_conflict(
        self, 
        doc_a: Dict[str, Any], 
        doc_b: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Resolve conflict between two documents deterministically.
        
        Args:
            doc_a: First document
            doc_b: Second document
            
        Returns:
            Tuple of (winning document or None, resolution method)
        """
        type_a = doc_a.get("content_type", "unknown")
        type_b = doc_b.get("content_type", "unknown")
        
        # Different types - use precedence
        if type_a != type_b:
            prec_a = self.get_precedence(type_a)
            prec_b = self.get_precedence(type_b)
            
            if prec_a < prec_b:
                logger.info(f"Conflict resolved: {type_a} (precedence {prec_a}) wins over {type_b} ({prec_b})")
                return (doc_a, "precedence")
            else:
                logger.info(f"Conflict resolved: {type_b} (precedence {prec_b}) wins over {type_a} ({prec_a})")
                return (doc_b, "precedence")
        
        # Same type - check scope overlap first
        if not self.scope_overlap(doc_a, doc_b):
            logger.info(f"Same type ({type_a}) but different scopes - no conflict")
            return (None, "no_conflict_different_scopes")
        
        # Same type, overlapping scope - use date/version resolution
        return self._resolve_same_type(doc_a, doc_b)
    
    def _resolve_same_type(
        self, 
        doc_a: Dict[str, Any], 
        doc_b: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], str]:
        """
        Resolve conflict between same-type documents with overlapping scope.
        
        Resolution order:
        1. Newer effective_date
        2. Higher version number
        3. Higher authority_confidence (raw)
        
        Args:
            doc_a: First document
            doc_b: Second document
            
        Returns:
            Tuple of (winning document, resolution method)
        """
        # 1. Try effective_date
        date_a = doc_a.get("effective_date") or doc_a.get("publication_date")
        date_b = doc_b.get("effective_date") or doc_b.get("publication_date")
        
        if date_a and date_b:
            try:
                parsed_a = datetime.fromisoformat(date_a.replace('Z', '+00:00'))
                parsed_b = datetime.fromisoformat(date_b.replace('Z', '+00:00'))
                
                if parsed_a > parsed_b:
                    logger.info(f"Same-type conflict resolved: doc_a newer ({date_a} > {date_b})")
                    return (doc_a, "newer_version")
                elif parsed_b > parsed_a:
                    logger.info(f"Same-type conflict resolved: doc_b newer ({date_b} > {date_a})")
                    return (doc_b, "newer_version")
            except Exception as e:
                logger.warning(f"Error parsing dates: {e}")
        
        # 2. Try version number
        version_a = doc_a.get("version")
        version_b = doc_b.get("version")
        
        if version_a and version_b:
            # Simple string comparison (assumes semantic versioning)
            if version_a > version_b:
                logger.info(f"Same-type conflict resolved: doc_a higher version ({version_a} > {version_b})")
                return (doc_a, "version_number")
            elif version_b > version_a:
                logger.info(f"Same-type conflict resolved: doc_b higher version ({version_b} > {version_a})")
                return (doc_b, "version_number")
        
        # 3. Fallback to authority_confidence (RAW, before multipliers)
        auth_a = doc_a.get("authority_confidence_raw", doc_a.get("authority_confidence", 0.0))
        auth_b = doc_b.get("authority_confidence_raw", doc_b.get("authority_confidence", 0.0))
        
        if auth_a > auth_b:
            logger.info(f"Same-type conflict resolved: doc_a higher authority ({auth_a} > {auth_b})")
            return (doc_a, "authority_confidence")
        else:
            logger.info(f"Same-type conflict resolved: doc_b higher authority ({auth_b} >= {auth_a})")
            return (doc_b, "authority_confidence")
    
    def rank_documents(
        self, 
        documents: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Rank documents by precedence, adding precedence_rank metadata.
        
        Args:
            documents: List of documents
            
        Returns:
            List with precedence_rank added to each document
        """
        for doc in documents:
            content_type = doc.get("content_type", "unknown")
            doc["precedence_rank"] = self.get_precedence(content_type)
        
        return self.sort_by_precedence(documents)
    
    def get_precedence_order(self) -> Dict[str, int]:
        """
        Get the full precedence order (for documentation/debugging).
        
        Returns:
            Copy of precedence order dictionary
        """
        return self.DOCUMENT_PRECEDENCE_ORDER.copy()

# Global instance
precedence_engine = PrecedenceEngine()