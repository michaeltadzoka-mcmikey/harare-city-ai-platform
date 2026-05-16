"""
Enhanced data models for Harare Chatbot Gateway v3.0
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class ChatRequest(BaseModel):
    message: str = Field(..., description="User's message")
    user_id: str = Field(default="anonymous", description="User identifier")
    session_id: Optional[str] = Field(None, description="Session identifier for conversation continuity")
    source: str = Field(default="web", description="Source of message: web, whatsapp, admin")
    reset_session: bool = Field(default=False, description="Whether to reset the session")
    user_preferences: Optional[Dict[str, Any]] = Field(None, description="User preferences (future use)")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")

class ChatResponse(BaseModel):
    response: str = Field(..., description="Bot's response to user")
    intent: str = Field(default="information_request", description="Detected intent")
    needs_action: bool = Field(default=False, description="Whether further action/input is needed")
    source: str = Field(default="llm", description="Response source")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Response metadata")
    session_id: Optional[str] = Field(None, description="Session identifier for tracking")