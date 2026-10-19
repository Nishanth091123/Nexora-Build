"""First-run data: the permanent owner account, company row and default settings."""
import logging

from sqlalchemy.orm import Session

from . import config
from .estimate.rates_seed import DEFAULT_STATE, RATES
from .models import AppSetting, Organization, RateItem, User, utcnow
from .security import hash_password

log = logging.getLogger("nexora.seed")

DEFAULT_SETTINGS: dict[str, dict] = {
    "general": {
        "default_language": config.DEFAULT_LANGUAGE,
        "default_state": config.DEFAULT_STATE,
        "default_spec_level": config.DEFAULT_SPEC_LEVEL,
        "default_structure": "rcc_framed",
        "allow_self_registration": True,
    },
    "units": {
        "unit_system": "metric",          # metric | imperial
        "decimal_places": 2,
        "currency": "INR",
        "rate_region": "Tamil Nadu",
        "measurement_input": "preserve",  # preserve | convert_to_metric
    },
    "ai": {
        "language": "ta_en",              # en | ta | ta_en (Tamil + English mixed)
        "response_style": "detailed",     # short | detailed
        "show_sources": True,
        "show_calculation_steps": True,
        "show_assumptions": True,
        "use_project_context": True,
        "voice_input": True,
        "provider_order": ["gemini", "groq", "openrouter"],
    },
    "notifications": {
        "project_updates": True, "task_assignments": True, "drawing_approvals": True,
        "estimate_revisions": True, "site_progress": True, "ai_suggestions": True,
        "email_notifications": False,
    },
    "security": {
        "session_timeout_minutes": 480,
        "password_policy": "min 8 characters, letters + numbers",
        "login_activity_tracking": True,
    },
    "backups": {
        "automatic": True,
        "frequency_hours": config.AUTO_BACKUP_HOURS,
    },
}


def seed(db: Session) -> None:
    owner = db.query(User).filter(User.role == "owner").first()
    if not owner:
        if not config.OWNER_EMAIL or not config.OWNER_INITIAL_PASSWORD:
            raise RuntimeError(
                "First start: set OWNER_EMAIL and OWNER_INITIAL_PASSWORD in .env to create the owner account")
        owner = User(
            username=config.OWNER_USERNAME, email=config.OWNER_EMAIL, full_name=config.OWNER_FULL_NAME,
            job_title="Project Engineer", password_hash=hash_password(config.OWNER_INITIAL_PASSWORD),
            role="owner", status="active", is_protected=True, can_create_projects=True,
            password_changed_at=utcnow(),
        )
        db.add(owner)
        log.info("Owner account '%s' created", config.OWNER_USERNAME)

    if not db.get(Organization, 1):
        db.add(Organization(id=1, name="", industry="Construction & Infrastructure"))

    # default Tamil Nadu rates – only ADD missing codes, never overwrite edited rates
    have = {r.code for r in db.query(RateItem).filter(RateItem.state == DEFAULT_STATE).all()}
    for code, kind, cat, name, unit, b, s_, p, note in RATES:
        if code not in have:
            db.add(RateItem(state=DEFAULT_STATE, code=code, kind=kind, category=cat, name=name, unit=unit,
                            basic=b, standard=s_, premium=p, note=note))

    for key, defaults in DEFAULT_SETTINGS.items():
        row = db.get(AppSetting, key)
        if not row:
            db.add(AppSetting(key=key, value=dict(defaults)))
        else:  # add new default keys without touching saved values
            merged = {**defaults, **(row.value or {})}
            if merged != row.value:
                row.value = merged
    db.commit()
