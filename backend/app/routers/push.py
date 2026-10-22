"""Phase 7.8 – phone / PC notifications (Web Push) and the daily weather-alert check."""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import alerts
from ..db import get_db
from ..models import PushSubscription, User
from ..security import get_current_user, require_owner

router = APIRouter(prefix="/api", tags=["notifications"])


class Keys(BaseModel):
    p256dh: str
    auth: str


class SubIn(BaseModel):
    endpoint: str
    keys: Keys
    device: str = ""


@router.get("/push/key")
def push_key(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"public_key": alerts.vapid_keys(db)["public"]}


@router.post("/push/subscribe")
def subscribe(body: SubIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    if not body.endpoint.startswith("https://") or len(body.endpoint) > 600:
        raise HTTPException(400, "Invalid subscription")
    s = db.query(PushSubscription).filter_by(endpoint=body.endpoint).first()
    if s:
        s.user_id, s.p256dh, s.auth, s.is_active = user.id, body.keys.p256dh, body.keys.auth, True
        s.device = body.device[:200]
    else:
        db.add(PushSubscription(user_id=user.id, endpoint=body.endpoint, p256dh=body.keys.p256dh,
                                auth=body.keys.auth, device=body.device[:200]))
    db.commit()
    return {"ok": True}


class EndIn(BaseModel):
    endpoint: str


@router.post("/push/unsubscribe")
def unsubscribe(body: EndIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    s = db.query(PushSubscription).filter_by(endpoint=body.endpoint, user_id=user.id).first()
    if s:
        s.is_active = False
        db.commit()
    return {"ok": True}


@router.get("/push/status")
def status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    n = db.query(PushSubscription).filter_by(user_id=user.id, is_active=True).count()
    return {"devices": n}


@router.post("/push/test")
def test(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    ta = user.language == "ta"
    n = alerts.push(db, [user.id], "Nexora Build ✅",
                    "இந்த device-க்கு weather safety alerts வரும்." if ta else
                    "Weather safety alerts will come to this device.", "/")
    if not n:
        raise HTTPException(400, "No device received it – press 'Turn on alerts' on this device first.")
    return {"sent": n}


@router.get("/alerts/today")
def today(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return {"items": alerts.bell_items(db, user)}


@router.get("/alerts/cron-key")
def cron_key(owner: User = Depends(require_owner), db: Session = Depends(get_db)):
    return {"key": alerts.cron_key(db)}


@router.get("/alerts/run")
def run(key: str = Query(...), db: Session = Depends(get_db)):
    """Opened by a free scheduler (cron-job.org) every morning and evening – wakes the server and sends alerts."""
    if key != alerts.cron_key(db):
        raise HTTPException(403, "Wrong key")
    db.close()
    return {"ok": True, "runs": alerts.run_due()}
