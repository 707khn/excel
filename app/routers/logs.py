from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_admin
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit_log import AuditLogOut, AuditLogPage

router = APIRouter()


@router.get("/logs", response_model=AuditLogPage)
def get_logs(
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user_id: Optional[int] = Query(None),
    action: Optional[str] = Query(None),
    file_id: Optional[int] = Query(None),
    _admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    q = db.query(AuditLog)
    if user_id is not None:
        q = q.filter(AuditLog.user_id == user_id)
    if action:
        q = q.filter(AuditLog.action == action)
    if file_id is not None:
        q = q.filter(AuditLog.file_id == file_id)
    total = q.count()
    items = q.order_by(AuditLog.created_at.desc()).offset((page - 1) * limit).limit(limit).all()
    return AuditLogPage(items=items, total=total, page=page, limit=limit)
