import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Activity, Briefcase, CheckCircle2, CircleDot, ClipboardList, Download, FileText, FolderKanban, FolderOpen,
  Hourglass, Image as ImageIcon, Lock, PauseCircle, Pencil, Plus, Save, Search, Send, UploadCloud, UserRound, Users,
} from "lucide-react";
import Page from "../components/Page";
import OwnerDelete from "../components/OwnerDelete";
import { ProjectFormModal, StatCard } from "../components/ProjectBits";
import { Badge, Card, Empty, Field, Modal, toast } from "../components/ui";
import { api, downloadFile, fmtBytes, fmtDate } from "../lib/api";
import { useAuth } from "../lib/auth";

type Client = { id: number; code: string; name: string; phone: string; email: string; address: string; location: string; notes: string; projects: number; documents: number };
type Stage = { key: string; label: string; done: boolean; date: string };
type CProject = { id: number; code: string; name: string; project_type: string; floors: string; plot: string; builtup_area: number | null; status: string; location: string; updated_at: string; workflow: Stage[] };
type Doc = { id: number; name: string; category: string; size_bytes: number; created_at: string; url: string; content_type: string };
type Detail = { client: Client; projects: CProject[]; documents: Doc[]; doc_categories: Record<string, string> };
type Note = { id: number; activity: string; remarks: string; date: string; by: string };
type PFile = { id: number; name: string; category: string; size_bytes: number; version: number; created_at: string; url: string; content_type: string };

const STATUS: Record<string, [string, string]> = {
  ongoing: ["In Progress", "amber"], completed: ["Completed", "green"], on_hold: ["On Hold", "gray"], archived: ["Archived", "gray"],
};
// project folders (image: Project Files & Drawings) → file categories
const FOLDERS: [string, string][] = [["drawing", "Architectural"], ["structural", "Structural"], ["estimation", "Estimation (BOQ)"],
  ["vastu", "Vastu"], ["approval", "Approval"], ["photo", "Photos"], ["other", "Others"]];
const cap = (s: string) => (s ? s[0].toUpperCase() + s.slice(1) : s);
const EMPTY_C = { name: "", phone: "", email: "", address: "", location: "", notes: "" };

