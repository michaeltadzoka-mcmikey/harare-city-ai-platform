import os
from pathlib import Path
from typing import Set, List, Dict, Any
from datetime import datetime

class Config:
    # Paths
    BASE_DIR = Path(__file__).parent.parent
    DOCUMENTS_DIR = BASE_DIR.parent / "shared_documents"
    DATA_DIR = BASE_DIR / "data"
    CHROMA_DIR = DATA_DIR / "chroma"
    ARCHIVE_DIR = DATA_DIR / "archive"
    MANIFEST_FILE = DATA_DIR / "manifest.json"
    VERSIONS_FILE = DATA_DIR / "versions.json"
    AUDIT_LOG_FILE = DATA_DIR / "audit.log"
    KNOWLEDGE_GAP_LOG_FILE = DATA_DIR / "knowledge_gaps.json"

    # Create required directories
    for dir_path in [DATA_DIR, CHROMA_DIR, ARCHIVE_DIR]:
        dir_path.mkdir(exist_ok=True, parents=True)

    # Embedding model – upgraded for much stronger semantic retrieval
    EMBEDDING_MODEL = "BAAI/bge-base-en-v1.5"
    EMBEDDING_DIM = 768

    # Chunking (defaults; type specific strategies override)
    CHUNK_SIZE = 400
    CHUNK_OVERLAP = 50

    # Retrieval defaults
    TOP_K = 5
    SCORE_THRESHOLD = 0.15           # lowered to include weaker‑scoring chunks
    LOCATION_BOOST_FACTOR = 1.5      # required by retriever

    # Priority boost for special content types
    SERVICE_UPDATE_BOOST = 1.3
    PINNED_OVERRIDE_BOOST = 2.0

    # File patterns
    SUPPORTED_EXTENSIONS: Set[str] = {'.txt', '.json', '.md'}

    # ChromaDB settings
    CHROMA_SETTINGS: Dict[str, Any] = {
        "persist_directory": str(CHROMA_DIR),
        "anonymized_telemetry": False
    }

    # ------------------------------------------------------------------
    # v2.2 Mandatory metadata fields (ingestion validation)
    # ------------------------------------------------------------------
    REQUIRED_METADATA_FIELDS: List[str] = [
        "document_id",
        "title",
        "version",
        "department",
        "valid_from",
        "valid_to",
        "content_type",
        "service_area",
        "locations",
        "topic_tags",
    ]

    # Controlled vocabularies for content_type (fixed – system defined)
    CONTENT_TYPES: Set[str] = {
        "procedure", "policy", "faq", "fee_schedule", "emergency",
        "contact_directory", "service_update", "pinned_override"
    }

    # Service areas – now ANY non‑empty string is accepted (validation removed).
    # This set is kept for reference only; the ingestion validator does NOT enforce it.
    SERVICE_AREAS: Set[str] = {
        "water_connection", "rates_payment", "waste_collection",
        "business_permit", "road_maintenance", "health_clinic"
    }

    # Validity check flag (enables temporal filtering at query time)
    VALIDITY_CHECK_ENABLED: bool = True

    # ------------------------------------------------------------------
    # Suburbs list for location completeness calculation
    # ------------------------------------------------------------------
    SUBURBS: List[str] = [
        "Budiriro", "Mabvuku", "Tafara", "Mbare", "Highfield",
        "Hatfield", "Greendale", "Borrowdale", "Avondale", "Belvedere"
    ]

    # ------------------------------------------------------------------
    # Governance fields for pinned overrides
    # ------------------------------------------------------------------
    PINNED_GOVERNANCE_FIELDS: List[str] = [
        "governance_justification",
        "approval_authority"
    ]

    # ------------------------------------------------------------------
    # Debug helper
    # ------------------------------------------------------------------
    @classmethod
    def print_paths(cls):
        print("Configuration Paths:")
        print(f"  BASE_DIR: {cls.BASE_DIR}")
        print(f"  DOCUMENTS_DIR: {cls.DOCUMENTS_DIR}")
        print(f"  DATA_DIR: {cls.DATA_DIR}")
        print(f"  CHROMA_DIR: {cls.CHROMA_DIR}")
        print(f"  ARCHIVE_DIR: {cls.ARCHIVE_DIR}")
        print(f"  DOCUMENTS_DIR exists: {cls.DOCUMENTS_DIR.exists()}")

# Global instance
config = Config()