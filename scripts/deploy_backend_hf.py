"""Put the Nexora Build backend online as a Hugging Face Space (Docker, free).

    backend\\.venv\\Scripts\\python.exe scripts\\deploy_backend_hf.py

Needs in .env:  HF_TOKEN (a "write" token from huggingface.co/settings/tokens), DATABASE_URL, JWT_SECRET,
and online file storage set by scripts\\setup_cloud_storage.py (STORAGE_BACKEND=hf private HF repo, or r2) –
the Space's own disk is wiped on every restart. Your keys are sent ONLY as Space *secrets* (encrypted, never shown, never in the code).
Run it again after every update – it uploads the new code and the Space rebuilds itself.
"""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
SPACE_NAME = os.getenv("NEXORA_SPACE", "nexora-build-api")

# Settings copied to the Space as secrets (values are never printed)
SECRET_KEYS = [
    "APP_NAME", "OWNER_USERNAME", "OWNER_EMAIL", "OWNER_FULL_NAME", "OWNER_INITIAL_PASSWORD", "JWT_SECRET",
    "DEFAULT_LANGUAGE", "DEFAULT_STATE", "DEFAULT_SPEC_LEVEL", "DATABASE_URL",
    "R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET",
    "GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "GEMINI_VISION_MODEL", "GROQ_VISION_MODEL",
    "OPENROUTER_VISION_MODEL", "GROQ_MODEL", "OPENROUTER_MODEL", "GEMINI_EMBED_MODEL", "GROQ_WHISPER_MODEL",
    "MAX_UPLOAD_MB", "AUTO_BACKUP_HOURS",
]

README = """---
title: Nexora Build API
emoji: 🏗️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---
Backend (API) of Nexora Build. The app itself is opened from its own web address (Vercel).
"""


def read_env() -> dict:
    p = ROOT / ".env"
    if not p.exists():
        sys.exit("[FAIL] .env not found in " + str(ROOT))
    out = {}
    for ln in p.read_text(encoding="utf-8").splitlines():
        if "=" in ln and not ln.strip().startswith("#"):
            k, v = ln.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def main() -> int:
    try:
        from huggingface_hub import HfApi
    except ImportError:
        sys.exit("[FAIL] huggingface_hub is missing. Run:  backend\\.venv\\Scripts\\python.exe -m pip install huggingface_hub")
    env = read_env()
    missing = [k for k in ("HF_TOKEN", "DATABASE_URL", "JWT_SECRET") if not env.get(k)]
    if missing:
        sys.exit(f"[FAIL] Fill these in .env first: {', '.join(missing)}")
    if env["JWT_SECRET"].startswith("change-me") or len(env["JWT_SECRET"]) < 24:
        sys.exit("[FAIL] JWT_SECRET is the default/too short. Run:  backend\\.venv\\Scripts\\python.exe scripts\\update_env.py")
    backend = env.get("STORAGE_BACKEND", "auto").lower()
    if backend not in ("hf", "r2"):
        sys.exit("[FAIL] Files are still stored only on this PC. Run first:  scripts\\setup_cloud_storage.py\n"
                 "       (go_online.bat does this automatically) – the free server's disk is wiped on restart.")

    api = HfApi(token=env["HF_TOKEN"])
    try:
        who = api.whoami()["name"]
    except Exception as e:
        sys.exit(f"[FAIL] HF_TOKEN not accepted ({type(e).__name__}). Make a new token with 'Write' access.")
    repo = f"{who}/{SPACE_NAME}"
    print(f"Hugging Face user: {who}   Space: {repo}")

    api.create_repo(repo, repo_type="space", space_sdk="docker", private=False, exist_ok=True)

    # secrets (encrypted on Hugging Face – not visible in the code or logs)
    n = 0
    for k in SECRET_KEYS:
        if env.get(k):
            api.add_space_secret(repo, k, env[k])
            n += 1
    api.add_space_secret(repo, "STORAGE_BACKEND", backend)
    if backend == "hf":  # the server needs the token to read/write the private files repo
        api.add_space_secret(repo, "HF_TOKEN", env["HF_TOKEN"])
        api.add_space_secret(repo, "HF_FILES_REPO", env.get("HF_FILES_REPO") or f"{who}/nexora-build-files")
        n += 2
    origins = env.get("FRONTEND_ORIGINS", "")
    extra = env.get("ONLINE_APP_URL", "").rstrip("/")
    if extra and extra not in origins:
        origins = (origins + "," + extra).strip(",")
    if origins:
        api.add_space_secret(repo, "FRONTEND_ORIGINS", origins)
    print(f"[OK] {n + 2} settings saved as Space secrets (values not shown)")

    # code: Dockerfile + requirements + app/ (no .env, no local storage, no caches)
    tmp = ROOT / "backend" / "README.md"
    tmp.write_text(README, encoding="utf-8")
    try:
        api.upload_folder(
            repo_id=repo, repo_type="space", folder_path=str(BACKEND),
            allow_patterns=["Dockerfile", "requirements.txt", "README.md", "app/**"],
            ignore_patterns=["**/__pycache__/**", "**/*.pyc", "**/.env*", "storage/**", ".venv/**"],
            commit_message="Nexora Build backend update",
        )
    finally:
        tmp.unlink(missing_ok=True)
    print("[OK] Code uploaded – the Space is building (3-6 minutes the first time)")

    host = f"https://{who.lower().replace('_', '-').replace('.', '-')}-{SPACE_NAME}.hf.space"
    try:
        info = api.space_info(repo)
        host = "https://" + (getattr(info, "host", None) or host.split("//", 1)[1]).replace("https://", "")
    except Exception:
        pass
    want = ""
    cfg = (BACKEND / "app" / "config.py").read_text(encoding="utf-8")
    for ln in cfg.splitlines():
        if ln.startswith("APP_VERSION"):
            want = ln.split("=", 1)[1].strip().strip('"')
    print(f"Waiting for {host}/api/health to answer version {want} ...")
    import httpx
    for i in range(60):  # up to ~15 minutes
        try:
            r = httpx.get(host + "/api/health", timeout=20)
            if r.status_code == 200 and r.json().get("version") == want:
                print()
                print(f"[OK] BACKEND ONLINE: {host}")
                print(f"     Vercel setting:  VITE_API_URL = {host}")
                return 0
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(15)
    print()
    print(f"[WAIT] Not answering yet. Open https://huggingface.co/spaces/{repo} -> 'Logs' to see the build.")
    print(f"       When it shows 'Ready', the backend address is: {host}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
