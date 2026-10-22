"""Nexora Build API – run locally with:  uvicorn app.main:app --reload --port 8000"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError

from . import config
from .alerts import start_alerts
from .backup import start_auto_backups
from .db import SessionLocal, init_db
from .routers import admin, ai, auth, extras, invites, push, trash, design, drawing, estimate, files, pm, projects, settings, site, users, vastu
from .seed import seed
from .storage import storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("nexora")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("Starting %s %s", config.APP_NAME, config.APP_VERSION)
    init_db()
    with SessionLocal() as db:
        seed(db)
    start_auto_backups()
    start_alerts()
    log.info("Ready. Storage backend: %s", storage.name)
    yield
    if storage.name == "hf":  # send files still waiting for upload before the server stops
        try:
            storage.flush()
        except Exception as e:
            log.warning("Files still waiting for upload (sent on next start): %s", e)


app = FastAPI(title="Nexora Build API", version=config.APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.FRONTEND_ORIGINS,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- speed log: requests slower than 1.5 s are written to the console with their database query count
import contextvars  # noqa: E402
import time as _time  # noqa: E402

from sqlalchemy import event  # noqa: E402

from .db import engine  # noqa: E402

_q = contextvars.ContextVar("nexora_queries", default=None)


@event.listens_for(engine, "before_cursor_execute")
def _count_query(*_a, **_k):
    c = _q.get()
    if c is not None:
        c[0] += 1


@app.middleware("http")
async def timing(request: Request, call_next):
    counter = [0]
    _q.set(counter)
    t0 = _time.perf_counter()
    response = await call_next(request)
    ms = (_time.perf_counter() - t0) * 1000
    response.headers["X-Response-Time-ms"] = f"{ms:.0f}"
    if ms > 1500 and not request.url.path.startswith(("/api/ai/chat", "/api/ai/transcribe", "/api/drawings")):
        log.warning("SLOW %s %s %.1f s (%d DB queries)", request.method, request.url.path, ms / 1000, counter[0])
    return response


@app.exception_handler(DBAPIError)
async def db_error_handler(request: Request, exc: DBAPIError):
    msg = str(getattr(exc, "orig", exc)).split("\n")[0]
    if "Nexora Build:" in msg:  # raised by our protection triggers
        return JSONResponse(status_code=400, content={"detail": msg[msg.index("Nexora Build:"):]})
    log.exception("Database error")
    return JSONResponse(status_code=500, content={"detail": "Database error – please try again"})


for r in (auth.router, users.router, projects.router, files.router, settings.router, admin.router,
          estimate.router, design.router, drawing.router, vastu.router, pm.router, site.router, ai.router,
          trash.router, invites.router, invites.notif_router, extras.router, push.router):
    app.include_router(r)


@app.get("/", include_in_schema=False)
def root():
    return {"message": "Nexora Build backend is running.",
            "api_docs": "/docs"}


@app.get("/api/health")
def health():
    return {"status": "ok", "app": config.APP_NAME, "version": config.APP_VERSION, "storage": storage.name}
