"""
Emergency Manager for Harare City Council LLM Gateway v5.3
Manages emergency mode activation, deactivation, and state
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)

class EmergencyManager:
    """
    Manages emergency modes for the gateway.

    Emergency modes:
    - water_outage
    - health_alert
    - council_strike
    - natural_disaster
    """

    # Emergency mode configurations
    EMERGENCY_MODES = {
        "water_outage": {
            "priority_boost": 10.0,
            "response_style": "directive",
            "header": "🚰 **EMERGENCY WATER OUTAGE INFORMATION**",
            "separate_templates": True
        },
        "health_alert": {
            "priority_boost": 15.0,
            "response_style": "alert",
            "header": "🏥 **PUBLIC HEALTH ALERT**",
            "separate_templates": True
        },
        "council_strike": {
            "priority_boost": 8.0,
            "response_style": "informative",
            "header": "⚖️ **COUNCIL SERVICE DISRUPTION**",
            "separate_templates": False
        },
        "natural_disaster": {
            "priority_boost": 20.0,
            "response_style": "directive",
            "header": "🌪️ **EMERGENCY ALERT**",
            "separate_templates": True
        }
    }

    def __init__(self, storage_backend="memory", redis_client=None):
        self.storage = storage_backend
        self.redis = redis_client
        self.active_modes = {}  # In-memory cache

        # Load from Redis if available
        if self.redis:
            self._load_from_redis()

        logger.info(f"Emergency Manager initialized (storage: {storage_backend})")

    def activate_emergency_mode(
        self,
        mode: str,
        duration_hours: int = 24,
        authorized_by: str = None,
        reason: str = None,
        affected_areas: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Activate an emergency mode.

        Args:
            mode: Emergency mode type
            duration_hours: Duration in hours
            authorized_by: Name of authorizing official
            reason: Reason for activation
            affected_areas: List of affected suburbs/wards

        Returns:
            Activation result
        """
        if mode not in self.EMERGENCY_MODES:
            logger.error(f"Invalid emergency mode: {mode}")
            return {
                "success": False,
                "error": f"Unknown mode: {mode}",
                "valid_modes": list(self.EMERGENCY_MODES.keys())
            }

        # Create activation record
        activation = {
            "mode": mode,
            "activated_at": datetime.utcnow().isoformat(),
            "expires_at": (datetime.utcnow() + timedelta(hours=duration_hours)).isoformat(),
            "duration_hours": duration_hours,
            "authorized_by": authorized_by,
            "reason": reason,
            "affected_areas": affected_areas or ["council-wide"],
            "config": self.EMERGENCY_MODES[mode],
            "active": True
        }

        # Store
        self.active_modes[mode] = activation

        if self.redis:
            try:
                self.redis.setex(
                    f"emergency:{mode}",
                    duration_hours * 3600,  # TTL in seconds
                    json.dumps(activation)
                )
                logger.info(f"Emergency mode '{mode}' stored in Redis")
            except Exception as e:
                logger.error(f"Failed to store emergency mode in Redis: {e}")

        logger.warning(
            f"EMERGENCY MODE ACTIVATED: {mode} by {authorized_by} "
            f"for {duration_hours}h - {reason}"
        )

        return {
            "success": True,
            "mode": mode,
            "activation": activation,
            "message": f"Emergency mode '{mode}' activated for {duration_hours} hours"
        }

    def deactivate_emergency_mode(
        self,
        mode: str,
        deactivated_by: str = None
    ) -> Dict[str, Any]:
        """
        Deactivate an emergency mode.

        Args:
            mode: Emergency mode to deactivate
            deactivated_by: Name of official deactivating

        Returns:
            Deactivation result
        """
        if mode not in self.active_modes:
            return {
                "success": False,
                "error": f"Mode '{mode}' is not active"
            }

        # Mark as inactive
        self.active_modes[mode]["active"] = False
        self.active_modes[mode]["deactivated_at"] = datetime.utcnow().isoformat()
        self.active_modes[mode]["deactivated_by"] = deactivated_by

        # Remove from Redis
        if self.redis:
            try:
                self.redis.delete(f"emergency:{mode}")
            except Exception as e:
                logger.error(f"Failed to delete emergency mode from Redis: {e}")

        # Remove from active modes
        del self.active_modes[mode]

        logger.warning(f"EMERGENCY MODE DEACTIVATED: {mode} by {deactivated_by}")

        return {
            "success": True,
            "mode": mode,
            "message": f"Emergency mode '{mode}' deactivated"
        }

    def get_active_emergency_mode(
        self,
        location: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get currently active emergency mode for a location.

        Args:
            location: User location (to check affected areas)

        Returns:
            Active emergency mode or None
        """
        # Clean up expired modes
        self._cleanup_expired_modes()

        # Find active modes
        active = []

        for mode, activation in self.active_modes.items():
            if not activation.get("active"):
                continue

            # Check expiry
            expires_at = datetime.fromisoformat(activation["expires_at"])
            if datetime.utcnow() > expires_at:
                continue

            # Check location if provided
            if location:
                affected_areas = activation.get("affected_areas", ["council-wide"])

                if "council-wide" in affected_areas:
                    active.append(activation)
                elif location.lower() in [area.lower() for area in affected_areas]:
                    active.append(activation)
            else:
                # No location filter
                active.append(activation)

        # Return highest priority mode (by priority_boost)
        if active:
            active.sort(key=lambda x: x["config"]["priority_boost"], reverse=True)
            return active[0]

        return None

    def get_all_active_modes(self) -> list:
        """
        Get all active emergency modes.

        Returns:
            List of active modes
        """
        self._cleanup_expired_modes()

        return [
            activation for activation in self.active_modes.values()
            if activation.get("active")
        ]

    def _cleanup_expired_modes(self):
        """Remove expired emergency modes."""
        now = datetime.utcnow()
        expired = []

        for mode, activation in self.active_modes.items():
            expires_at = datetime.fromisoformat(activation["expires_at"])
            if now > expires_at:
                expired.append(mode)

        for mode in expired:
            logger.info(f"Emergency mode '{mode}' expired, removing")
            del self.active_modes[mode]

            if self.redis:
                try:
                    self.redis.delete(f"emergency:{mode}")
                except Exception as e:
                    logger.error(f"Failed to delete expired mode from Redis: {e}")

    def _load_from_redis(self):
        """Load active emergency modes from Redis."""
        if not self.redis:
            return

        try:
            keys = self.redis.keys("emergency:*")

            for key in keys:
                mode = key.decode().split(":")[-1]
                data = self.redis.get(key)

                if data:
                    activation = json.loads(data)
                    self.active_modes[mode] = activation

            logger.info(f"Loaded {len(self.active_modes)} emergency modes from Redis")
        except Exception as e:
            logger.error(f"Failed to load emergency modes from Redis: {e}")

    def get_emergency_header(self, mode_data: Dict[str, Any]) -> str:
        """
        Get emergency header for response.

        Args:
            mode_data: Emergency mode activation data

        Returns:
            Header text
        """
        return mode_data["config"]["header"]

    def format_emergency_response(
        self,
        response: str,
        mode_data: Dict[str, Any]
    ) -> str:
        """
        Format response with emergency header.

        Args:
            response: Original response
            mode_data: Emergency mode data

        Returns:
            Formatted response with emergency header
        """
        header = self.get_emergency_header(mode_data)

        formatted = f"{header}\n\n{response}"

        # Add activation details
        activated_at = datetime.fromisoformat(mode_data["activated_at"])
        formatted += f"\n\n*This emergency alert was activated on {activated_at.strftime('%d %B %Y at %H:%M')}.*"

        return formatted

# Global instance
emergency_manager = EmergencyManager()