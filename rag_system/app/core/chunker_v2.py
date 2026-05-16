import hashlib
import re
import logging
from typing import List, Dict, Any
from app.config import config

logger = logging.getLogger(__name__)

class DocumentChunker:
    """Splits documents into chunks according to content_type."""

    def __init__(self, chunk_size: int = None, overlap: int = None):
        self.default_chunk_size = chunk_size or config.CHUNK_SIZE
        self.default_overlap = overlap or config.CHUNK_OVERLAP

    def chunk_document(self, document: Dict[str, Any]) -> List[Dict[str, Any]]:
        content = document.get("content", "")
        metadata = document.get("metadata", {})
        content_type = metadata.get("content_type", "policy")
        logger.info(f"CHUNKER v2 – chunking {content_type} doc: {metadata.get('document_id')}")

        if content_type == "procedure":
            return self._whole_document(content, metadata)
        elif content_type == "faq":
            return self._chunk_faq(content, metadata)
        elif content_type in ("policy", "fee_schedule", "emergency", "contact_directory"):
            return self._chunk_by_headings(content, metadata)
        else:
            return self._chunk_by_headings(content, metadata)

    def _create_chunk(self, text: str, metadata: Dict,
                      chunk_start: int, chunk_end: int, doc_total: int) -> Dict:
        chunk_text = text.strip()
        chunk_id = hashlib.md5(
            f"{metadata.get('document_id','')}:{chunk_start}:{chunk_end}".encode()
        ).hexdigest()[:16]
        return {
            "id": chunk_id,
            "text": chunk_text,
            "metadata": {
                **metadata,
                "chunk_start": chunk_start,
                "chunk_end": chunk_end,
                "total_chars": doc_total
            },
            "hash": hashlib.md5(chunk_text.encode()).hexdigest()
        }

    def _whole_document(self, content: str, metadata: Dict) -> List[Dict]:
        logger.info(f"  → whole document, {len(content)} chars")
        return [self._create_chunk(content, metadata, 0, len(content), len(content))]

    def _chunk_by_headings(self, content: str, metadata: Dict) -> List[Dict]:
        sections = re.split(r'(?=^## )', content, flags=re.MULTILINE)
        chunks = []
        pos = 0
        for sec in sections:
            if sec.strip():
                end = pos + len(sec)
                chunks.append(self._create_chunk(sec, metadata, pos, end, len(content)))
                pos = end
        logger.info(f"  → {len(chunks)} heading‑chunks")
        return chunks if chunks else self._whole_document(content, metadata)

    def _chunk_faq(self, content: str, metadata: Dict) -> List[Dict]:
        qa_sections = re.split(r'(?=^\s*(?:-\s*)?Q:)', content, flags=re.MULTILINE)
        chunks = []
        pos = 0
        for sec in qa_sections:
            if sec.strip():
                end = pos + len(sec)
                chunks.append(self._create_chunk(sec.strip(), metadata, pos, end, len(content)))
                pos = end
        logger.info(f"  → {len(chunks)} FAQ chunks")
        return chunks if chunks else self._whole_document(content, metadata)