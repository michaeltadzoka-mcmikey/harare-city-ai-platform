"""
Clean Response Formatter - Formats RAG responses without showing source paths
"""
import re
from typing import List, Dict, Any
import os

class CleanResponseFormatter:
    """Formats RAG responses without showing source paths."""
    
    @staticmethod
    def format_response(query: str, evidence_chunks: List[Dict]) -> Dict[str, Any]:
        """Format evidence into clean, user-friendly response."""
        
        if not evidence_chunks:
            return CleanResponseFormatter._format_no_results(query)
        
        # Build structured response
        structured_response = CleanResponseFormatter._structure_information(evidence_chunks)
        
        # Check if response indicates knowledge gap
        has_gap = CleanResponseFormatter._detect_knowledge_gap(query, structured_response)
        
        return {
            "answer": structured_response,
            "internal_sources": CleanResponseFormatter._extract_internal_sources(evidence_chunks),
            "has_knowledge_gap": has_gap,
            "confidence": CleanResponseFormatter._calculate_confidence(evidence_chunks),
            "suggested_actions": CleanResponseFormatter._suggest_actions(query, evidence_chunks)
        }
    
    @staticmethod
    def _structure_information(chunks: List[Dict]) -> str:
        """Structure information in clear, bullet-point format."""
        
        # Extract and clean key points
        key_points = []
        seen_points = set()
        
        for chunk in chunks:
            text = chunk.get("text", "")
            
            # Clean the text
            clean_text = CleanResponseFormatter._clean_chunk_text(text)
            
            # Extract main points (first 1-2 sentences)
            points = CleanResponseFormatter._extract_main_points(clean_text)
            
            for point in points:
                # Deduplicate and add
                normalized = CleanResponseFormatter._normalize_text(point)
                if normalized not in seen_points and len(point) > 10:
                    key_points.append(point)
                    seen_points.add(normalized)
        
        # Limit to 5 key points
        key_points = key_points[:5]
        
        # Format response
        if not key_points:
            return "I couldn't extract clear information from our documents."
        
        response_parts = ["Based on Harare City Council information:"]
        
        for i, point in enumerate(key_points, 1):
            response_parts.append(f"{i}. {point}")
        
        # Add conclusion
        if len(chunks) > 3:
            response_parts.append("\nFor complete information, visit the City Council offices or website.")
        
        return "\n".join(response_parts)
    
    @staticmethod
    def _clean_chunk_text(text: str) -> str:
        """Remove source references and formatting artifacts."""
        # Remove file path references
        text = re.sub(r'Source:.*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'File:.*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'Document:.*$', '', text, flags=re.MULTILINE)
        
        # Remove file extensions in parentheses
        text = re.sub(r'\(.*\.(txt|pdf|docx|doc)\)', '', text)
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove metadata markers
        text = re.sub(r'\[.*?\]', '', text)
        text = re.sub(r'\{.*?\}', '', text)
        
        return text.strip()
    
    @staticmethod
    def _extract_main_points(text: str) -> List[str]:
        """Extract main points from text."""
        # Split into sentences
        sentences = re.split(r'[.!?]+', text)
        
        points = []
        for sentence in sentences:
            sentence = sentence.strip()
            if (len(sentence) > 15 and 
                len(sentence.split()) >= 3 and
                not any(word in sentence.lower() for word in 
                       ["source:", "file:", "document:", "chapter", "section"])):
                
                # Ensure proper capitalization
                if sentence and not sentence[0].isupper():
                    sentence = sentence[0].upper() + sentence[1:]
                
                # Add period if missing
                if not sentence.endswith('.'):
                    sentence += '.'
                
                points.append(sentence)
        
        return points[:3]  # Return top 3 points
    
    @staticmethod
    def _normalize_text(text: str) -> str:
        """Normalize text for deduplication."""
        return re.sub(r'\s+', ' ', text.lower().strip())
    
    @staticmethod
    def _extract_internal_sources(chunks: List[Dict]) -> List[str]:
        """Extract source filenames for internal tracking (not shown to user)."""
        sources = []
        for chunk in chunks:
            source = chunk.get("metadata", {}).get("source", "")
            if source:
                # Get just the filename, not full path
                filename = os.path.basename(source)
                if filename not in sources:
                    sources.append(filename)
        return sources
    
    @staticmethod
    def _detect_knowledge_gap(query: str, response: str) -> bool:
        """Detect if response indicates a knowledge gap."""
        gap_indicators = [
            "couldn't extract",
            "don't have",
            "not available",
            "couldn't find",
            "no information",
            "unclear"
        ]
        return any(indicator in response.lower() for indicator in gap_indicators)
    
    @staticmethod
    def _calculate_confidence(chunks: List[Dict]) -> float:
        """Calculate confidence score based on evidence quality."""
        if not chunks:
            return 0.0
        
        # Average score of top chunks
        scores = [chunk.get("score", 0.0) for chunk in chunks[:3]]
        return sum(scores) / len(scores) if scores else 0.0
    
    @staticmethod
    def _suggest_actions(query: str, chunks: List[Dict]) -> List[str]:
        """Suggest actions based on query and results."""
        actions = []
        
        if not chunks:
            actions.append("contact_council")
            actions.append("check_website")
        elif len(chunks) < 3:
            actions.append("visit_office")
        
        return actions
    
    @staticmethod
    def _format_no_results(query: str) -> Dict[str, Any]:
        """Format response when no results found."""
        no_result_responses = [
            f"I don't have specific information about '{query}' in our Harare City Council documents.",
            f"This information isn't available in our current municipal documents.",
            f"I couldn't find details about '{query}' in our council resources."
        ]
        
        import random
        response = random.choice(no_result_responses)
        
        return {
            "answer": response + " You might want to contact the council directly or check our website.",
            "internal_sources": [],
            "has_knowledge_gap": True,
            "confidence": 0.1,
            "suggested_actions": ["contact_council", "check_website"]
        }