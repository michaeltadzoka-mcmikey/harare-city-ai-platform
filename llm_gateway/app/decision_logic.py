"""
Decision Ledger for Harare Chatbot Gateway v5.3
Hash-chained immutable audit trail for all interactions
"""

import logging
import json
import hashlib
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

class DecisionLedger:
    """
    Immutable, hash-chained audit ledger.
    
    Each entry contains:
    - Interaction data (query, response, sources)
    - Confidence scores (decomposed)
    - Decision reasoning (which band, why)
    - Contradiction resolutions
    - Override applications
    - Hash of previous entry (blockchain-style)
    
    This ensures complete auditability and tamper evidence.
    """
    
    def __init__(self, ledger_path: str = "logs/decision_ledger.jsonl"):
        self.ledger_path = Path(ledger_path)
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Initialize with genesis block if new
        if not self.ledger_path.exists():
            self._write_genesis_block()
        
        self.last_hash = self._get_last_hash()
        
        logger.info(f"Decision Ledger initialized at {self.ledger_path}")
    
    def log_interaction(
        self,
        session_id: str,
        user_id: str,
        user_message: str,
        bot_response: str,
        intent: str,
        confidence_scores: Dict[str, float],
        sources: List[Dict[str, Any]],
        contradictions: Optional[List[Dict]] = None,
        overrides_applied: Optional[List[Dict]] = None,
        expired_docs_filtered: Optional[List[str]] = None,
        missing_validity_docs: Optional[List[str]] = None,
        service_update_injected: bool = False,
        service_update_skipped: bool = False,
        pinned_override_short_circuit: bool = False,
        pinned_sufficiency_breakdown: Optional[Dict] = None,
        hard_floors_triggered: Optional[Dict[str, bool]] = None,
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Log a complete interaction to the ledger.
        
        Args:
            session_id: Session identifier
            user_id: User identifier
            user_message: User's query
            bot_response: Bot's response
            intent: Detected intent
            confidence_scores: Decomposed confidence scores
            sources: List of source documents used
            contradictions: Any contradictions resolved
            overrides_applied: Any overrides that were active
            expired_docs_filtered: IDs of expired documents removed
            missing_validity_docs: IDs of documents with missing validity metadata
            service_update_injected: Whether service update was injected
            service_update_skipped: Whether service update was skipped (already ahead)
            pinned_override_short_circuit: Whether pinned override short-circuited
            pinned_sufficiency_breakdown: Details of pinned sufficiency test
            hard_floors_triggered: Which hard floors were triggered
            metadata: Additional metadata
            
        Returns:
            Entry hash
        """
        entry = {
            "entry_id": self._generate_entry_id(),
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": session_id,
            "user_id": user_id,
            
            # Interaction
            "user_message": user_message,
            "bot_response": bot_response,
            "intent": intent,
            
            # Confidence (decomposed)
            "confidence_scores": {
                "retrieval": confidence_scores.get("retrieval_confidence", 0.0),
                "authority_raw": confidence_scores.get("authority_confidence_raw", 0.0),
                "authority_multiplied": confidence_scores.get("authority_confidence_multiplied", 0.0),
                "freshness": confidence_scores.get("freshness_confidence", 0.0),
                "composite": confidence_scores.get("composite", 0.0)
            },
            
            # Decision reasoning
            "confidence_band": metadata.get("confidence_band") if metadata else None,
            "synthesis_allowed": metadata.get("synthesis_allowed") if metadata else None,
            "force_verbatim": metadata.get("force_verbatim", False) if metadata else False,
            "hard_floors_triggered": hard_floors_triggered or {},
            
            # Sources
            "sources": [
                {
                    "id": src.get("id"),
                    "title": src.get("title"),
                    "content_type": src.get("content_type"),
                    "precedence_rank": src.get("precedence_rank"),
                    "department": src.get("department")
                }
                for src in sources
            ],
            
            # Governance events
            "contradictions_resolved": len(contradictions) if contradictions else 0,
            "contradiction_details": contradictions or [],
            "overrides_applied": len(overrides_applied) if overrides_applied else 0,
            "override_details": overrides_applied or [],
            "expired_docs_filtered": expired_docs_filtered or [],
            "missing_validity_docs": missing_validity_docs or [],
            "service_update_injected": service_update_injected,
            "service_update_skipped": service_update_skipped,
            "pinned_override_short_circuit": pinned_override_short_circuit,
            "pinned_sufficiency_breakdown": pinned_sufficiency_breakdown or {},
            
            # Temporal
            "validity_warnings_shown": metadata.get("validity_warnings_shown", False) if metadata else False,
            
            # Hash chain
            "previous_hash": self.last_hash,
            "entry_hash": None  # Will be computed
        }
        
        # Compute hash of this entry
        entry_hash = self._compute_hash(entry)
        entry["entry_hash"] = entry_hash
        
        # Write to ledger
        self._append_entry(entry)
        
        # Update last hash
        self.last_hash = entry_hash
        
        logger.debug(f"Ledger entry created: {entry['entry_id']} (hash: {entry_hash[:16]})")
        
        return entry_hash
    
    def verify_chain(self) -> Tuple[bool, Optional[str]]:
        """
        Verify integrity of the hash chain.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            previous_hash = None
            line_number = 0
            
            with open(self.ledger_path, 'r') as f:
                for line in f:
                    line_number += 1
                    entry = json.loads(line)
                    
                    # Check hash chain
                    if entry.get("previous_hash") != previous_hash:
                        return False, (
                            f"Chain broken at line {line_number}: "
                            f"expected previous_hash {previous_hash}, "
                            f"got {entry.get('previous_hash')}"
                        )
                    
                    # Verify entry hash
                    stored_hash = entry.get("entry_hash")
                    entry_copy = entry.copy()
                    entry_copy["entry_hash"] = None
                    computed_hash = self._compute_hash(entry_copy)
                    
                    if stored_hash != computed_hash:
                        return False, (
                            f"Hash mismatch at line {line_number}: "
                            f"stored {stored_hash[:16]}, "
                            f"computed {computed_hash[:16]}"
                        )
                    
                    previous_hash = stored_hash
            
            logger.info(f"Ledger chain verified: {line_number} entries valid")
            return True, None
            
        except Exception as e:
            logger.error(f"Ledger verification failed: {e}")
            return False, str(e)
    
    def _write_genesis_block(self):
        """Write the first entry (genesis block) to the ledger."""
        genesis = {
            "entry_id": "GENESIS",
            "timestamp": datetime.utcnow().isoformat(),
            "session_id": "system",
            "user_id": "system",
            "user_message": "System initialized",
            "bot_response": "Decision Ledger v5.3 started",
            "intent": "system_init",
            "confidence_scores": {},
            "sources": [],
            "contradictions_resolved": 0,
            "overrides_applied": 0,
            "expired_docs_filtered": [],
            "missing_validity_docs": [],
            "service_update_injected": False,
            "service_update_skipped": False,
            "pinned_override_short_circuit": False,
            "hard_floors_triggered": {},
            "previous_hash": None,
            "entry_hash": None
        }
        
        genesis_hash = self._compute_hash(genesis)
        genesis["entry_hash"] = genesis_hash
        
        self._append_entry(genesis)
        
        logger.info("Genesis block written to ledger")
    
    def _append_entry(self, entry: Dict):
        """Append entry to ledger file."""
        with open(self.ledger_path, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    
    def _compute_hash(self, entry: Dict) -> str:
        """Compute SHA-256 hash of entry (excluding entry_hash field)."""
        # Create a deterministic string representation
        entry_copy = entry.copy()
        entry_copy.pop("entry_hash", None)
        
        # Sort keys for deterministic hashing
        canonical = json.dumps(entry_copy, sort_keys=True)
        
        # Compute hash
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    def _get_last_hash(self) -> Optional[str]:
        """Get hash of most recent entry."""
        try:
            with open(self.ledger_path, 'r') as f:
                # Read from end
                lines = f.readlines()
                if lines:
                    last_entry = json.loads(lines[-1])
                    return last_entry.get("entry_hash")
        except Exception as e:
            logger.warning(f"Could not read last hash: {e}")
        
        return None
    
    def _generate_entry_id(self) -> str:
        """Generate unique entry ID."""
        timestamp = datetime.utcnow().isoformat()
        return hashlib.sha256(timestamp.encode()).hexdigest()[:12]
    
    def get_recent_entries(self, limit: int = 10) -> List[Dict]:
        """
        Get most recent ledger entries.
        
        Args:
            limit: Number of entries to return
            
        Returns:
            List of entries (most recent first)
        """
        entries = []
        
        try:
            with open(self.ledger_path, 'r') as f:
                lines = f.readlines()
                
                # Get last N lines
                for line in lines[-limit:]:
                    entry = json.loads(line)
                    entries.append(entry)
                
                # Reverse to get most recent first
                entries.reverse()
                
        except Exception as e:
            logger.error(f"Error reading ledger: {e}")
        
        return entries

# Global instance
decision_ledger = DecisionLedger()