import OwnerDelete from "../OwnerDelete";
import { useCallback, useEffect, useState } from "react";
import { Check, Plus, Save, Wand2 } from "lucide-react";
import { Badge, Empty, Field, Modal, toast } from "../ui";
import { api, fmtDate } from "../../lib/api";
import Gantt, { GROUP_COLOR, type Stage } from "./Gantt";

export type Schedule = {
  stages: Stage[]; overall: number; planned: number; variance_days: number; health: string;
  pipeline: { label: string; progress: number; status: string }[]; groups: { group: string; label: string; progress: number }[];
};

export function useSchedule(projectId?: number) {
  const [sch, setSch] = useState<Schedule | null>(null);
  const load = useCallback(async () => {
    if (!projectId) return;
    try { setSch(await api<Schedule>(`/api/projects/${projectId}/schedule`)); } catch { setSch(null); }
  }, [projectId]);
  useEffect(() => { load(); }, [load]);
  return { sch, reload: load };
}

export function CreateSchedule({ projectId, onDone, canEdit }: { projectId: number; onDone: () => void; canEdit: boolean }) {
  if (!canEdit) return <Empty text="No schedule yet – ask the project editor to create it." />;
  return (
    <Empty text="No schedule yet. Create one from the standard house-construction template (uses the project's floors and start / end dates), then adjust.">
      <button className="btn-primary btn-sm mt-1" onClick={async () => {
        try { await api(`/api/projects/${projectId}/schedule/template`, { method: "POST" }); toast("Schedule created"); onDone(); }
        catch (e: any) { toast(e.message, "err"); }
      }}><Wand2 size={14} />Create schedule</button>
    </Empty>
  );
}

export function GanttPanel({ projectId, canEdit, compact }: { projectId: number; canEdit: boolean; compact?: boolean }) {
  const { sch, reload } = useSchedule(projectId);
  if (!sch) return <p className="text-sm text-slate-500">Loading…</p>;
  if (!sch.stages.length) return <CreateSchedule projectId={projectId} onDone={reload} canEdit={canEdit} />;
  return <Gantt stages={sch.stages} compact={compact} maxRows={compact ? 8 : undefined} />;
}

export function StageProgress({ sch }: { sch: Schedule | null }) {
  if (!sch?.groups.length) return <p className="text-xs text-slate-500">Stage-wise progress appears when the schedule exists (Milestones tab).</p>;
  return (
    <ul className="space-y-2 text-sm">
      {sch.groups.map((g) => (
        <li key={g.group} className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: GROUP_COLOR[g.group] }} />
          <span className="w-40 shrink-0 text-slate-700">{g.label}</span>
          <span className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100"><span className="block h-full rounded-full" style={{ width: `${g.progress}%`, background: GROUP_COLOR[g.group] }} /></span>
          <span className="w-12 text-right font-semibold text-navy-ink">{Math.round(g.progress)}%</span>
        </li>
      ))}
    </ul>
  );
}

export function MilestoneList({ stages }: { stages: Stage[] }) {
  const ms = stages.filter((s) => s.is_milestone);
  if (!ms.length) return <p className="text-sm text-slate-500">No milestones yet.</p>;
  return (
    <ul className="divide-y divide-line text-sm">
      {ms.map((s) => (
        <li key={s.id} className="flex items-center justify-between gap-2 py-2">
          <span className="min-w-0 truncate"><span className="text-amber-500">◆ </span>{s.name}<span className="block text-xs text-slate-500">due {fmtDate(s.end_date)}</span></span>
          <Badge color={s.status === "completed" ? "green" : s.end_date && new Date(s.end_date) < new Date() ? "red" : s.status === "in_progress" ? "blue" : "amber"}>
            {s.status === "completed" ? "Done" : s.end_date && new Date(s.end_date) < new Date() ? "Late" : s.status === "in_progress" ? `${s.progress}%` : "Pending"}
          </Badge>
        </li>
      ))}
    </ul>
  );
}

