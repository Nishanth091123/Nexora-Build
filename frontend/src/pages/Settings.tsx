import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  Bell, Bot, Building2, Database, Download, FileClock, History, KeyRound, Pencil, Plus, Ruler, Search, Settings as Cog, Shield, ShieldCheck, UserCog, Users, Crown, User as UserIcon, IndianRupee, Trash2,
} from "lucide-react";
import Page from "../components/Page";
import RateLibrary from "../components/RateLibrary";
import InviteLinks from "../components/admin/InviteLinks";
import RecycleBin from "../components/admin/RecycleBin";
import RecoverBackup from "../components/admin/RecoverBackup";
import { PushCard } from "../components/PushAlerts";
import { Avatar, Badge, Card, Empty, Field, Modal, PillTabs, SegTabs, StatusBadge, Toggle, toast } from "../components/ui";
import { INDIAN_STATES } from "../components/ProjectBits";
import { api, downloadFile, fileObjectUrl, fmtBytes, fmtDateTime, setToken } from "../lib/api";
import { useAuth, type User } from "../lib/auth";
import { useI18n } from "../lib/i18n";

type SettingsData = Record<string, Record<string, any>>;

function useSettings() {
  const [s, setS] = useState<SettingsData | null>(null);
  const load = useCallback(() => api<SettingsData>("/api/settings").then(setS).catch((e) => toast(e.message, "err")), []);
  useEffect(() => { load(); }, [load]);
  const save = async (section: string, patch: Record<string, any>) => {
    try {
      const v = await api(`/api/settings/section/${section}`, { method: "PUT", body: patch });
      setS((prev) => (prev ? { ...prev, [section]: v } : prev));
      toast("Saved");
    } catch (e: any) { toast(e.message, "err"); }
  };
  return { s, save, reload: load };
}

// ---------------- Company ----------------
function CompanySection({ isOwner }: { isOwner: boolean }) {
  const { t } = useI18n();
  const [c, setC] = useState<any>(null);
  const [edit, setEdit] = useState(false);
  const [logo, setLogo] = useState<string>("/images/company_building.jpg");
  const input = useRef<HTMLInputElement>(null);
  const load = () => api("/api/settings/company").then((d) => {
    setC(d);
    if (d.logo_url) fileObjectUrl(d.logo_url).then(setLogo).catch(() => {});
  });
  useEffect(() => { load().catch((e) => toast(e.message, "err")); }, []);
  if (!c) return <Card title={t("Company Information")}><Empty text={t("Loading...")} /></Card>;
  const save = async () => {
    try { setC(await api("/api/settings/company", { method: "PUT", body: c })); setEdit(false); toast("Company saved"); }
    catch (e: any) { toast(e.message, "err"); }
  };
  const uploadLogo = async (f: File) => {
    const fd = new FormData(); fd.append("file", f);
    try { const d = await api("/api/settings/company/logo", { form: fd }); setC(d); setLogo(URL.createObjectURL(f)); toast("Logo updated"); }
    catch (e: any) { toast(e.message, "err"); }
  };
  const fields: [string, string][] = [["name", "Company Name"], ["registration_no", "Registration No."], ["address", "Address"],
    ["industry", "Industry"], ["phone", "Phone"], ["email", "Email"], ["website", "Website"]];
  return (
    <Card title={t("Company Information")} icon={<Building2 size={20} />}
      action={isOwner && !edit && <button className="btn-outline btn-sm" onClick={() => setEdit(true)}><Pencil size={14} />{t("Edit")}</button>}>
      <div className="@container"><div className="flex flex-col gap-5 @lg:flex-row">
        <div className="flex shrink-0 flex-col items-center gap-2 @lg:w-40">
          <img src={logo} alt="Company" className="h-32 w-40 rounded-lg border border-line object-cover" />
          {isOwner && <button className="btn-outline btn-sm w-full" onClick={() => input.current?.click()}>Change Logo</button>}
          <span className="text-center text-[11px] text-slate-500">Recommended size: 300 × 300 px</span>
          <input ref={input} type="file" hidden accept=".png,.jpg,.jpeg,.webp" onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadLogo(f); e.target.value = ""; }} />
        </div>
        {edit ? (
          <div className="grid min-w-0 flex-1 gap-3 @2xl:grid-cols-2">
            {fields.map(([k, l]) => (
              <Field key={k} label={l} className={k === "address" ? "@2xl:col-span-2" : ""}>
                {k === "address" ? <textarea className="input" value={c[k] || ""} onChange={(e) => setC({ ...c, [k]: e.target.value })} />
                  : <input className="input" value={c[k] || ""} onChange={(e) => setC({ ...c, [k]: e.target.value })} />}
              </Field>
            ))}
            <div className="flex gap-2 @2xl:col-span-2"><button className="btn-primary" onClick={save}>{t("Save")}</button><button className="btn-ghost" onClick={() => { setEdit(false); load(); }}>{t("Cancel")}</button></div>
          </div>
        ) : (
          <dl className="grid min-w-0 flex-1 gap-x-6 gap-y-3 text-sm @2xl:grid-cols-2">
            {fields.map(([k, l]) => (
              <div key={k} className={`min-w-0 break-words ${k === "address" ? "@2xl:col-span-2" : ""}`}>
                <dt className="text-xs text-slate-500">{l}</dt>
                <dd className={`font-semibold ${k === "email" || k === "website" ? "text-brand-600" : "text-navy-ink"}`}>{c[k] || <span className="font-normal text-slate-400">Not set</span>}</dd>
              </div>
            ))}
          </dl>
        )}
      </div></div>
    </Card>
  );
}

