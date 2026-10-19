"""Makes render_env.txt – the settings to paste into Render (Environment -> Add from .env).

    backend\\.venv\\Scripts\\python.exe scripts\\render_env.py

Only the settings the online backend needs are written (from your .env). The file contains keys:
it is ignored by git, never shown on screen – paste it into Render, then delete it.
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEED = ["APP_NAME", "OWNER_USERNAME", "OWNER_EMAIL", "OWNER_FULL_NAME", "OWNER_INITIAL_PASSWORD", "JWT_SECRET",
        "DEFAULT_LANGUAGE", "DEFAULT_STATE", "DEFAULT_SPEC_LEVEL", "DATABASE_URL",
        "STORAGE_BACKEND", "HF_TOKEN", "HF_FILES_REPO", "R2_ACCOUNT_ID", "R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET",
        "GEMINI_API_KEY", "GROQ_API_KEY", "OPENROUTER_API_KEY", "GEMINI_VISION_MODEL", "GROQ_VISION_MODEL", "OPENROUTER_VISION_MODEL",
        "GROQ_MODEL", "OPENROUTER_MODEL", "GEMINI_EMBED_MODEL", "GROQ_WHISPER_MODEL", "MAX_UPLOAD_MB", "AUTO_BACKUP_HOURS",
        "FRONTEND_ORIGINS"]


def main() -> int:
    envf = ROOT / ".env"
    if not envf.exists():
        print("[FAIL] .env not found")
        return 1
    env = {}
    for ln in envf.read_text(encoding="utf-8").splitlines():
        if "=" in ln and not ln.strip().startswith("#"):
            k, v = ln.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("DATABASE_URL", "JWT_SECRET"):
        if not env.get(k):
            print(f"[FAIL] {k} is empty in .env")
            return 1
    if env.get("STORAGE_BACKEND", "auto").lower() not in ("hf", "r2"):
        print("[FAIL] Files are still only on this PC. Run scripts\\go_online.bat (it sets up online storage first).")
        return 1
    if env.get("JWT_SECRET", "").startswith("change-me"):
        print("[FAIL] JWT_SECRET is the default. Run: backend\\.venv\\Scripts\\python.exe scripts\\update_env.py")
        return 1
    origins = env.get("FRONTEND_ORIGINS", "")
    if env.get("ONLINE_APP_URL"):
        origins = (origins + "," + env["ONLINE_APP_URL"].rstrip("/")).strip(",")
    env["FRONTEND_ORIGINS"] = origins
    lines = [f"{k}={env[k]}" for k in NEED if env.get(k)]
    out = ROOT / "render_env.txt"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[OK] render_env.txt made with {len(lines)} settings (values not shown). Opening it in Notepad...")
    print("     Copy ALL of it -> Render -> your service -> Environment -> 'Add from .env' -> paste -> Save.")
    print("     Then close Notepad and DELETE render_env.txt (it contains your keys).")
    if os.name == "nt":
        subprocess.Popen(["notepad.exe", str(out)])
    return 0


if __name__ == "__main__":
    sys.exit(main())
