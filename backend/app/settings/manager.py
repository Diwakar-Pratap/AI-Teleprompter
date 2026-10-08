"""
Settings manager — Phase 1 stub.
Full implementation in Phase 2 with database persistence.
"""

from app.logging.logger import get_logger

logger = get_logger(__name__)


class SettingsManager:
    """Manages application settings."""

    async def initialize(self) -> None:
        """Load settings from database (Phase 1: no-op)."""
        logger.info("SettingsManager initialized (Phase 1 stub)")

    async def get(self, key: str, default=None):
        """Get a setting value."""
        return default

    async def set(self, key: str, value) -> None:
        """Set a setting value."""
        logger.debug("Setting updated", key=key)
