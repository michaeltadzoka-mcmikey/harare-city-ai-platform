from fastapi import APIRouter, HTTPException, Body
from datetime import datetime, date, timedelta
from typing import List, Dict, Any, Optional
import json
import logging
import re

from app.core.index import VectorIndex
from app.core.coverage import CoverageScorer
from app.core.ingestion_validator import IngestionValidator
from app.core.chunker_v2 import DocumentChunker        # <-- NEW import
from app.config import config
from app.schemas.admin import (
    OverrideRequest, CoverageScoreResponse, KnowledgeGapReport,
    AuditEntry, ExpiringDocument, ArchivedDocument,
    ValidationResult, ConflictAnalyticsResponse, OverrideItem   # <-- NEW
)
from app.utils.audit import read_audit_log
from app.utils.contradiction_logger import get_conflict_analytics

router = APIRouter(prefix="/admin", tags=["admin"])
logger = logging.getLogger(__name__)

@router.get("/stats/coverage", response_model=List[CoverageScoreResponse])
async def get_coverage_scores():
    index = VectorIndex()
    scorer = CoverageScorer(index)
    service_areas = [
        ("Water and Sanitation", "water_connection"),
        ("Finance", "rates_payment"),
        ("Waste Management", "waste_collection"),
        ("Business Licensing", "business_permit"),
    ]
    results = []
    for dept, area in service_areas:
        score = scorer.compute_scs(dept, area)
        results.append(CoverageScoreResponse(
            department=dept,
            service_area=area,
            score=score,
            breakdown={}
        ))
    return results

@router.get("/stats/knowledge-gaps", response_model=List[KnowledgeGapReport])
async def get_knowledge_gaps(limit: int = 100):
    gaps = []
    gap_file = config.KNOWLEDGE_GAP_LOG_FILE
    if gap_file.exists():
        with open(gap_file, 'r') as f:
            try:
                data = json.load(f)
                gaps = data[-limit:]
            except json.JSONDecodeError:
                gaps = []
    return gaps

@router.get("/audit", response_model=List[AuditEntry])
async def get_audit_log(limit: int = 100):
    entries = read_audit_log(limit)
    return entries

@router.post("/override")
async def create_override(request: OverrideRequest):
    from app.utils.audit import audit_log
    audit_log(
        action="OVERRIDE",
        user="admin",
        document_id=request.document_id,
        version=None,
        details={"justification": request.justification}
    )
    return {"status": "logged"}

@router.get("/documents/expiring", response_model=List[ExpiringDocument])
async def get_expiring_documents(days: int = 30):
    index = VectorIndex()
    today = date.today()
    expiry_threshold = today + timedelta(days=days)

    results = index.active_collection.get(include=["metadatas"])
    docs = []
    for meta in results["metadatas"]:
        valid_to_str = meta.get("valid_to")
        if not valid_to_str:
            continue
        try:
            valid_to = date.fromisoformat(valid_to_str)
        except ValueError:
            continue
        if valid_to <= expiry_threshold:
            days_left = (valid_to - today).days
            docs.append(ExpiringDocument(
                document_id=meta.get("document_id", "unknown"),
                title=meta.get("title", ""),
                department=meta.get("department", ""),
                valid_to=datetime.combine(valid_to, datetime.min.time()),
                owner_email=meta.get("owner_email", ""),
                days_left=days_left
            ))
    return docs

@router.get("/documents/archive", response_model=List[ArchivedDocument])
async def get_archive(limit: int = 100):
    index = VectorIndex()
    results = index.archive_collection.get(limit=limit, include=["metadatas"])
    docs = []
    for meta in results["metadatas"]:
        docs.append(ArchivedDocument(
            document_id=meta.get("document_id", "unknown"),
            version=int(meta.get("version", 1)),
            title=meta.get("title", ""),
            archived_at=datetime.utcnow()
        ))
    return docs

@router.get("/config")
async def get_config():
    return {
        "embedding_model": config.EMBEDDING_MODEL,
        "chunk_size": config.CHUNK_SIZE,
        "chunk_overlap": config.CHUNK_OVERLAP,
        "location_boost_factor": config.LOCATION_BOOST_FACTOR,
        "service_update_boost": getattr(config, 'SERVICE_UPDATE_BOOST', 1.3),
        "pinned_override_boost": getattr(config, 'PINNED_OVERRIDE_BOOST', 2.0),
        "supported_extensions": list(config.SUPPORTED_EXTENSIONS),
        "required_metadata_fields": config.REQUIRED_METADATA_FIELDS,
        "content_types": list(config.CONTENT_TYPES),
        "service_areas": list(config.SERVICE_AREAS),
        "suburbs": config.SUBURBS,
        "validity_check_enabled": config.VALIDITY_CHECK_ENABLED,
        "pinned_governance_fields": getattr(config, 'PINNED_GOVERNANCE_FIELDS', [])
    }

