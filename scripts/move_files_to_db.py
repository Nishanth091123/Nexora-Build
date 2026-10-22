"""Move every stored file (drawings, photos, documents, backups) into the app's own database – once.

    backend\\.venv\\Scripts\\python.exe scripts\\move_files_to_db.py

After this, nothing uses Hugging Face (or a local folder) any more: the PC app and the online app read
the same files from the Neon database. Safe to run again – files already moved are skipped.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
sys.path.insert(0, str(ROOT / "backend"))
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")


def set_env(key: str, value: str, comment_out: tuple = ()) -> None:
    lines = ENV.read_text(encoding="utf-8").splitlines()
    out, done = [], False
    for ln in lines:
        k = ln.split("=", 1)[0].strip()
        if k == key and not ln.strip().startswith("#"):
            out.append(f"{key}={value}")
            done = True
        elif k in comment_out and not ln.strip().startswith("#"):
            out.append("# not used any more (files are in the database): " + ln)
        else:
            out.append(ln)
    if not done:
        out.append(f"{key}={value}")
    ENV.write_text("\n".join(out) + "\n", encoding="utf-8")


_hf = {}


def read_hf(key: str) -> bytes:
    """Old files that went to the private Hugging Face repo (only used here, once)."""
    import subprocess
    if "api" not in _hf:
        token = os.environ.get("HF_TOKEN", "")
        if not token:
            raise FileNotFoundError(key)
        try:
            import huggingface_hub  # noqa: F401
        except ImportError:
            print("  (installing the Hugging Face reader once, only to copy old files...)")
            subprocess.run([sys.executable, "-m", "pip", "install", "-q", "huggingface_hub"], check=True)
        from huggingface_hub import HfApi
        api = HfApi(token=token)
        _hf["api"], _hf["token"] = api, token
        _hf["repo"] = os.environ.get("HF_FILES_REPO") or f"{api.whoami()['name']}/nexora-build-files"
    from huggingface_hub import hf_hub_download
    return Path(hf_hub_download(_hf["repo"], key, repo_type="dataset", token=_hf["token"])).read_bytes()


def read_any(backend: str, key: str) -> bytes:
    from app.storage import backend_for
    try:
        return backend_for(backend).read(key)  # PC copy (storage folder / _hf_cache) or R2
    except Exception:
        if backend == "hf":
            return read_hf(key)
        raise


def main() -> int:
    os.environ["STORAGE_BACKEND"] = "db"
    from app.db import SessionLocal, init_db
    from app.models import BackupRecord, StoredFile
    from dotenv import load_dotenv
    load_dotenv(ENV)
    from app.storage import storage
    init_db()  # creates the stored_blobs table
    moved = skipped = failed = 0
    with SessionLocal() as db:
        files = db.query(StoredFile).filter(StoredFile.storage_backend != "db").all()
        print(f"{len(files)} file(s) to move into the database")
        for f in files:
            try:
                if not storage.exists(f.storage_key):
                    storage.save(f.storage_key, read_any(f.storage_backend, f.storage_key))
                f.storage_backend = "db"
                moved += 1
                if moved % 20 == 0:
                    db.commit()
                    print(f"  ... {moved} moved")
            except Exception as e:
                failed += 1
                print(f"  [not found] {f.original_name} ({type(e).__name__})")
        db.commit()
        for b in db.query(BackupRecord).order_by(BackupRecord.created_at.desc()).limit(20).all():
            if storage.exists(b.storage_key):
                skipped += 1
                continue
            for name in ("hf", "r2", "local"):
                try:
                    storage.save(b.storage_key, read_any(name, b.storage_key))
                    break
                except Exception:
                    continue
    print(f"[OK] Files moved: {moved}" + (f", not found anywhere: {failed} (re-upload those in the app)" if failed else ""))
    set_env("STORAGE_BACKEND", "db", comment_out=("HF_TOKEN", "HF_FILES_REPO") if not failed else ())
    print("[OK] .env: STORAGE_BACKEND=db" + ("  (Hugging Face settings switched off)" if not failed else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