/** Full schedule editor (Projects → Milestones tab). */
export function ScheduleEditor({ projectId, canEdit }: { projectId: number; canEdit: boolean }) {
  const { sch, reload } = useSchedule(projectId);
  const [add, setAdd] = useState(false);
  const [nw, setNw] = useState<any>({ name: "", stage_group: "finishing", start_date: "", end_date: "", weight: 2, is_milestone: false });
  if (!sch) return <p className="text-sm text-slate-500">Loading…</p>;
  if (!sch.stages.length) return <CreateSchedule projectId={projectId} onDone={reload} canEdit={canEdit} />;
  const patch = async (id: number, body: any) => {
    try { await api(`/api/schedule/stages/${id}`, { method: "PATCH", body }); reload(); } catch (e: any) { toast(e.message, "err"); }
  };
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2 text-sm">
        <Badge color="blue">Overall {sch.overall}%</Badge><Badge color="gray">Planned today {sch.planned}%</Badge>
        <Badge color={sch.variance_days < -3 ? "red" : "green"}>{sch.variance_days >= 0 ? `${sch.variance_days} days ahead` : `${-sch.variance_days} days behind`}</Badge>
      </div>
      <Gantt stages={sch.stages} />
      <div className="overflow-x-auto">
        <table className="w-full min-w-[820px]">
          <thead><tr>{["Stage", "Group", "Start", "End", "Weight", "Milestone", "Progress", ""].map((h) => <th key={h} className="table-th">{h}</th>)}</tr></thead>
          <tbody>
            {sch.stages.map((s) => (
              <tr key={s.id}>
                <td className="table-td"><input className="input py-1" defaultValue={s.name} disabled={!canEdit} onBlur={(e) => e.target.value !== s.name && patch(s.id, { name: e.target.value })} /></td>
                <td className="table-td"><select className="input py-1 text-xs" value={s.stage_group} disabled={!canEdit} onChange={(e) => patch(s.id, { stage_group: e.target.value })}>{Object.keys(GROUP_COLOR).map((g) => <option key={g}>{g}</option>)}</select></td>
                <td className="table-td"><input type="date" className="input py-1 text-xs" defaultValue={s.start_date || ""} disabled={!canEdit} onBlur={(e) => e.target.value && e.target.value !== s.start_date && patch(s.id, { start_date: e.target.value })} /></td>
                <td className="table-td"><input type="date" className="input py-1 text-xs" defaultValue={s.end_date || ""} disabled={!canEdit} onBlur={(e) => e.target.value && e.target.value !== s.end_date && patch(s.id, { end_date: e.target.value })} /></td>
                <td className="table-td"><input type="number" className="input w-16 py-1" defaultValue={s.weight} disabled={!canEdit} onBlur={(e) => Number(e.target.value) !== s.weight && patch(s.id, { weight: Number(e.target.value) || 1 })} /></td>
                <td className="table-td text-center"><input type="checkbox" className="h-4 w-4 accent-brand-600" checked={s.is_milestone} disabled={!canEdit} onChange={(e) => patch(s.id, { is_milestone: e.target.checked })} /></td>
                <td className="table-td"><div className="flex items-center gap-2"><input type="range" min={0} max={100} step={5} defaultValue={s.progress} disabled={!canEdit} onMouseUp={(e) => patch(s.id, { progress: Number((e.target as HTMLInputElement).value) })} onTouchEnd={(e) => patch(s.id, { progress: Number((e.target as HTMLInputElement).value) })} /><span className="w-10 text-right text-xs font-semibold">{s.progress}%</span></div></td>
                <td className="table-td"><OwnerDelete entity="stage" id={s.id} title={s.name} onDone={reload} /></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {canEdit && <button className="btn-outline btn-sm" onClick={() => setAdd(true)}><Plus size={14} />Add stage</button>}
      <Modal open={add} onClose={() => setAdd(false)} title="Add stage">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Name" className="sm:col-span-2"><input className="input" value={nw.name} onChange={(e) => setNw({ ...nw, name: e.target.value })} /></Field>
          <Field label="Group"><select className="input" value={nw.stage_group} onChange={(e) => setNw({ ...nw, stage_group: e.target.value })}>{Object.keys(GROUP_COLOR).map((g) => <option key={g}>{g}</option>)}</select></Field>
          <Field label="Weight (effort share)"><input className="input" type="number" value={nw.weight} onChange={(e) => setNw({ ...nw, weight: Number(e.target.value) })} /></Field>
          <Field label="Start"><input className="input" type="date" value={nw.start_date} onChange={(e) => setNw({ ...nw, start_date: e.target.value })} /></Field>
          <Field label="End"><input className="input" type="date" value={nw.end_date} onChange={(e) => setNw({ ...nw, end_date: e.target.value })} /></Field>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="accent-brand-600" checked={nw.is_milestone} onChange={(e) => setNw({ ...nw, is_milestone: e.target.checked })} />Milestone</label>
        </div>
        <div className="mt-4 flex justify-end"><button className="btn-primary" onClick={async () => {
          try { await api(`/api/projects/${projectId}/schedule/stages`, { body: { ...nw, start_date: nw.start_date || null, end_date: nw.end_date || null } }); setAdd(false); reload(); }
          catch (e: any) { toast(e.message, "err"); }
        }}><Save size={16} />Add</button></div>
      </Modal>
    </div>
  );
}

type TaskT = { id: number; title: string; description: string; assignee: string; assignee_id: number | null; due_date: string | null; priority: string; status: string; overdue: boolean };

export function TasksPanel({ projectId, canEdit, team, compact }: { projectId: number; canEdit: boolean; team: { id: number; full_name: string }[]; compact?: boolean }) {
  const [rows, setRows] = useState<TaskT[] | null>(null);
  const [open, setOpen] = useState(false);
  const [f, setF] = useState<any>({ title: "", assignee_id: "", due_date: "", priority: "normal", description: "" });
  const load = useCallback(async () => { try { setRows(await api<TaskT[]>(`/api/projects/${projectId}/tasks`)); } catch { setRows([]); } }, [projectId]);
  useEffect(() => { load(); }, [load]);
  const setStatus = async (t: TaskT, status: string) => { try { await api(`/api/tasks/${t.id}`, { method: "PATCH", body: { status } }); load(); } catch (e: any) { toast(e.message, "err"); } };
  const list = compact ? (rows || []).slice(0, 5) : rows || [];
  const tone = (t: TaskT) => (t.status === "completed" ? "green" : t.overdue ? "red" : t.status === "in_progress" ? "blue" : "amber");
  const label = (t: TaskT) => (t.status === "completed" ? "Completed" : t.overdue ? "Overdue" : t.status === "in_progress" ? "In Progress" : "Pending");
  return (
    <div>
      {canEdit && <div className="mb-2 flex justify-end"><button className="btn-primary btn-sm" onClick={() => setOpen(true)}><Plus size={14} />Add Task</button></div>}
      {!rows ? <p className="text-sm text-slate-500">Loading…</p> : !rows.length ? <Empty text="No tasks yet." /> : (
        <ul className="divide-y divide-line">
          {list.map((t) => (
            <li key={t.id} className="flex items-center gap-3 py-2 text-sm">
              <input type="checkbox" className="h-4 w-4 accent-brand-600" checked={t.status === "completed"} disabled={!canEdit} onChange={(e) => setStatus(t, e.target.checked ? "completed" : "pending")} />
              <span className="min-w-0 flex-1"><span className={t.status === "completed" ? "text-slate-400 line-through" : "text-navy-ink"}>{t.title}</span>
                {!compact && <span className="block text-xs text-slate-500">{t.assignee || "Unassigned"}{t.priority === "high" ? " · high priority" : ""}</span>}</span>
              <span className="w-20 text-right text-xs text-slate-500">{fmtDate(t.due_date)}</span>
              {!compact && canEdit && t.status !== "completed" && t.status !== "in_progress" && <button className="btn-ghost btn-sm" onClick={() => setStatus(t, "in_progress")}>Start</button>}
              <Badge color={tone(t)}>{label(t)}</Badge>
              {!compact && <OwnerDelete entity="task" id={t.id} title={t.title} onDone={load} />}
            </li>
          ))}
        </ul>
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="Add task">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Task" className="sm:col-span-2"><input className="input" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
          <Field label="Assign to"><select className="input" value={f.assignee_id} onChange={(e) => setF({ ...f, assignee_id: e.target.value })}><option value="">— Unassigned —</option>{team.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}</select></Field>
          <Field label="Due date"><input type="date" className="input" value={f.due_date} onChange={(e) => setF({ ...f, due_date: e.target.value })} /></Field>
          <Field label="Priority"><select className="input" value={f.priority} onChange={(e) => setF({ ...f, priority: e.target.value })}><option value="low">Low</option><option value="normal">Normal</option><option value="high">High</option></select></Field>
          <Field label="Details" className="sm:col-span-2"><textarea className="input" rows={2} value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
        </div>
        <div className="mt-4 flex justify-end"><button className="btn-primary" onClick={async () => {
          try { await api(`/api/projects/${projectId}/tasks`, { body: { ...f, assignee_id: f.assignee_id ? Number(f.assignee_id) : null, due_date: f.due_date || null } });
            setOpen(false); setF({ title: "", assignee_id: "", due_date: "", priority: "normal", description: "" }); load(); toast("Task added"); }
          catch (e: any) { toast(e.message, "err"); }
        }}><Save size={16} />Save task</button></div>
      </Modal>
    </div>
  );
}

type Appr = { id: number; item_type: string; title: string; note: string; status: string; approver: string; requested_by: string; history: { at: string; by: string; action: string; comment: string }[]; created_at: string };

export function ApprovalsPanel({ projectId, canRequest, canDecide, team, compact, meName }: { projectId: number; canRequest: boolean; canDecide: boolean; team: { id: number; full_name: string }[]; compact?: boolean; meName?: string }) {
  const [rows, setRows] = useState<Appr[] | null>(null);
  const [open, setOpen] = useState(false);
  const [sel, setSel] = useState<Appr | null>(null);
  const [comment, setComment] = useState("");
  const [f, setF] = useState<any>({ title: "", item_type: "drawing", note: "", approver_id: "" });
  const load = useCallback(async () => { try { setRows(await api<Appr[]>(`/api/projects/${projectId}/approvals`)); } catch { setRows([]); } }, [projectId]);
  useEffect(() => { load(); }, [load]);
  const tone: Record<string, string> = { pending: "amber", approved: "green", rejected: "red", changes: "purple" };
  const decide = async (status: string) => {
    if (!sel) return;
    try { await api(`/api/approvals/${sel.id}/decide`, { body: { status, comment } }); setSel(null); setComment(""); load(); toast(`Marked ${status}`); }
    catch (e: any) { toast(e.message, "err"); }
  };
  return (
    <div>
      {canRequest && <div className="mb-2 flex justify-end"><button className="btn-outline btn-sm" onClick={() => setOpen(true)}><Plus size={14} />Request approval</button></div>}
      {!rows ? <p className="text-sm text-slate-500">Loading…</p> : !rows.length ? <Empty text="No approvals yet." /> : (
        <ul className="divide-y divide-line">
          {(compact ? rows.slice(0, 5) : rows).map((a) => (
            <li key={a.id} className="flex items-center gap-1">
              <button className="flex min-w-0 flex-1 items-center gap-3 py-2 text-left text-sm hover:bg-slate-50" onClick={() => setSel(a)}>
                <span className="min-w-0 flex-1 truncate text-navy-ink">{a.title}{!compact && <span className="block text-xs text-slate-500">{a.item_type} · by {a.requested_by} · {fmtDate(a.created_at)}</span>}</span>
                <Badge color={tone[a.status]}>{a.status === "changes" ? "Changes asked" : a.status[0].toUpperCase() + a.status.slice(1)}</Badge>
              </button>
              {!compact && <OwnerDelete entity="approval" id={a.id} title={a.title} onDone={load} />}
            </li>
          ))}
        </ul>
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="Request approval">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="What needs approval" className="sm:col-span-2"><input className="input" placeholder="e.g. Floor Plan v2" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
          <Field label="Type"><select className="input" value={f.item_type} onChange={(e) => setF({ ...f, item_type: e.target.value })}>{["drawing", "estimate", "design", "material", "other"].map((x) => <option key={x}>{x}</option>)}</select></Field>
          <Field label="Approver"><select className="input" value={f.approver_id} onChange={(e) => setF({ ...f, approver_id: e.target.value })}><option value="">Owner</option>{team.map((m) => <option key={m.id} value={m.id}>{m.full_name}</option>)}</select></Field>
          <Field label="Note" className="sm:col-span-2"><textarea className="input" rows={2} value={f.note} onChange={(e) => setF({ ...f, note: e.target.value })} /></Field>
        </div>
        <div className="mt-4 flex justify-end"><button className="btn-primary" onClick={async () => {
          try { await api(`/api/projects/${projectId}/approvals`, { body: { ...f, approver_id: f.approver_id ? Number(f.approver_id) : null } }); setOpen(false); setF({ title: "", item_type: "drawing", note: "", approver_id: "" }); load(); toast("Approval requested"); }
          catch (e: any) { toast(e.message, "err"); }
        }}><Save size={16} />Send</button></div>
      </Modal>
      <Modal open={!!sel} onClose={() => setSel(null)} title={sel?.title || ""}>
        {sel && (
          <div className="space-y-3 text-sm">
            <div className="flex flex-wrap gap-2"><Badge color={tone[sel.status]}>{sel.status}</Badge><Badge color="gray">{sel.item_type}</Badge><span className="text-slate-500">Approver: {sel.approver}</span></div>
            <ul className="space-y-1 rounded-lg bg-slate-50 p-3">{sel.history.map((h, i) => <li key={i}><b>{h.by}</b> {h.action} · {fmtDate(h.at)}{h.comment && <span className="text-slate-600"> – “{h.comment}”</span>}</li>)}</ul>
            {(canDecide || sel.approver === meName) && sel.status === "pending" && (
              <>
                <textarea className="input" rows={2} placeholder="Comment (optional)" value={comment} onChange={(e) => setComment(e.target.value)} />
                <div className="flex flex-wrap justify-end gap-2">
                  <button className="btn-ghost text-red-600" onClick={() => decide("rejected")}>Reject</button>
                  <button className="btn-outline" onClick={() => decide("changes")}>Ask changes</button>
                  <button className="btn-primary" onClick={() => decide("approved")}><Check size={16} />Approve</button>
                </div>
              </>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
}
