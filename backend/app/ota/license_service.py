"""
License Management and Server-Authoritative License Validation.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from sqlalchemy.orm import selectinload

from app.ota.models import Device, License
from app.ota.auth import sign_license_payload
from app.ota.settings_service import get_all_settings
from app.ota.audit_service import log_audit
from app.logging.logger import get_logger

logger = get_logger(__name__)


async def validate_device_license(
    session: AsyncSession,
    device_id: str,
    device_token: str,
    application_version: str = "0.1.0",
) -> Dict[str, Any]:
    """
    Validate device license with cryptographic server signature.
    Server is authoritative on usage limit, consumption, and block state.
    """
    result = await session.execute(
        select(Device).options(selectinload(Device.license)).where(Device.device_id == device_id)
    )
    device = result.scalar_one_or_none()

    if not device or device.device_token != device_token:
        return {
            "device_id": device_id,
            "status": "unauthorized",
            "is_blocked": True,
            "error": "Invalid device credentials",
        }

    settings = await get_all_settings(session)
    threshold_1 = settings.get("warning_threshold_1", 80) / 100.0
    threshold_2 = settings.get("warning_threshold_2", 90) / 100.0

    lic = device.license
    if not lic:
        lic = License(
            device_id=device.device_id,
            license_type="FREE",
            usage_limit=settings.get("default_free_limit", 100),
            usage_consumed=0,
            status="active",
        )
        session.add(lic)
        await session.commit()
        await session.refresh(lic)

    is_blocked = device.is_blocked or lic.status == "blocked"
    if lic.usage_consumed >= lic.usage_limit:
        is_blocked = True
        lic.status = "blocked"
        device.is_blocked = True
        await session.commit()

    consumed = lic.usage_consumed
    limit = lic.usage_limit
    remaining = max(0, limit - consumed)

    warning_level = None
    if is_blocked or consumed >= limit:
        warning_level = "limit_reached"
    elif limit > 0 and (consumed / limit) >= threshold_2:
        warning_level = "warning_90"
    elif limit > 0 and (consumed / limit) >= threshold_1:
        warning_level = "warning_80"

    current_status = "blocked" if is_blocked else lic.status

    payload_for_signing = {
        "device_id": device.device_id,
        "status": current_status,
        "usage_limit": limit,
        "usage_consumed": consumed,
    }
    signature = sign_license_payload(payload_for_signing)

    return {
        "device_id": device.device_id,
        "status": current_status,
        "is_blocked": is_blocked,
        "license_type": lic.license_type,
        "usage_limit": limit,
        "usage_consumed": consumed,
        "usage_remaining": remaining,
        "warning_level": warning_level,
        "expires_at": lic.expiry_date.isoformat() if lic.expiry_date else None,
        "contact_name": settings.get("contact_name", "Diwakar"),
        "contact_email": settings.get("contact_email", "diwakar@example.com"),
        "contact_phone": settings.get("contact_phone", "+91-9876543210"),
        "support_message": settings.get("support_message", "For access activation or license upgrade."),
        "signature": signature,
    }


async def list_all_licenses(session: AsyncSession) -> List[Dict[str, Any]]:
    """Retrieve all license records with associated device metadata."""
    query = select(License).options(selectinload(License.device)).order_by(desc(License.updated_at))
    result = await session.execute(query)
    licenses = result.scalars().all()

    items = []
    for lic in licenses:
        items.append({
            "id": lic.id,
            "device_id": lic.device_id,
            "device_name": lic.device.device_name if lic.device else lic.device_id,
            "hostname": lic.device.hostname if lic.device else "unknown",
            "license_type": lic.license_type,
            "usage_limit": lic.usage_limit,
            "usage_consumed": lic.usage_consumed,
            "usage_remaining": max(0, lic.usage_limit - lic.usage_consumed),
            "status": lic.status,
            "expiry_date": lic.expiry_date.isoformat() if lic.expiry_date else None,
            "grace_period_hours": lic.grace_period_hours,
            "updated_at": lic.updated_at.isoformat(),
        })
    return items


async def update_license_config(
    session: AsyncSession,
    device_id: str,
    usage_limit: Optional[int] = None,
    license_type: Optional[str] = None,
    status_val: Optional[str] = None,
    admin_user: str = "Diwakar",
) -> Optional[License]:
    """Admin configuration of a device license."""
    result = await session.execute(
        select(License).options(selectinload(License.device)).where(License.device_id == device_id)
    )
    lic = result.scalar_one_or_none()
    if not lic:
        return None

    if usage_limit is not None:
        lic.usage_limit = usage_limit
        if lic.usage_consumed < usage_limit and lic.status == "blocked" and not lic.device.is_blocked:
            lic.status = "active"

    if license_type is not None:
        lic.license_type = license_type

    if status_val is not None:
        lic.status = status_val
        if status_val == "blocked":
            lic.device.is_blocked = True
        elif status_val == "active":
            lic.device.is_blocked = False

    lic.updated_at = datetime.utcnow()
    await session.commit()

    await log_audit(
        session,
        "LICENSE_UPDATED",
        device_id,
        admin_user,
        {"usage_limit": lic.usage_limit, "type": lic.license_type, "status": lic.status},
    )
    return lic
