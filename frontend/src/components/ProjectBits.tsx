import { useEffect, useState, type ReactNode } from "react";
import { CalendarDays, MapPin, MoreVertical } from "lucide-react";
import { api, fmtDate } from "../lib/api";
import type { Project } from "../lib/auth";
import { useI18n } from "../lib/i18n";
import { Field, Modal, toast } from "./ui";

export const INDIAN_STATES = [
  "Tamil Nadu", "Andhra Pradesh", "Arunachal Pradesh", "Assam", "Bihar", "Chhattisgarh", "Goa", "Gujarat", "Haryana",
  "Himachal Pradesh", "Jharkhand", "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Manipur", "Meghalaya",
  "Mizoram", "Nagaland", "Odisha", "Punjab", "Rajasthan", "Sikkim", "Telangana", "Tripura", "Uttar Pradesh",
  "Uttarakhand", "West Bengal", "Andaman and Nicobar Islands", "Chandigarh", "Dadra and Nagar Haveli and Daman and Diu",
  "Delhi", "Jammu and Kashmir", "Ladakh", "Lakshadweep", "Puducherry",
];

export const TN_DISTRICTS = [
  "Ariyalur", "Chengalpattu", "Chennai", "Coimbatore", "Cuddalore", "Dharmapuri", "Dindigul", "Erode", "Kallakurichi",
  "Kancheepuram", "Kanyakumari", "Karur", "Krishnagiri", "Madurai", "Mayiladuthurai", "Nagapattinam", "Namakkal",
  "Nilgiris", "Perambalur", "Pudukkottai", "Ramanathapuram", "Ranipet", "Salem", "Sivaganga", "Tenkasi", "Thanjavur",
  "Theni", "Thoothukudi", "Tiruchirappalli", "Tirunelveli", "Tirupathur", "Tiruppur", "Tiruvallur", "Tiruvannamalai",
  "Tiruvarur", "Vellore", "Viluppuram", "Virudhunagar",
];

export const PROJECT_TYPES: [string, string][] = [
  ["residential", "Residential"], ["villa", "Villa"], ["commercial", "Commercial"], ["industrial", "Industrial"],
  ["warehouse", "Warehouse"], ["road", "Road"], ["infrastructure", "Infrastructure"], ["other", "Other"],
];

export function StatCard({ icon, label, value, sub, tone }: { icon: ReactNode; label: string; value: ReactNode; sub: string; tone: string }) {
  return (
    <div className="card flex items-center gap-3 p-3.5">
      <div className={`flex h-12 w-12 shrink-0 items-center justify-center rounded-xl ${tone}`}>{icon}</div>
      <div className="min-w-0">
        <div className="text-[13px] font-semibold leading-tight text-navy-ink">{label}</div>
        <div className="text-2xl font-extrabold text-navy-ink">{value}</div>
        <div className="truncate text-xs text-slate-500">{sub}</div>
      </div>
    </div>
  );
}

export function healthBadge(p: Project): { text: string; cls: string } {
  if (p.status === "completed") return { text: "Completed", cls: "bg-slate-600" };
  if (p.status === "on_hold") return { text: "On Hold", cls: "bg-amber-500" };
  if (p.health === "delayed") return { text: "Delayed", cls: "bg-orange-500" };
  if (p.progress > 0 && p.progress < 100) return { text: "In Progress", cls: "bg-brand-600" };
  return { text: "On Track", cls: "bg-emerald-600" };
}