// ---------------- Users ----------------
function UserModal({ open, onClose, user, onSaved }: { open: boolean; onClose: () => void; user: User | null; onSaved: () => void }) {
  const { t } = useI18n();
  const [f, setF] = useState<any>({});
  const [err, setErr] = useState("");
  useEffect(() => {
    setErr("");
    setF(user ? { email: user.email || "", full_name: user.full_name, job_title: user.job_title, phone: user.phone, can_create_projects: user.can_create_projects, new_password: "" }
      : { username: "", email: "", full_name: "", job_title: "", phone: "", password: "", can_create_projects: false });
  }, [open, user]);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const save = async () => {
    setErr("");
    try {
      if (user) {
        const body = { ...f }; if (!body.new_password) delete body.new_password;
        await api(`/api/users/${user.id}`, { method: "PATCH", body });
      } else await api("/api/users", { body: f });
      toast(user ? "User updated" : "User added"); onSaved(); onClose();
    } catch (e: any) { setErr(e.message); }
  };
  return (
    <Modal open={open} onClose={onClose} title={user ? `${t("Edit")} – @${user.username}` : t("Add User")}>
      <div className="grid gap-3 sm:grid-cols-2">
        {!user && <Field label={t("Username")}><input className="input" name="nx_new_username" autoComplete="off" value={f.username || ""} onChange={set("username")} /></Field>}
        <Field label={`${t("Email")} (optional)`}><input className="input" type="email" name="nx_new_email" autoComplete="off" value={f.email || ""} onChange={set("email")} placeholder="not required" /></Field>
        <Field label={t("Full name")}><input className="input" name="nx_new_fullname" autoComplete="off" value={f.full_name || ""} onChange={set("full_name")} /></Field>
        <Field label={t("Job title")}><input className="input" name="nx_new_title" autoComplete="off" value={f.job_title || ""} onChange={set("job_title")} placeholder="Site Engineer" /></Field>
        <Field label={t("Phone")}><input className="input" name="nx_new_phone" autoComplete="off" value={f.phone || ""} onChange={set("phone")} /></Field>
        <Field label={user ? "Reset password (optional)" : t("Password")}><input className="input" type="password" name="nx_new_password" autoComplete="new-password" value={(user ? f.new_password : f.password) || ""} onChange={set(user ? "new_password" : "password")} /></Field>
        {!user?.is_protected && (
          <label className="flex items-center gap-3 sm:col-span-2"><Toggle checked={!!f.can_create_projects} onChange={(v) => setF({ ...f, can_create_projects: v })} /><span className="text-sm">Allow this user to create new projects</span></label>
        )}
      </div>
      {err && <p className="mt-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{err}</p>}
      <div className="mt-5 flex justify-end gap-2"><button className="btn-ghost" onClick={onClose}>{t("Cancel")}</button><button className="btn-primary" onClick={save}>{t("Save")}</button></div>
    </Modal>
  );
}

function UsersSection({ compact }: { compact?: boolean }) {
  const { t } = useI18n();
  const [data, setData] = useState<{ users: User[]; counts: Record<string, number> } | null>(null);
  const [filter, setFilter] = useState("all");
  const [q, setQ] = useState("");
  const [modal, setModal] = useState<{ open: boolean; user: User | null }>({ open: false, user: null });
  const load = useCallback(() => api("/api/users").then(setData).catch((e) => toast(e.message, "err")), []);
  useEffect(() => { load(); }, [load]);
  const setStatus = async (u: User, status: string) => {
    try { await api(`/api/users/${u.id}`, { method: "PATCH", body: { status } }); toast(`${u.username}: ${status === "active" ? "activated" : status}`); load(); }
    catch (e: any) { toast(e.message, "err"); }
  };
  const rows = (data?.users || []).filter((u) => (filter === "all" || u.status === filter) &&
    (!q || `${u.full_name} ${u.username} ${u.email || ""} ${u.job_title}`.toLowerCase().includes(q.toLowerCase())));
  const c = data?.counts || {};
  return (
    <Card title={t("Users & Team Management")} icon={<Users size={20} />}>
      <div className="mb-3 flex gap-2">
        <div className="relative flex-1"><Search size={16} className="absolute left-3 top-2.5 text-slate-400" /><input className="input pl-9" placeholder="Search users..." value={q} onChange={(e) => setQ(e.target.value)} /></div>
        <button className="btn-primary" onClick={() => setModal({ open: true, user: null })}><Plus size={16} />{t("Add User")}</button>
      </div>
      <div className="mb-3"><SegTabs value={filter} onChange={setFilter} tabs={[
        { id: "all", label: `All Users (${c.all ?? 0})` }, { id: "active", label: `${t("Active")} (${c.active ?? 0})` },
        { id: "pending", label: `${t("Pending")} (${c.pending ?? 0})` }, { id: "deactivated", label: `${t("Deactivated")} (${c.deactivated ?? 0})` }]} /></div>
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full min-w-[560px]">
          <thead><tr><th className="table-th">{t("Name")}</th><th className="table-th">{t("Role")}</th>{!compact && <th className="table-th">{t("Email")}</th>}<th className="table-th">{t("Status")}</th><th className="table-th text-right">{t("Actions")}</th></tr></thead>
          <tbody>
            {rows.map((u) => (
              <tr key={u.id}>
                <td className="table-td"><div className="flex items-center gap-2"><Avatar name={u.full_name || u.username} size={30} /><div><div className="font-semibold text-navy-ink">{u.full_name || u.username}</div><div className="text-[11px] text-slate-400">@{u.username}</div></div>{u.role === "owner" && <Crown size={14} className="text-amber-500" />}</div></td>
                <td className="table-td">{u.job_title || "—"}</td>
                {!compact && <td className="table-td">{u.email || "—"}</td>}
                <td className="table-td"><StatusBadge status={u.status} /></td>
                <td className="table-td">
                  <div className="flex justify-end gap-1">
                    {u.status === "pending" && <button className="btn-primary btn-sm" onClick={() => setStatus(u, "active")}>{t("Approve")}</button>}
                    {!u.is_protected && u.status === "active" && <button className="btn-ghost btn-sm text-red-600" onClick={() => setStatus(u, "deactivated")}>{t("Deactivate")}</button>}
                    {u.status === "deactivated" && <button className="btn-outline btn-sm" onClick={() => setStatus(u, "active")}>{t("Activate")}</button>}
                    <button className="btn-ghost btn-sm" onClick={() => setModal({ open: true, user: u })} aria-label="Edit"><Pencil size={14} /></button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && <div className="p-4"><Empty text={t("No data yet")} /></div>}
      </div>
      <p className="mt-2 text-xs text-slate-500">Users are never deleted – deactivate them to remove access. The owner account is permanent.</p>
      <UserModal open={modal.open} user={modal.user} onClose={() => setModal({ open: false, user: null })} onSaved={load} />
    </Card>
  );
}

function RolesSection({ counts }: { counts?: Record<string, number> }) {
  return (
    <Card title="Roles & Permissions" icon={<ShieldCheck size={20} />}>
      <ul className="space-y-2">
        <li className="flex items-center gap-3 rounded-lg border border-line p-3"><div className="flex h-10 w-10 items-center justify-center rounded-lg bg-amber-50 text-amber-500"><Crown size={22} /></div><div className="flex-1"><div className="text-sm font-bold text-amber-700">Owner</div><div className="text-xs text-slate-500">Full access to everything. Permanent – cannot be deleted or deactivated.</div></div><Badge color="blue">1 User</Badge></li>
        <li className="flex items-center gap-3 rounded-lg border border-line p-3"><div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 text-brand-600"><UserIcon size={22} /></div><div className="flex-1"><div className="text-sm font-bold text-brand-700">User</div><div className="text-xs text-slate-500">Sees only the projects and modules the owner allows (Project Access).</div></div><Badge color="blue">{Math.max(0, (counts?.all ?? 1) - 1)} Users</Badge></li>
      </ul>
    </Card>
  );
}

// ---------------- Project access ----------------
const MOD_LABEL: Record<string, string> = { view: "View", edit: "Edit/Docs", design: "Design", estimate: "Estimate", site: "Site", vastu: "Vastu", ai: "AI" };

function AccessSection() {
  const { t } = useI18n();
  const [m, setM] = useState<any>(null);
  const [uid, setUid] = useState<number | null>(null);
  const load = useCallback(() => api("/api/users/access/matrix").then((d) => { setM(d); setUid((u) => u ?? d.users[0]?.id ?? null); }).catch((e) => toast(e.message, "err")), []);
  useEffect(() => { load(); }, [load]);
  if (!m) return <Card title={t("Project Access Control")}><Empty text={t("Loading...")} /></Card>;
  const toggle = async (pid: number, mod: string) => {
    const cur = m.access[`${uid}:${pid}`];
    const next: any = { ...cur, [mod]: !cur[mod] };
    if (mod === "view" && !next.view) for (const k of m.modules) next[k] = false;
    try {
      const r = await api("/api/users/access", { method: "PUT", body: { user_id: uid, project_id: pid, ...Object.fromEntries(m.modules.map((k: string) => [k, !!next[k]])) } });
      setM({ ...m, access: { ...m.access, [`${uid}:${pid}`]: r } });
    } catch (e: any) { toast(e.message, "err"); }
  };
  return (
    <Card title={t("Project Access Control")} icon={<UserCog size={20} />}>
      {!m.users.length ? <Empty text="No users yet. Add users first (Users & Teams)." /> : !m.projects.length ? <Empty text="No projects yet." /> : (
        <>
          <Field label="User" className="mb-3 max-w-xs">
            <select className="input" value={uid ?? ""} onChange={(e) => setUid(Number(e.target.value))}>
              {m.users.map((u: any) => <option key={u.id} value={u.id}>{u.full_name} (@{u.username}){u.status !== "active" ? ` – ${u.status}` : ""}</option>)}
            </select>
          </Field>
          <div className="overflow-x-auto rounded-lg border border-line">
            <table className="w-full min-w-[620px]">
              <thead><tr><th className="table-th">Project Name</th>{m.modules.map((k: string) => <th key={k} className="table-th text-center">{MOD_LABEL[k]}</th>)}</tr></thead>
              <tbody>
                {m.projects.map((p: any) => (
                  <tr key={p.id}>
                    <td className="table-td"><div className="font-semibold text-navy-ink">{p.name}</div><div className="text-[11px] text-slate-400">{p.code}</div></td>
                    {m.modules.map((k: string) => (
                      <td key={k} className="table-td text-center">
                        <input type="checkbox" className="h-4 w-4 accent-brand-600" checked={!!m.access[`${uid}:${p.id}`]?.[k]} onChange={() => toggle(p.id, k)} />
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-xs text-slate-500">Changes save instantly. Any module automatically gives View access.</p>
        </>
      )}
    </Card>
  );
}

// ---------------- Units ----------------
function UnitsSection({ s, save }: { s: SettingsData; save: (k: string, v: any) => void }) {
  const u = s.units;
  const radio = (key: string, val: string, label: string, hint?: string) => (
    <label className="flex cursor-pointer items-start gap-2 text-sm"><input type="radio" className="mt-1 accent-brand-600" checked={u[key] === val} onChange={() => save("units", { [key]: val })} /><span>{label}{hint && <span className="block text-xs text-slate-500">{hint}</span>}</span></label>
  );
  return (
    <Card title="Units & Measurement Preferences" icon={<Ruler size={20} />}>
      <div className="grid gap-4 text-sm sm:grid-cols-[180px_1fr]">
        <div className="text-slate-600">Default Unit System</div><div className="space-y-1.5">{radio("unit_system", "metric", "Metric (m, m², m³, kg)")}{radio("unit_system", "imperial", "Imperial (ft, ft², ft³, kg)")}</div>
        <div className="text-slate-600">Display Format</div>
        <select className="input" value={u.decimal_places} onChange={(e) => save("units", { decimal_places: Number(e.target.value) })}>{[0, 1, 2, 3].map((d) => <option key={d} value={d}>{d} decimals ({(0).toFixed(d)})</option>)}</select>
        <div className="text-slate-600">Default Currency</div><select className="input" value={u.currency} disabled><option value="INR">INR (₹)</option></select>
        <div className="text-slate-600">Default Material Rates</div>
        <select className="input" value={u.rate_region} onChange={(e) => save("units", { rate_region: e.target.value })}>{INDIAN_STATES.map((st) => <option key={st}>{st}</option>)}</select>
        <div className="text-slate-600">Measurement Input</div>
        <div className="space-y-2">{radio("measurement_input", "preserve", "Preserve Input Units", "Keep user input units and show conversion")}{radio("measurement_input", "convert_to_metric", "Auto Convert to Metric", "Automatically convert all inputs to metric")}</div>
      </div>
    </Card>
  );
}

function RatesSection() {
  return (
    <Card title="Material & Labour Rate Settings" icon={<IndianRupee size={20} />}>
      <RateLibrary />
    </Card>
  );
}

// ---------------- AI / Notifications ----------------
function AISection({ s, save, keys }: { s: SettingsData; save: (k: string, v: any) => void; keys?: Record<string, boolean> }) {
  const a = s.ai;
  const tog = (k: string, l: string) => <div className="flex items-center justify-between py-1.5 text-sm"><span>{l}</span><Toggle checked={!!a[k]} onChange={(v) => save("ai", { [k]: v })} /></div>;
  return (
    <Card title="AI Preferences" icon={<Bot size={20} />}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Default AI Language"><select className="input" value={a.language} onChange={(e) => save("ai", { language: e.target.value })}><option value="ta_en">Tamil + English (Mixed)</option><option value="en">English</option><option value="ta">Tamil</option></select></Field>
        <Field label="AI Response Style"><select className="input" value={a.response_style} onChange={(e) => save("ai", { response_style: e.target.value })}><option value="detailed">Detailed with Examples</option><option value="short">Short & Direct</option></select></Field>
      </div>
      <div className="mt-3 divide-y divide-line">
        {tog("show_sources", "Show Sources & References")}{tog("show_calculation_steps", "Include Calculation Steps")}
        {tog("show_assumptions", "Use Assumptions (always shown)")}{tog("use_project_context", "Use Project Context")}{tog("voice_input", "Enable Voice Input (Tamil / English / Tanglish)")}
      </div>
      {keys && <div className="mt-3 flex flex-wrap gap-2 text-xs">LLM keys: {Object.entries(keys).map(([k, v]) => <Badge key={k} color={v ? "green" : "red"}>{k} {v ? "✓" : "missing"}</Badge>)}</div>}
      <p className="mt-2 text-xs text-slate-500">Fallback order: Gemini → Groq → OpenRouter. The assistant itself arrives in Phase 6.</p>
    </Card>
  );
}

function NotificationsSection({ s, save }: { s: SettingsData; save: (k: string, v: any) => void }) {
  const n = s.notifications;
  const items: [string, string][] = [["project_updates", "Project Updates"], ["task_assignments", "Task Assignments"], ["drawing_approvals", "Drawing Approvals"],
    ["estimate_revisions", "Estimate Revisions"], ["site_progress", "Site Progress Updates"], ["ai_suggestions", "AI Suggestions"], ["email_notifications", "Email Notifications"]];
  return (
    <div className="space-y-4">
      <PushCard />
      <Card title="Notification Settings" icon={<Bell size={20} />}>
        <div className="divide-y divide-line">{items.map(([k, l]) => <div key={k} className="flex items-center justify-between py-2 text-sm"><span>{l}</span><Toggle checked={!!n[k]} onChange={(v) => save("notifications", { [k]: v })} /></div>)}</div>
      </Card>
    </div>
  );
}

// ---------------- Security ----------------
function SecuritySection({ s, save, isOwner }: { s: SettingsData | null; save: (k: string, v: any) => void; isOwner: boolean }) {
  const { t } = useI18n();
  const [pw, setPw] = useState({ current_password: "", new_password: "", confirm: "" });
  const change = async () => {
    if (pw.new_password !== pw.confirm) return toast("New passwords do not match", "err");
    try {
      const r = await api<{ token: string }>("/api/auth/change-password", { body: { current_password: pw.current_password, new_password: pw.new_password } });
      setToken(r.token); setPw({ current_password: "", new_password: "", confirm: "" }); toast("Password changed");
    } catch (e: any) { toast(e.message, "err"); }
  };
  return (
    <Card title="Security & Access" icon={<Shield size={20} />}>
      <div className="space-y-3 text-sm">
        <div className="flex items-center justify-between"><span className="flex items-center gap-2"><KeyRound size={16} />Login Authentication</span><span className="text-slate-500">Username/Email + Password</span></div>
        {isOwner && s && (
          <>
            <div className="flex items-center justify-between gap-3"><span>Session Timeout</span>
              <select className="input w-40" value={s.security.session_timeout_minutes} onChange={(e) => save("security", { session_timeout_minutes: Number(e.target.value) })}>
                {[[30, "30 Minutes"], [60, "1 Hour"], [240, "4 Hours"], [480, "8 Hours"], [1440, "1 Day"], [10080, "7 Days"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select></div>
            <div className="flex items-center justify-between"><span>Password Policy</span><span className="text-slate-500">Min 8 characters, letters + numbers</span></div>
            <div className="flex items-center justify-between"><span>Allow new users to register (owner approves)</span><Toggle checked={!!s.general.allow_self_registration} onChange={(v) => save("general", { allow_self_registration: v })} /></div>
            <div className="flex items-center justify-between"><span>Login Activity Tracking</span><Badge color="green">On (Audit Logs)</Badge></div>
            <div className="flex items-center justify-between"><span>Data Protection</span><Badge color="green">Delete-protected database</Badge></div>
          </>
        )}
        <div className="mt-2 rounded-lg border border-line p-3">
          <div className="mb-2 font-semibold text-navy-ink">{t("Change Password")}</div>
          <div className="grid gap-2 sm:grid-cols-3">
            <input className="input" type="password" placeholder="Current password" value={pw.current_password} onChange={(e) => setPw({ ...pw, current_password: e.target.value })} />
            <input className="input" type="password" placeholder="New password" value={pw.new_password} onChange={(e) => setPw({ ...pw, new_password: e.target.value })} />
            <input className="input" type="password" placeholder="Confirm new" value={pw.confirm} onChange={(e) => setPw({ ...pw, confirm: e.target.value })} />
          </div>
          <button className="btn-primary btn-sm mt-2" onClick={change} disabled={!pw.current_password || !pw.new_password}>{t("Change Password")}</button>
        </div>
      </div>
    </Card>
  );
}

// ---------------- Backups ----------------
function BackupsSection({ s, save }: { s: SettingsData; save: (k: string, v: any) => void }) {
  const { t } = useI18n();
  const [d, setD] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [rec, setRec] = useState<any>(null);
  const load = useCallback(() => api("/api/admin/backups").then(setD).catch((e) => toast(e.message, "err")), []);
  useEffect(() => { load(); }, [load]);
  const now = async () => { setBusy(true); try {
      const r = await api<any>("/api/admin/backups", { method: "POST" }); toast(r.message || "Backup started");
      [5000, 15000, 40000, 90000].forEach((ms) => setTimeout(load, ms));
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); } };
  const b = s.backups;
  return (
    <Card title="Backups & Data Management" icon={<Database size={20} />} action={<button className="btn-outline btn-sm" onClick={now} disabled={busy}>{busy ? t("Loading...") : t("Backup Now")}</button>}>
      <div className="grid gap-3 text-sm sm:grid-cols-2">
        <div className="flex items-center justify-between rounded-lg border border-line p-3"><span>Automatic Backup</span><Toggle checked={!!b.automatic} onChange={(v) => save("backups", { automatic: v })} /></div>
        <div className="flex items-center justify-between gap-2 rounded-lg border border-line p-3"><span>Frequency</span>
          <select className="input w-32" value={b.frequency_hours} onChange={(e) => save("backups", { frequency_hours: Number(e.target.value) })}><option value={6}>6 hours</option><option value={12}>12 hours</option><option value={24}>Daily</option><option value={168}>Weekly</option></select></div>
        <div className="rounded-lg border border-line p-3"><div className="text-xs text-slate-500">Storage</div><div className="font-semibold text-navy-ink">{d ? `${d.storage_backend === "r2" ? "Cloudflare R2" : d.storage_backend === "hf" ? "Hugging Face (private)" : "Local folder"} · files ${fmtBytes(d.files_bytes)} · backups ${fmtBytes(d.backups_bytes)}` : "…"}</div></div>
        <div className="rounded-lg border border-line p-3"><div className="text-xs text-slate-500">Last Backup</div><div className="font-semibold text-navy-ink">{d?.backups[0] ? fmtDateTime(d.backups[0].created_at) : "Not yet"}</div></div>
      </div>
      <div className="mt-3 max-h-56 overflow-y-auto rounded-lg border border-line">
        {!d?.backups.length ? <div className="p-3"><Empty text="No backups yet – the first automatic backup runs shortly after the server starts." /></div> : (
          <table className="w-full"><tbody>{d.backups.map((x: any) => (
            <tr key={x.id}><td className="table-td">{fmtDateTime(x.created_at)}</td><td className="table-td"><Badge color={x.kind === "manual" ? "blue" : "gray"}>{x.kind}</Badge></td><td className="table-td">{fmtBytes(x.size_bytes)}</td>
              <td className="table-td whitespace-nowrap text-right"><button className="btn-ghost btn-sm" title="Bring back deleted items from this backup" onClick={() => setRec(x)}><History size={14} />Recover</button>
                <button className="btn-ghost btn-sm" onClick={() => downloadFile(`/api/admin/backups/${x.id}/download`, x.file).catch((e) => toast(e.message, "err"))}><Download size={14} />{t("Download")}</button></td></tr>
          ))}</tbody></table>
        )}
      </div>
      <p className="mt-2 text-xs text-slate-500">Each backup is a complete copy of the database (.json.gz). <b>Recover</b> brings back items that were deleted permanently (a “predelete” backup is taken before every permanent delete).
        To rebuild a whole new database from a file, see docs/PHASE_7_GUIDE.md (restore_backup.py). Neon also keeps its own point-in-time history.</p>
      <RecoverBackup backup={rec} onClose={() => setRec(null)} />
    </Card>
  );
}

// ---------------- Audit ----------------
function AuditSection({ compact }: { compact?: boolean }) {
  const { t } = useI18n();
  const [d, setD] = useState<any>(null);
  const [page, setPage] = useState(1);
  const [q, setQ] = useState("");
  useEffect(() => {
    const h = setTimeout(() => api(`/api/admin/audit?page=${page}&per_page=${compact ? 6 : 25}&q=${encodeURIComponent(q)}`).then(setD).catch((e) => toast(e.message, "err")), 250);
    return () => clearTimeout(h);
  }, [page, q, compact]);
  const color = (a: string) => (["approved", "created", "added", "login"].includes(a) ? "green" : a === "deactivated" || a === "hidden" ? "red" : "blue");
  return (
    <Card title="Activity Logs" icon={<FileClock size={20} />}>
      {!compact && <div className="relative mb-3"><Search size={16} className="absolute left-3 top-2.5 text-slate-400" /><input className="input pl-9" placeholder="Search user, action, details..." value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} /></div>}
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full min-w-[520px]">
          <thead><tr><th className="table-th">Date & Time</th><th className="table-th">User</th><th className="table-th">Action</th><th className="table-th">Details</th></tr></thead>
          <tbody>{d?.items.map((a: any) => (
            <tr key={a.id}><td className="table-td whitespace-nowrap">{fmtDateTime(a.created_at)}</td><td className="table-td">{a.username}</td>
              <td className="table-td"><Badge color={color(a.action)}>{a.action.replace("_", " ")}</Badge></td><td className="table-td">{a.entity}{a.details ? ` – ${a.details}` : ""}</td></tr>
          ))}</tbody>
        </table>
      </div>
      {!compact && d && d.total > d.per_page && (
        <div className="mt-3 flex items-center justify-end gap-2 text-sm">
          <button className="btn-ghost btn-sm" disabled={page <= 1} onClick={() => setPage(page - 1)}>‹ Prev</button>
          <span>{page} / {Math.ceil(d.total / d.per_page)}</span>
          <button className="btn-ghost btn-sm" disabled={page * d.per_page >= d.total} onClick={() => setPage(page + 1)}>Next ›</button>
        </div>
      )}
      {d && !d.items.length && <div className="mt-2"><Empty text={t("No data yet")} /></div>}
    </Card>
  );
}

// ---------------- Profile (all users) ----------------
function ProfileSection() {
  const { user, refreshUser } = useAuth();
  const { lang, setLang, t } = useI18n();
  const [f, setF] = useState({ full_name: user?.full_name || "", job_title: user?.job_title || "", phone: user?.phone || "" });
  const save = async () => {
    try { await api("/api/auth/me", { method: "PATCH", body: { ...f, language: lang } }); await refreshUser(); toast("Profile saved"); }
    catch (e: any) { toast(e.message, "err"); }
  };
  return (
    <Card title="My Profile" icon={<UserIcon size={20} />}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label={t("Full name")}><input className="input" value={f.full_name} onChange={(e) => setF({ ...f, full_name: e.target.value })} /></Field>
        <Field label={t("Job title")}><input className="input" value={f.job_title} onChange={(e) => setF({ ...f, job_title: e.target.value })} /></Field>
        <Field label={t("Phone")}><input className="input" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></Field>
        <Field label={t("Language")}><select className="input" value={lang} onChange={(e) => setLang(e.target.value as any)}><option value="en">English</option><option value="ta">தமிழ்</option></select></Field>
      </div>
      <button className="btn-primary mt-3" onClick={save}>{t("Save")}</button>
    </Card>
  );
}

// ---------------- Page ----------------
export default function Settings() {
  const { t } = useI18n();
  const { user } = useAuth();
  const isOwner = user?.role === "owner";
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") || (isOwner ? "general" : "security");
  const setTab = (v: string) => setParams({ tab: v });
  const { s, save } = useSettings();
  const [sys, setSys] = useState<any>(null);
  const [userCounts, setUserCounts] = useState<Record<string, number>>();
  useEffect(() => {
    if (!isOwner) return;
    api("/api/admin/system").then(setSys).catch(() => {});
    api("/api/users").then((d) => setUserCounts(d.counts)).catch(() => {});
  }, [isOwner]);

  const ownerTabs = [
    { id: "general", label: t("General"), icon: <Cog size={18} /> }, { id: "company", label: t("Company"), icon: <Building2 size={18} /> },
    { id: "users", label: t("Users & Teams"), icon: <Users size={18} /> }, { id: "access", label: t("Project Access"), icon: <UserCog size={18} /> },
    { id: "units", label: t("Units & Rates"), icon: <Ruler size={18} /> }, { id: "ai", label: t("AI Preferences"), icon: <Bot size={18} /> },
    { id: "notifications", label: t("Notifications"), icon: <Bell size={18} /> }, { id: "security", label: t("Security"), icon: <Shield size={18} /> },
    { id: "backups", label: t("Backups"), icon: <Database size={18} /> }, { id: "audit", label: t("Audit Logs"), icon: <FileClock size={18} /> },
    { id: "bin", label: "Recycle Bin", icon: <Trash2 size={18} /> },
  ];
  const userTabs = [{ id: "security", label: t("Security"), icon: <Shield size={18} /> }];

  return (
    <Page title={t("Settings & Administration")} subtitle={t("Manage your company, users, permissions, preferences and security")}>
      <PillTabs tabs={isOwner ? ownerTabs : userTabs} value={tab} onChange={setTab} />
      {!isOwner && <div className="grid gap-4 lg:grid-cols-2"><ProfileSection /><SecuritySection s={s} save={save} isOwner={false} /></div>}
      {isOwner && s && (
        <>
          {tab === "general" && (
            <div className="space-y-4">
              <div className="grid gap-4 xl:grid-cols-[1fr_1.15fr_0.95fr]"><CompanySection isOwner /><UsersSection compact /><RolesSection counts={userCounts} /></div>
              <div className="grid gap-4 xl:grid-cols-3"><AccessSection /><UnitsSection s={s} save={save} /><RatesSection /></div>
              <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-4"><AISection s={s} save={save} keys={sys?.llm_keys} /><NotificationsSection s={s} save={save} /><SecuritySection s={s} save={save} isOwner /><BackupsSection s={s} save={save} /></div>
              <AuditSection compact />
            </div>
          )}
          {tab === "company" && <div className="grid gap-4 lg:grid-cols-2"><CompanySection isOwner /><ProfileSection /></div>}
          {tab === "users" && <div className="grid gap-4 xl:grid-cols-[2fr_1fr]"><div className="min-w-0 space-y-4"><UsersSection /><InviteLinks /></div><RolesSection counts={userCounts} /></div>}
          {tab === "access" && <AccessSection />}
          {tab === "units" && <div className="grid gap-4 lg:grid-cols-2"><UnitsSection s={s} save={save} /><RatesSection /></div>}
          {tab === "ai" && <AISection s={s} save={save} keys={sys?.llm_keys} />}
          {tab === "notifications" && <NotificationsSection s={s} save={save} />}
          {tab === "security" && <div className="grid gap-4 lg:grid-cols-2"><SecuritySection s={s} save={save} isOwner /><Card title="System" icon={<Database size={20} />}>
            {sys ? <dl className="grid grid-cols-2 gap-2 text-sm">{[["App", `${sys.app} ${sys.version}`], ["Database", sys.database], ["Storage", sys.storage_backend], ...Object.entries(sys.counts).map(([k, v]) => [k, String(v)])].map(([k, v]) => <div key={k}><dt className="text-xs capitalize text-slate-500">{k.replace("_", " ")}</dt><dd className="font-semibold text-navy-ink">{v}</dd></div>)}</dl> : <Empty text={t("Loading...")} />}
          </Card></div>}
          {tab === "backups" && <BackupsSection s={s} save={save} />}
          {tab === "audit" && <AuditSection />}
          {tab === "bin" && <RecycleBin />}
        </>
      )}
    </Page>
  );
}
