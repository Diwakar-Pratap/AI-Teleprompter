"""
Usage Tracking & Analytics Service.
Tracks meaningful application usage events and computes aggregated metrics for charts.
"""

from datetime import datetime, timedelta
import json
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload

from app.ota.models import Device, License, UsageEvent, OTAJob, AppVersion
from app.ota.audit_service import log_audit
from app.logging.logger import get_logger

logger = get_logger(__name__)


async def record_usage_event(
    session: AsyncSession,
    device_id: str,
    device_token: str,
    event_type: str = "tool_execution",
    application_version: str = "0.1.0",
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Record a meaningful usage event and increment server-authoritative counter."""
    result = await session.execute(
        select(Device).options(selectinload(Device.license)).where(Device.device_id == device_id)
    )
    device = result.scalar_one_or_none()

    if not device or device.device_token != device_token:
        return {"status": "unauthorized", "error": "Invalid device credentials"}

    lic = device.license
    if not lic:
        lic = License(
            device_id=device.device_id,
            license_type="FREE",
            usage_limit=100,
            usage_consumed=0,
            status="active",
        )
        session.add(lic)

    # Save event
    meta_str = json.dumps(metadata) if metadata else None
    now = datetime.utcnow()
    event = UsageEvent(
        device_id=device_id,
        event_type=event_type,
        application_version=application_version,
        metadata_json=meta_str,
        timestamp=now,
    )
    session.add(event)

    # Increment usage counter
    lic.usage_consumed += 1
    lic.updated_at = now

    # Check limit enforcement
    if lic.usage_consumed >= lic.usage_limit:
        lic.status = "blocked"
        device.is_blocked = True
        device.status = "blocked"
        await log_audit(
            session,
            "LICENSE_LIMIT_REACHED",
            device_id,
            "System",
            {"usage_consumed": lic.usage_consumed, "usage_limit": lic.usage_limit},
        )

    await session.commit()

    return {
        "status": "ok",
        "device_id": device_id,
        "usage_consumed": lic.usage_consumed,
        "usage_limit": lic.usage_limit,
        "is_blocked": device.is_blocked or lic.status == "blocked",
        "license_status": lic.status,
    }


async def get_usage_analytics(session: AsyncSession) -> Dict[str, Any]:
    """Compute usage metrics, daily trends, device breakdown, and version adoption."""
    # Total executions
    total_execs_result = await session.execute(select(func.count(UsageEvent.id)))
    total_executions = total_execs_result.scalar_one() or 0

    # Daily usage for last 14 days
    now = datetime.utcnow()
    start_date = now - timedelta(days=14)
    events_result = await session.execute(
        select(UsageEvent).where(UsageEvent.timestamp >= start_date).order_by(UsageEvent.timestamp)
    )
    recent_events = events_result.scalars().all()

    daily_map = {}
    for i in range(14):
        day_str = (now - timedelta(days=13 - i)).strftime("%Y-%m-%d")
        daily_map[day_str] = 0

    for ev in recent_events:
        d_str = ev.timestamp.strftime("%Y-%m-%d")
        if d_str in daily_map:
            daily_map[d_str] += 1

    daily_usage = [{"date": k, "count": v} for k, v in daily_map.items()]

    # Devices & Licenses
    dev_result = await session.execute(select(Device).options(selectinload(Device.license)))
    devices = dev_result.scalars().all()

    total_devices = len(devices)
    blocked_count = sum(1 for d in devices if d.is_blocked or (d.license and d.license.status == "blocked"))
    timeout = timedelta(minutes=2)
    online_count = sum(1 for d in devices if (now - d.last_heartbeat) < timeout and not d.is_blocked)
    offline_count = max(0, total_devices - online_count - blocked_count)
    licensed_count = sum(1 for d in devices if d.license and d.license.license_type in ("PAID", "ENTERPRISE"))
    free_count = total_devices - licensed_count

    # Version distribution
    ver_map: Dict[str, int] = {}
    for d in devices:
        ver = d.application_version or "v0.1.0"
        ver_map[ver] = ver_map.get(ver, 0) + 1

    version_distribution = [
        {"version": k, "count": v, "percentage": round((v / max(1, total_devices)) * 100, 1)}
        for k, v in ver_map.items()
    ]

    # Top active devices
    top_devs = sorted(
        [
            {
                "device_id": d.device_id,
                "hostname": d.hostname,
                "usage_count": d.license.usage_consumed if d.license else 0,
                "usage_limit": d.license.usage_limit if d.license else 100,
                "status": d.status,
            }
            for d in devices
        ],
        key=lambda x: x["usage_count"],
        reverse=True,
    )[:10]

    # Free limit exhaustion rate
    exhausted_count = sum(
        1 for d in devices if d.license and d.license.usage_consumed >= d.license.usage_limit
    )
    exhaustion_rate = round((exhausted_count / max(1, total_devices)) * 100, 1)

    # OTA Updates stats
    ota_jobs_result = await session.execute(select(OTAJob))
    all_ota_jobs = ota_jobs_result.scalars().all()
    total_updates = len(all_ota_jobs)
    success_updates = sum(1 for j in all_ota_jobs if j.status == "SUCCESS")
    failed_updates = sum(1 for j in all_ota_jobs if j.status in ("FAILED", "ROLLED_BACK"))

    # Active/latest version
    latest_ver_result = await session.execute(
        select(AppVersion).where(AppVersion.status == "Active").order_by(desc(AppVersion.release_date))
    )
    active_ver = latest_ver_result.scalar_one_or_none()
    current_version_str = active_ver.version if active_ver else "v0.1.0"

    return {
        "summary": {
            "total_devices": total_devices,
            "online_devices": online_count,
            "offline_devices": offline_count,
            "blocked_devices": blocked_count,
            "licensed_devices": licensed_count,
            "free_trial_devices": free_count,
            "current_version": current_version_str,
            "total_updates": total_updates,
            "successful_updates": success_updates,
            "failed_updates": failed_updates,
            "exhaustion_rate_percent": exhaustion_rate,
            "total_executions": total_executions,
        },
        "daily_usage": daily_usage,
        "version_distribution": version_distribution,
        "top_active_devices": top_devs,
    }
