import io
import uuid
from typing import Optional

import openpyxl
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_db, require_admin
from app.models.excel_file import ExcelFile
from app.models.permission import FilePermission
from app.models.user import User
from app.schemas.file import ExcelFileOut
from app.schemas.permission import PermissionCreate, PermissionOut, PermissionWithUser
from app.schemas.user import UserCreate, UserOut, UserUpdate
from app.services import audit_service
from app.services.auth_service import hash_password

router = APIRouter()


# ── Users ──────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=list[UserOut])
def list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(User).all()


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(
    body: UserCreate,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if db.query(User).filter(User.email == body.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
        is_admin=body.is_admin,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    audit_service.log_action(
        db, request, "ADMIN_USER_CREATE",
        user_id=admin.id, user_email=admin.email,
        metadata={"created_email": body.email},
    )
    return user


@router.put("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdate,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.password is not None:
        user.hashed_password = hash_password(body.password)
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.is_admin is not None:
        user.is_admin = body.is_admin
    db.commit()
    db.refresh(user)
    audit_service.log_action(
        db, request, "ADMIN_USER_UPDATE",
        user_id=admin.id, user_email=admin.email,
        metadata={"target_user_id": user_id},
    )
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot deactivate yourself")
    user.is_active = False
    db.commit()
    audit_service.log_action(
        db, request, "ADMIN_USER_DEACTIVATE",
        user_id=admin.id, user_email=admin.email,
        metadata={"target_user_id": user_id},
    )


# ── Files ──────────────────────────────────────────────────────────────────────

@router.get("/files", response_model=list[ExcelFileOut])
def list_all_files(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.query(ExcelFile).all()


@router.post("/files/upload", response_model=ExcelFileOut, status_code=status.HTTP_201_CREATED)
async def upload_file(
    request: Request,
    file: UploadFile = File(...),
    description: Optional[str] = Form(None),
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if not file.filename or not file.filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx files are allowed")
    raw = await file.read()
    if len(raw) > settings.max_file_size_mb * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"File exceeds {settings.max_file_size_mb} MB limit")
    try:
        openpyxl.load_workbook(io.BytesIO(raw))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid Excel file")
    stored_name = f"{uuid.uuid4()}.xlsx"
    size = len(raw)
    record = ExcelFile(
        filename=file.filename,
        stored_name=stored_name,
        description=description,
        file_size=size,
        file_content=raw,
        uploaded_by=admin.id,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    audit_service.log_action(
        db, request, "FILE_UPLOAD",
        user_id=admin.id, user_email=admin.email,
        file_id=record.id, file_name=record.filename,
        metadata={"bytes": size},
    )
    return record


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(
    file_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    record = db.query(ExcelFile).filter(ExcelFile.id == file_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="File not found")
    db.query(FilePermission).filter(FilePermission.file_id == file_id).delete()
    db.delete(record)
    db.commit()
    audit_service.log_action(
        db, request, "FILE_DELETE",
        user_id=admin.id, user_email=admin.email,
        metadata={"deleted_file": record.filename},
    )


# ── Permissions ────────────────────────────────────────────────────────────────

@router.get("/files/{file_id}/permissions", response_model=list[PermissionWithUser])
def get_permissions(
    file_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    perms = db.query(FilePermission).filter(FilePermission.file_id == file_id).all()
    result = []
    for p in perms:
        u = db.query(User).filter(User.id == p.user_id).first()
        result.append(PermissionWithUser(
            **p.__dict__,
            user_email=u.email if u else "",
            user_full_name=u.full_name if u else "",
        ))
    return result


@router.post("/files/{file_id}/permissions", response_model=PermissionOut, status_code=status.HTTP_201_CREATED)
def grant_permission(
    file_id: int,
    body: PermissionCreate,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    if body.access_level not in ("read", "write"):
        raise HTTPException(status_code=400, detail="access_level must be 'read' or 'write'")
    if not db.query(ExcelFile).filter(ExcelFile.id == file_id).first():
        raise HTTPException(status_code=404, detail="File not found")
    if not db.query(User).filter(User.id == body.user_id).first():
        raise HTTPException(status_code=404, detail="User not found")
    existing = (
        db.query(FilePermission)
        .filter(FilePermission.user_id == body.user_id, FilePermission.file_id == file_id)
        .first()
    )
    if existing:
        existing.access_level = body.access_level
        existing.granted_by = admin.id
        db.commit()
        db.refresh(existing)
        return existing
    perm = FilePermission(
        user_id=body.user_id,
        file_id=file_id,
        access_level=body.access_level,
        granted_by=admin.id,
    )
    db.add(perm)
    db.commit()
    db.refresh(perm)
    audit_service.log_action(
        db, request, "ADMIN_PERMISSION_GRANT",
        user_id=admin.id, user_email=admin.email,
        file_id=file_id,
        metadata={"target_user_id": body.user_id, "level": body.access_level},
    )
    return perm


@router.delete("/files/{file_id}/permissions/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_permission(
    file_id: int,
    user_id: int,
    request: Request,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    perm = (
        db.query(FilePermission)
        .filter(FilePermission.file_id == file_id, FilePermission.user_id == user_id)
        .first()
    )
    if not perm:
        raise HTTPException(status_code=404, detail="Permission not found")
    db.delete(perm)
    db.commit()
    audit_service.log_action(
        db, request, "ADMIN_PERMISSION_REVOKE",
        user_id=admin.id, user_email=admin.email,
        file_id=file_id,
        metadata={"target_user_id": user_id},
    )
