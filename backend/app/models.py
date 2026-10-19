"""Database tables. RULE: tables/columns are only ever ADDED, never dropped or renamed."""
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import (JSON, BigInteger, Boolean, Date, DateTime, Float, ForeignKey,
                        Integer, String, Text, UniqueConstraint)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(200), unique=True, index=True, nullable=True)  # optional
    full_name: Mapped[str] = mapped_column(String(120), default="")
    job_title: Mapped[str] = mapped_column(String(80), default="")  # Site Engineer, QS ...
    phone: Mapped[str] = mapped_column(String(30), default="")
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20), default="user")  # owner | user
    status: Mapped[str] = mapped_column(String(20), default="pending")  # active | pending | deactivated
    is_protected: Mapped[bool] = mapped_column(Boolean, default=False)  # True only for owner
    can_create_projects: Mapped[bool] = mapped_column(Boolean, default=False)
    language: Mapped[str] = mapped_column(String(5), default="en")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    invited_via: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # invite link id (6.6)


class Organization(Base):
    """Company information shown in Settings > General (single row, id=1)."""
    __tablename__ = "organization"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), default="")
    registration_no: Mapped[str] = mapped_column(String(80), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    industry: Mapped[str] = mapped_column(String(120), default="Construction & Infrastructure")
    phone: Mapped[str] = mapped_column(String(40), default="")
    email: Mapped[str] = mapped_column(String(200), default="")
    website: Mapped[str] = mapped_column(String(200), default="")
    logo_file_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)  # PRJ-0001
    name: Mapped[str] = mapped_column(String(200))
    project_type: Mapped[str] = mapped_column(String(30), default="residential")
    client_name: Mapped[str] = mapped_column(String(160), default="")
    location: Mapped[str] = mapped_column(String(160), default="")  # city / town
    district: Mapped[str] = mapped_column(String(80), default="")
    state: Mapped[str] = mapped_column(String(80), default="Tamil Nadu")
    plot_width: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    plot_length: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unit: Mapped[str] = mapped_column(String(5), default="ft")  # ft | m
    facing: Mapped[str] = mapped_column(String(12), default="")  # east, west ... ("" = not given)
    road_width: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # metres
    floors: Mapped[str] = mapped_column(String(20), default="G")  # G, G+1 ...
    builtup_area: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # sq ft
    structure_type: Mapped[str] = mapped_column(String(20), default="rcc_framed")  # rcc_framed | load_bearing
    spec_level: Mapped[str] = mapped_column(String(12), default="standard")  # basic | standard | premium
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ongoing")  # ongoing | on_hold | completed | archived
    health: Mapped[str] = mapped_column(String(20), default="on_track")  # on_track | delayed
    progress: Mapped[float] = mapped_column(Float, default=0)
    cover_image: Mapped[str] = mapped_column(String(200), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)  # in the Recycle Bin (6.6)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ProjectAccess(Base):
    """Per-user, per-project module permissions chosen by the owner."""
    __tablename__ = "project_access"
    __table_args__ = (UniqueConstraint("user_id", "project_id", name="uq_access_user_project"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    can_view: Mapped[bool] = mapped_column(Boolean, default=True)
    can_edit: Mapped[bool] = mapped_column(Boolean, default=False)  # edit project details, upload docs
    can_design: Mapped[bool] = mapped_column(Boolean, default=False)
    can_estimate: Mapped[bool] = mapped_column(Boolean, default=False)
    can_site: Mapped[bool] = mapped_column(Boolean, default=False)
    can_vastu: Mapped[bool] = mapped_column(Boolean, default=False)
    can_ai: Mapped[bool] = mapped_column(Boolean, default=True)
    project_role: Mapped[str] = mapped_column(String(20), default="viewer")  # editor | viewer (label only)
    granted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    user: Mapped[User] = relationship()


class StoredFile(Base):
    __tablename__ = "files"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(30), default="other")  # drawing|report|photo|contract|logo|other
    original_name: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(400), unique=True)
    storage_backend: Mapped[str] = mapped_column(String(10), default="local")
    content_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    uploaded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)  # "delete" only hides; data kept


