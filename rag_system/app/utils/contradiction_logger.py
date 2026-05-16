import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional
from collections import defaultdict
from app.config import config

CONTRADICTION_LOG_FILE = config.DATA_DIR / "contradictions.json"

def log_contradiction(query: str, contradiction: Dict[str, Any]):
    """Append a contradiction event to the log file."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "query": query,
        "contradiction": contradiction
    }
    # Read existing
    if CONTRADICTION_LOG_FILE.exists():
        with open(CONTRADICTION_LOG_FILE, 'r') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = []
    else:
        data = []
    data.append(entry)
    # Keep last 10k entries
    if len(data) > 10000:
        data = data[-10000:]
    with open(CONTRADICTION_LOG_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def read_contradiction_log(days: Optional[int] = None) -> List[Dict]:
    """Read contradiction log, optionally filtered by last N days."""
    if not CONTRADICTION_LOG_FILE.exists():
        return []
    with open(CONTRADICTION_LOG_FILE, 'r') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            return []
    if days is not None:
        cutoff = datetime.utcnow() - timedelta(days=days)
        data = [e for e in data if datetime.fromisoformat(e["timestamp"]) >= cutoff]
    return data

def get_conflict_analytics(days: int = 30) -> Dict[str, Any]:
    """Aggregate contradiction statistics for the last N days."""
    entries = read_contradiction_log(days)
    total = len(entries)

    # Initialize counters
    cross_type = 0
    same_type = 0
    same_type_newer = 0
    same_type_version = 0
    same_type_authority = 0
    precedence_override = 0
    by_dept = defaultdict(int)

    for entry in entries:
        contra = entry["contradiction"]
        # Determine type based on conflicting sources' content_type
        # For simplicity, we assume the contradiction dict has a "type" field.
        # If not, we infer from metadata (but that requires additional logic).
        # We'll use a placeholder: if "type" not present, default to cross-type.
        ctype = contra.get("type", "cross-type")
        if ctype == "cross-type":
            cross_type += 1
        elif ctype == "same-type":
            same_type += 1
            resolution = contra.get("resolution_basis", "")
            if "newer" in resolution.lower():
                same_type_newer += 1
            elif "version" in resolution.lower():
                same_type_version += 1
            elif "authority" in resolution.lower():
                same_type_authority += 1
        # Precedence override count (subset of cross-type)
        if contra.get("precedence_override", False):
            precedence_override += 1

        # Department from first source (if we can map document_id to department)
        # This would require a lookup; for now we skip department breakdown.
        # In a real implementation, you might query the index or manifest.

    return {
        "total_conflicts": total,
        "breakdown": {
            "cross_type": cross_type,
            "same_type": same_type,
            "same_type_resolved_by_newer": same_type_newer,
            "same_type_resolved_by_version": same_type_version,
            "same_type_resolved_by_authority": same_type_authority,
            "precedence_override_count": precedence_override
        },
        "by_department": dict(by_dept),
        "period_days": days
    }