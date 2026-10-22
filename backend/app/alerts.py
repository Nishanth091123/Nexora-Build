"""Phase 7.8 – weather safety alerts for every project site.

* Bell (in the app): today's risks for the projects a user can open.
* Phone / PC push (Web Push): sent automatically at 6 AM (today) and 6 PM (tomorrow), once per project per day.
  Works while the server is awake; on the free Render plan a free scheduler (cron-job.org) opens the
  "daily check" link each morning and evening, which wakes the server and sends the alerts.
Forecast: Open-Meteo (free, no key). The rules are the same as the Home weather card.
"""
from __future__ import annotations

import base64
import json
import logging
import secrets
import threading
import time
from datetime import date, datetime, timedelta, timezone

import httpx
from sqlalchemy.orm import Session

from . import config
from .db import SessionLocal
from .models import AppSetting, Project, ProjectAccess, PushSubscription, User

log = logging.getLogger("nexora.alerts")
IST = timezone(timedelta(hours=5, minutes=30))
_fc: dict = {}     # (lat, lon) -> (time, days)
_geo: dict = {}    # place name -> (lat, lon) | None


# ---------------------------------------------------------------- forecast
def _point(p: Project):
    if p.latitude is not None and p.longitude is not None:
        return float(p.latitude), float(p.longitude)
    name = (p.location or p.district or "").split(",")[0].strip()
    if not name:
        return None
    if name not in _geo:
        try:
            r = httpx.get("https://geocoding-api.open-meteo.com/v1/search",
                          params={"name": name, "count": 1, "countryCode": "IN", "format": "json"}, timeout=8)
            hit = (r.json().get("results") or [None])[0]
            _geo[name] = (hit["latitude"], hit["longitude"]) if hit else None
        except Exception:
            return None
    return _geo[name]


def _days(lat: float, lon: float) -> list[dict]:
    key = (round(lat, 2), round(lon, 2))
    hit = _fc.get(key)
    if hit and time.time() - hit[0] < 3600:
        return hit[1]
    r = httpx.get("https://api.open-meteo.com/v1/forecast", timeout=8, params={
        "latitude": lat, "longitude": lon, "timezone": "Asia/Kolkata", "forecast_days": 2,
        "daily": "weather_code,temperature_2m_max,precipitation_probability_max,precipitation_sum,"
                 "wind_speed_10m_max,wind_gusts_10m_max"})
    d = r.json().get("daily") or {}
    days = [{"date": t, "code": (d.get("weather_code") or [0])[i] or 0,
             "tmax": (d.get("temperature_2m_max") or [0])[i] or 0,
             "prob": (d.get("precipitation_probability_max") or [0])[i] or 0,
             "mm": (d.get("precipitation_sum") or [0])[i] or 0,
             "gust": max((d.get("wind_gusts_10m_max") or [0])[i] or 0, (d.get("wind_speed_10m_max") or [0])[i] or 0)}
            for i, t in enumerate(d.get("time") or [])]
    _fc[key] = (time.time(), days)
    return days


# ---------------------------------------------------------------- rules (same as the Home card)
def risks(day: dict, lang: str = "en") -> list[dict]:
    ta = lang == "ta"
    out = []
    if day["code"] >= 95:
        out.append(("storm", "இடியுடன் மழை" if ta else "Thunderstorm",
                    "புயலின் போது கிரேன், கம்பி, மொட்டைமாடி வேலை வேண்டாம். கம்பிகளிடம் இருந்து விலகி இருங்கள்." if ta else
                    "Stop crane, steel and terrace work during the storm. Keep workers away from steel bars."))
    if day["mm"] >= 20 or (day["prob"] >= 85 and day["mm"] >= 10):
        out.append(("heavy", f"கனமழை ({round(day['mm'])} mm)" if ta else f"Heavy rain ({round(day['mm'])} mm)",
                    "தோண்டுதல், ஆழமான குழி வேலை வேண்டாம். புதிய கான்கிரீட்டை மூடுங்கள்." if ta else
                    "No excavation or deep-trench work. Cover fresh concrete and drain the pits."))
    elif day["prob"] >= 70:
        out.append(("rain", f"மழை வாய்ப்பு {round(day['prob'])}%" if ta else f"Rain likely ({round(day['prob'])}%)",
                    "கான்கிரீட் / பூச்சு வேலை வேண்டாம். சிமெண்ட் மூட்டைகளை உள்ளே வையுங்கள்." if ta else
                    "Avoid concreting and plastering. Keep cement bags inside on pallets."))
    if day["gust"] >= 50:
        out.append(("wind", f"பலத்த காற்று ({round(day['gust'])} km/h)" if ta else f"Strong wind ({round(day['gust'])} km/h)",
                    "சாரம், கூரை, உயர வேலை வேண்டாம். ஷீட் / ஷட்டரிங் கட்டி வையுங்கள்." if ta else
                    "No scaffolding, roof or work at height. Tie down sheets and shuttering."))
    if day["tmax"] >= 39:
        out.append(("heat", f"கடும் வெயில் ({round(day['tmax'])}°C)" if ta else f"Extreme heat ({round(day['tmax'])}°C)",
                    "12–3 மணி ஓய்வு, குடிநீர், நிழல். காலை / மாலை கான்கிரீட், அடிக்கடி க்யூரிங்." if ta else
                    "Rest 12–3 pm, water and shade for workers. Pour early or late and cure more often."))
    return [{"kind": k, "title": t, "body": b} for k, t, b in out]


