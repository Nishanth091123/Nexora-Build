"""Disaster recovery: rebuild an EMPTY database from a Nexora backup file (.json.gz).

    backend\\.venv\\Scripts\\python.exe scripts\\restore_backup.py  C:\\path\\nexora_manual_20261019_101500.json.gz

The database is the DATABASE_URL in .env. Make a NEW empty Neon database (or branch), put its
connection string in .env, then run this. It refuses to write into a database that already has projects.
To bring back only a few deleted items, use the app instead: Settings -> Backups -> Recover.
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    path = Path(sys.argv[1].strip('"'))
    if not path.exists():
        print(f"[FAIL] File not found: {path}")
        return 1
    from sqlalchemy import func, text
    from app import restore
    from app.db import SessionLocal, init_db
    from app.models import Base, Project, User

    doc = restore.load(path.read_bytes())
    print(f"Backup: {path.name}  made {doc.get('created_at', '?')}  ({doc.get('kind', '?')})")
    init_db()  # creates the tables if the database is new
    with SessionLocal() as db:
        if db.query(func.count(User.id)).scalar() or db.query(func.count(Project.id)).scalar():
            print("[STOP] This database is not empty. Restore needs a NEW empty database – do not start the app on it")
            print("       before restoring (see docs/PHASE_7_GUIDE.md). To bring back a few deleted items, use the app:")
            print("       Settings -> Backups -> Recover.")
            return 1
        for table in reversed(Base.metadata.sorted_tables):  # small default rows, if any
            if table.name != "schema_migrations" and table.name not in ("users",):
                if db.execute(text(f"SELECT 1 FROM {table.name} LIMIT 1")).first():
                    if db.get_bind().dialect.name == "postgresql":
                        db.execute(text("SET LOCAL nexora.allow_delete = 'on'"))
                    db.execute(table.delete())
        db.flush()
        counts = restore.restore_all(db, doc)
        users = db.query(func.count(User.id)).scalar()
    total = sum(counts.values())
    for k, v in counts.items():
        if v:
            print(f"  {k:28s} {v}")
    print(f"[OK] Restored {total} rows ({users} users). Start the app: scripts\\start.bat")
    print("     Stored files (drawings / photos) are in R2 or backend\\storage – they are not inside the backup.")
    print("     AI document search vectors are re-made automatically the next time the AI reads each project.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