class AppSetting(Base):
    __tablename__ = "app_settings"
    key: Mapped[str] = mapped_column(String(60), primary_key=True)  # units | ai | notifications | security
    value: Mapped[dict] = mapped_column(JSON, default=dict)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    username: Mapped[str] = mapped_column(String(60), default="")
    action: Mapped[str] = mapped_column(String(40))  # created | updated | uploaded | approved | login ...
    entity: Mapped[str] = mapped_column(String(40), default="")
    entity_id: Mapped[str] = mapped_column(String(40), default="")
    project_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    details: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class BackupRecord(Base):
    __tablename__ = "backup_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(10), default="auto")  # auto | manual
    storage_key: Mapped[str] = mapped_column(String(400))
    size_bytes: Mapped[int] = mapped_column(BigInteger, default=0)
    tables: Mapped[dict] = mapped_column(JSON, default=dict)  # {table: row_count}
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SchemaMigration(Base):
    __tablename__ = "schema_migrations"
    version: Mapped[str] = mapped_column(String(40), primary_key=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------- Phase 2: rate library + estimates ----------------

class RateItem(Base):
    """One editable rate for one state. Spec-level rates for materials; day wage for labour."""
    __tablename__ = "rate_items"
    __table_args__ = (UniqueConstraint("state", "code", name="uq_rate_state_code"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    state: Mapped[str] = mapped_column(String(80), index=True)
    code: Mapped[str] = mapped_column(String(60))
    kind: Mapped[str] = mapped_column(String(12))            # material | labour | equipment | extra
    category: Mapped[str] = mapped_column(String(40), default="")
    name: Mapped[str] = mapped_column(String(160))
    unit: Mapped[str] = mapped_column(String(20))
    basic: Mapped[float] = mapped_column(Float, default=0)
    standard: Mapped[float] = mapped_column(Float, default=0)
    premium: Mapped[float] = mapped_column(Float, default=0)
    note: Mapped[str] = mapped_column(Text, default="")
    is_custom: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Estimate(Base):
    """A saved estimate version. New calculations create new rows – old versions are kept."""
    __tablename__ = "estimates"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(160), default="")
    rate_state: Mapped[str] = mapped_column(String(80), default="Tamil Nadu")
    spec_level: Mapped[str] = mapped_column(String(12), default="standard")
    inputs: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    rates_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    grand_total: Mapped[float] = mapped_column(Float, default=0)
    cost_per_sqft: Mapped[float] = mapped_column(Float, default=0)
    builtup_sqft: Mapped[float] = mapped_column(Float, default=0)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Design(Base):
    """A saved floor-plan design version (Phase 3). Every save is a new row – old versions are kept."""
    __tablename__ = "designs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    title: Mapped[str] = mapped_column(String(160), default="")
    prompt: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(20), default="ai")  # ai | edited | manual
    plan: Mapped[dict] = mapped_column(JSON, default=dict)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    spec_level: Mapped[str] = mapped_column(String(12), default="standard")
    rate_state: Mapped[str] = mapped_column(String(80), default="Tamil Nadu")
    estimate_total: Mapped[float] = mapped_column(Float, default=0)
    cost_per_sqft: Mapped[float] = mapped_column(Float, default=0)
    builtup_sqft: Mapped[float] = mapped_column(Float, default=0)
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DrawingAnalysis(Base):
    """An uploaded drawing read by Nexora (Phase 4): what was found, and what the user confirmed."""
    __tablename__ = "drawing_analyses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    file_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    file_name: Mapped[str] = mapped_column(String(200), default="")
    method: Mapped[str] = mapped_column(String(20), default="")  # dxf | pdf | pdf-vision | image-vision
    model: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(20), default="analysed")  # analysed | confirmed
    extraction: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    design_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class VastuReport(Base):
    """A saved Vastu check of a design version."""
    __tablename__ = "vastu_reports"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    design_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    design_version: Mapped[int] = mapped_column(Integer, default=0)
    north_deg: Mapped[float] = mapped_column(Float, default=0)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    plan: Mapped[dict] = mapped_column(JSON, default=dict)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)



# ---------------------------------------------------------------- Phase 5: site + project management
class _Base5:
    pass


