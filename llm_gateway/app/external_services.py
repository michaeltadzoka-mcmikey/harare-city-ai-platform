"""
External Services Handler for Harare City Council LLM Gateway v5.6.2
"""

import yaml
import logging
from typing import Dict

logger = logging.getLogger(__name__)

class ExternalServices:
    """Provides canned responses for out-of-domain intents."""

    def __init__(self, config_path: str):
        self.mappings = {}
        try:
            with open(config_path, 'r') as f:
                self.mappings = yaml.safe_load(f)
            logger.info(f"Loaded external services from {config_path}")
        except Exception as e:
            logger.error(f"Failed to load external services: {e}")

    def get_response(self, intent: str) -> str:
        """Return the canned response for a given external intent."""
        return self.mappings.get(intent, "I'm not sure how to help with that. Please contact Harare City Council at 04-700600.")