#!/usr/bin/env python3
import sys
from pathlib import Path
import json
import hashlib
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import config
from app.core.loader import DocumentLoader
from app.core.ingestion_validator import IngestionValidator
from app.core.chunker import DocumentChunker
from app.core.index import VectorIndex

def compute_file_hash(file_path: Path) -> str:
    hasher = hashlib.md5()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b''):
            hasher.update(chunk)
    return hasher.hexdigest()

def main():
    print("[START] Starting document ingestion...")
    config.print_paths()

    if not config.DOCUMENTS_DIR.exists():
        print(f"[ERROR] Documents directory not found: {config.DOCUMENTS_DIR}")
        return

    loader = DocumentLoader()
    validator = IngestionValidator()
    chunker = DocumentChunker()
    index = VectorIndex()

    documents = loader.load_directory(config.DOCUMENTS_DIR)
    print(f"[DOC] Loaded {len(documents)} documents")

    validated = []
    failures = []
    for doc in documents:
        is_valid, reason, missing = validator.validate_document(doc)
        if is_valid:
            validated.append(doc)
        else:
            failures.append((doc["metadata"]["filename"], reason))

    if failures:
        print("\n[WARN] Validation failures:")
        for fname, reason in failures:
            print(f"  ❌ {fname}: {reason}")

    if not validated:
        print("[ERROR] No valid documents to ingest.")
        return

    all_chunks = []
    for doc in validated:
        chunks = chunker.chunk_document(doc)
        all_chunks.extend(chunks)
        print(f"  -> {doc['metadata']['filename']}: {len(chunks)} chunks")

    print(f"[CHUNK] Created {len(all_chunks)} chunks")

    try:
        index.add_documents(all_chunks, override_overlap=False)
    except ValueError as e:
        print(f"[ERROR] {e}")
        return

    # Update manifest
    manifest = {}
    for file_path in config.DOCUMENTS_DIR.rglob("*"):
        if file_path.is_file() and file_path.suffix in config.SUPPORTED_EXTENSIONS:
            file_key = str(file_path.relative_to(config.DOCUMENTS_DIR))
            manifest[file_key] = {
                "hash": compute_file_hash(file_path),
                "ingested_at": datetime.utcnow().isoformat(),
                "size": file_path.stat().st_size
            }
    with open(config.MANIFEST_FILE, 'w') as f:
        json.dump(manifest, f, indent=2)

    print("[OK] Ingestion complete!")
    stats = index.get_stats()
    print(f"[STATS] Active chunks: {stats.get('total_chunks_active')}")

if __name__ == "__main__":
    main()