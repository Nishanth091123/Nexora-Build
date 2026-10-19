"""Copy files kept on this PC (backend\\storage) to Cloudflare R2, so the online app can open them.

    backend\\.venv\\Scripts\\python.exe scripts\\sync_local_to_r2.py

Safe to run many times: a file already in R2 is skipped. Nothing is deleted from this PC.
Needs the R2 keys in .env.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main() -> int:
    from app import config
    if not all([config.R2_ACCOUNT_ID, config.R2_ACCESS_KEY_ID, config.R2_SECRET_ACCESS_KEY]):
        print("[FAIL] R2 keys are missing in .env (R2_ACCOUNT_ID, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY)")
        return 1
    from app.db import SessionLocal
    from app.models import BackupRecord, StoredFile
    from app.storage import R2Storage, local_fallback

    r2 = R2Storage()
    moved = skipped = lost = 0
    with SessionLocal() as db:
        files = db.query(StoredFile).filter(StoredFile.storage_backend != "r2").all()
        print(f"{len(files)} file(s) are recorded as kept on this PC")
        for f in files:
            if r2.exists(f.storage_key):
                f.storage_backend = "r2"
                skipped += 1
                continue
            if not local_fallback.exists(f.storage_key):
                lost += 1
                print(f"  [missing on this PC] {f.original_name}")
                continue
            r2.save(f.storage_key, local_fallback.read(f.storage_key), f.content_type or "")
            f.storage_backend = "r2"
            moved += 1
            if moved % 20 == 0:
                db.commit()
                print(f"  ... {moved} copied")
        db.commit()
        b_moved = 0
        for b in db.query(BackupRecord).all():  # backups have no backend column: copy if missing in R2
            if local_fallback.exists(b.storage_key) and not r2.exists(b.storage_key):
                r2.save(b.storage_key, local_fallback.read(b.storage_key), "application/gzip")
                b_moved += 1
    print(f"[OK] Files copied to R2: {moved}, already there: {skipped}, backups copied: {b_moved}")
    if lost:
        print(f"[WARN] {lost} file(s) were not found on this PC (they cannot be opened anywhere – re-upload them)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
