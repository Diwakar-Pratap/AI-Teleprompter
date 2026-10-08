"""
Device / SUT Management Service.
Handles registration, heartbeat, online/offline tracking, specs, and admin actions.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc
from sqlalchemy.orm import selectinload

from app.ota.models import Device, License, OTAJob, UsageEvent
from app.ota.schemas import DeviceRegisterRequest, DeviceHeartbeatRequest
from app.ota.auth import generate_device_token
from app.ota.settings_service import get_all_settings
from app.ota.audit_service import log_audit
from app.logging.logger import get_logger

logger = get_logger(__name__)


async def register_or_update_device(
    session: AsyncSession,
    data: DeviceRegisterRequest,
) -> Tuple[Device, str]:
    """Register a new SUT or update its hardware specification upon startup."""
    result = await session.execute(
        select(Device).options(selectinload(Device.license)).where(Device.device_id == data.device_id)
    )
    device = result.scalar_one_or_none()
    settings = await get_all_settings(session)
    default_limit = settings.get("default_free_limit", 100)

    now = datetime.utcnow()

    if not device:
        token = generate_device_token()
        device = Device(
            device_id=data.device_id,
            device_token=token,
            device_name=data.device_name or data.hostname,
            hostname=data.hostname,
            os=data.os,
            os_version=data.os_version,
            cpu=data.cpu,
            ram=data.ram,
            disk_space=data.disk_space,
            ip_address=data.ip_address,
            mac_address=data.mac_address,
            python_version=data.python_version,
            application_version=data.application_version,
            agent_version=data.agent_version,
            status="online",
            is_blocked=False,
            last_seen=now,
            last_heartbeat=now,
            installation_date=now,
            created_at=now,
        )
        session.add(device)

        # Create corresponding License record
        license_obj = License(
            device_id=data.device_id,
            license_type="FREE",
            usage_limit=default_limit,
            usage_consumed=0,
            status="active",
            grace_period_hours=settings.get("grace_period_hours", 24),
            created_at=now,
            updated_at=now,
        )
        session.add(license_obj)
        await session.commit()
        await session.refresh(device)

        await log_audit(
            session=session,
            action="DEVICE_REGISTERED",
            device_id=data.device_id,
            user_id="Client",
            metadata={"hostname": data.hostname, "app_version": data.application_version},
        )
        logger.info("New SUT registered", device_id=data.device_id, hostname=data.hostname)
        return device, token

    else:
        # Update device specs
        device.hostname = data.hostname
        device.os = data.os
        device.os_version = data.os_version
        device.cpu = data.cpu
        device.ram = data.ram
        device.disk_space = data.disk_space
        device.ip_address = data.ip_address
        device.mac_address = data.mac_address or device.mac_address
        device.python_version = data.python_version or device.python_version
        device.application_version = data.application_version
        device.agent_version = data.agent_version
        device.last_seen = now
        device.last_heartbeat = now
        if not device.is_blocked:
            device.status = "online"

        await session.commit()
        await session.refresh(device)
        return device, device.device_token


async def process_heartbeat(
    session: AsyncSession,
    data: DeviceHeartbeatRequest,
) -> Dict[str, Any]:
    """Process incoming client heartbeat, update online status, and return state."""
    result = await session.execute(
        select(Device).options(selectinload(Device.license)).where(Device.device_id == data.device_id)
    )
    device = result.scalar_one_or_none()

    if not device or device.device_token != data.device_token:
        return {"status": "unauthorized", "error": "Invalid device credentials"}

    now = datetime.utcnow()
    device.last_seen = now
    device.last_heartbeat = now
    if data.app_version:
        device.application_version = data.app_version
    if data.agent_version:
        device.agent_version = data.agent_version

    license_obj = device.license
    if not license_obj:
        license_obj = License(
            device_id=device.device_id,
            license_type="FREE",
            usage_limit=100,
            usage_consumed=0,
            status="active",
        )
        session.add(license_obj)

    # Sync usage if reported higher
    if data.usage_count is not None and data.usage_count > license_obj.usage_consumed:
        license_obj.usage_consumed = data.usage_count

    # Check limits
    if license_obj.usage_consumed >= license_obj.usage_limit:
        license_obj.status = "blocked"
        device.is_blocked = True

    if device.is_blocked:
        device.status = "blocked"
        license_obj.status = "blocked"
    else:
        device.status = "online"

    await session.commit()

    # Check for pending OTA job
    job_result = await session.execute(
        select(OTAJob)
        .where(OTAJob.device_id == device.device_id, OTAJob.status == "PENDING")
        .order_by(desc(OTAJob.started_at))
    )
    pending_job = job_result.scalar_one_or_none()
    pending_job_dict = None
    if pending_job:
        # Fetch package details
        from app.ota.models import AppVersion
        ver_result = await session.execute(select(AppVersion).where(AppVersion.version == pending_job.target_version))
        ver = ver_result.scalar_one_or_none()
        pending_job_dict = {
            "job_id": pending_job.id,
            "target_version": pending_job.target_version,
            "source_version": pending_job.source_version,
            "job_type": pending_job.job_type,
            "package_url": ver.package_url if ver else "",
            "package_hash": ver.package_hash if ver else "",
            "package_signature": ver.package_signature if ver else "",
        }

    settings = await get_all_settings(session)

    return {
        "status": "ok",
        "device_id": device.device_id,
        "license_status": license_obj.status,
        "is_blocked": device.is_blocked or license_obj.status == "blocked",
        "usage_limit": license_obj.usage_limit,
        "usage_consumed": license_obj.usage_consumed,
        "pending_ota_job": pending_job_dict,
        "contact_info": {
            "contact_name": settings.get("contact_name", "Diwakar"),
            "contact_email": settings.get("contact_email", "diwakar@example.com"),
            "contact_phone": settings.get("contact_phone", "+91-9876543210"),
            "support_message": settings.get("support_message", "For access activation or license upgrade."),
        },
    }


async def list_devices(
    session: AsyncSession,
    search: Optional[str] = None,
    status_filter: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Retrieve list of devices with computed online/offline statuses and usage."""
    query = select(Device).options(selectinload(Device.license)).order_by(desc(Device.last_seen))
    result = await session.execute(query)
    devices = result.scalars().all()

    now = datetime.utcnow()
    timeout = timedelta(minutes=2)

    device_list = []
    for d in devices:
        is_online = (now - d.last_heartbeat) < timeout
        computed_status = "blocked" if d.is_blocked else ("online" if is_online else "offline")

        if status_filter and computed_status != status_filter:
            continue

        if search:
            s_lower = search.lower()
            if (
                s_lower not in d.device_id.lower()
                and s_lower not in d.hostname.lower()
                and s_lower not in (d.ip_address or "").lower()
                and s_lower not in d.application_version.lower()
            ):
                continue

        lic = d.license
        device_list.append({
            "id": d.id,
            "device_id": d.device_id,
            "device_name": d.device_name or d.hostname,
            "hostname": d.hostname,
            "os": d.os,
            "os_version": d.os_version,
            "cpu": d.cpu,
            "ram": d.ram,
            "disk_space": d.disk_space,
            "ip_address": d.ip_address,
            "mac_address": d.mac_address,
            "python_version": d.python_version,
            "application_version": d.application_version,
            "agent_version": d.agent_version,
            "status": computed_status,
            "is_blocked": d.is_blocked,
            "last_seen": d.last_seen.isoformat(),
            "last_heartbeat": d.last_heartbeat.isoformat(),
            "installation_date": d.installation_date.isoformat(),
            "usage_count": lic.usage_consumed if lic else 0,
            "usage_limit": lic.usage_limit if lic else 100,
            "license_status": lic.status if lic else "active",
        })

    return device_list


