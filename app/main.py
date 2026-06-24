import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import SessionLocal, init_db
from app.routers import admin, auth, files, logs
from app.services.auth_service import hash_password

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


def _auto_seed_admin() -> None:
    if not settings.admin_email or not settings.admin_password:
        return
    from app.models.user import User
    db = SessionLocal()
    try:
        if not db.query(User).filter(User.email == settings.admin_email).first():
            admin_user = User(
                email=settings.admin_email,
                full_name="Admin",
                hashed_password=hash_password(settings.admin_password),
                is_admin=True,
                is_active=True,
            )
            db.add(admin_user)
            db.commit()
            logging.getLogger(__name__).info("Admin user created: %s", settings.admin_email)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    Path(settings.file_storage_path).mkdir(parents=True, exist_ok=True)
    _auto_seed_admin()
    yield


app = FastAPI(title="Excel File Manager", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(files.router, prefix="/files", tags=["files"])
app.include_router(admin.router, prefix="/admin", tags=["admin"])
app.include_router(logs.router, prefix="/admin", tags=["logs"])

app.mount("/static", StaticFiles(directory="frontend/static"), name="static")

_PAGES = {"": "index", "dashboard": "dashboard", "viewer": "viewer", "editor": "editor", "admin": "admin"}


@app.get("/")
def root():
    return FileResponse("frontend/index.html")


@app.get("/{page}")
def serve_page(page: str):
    mapped = _PAGES.get(page)
    if mapped:
        return FileResponse(f"frontend/{mapped}.html")
    return FileResponse("frontend/index.html")
