from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class SourceMetadata(BaseModel):
    document_id: str
    version: int
    title: str
    department: str
    last_updated: datetime
    confidence_source: str
    locations: List[str]
    # <-- NEW: explanation of why this source was retrieved
    match_reason: Optional[str] = Field(None, description="Why this document matched the query (e.g., location, keyword, semantic)")

class EvidenceItem(BaseModel):
    text: str
    score: float
    metadata: Dict[str, Any] = Field(default_factory=dict)
    # <-- NEW: match reason can also be included here
    match_reason: Optional[str] = None

class Contradiction(BaseModel):
    topic: str
    conflicting_sources: List[str]
    resolution: str
    resolution_basis: str

class QueryResponse(BaseModel):
    query: str
    answer: str
    sources: List[SourceMetadata] = Field(default_factory=list)
    evidence: List[EvidenceItem] = Field(default_factory=list)
    total_results: int = 0
    coverage: str = "none"
    has_knowledge_gap: bool = False
    confidence: float = 0.0
    suggested_actions: List[str] = Field(default_factory=list)
    contradictions: List[Contradiction] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        json_schema_extra = {
            "example": {
                "query": "water connection fee",
                "answer": "The fee for a new water connection is ZWL 5000.",
                "sources": [
                    {
                        "document_id": "WATER-FEES-001",
                        "version": 3,
                        "title": "2024 Water Connection Fees",
                        "department": "Water and Sanitation",
                        "last_updated": "2024-01-15T00:00:00Z",
                        "confidence_source": "Council Resolution 12/2024",
                        "locations": ["Council-wide"],
                        "match_reason": "Semantic similarity (score 0.92) and contains keyword 'fee'"
                    }
                ],
                "total_results": 3,
                "coverage": "full",
                "has_knowledge_gap": False,
                "confidence": 0.95,
                "contradictions": []
            }
        }

class KnowledgeGap(BaseModel):
    query: str
    user_id: Optional[str] = None
    response: str
    confidence: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    suggested_documents: List[str] = Field(default_factory=list)