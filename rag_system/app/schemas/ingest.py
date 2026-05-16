from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime

class IngestRequest(BaseModel):
    path: Optional[str] = Field(None)
    reindex: bool = False
    validate_domain: bool = True
    override_overlap: bool = False
    override_justification: Optional[str] = None

class IngestResponse(BaseModel):
    message: str
    total_documents: int = 0
    ingested: int = 0
    chunks_created: int = 0
    skipped: int = 0
    validation_failures: List[Dict[str, str]] = Field(default_factory=list)
    version_superseded: bool = False
    overlap_rejected: bool = False
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class IngestStatus(BaseModel):
    status: str = "ready"
    total_files: int = 0
    total_chunks: int = 0
    last_ingestion: Optional[str] = None
    files: List[Dict[str, Any]] = Field(default_factory=list)