"""
Nexora Build - Phase 0 verification
Checks .env keys WITHOUT printing them:
  1. Neon Postgres connection + enables pgvector extension
  2. Gemini key   3. Groq key   4. OpenRouter key
Run from C:\\PROJECTS\\Nexora_Build with the backend venv active:
    python scripts\\verify_setup.py
"""
import os
import sys
from pathlib import Path

try:
    import httpx
    import psycopg
    from dotenv import load_dotenv
except ImportError:
    print("[ERROR] Packages missing. Run:  pip install \"psycopg[binary]\" python-dotenv httpx")
    sys.exit(1)

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / ".env"
if not ENV.exists():
    print(f"[ERROR] .env not found at {ENV}")
    sys.exit(1)
load_dotenv(ENV)

results = []


def report(name, ok, detail=""):
    results.append(ok)
    print(f"[{'OK' if ok else 'FAIL'}] {name}" + (f"  - {detail}" if detail else ""))


def get(name):
    v = (os.getenv(name) or "").strip().strip('"').strip("'")
    return v


# 1. Neon
url = get("DATABASE_URL")
if not url:
    report("Neon DATABASE_URL", False, "empty in .env")
else:
    try:
        with psycopg.connect(url, connect_timeout=15) as conn:
            with conn.cursor() as cur:
                cur.execute("SHOW server_version")
                ver = cur.fetchone()[0]
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute("SELECT extversion FROM pg_extension WHERE extname='vector'")
                vec = cur.fetchone()[0]
            conn.commit()
        report("Neon Postgres", True, f"Postgres {ver}, pgvector {vec} enabled")
    except Exception as e:
        report("Neon Postgres", False, type(e).__name__ + ": " + str(e).split("\n")[0][:150])


def check_http(name, env_name, url, headers=None, params=None):
    key = get(env_name)
    if not key:
        report(name, False, f"{env_name} empty in .env")
        return
    h = {k: v.replace("{KEY}", key) for k, v in (headers or {}).items()}
    p = {k: v.replace("{KEY}", key) for k, v in (params or {}).items()}
    try:
        r = httpx.get(url, headers=h, params=p, timeout=20)
        if r.status_code == 200:
            data = r.json()
            n = len(data.get("data", data.get("models", []))) if isinstance(data, dict) else 0
            report(name, True, f"key valid" + (f", {n} models visible" if n else ""))
        else:
            report(name, False, f"HTTP {r.status_code} - key wrong or not activated")
    except Exception as e:
        report(name, False, type(e).__name__ + ": " + str(e)[:120])


# 2-4. LLM keys
check_http("Gemini", "GEMINI_API_KEY",
           "https://generativelanguage.googleapis.com/v1beta/models",
           params={"key": "{KEY}"})
check_http("Groq", "GROQ_API_KEY",
           "https://api.groq.com/openai/v1/models",
           headers={"Authorization": "Bearer {KEY}"})
check_http("OpenRouter", "OPENROUTER_API_KEY",
           "https://openrouter.ai/api/v1/key",
           headers={"Authorization": "Bearer {KEY}"})

print()
if all(results):
    print("ALL CHECKS PASSED - ready for Phase 1")
else:
    print(f"{results.count(False)} check(s) failed - send this output to Claude (it contains no keys)")
