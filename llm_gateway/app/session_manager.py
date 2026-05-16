"""
Session manager with conversation state, user facts, and expiry.
"""

import json
import uuid
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class SessionManager:
    def __init__(self, config=None):
        if config is None:
            config = {}
        self.timeout = config.get("limits", {}).get("session_expiry_seconds", 3600)
        self.sessions = {}  # in memory; use Redis in production

    def create_session(self, session_id: str, user_id: str, source: str) -> dict:
        session = {
            "session_id": session_id,
            "user_id": user_id,
            "source": source,
            "created_at": datetime.utcnow().isoformat(),
            "last_accessed": datetime.utcnow().isoformat(),
            "conversation_history": [],
            "structured": {
                "user_facts": {},
                "current_task": None,
                "pending_action": None,
                "last_topics": [],
                "turn_count": 0,
                "structured_summary": {}
            }
        }
        self.sessions[session_id] = session
        return session

    def get_session(self, session_id: str) -> dict:
        session = self.sessions.get(session_id)
        if session:
            session["last_accessed"] = datetime.utcnow().isoformat()
        return session

    def get_structured_session(self, session_id: str, user_profile: dict) -> dict:
        session = self.get_session(session_id)
        if not session:
            return {}
        structured = session.get("structured", {}).copy()
        if user_profile:
            user_facts = structured.get("user_facts", {})
            for key, val in user_profile.get("user_facts", {}).items():
                if key not in user_facts:
                    user_facts[key] = val
            structured["user_facts"] = user_facts
        return structured

    def update_structured_session(self, session_id: str, updates: dict):
        session = self.get_session(session_id)
        if session:
            structured = session.get("structured", {})
            structured.update(updates)
            session["structured"] = structured
            session["last_accessed"] = datetime.utcnow().isoformat()

    def add_conversation(self, session_id: str, user_message: str, bot_response: str, intent: str, source: str, metadata: dict):
        session = self.get_session(session_id)
        if session:
            history = session.get("conversation_history", [])
            history.append({
                "timestamp": datetime.utcnow().isoformat(),
                "user": user_message,
                "bot": bot_response,
                "intent": intent,
                "source": source,
                "metadata": metadata
            })
            session["conversation_history"] = history[-20:]
            self.update_structured_session(session_id, {"turn_count": len(history)})

    def get_conversation_history(self, session_id: str, limit: int = 10, as_text: bool = False):
        session = self.get_session(session_id)
        if not session:
            return [] if not as_text else ""
        history = session.get("conversation_history", [])
        if limit:
            history = history[-limit:]
        if as_text:
            return "\n".join([f"User: {h['user']}\nBot: {h['bot']}" for h in history])
        return history

    def get_active_session_count(self) -> int:
        """Return number of sessions that have been accessed within the timeout period."""
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.timeout)
        count = 0
        for sess in self.sessions.values():
            last = datetime.fromisoformat(sess["last_accessed"])
            if last > cutoff:
                count += 1
        return count

    def cleanup_expired_sessions(self):
        now = datetime.utcnow()
        expired = []
        for sid, sess in self.sessions.items():
            last = datetime.fromisoformat(sess["last_accessed"])
            if (now - last).total_seconds() > self.timeout:
                expired.append(sid)
        for sid in expired:
            del self.sessions[sid]
        if expired:
            logger.info(f"Cleaned up {len(expired)} expired sessions")

# Global instance (for backward compatibility; orchestrator uses its own)
session_manager = SessionManager()