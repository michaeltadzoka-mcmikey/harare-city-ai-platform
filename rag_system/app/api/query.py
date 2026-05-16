from fastapi import APIRouter, HTTPException
from datetime import datetime, date
import logging
import json

from app.core.index import VectorIndex
from app.core.retriever import Retriever
from app.core.response_formatter import CleanResponseFormatter
from app.core.guardrails import DomainGuardrails
from app.core.contradiction import ContradictionDetector
from app.core.confidence import ConfidenceScorer
from app.schemas.query import QueryRequest, QueryContext
from app.schemas.response import QueryResponse, SourceMetadata, EvidenceItem, Contradiction
from app.config import config
from app.utils.knowledge_gap import log_knowledge_gap
from app.utils.contradiction_logger import log_contradiction

router = APIRouter()
logger = logging.getLogger(__name__)

index = VectorIndex()
retriever = Retriever(index)
formatter = CleanResponseFormatter()
guardrails = DomainGuardrails()
contradiction_detector = ContradictionDetector()
confidence_scorer = ConfidenceScorer()

def parse_locations(locations_str: str) -> list:
    if not locations_str:
        return []
    try:
        return json.loads(locations_str)
    except (json.JSONDecodeError, TypeError):
        return []

@router.post("/query", response_model=QueryResponse)
async def query_documents(request: QueryRequest):
    try:
        # ----- FAST PATH: no documents at all -----
        if index.active_collection.count() == 0:
            logger.info("No documents in active index – returning knowledge gap immediately")
            return QueryResponse(
                query=request.query,
                answer="I couldn't find any information in the current documents.",
                sources=[],
                evidence=[],
                total_results=0,
                coverage="none",
                has_knowledge_gap=True,
                confidence=0.0,
                suggested_actions=["contact_council", "check_website"],
                contradictions=[],
                metadata={"location_used": None, "historical": False}
            )

        if not request.query or len(request.query.strip()) < 2:
            raise HTTPException(status_code=400, detail="Query too short")

        query = request.query.strip()
        context = request.context or QueryContext()
        location = context.location.suburb if context.location else None
        valid_at = date.today().isoformat() if context.inferred_time_intent == "current" else None
        include_archive = context.historical

        # Use conversation_context if provided
        conversation_context = request.conversation_context

        # Retrieve with filters, passing conversation_context
        raw_chunks = retriever.retrieve(
            query,
            conversation_context=conversation_context,
            top_k=request.top_k * 2,
            threshold=request.threshold,
            location=location,
            valid_at=valid_at,
            include_archive=include_archive
        )

        if not raw_chunks:
            logger.info(f"No results for query: {query}")
            log_knowledge_gap(query, request.session_id, 0.0, [])
            return QueryResponse(
                query=query,
                answer="I couldn't find any information about that in the current municipal documents.",
                sources=[],
                evidence=[],
                total_results=0,
                coverage="none",
                has_knowledge_gap=True,
                confidence=0.0,
                suggested_actions=["contact_council", "check_website"],
                contradictions=[],
                metadata={"location_used": location, "historical": include_archive}
            )

        # Apply domain guardrails
        filtered_chunks, filtering_stats = guardrails.filter_results(query, raw_chunks)
        filtered_chunks = filtered_chunks[:request.top_k]

        if not filtered_chunks:
            logger.info(f"All results filtered out for query: {query}")
            log_knowledge_gap(query, request.session_id, 0.0, [])
            return QueryResponse(
                query=query,
                answer="I found some information, but it did not meet the domain relevance criteria.",
                sources=[],
                evidence=[],
                total_results=0,
                coverage="none",
                has_knowledge_gap=True,
                confidence=0.0,
                suggested_actions=["contact_council"],
                contradictions=[],
                metadata={"filtering_stats": filtering_stats}
            )

        # Detect contradictions
        contradictions_raw = contradiction_detector.detect(filtered_chunks)
        contradictions = []
        for c in contradictions_raw:
            log_contradiction(query, c)
            contradictions.append(Contradiction(
                topic=c.get("topic", "unknown"),
                conflicting_sources=c.get("conflicting_sources", []),
                resolution=c.get("resolution", ""),
                resolution_basis=c.get("resolution_basis", "")
            ))

        # Compute confidence
        confidence = confidence_scorer.compute(filtered_chunks, query)

        # Format answer
        response_data = formatter.format_response(query, filtered_chunks)

        # Build source metadata with match_reason
        sources = []
        seen_ids = set()
        for chunk in filtered_chunks:
            meta = chunk["metadata"]
            doc_id = meta.get("document_id", "unknown")
            if doc_id not in seen_ids:
                seen_ids.add(doc_id)
                locations_list = parse_locations(meta.get("locations", "[]"))
                sources.append(SourceMetadata(
                    document_id=doc_id,
                    version=int(meta.get("version", 1)),
                    title=meta.get("title", ""),
                    department=meta.get("department", ""),
                    last_updated=datetime.fromisoformat(meta.get("last_updated", datetime.utcnow().isoformat())),
                    confidence_source=meta.get("confidence_source", ""),
                    locations=locations_list,
                    match_reason=chunk.get("match_reason")
                ))

        evidence_items = [
            EvidenceItem(
                text=formatter._clean_chunk_text(chunk["text"]),
                score=chunk["score"],
                metadata=chunk["metadata"],
                match_reason=chunk.get("match_reason")
            )
            for chunk in filtered_chunks
        ]

        # Determine coverage level
        coverage = "none"
        if len(filtered_chunks) >= 3 and confidence > 0.7:
            coverage = "full"
        elif len(filtered_chunks) >= 1:
            coverage = "partial"

        has_knowledge_gap = response_data.get("has_knowledge_gap", False) or len(filtered_chunks) == 0

        if has_knowledge_gap or confidence < 0.5:
            log_knowledge_gap(
                query=query,
                user_id=request.session_id,
                confidence=confidence,
                suggested_documents=[s.document_id for s in sources]
            )

        return QueryResponse(
            query=query,
            answer=response_data["answer"],
            sources=sources,
            evidence=evidence_items,
            total_results=len(evidence_items),
            coverage=coverage,
            has_knowledge_gap=has_knowledge_gap,
            confidence=confidence,
            suggested_actions=response_data.get("suggested_actions", []),
            contradictions=contradictions,
            metadata={
                "filtering_stats": filtering_stats,
                "location_used": location,
                "historical": include_archive
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Query failed: {e}", exc_info=True)
        return QueryResponse(
            query=request.query if request else "",
            answer="An internal error occurred while processing your query. Please try again later.",
            sources=[],
            evidence=[],
            total_results=0,
            coverage="none",
            has_knowledge_gap=True,
            confidence=0.0,
            suggested_actions=[],
            contradictions=[],
            metadata={"error": str(e)}
        )