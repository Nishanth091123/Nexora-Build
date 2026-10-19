import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import OwnerDelete from "../components/OwnerDelete";
import PermitChecklist from "../components/PermitChecklist";
import {
  Activity, BadgeCheck, CalendarRange, CheckCircle2, ClipboardList, Clock, FileText, Flag, FolderKanban,
  Image as ImageIcon, LayoutDashboard, ListChecks, MapPin, Pencil, Plus, Search, Settings as SettingsIcon,
  Target, UploadCloud, Users,
} from "lucide-react";
import Page from "../components/Page";
import { Avatar, Badge, Card, Empty, PhaseNote, PillTabs, SegTabs, toast } from "../components/ui";
import { ProgressRing, ProjectCard, ProjectFormModal, StatCard } from "../components/ProjectBits";
import { api, downloadFile, fmtBytes, fmtDate, timeAgo } from "../lib/api";
import { useAuth, type Project } from "../lib/auth";
import { ApprovalsPanel, GanttPanel, MilestoneList, ScheduleEditor, StageProgress, TasksPanel, useSchedule } from "../components/pm/PmPanels";
import { useI18n } from "../lib/i18n";

type Detail = {
  project: Project;
  team: { id: number; full_name: string; job_title: string; project_role: string }[];
  document_counts: Record<string, number>;
  activity: { id: number; username: string; action: string; entity: string; details: string; created_at: string }[];
};
type FileItem = { id: number; name: string; category: string; size_bytes: number; version: number; created_at: string; url: string; content_type: string };

const CATS: [string, string][] = [["drawing", "Drawings"], ["report", "Reports"], ["photo", "Photos"], ["contract", "Contracts"], ["other", "Others"]];
const cap = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s);
const ROLE_COLOR: Record<string, string> = { owner: "blue", editor: "green", viewer: "amber" };

