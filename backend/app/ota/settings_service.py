"""
System settings service for configurable limits and contact information.
"""

from typing import Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.ota.models import SystemSetting
from app.logging.logger import get_logger

logger = get_logger(__name__)

DEFAULT_SETTINGS: Dict[str, Dict[str, str]] = {
    "contact_name": {"value": "Diwakar", "description": "Administrator / Support contact name"},
    "contact_email": {"value": "diwakar@example.com", "description": "Support contact email"},
    "contact_phone": {"value": "+91-9876543210", "description": "Support contact telephone"},
    "support_message": {"value": "For access activation or license upgrade.", "description": "Support banner guidance message"},
    "default_free_limit": {"value": "100", "description": "Default free usage limit for new SUT installations"},
    "warning_threshold_1": {"value": "80", "description": "Warning threshold percentage level 1 (e.g. 80%)"},
    "warning_threshold_2": {"value": "90", "description": "Warning threshold percentage level 2 (e.g. 90%)"},
    "heartbeat_interval_seconds": {"value": "60", "description": "Device heartbeat interval in seconds"},
    "grace_period_hours": {"value": "24", "description": "Offline grace period in hours before forcing server re-validation"},
}


async def init_default_settings(session: AsyncSession) -> None:
    """Ensure all default system settings exist in database."""
    for key, item in DEFAULT_SETTINGS.items():
        result = await session.execute(select(SystemSetting).where(SystemSetting.key == key))
        setting = result.scalar_one_or_none()
        if not setting:
            setting = SystemSetting(key=key, value=item["value"], description=item["description"])
            session.add(setting)
    await session.commit()


async def get_all_settings(session: AsyncSession) -> Dict[str, Any]:
    """Retrieve all current system settings."""
    result = await session.execute(select(SystemSetting))
    settings = result.scalars().all()
    setting_dict = {}
    for s in settings:
        if s.key in ("default_free_limit", "warning_threshold_1", "warning_threshold_2", "heartbeat_interval_seconds", "grace_period_hours"):
            try:
                setting_dict[s.key] = int(s.value)
            except ValueError:
                setting_dict[s.key] = int(DEFAULT_SETTINGS.get(s.key, {}).get("value", 100))
        else:
            setting_dict[s.key] = s.value

    # Fill defaults if any missing
    for key, item in DEFAULT_SETTINGS.items():
        if key not in setting_dict:
            if key in ("default_free_limit", "warning_threshold_1", "warning_threshold_2", "heartbeat_interval_seconds", "grace_period_hours"):
                setting_dict[key] = int(item["value"])
            else:
                setting_dict[key] = item["value"]

    return setting_dict


async def update_setting(session: AsyncSession, key: str, value: str) -> None:
    """Update a specific setting."""
    result = await session.execute(select(SystemSetting).where(SystemSetting.key == key))
    setting = result.scalar_one_or_none()
    if setting:
        setting.value = str(value)
    else:
        setting = SystemSetting(key=key, value=str(value), description=DEFAULT_SETTINGS.get(key, {}).get("description"))
        session.add(setting)
    await session.commit()