export default function Clients() {
  const { user, setCurrentProjectId, reloadProjects } = useAuth();
  const nav = useNavigate();
  const [stats, setStats] = useState<Record<string, number>>({});
  const [q, setQ] = useState("");
  const [list, setList] = useState<Client[]>([]);
  const [cid, setCid] = useState<number | null>(null);
  const [d, setD] = useState<Detail | null>(null);
  const [form, setForm] = useState<typeof EMPTY_C>(EMPTY_C);
  const [dirty, setDirty] = useState(false);
  const [newOpen, setNewOpen] = useState(false);
  const [docCat, setDocCat] = useState("all");
  const [pid, setPid] = useState<number | null>(null);
  const [projOpen, setProjOpen] = useState(false);
  const docInput = useRef<HTMLInputElement>(null);
  const [upCat, setUpCat] = useState("land");

  const loadStats = () => api<any>("/api/clients/stats").then(setStats).catch(() => {});
  const loadList = useCallback(() => api<{ clients: Client[] }>(`/api/clients?q=${encodeURIComponent(q)}`)
    .then((r) => { setList(r.clients); if (!cid && r.clients[0]) setCid(r.clients[0].id); }).catch((e) => toast(e.message, "err")), [q]);
  const loadDetail = useCallback(async () => {
    if (!cid) { setD(null); return; }
    const r = await api<Detail>(`/api/clients/${cid}`);
    setD(r);
    const c = r.client;
    setForm({ name: c.name, phone: c.phone, email: c.email, address: c.address, location: c.location, notes: c.notes });
    setDirty(false);
    setPid((old) => (old && r.projects.some((p) => p.id === old) ? old : r.projects[0]?.id ?? null));
  }, [cid]);

  const isOwner = user?.role === "owner";
  useEffect(() => { if (isOwner) loadStats(); }, [isOwner]);
  useEffect(() => { if (!isOwner) return; const h = setTimeout(loadList, 250); return () => clearTimeout(h); }, [loadList, isOwner]);
  useEffect(() => { if (isOwner) loadDetail().catch((e) => toast(e.message, "err")); }, [loadDetail, isOwner]);

  if (!isOwner) {
    return <Page title="Clients" subtitle="Owner only"><Empty icon={<Lock className="text-slate-400" />} text="Clients are visible only to the owner." /></Page>;
  }

  const saveClient = async () => {
    if (!cid) return;
    try { await api(`/api/clients/${cid}`, { method: "PATCH", body: form }); toast("Client saved"); await Promise.all([loadDetail(), loadList()]); }
    catch (e: any) { toast(e.message, "err"); }
  };
  const uploadDoc = async (file: File) => {
    if (!cid) return;
    const fd = new FormData(); fd.append("category", upCat); fd.append("file", file);
    try { await api(`/api/clients/${cid}/files`, { form: fd }); toast(`${file.name} uploaded`); await Promise.all([loadDetail(), loadList()]); }
    catch (e: any) { toast(e.message, "err"); }
  };
  const docs = (d?.documents || []).filter((x) => docCat === "all" || x.category === `client_${docCat}`);
  const project = d?.projects.find((p) => p.id === pid) || null;
  const set = (k: keyof typeof EMPTY_C) => (e: any) => { setForm({ ...form, [k]: e.target.value }); setDirty(true); };

  return (
    <Page title="Clients & Projects" subtitle="Your clients, their documents and every project – visible only to you">
      {/* stats + quick actions */}
      <div className="grid gap-4 xl:grid-cols-[1fr_260px]">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 2xl:grid-cols-6">
          <StatCard tone="bg-brand-50 text-brand-600" icon={<Users size={26} />} label="Total Clients" value={stats.clients ?? 0} sub="Clients" />
          <StatCard tone="bg-amber-50 text-amber-600" icon={<FolderKanban size={26} />} label="Total Projects" value={stats.projects ?? 0} sub="Projects" />
          <StatCard tone="bg-emerald-50 text-emerald-600" icon={<Hourglass size={26} />} label="In Progress" value={stats.in_progress ?? 0} sub="Projects" />
          <StatCard tone="bg-violet-50 text-violet-600" icon={<CheckCircle2 size={26} />} label="Completed" value={stats.completed ?? 0} sub="Projects" />
          <StatCard tone="bg-red-50 text-red-600" icon={<Send size={26} />} label="Submitted" value={stats.submitted ?? 0} sub="For approval" />
          <StatCard tone="bg-slate-100 text-slate-600" icon={<PauseCircle size={26} />} label="On Hold" value={stats.on_hold ?? 0} sub="Projects" />
        </div>
        <Card title="Quick Actions" icon={<Briefcase size={20} />}>
          <div className="flex flex-col gap-2">
            <button className="btn-primary" onClick={() => setNewOpen(true)}><Plus size={16} />New Client</button>
            <button className="btn-outline" disabled={!cid} onClick={() => setProjOpen(true)}><Plus size={16} />New Project</button>
            <button className="btn-outline" onClick={() => nav("/design")}><UploadCloud size={16} />Import Drawing</button>
          </div>
        </Card>
      </div>

      {/* clients list · client details · client documents */}
      <div className="grid gap-4 xl:grid-cols-[1.25fr_1fr_1.25fr]">
        <Card title="Clients List" icon={<Users size={20} />}>
          <div className="relative mb-3">
            <Search size={16} className="absolute left-3 top-2.5 text-slate-400" />
            <input className="input pl-9" placeholder="Search client by name, phone, location..." value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          {!list.length ? <Empty text={q ? "No client matches." : "No clients yet – add your first client."} /> : (
            <div className="max-h-[360px] overflow-auto rounded-lg border border-line">
              <table className="w-full text-sm">
                <thead className="sticky top-0 bg-slate-50 text-left text-xs text-slate-500"><tr>
                  <th className="px-3 py-2">ID</th><th className="px-3 py-2">Client</th><th className="px-3 py-2">Contact</th>
                  <th className="px-3 py-2">Location</th><th className="px-3 py-2 text-center">Projects</th></tr></thead>
                <tbody>
                  {list.map((c) => (
                    <tr key={c.id} onClick={() => setCid(c.id)}
                      className={`cursor-pointer border-t border-line ${c.id === cid ? "bg-brand-50" : "hover:bg-slate-50"}`}>
                      <td className="px-3 py-2 font-semibold text-brand-700">{c.code}</td>
                      <td className="px-3 py-2 font-medium text-navy-ink">{c.name}</td>
                      <td className="px-3 py-2 text-slate-600">{c.phone || "—"}</td>
                      <td className="px-3 py-2 text-slate-600">{c.location || "—"}</td>
                      <td className="px-3 py-2 text-center">{c.projects}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>

        <Card title="Client Details" icon={<UserRound size={20} />}
          action={d && <div className="flex items-center gap-1">
            <OwnerDelete entity="client" id={d.client.id} title={`${d.client.code} · ${d.client.name}`} onDone={() => { setCid(null); loadList(); loadStats(); }} />
          </div>}>
          {!d ? <Empty text="Select or add a client" /> : (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-xs text-slate-500">Client ID <b className="text-navy-ink">{d.client.code}</b></div>
              <Field label="Client Name"><input className="input" value={form.name} onChange={set("name")} /></Field>
              <div className="grid grid-cols-2 gap-3">
                <Field label="Contact No"><input className="input" value={form.phone} onChange={set("phone")} /></Field>
                <Field label="Location (town)"><input className="input" value={form.location} onChange={set("location")} /></Field>
              </div>
              <Field label="Email"><input className="input" value={form.email} onChange={set("email")} /></Field>
              <Field label="Address"><textarea className="input min-h-[60px]" value={form.address} onChange={set("address")} /></Field>
              <Field label="Notes"><textarea className="input min-h-[60px]" value={form.notes} onChange={set("notes")} placeholder="Need plan, estimate and approval." /></Field>
              <button className="btn-primary w-full" disabled={!dirty || form.name.trim().length < 2} onClick={saveClient}><Save size={16} />Save</button>
            </div>
          )}
        </Card>

        <Card title="Client Documents" icon={<FolderOpen size={20} />}
          action={d && <button className="btn-primary btn-sm" onClick={() => docInput.current?.click()}><UploadCloud size={14} />Upload</button>}>
          {!d ? <Empty text="Select a client" /> : (
            <>
              <div className="mb-3 flex flex-wrap gap-1.5">
                {[["all", "All Documents"], ...Object.entries(d.doc_categories)].map(([k, l]) => (
                  <button key={k} onClick={() => setDocCat(k)} className={`rounded-md px-3 py-1.5 text-xs font-semibold ${docCat === k ? "bg-brand-600 text-white" : "bg-brand-50 text-navy-ink"}`}>{l}</button>
                ))}
              </div>
              {!docs.length ? <Empty text="No documents here yet." /> : (
                <ul className="max-h-[300px] divide-y divide-line overflow-auto rounded-lg border border-line">
                  {docs.map((x) => (
                    <li key={x.id} className="flex items-center gap-2 px-3 py-2 text-sm">
                      {x.content_type.startsWith("image/") ? <ImageIcon size={18} className="shrink-0 text-brand-600" /> : <FileText size={18} className="shrink-0 text-red-500" />}
                      <div className="min-w-0 flex-1">
                        <div className="truncate font-medium text-navy-ink">{x.name}</div>
                        <div className="text-[11px] text-slate-500">{d.doc_categories[x.category.replace("client_", "")] || "Other"} · {fmtDate(x.created_at)} · {fmtBytes(x.size_bytes)}</div>
                      </div>
                      <button className="btn-ghost btn-sm" title="Download" onClick={() => downloadFile(x.url, x.name).catch((e) => toast(e.message, "err"))}><Download size={15} /></button>
                      <OwnerDelete entity="file" id={x.id} title={x.name} onDone={loadDetail} />
                    </li>
                  ))}
                </ul>
              )}
              <div className="mt-3 flex items-center gap-2 rounded-lg border-2 border-dashed border-brand-100 p-3 text-xs text-slate-600">
                <span>Upload as</span>
                <select className="input w-auto py-1 text-xs" value={upCat} onChange={(e) => setUpCat(e.target.value)}>
                  {Object.entries(d.doc_categories).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
                </select>
                <button className="link" onClick={() => docInput.current?.click()}>Browse files</button>
                <span className="ml-auto text-[11px] text-slate-400">PDF, JPG, PNG · only you can open these</span>
              </div>
              <input ref={docInput} type="file" hidden accept=".pdf,.png,.jpg,.jpeg,.webp,.docx,.xlsx"
                onChange={(e) => { const f = e.target.files?.[0]; if (f) uploadDoc(f); e.target.value = ""; }} />
            </>
          )}
        </Card>
      </div>

      {/* projects of the client · project details */}
      <div className="grid gap-4 xl:grid-cols-[1.6fr_1fr]">
        <Card title={d ? `Projects List (Client: ${d.client.name})` : "Projects List"} icon={<ClipboardList size={20} />}
          action={d && <button className="btn-primary btn-sm" onClick={() => setProjOpen(true)}><Plus size={14} />New Project</button>}>
          {!d?.projects.length ? <Empty text={d ? "No projects for this client yet." : "Select a client"} /> : (
            <div className="overflow-x-auto rounded-lg border border-line">
              <table className="w-full min-w-[640px] text-sm">
                <thead className="bg-slate-50 text-left text-xs text-slate-500"><tr>
                  <th className="px-3 py-2">Project ID</th><th className="px-3 py-2">Project Name</th><th className="px-3 py-2">Type</th><th className="px-3 py-2">Floors</th>
                  <th className="px-3 py-2">Plot Size</th><th className="px-3 py-2">Built-up</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Last Updated</th><th /></tr></thead>
                <tbody>
                  {d.projects.map((p) => (
                    <tr key={p.id} onClick={() => setPid(p.id)} className={`cursor-pointer border-t border-line ${p.id === pid ? "bg-brand-50" : "hover:bg-slate-50"}`}>
                      <td className="px-3 py-2 font-semibold text-brand-700">{p.code}</td>
                      <td className="px-3 py-2 font-medium text-navy-ink">{p.name}</td>
                      <td className="px-3 py-2">{cap(p.project_type)}</td>
                      <td className="px-3 py-2">{p.floors}</td>
                      <td className="px-3 py-2">{p.plot || "—"}</td>
                      <td className="px-3 py-2">{p.builtup_area ? `${p.builtup_area.toLocaleString("en-IN")} sq.ft` : "—"}</td>
                      <td className="px-3 py-2"><Badge color={(STATUS[p.status] || ["", "gray"])[1]}>{(STATUS[p.status] || [cap(p.status)])[0]}</Badge></td>
                      <td className="px-3 py-2 text-slate-600">{fmtDate(p.updated_at)}</td>
                      <td className="px-3 py-2"><button className="btn-outline btn-sm" onClick={(e) => { e.stopPropagation(); setCurrentProjectId(p.id); nav("/projects"); }}>Open</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
        <Card title={project ? `Project Details (${project.code})` : "Project Details"} icon={<FileText size={20} />}>
          {!project ? <Empty text="Select a project" /> : (
            <div className="overflow-hidden rounded-lg border border-line text-sm">
              {[["Project Name", project.name], ["Location", project.location || "—"], ["Plot Size", project.plot || "—"],
                ["Built-up Area", project.builtup_area ? `${project.builtup_area.toLocaleString("en-IN")} sq.ft` : "—"],
                ["Building Type", cap(project.project_type)], ["No. of Floors", project.floors],
                ["Current Status", (STATUS[project.status] || [cap(project.status)])[0]]].map(([k, v]) => (
                <div key={k} className="flex justify-between gap-3 border-b border-line px-3 py-2 last:border-b-0">
                  <span className="text-slate-500">{k}</span><span className="text-right font-semibold text-navy-ink">{v}</span>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>

      {project && <ProjectFiles key={`f${project.id}`} pid={project.id} />}
      {project && <Tracker key={`w${project.id}`} pid={project.id} code={project.code} onChange={() => { loadDetail(); loadStats(); }} />}
      {project && <Notes key={`n${project.id}`} pid={project.id} />}

      <NewClientModal open={newOpen} onClose={() => setNewOpen(false)}
        onSaved={(c) => { setQ(""); setCid(c.id); loadList(); loadStats(); }} />
      {d && <ProjectFormModal open={projOpen} onClose={() => setProjOpen(false)} project={null}
        preset={{ client_id: d.client.id, client_name: d.client.name, location: d.client.location }}
        onSaved={async (p) => { await reloadProjects(); await loadDetail(); await loadList(); loadStats(); setPid(p.id); }} />}
    </Page>
  );
}

function NewClientModal({ open, onClose, onSaved }: { open: boolean; onClose: () => void; onSaved: (c: Client) => void }) {
  const [f, setF] = useState(EMPTY_C);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) setF(EMPTY_C); }, [open]);
  const set = (k: keyof typeof EMPTY_C) => (e: any) => setF({ ...f, [k]: e.target.value });
  const save = async () => {
    if (f.name.trim().length < 2) return toast("Client name is required", "err");
    setBusy(true);
    try { const c = await api<Client>("/api/clients", { body: f }); toast(`Client ${c.code} added`); onSaved(c); onClose(); }
    catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  return (
    <Modal open={open} onClose={onClose} title="New Client">
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Client name *" className="sm:col-span-2"><input className="input" value={f.name} onChange={set("name")} placeholder="Mr. Kumar" /></Field>
        <Field label="Contact No"><input className="input" value={f.phone} onChange={set("phone")} /></Field>
        <Field label="Location (town)"><input className="input" value={f.location} onChange={set("location")} placeholder="Thiruvarur" /></Field>
        <Field label="Email" className="sm:col-span-2"><input className="input" value={f.email} onChange={set("email")} /></Field>
        <Field label="Address" className="sm:col-span-2"><textarea className="input min-h-[60px]" value={f.address} onChange={set("address")} /></Field>
        <Field label="Notes" className="sm:col-span-2"><textarea className="input min-h-[60px]" value={f.notes} onChange={set("notes")} /></Field>
      </div>
      <div className="mt-5 flex justify-end gap-2">
        <button className="btn-ghost" onClick={onClose}>Cancel</button>
        <button className="btn-primary" disabled={busy} onClick={save}>{busy ? "Saving..." : "Save Client"}</button>
      </div>
    </Modal>
  );
}

function ProjectFiles({ pid }: { pid: number }) {
  const [files, setFiles] = useState<PFile[]>([]);
  const [cat, setCat] = useState("drawing");
  const input = useRef<HTMLInputElement>(null);
  const load = useCallback(() => api<PFile[]>(`/api/files/project/${pid}`).then(setFiles).catch((e) => toast(e.message, "err")), [pid]);
  useEffect(() => { load(); }, [load]);
  const shown = useMemo(() => files.filter((f) => f.category === cat), [files, cat]);
  const count = (c: string) => files.filter((f) => f.category === c).length;
  const upload = async (file: File) => {
    const fd = new FormData(); fd.append("category", cat); fd.append("file", file);
    try { await api(`/api/files/project/${pid}`, { form: fd }); toast(`${file.name} uploaded`); load(); }
    catch (e: any) { toast(e.message, "err"); }
  };
  return (
    <Card title="Project Files & Drawings" icon={<FolderOpen size={20} />}
      action={<button className="btn-primary btn-sm" onClick={() => input.current?.click()}><UploadCloud size={14} />Upload Drawing</button>}>
      <div className="mb-3 flex flex-wrap gap-1.5">
        {FOLDERS.map(([c, l]) => (
          <button key={c} onClick={() => setCat(c)} className={`rounded-md px-3 py-1.5 text-xs font-semibold ${cat === c ? "bg-brand-600 text-white" : "bg-brand-50 text-navy-ink"}`}>{l} ({count(c)})</button>
        ))}
      </div>
      {!shown.length ? <Empty text="No files in this folder yet." /> : (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 xl:grid-cols-7">
          {shown.map((f) => (
            <div key={f.id} role="button" tabIndex={0} onClick={() => downloadFile(f.url, f.name).catch((e) => toast(e.message, "err"))}
              className="relative cursor-pointer rounded-lg border border-line p-2 hover:bg-slate-50">
              <OwnerDelete entity="file" id={f.id} title={f.name} onDone={load} className="absolute right-1 top-1 bg-white/90" />
              <div className="flex h-16 items-center justify-center rounded-md bg-slate-50">
                {f.content_type.startsWith("image/") ? <ImageIcon className="text-brand-600" size={26} /> : <FileText className="text-red-500" size={26} />}
              </div>
              <div className="mt-2 truncate text-xs font-semibold text-navy-ink">{f.name}</div>
              <div className="text-[11px] text-slate-500">{fmtDate(f.created_at)} · {fmtBytes(f.size_bytes)}</div>
            </div>
          ))}
        </div>
      )}
      <input ref={input} type="file" hidden accept=".pdf,.png,.jpg,.jpeg,.webp,.dxf,.dwg,.xlsx,.xls,.csv,.docx,.glb"
        onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ""; }} />
    </Card>
  );
}

function Tracker({ pid, code, onChange }: { pid: number; code: string; onChange: () => void }) {
  const [stages, setStages] = useState<Stage[]>([]);
  const [edit, setEdit] = useState<Stage | null>(null);
  const [date, setDate] = useState("");
  useEffect(() => { api<{ stages: Stage[] }>(`/api/projects/${pid}/workflow`).then((r) => setStages(r.stages)).catch(() => {}); }, [pid]);
  const save = async (done: boolean) => {
    if (!edit) return;
    try {
      const r = await api<{ stages: Stage[] }>(`/api/projects/${pid}/workflow`, { method: "PUT", body: { key: edit.key, done, date: done ? date || null : null } });
      setStages(r.stages); setEdit(null); onChange();
    } catch (e: any) { toast(e.message, "err"); }
  };
  const next = stages.findIndex((s) => !s.done);
  return (
    <Card title={`Project Progress Tracker (${code})`} icon={<Activity size={20} />}>
      <div className="no-scrollbar overflow-x-auto pb-2">
        <ol className="flex min-w-[760px] items-start">
          {stages.map((s, i) => (
            <li key={s.key} className="relative flex flex-1 flex-col items-center text-center">
              {i > 0 && <span className={`absolute right-1/2 top-4 h-0.5 w-full ${s.done || stages[i - 1].done ? "bg-emerald-400" : "bg-slate-200"}`} />}
              <button onClick={() => { setEdit(s); setDate(s.date || new Date().toISOString().slice(0, 10)); }}
                className={`relative z-10 flex h-8 w-8 items-center justify-center rounded-full border-2 ${s.done ? "border-emerald-500 bg-emerald-500 text-white" : i === next ? "border-amber-400 bg-amber-50 text-amber-600" : "border-slate-300 bg-white text-slate-400"}`}
                title="Tap to mark done / pending">
                {s.done ? <CheckCircle2 size={18} /> : <CircleDot size={16} />}
              </button>
              <div className="mt-2 text-xs font-semibold text-navy-ink">{s.label}</div>
              <div className={`text-[11px] ${s.done ? "text-emerald-700" : i === next ? "text-amber-600" : "text-slate-400"}`}>
                {s.done ? fmtDate(s.date) : i === next ? "In Progress" : "Pending"}</div>
            </li>
          ))}
        </ol>
      </div>
      <Modal open={!!edit} onClose={() => setEdit(null)} title={edit?.label || ""}>
        <Field label="Date"><input className="input" type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
        <div className="mt-4 flex justify-end gap-2">
          {edit?.done && <button className="btn-ghost" onClick={() => save(false)}>Mark pending</button>}
          <button className="btn-primary" onClick={() => save(true)}><CheckCircle2 size={16} />{edit?.done ? "Update date" : "Mark done"}</button>
        </div>
      </Modal>
    </Card>
  );
}

function Notes({ pid }: { pid: number }) {
  const [notes, setNotes] = useState<Note[]>([]);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState({ activity: "", remarks: "", note_date: "" });
  const load = useCallback(() => api<{ notes: Note[] }>(`/api/projects/${pid}/notes`).then((r) => setNotes(r.notes)).catch(() => {}), [pid]);
  useEffect(() => { load(); }, [load]);
  const add = async () => {
    if (f.activity.trim().length < 2) return toast("Write the activity", "err");
    try { await api(`/api/projects/${pid}/notes`, { body: { ...f, note_date: f.note_date || null } }); setOpen(false); setF({ activity: "", remarks: "", note_date: "" }); load(); }
    catch (e: any) { toast(e.message, "err"); }
  };
  return (
    <Card title="Notes & Activity History" icon={<Pencil size={20} />}
      action={<button className="btn-primary btn-sm" onClick={() => setOpen(true)}><Plus size={14} />Add Note</button>}>
      {!notes.length ? <Empty text="No notes yet – e.g. “Revised bedroom size”, “Uploaded site photos”." /> : (
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full min-w-[520px] text-sm">
            <thead className="bg-slate-50 text-left text-xs text-slate-500"><tr>
              <th className="px-3 py-2">Date</th><th className="px-3 py-2">Activity</th><th className="px-3 py-2">By</th><th className="px-3 py-2">Remarks</th><th /></tr></thead>
            <tbody>
              {notes.map((n) => (
                <tr key={n.id} className="border-t border-line">
                  <td className="whitespace-nowrap px-3 py-2">{fmtDate(n.date)}</td>
                  <td className="px-3 py-2 font-medium text-navy-ink">{n.activity}</td>
                  <td className="px-3 py-2 text-slate-600">{n.by}</td>
                  <td className="px-3 py-2 text-slate-600">{n.remarks}</td>
                  <td className="px-2 py-2"><OwnerDelete entity="note" id={n.id} title={n.activity} onDone={load} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="Add Note">
        <div className="space-y-3">
          <Field label="Activity *"><input className="input" value={f.activity} onChange={(e) => setF({ ...f, activity: e.target.value })} placeholder="Updated Floor Plan" /></Field>
          <Field label="Remarks"><input className="input" value={f.remarks} onChange={(e) => setF({ ...f, remarks: e.target.value })} placeholder="Revised bedroom size" /></Field>
          <Field label="Date (blank = today)"><input className="input" type="date" value={f.note_date} onChange={(e) => setF({ ...f, note_date: e.target.value })} /></Field>
        </div>
        <div className="mt-4 flex justify-end"><button className="btn-primary" onClick={add}><Save size={16} />Save</button></div>
      </Modal>
    </Card>
  );
}
