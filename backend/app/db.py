"""Database engine + safe, additive schema setup.

Safety rules enforced here:
  * create_all() only CREATES missing tables – it never drops or alters existing ones.
  * Future column additions go into ADDITIVE_MIGRATIONS (ALTER TABLE ... ADD COLUMN IF NOT EXISTS).
  * Postgres triggers block DELETE on business tables and protect the owner account,
    so even a coding mistake cannot remove data.
"""
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from . import config
from .models import Base, SchemaMigration

log = logging.getLogger("nexora.db")

engine = create_engine(
    config.database_url(),
    pool_pre_ping=True,      # Neon suspends idle computes – re-check connections
    pool_recycle=280,
    pool_size=5,
    max_overflow=5,
    pool_timeout=20,
    # keepalives: a connection silently dropped by the network / Neon is detected in ~1 min instead of hanging
    connect_args={"prepare_threshold": None, "connect_timeout": 20, "keepalives": 1, "keepalives_idle": 30,
                  "keepalives_interval": 10, "keepalives_count": 3},  # safe with Neon's pooler
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Tables whose rows may never be deleted (soft-hide / archive instead).
NO_DELETE_TABLES = ["projects", "files", "audit_logs", "backup_records", "project_access", "organization",
                    "rate_items", "estimates", "designs", "drawing_analyses", "vastu_reports",
                    "schedule_stages", "tasks", "approvals", "site_reports", "site_activities", "site_photos",
                    "material_entries", "workers", "attendance", "quality_checks", "safety_records",
                    "ai_conversations", "ai_messages", "ai_indexed_files", "ai_doc_chunks",
                    "trash_log", "invite_links", "bbs_schedules", "permit_checklists", "ai_photo_checks",
                    "clients", "project_notes", "structural_designs", "library_items"]

PG_PROTECTION_SQL = [
    """
    CREATE OR REPLACE FUNCTION nexora_block_delete() RETURNS trigger AS $$
    BEGIN
        -- only the owner's "Delete permanently" (Recycle Bin) sets this, inside its own transaction
        IF current_setting('nexora.allow_delete', true) = 'on' THEN
            RETURN OLD;
        END IF;
        RAISE EXCEPTION 'Nexora Build: deleting rows from % is not allowed (data is never deleted)', TG_TABLE_NAME;
    END $$ LANGUAGE plpgsql;
    """,
    """
    CREATE OR REPLACE FUNCTION nexora_protect_owner() RETURNS trigger AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'Nexora Build: user accounts cannot be deleted (deactivate instead)';
        END IF;
        IF OLD.is_protected THEN
            IF NEW.role <> 'owner' OR NEW.status <> 'active' OR NEW.is_protected = false THEN
                RAISE EXCEPTION 'Nexora Build: the owner account cannot be demoted or deactivated';
            END IF;
        END IF;
        RETURN NEW;
    END $$ LANGUAGE plpgsql;
    """,
    "DROP TRIGGER IF EXISTS trg_nexora_protect_owner ON users",
    """CREATE TRIGGER trg_nexora_protect_owner BEFORE UPDATE OR DELETE ON users
       FOR EACH ROW EXECUTE FUNCTION nexora_protect_owner()""",
]

# version -> list of SQL statements. Only ADD things. Never DROP/RENAME.
ADDITIVE_MIGRATIONS: dict[str, list[str]] = {
    "0001_phase1_initial": [],  # tables come from create_all
    "0002_optional_user_email": ["ALTER TABLE users ALTER COLUMN email DROP NOT NULL"],
    "0003_phase2_estimates": [],  # rate_items + estimates come from create_all
    "0004_phase3_designs": [],  # designs table comes from create_all
    "0005_phase4_drawings_vastu": [],  # drawing_analyses + vastu_reports come from create_all
    "0006_phase5_site": [
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION",
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION",
    ],
    # ai_* tables come from create_all; the pgvector column for document search is added here.
    "0007_phase6_ai": ["ALTER TABLE ai_doc_chunks ADD COLUMN IF NOT EXISTS embedding vector(768)"],
    # Recycle Bin, invites, BBS, permit checklist, photo check (new tables come from create_all)
    "0008_phase6_6_bin_invites": [
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN NOT NULL DEFAULT false",
        "ALTER TABLE workers ADD COLUMN IF NOT EXISTS is_hidden BOOLEAN NOT NULL DEFAULT false",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS invited_via INTEGER",
    ],
    # 1.8: Clients (owner only), project workflow tracker, company proprietor
    "0009_v18_clients": [
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS client_id INTEGER",
        "ALTER TABLE projects ADD COLUMN IF NOT EXISTS workflow JSON",
        "CREATE INDEX IF NOT EXISTS ix_projects_client_id ON projects (client_id)",
        "ALTER TABLE files ADD COLUMN IF NOT EXISTS client_id INTEGER",
        "CREATE INDEX IF NOT EXISTS ix_files_client_id ON files (client_id)",
        "ALTER TABLE organization ADD COLUMN IF NOT EXISTS proprietor VARCHAR(160) NOT NULL DEFAULT ''",
        "UPDATE organization SET name = 'Praganya Construction' WHERE id = 1 AND (name IS NULL OR name = '')",
        "UPDATE organization SET proprietor = 'Nishanth S' WHERE id = 1 AND (proprietor IS NULL OR proprietor = '')",
    ],
    # 1.9.1: the owner asked for the firm name – replace the old app-name placeholder too (once)
    "0010_v191_company_name": [
        "UPDATE organization SET name = 'Praganya Construction' WHERE id = 1 AND (name IS NULL OR name = '' OR name ILIKE 'nexora%')",
        "UPDATE organization SET proprietor = 'Nishanth S' WHERE id = 1 AND (proprietor IS NULL OR proprietor = '')",
    ],
    # 1.14: client documents checklist (no files), approval drawing details + approval stages
    "0011_v114_approval": [
        "ALTER TABLE clients ADD COLUMN IF NOT EXISTS doc_checklist JSON",
        "ALTER TABLE permit_checklists ADD COLUMN IF NOT EXISTS site_info JSON",
        "ALTER TABLE permit_checklists ADD COLUMN IF NOT EXISTS workflow JSON",
    ],
    # 1.16: separate Approval / Material Rates permissions (default off = owner only)
    "0012_v116_perms": [
        "ALTER TABLE project_access ADD COLUMN IF NOT EXISTS can_approval BOOLEAN DEFAULT FALSE",
        "ALTER TABLE project_access ADD COLUMN IF NOT EXISTS can_rates BOOLEAN DEFAULT FALSE",
    ],
}


def _protection_triggers() -> None:
    """1.11.1: create the delete-protection triggers ONLY when missing.

    Before, every start (PC test backend, Render wake-up / deploy) dropped and re-created ~35 triggers in one
    transaction. That needs an exclusive lock on every table; with two servers on the same Neon database the
    locks queued behind each other and a simple save could hang for minutes (811 s in the test).
    Now: functions are replaced (no table lock), triggers are created only if absent, each in its own short
    transaction with lock_timeout, so a busy table never blocks the start-up or other users."""
    funcs = [s for s in PG_PROTECTION_SQL if "FUNCTION" in s and "TRIGGER trg_" not in s and not s.strip().startswith("DROP")]
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL lock_timeout = '5s'"))
        for stmt in funcs:
            conn.execute(text(stmt))
    with engine.connect() as conn:
        have = {r[0] for r in conn.execute(text("SELECT tgname FROM pg_trigger WHERE NOT tgisinternal"))}
    wanted = [(f"trg_nexora_nodelete_{t}", f"CREATE TRIGGER trg_nexora_nodelete_{t} BEFORE DELETE ON {t} "
                                          f"FOR EACH ROW EXECUTE FUNCTION nexora_block_delete()") for t in NO_DELETE_TABLES]
    wanted.append(("trg_nexora_protect_owner", "CREATE TRIGGER trg_nexora_protect_owner BEFORE UPDATE OR DELETE ON users "
                                               "FOR EACH ROW EXECUTE FUNCTION nexora_protect_owner()"))
    for name, stmt in wanted:
        if name in have:
            continue
        try:
            with engine.begin() as conn:
                conn.execute(text("SET LOCAL lock_timeout = '5s'"))
                conn.execute(text(stmt))
            log.info("Protection trigger added: %s", name)
        except Exception as e:  # a busy table: try again on the next start, never hang
            log.warning("Protection trigger %s not added now (table busy): %s", name, str(e).split("\n")[0][:120])


def init_db() -> None:
    is_pg = engine.dialect.name == "postgresql"
    with engine.begin() as conn:
        if is_pg:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine, checkfirst=True)

    if is_pg:
        _protection_triggers()

    with Session(engine) as db:
        done = {m.version for m in db.query(SchemaMigration).all()}
        for version, stmts in ADDITIVE_MIGRATIONS.items():
            if version in done:
                continue
            for s in stmts:
                db.execute(text(s))
            db.add(SchemaMigration(version=version))
            db.commit()
            log.info("Applied migration %s", version)
