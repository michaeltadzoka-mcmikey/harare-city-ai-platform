import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
from app.config import config

AUDIT_FILE = config.AUDIT_LOG_FILE

def audit_log(action: str, user: str, document_id: str, version: Optional[int], details: Dict[str, Any]):
    """Append an audit entry as JSON line."""
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "action": action,
        "user": user,
        "document_id": document_id,
        "version": version,
        "details": details
    }
    with open(AUDIT_FILE, 'a') as f:
        f.write(json.dumps(entry) + '\n')

def read_audit_log(limit: int = 100) -> List[Dict[str, Any]]:
    """Read last `limit` audit entries."""
    if not AUDIT_FILE.exists():
        return []
    entries = []
    with open(AUDIT_FILE, 'r') as f:
        for line in f:
            try:
                entries.append(json.loads(line))
            except:
                continue
    return entries[-limit:]