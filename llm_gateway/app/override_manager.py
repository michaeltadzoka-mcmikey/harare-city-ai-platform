"""
Override Manager for Harare Chatbot Gateway v6.0
Implements human authority override and freeze mechanisms + Dashboard sync.
"""

import logging
import asyncio
import json
import hashlib
import math
import os
import httpx
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)

class OverrideManager:
    def __init__(self, storage_backend="memory", redis_client=None, dashboard_config=None):
        self.storage = storage_backend
        self.redis = redis_client
        self.overrides = {}
        self.dashboard_config = dashboard_config or {}
        self.sync_task = None
        logger.info(f"Override Manager initialized (storage: {storage_backend})")

    def create_override(
        self,
        override_type: str,
        target_type: str,
        target_value: str,
        authority_name: str,
        authority_role: str,
        override_reason: str,
        effective_from: Optional[datetime] = None,
        expires_at: Optional[datetime] = None,
        replacement_text: Optional[str] = None
    ) -> str:
        if effective_from is None:
            effective_from = datetime.utcnow()
        override_id = hashlib.sha256(
            f"{target_type}:{target_value}:{effective_from.isoformat()}".encode()
        ).hexdigest()[:16]
        override = {
            "override_id": override_id,
            "override_type": override_type,
            "target_type": target_type,
            "target_value": target_value,
            "authority_name": authority_name,
            "authority_role": authority_role,
            "override_reason": override_reason,
            "effective_from": effective_from.isoformat(),
            "expires_at": expires_at.isoformat() if expires_at else None,
            "replacement_text": replacement_text,
            "created_at": datetime.utcnow().isoformat(),
            "revoked": False
        }
        self._store_override(override_id, override)
        logger.info(f"Override created: {override_id}")
        return override_id

    def get_matching_override_for_query(self, query: str) -> Optional[Dict[str, Any]]:
        """Return the first active keyword override that matches the user's query."""
        now = datetime.utcnow()
        query_lower = query.lower()
        for override in self.overrides.values():
            if override.get("revoked"):
                continue
            expires_at = override.get("expires_at")
            if expires_at:
                expires_dt = datetime.fromisoformat(expires_at).replace(tzinfo=None)
                if now > expires_dt:
                    continue
            if override.get("target_type") == "keyword":
                target = override["target_value"].lower()
                if target in query_lower:
                    logger.info(f"Override matched: {override['override_id']} (keyword '{target}')")
                    return override
        return None

    def check_overrides(self, document=None, topic=None, department=None) -> List[Dict]:
        return []

    def _store_override(self, override_id: str, override: Dict):
        self.overrides[override_id] = override
        if self.redis:
            try:
                self.redis.set(f"override:{override_id}", json.dumps(override), ex=86400*30)
            except:
                pass

    async def load_from_dashboard(self):
        """Fetch active overrides from Dashboard API and update local cache."""
        url = self.dashboard_config.get("url", "http://localhost:5000")
        api_key = os.environ.get("DASHBOARD_API_KEY")
        if not api_key:
            api_key = self.dashboard_config.get("api_key")
        headers = {"X-API-Key": api_key} if api_key else {}
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"{url}/documents/api/overrides?show_expired=false", headers=headers)
                if resp.status_code == 200:
                    remote_overrides = resp.json()
                    new_ids = set()
                    for ov in remote_overrides:
                        ov_id = ov.get("override_id") or str(ov.get("id"))
                        gateway_override = {
                            "override_id": ov_id,
                            "override_type": ov.get("override_type", "pinned"),
                            "target_type": ov.get("target_type", "keyword"),
                            "target_value": ov.get("target_value", ""),
                            "authority_name": ov.get("created_by", "dashboard"),
                            "authority_role": "admin",
                            "override_reason": ov.get("justification", ""),
                            "expires_at": ov.get("valid_to"),
                            "replacement_text": ov.get("content"),
                            "revoked": not ov.get("is_active", True)
                        }
                        self.overrides[ov_id] = gateway_override
                        new_ids.add(ov_id)
                    for local_id in list(self.overrides.keys()):
                        if local_id not in new_ids:
                            del self.overrides[local_id]
                    logger.info(f"Synced {len(remote_overrides)} overrides from Dashboard")
                else:
                    logger.error(f"Failed to fetch overrides: HTTP {resp.status_code}")
        except Exception as e:
            logger.error(f"Dashboard sync failed: {e}")

    async def start_periodic_sync(self, interval_seconds: int = 60):
        while True:
            await self.load_from_dashboard()
            await asyncio.sleep(interval_seconds)

# Global instance
override_manager = OverrideManager()