class ScheduleStage(Base):
    """A stage / work package on the project schedule (Gantt). Also drives stage-wise and overall progress."""
    __tablename__ = "schedule_stages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    stage_group: Mapped[str] = mapped_column(String(40), default="")  # foundation | structure | masonry | services | finishing | handover
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    progress: Mapped[float] = mapped_column(Float, default=0)
    weight: Mapped[float] = mapped_column(Float, default=1)
    is_milestone: Mapped[bool] = mapped_column(Boolean, default=False)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    actual_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    actual_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    assignee_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    stage_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(String(10), default="normal")  # low | normal | high
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | in_progress | completed
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    item_type: Mapped[str] = mapped_column(String(20), default="drawing")  # drawing | estimate | design | material | other
    title: Mapped[str] = mapped_column(String(200))
    ref_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # file / estimate / design id
    note: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | approved | rejected | changes
    approver_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    requested_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    history: Mapped[list] = mapped_column(JSON, default=list)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SiteReport(Base):
    """Daily Progress Report (one per project per day; edits update it)."""
    __tablename__ = "site_reports"
    __table_args__ = (UniqueConstraint("project_id", "report_date", name="uq_site_report_day"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    report_date: Mapped[date] = mapped_column(Date)
    weather: Mapped[str] = mapped_column(String(40), default="")
    work_done: Mapped[str] = mapped_column(Text, default="")
    next_plan: Mapped[str] = mapped_column(Text, default="")
    remarks: Mapped[str] = mapped_column(Text, default="")
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SiteActivity(Base):
    __tablename__ = "site_activities"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    title: Mapped[str] = mapped_column(String(200))
    location: Mapped[str] = mapped_column(String(120), default="")  # block / floor / area
    stage_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending | in_progress | completed
    progress: Mapped[float] = mapped_column(Float, default=0)
    photo_file_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SitePhoto(Base):
    __tablename__ = "site_photos"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    file_id: Mapped[int] = mapped_column(Integer)
    caption: Mapped[str] = mapped_column(String(200), default="")
    taken_on: Mapped[date] = mapped_column(Date)
    location: Mapped[str] = mapped_column(String(120), default="")
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    activity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class MaterialEntry(Base):
    """Material received at site or used / issued (stock = received − used)."""
    __tablename__ = "material_entries"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    code: Mapped[str] = mapped_column(String(40), default="")  # rate-library code, e.g. cement
    name: Mapped[str] = mapped_column(String(120))
    unit: Mapped[str] = mapped_column(String(20), default="")
    kind: Mapped[str] = mapped_column(String(10), default="received")  # received | used
    qty: Mapped[float] = mapped_column(Float, default=0)
    rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    supplier: Mapped[str] = mapped_column(String(120), default="")
    bill_no: Mapped[str] = mapped_column(String(60), default="")
    notes: Mapped[str] = mapped_column(Text, default="")
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Worker(Base):
    __tablename__ = "workers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    trade: Mapped[str] = mapped_column(String(30), default="mason")  # labour code from the rate library
    phone: Mapped[str] = mapped_column(String(20), default="")
    day_wage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    contractor: Mapped[str] = mapped_column(String(120), default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)  # in the Recycle Bin (6.6)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("worker_id", "work_date", name="uq_attendance_day"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    worker_id: Mapped[int] = mapped_column(Integer, index=True)
    work_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(10), default="present")  # present | half | absent
    wage: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    ot_hours: Mapped[float] = mapped_column(Float, default=0)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class QualityCheck(Base):
    __tablename__ = "quality_checks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    stage: Mapped[str] = mapped_column(String(40), default="")
    item: Mapped[str] = mapped_column(String(160))
    standard: Mapped[str] = mapped_column(Text, default="")  # what to check / tolerance
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | checked | failed
    remarks: Mapped[str] = mapped_column(Text, default="")
    checked_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    checked_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    photo_file_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    sort: Mapped[int] = mapped_column(Integer, default=0)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class SafetyRecord(Base):
    """Safety records and site issues / delays."""
    __tablename__ = "safety_records"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id"), index=True)
    record_date: Mapped[date] = mapped_column(Date, index=True)
    kind: Mapped[str] = mapped_column(String(20), default="toolbox")  # toolbox | ppe | inspection | near_miss | incident | issue | delay
    title: Mapped[str] = mapped_column(String(200))
    details: Mapped[str] = mapped_column(Text, default="")
    severity: Mapped[str] = mapped_column(String(10), default="low")  # low | medium | high
    status: Mapped[str] = mapped_column(String(10), default="open")  # open | closed
    action: Mapped[str] = mapped_column(Text, default="")
    delay_days: Mapped[float] = mapped_column(Float, default=0)
    closed_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ---------------------------------------------------------------- Phase 6: AI assistant
class AIConversation(Base):
    """A chat thread with the assistant. Hidden instead of deleted."""
    __tablename__ = "ai_conversations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    project_id: Mapped[Optional[int]] = mapped_column(ForeignKey("projects.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200), default="New conversation")
    agent: Mapped[str] = mapped_column(String(30), default="general")
    state: Mapped[dict] = mapped_column(JSON, default=dict)  # pending questions, last plan / design id …
    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AIMessage(Base):
    __tablename__ = "ai_messages"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("ai_conversations.id"), index=True)
    role: Mapped[str] = mapped_column(String(12))  # user | assistant
    content: Mapped[str] = mapped_column(Text, default="")
    cards: Mapped[list] = mapped_column(JSON, default=list)  # plan / estimate / calc / vastu / questions …
    sources: Mapped[list] = mapped_column(JSON, default=list)
    tool: Mapped[str] = mapped_column(String(40), default="")
    provider: Mapped[str] = mapped_column(String(120), default="")
    language: Mapped[str] = mapped_column(String(10), default="en")
    attachment_file_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    feedback: Mapped[int] = mapped_column(Integer, default=0)  # 1 helpful, -1 not helpful
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AIIndexedFile(Base):
    """Which project documents were read for Document Q&A (one row per file)."""
    __tablename__ = "ai_indexed_files"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    project_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="indexed")  # indexed | empty | failed
    chunks: Mapped[int] = mapped_column(Integer, default=0)
    pages: Mapped[int] = mapped_column(Integer, default=0)
    embedded: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AIDocChunk(Base):
    """A piece of a project document. The 'embedding' vector(768) column is added by migration 0007 (pgvector)."""
    __tablename__ = "ai_doc_chunks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    file_id: Mapped[int] = mapped_column(Integer, index=True)
    chunk_no: Mapped[int] = mapped_column(Integer, default=0)
    page: Mapped[int] = mapped_column(Integer, default=0)
    text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)



