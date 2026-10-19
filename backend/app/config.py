"""Central configuration – everything comes from the project-level .env file."""
import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent
load_dotenv(PROJECT_DIR / ".env")
load_dotenv(BACKEND_DIR / ".env")  # optional override (used on Hugging Face)


def env(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip().strip('"').strip("'")


APP_NAME = env("APP_NAME", "Nexora Build")
APP_VERSION = "1.7.6-phase7"

OWNER_USERNAME = env("OWNER_USERNAME", "nishanth_s").lower()
OWNER_EMAIL = env("OWNER_EMAIL").lower()
OWNER_INITIAL_PASSWORD = env("OWNER_INITIAL_PASSWORD")
OWNER_FULL_NAME = env("OWNER_FULL_NAME", "Nishanth S")

JWT_SECRET = env("JWT_SECRET", "change-me")
JWT_ALGORITHM = "HS256"

DATABASE_URL = env("DATABASE_URL")

STORAGE_BACKEND = env("STORAGE_BACKEND", "auto")  # auto | local | r2 | hf
LOCAL_STORAGE_DIR = Path(env("LOCAL_STORAGE_DIR", str(BACKEND_DIR / "storage")))
R2_ACCOUNT_ID = env("R2_ACCOUNT_ID")
R2_ACCESS_KEY_ID = env("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = env("R2_SECRET_ACCESS_KEY")
R2_BUCKET = env("R2_BUCKET", "nexora-build-files")
HF_TOKEN = env("HF_TOKEN")
HF_FILES_REPO = env("HF_FILES_REPO")  # private dataset repo for files when STORAGE_BACKEND=hf (blank = <you>/nexora-build-files)

FRONTEND_ORIGINS = [o.strip() for o in env(
    "FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if o.strip()]

DEFAULT_LANGUAGE = env("DEFAULT_LANGUAGE", "en")
DEFAULT_STATE = env("DEFAULT_STATE", "Tamil Nadu")
DEFAULT_SPEC_LEVEL = env("DEFAULT_SPEC_LEVEL", "standard")

MAX_UPLOAD_MB = int(env("MAX_UPLOAD_MB", "25"))
AUTO_BACKUP_HOURS = int(env("AUTO_BACKUP_HOURS", "24"))


def database_url() -> str:
    """Convert a Neon 'postgresql://' URL to the SQLAlchemy psycopg3 driver form."""
    url = DATABASE_URL
    if not url:
        raise RuntimeError(
            "DATABASE_URL is empty. Put your Neon connection string in C:\\PROJECTS\\Nexora_Build\\.env")
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url
