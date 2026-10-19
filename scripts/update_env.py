"""Adds the new Phase 1 settings to your .env WITHOUT changing anything already there.
Run:  python scripts\\update_env.py
"""
import getpass
import secrets
from pathlib import Path

ENV = Path(__file__).resolve().parent.parent / ".env"
if not ENV.exists():
    raise SystemExit("[ERROR] .env not found. Run: copy .env.example .env")

text = ENV.read_text(encoding="utf-8")
lines = text.splitlines()
current = {}
for ln in lines:
    if "=" in ln and not ln.strip().startswith("#"):
        k, v = ln.split("=", 1)
        current[k.strip()] = v.strip()

changes = []


def setval(key, value):
    global lines
    for i, ln in enumerate(lines):
        if ln.split("=", 1)[0].strip() == key and not ln.strip().startswith("#"):
            lines[i] = f"{key}={value}"
            break
    else:
        lines.append(f"{key}={value}")
    current[key] = value
    changes.append(key)


if not current.get("JWT_SECRET") or current["JWT_SECRET"].startswith("change-me"):
    setval("JWT_SECRET", secrets.token_urlsafe(48))
if not current.get("OWNER_USERNAME"):
    setval("OWNER_USERNAME", "nishanth_s")
if not current.get("OWNER_FULL_NAME"):
    setval("OWNER_FULL_NAME", "Nishanth S")
if not current.get("OWNER_EMAIL"):
    setval("OWNER_EMAIL", input("Owner login email: ").strip().lower())
if not current.get("OWNER_INITIAL_PASSWORD"):
    while True:
        p1 = getpass.getpass("Choose owner password (min 8, letters + numbers, hidden): ")
        p2 = getpass.getpass("Type it again: ")
        if p1 != p2:
            print("  Not matching, try again.")
        elif len(p1) < 8 or not any(c.isdigit() for c in p1) or not any(c.isalpha() for c in p1):
            print("  Too weak, try again.")
        else:
            setval("OWNER_INITIAL_PASSWORD", p1)
            break
for key, val in [("STORAGE_BACKEND", "auto"), ("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"),
                 ("MAX_UPLOAD_MB", "25"), ("AUTO_BACKUP_HOURS", "24")]:
    if key not in current:
        setval(key, val)

if changes:
    ENV.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("[OK] .env updated:", ", ".join(changes))
else:
    print("[OK] .env already complete – nothing changed")
print("Your existing keys (Neon, Gemini, Groq, OpenRouter) were not touched.")
