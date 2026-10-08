"""
Client-side License Validator with Offline Grace Period & Tamper Protection.
Authoritative validation against central backend with fallback caching.
"""

from datetime import datetime, timedelta
import json
from pathlib import Path
from typing import Optional, Dict, Any
import httpx

from app.ota.agent.identity import get_or_create_device_id, get_device_token
from app.ota.auth import verify_license_signature
from app.logging.logger import get_logger

logger = get_logger(__name__)

CONFIG_DIR = Path.home() / ".ai-teleprompter"
CACHE_FILE = CONFIG_DIR / "license_cache.json"


class ClientLicenseManager:
    """Client-side license coordinator with offline grace period caching."""

    def __init__(self, server_url: str = "http://127.0.0.1:8765"):
        self.server_url = server_url.rstrip("/")
        self.current_state: Dict[str, Any] = self._load_cache() or {
            "device_id": get_or_create_device_id(),
            "status": "active",
            "is_blocked": False,
            "usage_limit": 100,
            "usage_consumed": 0,
            "usage_remaining": 100,
            "warning_level": None,
            "contact_name": "Diwakar",
            "contact_email": "diwakar@example.com",
            "contact_phone": "+91-9876543210",
            "support_message": "For access activation or license upgrade.",
            "last_validated": datetime.utcnow().isoformat(),
        }

    def _load_cache(self) -> Optional[Dict[str, Any]]:
        """Load cached license response from disk."""
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Failed to load license cache", error=str(e))
        return None

    def _save_cache(self, state: Dict[str, Any]) -> None:
        """Save validated state to cache file."""
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        try:
            state["last_validated"] = datetime.utcnow().isoformat()
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error("Failed to write license cache", error=str(e))

    async def validate(self, app_version: str = "0.1.0") -> Dict[str, Any]:
        """Validate license with server, falling back to cached grace period if offline."""
        device_id = get_or_create_device_id()
        device_token = get_device_token()

        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                resp = await client.post(
                    f"{self.server_url}/api/v1/license/validate",
                    json={
                        "device_id": device_id,
                        "device_token": device_token,
                        "application_version": app_version,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()

                    # Verify cryptographic signature
                    sig = data.get("signature", "")
                    payload_to_verify = {
                        "device_id": data.get("device_id"),
                        "status": data.get("status"),
                        "usage_limit": data.get("usage_limit"),
                        "usage_consumed": data.get("usage_consumed"),
                    }
                    if verify_license_signature(payload_to_verify, sig):
                        self.current_state = data
                        self._save_cache(data)
                        logger.info("License validated with server", status=data.get("status"), usage=data.get("usage_consumed"))
                        return data
                    else:
                        logger.warning("License signature verification failed! Possible tampering detected.")
        except Exception as e:
            logger.warning("Server unreachable for license check; applying offline grace period", error=str(e))

        # Handle offline grace period
        return self._handle_offline_state()

    def _handle_offline_state(self) -> Dict[str, Any]:
        """Evaluate cached license against 24-hour grace period."""
        last_val_str = self.current_state.get("last_validated")
        if last_val_str:
            try:
                last_dt = datetime.fromisoformat(last_val_str)
                grace_limit = timedelta(hours=self.current_state.get("grace_period_hours", 24))
                if datetime.utcnow() - last_dt > grace_limit:
                    logger.warning("Grace period expired! Application locked until server revalidation.")
                    self.current_state["status"] = "blocked"
                    self.current_state["is_blocked"] = True
                    self.current_state["warning_level"] = "limit_reached"
                    return self.current_state
            except Exception:
                pass

        return self.current_state

    def is_allowed(self) -> bool:
        """Check whether the client is currently permitted to run teleprompter functions."""
        if self.current_state.get("is_blocked"):
            return False
        if self.current_state.get("status") == "blocked":
            return False
        limit = self.current_state.get("usage_limit", 100)
        consumed = self.current_state.get("usage_consumed", 0)
        return consumed < limit
