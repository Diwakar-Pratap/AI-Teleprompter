"""
Pydantic schemas for OTA Management, SUT Monitoring & License Control.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ─── Auth Schemas ─────────────────────────────────────────────────────────────
class UserLogin(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_name: str
    user_email: str
    role: str


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    role: str
    is_active: bool
    created_at: datetime


# ─── Device Schemas ───────────────────────────────────────────────────────────
class DeviceRegisterRequest(BaseModel):
    device_id: str
    device_name: Optional[str] = None
    hostname: str
    os: str
    os_version: str
    cpu: str
    ram: str
    disk_space: str
    ip_address: Optional[str] = "127.0.0.1"
    mac_address: Optional[str] = None
    python_version: Optional[str] = None
    application_version: str = "0.1.0"
    agent_version: str = "1.0.0"


class DeviceHeartbeatRequest(BaseModel):
    device_id: str
    device_token: str
    hostname: Optional[str] = None
    app_version: Optional[str] = None
    agent_version: Optional[str] = None
    os: Optional[str] = None
    last_activity: Optional[str] = None
    usage_count: Optional[int] = None


class DeviceHeartbeatResponse(BaseModel):
    status: str  # "ok"
    device_id: str
    license_status: str  # "active", "blocked", "expired"
    is_blocked: bool
    usage_limit: int
    usage_consumed: int
    pending_ota_job: Optional[Dict[str, Any]] = None
    contact_info: Dict[str, str]


class DeviceOut(BaseModel):
    id: int
    device_id: str
    device_name: Optional[str]
    hostname: str
    os: str
    os_version: str
    cpu: str
    ram: str
    disk_space: str
    ip_address: Optional[str]
    mac_address: Optional[str]
    python_version: Optional[str]
    application_version: str
    agent_version: str
    status: str
    is_blocked: bool
    last_seen: datetime
    last_heartbeat: datetime
    installation_date: datetime
    usage_count: int = 0
    usage_limit: int = 100
    license_status: str = "active"


# ─── License Schemas ──────────────────────────────────────────────────────────
class LicenseValidateRequest(BaseModel):
    device_id: str
    device_token: str
    application_version: str = "0.1.0"


class LicenseValidateResponse(BaseModel):
    device_id: str
    status: str  # "active", "blocked", "expired"
    is_blocked: bool
    license_type: str
    usage_limit: int
    usage_consumed: int
    usage_remaining: int
    warning_level: Optional[str] = None  # None, "warning_80", "warning_90", "limit_reached"
    expires_at: Optional[str] = None
    contact_name: str = "Diwakar"
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    support_message: str = "For access activation or license upgrade."
    signature: str


class LicenseOut(BaseModel):
    id: int
    device_id: str
    license_type: str
    usage_limit: int
    usage_consumed: int
    status: str
    expiry_date: Optional[datetime]
    grace_period_hours: int
    updated_at: datetime


class LicenseUpdateRequest(BaseModel):
    usage_limit: Optional[int] = None
    license_type: Optional[str] = None
    status: Optional[str] = None


# ─── Usage Schemas ────────────────────────────────────────────────────────────
class UsageEventCreate(BaseModel):
    device_id: str
    device_token: str
    event_type: str = "application_launch"
    application_version: str = "0.1.0"
    metadata: Optional[Dict[str, Any]] = None


class UsageAnalyticsResponse(BaseModel):
    total_executions: int
    daily_usage: List[Dict[str, Any]]
    weekly_usage: List[Dict[str, Any]]
    device_usage_distribution: List[Dict[str, Any]]
    version_distribution: List[Dict[str, Any]]
    top_active_devices: List[Dict[str, Any]]
    exhaustion_rate_percent: float


# ─── Version Schemas ──────────────────────────────────────────────────────────
class AppVersionCreate(BaseModel):
    version: str
    build_number: int = 1
    package_url: str
    package_hash: str
    package_size: int = 0
    package_signature: Optional[str] = None
    release_notes: Optional[str] = None
    minimum_supported_version: Optional[str] = "v0.0.1"
    maximum_supported_version: Optional[str] = None
    status: str = "Active"


class AppVersionOut(BaseModel):
    id: int
    version: str
    build_number: int
    package_url: str
    package_hash: str
    package_size: int
    package_signature: Optional[str]
    release_notes: Optional[str]
    status: str
    release_date: datetime


# ─── OTA Job Schemas ──────────────────────────────────────────────────────────
class OTAJobCreate(BaseModel):
    device_id: str
    target_version: str
    job_type: str = "upgrade"  # "upgrade", "downgrade"


class BulkOTAJobCreate(BaseModel):
    device_ids: List[str]
    target_version: str


class OTAJobReportRequest(BaseModel):
    job_id: str
    device_id: str
    device_token: str
    status: str  # DOWNLOADING, VERIFYING, INSTALLING, RESTARTING, HEALTH_CHECK, SUCCESS, FAILED, ROLLBACK, ROLLED_BACK
    error_message: Optional[str] = None


class OTAJobOut(BaseModel):
    id: str
    device_id: str
    source_version: str
    target_version: str
    job_type: str
    status: str
    error_message: Optional[str]
    created_by: str
    started_at: datetime
    completed_at: Optional[datetime]


# ─── System Settings Schemas ──────────────────────────────────────────────────
class SystemSettingsOut(BaseModel):
    contact_name: str
    contact_email: str
    contact_phone: str
    support_message: str
    default_free_limit: int
    warning_threshold_1: int
    warning_threshold_2: int
    heartbeat_interval_seconds: int
    grace_period_hours: int


class SystemSettingsUpdate(BaseModel):
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    support_message: Optional[str] = None
    default_free_limit: Optional[int] = None
    warning_threshold_1: Optional[int] = None
    warning_threshold_2: Optional[int] = None
    heartbeat_interval_seconds: Optional[int] = None
    grace_period_hours: Optional[int] = None


# ─── Audit Log Schemas ────────────────────────────────────────────────────────
class AuditLogOut(BaseModel):
    id: int
    user_id: Optional[str]
    device_id: Optional[str]
    action: str
    metadata_json: Optional[str]
    timestamp: datetime
