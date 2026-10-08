"""
FastAPI Routes for OTA Management, SUT Monitoring, License Control, and Admin Dashboard.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database.engine import get_session
from app.ota.models import User
from app.ota.schemas import (
    UserLogin,
    TokenResponse,
    UserOut,
    DeviceRegisterRequest,
    DeviceHeartbeatRequest,
    DeviceHeartbeatResponse,
    LicenseValidateRequest,
    LicenseValidateResponse,
    LicenseUpdateRequest,
    UsageEventCreate,
    AppVersionCreate,
    AppVersionOut,
    OTAJobCreate,
    BulkOTAJobCreate,
    OTAJobReportRequest,
    SystemSettingsOut,
    SystemSettingsUpdate,
)
from app.ota.auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_admin,
)
import app.ota.device_service as device_service
import app.ota.license_service as license_service
import app.ota.usage_service as usage_service
import app.ota.ota_service as ota_service
import app.ota.settings_service as settings_service
import app.ota.audit_service as audit_service
from app.logging.logger import get_logger

logger = get_logger(__name__)

ota_router = APIRouter(tags=["OTA Management & Licensing"])


# ─── Auth Endpoints ───────────────────────────────────────────────────────────
@ota_router.post("/auth/login", response_model=TokenResponse)
async def login_admin(
    credentials: UserLogin,
    session: AsyncSession = Depends(get_session),
):
    """Authenticate administrator to access the OTA Management Dashboard."""
    result = await session.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()

    # Fallback to create initial admin if database is empty
    if not user and credentials.email in ("admin@teleprompter.local", "diwakar@example.com"):
        user = User(
            name="Diwakar",
            email=credentials.email,
            password_hash=hash_password(credentials.password),
            role="admin",
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

    if not user or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = create_access_token({"sub": user.id, "email": user.email, "role": user.role, "name": user.name})
    return {
        "access_token": token,
        "token_type": "bearer",
        "user_name": user.name,
        "user_email": user.email,
        "role": user.role,
    }


@ota_router.get("/auth/me")
async def get_current_user(admin: Dict[str, Any] = Depends(get_current_admin)):
    """Validate active admin session."""
    return {"status": "ok", "admin": admin}


# ─── Device / SUT Endpoints ───────────────────────────────────────────────────
@ota_router.post("/devices/register")
async def register_device(
    payload: DeviceRegisterRequest,
    session: AsyncSession = Depends(get_session),
):
    """Register or update an SUT installation profile."""
    device, token = await device_service.register_or_update_device(session, payload)
    return {
        "status": "registered",
        "device_id": device.device_id,
        "device_token": token,
        "application_version": device.application_version,
    }


@ota_router.post("/devices/heartbeat")
async def device_heartbeat(
    payload: DeviceHeartbeatRequest,
    session: AsyncSession = Depends(get_session),
):
    """Periodic client heartbeat, synchronizing presence, limits, and pending OTA jobs."""
    result = await device_service.process_heartbeat(session, payload)
    if result.get("status") == "unauthorized":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid device credentials")
    return result


@ota_router.get("/devices")
async def get_all_devices(
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """List all SUTs with search and status filters for Dashboard."""
    return await device_service.list_devices(session, search=search, status_filter=status_filter)


@ota_router.get("/devices/{device_id}")
async def get_device_info(
    device_id: str,
    session: AsyncSession = Depends(get_session),
):
    """Retrieve detailed hardware specs, license, and OTA history for a single SUT."""
    device = await device_service.get_device_detail(session, device_id)
    if not device:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    return device


async def broadcast_license_update(device_id: str, session: AsyncSession) -> None:
    """Broadcast real-time license and blocked/unblocked status to all active WebSocket clients."""
    try:
        from app.api.websocket import manager
        from app.ota.device_service import get_device_by_id
        from app.ota.settings_service import get_system_settings
        from app.ota.agent.identity import get_or_create_device_id
        from app.ota.agent.license_client import ClientLicenseManager

        dev = await get_device_by_id(session, device_id)
        if not dev:
            return
        settings = await get_system_settings(session)
        lic = dev.license
        is_blk = bool(dev.is_blocked or (lic and lic.status == "blocked"))
        status_val = "blocked" if is_blk else (lic.status if lic else "active")
        usage_consumed = lic.usage_consumed if lic else 0
        usage_limit = lic.usage_limit if lic else 100
        usage_remaining = max(0, usage_limit - usage_consumed)

        warning_level = None
        if usage_consumed >= usage_limit:
            warning_level = "limit_reached"
        elif usage_consumed >= int(usage_limit * 0.9):
            warning_level = "warning_90"
        elif usage_consumed >= int(usage_limit * 0.8):
            warning_level = "warning_80"

        payload = {
            "device_id": device_id,
            "status": status_val,
            "is_blocked": is_blk,
            "usage_limit": usage_limit,
            "usage_consumed": usage_consumed,
            "usage_remaining": usage_remaining,
            "warning_level": warning_level,
            "contact_name": settings.contact_name,
            "contact_email": settings.contact_email,
            "contact_phone": settings.contact_phone,
            "support_message": settings.support_message,
        }

        # Broadcast real-time events over WebSocket to all desktop overlays
        await manager.broadcast_event("license.status", payload)
        if is_blk:
            await manager.broadcast_event("license.blocked", payload)

        # If this device is the local host's device, sync local ClientLicenseManager cache as well
        local_id = get_or_create_device_id()
        if device_id == local_id:
            lic_mgr = ClientLicenseManager()
            lic_mgr.current_state.update(payload)
            lic_mgr._save_cache(lic_mgr.current_state)
            logger.info("Local SUT license state synchronized with remote block status", is_blocked=is_blk)
    except Exception as e:
        logger.warning("Failed to broadcast license update", device_id=device_id, error=str(e))


@ota_router.post("/devices/{device_id}/block")
async def block_device_endpoint(
    device_id: str,
    admin: Dict[str, Any] = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    """Remotely block an SUT."""
    success = await device_service.block_device(session, device_id, admin_user=admin.get("name", "Diwakar"))
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    await broadcast_license_update(device_id, session)
    return {"status": "ok", "message": f"Device {device_id} has been blocked"}


@ota_router.post("/devices/{device_id}/unblock")
async def unblock_device_endpoint(
    device_id: str,
    admin: Dict[str, Any] = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    """Remotely unblock an SUT."""
    success = await device_service.unblock_device(session, device_id, admin_user=admin.get("name", "Diwakar"))
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    await broadcast_license_update(device_id, session)
    return {"status": "ok", "message": f"Device {device_id} has been unblocked"}


@ota_router.post("/devices/{device_id}/reset-usage")
async def reset_usage_endpoint(
    device_id: str,
    admin: Dict[str, Any] = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    """Reset free usage counter back to 0 for an SUT."""
    success = await device_service.reset_device_usage(session, device_id, admin_user=admin.get("name", "Diwakar"))
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device or license not found")
    await broadcast_license_update(device_id, session)
    return {"status": "ok", "message": f"Usage reset to 0 for {device_id}"}


@ota_router.post("/devices/{device_id}/revoke")
async def revoke_device_endpoint(
    device_id: str,
    admin: Dict[str, Any] = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    """Revoke credentials of an SUT."""
    success = await device_service.revoke_device(session, device_id, admin_user=admin.get("name", "Diwakar"))
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Device not found")
    await broadcast_license_update(device_id, session)
    return {"status": "ok", "message": f"Device credentials revoked for {device_id}"}


# ─── License Endpoints ────────────────────────────────────────────────────────
@ota_router.post("/license/validate", response_model=LicenseValidateResponse)
async def validate_license(
    payload: LicenseValidateRequest,
    session: AsyncSession = Depends(get_session),
):
    """Authoritative license validation with cryptographic signature."""
    res = await license_service.validate_device_license(
        session,
        device_id=payload.device_id,
        device_token=payload.device_token,
        application_version=payload.application_version,
    )
    if res.get("status") == "unauthorized":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid device credentials")
    return res


@ota_router.get("/licenses")
async def get_licenses(session: AsyncSession = Depends(get_session)):
    """Retrieve all device licenses."""
    return await license_service.list_all_licenses(session)


@ota_router.put("/licenses/{device_id}")
async def update_license(
    device_id: str,
    payload: LicenseUpdateRequest,
    admin: Dict[str, Any] = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    """Update license parameters (limit, type, status)."""
    lic = await license_service.update_license_config(
        session,
        device_id=device_id,
        usage_limit=payload.usage_limit,
        license_type=payload.license_type,
        status_val=payload.status,
        admin_user=admin.get("name", "Diwakar"),
    )
    if not lic:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="License not found")
    await broadcast_license_update(device_id, session)
    return {"status": "ok", "message": "License updated successfully"}


# ─── Usage Tracking & Analytics ───────────────────────────────────────────────
@ota_router.post("/usage/events")
async def record_usage(
    payload: UsageEventCreate,
    session: AsyncSession = Depends(get_session),
):
    """Client records a meaningful usage execution event."""
    result = await usage_service.record_usage_event(
        session,
        device_id=payload.device_id,
        device_token=payload.device_token,
        event_type=payload.event_type,
        application_version=payload.application_version,
        metadata=payload.metadata,
    )
    if result.get("status") == "unauthorized":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return result


@ota_router.get("/usage/analytics")
async def get_analytics(session: AsyncSession = Depends(get_session)):
    """Retrieve aggregated usage trends, version adoption, and KPI metrics."""
    return await usage_service.get_usage_analytics(session)


# ─── Versions & OTA Job Endpoints ─────────────────────────────────────────────
@ota_router.get("/versions")
async def get_versions(session: AsyncSession = Depends(get_session)):
    """List available OTA versions in repository."""
    return await ota_service.list_versions(session)


@ota_router.post("/versions")
async def create_new_version(
    payload: AppVersionCreate,
    admin: Dict[str, Any] = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    """Admin registers a new OTA package version."""
    ver = await ota_service.create_version(session, payload, admin_user=admin.get("name", "Diwakar"))
    return {"status": "ok", "version": ver.version}


@ota_router.get("/ota/jobs")
async def get_ota_jobs(
    device_id: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
):
    """Retrieve list of OTA jobs."""
    return await ota_service.list_ota_jobs(session, device_id=device_id)


@ota_router.post("/ota/jobs")
async def schedule_ota_job(
    payload: OTAJobCreate,
    admin: Dict[str, Any] = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    """Admin schedules an OTA upgrade or downgrade job for an SUT."""
    job = await ota_service.create_ota_job(
        session,
        device_id=payload.device_id,
        target_version=payload.target_version,
        job_type=payload.job_type,
        admin_user=admin.get("name", "Diwakar"),
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid device or version")
    return {"status": "ok", "job_id": job.id, "target_version": job.target_version}


@ota_router.post("/ota/jobs/bulk")
async def schedule_bulk_ota_jobs(
    payload: BulkOTAJobCreate,
    admin: Dict[str, Any] = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    """Admin schedules OTA updates for multiple selected SUTs."""
    jobs = await ota_service.create_bulk_ota_jobs(
        session,
        device_ids=payload.device_ids,
        target_version=payload.target_version,
        admin_user=admin.get("name", "Diwakar"),
    )
    return {"status": "ok", "created_jobs_count": len(jobs)}


@ota_router.post("/ota/report")
async def report_job_progress(
    payload: OTAJobReportRequest,
    session: AsyncSession = Depends(get_session),
):
    """Client reports OTA installation progress and health check results."""
    job = await ota_service.report_ota_job_progress(
        session,
        job_id=payload.job_id,
        device_id=payload.device_id,
        device_token=payload.device_token,
        status=payload.status,
        error_message=payload.error_message,
    )
    if not job:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Failed to report progress")
    return {"status": "ok", "job_status": job.status}


# ─── System Settings Endpoints ────────────────────────────────────────────────
@ota_router.get("/settings/system", response_model=SystemSettingsOut)
async def get_system_settings(session: AsyncSession = Depends(get_session)):
    """Retrieve system configuration (Contact details, Free Limits, Intervals)."""
    return await settings_service.get_all_settings(session)


@ota_router.put("/settings/system")
async def update_system_settings(
    payload: SystemSettingsUpdate,
    admin: Dict[str, Any] = Depends(get_current_admin),
    session: AsyncSession = Depends(get_session),
):
    """Admin updates system configuration."""
    for key, val in payload.model_dump(exclude_unset=True).items():
        if val is not None:
            await settings_service.update_setting(session, key, str(val))
    return {"status": "ok", "message": "Settings updated"}


# ─── Audit Logs Endpoint ──────────────────────────────────────────────────────
@ota_router.get("/audit-logs")
async def get_audit_history(
    device_id: Optional[str] = Query(None),
    limit: int = Query(100),
    session: AsyncSession = Depends(get_session),
):
    """Retrieve audit trail of all administrative and system events."""
    logs = await audit_service.get_audit_logs(session, limit=limit, device_id=device_id)
    return [
        {
            "id": l.id,
            "user_id": l.user_id,
            "device_id": l.device_id,
            "action": l.action,
            "metadata_json": l.metadata_json,
            "timestamp": l.timestamp.isoformat(),
        }
        for l in logs
    ]