export function ProjectCard({ p, selected, onClick, onEdit }: { p: Project; selected?: boolean; onClick?: () => void; onEdit?: () => void }) {
  const { t } = useI18n();
  const b = healthBadge(p);
  const bar = p.status === "completed" || p.progress >= 100 ? "bg-emerald-500" : p.health === "delayed" ? "bg-emerald-500" : "bg-brand-600";
  return (
    <div onClick={onClick} className={`card cursor-pointer overflow-hidden p-2 transition hover:shadow-md ${selected ? "ring-2 ring-brand-600" : ""}`}>
      <div className="relative h-32 overflow-hidden rounded-lg">
        <img src={p.cover_image} alt="" className="h-full w-full object-cover" loading="lazy" />
        <span className={`absolute left-2 top-2 rounded-md px-2 py-0.5 text-[11px] font-bold text-white ${b.cls}`}>{t(b.text)}</span>
        {onEdit && (
          <button onClick={(e) => { e.stopPropagation(); onEdit(); }} className="absolute right-2 top-2 rounded-md bg-white/90 p-1 text-navy-ink" aria-label="Edit">
            <MoreVertical size={16} />
          </button>
        )}
      </div>
      <div className="px-1.5 pb-1 pt-2.5">
        <div className="truncate text-[15px] font-bold text-navy-ink">{p.name}</div>
        <div className="mt-0.5 flex items-center gap-1 truncate text-xs text-slate-500"><MapPin size={13} />{[p.location, p.state === "Tamil Nadu" ? "TN" : p.state].filter(Boolean).join(", ") || "—"}</div>
        <div className="mt-2.5 flex items-center gap-2">
          <div className="h-2 flex-1 rounded-full bg-slate-100"><div className={`h-2 rounded-full ${bar}`} style={{ width: `${Math.min(100, p.progress)}%` }} /></div>
          <span className="text-xs font-bold text-navy-ink">{Math.round(p.progress)}%</span>
        </div>
        <div className="mt-2.5 grid grid-cols-2 gap-1 text-[11px] text-slate-500">
          <div><div className="flex items-center gap-1"><CalendarDays size={12} />{t("Start")}</div><div className="font-semibold text-slate-700">{fmtDate(p.start_date)}</div></div>
          <div><div className="flex items-center gap-1"><CalendarDays size={12} />{t("End")}</div><div className="font-semibold text-slate-700">{fmtDate(p.end_date)}</div></div>
        </div>
      </div>
    </div>
  );
}

export function ProgressRing({ value, size = 120, label }: { value: number; size?: number; label?: string }) {
  const r = (size - 14) / 2, c = 2 * Math.PI * r, v = Math.max(0, Math.min(100, value));
  return (
    <div className="flex flex-col items-center">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#e8edf5" strokeWidth="11" />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#16a34a" strokeWidth="11" strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={c * (1 - v / 100)} transform={`rotate(-90 ${size / 2} ${size / 2})`} />
        <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle" className="fill-navy-ink" fontSize={size / 4.6} fontWeight="800">{Math.round(v)}%</text>
      </svg>
      {label && <div className="mt-1 text-sm font-bold text-navy-ink">{label}</div>}
    </div>
  );
}

type Form = Record<string, any>;
const EMPTY: Form = {
  name: "", project_type: "residential", client_name: "", location: "", district: "", state: "Tamil Nadu",
  plot_width: "", plot_length: "", unit: "ft", facing: "", road_width: "", floors: "G", builtup_area: "",
  structure_type: "rcc_framed", spec_level: "standard", start_date: "", end_date: "", status: "ongoing",
  health: "on_track", progress: 0, notes: "",
};

