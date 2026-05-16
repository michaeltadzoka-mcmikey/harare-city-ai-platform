from fastapi import APIRouter, HTTPException, Request
from typing import Optional, Dict, Any, List
from pathlib import Path
import json, hashlib, re, zipfile, logging
from datetime import datetime, date

from app.core.loader import DocumentLoader
from app.core.ingestion_validator import IngestionValidator
from app.core.index import VectorIndex
from app.config import config
from app.utils.audit import audit_log
from app.schemas.ingest import IngestRequest, IngestResponse, IngestStatus

router = APIRouter()
logger = logging.getLogger(__name__)

# ── Universal chunker – one chunk per ##/### heading ─────────────
def _chunk_content(content: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Split on any markdown heading (## or ###). Each section becomes one chunk."""
    parts = re.split(r'(?=^#{2,3}\s)', content, flags=re.MULTILINE)
    chunks = []
    pos = 0
    for part in parts:
        text = part.strip()
        if text:
            end = pos + len(text)
            chunk_id = hashlib.md5(
                f"{metadata.get('document_id','')}:{pos}:{end}".encode()
            ).hexdigest()[:16]
            chunks.append({
                "id": chunk_id,
                "text": text,
                "metadata": {
                    **metadata,
                    "chunk_start": pos,
                    "chunk_end": end,
                    "total_chars": len(content)
                },
                "hash": hashlib.md5(text.encode()).hexdigest()
            })
            pos = end

    # Fallback: if no headings, keep whole document
    if not chunks and content.strip():
        text = content.strip()
        chunk_id = hashlib.md5(
            f"{metadata.get('document_id','')}:0:{len(text)}".encode()
        ).hexdigest()[:16]
        chunks.append({
            "id": chunk_id,
            "text": text,
            "metadata": {
                **metadata,
                "chunk_start": 0,
                "chunk_end": len(text),
                "total_chars": len(text)
            },
            "hash": hashlib.md5(text.encode()).hexdigest()
        })
    return chunks

# ── helpers ──────────────────────────────────────────────────────
def compute_file_hash(file_path: Path) -> str:
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hasher.update(chunk)
    return hasher.hexdigest()

def clean_metadata_dict(meta: Dict[str, Any]) -> Dict[str, Any]:
    cleaned = {}
    for k, v in meta.items():
        if v is None:
            continue
        if isinstance(v, (list, dict)):
            cleaned[k] = v
        elif isinstance(v, (str, int, float, bool)):
            cleaned[k] = v
        else:
            cleaned[k] = str(v)
    return cleaned

def extract_content_block(raw_text: str) -> str:
    if "## CONTENT_BLOCK" in raw_text:
        return raw_text.split("## CONTENT_BLOCK", 1)[-1].strip()
    elif "### Summary" in raw_text:
        return raw_text.split("### Summary", 1)[-1].strip()
    return raw_text.strip()

# ── ingestion endpoint ──────────────────────────────────────────
@router.post("/ingest", response_model=IngestResponse)
async def ingest_documents(request: Request, req: Optional[IngestRequest] = None):
    try:
        body = None
        try:
            body = await request.json()
        except:
            pass

        # ----- Direct payload (Dashboard) -----
        if body and body.get("content"):
            logger.info("Ingesting direct document from request body")
            validator = IngestionValidator()

            metadata = {
                "document_id": body.get("document_id", ""),
                "title": body.get("title", ""),
                "version": body.get("version", 1),
                "department": body.get("department", ""),
                "owner_email": body.get("owner_email", ""),
                "valid_from": body.get("valid_from"),
                "valid_to": body.get("valid_to"),
                "content_type": body.get("content_type") or body.get("category", "procedure"),
                "service_area": body.get("service_area") or body.get("service", ""),
                "locations": body.get("locations", ["Council-wide"]),
                "topic_tags": body.get("topic_tags", []),
                "prerequisites": body.get("prerequisites", []),
                "related_documents": body.get("related_documents", []),
                "review_cycle": body.get("review_cycle"),
                "cross_service_flag": body.get("cross_service_flag", False),
                "authority_confidence": body.get("authority_confidence", 0.9),
                "confidence_source": body.get("confidence_source"),
                "authority_override": body.get("authority_override"),
                "filename": body.get("document_id", "direct.txt"),
                "source": str(config.DOCUMENTS_DIR / (body.get("document_id", "direct") + ".txt"))
            }
            for field in ["topic_tags", "prerequisites", "related_documents", "locations"]:
                if field in metadata and isinstance(metadata[field], str):
                    metadata[field] = [x.strip() for x in metadata[field].split(',') if x.strip()]

            if metadata.get("valid_from"):
                metadata["valid_from"] = str(metadata["valid_from"])
            if metadata.get("valid_to"):
                metadata["valid_to"] = str(metadata["valid_to"])

            metadata = clean_metadata_dict(metadata)
            clean_content = extract_content_block(body["content"])

            doc = {
                "content": clean_content,
                "metadata": metadata,
                "size": len(body["content"])
            }

            is_valid, reason, missing = validator.validate_document(doc)
            if not is_valid:
                logger.warning(f"Validation failed: {reason}, missing: {missing}")
                return IngestResponse(
                    message=f"Validation failed: {reason}",
                    total_documents=1, ingested=0, chunks_created=0, skipped=0,
                    validation_failures=[{"file": metadata.get("filename", "direct"), "reason": reason}]
                )

            valid_to_str = doc["metadata"].get("valid_to")
            if valid_to_str:
                try:
                    valid_to = date.fromisoformat(valid_to_str)
                    doc["metadata"]["is_active"] = valid_to >= date.today()
                except:
                    doc["metadata"]["is_active"] = True
            else:
                doc["metadata"]["is_active"] = True

            chunks = _chunk_content(doc["content"], doc["metadata"])
            if not chunks:
                logger.warning("No chunks produced for document")
                return IngestResponse(
                    message="Document produced no chunks",
                    total_documents=1, ingested=0, chunks_created=0, skipped=0
                )

            index = VectorIndex()
            overlap_rejected = False
            try:
                index.add_documents(chunks, override_overlap=req.override_overlap if req else False)
            except ValueError as e:
                if "Overlap detected" in str(e):
                    overlap_rejected = True
                    audit_log(
                        action="OVERLAP_REJECTED", user="system",
                        document_id=doc["metadata"].get("document_id", "unknown"),
                        version=doc["metadata"].get("version"),
                        details={"reason": str(e)}
                    )
                    return IngestResponse(
                        message=f"Ingestion rejected: {e}",
                        total_documents=1, ingested=0, chunks_created=0, skipped=0,
                        overlap_rejected=True
                    )
                else:
                    raise

            audit_log(
                action="INGEST", user="system",
                document_id=doc["metadata"].get("document_id", "unknown"),
                version=doc["metadata"].get("version"),
                details={"filename": doc["metadata"].get("filename", "direct")}
            )

            return IngestResponse(
                message=f"Ingested 1 document ({len(chunks)} chunks)",
                total_documents=1, ingested=1, chunks_created=len(chunks), skipped=0,
                overlap_rejected=overlap_rejected
            )

        # ----- File‑based ingestion -----
        target_path = config.DOCUMENTS_DIR
        if req and req.path:
            target_path = config.DOCUMENTS_DIR / req.path

        if not target_path.exists():
            raise HTTPException(status_code=404, detail=f"Path not found: {target_path}")

        manifest = {}
        if config.MANIFEST_FILE.exists():
            with open(config.MANIFEST_FILE, 'r') as f:
                manifest = json.load(f)

        loader = DocumentLoader()
        validator = IngestionValidator()

        if target_path.is_file():
            documents = [loader.load_file(target_path)]
        else:
            documents = loader.load_directory(target_path)

        logger.info(f"Loaded {len(documents)} documents from disk")

        validated_documents = []
        validation_failures = []

        for doc in documents:
            doc["content"] = extract_content_block(doc["content"])
            is_valid, reason, missing = validator.validate_document(doc)
            if not is_valid:
                validation_failures.append({
                    "file": doc["metadata"]["filename"],
                    "reason": reason
                })
                continue

            valid_to_str = doc["metadata"].get("valid_to")
            if valid_to_str:
                valid_to = date.fromisoformat(valid_to_str)
                doc["metadata"]["is_active"] = valid_to >= date.today()
            else:
                doc["metadata"]["is_active"] = True

            validated_documents.append(doc)

        new_or_changed = []
        skipped = 0
        for doc in validated_documents:
            file_path = Path(doc["metadata"]["source"])
            file_hash = compute_file_hash(file_path)
            file_key = str(file_path.relative_to(config.DOCUMENTS_DIR))
            needs_indexing = (
                (req and req.reindex) or
                file_key not in manifest or
                manifest[file_key].get("hash") != file_hash
            )
            if needs_indexing:
                new_or_changed.append(doc)
                manifest[file_key] = {
                    "hash": file_hash,
                    "ingested_at": datetime.utcnow().isoformat(),
                    "size": doc["size"],
                    "domain_score": validator.get_domain_score(doc["content"]),
                    "category": validator.suggest_document_category(doc["content"]),
                    "metadata": doc["metadata"]
                }
            else:
                skipped += 1

        if not new_or_changed:
            return IngestResponse(
                message="No new or changed documents",
                total_documents=len(documents), ingested=0, chunks_created=0, skipped=skipped,
                validation_failures=validation_failures
            )

        all_chunks = []
        for doc in new_or_changed:
            chunks = _chunk_content(doc["content"], doc["metadata"])
            all_chunks.extend(chunks)

        index = VectorIndex()
        overlap_rejected = False
        try:
            index.add_documents(all_chunks, override_overlap=req.override_overlap if req else False)
        except ValueError as e:
            if "Overlap detected" in str(e):
                overlap_rejected = True
                for doc in new_or_changed:
                    audit_log(
                        action="OVERLAP_REJECTED", user="system",
                        document_id=doc["metadata"].get("document_id", "unknown"),
                        version=doc["metadata"].get("version"),
                        details={"reason": str(e)}
                    )
                return IngestResponse(
                    message=f"Ingestion rejected: {e}",
                    total_documents=len(documents), ingested=0, chunks_created=0, skipped=skipped,
                    validation_failures=validation_failures, overlap_rejected=True
                )
            else:
                raise

        with open(config.MANIFEST_FILE, 'w') as f:
            json.dump(manifest, f, indent=2)

        for doc in new_or_changed:
            audit_log(
                action="INGEST", user="system",
                document_id=doc["metadata"].get("document_id", "unknown"),
                version=doc["metadata"].get("version"),
                details={"filename": doc["metadata"]["filename"]}
            )

        return IngestResponse(
            message=f"Ingested {len(new_or_changed)} documents ({len(all_chunks)} chunks)",
            total_documents=len(documents), ingested=len(new_or_changed),
            chunks_created=len(all_chunks), skipped=skipped,
            validation_failures=validation_failures, version_superseded=False,
            overlap_rejected=overlap_rejected
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ingestion failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

@router.get("/ingest/status", response_model=IngestStatus)
async def get_ingest_status():
    try:
        manifest = {}
        if config.MANIFEST_FILE.exists():
            with open(config.MANIFEST_FILE) as f:
                manifest = json.load(f)
        index = VectorIndex()
        stats = index.get_stats()
        return IngestStatus(
            status="ready",
            total_files=len(manifest),
            total_chunks=stats.get("total_chunks_active", 0),
            last_ingestion=max((v.get("ingested_at") for v in manifest.values() if v.get("ingested_at")), default=None),
            files=[{"path": k, **v} for k, v in manifest.items()]
        )
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        return IngestStatus(status="error", total_files=0, total_chunks=0)

@router.delete("/ingest/clear")
async def clear_index(backup: bool = True):
    index = VectorIndex()
    backup_zip = None

    if backup:
        backup_dir = config.DATA_DIR / "backups"
        backup_dir.mkdir(exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_zip = backup_dir / f"rag_backup_{timestamp}.zip"

        if config.MANIFEST_FILE.exists():
            with open(config.MANIFEST_FILE, 'r') as f:
                manifest = json.load(f)

            with zipfile.ZipFile(backup_zip, 'w', zipfile.ZIP_DEFLATED) as zf:
                for file_key in manifest.keys():
                    file_path = config.DOCUMENTS_DIR / file_key
                    if file_path.exists():
                        zf.write(file_path, arcname=file_key)
                zf.write(config.MANIFEST_FILE, arcname="manifest.json")

            archive_wipe_dir = config.ARCHIVE_DIR / f"wipe_{timestamp}"
            archive_wipe_dir.mkdir(parents=True, exist_ok=True)

            active_results = index.active_collection.get(include=["metadatas", "documents", "embeddings"])
            if active_results["ids"]:
                index.archive_collection.add(
                    embeddings=active_results["embeddings"],
                    documents=active_results["documents"],
                    metadatas=active_results["metadatas"],
                    ids=[f"{id}_wipe_{timestamp}" for id in active_results["ids"]]
                )

            logger.info(f"Backup created at {backup_zip}, vectors preserved in archive")

    try:
        index.client.delete_collection("harare_docs_active")
        index.client.delete_collection("harare_docs_archive")
    except:
        pass

    index.active_collection = index.client.create_collection("harare_docs_active", metadata={"hnsw:space": "cosine"})
    index.archive_collection = index.client.create_collection("harare_docs_archive", metadata={"hnsw:space": "cosine"})

    if config.MANIFEST_FILE.exists() and backup:
        manifest_backup = config.DATA_DIR / f"manifest_{timestamp}.json"
        config.MANIFEST_FILE.rename(manifest_backup)

    logger.warning("All indices cleared")
    return {
        "message": "Index cleared",
        "backup_created": str(backup_zip) if backup and backup_zip else None
    }