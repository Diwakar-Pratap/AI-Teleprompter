"""
Audit logging service for tracking system and administrative activities.
"""

from datetime import datetime
import json
from typing import Optional, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from app.ota.models import AuditLog
from app.logging.logger import get_logger

logger = get_logger(__name__)


async def log_audit(
    session: AsyncSession,
    action: str,
    device_id: Optional[str] = None,
    user_id: Optional[str] = "System",
    metadata: Optional[Any] = None,
) -> None:
    """Record an immutable audit log entry."""
    try:
        metadata_str = json.dumps(metadata) if metadata is not None else None
        entry = AuditLog(
            user_id=user_id,
            device_id=device_id,
            action=action,
            metadata_json=metadata_str,
            timestamp=datetime.utcnow(),
        )
        session.add(entry)
        await session.commit()
        logger.info("Audit log recorded", action=action, device_id=device_id, user_id=user_id)
    except Exception as e:
        logger.error("Failed to write audit log", error=str(e), action=action)


async def get_audit_logs(session: AsyncSession, limit: int = 100, device_id: Optional[str] = None):
    """Retrieve audit logs."""
    query = select(AuditLog)
    if device_id:
        query = query.where(AuditLog.device_id == device_id)
    query = query.order_by(desc(AuditLog.timestamp)).limit(limit)
    result = await session.execute(query)
    return result.scalars().all()
