import base64
import io

import openpyxl
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.excel_file import ExcelFile
from app.models.permission import FilePermission
from app.models.user import User
from app.schemas.file import ExcelFileWithAccess, FileContentResponse, FileSaveRequest
from app.services import audit_service

router = APIRouter()


def _get_permission(db: Session, user: User, file_id: int) -> FilePermission:
    if user.is_admin:
        file = db.query(ExcelFile).filter(ExcelFile.id == file_id).first()
        if not file:
            raise HTTPException(status_code=404, detail="File not found")
        perm = FilePermission(user_id=user.id, file_id=file_id, access_level="write")
        perm.file = file
        return perm
    perm = (
        db.query(FilePermission)
        .filter(FilePermission.user_id == user.id, FilePermission.file_id == file_id)
        .first()
    )
    if not perm:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return perm


@router.get("", response_model=list[ExcelFileWithAccess])
def list_files(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.is_admin:
        files = db.query(ExcelFile).all()
        return [
            ExcelFileWithAccess(**f.__dict__, has_content=f.has_content, access_level="write")
            for f in files
        ]

    perms = db.query(FilePermission).filter(FilePermission.user_id == current_user.id).all()
    result = []
    for p in perms:
        f = db.query(ExcelFile).filter(ExcelFile.id == p.file_id).first()
        if f:
            result.append(
                ExcelFileWithAccess(**f.__dict__, has_content=f.has_content, access_level=p.access_level)
            )
    return result


@router.get("/{file_id}/content", response_model=FileContentResponse)
def get_file_content(
    file_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    perm = _get_permission(db, current_user, file_id)
    file = db.query(ExcelFile).filter(ExcelFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    raw = file.file_content
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Файл недоступен: данные были потеряны при перезапуске сервера. Загрузите файл заново.",
        )
    audit_service.log_action(
        db, request, "FILE_VIEW",
        user_id=current_user.id, user_email=current_user.email,
        file_id=file.id, file_name=file.filename,
    )
    return FileContentResponse(
        content=base64.b64encode(raw).decode(),
        filename=file.filename,
        access_level=perm.access_level,
    )


@router.get("/{file_id}/download")
def download_file(
    file_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_permission(db, current_user, file_id)
    file = db.query(ExcelFile).filter(ExcelFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    raw = file.file_content
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Файл недоступен: данные были потеряны при перезапуске сервера. Загрузите файл заново.",
        )
    audit_service.log_action(
        db, request, "FILE_DOWNLOAD",
        user_id=current_user.id, user_email=current_user.email,
        file_id=file.id, file_name=file.filename,
    )
    return StreamingResponse(
        io.BytesIO(raw),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{file.filename}"'},
    )


@router.post("/{file_id}/save")
def save_file(
    file_id: int,
    body: FileSaveRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    perm = _get_permission(db, current_user, file_id)
    if perm.access_level != "write" and not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Write access required")
    file = db.query(ExcelFile).filter(ExcelFile.id == file_id).first()
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    try:
        raw = base64.b64decode(body.content)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 content")
    try:
        openpyxl.load_workbook(io.BytesIO(raw))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Excel file")
    from datetime import datetime, timezone
    size = len(raw)
    file.file_content = raw
    file.file_size = size
    file.updated_at = datetime.now(timezone.utc)
    db.commit()
    audit_service.log_action(
        db, request, "FILE_EDIT_SAVE",
        user_id=current_user.id, user_email=current_user.email,
        file_id=file.id, file_name=file.filename,
        metadata={"bytes": size},
    )
    return {"success": True, "updated_at": file.updated_at.isoformat()}
