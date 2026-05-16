"""
Workflow Orchestrator for Harare Chatbot Gateway v5.3
Intelligent routing and service update injection
"""

import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date

logger = logging.getLogger(__name__)

class WorkflowOrchestrator:
    """
    Routes incoming messages and orchestrates the complete workflow.

    Responsibilities:
    - Determine primary workflow (RAG, RASA, out-of-domain)
    - Apply service update injection
    - Check for pinned override short-circuit
    - Coordinate with precedence engine
    """

    def __init__(
        self,
        precedence_engine,
        override_manager,
        config: Optional[Dict] = None
    ):
        self.precedence_engine = precedence_engine
        self.override_manager = override_manager
        self.config = config or {}

        logger.info("Workflow Orchestrator initialized")

    def determine_workflow(
        self,
        message: str,
        intent: str,
        session_context: Dict[str, Any]
    ) -> str:
        message_lower = message.lower()
        if session_context.get("in_rasa_form"):
            logger.debug("User in active form - routing to rasa")
            return "rasa_report"
        chitchat_intents = ["greeting", "farewell", "chitchat"]
        if intent in chitchat_intents:
            return "chitchat"
        report_keywords = [
            "report", "issue", "problem", "pothole", "leak",
            "garbage", "broken", "damaged", "complaint"
        ]
        if intent == "start_report" or any(kw in message_lower for kw in report_keywords):
            return "rasa_report"
        info_keywords = [
            "what", "how", "when", "where", "tell me",
            "requirement", "document", "fee", "cost", "schedule"
        ]
        if intent == "information_request" or any(kw in message_lower for kw in info_keywords):
            return "rag_knowledge"
        return "rag_knowledge"

    def inject_service_updates(
        self,
        documents: List[Dict[str, Any]],
        user_location: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], bool, bool]:
        """
        Inject active service updates before procedure documents.

        Returns:
            Tuple of (reordered_documents, injected_flag, skipped_flag)
        """
        today = date.today()

        # Find service updates
        service_updates = [
            doc for doc in documents
            if doc.get("content_type") == "service_update"
        ]

        if not service_updates:
            return documents, False, False

        # Find procedure documents
        procedures = [
            doc for doc in documents
            if doc.get("content_type") == "procedure"
        ]

        if not procedures:
            return documents, False, False

        # Check each service update
        updates_to_inject = []
        any_skipped = False

        for update in service_updates:
            # Check validity
            valid_from = update.get("valid_from")
            valid_to = update.get("valid_to")

            if valid_from and valid_to:
                try:
                    valid_from_date = self._parse_date(valid_from)
                    valid_to_date = self._parse_date(valid_to)

                    if not (valid_from_date <= today <= valid_to_date):
                        logger.debug(f"Service update {update.get('id')} not valid now")
                        continue
                except:
                    logger.warning(f"Could not parse dates for update {update.get('id')}")
                    continue

            # Check location match
            location_scope = update.get("location_scope", [])
            if isinstance(location_scope, str):
                location_scope = [location_scope] if location_scope != "council-wide" else []

            if location_scope and user_location:
                if user_location not in location_scope:
                    logger.debug(f"Service update {update.get('id')} location mismatch")
                    continue

            # Check for active override
            overrides = self.override_manager.check_overrides(document=update)
            if any(o["override_type"] in ["freeze", "suspension"] for o in overrides):
                logger.debug(f"Service update {update.get('id')} has active override")
                continue

            # Check if already ahead of procedures
            try:
                update_index = documents.index(update)
            except ValueError:
                continue

            first_procedure_index = None
            for i, doc in enumerate(documents):
                if doc.get("content_type") == "procedure":
                    first_procedure_index = i
                    break

            if first_procedure_index is not None and update_index < first_procedure_index:
                logger.debug(f"Service update {update.get('id')} already ahead - skipping injection")
                any_skipped = True
                continue

            updates_to_inject.append(update)

        if not updates_to_inject:
            return documents, False, any_skipped

        # Perform injection: remove from current position, insert before first procedure
        documents_copy = documents.copy()
        for update in updates_to_inject:
            documents_copy.remove(update)

        # Find new first procedure index
        first_procedure_index = None
        for i, doc in enumerate(documents_copy):
            if doc.get("content_type") == "procedure":
                first_procedure_index = i
                break

        if first_procedure_index is not None:
            for update in reversed(updates_to_inject):
                documents_copy.insert(first_procedure_index, update)

            logger.info(f"Injected {len(updates_to_inject)} service update(s) before procedures")
            return documents_copy, True, any_skipped

        return documents, False, any_skipped

    def check_pinned_short_circuit(
        self,
        documents: List[Dict[str, Any]],
        query: str,
        query_embedding: Optional[List[float]] = None,
        required_slots: Optional[List[str]] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]], Dict[str, Any]]:
        """Check if a pinned document can short-circuit normal processing."""
        pinned_docs = [doc for doc in documents if doc.get("is_pinned")]
        if not pinned_docs:
            return False, None, {}

        for doc in pinned_docs:
            is_sufficient, breakdown = self.override_manager.is_pinned_and_sufficient(
                doc,
                query,
                query_embedding,
                required_slots
            )
            if is_sufficient:
                logger.info(f"Pinned document {doc.get('id')} is sufficient - short-circuiting")
                return True, doc, breakdown

        logger.debug("Pinned documents found but none are sufficient")
        return False, None, {}

    def route_to_rag(
        self,
        message: str,
        session_id: str,
        location: Optional[str] = None,
        emergency_mode: Optional[str] = None
    ) -> Dict[str, Any]:
        return {
            "workflow": "rag_knowledge",
            "message": message,
            "session_id": session_id,
            "location": location,
            "emergency_mode": emergency_mode,
            "top_k": 7,
            "min_confidence": 0.3
        }

    def route_to_rasa(
        self,
        message: str,
        session_id: str
    ) -> Dict[str, Any]:
        return {
            "workflow": "rasa_report",
            "message": message,
            "session_id": session_id
        }

    def _parse_date(self, date_str: Any) -> date:
        if isinstance(date_str, date):
            return date_str
        if isinstance(date_str, datetime):
            return date_str.date()
        if isinstance(date_str, str):
            try:
                return datetime.fromisoformat(date_str.replace('Z', '+00:00')).date()
            except:
                for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"]:
                    try:
                        return datetime.strptime(date_str, fmt).date()
                    except:
                        continue
        raise ValueError(f"Cannot parse date: {date_str}")

# Global instance will be set in main.py
workflow_orchestrator = None