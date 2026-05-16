"""
Health API - Enhanced with detailed system statistics and Service Coverage Score
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
from pathlib import Path
import json
import logging

from app.core.index import VectorIndex
from app.core.coverage import CoverageScorer
from app.config import config

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/health")
async def health_check():
    """
    Comprehensive health check with system statistics and Service Coverage Score.
    """
    try:
        components = {
            "data_directory": config.DATA_DIR.exists(),
            "chroma_db": config.CHROMA_DIR.exists(),
            "documents_directory": config.DOCUMENTS_DIR.exists(),
            "manifest_file": config.MANIFEST_FILE.exists()
        }

        try:
            index = VectorIndex()
            index_stats = index.get_stats()
        except Exception as e:
            logger.error(f"Failed to get index stats: {e}")
            index_stats = {
                "total_chunks_active": 0,
                "total_chunks_archive": 0,
                "error": str(e)
            }

        try:
            scorer = CoverageScorer(index)
            test_areas = [
                ("Water and Sanitation", "water_connection"),
                ("Finance", "rates_payment"),
                ("Waste Management", "waste_collection"),
                ("Business Licensing", "business_permit")
            ]
            scs_values = []
            for dept, area in test_areas:
                scs_values.append(scorer.compute_scs(dept, area))
            avg_scs = sum(scs_values) / len(scs_values) if scs_values else 0.0
        except Exception as e:
            logger.error(f"Failed to compute SCS: {e}")
            avg_scs = 0.0

        document_stats = {
            "total_documents": 0,
            "total_size_bytes": 0,
            "categories": {},
            "last_ingestion": None
        }

        if config.MANIFEST_FILE.exists():
            try:
                with open(config.MANIFEST_FILE, 'r') as f:
                    manifest = json.load(f)
                document_stats["total_documents"] = len(manifest)
                document_stats["total_size_bytes"] = sum(
                    v.get("size", 0) for v in manifest.values()
                )
                for file_data in manifest.values():
                    category = file_data.get("category", "unknown")
                    document_stats["categories"][category] = \
                        document_stats["categories"].get(category, 0) + 1
                ingestion_times = [
                    v.get("ingested_at")
                    for v in manifest.values()
                    if v.get("ingested_at")
                ]
                if ingestion_times:
                    document_stats["last_ingestion"] = max(ingestion_times)
            except Exception as e:
                logger.error(f"Failed to read manifest: {e}")

        critical_components = ["data_directory", "chroma_db"]
        critical_ok = all(components[c] for c in critical_components)

        if not critical_ok:
            status = "unhealthy"
        elif not components["documents_directory"]:
            status = "degraded"
        elif index_stats.get("total_chunks_active", 0) == 0:
            status = "degraded"
        else:
            status = "healthy"

        return {
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "version": "2.2.0",
            "components": components,
            "index": index_stats,
            "documents": document_stats,
            "service_coverage_score": round(avg_scs, 3),
            "configuration": {
                "embedding_model": config.EMBEDDING_MODEL,
                "chunk_size": config.CHUNK_SIZE,
                "chunk_overlap": config.CHUNK_OVERLAP,
                "supported_extensions": list(config.SUPPORTED_EXTENSIONS),
                "location_boost_factor": config.LOCATION_BOOST_FACTOR,
                "validity_check_enabled": config.VALIDITY_CHECK_ENABLED
            }
        }

    except Exception as e:
        logger.error(f"Health check failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail={
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
        )

@router.get("/health/ready")
async def readiness_check():
    try:
        index = VectorIndex()
        stats = index.get_stats()
        if stats.get("total_chunks_active", 0) > 0:
            return {"status": "ready"}
        else:
            raise HTTPException(
                status_code=503,
                detail="No documents indexed yet"
            )
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Not ready: {str(e)}"
        )

@router.get("/health/live")
async def liveness_check():
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat()
    }

@router.get("/stats")
async def get_statistics():
    try:
        index = VectorIndex()
        index_stats = index.get_stats()

        document_stats = {"total": 0, "by_category": {}, "by_extension": {}}

        if config.MANIFEST_FILE.exists():
            with open(config.MANIFEST_FILE, 'r') as f:
                manifest = json.load(f)
                document_stats["total"] = len(manifest)

                for file_path, file_data in manifest.items():
                    category = file_data.get("category", "unknown")
                    document_stats["by_category"][category] = \
                        document_stats["by_category"].get(category, 0) + 1

                    ext = Path(file_path).suffix
                    document_stats["by_extension"][ext] = \
                        document_stats["by_extension"].get(ext, 0) + 1

        return {
            "index": index_stats,
            "documents": document_stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Stats failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get stats: {str(e)}"
        )