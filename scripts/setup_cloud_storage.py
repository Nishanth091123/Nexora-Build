"""Move file storage online (needed before going online) and copy the files kept on this PC.

    backend\\.venv\\Scripts\\python.exe scripts\\setup_cloud_storage.py

* R2 keys in .env  -> Cloudflare R2
* otherwise        -> a PRIVATE Hugging Face dataset repo  <your-hf-name>/nexora-build-files  (free, no card; uses HF_TOKEN)
It writes STORAGE_BACKEND (and HF_FILES_REPO) into .env, then copies drawings, photos and backups from
backend\\storage. Safe to run many times: files already online are skipped. Nothing is deleted from this PC.
Key values are never printed.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV = ROOT / ".env"
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")  # no progress bars in the CMD window
sys.path.insert(0, str(ROOT / "backend"))


def read_env() -> dict:
    out = {}
    for ln in ENV.read_text(encoding="utf-8").splitlines():
        if "=" in ln and not ln.strip().startswith("#"):
            k, v = ln.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def set_env(key: str, value: str) -> None:
    lines = ENV.read_text(encoding="utf-8").splitlines()
    for i, ln in enumerate(lines):
        if ln.split("=", 1)[0].strip() == key and not ln.strip().startswith("#"):
            lines[i] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.environ[key] = value


def main() -> int:
    if not ENV.exists():
        print("[FAIL] .env not found")
        return 1
    env = read_env()
    if all(env.get(k) for k in ("R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY")):
        target = "r2"
    elif env.get("HF_TOKEN"):
        target = "hf"
    else:
        print("[FAIL] Put your Hugging Face token in .env first:  HF_TOKEN=hf_...   (huggingface.co -> Settings -> Access Tokens -> Write)")
        return 1

    if target == "hf":
        try:
            from huggingface_hub import HfApi
        except ImportError:
            print("[FAIL] Run scripts\\update.bat first (installs huggingface_hub)")
            return 1
        api = HfApi(token=env["HF_TOKEN"])
        try:
            who = api.whoami()["name"]
        except Exception:
            print("[FAIL] HF_TOKEN not accepted – make a new token with 'Write' access")
            return 1
        repo = env.get("HF_FILES_REPO") or f"{who}/nexora-build-files"
        api.create_repo(repo, repo_type="dataset", private=True, exist_ok=True)
        set_env("HF_FILES_REPO", repo)
        print(f"[OK] Private file storage: huggingface.co/datasets/{repo}  (only you can see it)")
    set_env("STORAGE_BACKEND", target)
    print(f"[OK] .env: STORAGE_BACKEND={target}")

    # import the app only now, so it uses the new settings
    from app.db import SessionLocal
    from app.models import BackupRecord, StoredFile
    from app.storage import local_fallback, storage
    if storage.name != target:
        print(f"[FAIL] storage did not switch (got {storage.name})")
        return 1

    with SessionLocal() as db:
        files = db.query(StoredFile).filter(StoredFile.storage_backend == "local").all()
        backups = db.query(BackupRecord).all()
        todo = [(f.storage_key, f) for f in files] + [(b.storage_key, None) for b in backups]
        online = set()
        if target == "hf":
            online = set(storage.api.list_repo_files(storage.repo, repo_type="dataset"))
        moved = skipped = lost = 0
        batch = []

        def flush():
            nonlocal batch
            if batch:
                from huggingface_hub import CommitOperationAdd
                storage.api.create_commit(storage.repo, repo_type="dataset", commit_message=f"copy {len(batch)} files from PC",
                                          operations=[CommitOperationAdd(path_in_repo=k, path_or_fileobj=data) for k, data, _ in batch])
                for _, _, f in batch:
                    if f is not None:
                        f.storage_backend = target
                db.commit()
                print(f"  ... {moved} copied")
                batch = []

        for key, f in todo:
            already = key in online if target == "hf" else storage.exists(key)
            if already:
                if f is not None:
                    f.storage_backend = target
                skipped += 1
                continue
            if not local_fallback.exists(key):
                if f is not None:
                    lost += 1
                    print(f"  [missing on this PC] {f.original_name}")
                continue
            data = local_fallback.read(key)
            moved += 1
            if target == "hf":
                batch.append((key, data, f))
                if len(batch) >= 40 or sum(len(d) for _, d, _ in batch) > 150_000_000:
                    flush()
            else:
                storage.save(key, data, (f.content_type if f is not None else "application/gzip") or "")
                if f is not None:
                    f.storage_backend = target
                if moved % 20 == 0:
                    db.commit()
                    print(f"  ... {moved} copied")
        flush()
        db.commit()
    print(f"[OK] Copied online: {moved}, already there: {skipped}")
    if lost:
        print(f"[WARN] {lost} file(s) were not found on this PC – re-upload them in the app")
    print("     Restart scripts\\start.bat – Settings -> Backups -> Storage now shows the online storage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