# Real-time validation endpoint
@router.post("/validate", response_model=ValidationResult)
async def validate_document(document: Dict[str, Any] = Body(...)):
    try:
        if "content" not in document or "metadata" not in document:
            raise HTTPException(status_code=400, detail="Document must have 'content' and 'metadata' fields")

        validator = IngestionValidator()
        is_valid, reason, missing = validator.validate_document(document)

        index = VectorIndex()
        doc_metadata = document["metadata"]
        doc_id = doc_metadata.get("document_id")
        content_type = doc_metadata.get("content_type")
        service_area = doc_metadata.get("service_area")
        valid_from = doc_metadata.get("valid_from")
        valid_to = doc_metadata.get("valid_to")

        duplicate_id = False
        if doc_id:
            where = {"document_id": {"$eq": doc_id}}
            results = index.active_collection.get(where=where, limit=1)
            duplicate_id = len(results["ids"]) > 0

        overlap_detected = False
        overlap_with = None
        if content_type and service_area and valid_from and valid_to:
            try:
                overlap, conflict = index.check_overlap(doc_metadata)
                overlap_detected = overlap
                if conflict:
                    overlap_with = conflict.get("document_id")
            except Exception:
                pass

        id_format_valid = bool(re.match(r'^[A-Z]+-[A-Z]+-\d+$', doc_id)) if doc_id else False
        summary_present = "### Summary" in document.get("content", "")
        content = document.get("content", "")
        headings = re.findall(r'^###\s+', content, re.MULTILINE)
        structured_content = len(headings) > 1

        checklist = {
            "metadata_complete": is_valid and not missing,
            "summary_present": summary_present,
            "structured_content": structured_content,
            "duplicate_id": duplicate_id,
            "overlap_detected": overlap_detected,
            "id_format_valid": id_format_valid
        }

        expiry_days = None
        if valid_to:
            try:
                v_to = date.fromisoformat(valid_to)
                days_left = (v_to - date.today()).days
                if 0 <= days_left <= 30:
                    expiry_days = days_left
            except:
                pass

        return ValidationResult(
            is_valid=is_valid,
            reason=reason,
            missing_fields=missing,
            checklist=checklist,
            overlap_with=overlap_with,
            expiry_days=expiry_days
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Validation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Trigger archive of expired documents
@router.post("/archive-expired")
async def archive_expired_documents():
    try:
        index = VectorIndex()
        today = date.today().isoformat()
        results = index.active_collection.get(include=["metadatas", "documents", "embeddings"])
        expired_ids = []
        expired_metadatas = []
        expired_docs = []
        expired_embeddings = []

        for i, meta in enumerate(results["metadatas"]):
            valid_to_str = meta.get("valid_to")
            if valid_to_str and valid_to_str < today:
                expired_ids.append(results["ids"][i])
                expired_metadatas.append(meta)
                expired_docs.append(results["documents"][i])
                expired_embeddings.append(results["embeddings"][i])

        if expired_ids:
            index.archive_collection.add(
                embeddings=expired_embeddings,
                documents=expired_docs,
                metadatas=expired_metadatas,
                ids=[f"{id}_archived_{datetime.utcnow().isoformat()}" for id in expired_ids]
            )
            index.active_collection.delete(ids=expired_ids)
            logger.info(f"Archived {len(expired_ids)} expired documents")

        return {"archived_count": len(expired_ids)}
    except Exception as e:
        logger.error(f"Archive expired failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Conflict analytics endpoint
@router.get("/conflict-analytics", response_model=ConflictAnalyticsResponse)
async def get_conflict_analytics_endpoint(days: int = 30):
    try:
        # get_conflict_analytics is synchronous – do NOT await
        analytics = get_conflict_analytics(days)
        return ConflictAnalyticsResponse(
            total_conflicts=analytics["total_conflicts"],
            breakdown=ConflictTypeBreakdown(**analytics["breakdown"]),
            by_department=analytics["by_department"],
            period_days=analytics["period_days"]
        )
    except Exception as e:
        logger.error(f"Conflict analytics failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# <-- NEW: Chunk preview endpoint
@router.post("/chunk-preview")
async def chunk_preview(document: Dict[str, Any] = Body(...)):
    """
    Preview how a document will be split into chunks.
    Returns list of chunks with text and token count.
    """
    try:
        if "content" not in document or "metadata" not in document:
            raise HTTPException(status_code=400, detail="Document must have 'content' and 'metadata' fields")

        chunker = DocumentChunker()
        chunks = chunker.chunk_document(document)

        # Simple token count estimation (characters / 4)
        preview = []
        for chunk in chunks:
            preview.append({
                "text": chunk["text"][:200] + "..." if len(chunk["text"]) > 200 else chunk["text"],
                "token_estimate": len(chunk["text"]) // 4,
                "char_count": len(chunk["text"])
            })
        return {"chunks": preview, "strategy": document["metadata"].get("content_type", "unknown")}
    except Exception as e:
        logger.error(f"Chunk preview failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# <-- NEW: Active overrides registry
@router.get("/overrides", response_model=List[OverrideItem])
async def get_active_overrides(limit: int = 100):
    """
    List all active pinned_override documents (valid_to >= today).
    """
    try:
        index = VectorIndex()
        today = date.today().isoformat()
        # Fetch all pinned_override documents from active collection
        results = index.active_collection.get(
            where={"content_type": {"$eq": "pinned_override"}},
            include=["metadatas", "documents"]
        )
        overrides = []
        for i, meta in enumerate(results["metadatas"]):
            valid_to = meta.get("valid_to")
            if valid_to and valid_to >= today:
                # Create content preview
                content = results["documents"][i]
                preview = content[:200] + "..." if len(content) > 200 else content
                overrides.append(OverrideItem(
                    document_id=meta.get("document_id", "unknown"),
                    title=meta.get("title", ""),
                    content=preview,
                    valid_to=valid_to,
                    justification=meta.get("governance_justification"),
                    approval_authority=meta.get("approval_authority"),
                    department=meta.get("department")
                ))
        return overrides[:limit]
    except Exception as e:
        logger.error(f"Failed to fetch overrides: {e}")
        raise HTTPException(status_code=500, detail=str(e))