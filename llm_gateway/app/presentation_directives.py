# llm_gateway/app/presentation_directives.py
"""
Presentation Directives Parser for Harare City Council LLM Gateway v5.3
Parses and validates RAG 2.1 presentation metadata
"""

import logging
from typing import Dict, Any, Optional, List
from pydantic import BaseModel, Field, ValidationError

logger = logging.getLogger(__name__)

class PresentationDirectives(BaseModel):
    """Schema for RAG presentation directives."""
    template: str = Field(default="default", description="Template to use for response")
    required_slots: List[str] = Field(default_factory=list, description="Required template slots")
    show_confidence_breakdown: bool = Field(default=False, description="Show confidence components to user")
    show_sources: bool = Field(default=True, description="Show source attribution")
    show_validity: bool = Field(default=True, description="Show validity dates")
    response_style: Optional[str] = Field(None, description="Response style override")
    max_length: Optional[int] = Field(None, description="Maximum response length")

class DirectivesParser:
    """Parses and validates presentation directives from RAG responses."""
    
    def parse(self, rag_response: Dict[str, Any]) -> Optional[PresentationDirectives]:
        """
        Parse presentation directives from RAG response.
        
        Args:
            rag_response: RAG response dictionary
            
        Returns:
            Validated directives or None if not present/invalid
        """
        # Check for presentation block
        presentation = rag_response.get("presentation")
        
        if not presentation:
            logger.debug("No presentation directives in RAG response")
            return None
        
        # Validate directives
        try:
            directives = presentation.get("directives", {})
            parsed = PresentationDirectives(**directives)
            
            logger.info(
                f"Parsed presentation directives: template={parsed.template}, "
                f"required_slots={len(parsed.required_slots)}, "
                f"show_confidence={parsed.show_confidence_breakdown}"
            )
            
            return parsed
            
        except ValidationError as e:
            logger.error(f"Invalid presentation directives: {e}")
            return None
        except Exception as e:
            logger.error(f"Error parsing presentation directives: {e}")
            return None
    
    def validate_slots(
        self, 
        directives: PresentationDirectives,
        available_data: Dict[str, Any]
    ) -> tuple[bool, List[str]]:
        """
        Validate that all required slots are present in data.
        
        Args:
            directives: Parsed directives
            available_data: Data available for template
            
        Returns:
            Tuple of (all_present, missing_slots)
        """
        missing = []
        
        for slot in directives.required_slots:
            if slot not in available_data:
                missing.append(slot)
        
        if missing:
            logger.warning(f"Missing required template slots: {missing}")
        
        return len(missing) == 0, missing

# Global instance
directives_parser = DirectivesParser()