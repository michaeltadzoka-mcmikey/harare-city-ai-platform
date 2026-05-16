from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class LocationContext(BaseModel):
    suburb: Optional[str] = None
    ward: Optional[str] = None

class QueryContext(BaseModel):
    location: Optional[LocationContext] = Field(None)
    inferred_time_intent: str = "current"
    historical: bool = False

class QueryRequest(BaseModel):
    query: str = Field(..., min_length=2)
    session_id: Optional[str] = None
    context: QueryContext = Field(default_factory=QueryContext)
    # <-- NEW: plain‑text conversation summary for context‑aware retrieval
    conversation_context: Optional[str] = Field(None, description="Brief summary of the conversation so far")
    top_k: Optional[int] = 5
    threshold: Optional[float] = 0.3
    filters: Optional[Dict[str, Any]] = None

class QuerySuggestion(BaseModel):
    query: str
    suggestions: List[str]