def project_risks(p: Project, offset: int = 0, lang: str = "en") -> list[dict]:
    pt = _point(p)
    if not pt:
        return []
    try:
        days = _days(*pt)
    except Exception as e:
        log.info("forecast failed for %s: %s", p.code, e)
        return []
    return risks(days[offset], lang) if len(days) > offset else []


# ---------------------------------------------------------------- who sees which project
def _live_projects(db: Session) -> list[Project]:
    return db.query(Project).filter(Project.is_hidden.is_(False), Project.status.in_(("ongoing", "on_hold"))).all()


def visible_projects(db: Session, user: User) -> list[Project]:
    live = _live_projects(db)
    if user.role == "owner":
        return live
    ok = {a.project_id for a in db.query(ProjectAccess).filter_by(user_id=user.id).all()}
    return [p for p in live if p.id in ok]


_refreshing = threading.Event()


def _refresh(points: list) -> None:
    try:
        for pt in points:
            try:
                _days(*pt)
            except Exception:
                pass
    finally:
        _refreshing.clear()


def _cached_risks(p: Project, lang: str) -> list[dict] | None:
    """Only from the cache – the bell must never wait for the weather service."""
    name = (p.location or p.district or "").split(",")[0].strip()
    if p.latitude is not None and p.longitude is not None:
        pt = (float(p.latitude), float(p.longitude))
    elif name in _geo:
        pt = _geo[name]
    else:
        return None
    if not pt:
        return []
    hit = _fc.get((round(pt[0], 2), round(pt[1], 2)))
    if not hit or time.time() - hit[0] > 3600:
        return None
    return risks(hit[1][0], lang) if hit[1] else []


def bell_items(db: Session, user: User) -> list[dict]:
    items = []
    now = datetime.now(IST)
    missing = []
    for p in visible_projects(db, user)[:6]:
        found = _cached_risks(p, user.language or "en")
        if found is None:
            missing.append(p)
            continue
        for r in found:
            items.append({"key": f"weather:{p.id}:{now.date()}:{r['kind']}", "kind": "weather",
                          "title": f"⚠️ {p.name}: {r['title']}", "body": r["body"], "link": "/",
                          "at": now.isoformat()})
    if missing and not _refreshing.is_set():  # fetch in the background; the next bell check shows them
        _refreshing.set()

        def work(ps=missing):
            pts = [pt for pt in (_point(x) for x in ps) if pt]
            _refresh(pts)
        threading.Thread(target=work, daemon=True).start()
    return items


# ---------------------------------------------------------------- Web Push
def _setting(db: Session, key: str) -> AppSetting:
    s = db.get(AppSetting, key)
    if not s:
        s = AppSetting(key=key, value={})
        db.add(s)
        db.flush()
    return s


