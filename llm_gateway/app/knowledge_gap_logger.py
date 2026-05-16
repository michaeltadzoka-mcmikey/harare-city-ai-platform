"""
Knowledge Gap Logger for Harare Chatbot
Tracks questions that the bot cannot answer well for continuous improvement.
Now sends to the Dashboard's inbound endpoint with proper API key expansion.
"""

import httpx
import os
from typing import Dict, Any, Optional
import logging
from datetime import datetime
import json

logger = logging.getLogger(__name__)

class KnowledgeGapLogger:
    """
    Logs questions that indicate knowledge gaps for dashboard tracking.
    """

    def __init__(self, dashboard_url: str = "http://localhost:5000", api_key: str = ""):
        self.dashboard_url = dashboard_url.rstrip('/')
        # Expand environment variable if it starts with ${...}
        if api_key and api_key.startswith("${") and api_key.endswith("}"):
            env_var = api_key[2:-1]
            api_key = os.getenv(env_var, "")
        self.api_key = api_key
        self.logged_gaps = set()  # Prevent duplicate logging in same session

    async def log_gap(
        self,
        question: str,
        response: str,
        user_id: str,
        session_id: str,
        source: str,
        confidence: float = 0.0,
        metadata: Optional[Dict] = None,
        dashboard_client=None  # kept for compatibility
    ):
        """
        Log a knowledge gap to the dashboard using the inbound endpoint.
        """
        gap_signature = f"{question.lower().strip()}_{session_id}"
        if gap_signature in self.logged_gaps:
            return

        # Determine gap type based on confidence and response
        if confidence < 0.3:
            gap_type = "low_confidence"
        elif "couldn't generate" in response.lower() or "sorry" in response.lower():
            gap_type = "no_match"
        else:
            gap_type = "unknown"

        payload = {
            "query": question,
            "gap_type": gap_type,
            "confidence": confidence,
            "suggested_action": f"Source: {source}, Response preview: {response[:200]}"
        }

        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key

        url = f"{self.dashboard_url}/knowledge-gaps/api/inbound"
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                if resp.status_code in (200, 201):
                    self.logged_gaps.add(gap_signature)
                    logger.info(f"Knowledge gap logged: {question[:50]}...")
                else:
                    logger.warning(f"Failed to log knowledge gap: HTTP {resp.status_code} - {resp.text}")
        except Exception as e:
            logger.error(f"Error logging knowledge gap: {e}")

# Global instance will be set in main.py
gap_logger = None