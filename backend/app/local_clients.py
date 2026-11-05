"""1.14 – bring client records back into the app.

1.13 moved client records + documents into  <project folder>\\local_data\\  on the PC (SQLite + files).
Nishanth's real wish: the CLIENT RECORDS stay in the app (ID, details, which documents are needed);
only the document FILES are never stored by the app – he keeps them in his own laptop folder.

At the PC start-up this copies the client records from local_data\\clients.db back into the app database
(same ID and code, so project links stay), marks the documents checklist from the files he had uploaded,
and renames clients.db so it is not read again. The document files stay untouched in
local_data\\client_files\\<code>\\ on the PC (nothing is uploaded, nothing is deleted).
"""
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from . import config

log = logging.getLogger("nexora.clients")
ONLINE = bool(os.getenv("RENDER")) or config.env("NEXORA_MODE").lower() == "online"
LOCAL_DIR = Path(config.env("LOCAL_DATA_DIR", str(config.PROJECT_DIR / "local_data")))

CAT_TO_DOC = {"client_land": ("patta", "sale_deed"), "client_id": ("aadhaar",), "client_site": ("site_photos",)}


def move_back(db) -> int:
    from .models import Client
    src = LOCAL_DIR / "clients.db"
    if ONLINE or not src.exists():
        return 0
    con = sqlite3.connect(str(src))
    con.row_factory = sqlite3.Row
    try:
        clients = [dict(r) for r in con.execute("SELECT * FROM clients")]
        files = [dict(r) for r in con.execute("SELECT * FROM client_files")] if con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='client_files'").fetchone() else []
    finally:
        con.close()
    n = 0
    today = datetime.now().strftime("%Y-%m-%d")
    for r in clients:
        c = db.get(Client, r["id"])
        if c is None:
            code = r["code"]
            if db.query(Client).filter_by(code=code).first():
                code = f"{code}-{r['id']}"
            c = Client(id=r["id"], code=code, name=r["name"], phone=r.get("phone") or "", email=r.get("email") or "",
                       address=r.get("address") or "", location=r.get("location") or "", notes=r.get("notes") or "",
                       is_hidden=bool(r.get("is_hidden")), created_by=r.get("created_by"))
            db.add(c)
            n += 1
        docs = {i.get("key"): i for i in (c.doc_checklist or [])}
        for f in files:
            if f["client_id"] != r["id"] or f.get("is_hidden"):
                continue
            for key in CAT_TO_DOC.get(f.get("category") or "", ()):
                docs.setdefault(key, {"key": key, "name": "", "status": "received", "date": today,
                                      "note": f"File kept on the PC: local_data/{f.get('rel_path', '')}", "custom": False})
        if docs:
            c.doc_checklist = [d for d in docs.values() if d.get("name") or d.get("key")]
            for d in c.doc_checklist:
                if not d.get("name"):
                    d["name"] = {"patta": "Patta (Chitta / Adangal)", "sale_deed": "Sale deed / title deed",
                                 "aadhaar": "Aadhaar card (owner)", "site_photos": "Site photographs"}.get(d["key"], d["key"])
    db.commit()
    if db.get_bind().dialect.name == "postgresql":  # explicit ids were used – move the id counter past them
        db.execute(text("SELECT setval(pg_get_serial_sequence('clients', 'id'), GREATEST((SELECT COALESCE(MAX(id), 1) FROM clients), 1))"))
        db.commit()
    src.rename(src.with_name(f"clients_back_in_app_{datetime.now():%Y%m%d_%H%M%S}.db"))
    log.info("Clients back in the app: %d record(s). Document files stay in %s", n, LOCAL_DIR / "client_files")
    return n