async def get_device_detail(session: AsyncSession, device_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve comprehensive details of a single SUT."""
    result = await session.execute(
        select(Device)
        .options(selectinload(Device.license), selectinload(Device.ota_jobs))
        .where(Device.device_id == device_id)
    )
    device = result.scalar_one_or_none()
    if not device:
        return None

    now = datetime.utcnow()
    is_online = (now - device.last_heartbeat) < timedelta(minutes=2)
    computed_status = "blocked" if device.is_blocked else ("online" if is_online else "offline")

    lic = device.license

    # Fetch recent OTA jobs
    jobs = [
        {
            "id": j.id,
            "source_version": j.source_version,
            "target_version": j.target_version,
            "job_type": j.job_type,
            "status": j.status,
            "error_message": j.error_message,
            "created_by": j.created_by,
            "started_at": j.started_at.isoformat(),
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        }
        for j in sorted(device.ota_jobs, key=lambda x: x.started_at, reverse=True)[:10]
    ]

    return {
        "id": device.id,
        "device_id": device.device_id,
        "device_name": device.device_name or device.hostname,
        "hostname": device.hostname,
        "os": device.os,
        "os_version": device.os_version,
        "cpu": device.cpu,
        "ram": device.ram,
        "disk_space": device.disk_space,
        "ip_address": device.ip_address,
        "mac_address": device.mac_address,
        "python_version": device.python_version,
        "application_version": device.application_version,
        "agent_version": device.agent_version,
        "status": computed_status,
        "is_blocked": device.is_blocked,
        "last_seen": device.last_seen.isoformat(),
        "last_heartbeat": device.last_heartbeat.isoformat(),
        "installation_date": device.installation_date.isoformat(),
        "license": {
            "status": lic.status if lic else "active",
            "license_type": lic.license_type if lic else "FREE",
            "usage_limit": lic.usage_limit if lic else 100,
            "usage_consumed": lic.usage_consumed if lic else 0,
            "usage_remaining": max(0, (lic.usage_limit - lic.usage_consumed)) if lic else 100,
            "grace_period_hours": lic.grace_period_hours if lic else 24,
            "expiry_date": lic.expiry_date.isoformat() if lic and lic.expiry_date else None,
        },
        "ota_jobs": jobs,
    }


async def block_device(session: AsyncSession, device_id: str, admin_user: str = "Diwakar") -> bool:
    """Remotely block an SUT."""
    result = await session.execute(
        select(Device).options(selectinload(Device.license)).where(Device.device_id == device_id)
    )
    device = result.scalar_one_or_none()
    if not device:
        return False

    device.is_blocked = True
    device.status = "blocked"
    if device.license:
        device.license.status = "blocked"

    await session.commit()
    await log_audit(session, "DEVICE_BLOCKED", device_id, admin_user)
    return True


async def unblock_device(session: AsyncSession, device_id: str, admin_user: str = "Diwakar") -> bool:
    """Remotely unblock an SUT."""
    result = await session.execute(
        select(Device).options(selectinload(Device.license)).where(Device.device_id == device_id)
    )
    device = result.scalar_one_or_none()
    if not device:
        return False

    device.is_blocked = False
    device.status = "online"
    if device.license:
        # If usage consumed reached limit, bump limit or allow active
        if device.license.usage_consumed >= device.license.usage_limit:
            device.license.usage_limit = device.license.usage_consumed + 50
        device.license.status = "active"

    await session.commit()
    await log_audit(session, "DEVICE_UNBLOCKED", device_id, admin_user)
    return True


async def reset_device_usage(session: AsyncSession, device_id: str, admin_user: str = "Diwakar") -> bool:
    """Reset the consumed usage counter for an SUT back to 0."""
    result = await session.execute(
        select(Device).options(selectinload(Device.license)).where(Device.device_id == device_id)
    )
    device = result.scalar_one_or_none()
    if not device or not device.license:
        return False

    old_usage = device.license.usage_consumed
    device.license.usage_consumed = 0
    device.is_blocked = False
    device.license.status = "active"
    device.status = "online"

    await session.commit()
    await log_audit(
        session,
        "USAGE_RESET",
        device_id,
        admin_user,
        {"previous_usage": old_usage, "new_usage": 0},
    )
    return True


async def revoke_device(session: AsyncSession, device_id: str, admin_user: str = "Diwakar") -> bool:
    """Revoke an SUT's credentials by rotating device_token."""
    result = await session.execute(select(Device).where(Device.device_id == device_id))
    device = result.scalar_one_or_none()
    if not device:
        return False

    device.device_token = generate_device_token()
    device.is_blocked = True
    device.status = "blocked"
    if device.license:
        device.license.status = "blocked"

    await session.commit()
    await log_audit(session, "DEVICE_REVOKED", device_id, admin_user)
    return True
