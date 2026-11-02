"""Tiny helper for update.bat: has an install step's input changed since the last successful run?

    python scripts\\changed.py check NAME file1 [file2 ...]   -> exit 0 = changed (run the step), 1 = same (skip)
    python scripts\\changed.py save  NAME file1 [file2 ...]   -> remember the current state (after the step worked)
A folder is hashed with all files inside it. Stored in .update_cache\\ (not pushed to GitHub).
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = ROOT / ".update_cache"
SKIP_DIRS = {"node_modules", "dist", ".venv", "__pycache__", ".git"}


def digest(paths: list[str]) -> str:
    h = hashlib.sha256()
    for p in paths:
        p = ROOT / p
        files = [p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file() and not (set(x.parts) & SKIP_DIRS)) if p.exists() else []
        for f in files:
            h.update(str(f.relative_to(ROOT)).encode())
            h.update(f.read_bytes())
    return h.hexdigest()


def main() -> int:
    mode, name, paths = sys.argv[1], sys.argv[2], sys.argv[3:]
    CACHE.mkdir(exist_ok=True)
    mark = CACHE / f"{name}.sha"
    cur = digest(paths)
    if mode == "save":
        mark.write_text(cur)
        return 0
    return 1 if mark.exists() and mark.read_text().strip() == cur else 0


if __name__ == "__main__":
    sys.exit(main())
