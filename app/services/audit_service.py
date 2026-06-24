import json
import logging
from typing import Optional

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)


def _get_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def log_action(
    db: Session,
    request: Request,
    action: str,
    user_id: Optional[int] = None,
    user_email: str = "",
    file_id: Optional[int] = None,
    file_name: str = "",
    metadata: Optional[dict] = None,
) -> None:
    entry = AuditLog(
        user_id=user_id,
        user_email=user_email,
        action=action,
        file_id=file_id,
        file_name=file_name,
        ip_address=_get_ip(request),
        user_agent=request.headers.get("User-Agent", "")[:500],
        metadata_=json.dumps(metadata) if metadata else None,
    )
    db.add(entry)
    db.commit()
    logger.info("AUDIT user=%s action=%s file=%s ip=%s", user_email, action, file_name, entry.ip_address)
