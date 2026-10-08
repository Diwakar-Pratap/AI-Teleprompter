"""
SQLAlchemy ORM models for OTA Management, SUT Monitoring & License Control.
"""

from datetime import datetime
from typing import Optional
import uuid

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import relationship

from app.database.engine import Base


class User(Base):
    """Admin user table for Dashboard authentication."""
    __tablename__ = "ota_users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(50), default="admin", nullable=False)  # "admin", "viewer"
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class Device(Base):
    """Systems Under Test (SUT) / Client installations."""
    __tablename__ = "ota_devices"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(64), unique=True, nullable=False, index=True)  # e.g. "SUT-8F29A7C1"
    device_token = Column(String(128), nullable=False)  # Secret token for authentication
    device_name = Column(String(100), nullable=True)
    hostname = Column(String(100), nullable=False, default="unknown")
    os = Column(String(50), nullable=False, default="unknown")  # e.g. Windows
    os_version = Column(String(100), nullable=False, default="unknown")
    cpu = Column(String(100), nullable=False, default="unknown")
    ram = Column(String(50), nullable=False, default="unknown")  # e.g. "16 GB"
    disk_space = Column(String(50), nullable=False, default="unknown")
    ip_address = Column(String(45), nullable=True, default="127.0.0.1")
    mac_address = Column(String(50), nullable=True)
    python_version = Column(String(50), nullable=True)
    application_version = Column(String(50), nullable=False, default="0.1.0")
    agent_version = Column(String(50), nullable=False, default="1.0.0")
    status = Column(String(20), nullable=False, default="offline")  # online, offline, blocked
    is_blocked = Column(Boolean, default=False, nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_heartbeat = Column(DateTime, default=datetime.utcnow, nullable=False)
    installation_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    license = relationship("License", back_populates="device", uselist=False, cascade="all, delete-orphan")
    ota_jobs = relationship("OTAJob", back_populates="device", cascade="all, delete-orphan")
    usage_events = relationship("UsageEvent", back_populates="device", cascade="all, delete-orphan")


class License(Base):
    """License and Free Usage Limit record per device."""
    __tablename__ = "ota_licenses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(64), ForeignKey("ota_devices.device_id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    license_type = Column(String(50), default="FREE", nullable=False)  # FREE, PAID, TRIAL, ENTERPRISE, BLOCKED
    usage_limit = Column(Integer, default=100, nullable=False)
    usage_consumed = Column(Integer, default=0, nullable=False)
    status = Column(String(50), default="active", nullable=False)  # active, blocked, expired
    expiry_date = Column(DateTime, nullable=True)
    grace_period_hours = Column(Integer, default=24, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    device = relationship("Device", back_populates="license")


class UsageEvent(Base):
    """Usage activity events emitted by client installations."""
    __tablename__ = "ota_usage_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(String(64), ForeignKey("ota_devices.device_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type = Column(String(50), nullable=False)  # application_launch, speech_transcription, question_answered, chat_sent, tool_execution
    application_version = Column(String(50), nullable=False, default="0.1.0")
    metadata_json = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    device = relationship("Device", back_populates="usage_events")


class AppVersion(Base):
    """OTA version repository catalog."""
    __tablename__ = "ota_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(50), unique=True, nullable=False, index=True)  # e.g. "v0.1.0"
    build_number = Column(Integer, nullable=False, default=1)
    package_url = Column(String(500), nullable=False)
    package_hash = Column(String(128), nullable=False)  # SHA-256
    package_size = Column(Integer, nullable=False, default=0)  # bytes
    package_signature = Column(String(256), nullable=True)  # HMAC signature
    release_notes = Column(Text, nullable=True)
    minimum_supported_version = Column(String(50), nullable=True, default="v0.0.1")
    maximum_supported_version = Column(String(50), nullable=True)
    status = Column(String(50), default="Active", nullable=False)  # Active, Available, Archived, Deprecated
    release_date = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class OTAJob(Base):
    """OTA Upgrade / Downgrade job state machine."""
    __tablename__ = "ota_jobs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(64), ForeignKey("ota_devices.device_id", ondelete="CASCADE"), nullable=False, index=True)
    source_version = Column(String(50), nullable=False)
    target_version = Column(String(50), nullable=False)
    job_type = Column(String(20), default="upgrade", nullable=False)  # upgrade, downgrade, rollback
    status = Column(
        String(30),
        default="PENDING",
        nullable=False,
        index=True
    )  # PENDING, DOWNLOADING, VERIFYING, INSTALLING, RESTARTING, HEALTH_CHECK, SUCCESS, FAILED, ROLLBACK, ROLLED_BACK
    error_message = Column(Text, nullable=True)
    created_by = Column(String(100), default="Diwakar", nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    device = relationship("Device", back_populates="ota_jobs")


class AuditLog(Base):
    """Immutable audit history of all admin and system operations."""
    __tablename__ = "ota_audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=True, default="System")
    device_id = Column(String(64), nullable=True, index=True)
    action = Column(String(100), nullable=False, index=True)  # e.g. DEVICE_BLOCKED, OTA_STARTED, USAGE_RESET
    metadata_json = Column(Text, nullable=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class SystemSetting(Base):
    """Configurable system settings (Contact info, default limits, warning thresholds)."""
    __tablename__ = "ota_system_settings"

    key = Column(String(100), primary_key=True)
    value = Column(Text, nullable=False)
    description = Column(String(255), nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