def vapid_keys(db: Session) -> dict:
    """Created once and kept in the database, so the PC copy and the online copy use the same keys."""
    s = _setting(db, "webpush")
    if not (s.value or {}).get("public"):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        k = ec.generate_private_key(ec.SECP256R1())
        pem = k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                              serialization.NoEncryption()).decode()
        raw = k.public_key().public_bytes(serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
        s.value = {"private_pem": pem, "public": base64.urlsafe_b64encode(raw).decode().rstrip("=")}
        db.commit()
    return s.value


def cron_key(db: Session) -> str:
    s = _setting(db, "alerts")
    if not (s.value or {}).get("cron_key"):
        s.value = {**(s.value or {}), "cron_key": secrets.token_urlsafe(24)}
        db.commit()
    return s.value["cron_key"]


def push(db: Session, user_ids: list[int], title: str, body: str, url: str = "/") -> int:
    """Send to every active device of these users. Dead subscriptions are switched off."""
    subs = db.query(PushSubscription).filter(PushSubscription.user_id.in_(user_ids),
                                             PushSubscription.is_active.is_(True)).all()
    if not subs:
        return 0
    try:
        from py_vapid import Vapid
        from pywebpush import WebPushException, webpush
    except ImportError:
        log.warning("pywebpush is not installed – run scripts\\update.bat")
        return 0
    keys = vapid_keys(db)
    vapid = Vapid.from_pem(keys["private_pem"].encode())
    sub_mail = config.OWNER_EMAIL or "admin@nexora.build"
    sent = 0
    payload = json.dumps({"title": title, "body": body, "url": url}, ensure_ascii=False)
    for s in subs:
        try:
            webpush({"endpoint": s.endpoint, "keys": {"p256dh": s.p256dh, "auth": s.auth}}, payload,
                    vapid_private_key=vapid, vapid_claims={"sub": f"mailto:{sub_mail}"}, ttl=12 * 3600)
            sent += 1
        except WebPushException as e:
            code = getattr(getattr(e, "response", None), "status_code", 0)
            if code in (404, 410):
                s.is_active = False
            log.info("push failed (%s): %s", code, str(e)[:120])
        except Exception as e:
            log.info("push failed: %s", str(e)[:120])
    db.commit()
    return sent


def _audience(db: Session, p: Project) -> list[User]:
    owners = db.query(User).filter(User.role == "owner", User.status == "active").all()
    ids = {a.user_id for a in db.query(ProjectAccess).filter_by(project_id=p.id).all()}
    users = db.query(User).filter(User.id.in_(ids), User.status == "active").all() if ids else []
    return {u.id: u for u in owners + users}.values()


_run_lock = threading.Lock()


def run(when: str = "today") -> dict:
    """Check every live project and push today's (or tomorrow's) risks – once per project per day."""
    with _run_lock, SessionLocal() as db:
        offset = 0 if when == "today" else 1
        day = (datetime.now(IST).date() + timedelta(days=offset)).isoformat()
        s = _setting(db, "alerts")
        sent_log = dict((s.value or {}).get("sent") or {})
        done = set(sent_log.get(day) or [])
        projects, pushed = 0, 0
        for p in _live_projects(db):
            tag = f"{p.id}:{when}"
            if tag in done:
                continue
            pt = _point(p)
            if not pt:
                continue  # no site location / town – nothing to check
            try:
                _days(*pt)
            except Exception:
                continue  # weather service not reachable – try again in 15 minutes
            found = project_risks(p, offset, "en")
            done.add(tag)
            if not found:
                continue
            projects += 1
            for u in _audience(db, p):
                rs = project_risks(p, offset, u.language or "en")
                head = ("இன்று" if when == "today" else "நாளை") if u.language == "ta" else ("Today" if when == "today" else "Tomorrow")
                title = f"⚠️ {p.name}: {head} – {rs[0]['title']}"
                body = " ".join(f"{r['title']}: {r['body']}" if i else r["body"] for i, r in enumerate(rs[:2]))
                pushed += push(db, [u.id], title, body, "/")
        keep = sorted(sent_log)[-6:]
        sent_log = {k: sent_log[k] for k in keep}
        sent_log[day] = sorted(done)
        s = _setting(db, "alerts")
        s.value = {**(s.value or {}), "sent": sent_log, "last_run": datetime.now(IST).isoformat()}
        db.commit()
        return {"day": day, "when": when, "projects_with_risk": projects, "notifications_sent": pushed}


def run_due() -> list[dict]:
    """What is due now (IST): from 6 AM today's alerts, from 5 PM tomorrow's."""
    now = datetime.now(IST)
    out = []
    if now.hour >= 6:
        out.append(run("today"))
    if now.hour >= 17:
        out.append(run("tomorrow"))
    return out


def _loop():
    time.sleep(60)
    while True:
        try:
            run_due()
        except Exception as e:  # never stop the app because of alerts
            log.warning("weather alerts: %s", e)
        time.sleep(900)  # every 15 minutes (each project is sent once per day)


def start_alerts() -> None:
    threading.Thread(target=_loop, name="nexora-alerts", daemon=True).start()
