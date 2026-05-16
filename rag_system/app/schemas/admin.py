from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from datetime import datetime

class OverrideRequest(BaseModel):
    document_id: str
    justification: str

class CoverageScoreResponse(BaseModel):
    department: str
    service_area: str
    score: float
    breakdown: Dict[str, Any]

class KnowledgeGapReport(BaseModel):
    query: str
    user_id: Optional[str]
    timestamp: datetime
    confidence: float
    suggested_documents: List[str]

class AuditEntry(BaseModel):
    timestamp: datetime
    action: str
    user: Optional[str]
    document_id: str
    version: Optional[int]
    details: Dict[str, Any]

class ExpiringDocument(BaseModel):
    document_id: str
    title: str
    department: str
    valid_to: datetime
    owner_email: str
    days_left: int

class ArchivedDocument(BaseModel):
    document_id: str
    version: int
    title: str
    archived_at: datetime

# Validation result for real-time validation
class ValidationResult(BaseModel):
    is_valid: bool
    reason: Optional[str] = None
    missing_fields: List[str] = []
    checklist: Dict[str, bool]
    overlap_with: Optional[str] = None
    expiry_days: Optional[int] = None

# Conflict analytics
class ConflictTypeBreakdown(BaseModel):
    cross_type: int = 0
    same_type: int = 0
    same_type_resolved_by_newer: int = 0
    same_type_resolved_by_version: int = 0
    same_type_resolved_by_authority: int = 0
    precedence_override_count: int = 0

class ConflictAnalyticsResponse(BaseModel):
    total_conflicts: int
    breakdown: ConflictTypeBreakdown
    by_department: Dict[str, int]
    period_days: int

# <-- NEW: Override item for registry
class OverrideItem(BaseModel):
    document_id: str
    title: str
    content: str  # preview snippet
    valid_to: str
    justification: Optional[str] = None
    approval_authority: Optional[str] = None
    department: Optional[str] = None