export default function Projects() {
  const { t } = useI18n();
  const nav = useNavigate();
  const { user, currentProject, setCurrentProjectId, reloadProjects } = useAuth();
  const [params] = useSearchParams();
  const [tab, setTab] = useState(params.get("tab") || "dashboard");
  const [filter, setFilter] = useState("all");
  const [q, setQ] = useState("");
  const [sort, setSort] = useState("updated");
  const [list, setList] = useState<Project[]>([]);
  const [counts, setCounts] = useState<Record<string, number>>({});
  const [teamTotal, setTeamTotal] = useState(0);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [files, setFiles] = useState<FileItem[]>([]);
  const [cat, setCat] = useState("drawing");
  const [form, setForm] = useState<{ open: boolean; project: Project | null }>({ open: false, project: null });
  const [subTab, setSubTab] = useState("progress");
  const fileInput = useRef<HTMLInputElement>(null);

  const loadList = useCallback(async () => {
    const r = await api<{ projects: Project[]; counts: Record<string, number>; team_members: number }>(
      `/api/projects?status=${filter}&q=${encodeURIComponent(q)}&sort=${sort}`);
    setList(r.projects); setCounts(r.counts); setTeamTotal(r.team_members);
  }, [filter, q, sort]);

  const loadDetail = useCallback(async () => {
    if (!currentProject) { setDetail(null); setFiles([]); return; }
    const [d, f] = await Promise.all([
      api<Detail>(`/api/projects/${currentProject.id}`),
      api<FileItem[]>(`/api/files/project/${currentProject.id}`),
    ]);
    setDetail(d); setFiles(f);
  }, [currentProject?.id]);

  useEffect(() => { const h = setTimeout(() => loadList().catch((e) => toast(e.message, "err")), 250); return () => clearTimeout(h); }, [loadList]);
  useEffect(() => { loadDetail().catch((e) => toast(e.message, "err")); }, [loadDetail]);

  const onSaved = async (p: Project) => { await reloadProjects(); await loadList(); setCurrentProjectId(p.id); await loadDetail(); };
  const canCreate = user?.role === "owner" || user?.can_create_projects;
  const p = detail?.project;
  const canEdit = !!p?.permissions?.edit;
  const canWrite = !!(p?.permissions?.edit || p?.permissions?.site);
  const { sch } = useSchedule(p?.id);
  const schKey = sch?.stages.length ?? 0;

  const upload = async (file: File) => {
    if (!p) return;
    const fd = new FormData(); fd.append("category", cat); fd.append("file", file);
    try { await api(`/api/files/project/${p.id}`, { form: fd }); toast(`${file.name} uploaded`); await loadDetail(); }
    catch (e: any) { toast(e.message, "err"); }
  };

  const catFiles = useMemo(() => files.filter((f) => f.category === cat), [files, cat]);

  const tabs = [
    { id: "dashboard", label: t("Project Dashboard"), icon: <LayoutDashboard size={18} /> },
    { id: "mine", label: t("My Projects"), icon: <FolderKanban size={18} /> },
    { id: "team", label: t("Team & Permissions"), icon: <Users size={18} /> },
    { id: "docs", label: t("Documents"), icon: <FileText size={18} /> },
    { id: "tasks", label: t("Tasks"), icon: <ListChecks size={18} /> },
    { id: "milestones", label: t("Milestones"), icon: <Flag size={18} /> },
    { id: "approvals", label: t("Approvals"), icon: <BadgeCheck size={18} /> },
    { id: "permit", label: "Plan Approval", icon: <ClipboardList size={18} /> },
    { id: "activity", label: t("Activity Logs"), icon: <Activity size={18} /> },
    { id: "settings", label: t("Settings"), icon: <SettingsIcon size={18} /> },
  ];

  // ---------- reusable blocks ----------
  const projectsCard = (
    <Card title={t("My Projects")} icon={<ClipboardList size={20} />}
      action={canCreate && <button className="btn-primary btn-sm" onClick={() => setForm({ open: true, project: null })}><Plus size={16} />{t("Create Project")}</button>}>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <SegTabs value={filter} onChange={setFilter} tabs={[
          { id: "all", label: `${t("All")} (${counts.all ?? 0})` }, { id: "ongoing", label: `${t("Ongoing")} (${counts.ongoing ?? 0})` },
          { id: "completed", label: `${t("Completed")} (${counts.completed ?? 0})` }, { id: "on_hold", label: `${t("On Hold")} (${counts.on_hold ?? 0})` }]} />
        <div className="relative min-w-[180px] flex-1">
          <Search size={16} className="absolute left-3 top-2.5 text-slate-400" />
          <input className="input pl-9" placeholder={t("Search projects...")} value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <select className="input w-auto" value={sort} onChange={(e) => setSort(e.target.value)}>
          <option value="updated">Sort by: Last Updated</option><option value="name">Sort by: Name</option>
          <option value="start">Sort by: Start Date</option><option value="created">Sort by: Newest</option>
        </select>
      </div>
      {list.length === 0 ? (
        <Empty icon={<FolderKanban className="text-slate-400" />} text={counts.all ? "No projects match this filter." : "No projects yet. Create your first project."}>
          {canCreate && !counts.all && <button className="btn-primary btn-sm mt-1" onClick={() => setForm({ open: true, project: null })}><Plus size={16} />{t("Create Project")}</button>}
        </Empty>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-5">
          {list.map((x) => (
            <ProjectCard key={x.id} p={x} selected={x.id === currentProject?.id} onClick={() => setCurrentProjectId(x.id)}
              onEdit={x.permissions?.edit ? () => setForm({ open: true, project: x }) : undefined} />
          ))}
        </div>
      )}
    </Card>
  );

  const detailsCard = p && (
    <Card title={t("Project Details")} icon={<FileText size={20} />}
      action={<div className="flex items-center gap-1">
        {canEdit && <button className="btn-outline btn-sm" onClick={() => setForm({ open: true, project: p })}><Pencil size={14} />{t("Edit")}</button>}
        <OwnerDelete entity="project" id={p.id} title={`${p.code} · ${p.name}`} onDone={async () => { setCurrentProjectId(null); await reloadProjects(); await loadList(); }} />
      </div>}>
      <div className="flex gap-3">
        <img src={p.cover_image} alt="" className="h-20 w-24 shrink-0 rounded-lg object-cover" />
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="text-base font-bold text-navy-ink">{p.name}</div>
            <Badge color={p.health === "delayed" ? "red" : "green"}>{t(p.health === "delayed" ? "Delayed" : "On Track")}</Badge>
          </div>
          <div className="mt-1 flex items-center gap-1 text-xs text-slate-500"><MapPin size={13} />{[p.location, p.district, p.state].filter(Boolean).join(", ")}</div>
          <div className="mt-1 text-xs text-slate-400">{p.code}</div>
        </div>
      </div>
      <div className="mt-4 grid grid-cols-3 overflow-hidden rounded-lg border border-line text-xs">
        {[[t("Client"), p.client_name || "—"], [t("Type"), cap(p.project_type)], [t("Built-up Area"), p.builtup_area ? `${p.builtup_area.toLocaleString("en-IN")} sq ft` : "—"],
          [t("Floors"), p.floors], [t("Start Date"), fmtDate(p.start_date)], [t("End Date"), fmtDate(p.end_date)],
          ["Plot", p.plot_width && p.plot_length ? `${p.plot_width} × ${p.plot_length} ${p.unit}` : "—"], ["Facing", p.facing ? cap(p.facing) : "Not given"],
          ["Spec", cap(p.spec_level)]].map(([k, v], i) => (
          <div key={i} className="border-b border-r border-line p-2.5 [&:nth-child(3n)]:border-r-0">
            <div className="text-slate-500">{k}</div><div className="mt-0.5 font-semibold text-navy-ink">{v}</div>
          </div>
        ))}
      </div>
      <div className="no-scrollbar mt-4 flex gap-1 overflow-x-auto">
        {[["progress", "Progress"], ["milestones", "Milestones"], ["documents", "Documents"], ["team", "Team"]].map(([id, l]) => (
          <button key={id} onClick={() => setSubTab(id)} className={`rounded-md px-3 py-1.5 text-xs font-semibold ${subTab === id ? "bg-brand-600 text-white" : "bg-brand-50 text-navy-ink"}`}>{t(l)}</button>
        ))}
      </div>
      <div className="mt-4">
        {subTab === "progress" && (
          <div className="flex flex-wrap items-center gap-6">
            <ProgressRing value={p.progress} label="Overall Progress" />
            <div className="min-w-[200px] flex-1"><StageProgress sch={sch} /></div>
          </div>
        )}
        {subTab === "milestones" && <MilestoneList stages={sch?.stages || []} />}
        {subTab === "documents" && (
          <div className="grid grid-cols-2 gap-2 text-sm">{CATS.map(([c, l]) => <div key={c} className="flex justify-between rounded-lg bg-slate-50 px-3 py-2"><span>{t(l)}</span><b>{detail?.document_counts[c] ?? 0}</b></div>)}</div>
        )}
        {subTab === "team" && <div className="text-sm text-slate-600">{detail?.team.length} member(s) – see Team Members card.</div>}
      </div>
    </Card>
  );

  const teamCard = (
    <Card title={t("Team Members")} icon={<Users size={20} />}
      action={user?.role === "owner" && <button className="link" onClick={() => nav("/settings?tab=access")}>{t("Project Access")}</button>}>
      {!detail?.team.length ? <Empty text={t("No data yet")} /> : (
        <ul className="divide-y divide-line">
          {detail.team.map((m) => (
            <li key={m.id} className="flex items-center gap-3 py-2.5">
              <span className="h-2 w-2 rounded-full bg-emerald-500" />
              <Avatar name={m.full_name} />
              <div className="min-w-0 flex-1"><div className="truncate text-sm font-semibold text-navy-ink">{m.full_name}</div><div className="truncate text-xs text-slate-500">{m.job_title || "—"}</div></div>
              <Badge color={ROLE_COLOR[m.project_role] || "gray"}>{m.project_role === "owner" ? "Owner" : m.project_role === "editor" ? "Editor" : "Viewer"}</Badge>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );

  const activityCard = (full?: boolean) => (
    <Card title={t("Recent Activity")} icon={<Activity size={20} />}>
      {!detail?.activity.length ? <Empty text={t("No data yet")} /> : (
        <ul className="space-y-3">
          {detail.activity.slice(0, full ? 50 : 5).map((a) => (
            <li key={a.id} className="flex items-start gap-3 rounded-lg bg-slate-50/70 p-2.5">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600"><Clock size={18} /></div>
              <div className="min-w-0 flex-1">
                <div className="truncate text-sm font-semibold text-navy-ink">{cap(a.action.replace("_", " "))} {a.entity}{a.details ? ` – ${a.details}` : ""}</div>
                <div className="text-xs text-slate-500">By {a.username}</div>
              </div>
              <div className="shrink-0 text-xs text-slate-500">{timeAgo(a.created_at)}</div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );

  const docsCard = (
    <Card title={t("Project Drawings & Documents")} icon={<FileText size={20} />}>
      <div className="mb-4 flex flex-wrap gap-2">
        {CATS.map(([c, l]) => (
          <button key={c} onClick={() => setCat(c)} className={`rounded-lg px-4 py-2 text-sm font-medium ${cat === c ? "bg-brand-600 text-white" : "bg-brand-50 text-navy-ink"}`}>
            {t(l)} ({detail?.document_counts[c] ?? 0})
          </button>
        ))}
      </div>
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-7">
        {catFiles.map((f) => (
          <div key={f.id} role="button" tabIndex={0} onClick={() => downloadFile(f.url, f.name).catch((e) => toast(e.message, "err"))} title={`v${f.version} · ${fmtBytes(f.size_bytes)}`}
            className="relative flex cursor-pointer flex-col rounded-lg border border-line p-2 text-left hover:border-brand-100 hover:bg-slate-50">
            <OwnerDelete entity="file" id={f.id} title={f.name} onDone={loadDetail} className="absolute right-1 top-1 bg-white/90" />
            <div className="flex h-20 items-center justify-center rounded-md bg-slate-50">
              {f.content_type.startsWith("image/") ? <ImageIcon className="text-brand-600" size={30} /> : <FileText className="text-red-500" size={30} />}
            </div>
            <div className="mt-2 truncate text-xs font-semibold text-navy-ink">{f.name}</div>
            <div className="text-[11px] text-slate-500">v{f.version} · {fmtBytes(f.size_bytes)}</div>
          </div>
        ))}
        {canEdit && (
          <button onClick={() => fileInput.current?.click()} className="flex min-h-[130px] flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed border-brand-100 text-sm font-semibold text-brand-600 hover:bg-brand-50">
            <UploadCloud size={28} />{t("Upload File")}
          </button>
        )}
      </div>
      {!catFiles.length && !canEdit && <Empty text={t("No data yet")} />}
      <p className="mt-3 text-xs text-slate-500">PDF, PNG, JPG, DXF, Excel, Word · max 25 MB. DWG → convert to DXF 2018 or vector PDF first.</p>
      <input ref={fileInput} type="file" hidden accept=".pdf,.png,.jpg,.jpeg,.webp,.dxf,.dwg,.xlsx,.xls,.csv,.docx,.glb"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ""; }} />
    </Card>
  );

  return (
    <Page title={t("Projects")} subtitle={t("Manage multiple projects, teams, documents and track progress")}>
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1"><PillTabs tabs={tabs} value={tab} onChange={setTab} /></div>
        {canCreate && <button className="btn-primary hidden py-2.5 md:inline-flex" onClick={() => setForm({ open: true, project: null })}><Plus size={18} />{t("New Project")}</button>}
      </div>

      {tab === "dashboard" && (
        <>
          <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-3 2xl:grid-cols-5">
                <StatCard tone="bg-brand-50 text-brand-600" icon={<FolderKanban size={28} />} label={t("Total Projects")} value={counts.all ?? 0} sub={t("Active Projects")} />
                <StatCard tone="bg-emerald-50 text-emerald-600" icon={<Target size={28} />} label={t("On Track")} value={counts.on_track ?? 0} sub={t("Projects")} />
                <StatCard tone="bg-red-50 text-red-600" icon={<Clock size={28} />} label={t("Delayed")} value={counts.delayed ?? 0} sub={t("Project")} />
                <StatCard tone="bg-brand-50 text-brand-600" icon={<CheckCircle2 size={28} />} label={t("Completed")} value={counts.completed ?? 0} sub={t("Project")} />
                <StatCard tone="bg-brand-50 text-brand-600" icon={<Users size={28} />} label={t("Total Team Members")} value={teamTotal} sub={t("Users")} />
              </div>
              {projectsCard}
            </div>
            <div>{detailsCard || <Card title={t("Project Details")}><Empty text="Select or create a project" /></Card>}</div>
          </div>
          <div className="grid gap-4 lg:grid-cols-2 2xl:grid-cols-[1.4fr_1fr_1fr_1fr]">
            <Card title={t("Project Timeline (Gantt Chart)")} icon={<CalendarRange size={20} />} action={<button className="link" onClick={() => setTab("milestones")}>View Full Schedule</button>}>
              {p ? <GanttPanel key={`g${p.id}-${schKey}`} projectId={p.id} canEdit={canWrite} compact /> : <Empty text="Select a project" />}
            </Card>
            {teamCard}
            {activityCard()}
            <Card title={t("Milestones")} icon={<Flag size={20} />} action={<button className="link" onClick={() => setTab("milestones")}>{t("View All")}</button>}>
              <MilestoneList stages={sch?.stages || []} />
            </Card>
          </div>
          <div className="grid gap-4 xl:grid-cols-[1.6fr_1fr_1fr]">
            {docsCard}
            <Card title={t("Task Management")} icon={<ListChecks size={20} />} action={<button className="link" onClick={() => setTab("tasks")}>{t("View All")}</button>}>
              {p ? <TasksPanel key={`t${p.id}`} projectId={p.id} canEdit={canWrite} team={detail?.team || []} compact /> : <Empty text="Select a project" />}
            </Card>
            <Card title={t("Approvals")} icon={<BadgeCheck size={20} />} action={<button className="link" onClick={() => setTab("approvals")}>{t("View All")}</button>}>
              {p ? <ApprovalsPanel key={`a${p.id}`} projectId={p.id} canRequest={canWrite} canDecide={user?.role === "owner"} meName={user?.full_name} team={detail?.team || []} compact /> : <Empty text="Select a project" />}
            </Card>
          </div>
        </>
      )}
      {tab === "mine" && projectsCard}
      {tab === "team" && <div className="grid gap-4 lg:grid-cols-2">{teamCard}{user?.role === "owner" && (
        <Card title={t("Project Access")} icon={<Users size={20} />}><p className="mb-3 text-sm text-slate-600">Choose who can see Design, Estimate, Site and Vastu for each project.</p>
          <button className="btn-primary" onClick={() => nav("/settings?tab=access")}>Open Project Access</button></Card>)}</div>}
      {tab === "docs" && docsCard}
      {tab === "tasks" && (p ? <Card title={t("Task Management")} icon={<ListChecks size={20} />}><TasksPanel projectId={p.id} canEdit={canWrite} team={detail?.team || []} /></Card> : <Empty text="Select a project" />)}
      {tab === "milestones" && (p ? <Card title={`${t("Milestones")} & ${t("Project Timeline (Gantt Chart)")}`} icon={<Flag size={20} />}><ScheduleEditor projectId={p.id} canEdit={canWrite} /></Card> : <Empty text="Select a project" />)}
      {tab === "approvals" && (p ? <Card title={t("Approvals")} icon={<BadgeCheck size={20} />}><ApprovalsPanel projectId={p.id} canRequest={canWrite} canDecide={user?.role === "owner"} meName={user?.full_name} team={detail?.team || []} /></Card> : <Empty text="Select a project" />)}
      {tab === "permit" && (p ? <PermitChecklist pid={p.id} canEdit={canEdit} /> : <Empty text="Select a project" />)}
      {tab === "activity" && activityCard(true)}
      {tab === "settings" && (detailsCard || <Empty text="Select a project" />)}

      <ProjectFormModal open={form.open} project={form.project} onClose={() => setForm({ open: false, project: null })} onSaved={onSaved} />
    </Page>
  );
}
