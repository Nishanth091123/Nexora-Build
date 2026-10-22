"""File storage: inside the Neon database (default from 7.11), Cloudflare R2, or a local folder.

All backends use the same 'key' strings, so moving from local to online storage only
needs the files copied (scripts/sync_local_to_cloud.py).
"""
import logging
from pathlib import Path
from typing import Iterator

from . import config

log = logging.getLogger("nexora.storage")


class LocalStorage:
    name = "local"

    def __init__(self, root: Path):
        self.root = root
        try:
            self.root.mkdir(parents=True, exist_ok=True)
        except OSError:  # read-only app folder on a server – use the temp folder instead
            import tempfile
            self.root = Path(tempfile.gettempdir()) / "nexora_storage"
            self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        p = (self.root / key).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError("Invalid storage key")
        return p

    def save(self, key: str, data: bytes, content_type: str = "") -> None:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)

    def read(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def stream(self, key: str, chunk: int = 1024 * 256) -> Iterator[bytes]:
        with self._path(key).open("rb") as f:
            while True:
                b = f.read(chunk)
                if not b:
                    break
                yield b

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        """Only used by the owner's 'Delete permanently' in the Recycle Bin."""
        p = self._path(key)
        if p.exists():
            p.unlink()


class R2Storage:
    name = "r2"

    def __init__(self):
        import boto3
        from botocore.config import Config
        self.bucket = config.R2_BUCKET
        self.s3 = boto3.client(
            "s3",
            endpoint_url=f"https://{config.R2_ACCOUNT_ID}.r2.cloudflarestorage.com",
            aws_access_key_id=config.R2_ACCESS_KEY_ID,
            aws_secret_access_key=config.R2_SECRET_ACCESS_KEY,
            region_name="auto",
            config=Config(signature_version="s3v4", retries={"max_attempts": 3}),
        )

    def save(self, key: str, data: bytes, content_type: str = "") -> None:
        self.s3.put_object(Bucket=self.bucket, Key=key, Body=data,
                           ContentType=content_type or "application/octet-stream")

    def read(self, key: str) -> bytes:
        return self.s3.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def stream(self, key: str, chunk: int = 1024 * 256) -> Iterator[bytes]:
        body = self.s3.get_object(Bucket=self.bucket, Key=key)["Body"]
        yield from body.iter_chunks(chunk)

    def exists(self, key: str) -> bool:
        try:
            self.s3.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False

    def delete(self, key: str) -> None:
        """Only used by the owner's 'Delete permanently' in the Recycle Bin."""
        self.s3.delete_object(Bucket=self.bucket, Key=key)


class DBStorage:
    """File contents in the app's own database (table stored_blobs). Same on the PC and online, nothing
    extra to set up. Neon's free plan holds about 0.5 GB – photos are compressed before upload."""
    name = "db"

    def _s(self):
        from .db import SessionLocal
        return SessionLocal()

    def save(self, key: str, data: bytes, content_type: str = "") -> None:
        from .models import StoredBlob
        with self._s() as db:
            b = db.get(StoredBlob, key)
            if b:
                b.data, b.size_bytes = data, len(data)
            else:
                db.add(StoredBlob(key=key, data=data, size_bytes=len(data)))
            db.commit()

    def read(self, key: str) -> bytes:
        from .models import StoredBlob
        with self._s() as db:
            b = db.get(StoredBlob, key)
            if not b:
                raise FileNotFoundError(key)
            return bytes(b.data)

    def stream(self, key: str, chunk: int = 1024 * 256) -> Iterator[bytes]:
        data = self.read(key)
        for i in range(0, len(data), chunk):
            yield data[i:i + chunk]

    def exists(self, key: str) -> bool:
        from .models import StoredBlob
        with self._s() as db:
            return db.query(StoredBlob.key).filter(StoredBlob.key == key).first() is not None

    def delete(self, key: str) -> None:
        """Only used by the owner's 'Delete permanently' in the Recycle Bin."""
        from sqlalchemy import text
        from .models import StoredBlob
        with self._s() as db:
            if db.get_bind().dialect.name == "postgresql":
                db.execute(text("SET LOCAL nexora.allow_delete = 'on'"))
            db.query(StoredBlob).filter(StoredBlob.key == key).delete(synchronize_session=False)
            db.commit()


def _make():
    want = config.STORAGE_BACKEND.lower()
    has_r2 = all([config.R2_ACCOUNT_ID, config.R2_ACCESS_KEY_ID, config.R2_SECRET_ACCESS_KEY])
    # "db" is the default. Old settings "hf" / "auto" (without R2 keys) also mean the database now.
    if want in ("db", "hf") or (want == "auto" and not has_r2):
        log.info("File storage: inside the database")
        return DBStorage()
    if want == "r2" or (want == "auto" and has_r2):
        if not has_r2:
            raise RuntimeError("STORAGE_BACKEND=r2 but R2 keys are missing in .env")
        log.info("File storage: Cloudflare R2 bucket %s", config.R2_BUCKET)
        return R2Storage()
    log.info("File storage: local folder %s", config.LOCAL_STORAGE_DIR)
    return LocalStorage(config.LOCAL_STORAGE_DIR)


storage = _make()
local_fallback = LocalStorage(config.LOCAL_STORAGE_DIR)


def backend_for(name: str):
    """Files keep the backend they were saved with, so old local files stay readable."""
    if name == storage.name:
        return storage
    if name == "local":
        return local_fallback
    if name == "db":
        return DBStorage()
    return _other(name)


_others: dict = {}


def _other(name: str):
    """A file saved on another online backend (e.g. R2 earlier) – open it there if its keys exist."""
    if name not in _others:
        try:
            # "hf": very old rows – only the copy left on this PC can be read (scripts/move_files_to_db.py moves them)
            _others[name] = R2Storage() if name == "r2" else LocalStorage(config.LOCAL_STORAGE_DIR / "_hf_cache") if name == "hf" else local_fallback
        except Exception as e:
            log.warning("storage %s not available: %s", name, e)
            _others[name] = local_fallback
    return _others[name]
