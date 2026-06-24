from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.user import TokenResponse, UserOut
from app.services import audit_service, auth_service

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
):
    user: User | None = db.query(User).filter(User.email == form_data.username).first()
    if not user or not auth_service.verify_password(form_data.password, user.hashed_password):
        audit_service.log_action(
            db, request, "LOGIN_FAILED", user_email=form_data.username,
            metadata={"reason": "bad credentials"},
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is disabled")
    audit_service.log_action(db, request, "LOGIN", user_id=user.id, user_email=user.email)
    return TokenResponse(
        access_token=auth_service.create_access_token(user.id, user.email, user.is_admin),
        refresh_token=auth_service.create_refresh_token(user.id, user.email, user.is_admin),
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, body: dict, db: Session = Depends(get_db)):
    token = body.get("refresh_token", "")
    payload = auth_service.decode_token(token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user: User | None = db.query(User).filter(User.id == int(payload["sub"])).first()
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found or inactive")
    return TokenResponse(
        access_token=auth_service.create_access_token(user.id, user.email, user.is_admin),
        refresh_token=auth_service.create_refresh_token(user.id, user.email, user.is_admin),
    )


@router.get("/me", response_model=UserOut)
def me(current_user: User = Depends(get_current_user)):
    return current_user
