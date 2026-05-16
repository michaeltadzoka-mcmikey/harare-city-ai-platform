"""
Dashboard Client for Harare City Council LLM Gateway v5.6.2
Sends metrics and events to dashboard, including intelligence metrics.
Now includes API key for authenticated endpoints.
"""

import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

class DashboardClient:
    """
    Sends metrics and events to the dashboard.
    API key is used for authenticated endpoints (e.g., report submission).
    """

    def __init__(
        self,
        dashboard_url: str = "http://localhost:5000",
        api_key: str = "",
        timeout: int = 10,
        enabled: bool = True,
        redact_pii: bool = True
    ):
        self.url = dashboard_url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout
        self.enabled = enabled
        self.redact_pii = redact_pii
        self.client = httpx.AsyncClient(timeout=timeout)

        if enabled:
            logger.info(f"✓ Dashboard client initialized: {dashboard_url}")

    # ===== Existing methods (with authentication where needed) =====

    async def log_conversation(
        self,
        session_id: str,
        user_message: str,
        bot_response: str,
        metadata: Dict[str, Any]
    ):
        if not self.enabled:
            return
        try:
            if self.redact_pii:
                user_message = self._redact_pii(user_message)
            payload = {
                "timestamp": datetime.utcnow().isoformat(),
                "session_id": session_id,
                "user_message": user_message,
                "bot_response": bot_response,
                "metadata": metadata
            }
            await self.client.post(f"{self.url}/api/conversations", json=payload)
        except Exception as e:
            logger.error(f"Failed to log conversation: {e}")

    async def log_knowledge_gap(
        self,
        query: str,
        gap_type: str,
        confidence: float,
        suggested_action: Optional[str] = None
    ):
        if not self.enabled:
            return
        try:
            payload = {
                "timestamp": datetime.utcnow().isoformat(),
                "query": query,
                "gap_type": gap_type,
                "confidence": confidence,
                "suggested_action": suggested_action
            }
            await self.client.post(f"{self.url}/api/knowledge_gaps", json=payload)
            logger.info(f"Knowledge gap logged: {gap_type}")
        except Exception as e:
            logger.error(f"Failed to log knowledge gap: {e}")

    async def send_expired_doc_count(self, count: int, session_id: str):
        if not self.enabled or count == 0:
            return
        try:
            payload = {
                "timestamp": datetime.utcnow().isoformat(),
                "metric": "expired_documents_filtered",
                "value": count,
                "session_id": session_id
            }
            await self.client.post(f"{self.url}/api/metrics", json=payload)
        except Exception as e:
            logger.error(f"Failed to send expired doc count: {e}")

    async def send_missing_validity_count(self, count: int, session_id: str):
        if not self.enabled or count == 0:
            return
        try:
            payload = {
                "timestamp": datetime.utcnow().isoformat(),
                "metric": "documents_missing_validity",
                "value": count,
                "session_id": session_id
            }
            await self.client.post(f"{self.url}/api/metrics", json=payload)
        except Exception as e:
            logger.error(f"Failed to send missing validity count: {e}")

    async def send_service_update_injection(
        self,
        injected: bool,
        skipped: bool,
        update_id: str,
        session_id: str
    ):
        if not self.enabled:
            return
        try:
            payload = {
                "timestamp": datetime.utcnow().isoformat(),
                "metric": "service_update_injection",
                "injected": injected,
                "skipped": skipped,
                "update_id": update_id,
                "session_id": session_id
            }
            await self.client.post(f"{self.url}/api/metrics", json=payload)
        except Exception as e:
            logger.error(f"Failed to send service update injection: {e}")

    async def send_conflict_resolution(
        self,
        method: str,
        scope_overlap: bool,
        doc_ids: List[str],
        session_id: str
    ):
        if not self.enabled:
            return
        try:
            payload = {
                "timestamp": datetime.utcnow().isoformat(),
                "metric": "conflict_resolution",
                "method": method,
                "scope_overlap": scope_overlap,
                "document_count": len(doc_ids),
                "session_id": session_id
            }
            await self.client.post(f"{self.url}/api/metrics", json=payload)
        except Exception as e:
            logger.error(f"Failed to send conflict resolution: {e}")

    async def send_pinned_override_activation(
        self,
        sufficient: bool,
        override_id: str,
        retrieval_confidence: float,
        embedding_similarity: float,
        slots_complete: bool,
        session_id: str
    ):
        if not self.enabled:
            return
        try:
            payload = {
                "timestamp": datetime.utcnow().isoformat(),
                "metric": "pinned_override_activation",
                "sufficient": sufficient,
                "override_id": override_id,
                "retrieval_confidence": retrieval_confidence,
                "embedding_similarity": embedding_similarity,
                "slots_complete": slots_complete,
                "session_id": session_id
            }
            await self.client.post(f"{self.url}/api/metrics", json=payload)
        except Exception as e:
            logger.error(f"Failed to send pinned override activation: {e}")

    async def send_confidence_breakdown(
        self,
        retrieval: float,
        authority: float,
        freshness: float,
        composite: float,
        band: str,
        session_id: str
    ):
        if not self.enabled:
            return
        try:
            payload = {
                "timestamp": datetime.utcnow().isoformat(),
                "metric": "confidence_breakdown",
                "retrieval_confidence": retrieval,
                "authority_confidence": authority,
                "freshness_confidence": freshness,
                "composite_confidence": composite,
                "band": band,
                "session_id": session_id
            }
            await self.client.post(f"{self.url}/api/metrics", json=payload)
        except Exception as e:
            logger.error(f"Failed to send confidence breakdown: {e}")

    async def send_emergency_mode_activation(
        self,
        mode: str,
        authorized_by: str,
        duration_hours: int,
        affected_areas: List[str]
    ):
        if not self.enabled:
            return
        try:
            payload = {
                "timestamp": datetime.utcnow().isoformat(),
                "event": "emergency_mode_activated",
                "mode": mode,
                "authorized_by": authorized_by,
                "duration_hours": duration_hours,
                "affected_areas": affected_areas
            }
            await self.client.post(f"{self.url}/api/events", json=payload)
            logger.warning(f"Emergency mode activation logged: {mode}")
        except Exception as e:
            logger.error(f"Failed to send emergency activation: {e}")

    async def send_citizen_feedback(
        self,
        feedback_type: str,
        question: str,
        user_id: str,
        details: Optional[str] = None
    ):
        if not self.enabled:
            return
        try:
            payload = {
                "timestamp": datetime.utcnow().isoformat(),
                "feedback_type": feedback_type,
                "question": question,
                "user_id": user_id,
                "details": details
            }
            await self.client.post(f"{self.url}/api/feedback", json=payload)
        except Exception as e:
            logger.error(f"Failed to send citizen feedback: {e}")

    async def submit_report(self, report_data: dict) -> Optional[str]:
        if not self.enabled:
            return None
        url = f"{self.url}/api/reports"
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        try:
            response = await self.client.post(url, json=report_data, headers=headers)
            if response.status_code in (200, 201):
                data = response.json()
                return data.get("reference_id")
            else:
                logger.error(f"Failed to submit report: HTTP {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error submitting report: {e}")
            return None

    async def get_report_status(self, reference_id: str) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        url = f"{self.url}/api/reports/status?ref={reference_id}"
        try:
            response = await self.client.get(url, timeout=self.timeout)
            if response.status_code == 200:
                return response.json()
            elif response.status_code == 404:
                return {"status": "Not found", "last_update": ""}
            else:
                logger.error(f"Status check failed: HTTP {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error getting report status: {e}")
            return None

    # ===== Intelligence metrics methods (unchanged) =====

    async def send_satisfaction(self, session_id: str, rating: int):
        if not self.enabled:
            return
        try:
            payload = {
                "timestamp": datetime.utcnow().isoformat(),
                "session_id": session_id,
                "rating": rating
            }
            await self.client.post(f"{self.url}/api/metrics/satisfaction", json=payload)
        except Exception as e:
            logger.error(f"Failed to send satisfaction: {e}")

    async def send_clarification_rate(self, stats: Dict):
        if not self.enabled:
            return
        try:
            payload = {
                "timestamp": datetime.utcnow().isoformat(),
                "stats": stats
            }
            await self.client.post(f"{self.url}/api/metrics/clarification", json=payload)
        except Exception as e:
            logger.error(f"Failed to send clarification rate: {e}")

    async def send_recurrence_rate(self, stats: Dict):
        if not self.enabled:
            return
        try:
            payload = {
                "timestamp": datetime.utcnow().isoformat(),
                "stats": stats
            }
            await self.client.post(f"{self.url}/api/metrics/recurrence", json=payload)
        except Exception as e:
            logger.error(f"Failed to send recurrence rate: {e}")

    async def send_benchmark_score(self, score: float, date: str):
        if not self.enabled:
            return
        try:
            payload = {
                "timestamp": datetime.utcnow().isoformat(),
                "score": score,
                "benchmark_date": date
            }
            await self.client.post(f"{self.url}/api/metrics/benchmark", json=payload)
        except Exception as e:
            logger.error(f"Failed to send benchmark score: {e}")

    def _redact_pii(self, text: str) -> str:
        import re
        text = re.sub(r'\b\d{10,}\b', '[PHONE]', text)
        text = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL]', text)
        text = re.sub(r'\b\d{2}-\d{6,7}[A-Z]\d{2}\b', '[ID]', text)
        return text

    async def close(self):
        await self.client.aclose()