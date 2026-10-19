"""File storage: Cloudflare R2, a private Hugging Face dataset repo, or a local folder.

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


class HFStorage:
    """Files in a PRIVATE Hugging Face dataset repo (free, no card). Each save is one small commit."""
    name = "hf"

    def __init__(self):
        from huggingface_hub import HfApi
        if not config.HF_TOKEN:
            raise RuntimeError("STORAGE_BACKEND=hf needs HF_TOKEN in .env")
        self.api = HfApi(token=config.HF_TOKEN)
        self._repo = config.HF_FILES_REPO
        self._ready = False

    @property
    def repo(self) -> str:
        if not self._repo:  # looked up on first use, so the app also starts without internet
            self._repo = f"{self.api.whoami()['name']}/nexora-build-files"
        return self._repo

    def _ensure(self) -> None:
        if not self._ready:
            self.api.create_repo(self.repo, repo_type="dataset", private=True, exist_ok=True)
            self._ready = True

    def _retry(self, fn):
        import time
        for i in range(4):  # two saves at the same moment can clash – try again
            try:
                return fn()
            except Exception as e:
                if i == 3 or "404" in str(e) or "EntryNotFound" in type(e).__name__:
                    raise
                time.sleep(1.5 * (i + 1))

    def save(self, key: str, data: bytes, content_type: str = "") -> None:
        import io
        self._ensure()
        self._retry(lambda: self.api.upload_file(path_or_fileobj=io.BytesIO(data), path_in_repo=key, repo_id=self.repo,
                                                 repo_type="dataset", commit_message=f"add {key.split('/')[-1]}"))

    def read(self, key: str) -> bytes:
        from huggingface_hub import hf_hub_download
        path = self._retry(lambda: hf_hub_download(self.repo, key, repo_type="dataset", token=config.HF_TOKEN))
        return Path(path).read_bytes()

    def stream(self, key: str, chunk: int = 1024 * 256) -> Iterator[bytes]:
        data = self.read(key)
        for i in range(0, len(data), chunk):
            yield data[i:i + chunk]

    def exists(self, key: str) -> bool:
        try:
            return bool(self.api.file_exists(self.repo, key, repo_type="dataset"))
        except Exception:
            return False

    def delete(self, key: str) -> None:
        """Only used by the owner's 'Delete permanently' in the Recycle Bin."""
        self._retry(lambda: self.api.delete_file(key, self.repo, repo_type="dataset", commit_message="delete file"))


def _make():
    want = config.STORAGE_BACKEND.lower()
    if want == "hf":
        st = HFStorage()
        log.info("File storage: private Hugging Face repo %s", config.HF_FILES_REPO or "<you>/nexora-build-files")
        return st
    has_r2 = all([config.R2_ACCOUNT_ID, config.R2_ACCESS_KEY_ID, config.R2_SECRET_ACCESS_KEY])
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
    return _other(name)


_others: dict = {}


def _other(name: str):
    """A file saved on another online backend (e.g. R2 earlier, HF now) – open it there if its keys exist."""
    if name not in _others:
        try:
            _others[name] = R2Storage() if name == "r2" else HFStorage() if name == "hf" else local_fallback
        except Exception as e:
            log.warning("storage %s not available: %s", name, e)
            _others[name] = local_fallback
    return _others[name]
