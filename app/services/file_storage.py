from pathlib import Path

from app.config import settings


def _base() -> Path:
    return Path(settings.file_storage_path)


def save_file(stored_name: str, content: bytes) -> int:
    tmp = _base() / f"{stored_name}.tmp"
    tmp.write_bytes(content)
    tmp.rename(_base() / stored_name)
    return len(content)


def read_file(stored_name: str) -> bytes:
    path = _base() / stored_name
    if not path.exists():
        raise FileNotFoundError(stored_name)
    return path.read_bytes()


def delete_file(stored_name: str) -> None:
    path = _base() / stored_name
    if path.exists():
        path.unlink()


def file_exists(stored_name: str) -> bool:
    return (_base() / stored_name).exists()