# ---------------------------------------------------------------- Phase 6.6
class TrashLog(Base):
    """Who moved what to the Recycle Bin, and what happened to it (restored / deleted permanently)."""
    __tablename__ = "trash_log"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity: Mapped[str] = mapped_column(String(30), index=True)
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    project_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(String(300), default="")
    state: Mapped[str] = mapped_column(String(12), default="in_bin")  # in_bin | restored | purged
    deleted_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    deleted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    done_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class InviteLink(Base):
    __tablename__ = "invite_links"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    label: Mapped[str] = mapped_column(String(120), default="")
    job_title: Mapped[str] = mapped_column(String(80), default="")
    access: Mapped[dict] = mapped_column(JSON, default=dict)  # {"<project_id>": {"view": true, "site": true, ...}}
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    uses: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BbsSchedule(Base):
    """Bar bending schedule saved for a project."""
    __tablename__ = "bbs_schedules"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, index=True)
    title: Mapped[str] = mapped_column(String(200), default="BBS")
    members: Mapped[list] = mapped_column(JSON, default=list)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    total_kg: Mapped[float] = mapped_column(Float, default=0)
    is_hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class PermitChecklist(Base):
    """Plan approval (building permit) document checklist – one per project."""
    __tablename__ = "permit_checklists"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    project_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    authority: Mapped[str] = mapped_column(String(30), default="dtcp")
    items: Mapped[list] = mapped_column(JSON, default=list)
    fees: Mapped[list] = mapped_column(JSON, default=list)
    application_no: Mapped[str] = mapped_column(String(80), default="")
    approval_no: Mapped[str] = mapped_column(String(80), default="")
    approval_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    approved_file_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AIPhotoCheck(Base):
    """AI look at one site photo (only when the user asks)."""
    __tablename__ = "ai_photo_checks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    file_id: Mapped[int] = mapped_column(Integer, index=True)
    project_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    provider: Mapped[str] = mapped_column(String(120), default="")
    created_by: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