export function ProjectFormModal({ open, onClose, project, onSaved }: {
  open: boolean; onClose: () => void; project?: Project | null; onSaved: (p: Project) => void;
}) {
  const { t } = useI18n();
  const [f, setF] = useState<Form>(EMPTY);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  useEffect(() => {
    if (!open) return;
    setErr("");
    setF(project ? Object.fromEntries(Object.keys(EMPTY).map((k) => [k, (project as any)[k] ?? ""])) : EMPTY);
  }, [open, project]);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });

  const save = async () => {
    setErr("");
    if (!f.name.trim()) return setErr("Project name is required");
    const num = (v: any) => (v === "" || v === null ? null : Number(v));
    const body: Form = {
      ...f, plot_width: num(f.plot_width), plot_length: num(f.plot_length), road_width: num(f.road_width),
      builtup_area: num(f.builtup_area), start_date: f.start_date || null, end_date: f.end_date || null,
      progress: Number(f.progress) || 0,
    };
    if (!project) delete body.progress;
    setBusy(true);
    try {
      const p = project
        ? await api<Project>(`/api/projects/${project.id}`, { method: "PATCH", body })
        : await api<Project>("/api/projects", { body });
      toast(project ? "Project updated" : `Project ${p.code} created`);
      onSaved(p); onClose();
    } catch (e: any) { setErr(e.message); }
    finally { setBusy(false); }
  };

  const sel = (k: string, opts: [string, string][]) => (
    <select className="input" value={f[k]} onChange={set(k)}>{opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
  );

  return (
    <Modal open={open} onClose={onClose} title={project ? `${t("Edit")} – ${project.code}` : t("New Project")} wide>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Project name *" className="sm:col-span-2"><input className="input" value={f.name} onChange={set("name")} placeholder="30x40 Residential House" /></Field>
        <Field label={t("Type")}>{sel("project_type", PROJECT_TYPES)}</Field>
        <Field label={t("Client")}><input className="input" value={f.client_name} onChange={set("client_name")} /></Field>
        <Field label="State">{sel("state", INDIAN_STATES.map((s) => [s, s]))}</Field>
        <Field label="District">
          {f.state === "Tamil Nadu"
            ? <select className="input" value={f.district} onChange={set("district")}><option value="">— Select —</option>{TN_DISTRICTS.map((d) => <option key={d}>{d}</option>)}</select>
            : <input className="input" value={f.district} onChange={set("district")} />}
        </Field>
        <Field label={`${t("Location")} (city / town)`} className="sm:col-span-2"><input className="input" value={f.location} onChange={set("location")} placeholder="Thanjavur" /></Field>

        <div className="grid grid-cols-3 gap-3 sm:col-span-2">
          <Field label="Plot width"><input className="input" type="number" min="0" step="any" value={f.plot_width} onChange={set("plot_width")} /></Field>
          <Field label="Plot length"><input className="input" type="number" min="0" step="any" value={f.plot_length} onChange={set("plot_length")} /></Field>
          <Field label="Unit">{sel("unit", [["ft", "feet"], ["m", "metres"]])}</Field>
        </div>
        <Field label="Facing">{sel("facing", [["", "Not decided yet"], ["east", "East"], ["west", "West"], ["north", "North"], ["south", "South"], ["north-east", "North-East"], ["north-west", "North-West"], ["south-east", "South-East"], ["south-west", "South-West"]])}</Field>
        <Field label="Abutting road width (m) – for TN setbacks"><input className="input" type="number" min="0" step="any" value={f.road_width} onChange={set("road_width")} /></Field>
        <Field label={t("Floors")}>{sel("floors", [["G", "G"], ["G+1", "G+1"], ["G+2", "G+2"], ["G+3", "G+3"], ["Stilt+1", "Stilt+1"], ["Stilt+2", "Stilt+2"], ["Stilt+3", "Stilt+3"]])}</Field>
        <Field label={`${t("Built-up Area")} (sq ft, optional)`}><input className="input" type="number" min="0" step="any" value={f.builtup_area} onChange={set("builtup_area")} /></Field>
        <Field label="Structure">{sel("structure_type", [["rcc_framed", "RCC framed"], ["load_bearing", "Load bearing"]])}</Field>
        <Field label="Specification">{sel("spec_level", [["basic", "Basic"], ["standard", "Standard"], ["premium", "Premium"]])}</Field>
        <Field label={t("Start Date")}><input className="input" type="date" value={f.start_date || ""} onChange={set("start_date")} /></Field>
        <Field label={t("End Date")}><input className="input" type="date" value={f.end_date || ""} onChange={set("end_date")} /></Field>
        {project && (
          <>
            <Field label={t("Status")}>{sel("status", [["ongoing", "Ongoing"], ["on_hold", "On Hold"], ["completed", "Completed"], ["archived", "Archived (owner)"]])}</Field>
            <Field label="Schedule">{sel("health", [["on_track", "On Track"], ["delayed", "Delayed"]])}</Field>
            <Field label={`${t("Progress")} % (auto from Site in Phase 5)`}><input className="input" type="number" min="0" max="100" value={f.progress} onChange={set("progress")} /></Field>
          </>
        )}
        <Field label="Notes" className="sm:col-span-2"><textarea className="input min-h-[70px]" value={f.notes} onChange={set("notes")} /></Field>
      </div>
      {err && <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{err}</p>}
      <div className="mt-5 flex justify-end gap-2">
        <button className="btn-ghost" onClick={onClose}>{t("Cancel")}</button>
        <button className="btn-primary" onClick={save} disabled={busy}>{busy ? t("Loading...") : t("Save")}</button>
      </div>
    </Modal>
  );
}
