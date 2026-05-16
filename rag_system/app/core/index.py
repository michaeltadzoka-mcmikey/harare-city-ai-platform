import chromadb
from chromadb.config import Settings
import hashlib
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import logging
from datetime import datetime, date, timedelta
from app.config import config
from app.core.embedder import EmbeddingModel
from app.utils.audit import audit_log

logger = logging.getLogger(__name__)

def date_to_int(d: str) -> int:
    """Convert ISO date string to integer YYYYMMDD."""
    return int(d.replace('-', ''))

def prepare_metadata_for_chromadb(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Convert any list values to JSON strings and remove None values for ChromaDB compatibility."""
    prepared = {}
    for k, v in metadata.items():
        if v is None:
            continue
        if isinstance(v, list):
            prepared[k] = json.dumps(v)
        elif isinstance(v, dict):
            prepared[k] = json.dumps(v)
        elif isinstance(v, (str, int, float, bool)):
            prepared[k] = v
        else:
            prepared[k] = str(v)
    return prepared

class VectorIndex:
    def __init__(self, embedding_batch_size: int = 100, chroma_batch_size: int = 50):
        self.embedder = EmbeddingModel(batch_size=embedding_batch_size)
        self.chroma_batch_size = chroma_batch_size
        self.client = None
        self.active_collection = None
        self.archive_collection = None
        self._initialize()

    def _initialize(self):
        config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(config.CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False)
        )
        try:
            self.active_collection = self.client.get_collection("harare_docs_active")
        except:
            self.active_collection = self.client.create_collection(
                name="harare_docs_active",
                metadata={"hnsw:space": "cosine"}
            )
        try:
            self.archive_collection = self.client.get_collection("harare_docs_archive")
        except:
            self.archive_collection = self.client.create_collection(
                name="harare_docs_archive",
                metadata={"hnsw:space": "cosine"}
            )
        logger.info(f"Active collection: {self.active_collection.count()} chunks, "
                    f"Archive: {self.archive_collection.count()} chunks")

    # ------------------------------------------------------------------
    # Overlap detection (pre ingestion) – Python filtering
    # ------------------------------------------------------------------
    def check_overlap(self, new_doc_metadata: Dict[str, Any]) -> Tuple[bool, Optional[Dict]]:
        content_type = new_doc_metadata.get("content_type")
        service_area = new_doc_metadata.get("service_area")
        new_valid_from = date.fromisoformat(new_doc_metadata["valid_from"])
        new_valid_to = date.fromisoformat(new_doc_metadata["valid_to"])

        where = {
            "$and": [
                {"content_type": {"$eq": content_type}},
                {"service_area": {"$eq": service_area}}
            ]
        }
        results = self.active_collection.get(
            where=where,
            include=["metadatas"]
        )
        if not results["metadatas"]:
            return False, None

        today = date.today()
        for meta in results["metadatas"]:
            # Parse metadata (some fields may be JSON strings)
            valid_to_str = meta.get("valid_to")
            if not valid_to_str:
                continue
            existing_valid_to = date.fromisoformat(valid_to_str)
            if existing_valid_to < today:
                continue
            existing_valid_from = date.fromisoformat(meta["valid_from"])
            if new_valid_from <= existing_valid_to and new_valid_to >= existing_valid_from:
                return True, meta
        return False, None

    # ------------------------------------------------------------------
    # Version transition – Python filtering
    # ------------------------------------------------------------------
    def handle_version_transition(self, new_doc_metadata: Dict[str, Any]) -> Optional[Dict]:
        new_doc_id = new_doc_metadata.get("document_id")
        if not new_doc_id:
            return None
        base_id = new_doc_id.rsplit('-v', 1)[0] if '-v' in new_doc_id else new_doc_id

        results = self.active_collection.get(
            include=["metadatas", "documents", "embeddings"]
        )
        if not results["ids"]:
            return None

        candidates = []
        for idx, meta in enumerate(results["metadatas"]):
            if meta.get("document_id", "").startswith(base_id):
                candidates.append((idx, meta))

        if not candidates:
            return None

        candidates = [(idx, meta) for idx, meta in candidates if meta.get("document_id") != new_doc_id]

        if not candidates:
            return None

        candidates.sort(key=lambda x: int(x[1].get("version", 0)), reverse=True)
        old_idx, old_meta = candidates[0]

        old_valid_to = date.fromisoformat(old_meta["valid_to"])
        new_valid_from = date.fromisoformat(new_doc_metadata["valid_from"])
        if new_valid_from <= old_valid_to:
            new_valid_to_old = (new_valid_from - timedelta(days=1)).isoformat()
            old_id = results["ids"][old_idx]
            old_doc = results["documents"][old_idx]
            old_embedding = results["embeddings"][old_idx]
            old_metadata = results["metadatas"][old_idx].copy()
            old_metadata["valid_to"] = new_valid_to_old
            self.archive_collection.add(
                embeddings=[old_embedding],
                documents=[old_doc],
                metadatas=[prepare_metadata_for_chromadb(old_metadata)],
                ids=[f"{old_id}_archived_{datetime.utcnow().isoformat()}"]
            )
            self.active_collection.delete(ids=[old_id])
            logger.info(f"Retired old version {old_meta['document_id']} valid_to set to {new_valid_to_old}")

            audit_log(
                action="VERSION_SUPERSEDED",
                user="system",
                document_id=old_meta["document_id"],
                version=old_meta.get("version"),
                details={
                    "new_document_id": new_doc_metadata["document_id"],
                    "new_valid_from": new_doc_metadata["valid_from"],
                    "old_valid_to_adjusted": new_valid_to_old
                }
            )
            return old_metadata
        return None

    # ------------------------------------------------------------------
    # Add documents (with governance)
    # ------------------------------------------------------------------
    def add_documents(self, chunks: List[Dict[str, Any]], override_overlap: bool = False):
        if not chunks:
            return

        today_int = date_to_int(date.today().isoformat())
        active_chunks = []
        for chunk in chunks:
            meta = chunk["metadata"]
            if "valid_from" in meta and isinstance(meta["valid_from"], str):
                meta["valid_from_int"] = date_to_int(meta["valid_from"])
            if "valid_to" in meta and isinstance(meta["valid_to"], str):
                meta["valid_to_int"] = date_to_int(meta["valid_to"])

            valid_to_int = meta.get("valid_to_int", 99999999)
            if valid_to_int >= today_int:
                active_chunks.append(chunk)
            else:
                self._add_to_archive([chunk])

        if not active_chunks:
            return

        docs_map = {}
        for chunk in active_chunks:
            doc_id = chunk["metadata"].get("document_id")
            if doc_id not in docs_map:
                docs_map[doc_id] = []
            docs_map[doc_id].append(chunk)

        final_chunks = []
        for doc_id, doc_chunks in docs_map.items():
            doc_metadata = doc_chunks[0]["metadata"]

            if not override_overlap:
                overlap, conflict = self.check_overlap(doc_metadata)
                if overlap:
                    raise ValueError(f"Overlap detected with active document {conflict.get('document_id')}. Use override to force.")

            self.handle_version_transition(doc_metadata)

            texts = [chunk["text"] for chunk in doc_chunks]
            embeddings = self.embedder.embed(texts)
            for i, chunk in enumerate(doc_chunks):
                chunk["embedding"] = embeddings[i].tolist()
                final_chunks.append(chunk)

        self._add_to_active(final_chunks)

    def _add_to_active(self, chunks: List[Dict]):
        if not chunks:
            return
        ids = [chunk["id"] for chunk in chunks]
        texts = [chunk["text"] for chunk in chunks]
        # Convert metadata for ChromaDB, removing None values
        metadatas = [prepare_metadata_for_chromadb(chunk["metadata"]) for chunk in chunks]
        embeddings = [chunk["embedding"] for chunk in chunks]

        for i in range(0, len(chunks), self.chroma_batch_size):
            end = min(i + self.chroma_batch_size, len(chunks))
            self.active_collection.add(
                embeddings=embeddings[i:end],
                documents=texts[i:end],
                metadatas=metadatas[i:end],
                ids=ids[i:end]
            )
        logger.info(f"Added {len(chunks)} chunks to active index")

    def _add_to_archive(self, chunks: List[Dict]):
        texts = [chunk["text"] for chunk in chunks if "embedding" not in chunk]
        if texts:
            embeddings = self.embedder.embed(texts)
            emb_idx = 0
            for chunk in chunks:
                if "embedding" not in chunk:
                    chunk["embedding"] = embeddings[emb_idx].tolist()
                    emb_idx += 1
        ids = [f"{chunk['id']}_archived" for chunk in chunks]
        texts = [chunk["text"] for chunk in chunks]
        metadatas = [prepare_metadata_for_chromadb(chunk["metadata"]) for chunk in chunks]
        embeddings = [chunk["embedding"] for chunk in chunks]
        self.archive_collection.add(
            embeddings=embeddings,
            documents=texts,
            metadatas=metadatas,
            ids=ids
        )
        logger.info(f"Added {len(chunks)} chunks to archive")

    # ------------------------------------------------------------------
    # Search with filters
    # ------------------------------------------------------------------
    def search(self, query: str, n_results: int = 5, score_threshold: float = 0.3,
               where: Optional[Dict] = None, include_archive: bool = False) -> List[Dict]:
        query_emb = self.embedder.embed_single(query)
        collection = self.archive_collection if include_archive else self.active_collection
        results = collection.query(
            query_embeddings=[query_emb.tolist()],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"]
        )
        formatted = []
        if results["documents"] and results["documents"][0]:
            for i, (doc, meta, dist) in enumerate(zip(
                results["documents"][0], results["metadatas"][0], results["distances"][0]
            )):
                similarity = 1 - dist
                if similarity >= score_threshold:
                    formatted.append({
                        "text": doc,
                        "metadata": meta,
                        "score": float(similarity),
                        "distance": float(dist),
                        "rank": i+1
                    })
        return formatted

    def search_with_filters(self, query: str, n_results: int = 5,
                            locations: Optional[List[str]] = None,
                            valid_at: Optional[str] = None,
                            include_archive: bool = False,
                            **kwargs) -> List[Dict]:
        conditions = []
        if valid_at:
            valid_int = date_to_int(valid_at)
            conditions.append({"valid_from_int": {"$lte": valid_int}})
            conditions.append({"valid_to_int": {"$gte": valid_int}})

        where = None
        if len(conditions) == 1:
            where = conditions[0]
        elif len(conditions) > 1:
            where = {"$and": conditions}

        return self.search(query, n_results=n_results, where=where,
                           include_archive=include_archive, **kwargs)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------
    def get_stats(self) -> Dict[str, Any]:
        try:
            return {
                "total_chunks_active": self.active_collection.count(),
                "total_chunks_archive": self.archive_collection.count(),
                "embedding_model": config.EMBEDDING_MODEL,
                "embedding_dimension": self.embedder.get_embedding_dimension()
            }
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {"error": str(e)}

    def clear_index(self):
        try:
            self.client.delete_collection("harare_docs_active")
            self.client.delete_collection("harare_docs_archive")
        except:
            pass
        self.active_collection = self.client.create_collection("harare_docs_active", metadata={"hnsw:space": "cosine"})
        self.archive_collection = self.client.create_collection("harare_docs_archive", metadata={"hnsw:space": "cosine"})
        logger.warning("All indices cleared")