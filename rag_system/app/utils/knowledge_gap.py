import json
from datetime import datetime
from typing import Optional, List
from app.config import config

GAP_FILE = config.KNOWLEDGE_GAP_LOG_FILE

def log_knowledge_gap(query: str, user_id: Optional[str], confidence: float, suggested_documents: List[str]):
    """Append a knowledge gap entry to the JSON log file."""
    entry = {
        "query": query,
        "user_id": user_id,
        "timestamp": datetime.utcnow().isoformat(),
        "confidence": confidence,
        "suggested_documents": suggested_documents
    }
    # Read existing gaps
    gaps = []
    if GAP_FILE.exists():
        try:
            with open(GAP_FILE, 'r') as f:
                gaps = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            gaps = []
    gaps.append(entry)
    # Keep only last 1000 entries (optional)
    if len(gaps) > 1000:
        gaps = gaps[-1000:]
    with open(GAP_FILE, 'w') as f:
        json.dump(gaps, f, indent=2)