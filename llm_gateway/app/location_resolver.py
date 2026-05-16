# llm_gateway/app/location_resolver.py
"""
Location Resolver for Harare City Council LLM Gateway v5.3
Normalizes locations, calculates confidence, and manages location mappings
"""

import logging
import yaml
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import re

logger = logging.getLogger(__name__)

class LocationResolver:
    """
    Resolves and normalizes user-provided locations.
    
    Features:
    - Suburb/ward normalization
    - GPS coordinate parsing
    - Fuzzy matching
    - Confidence scoring
    - Location inference from text
    """
    
    def __init__(self, mapping_file: str = "config/location_mapping.yaml"):
        self.mapping_file = Path(mapping_file)
        self.location_data = {}
        self.suburbs = []
        self.wards = []
        self.aliases = {}
        
        self._load_mappings()
        logger.info(f"Location Resolver initialized with {len(self.suburbs)} suburbs")
    
    def _load_mappings(self):
        """Load location mappings from YAML file."""
        try:
            if not self.mapping_file.exists():
                logger.warning(f"Location mapping file not found: {self.mapping_file}")
                self._create_default_mappings()
                return
            
            with open(self.mapping_file, 'r') as f:
                data = yaml.safe_load(f)
            
            self.location_data = data.get('locations', {})
            
            # Build lookup structures
            for location in self.location_data.get('suburbs', []):
                suburb_name = location['name']
                self.suburbs.append(suburb_name.lower())
                
                # Add aliases
                for alias in location.get('aliases', []):
                    self.aliases[alias.lower()] = suburb_name
            
            for ward in self.location_data.get('wards', []):
                self.wards.append(ward['name'].lower())
            
            logger.info(f"Loaded {len(self.suburbs)} suburbs, {len(self.wards)} wards")
            
        except Exception as e:
            logger.error(f"Error loading location mappings: {e}")
            self._create_default_mappings()
    
    def _create_default_mappings(self):
        """Create default Harare location mappings."""
        default_suburbs = [
            "mbare", "highfield", "glen norah", "warren park", "dzivarasekwa",
            "budiriro", "hatcliffe", "epworth", "borrowdale", "mount pleasant",
            "avondale", "mabelreign", "marlborough", "greendale", "highlands",
            "msasa", "workington", "southerton", "ardbennie", "waterfalls"
        ]
        
        self.suburbs = default_suburbs
        self.wards = [f"ward {i}" for i in range(1, 47)]  # Harare has 46 wards
        
        logger.info(f"Using default location mappings: {len(self.suburbs)} suburbs")
    
    def resolve_location(
        self, 
        location_str: Optional[str] = None,
        message: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resolve location from string or infer from message.
        
        Args:
            location_str: Explicit location string
            message: User message to extract location from
            
        Returns:
            Dict with normalized location, confidence, inferred flag
        """
        if location_str:
            # Explicit location provided
            return self._normalize_location(location_str, inferred=False)
        
        if message:
            # Try to infer from message
            inferred_location = self._infer_location_from_message(message)
            if inferred_location:
                return self._normalize_location(
                    inferred_location['location'],
                    inferred=True,
                    inference_confidence=inferred_location['confidence']
                )
        
        # No location found
        return {
            "normalized": None,
            "original": None,
            "confidence": 0.0,
            "inferred": False,
            "type": None,
            "ward": None,
            "disclaimer_needed": False
        }
    
    def _normalize_location(
        self, 
        location_str: str, 
        inferred: bool = False,
        inference_confidence: float = 1.0
    ) -> Dict[str, Any]:
        """
        Normalize a location string to standard format.
        
        Args:
            location_str: Location string to normalize
            inferred: Whether location was inferred from message
            inference_confidence: Confidence of inference
            
        Returns:
            Normalized location dict
        """
        location_lower = location_str.lower().strip()
        
        # Check for exact suburb match
        if location_lower in self.suburbs:
            return {
                "normalized": location_lower.title(),
                "original": location_str,
                "confidence": 1.0 if not inferred else inference_confidence,
                "inferred": inferred,
                "type": "suburb",
                "ward": self._get_ward_for_suburb(location_lower),
                "disclaimer_needed": inferred
            }
        
        # Check aliases
        if location_lower in self.aliases:
            normalized = self.aliases[location_lower]
            return {
                "normalized": normalized.title(),
                "original": location_str,
                "confidence": 0.9 if not inferred else inference_confidence * 0.9,
                "inferred": inferred,
                "type": "suburb",
                "ward": self._get_ward_for_suburb(normalized.lower()),
                "disclaimer_needed": inferred
            }
        
        # Check for ward
        if location_lower.startswith('ward '):
            return {
                "normalized": location_lower.title(),
                "original": location_str,
                "confidence": 1.0 if not inferred else inference_confidence,
                "inferred": inferred,
                "type": "ward",
                "ward": location_lower,
                "disclaimer_needed": inferred
            }
        
        # Fuzzy matching
        fuzzy_match = self._fuzzy_match(location_lower)
        if fuzzy_match:
            return {
                "normalized": fuzzy_match['match'].title(),
                "original": location_str,
                "confidence": fuzzy_match['confidence'] * (inference_confidence if inferred else 1.0),
                "inferred": inferred,
                "type": "suburb",
                "ward": self._get_ward_for_suburb(fuzzy_match['match']),
                "disclaimer_needed": True  # Always show disclaimer for fuzzy matches
            }
        
        # Council-wide (no specific location)
        if any(term in location_lower for term in ['harare', 'city', 'council-wide', 'all']):
            return {
                "normalized": "Harare City (Council-wide)",
                "original": location_str,
                "confidence": 1.0,
                "inferred": inferred,
                "type": "council-wide",
                "ward": None,
                "disclaimer_needed": False
            }
        
        # Unknown location
        return {
            "normalized": location_str,
            "original": location_str,
            "confidence": 0.3,
            "inferred": inferred,
            "type": "unknown",
            "ward": None,
            "disclaimer_needed": True
        }
    
    def _infer_location_from_message(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Infer location from message text.
        
        Args:
            message: User message
            
        Returns:
            Dict with location and confidence, or None
        """
        message_lower = message.lower()
        
        # Look for "in [location]" pattern
        in_pattern = r'\bin\s+([a-z\s]+?)(?:\s+(?:area|suburb|ward))?(?:\s|$|,|\.|;)'
        matches = re.finditer(in_pattern, message_lower)
        
        for match in matches:
            location_candidate = match.group(1).strip()
            
            # Check if it's a known location
            if location_candidate in self.suburbs:
                return {
                    "location": location_candidate,
                    "confidence": 0.8
                }
            
            if location_candidate in self.aliases:
                return {
                    "location": self.aliases[location_candidate],
                    "confidence": 0.75
                }
        
        # Look for standalone suburb names
        for suburb in self.suburbs:
            if suburb in message_lower:
                # Ensure it's a word boundary
                pattern = r'\b' + re.escape(suburb) + r'\b'
                if re.search(pattern, message_lower):
                    return {
                        "location": suburb,
                        "confidence": 0.7
                    }
        
        return None
    
    def _fuzzy_match(self, location_str: str) -> Optional[Dict[str, Any]]:
        """
        Fuzzy match location string to known locations.
        
        Args:
            location_str: Location to match
            
        Returns:
            Dict with match and confidence, or None
        """
        # Simple Levenshtein-like matching
        best_match = None
        best_score = 0
        
        for suburb in self.suburbs:
            score = self._similarity_score(location_str, suburb)
            if score > best_score and score > 0.6:  # Threshold
                best_score = score
                best_match = suburb
        
        if best_match:
            return {
                "match": best_match,
                "confidence": best_score * 0.7  # Penalty for fuzzy match
            }
        
        return None
    
    def _similarity_score(self, str1: str, str2: str) -> float:
        """
        Calculate similarity score between two strings.
        
        Simple implementation - in production use python-Levenshtein or similar.
        """
        # Character overlap ratio
        set1 = set(str1)
        set2 = set(str2)
        
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def _get_ward_for_suburb(self, suburb: str) -> Optional[str]:
        """
        Get ward for a suburb.
        
        Args:
            suburb: Suburb name (lowercase)
            
        Returns:
            Ward name or None
        """
        # Look up in location data
        for location in self.location_data.get('suburbs', []):
            if location['name'].lower() == suburb:
                return location.get('ward')
        
        # Default mapping (simplified)
        ward_map = {
            "mbare": "Ward 8",
            "highfield": "Ward 7",
            "glen norah": "Ward 6",
            "budiriro": "Ward 5",
            "dzivarasekwa": "Ward 38"
        }
        
        return ward_map.get(suburb)
    
    def generate_disclaimer(
        self, 
        location_info: Dict[str, Any]
    ) -> Optional[str]:
        """
        Generate location disclaimer if needed.
        
        Args:
            location_info: Result from resolve_location
            
        Returns:
            Disclaimer text or None
        """
        if not location_info.get('disclaimer_needed'):
            return None
        
        normalized = location_info['normalized']
        confidence = location_info['confidence']
        
        if location_info['inferred']:
            return (
                f"*Assuming this applies to {normalized}. "
                f"If your location is different, your answer may vary.*"
            )
        elif confidence < 0.7:
            return (
                f"*I interpreted your location as {normalized}. "
                f"If this is incorrect, please specify your location.*"
            )
        
        return None

# Global instance
location_resolver = LocationResolver()