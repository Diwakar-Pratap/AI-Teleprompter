"""
OTA Management Service.
Handles Version repository, OTA Upgrade/Downgrade job scheduling, and progress tracking.
"""

from datetime import datetime
import hashlib
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.ota.models import AppVersion, OTAJob, Device
from app.ota.schemas import AppVersionCreate
from app.ota.audit_service import log_audit
from app.logging.logger import get_logger

logger = get_logger(__name__)

INITIAL_VERSIONS = [
    {
        "version": "v0.1.0",
        "build_number": 100,
        "package_url": "/api/v1/ota/packages/v0.1.0.zip",
        "package_hash": hashlib.sha256(b"v0.1.0-ai-teleprompter-initial-build").hexdigest(),
        "package_size": 15420100,
        "package_signature": "sig-hmac-sha256-v010-valid",
        "release_notes": "Initial release: Real-time transparent overlay, WASAPI audio loopback, and Whisper STT.",
        "minimum_supported_version": "v0.0.1",
        "status": "Active",
    },
    {
        "version": "v0.2.0",
        "build_number": 105,
        "package_url": "/api/v1/ota/packages/v0.2.0.zip",
        "package_hash": hashlib.sha256(b"v0.2.0-ai-teleprompter-ota-release").hexdigest(),
        "package_size": 16840220,
        "package_signature": "sig-hmac-sha256-v020-valid",
        "release_notes": "OTA update: Centralized SUT monitoring, license control, and en-IN voice enhancement.",
        "minimum_supported_version": "v0.1.0",
        "status": "Available",
    },
]


async def init_default_versions(session: AsyncSession) -> None:
    """Seed initial versions into repository if empty."""
    result = await session.execute(select(AppVersion))
    existing = result.scalars().all()
    if not existing:
        for v in INITIAL_VERSIONS:
            item = AppVersion(
                version=v["version"],
                build_number=v["build_number"],
                package_url=v["package_url"],
                package_hash=v["package_hash"],
                package_size=v["package_size"],
                package_signature=v["package_signature"],
                release_notes=v["release_notes"],
                minimum_supported_version=v["minimum_supported_version"],
                status=v["status"],
                release_date=datetime.utcnow(),
                created_at=datetime.utcnow(),
            )
            session.add(item)
        await session.commit()
        logger.info("Initialized default OTA versions catalog")


async def list_versions(session: AsyncSession) -> List[Dict[str, Any]]:
    """Retrieve all catalog versions."""
    result = await session.execute(select(AppVersion).order_by(desc(AppVersion.build_number)))
    versions = result.scalars().all()
    return [
        {
            "id": v.id,
            "version": v.version,
            "build_number": v.build_number,
            "package_url": v.package_url,
            "package_hash": v.package_hash,
            "package_size": v.package_size,
            "package_signature": v.package_signature,
            "release_notes": v.release_notes,
            "minimum_supported_version": v.minimum_supported_version,
            "maximum_supported_version": v.maximum_supported_version,
            "status": v.status,
            "release_date": v.release_date.isoformat(),
        }
        for v in versions
    ]


async def create_version(
    session: AsyncSession,
    data: AppVersionCreate,
    admin_user: str = "Diwakar",
) -> AppVersion:
    """Register a new release version in the catalog."""
    ver = AppVersion(
        version=data.version,
        build_number=data.build_number,
        package_url=data.package_url,
        package_hash=data.package_hash,
        package_size=data.package_size,
        package_signature=data.package_signature,
        release_notes=data.release_notes,
        minimum_supported_version=data.minimum_supported_version,
        maximum_supported_version=data.maximum_supported_version,
        status=data.status,
        release_date=datetime.utcnow(),
        created_at=datetime.utcnow(),
    )
    session.add(ver)
    await session.commit()
    await session.refresh(ver)

    await log_audit(
        session,
        "VERSION_REGISTERED",
        user_id=admin_user,
        metadata={"version": data.version, "build_number": data.build_number},
    )
    return ver


async def create_ota_job(
    session: AsyncSession,
    device_id: str,
    target_version: str,
    job_type: str = "upgrade",
    admin_user: str = "Diwakar",
) -> Optional[OTAJob]:
    """Create an OTA Upgrade or Downgrade job for an SUT."""
    # Validate device
    dev_res = await session.execute(select(Device).where(Device.device_id == device_id))
    device = dev_res.scalar_one_or_none()
    if not device:
        return None

    # Validate target version
    ver_res = await session.execute(select(AppVersion).where(AppVersion.version == target_version))
    ver = ver_res.scalar_one_or_none()
    if not ver:
        return None

    job = OTAJob(
        device_id=device_id,
        source_version=device.application_version,
        target_version=target_version,
        job_type=job_type,
        status="PENDING",
        created_by=admin_user,
        started_at=datetime.utcnow(),
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)

    await log_audit(
        session,
        "OTA_JOB_CREATED",
        device_id=device_id,
        user_id=admin_user,
        metadata={"job_id": job.id, "source": job.source_version, "target": target_version, "type": job_type},
    )
    return job


async def create_bulk_ota_jobs(
    session: AsyncSession,
    device_ids: List[str],
    target_version: str,
    admin_user: str = "Diwakar",
) -> List[OTAJob]:
    """Create independent OTA jobs for multiple selected SUTs."""
    created_jobs = []
    for d_id in device_ids:
        job = await create_ota_job(
            session=session,
            device_id=d_id,
            target_version=target_version,
            job_type="upgrade",
            admin_user=admin_user,
        )
        if job:
            created_jobs.append(job)
    return created_jobs


async def report_ota_job_progress(
    session: AsyncSession,
    job_id: str,
    device_id: str,
    device_token: str,
    status: str,
    error_message: Optional[str] = None,
) -> Optional[OTAJob]:
    """Process status reports from SUT updater agent."""
    dev_res = await session.execute(select(Device).where(Device.device_id == device_id))
    device = dev_res.scalar_one_or_none()
    if not device or device.device_token != device_token:
        return None

    job_res = await session.execute(select(OTAJob).where(OTAJob.id == job_id, OTAJob.device_id == device_id))
    job = job_res.scalar_one_or_none()
    if not job:
        return None

    job.status = status
    if error_message:
        job.error_message = error_message

    now = datetime.utcnow()
    if status == "SUCCESS":
        job.completed_at = now
        device.application_version = job.target_version
    elif status in ("FAILED", "ROLLED_BACK"):
        job.completed_at = now

    await session.commit()
    await session.refresh(job)

    await log_audit(
        session,
        f"OTA_{status}",
        device_id=device_id,
        user_id="ClientUpdater",
        metadata={"job_id": job.id, "target_version": job.target_version, "error": error_message},
    )
    return job


async def list_ota_jobs(session: AsyncSession, device_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Retrieve OTA jobs history."""
    query = select(OTAJob).order_by(desc(OTAJob.started_at))
    if device_id:
        query = query.where(OTAJob.device_id == device_id)
    result = await session.execute(query)
    jobs = result.scalars().all()

    return [
        {
            "id": j.id,
            "device_id": j.device_id,
            "source_version": j.source_version,
            "target_version": j.target_version,
            "job_type": j.job_type,
            "status": j.status,
            "error_message": j.error_message,
            "created_by": j.created_by,
            "started_at": j.started_at.isoformat(),
            "completed_at": j.completed_at.isoformat() if j.completed_at else None,
        }
        for j in jobs
    ]
