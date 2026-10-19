import { useCallback, useEffect, useState } from "react";
import { Copy, Link2, Pause, Play, Plus, Users } from "lucide-react";
import { Badge, Card, Field, Modal, toast } from "../ui";
import { api, fmtDateTime } from "../../lib/api";
import { useAuth } from "../../lib/auth";

const MODS: [string, string][] = [["view", "View"], ["edit", "Edit / Docs"], ["design", "Design"], ["estimate", "Estimate"], ["site", "Site"], ["vastu", "Vastu"], ["ai", "AI"]];
const PRESETS: Record<string, string[]> = {
  "Site Engineer": ["view", "site", "ai"], "Design Engineer": ["view", "design", "vastu", "ai"], "Quantity Surveyor": ["view", "estimate", "ai"],
  "Supervisor": ["view", "site"], "Viewer (client)": ["view"],
};
const linkOf = (token: string) => `${window.location.origin}/join/${token}`;

/** Owner: create invite links with ready project access. People who join wait for approval (Users → Pending). */
export default function InviteLinks() {
  const { projects } = useAuth();
  const [rows, setRows] = useState<any[]>([]);
  const [open, setOpen] = useState(false);
  const [label, setLabel] = useState("");
  const [job, setJob] = useState("Site Engineer");
  const [acc, setAcc] = useState<Record<number, Record<string, boolean>>>({});
  const load = useCallback(() => api<any[]>("/api/invites").then(setRows).catch(() => setRows([])), []);
  useEffect(() => { load(); }, [load]);

  const applyPreset = (j: string) => {
    setJob(j);
    const mods = PRESETS[j];
    if (mods) setAcc(Object.fromEntries(Object.keys(acc).map((pid) => [pid, Object.fromEntries(MODS.map(([m]) => [m, mods.includes(m)]))])));
  };
  const toggleProject = (pid: number, on: boolean) => {
    const n = { ...acc };
    if (on) n[pid] = Object.fromEntries(MODS.map(([m]) => [m, (PRESETS[job] || ["view"]).includes(m)]));
    else delete n[pid];
    setAcc(n);
  };
  const create = async () => {
    try {
      const r = await api<any>("/api/invites", { body: { label: label || job, job_title: job, access: acc } });
      setOpen(false); setLabel(""); setAcc({}); load();
      copy(r.token);
    } catch (e: any) { toast(e.message, "err"); }
  };
  const copy = (token: string) => {
    const l = linkOf(token);
    (navigator.clipboard?.writeText(l) || Promise.reject()).then(() => toast("Invite link copied – send it by WhatsApp / SMS / email"))
      .catch(() => window.prompt("Copy this invite link", l));
  };
  const setActive = async (id: number, is_active: boolean) => {
    try { await api(`/api/invites/${id}`, { method: "PATCH", body: { is_active } }); load(); toast(is_active ? "Link working again" : "Link stopped"); }
    catch (e: any) { toast(e.message, "err"); }
  };

  return (
    <Card title="Invite links" icon={<Link2 size={20} />} action={<button className="btn-primary btn-sm" onClick={() => setOpen(true)}><Plus size={14} />Create invite link</button>}>
      <p className="mb-3 text-xs text-slate-500">Send a link to a site engineer or team member. They sign up with it, then wait until you <b>approve</b> them
        (Users → Pending). Their project access is already set from the link – you can change it any time in Project Access. Links work until you stop them.
        {window.location.hostname === "localhost" && " Note: on localhost only this PC can open the link – other places can use it after the app is put online (docs/PHASE_7_GUIDE.md)."}</p>
      {!rows.length ? <p className="text-sm text-slate-500">No invite links yet.</p> : (
        <ul className="space-y-2">
          {rows.map((r) => (
            <li key={r.id} className="rounded-lg border border-line p-3">
              <div className="flex flex-wrap items-center gap-2">
                <b className="text-sm text-navy-ink">{r.label}</b>{r.job_title && <Badge color="blue">{r.job_title}</Badge>}
                <Badge color={r.is_active ? "green" : "gray"}>{r.is_active ? "Working" : "Stopped"}</Badge>
                <span className="text-[11px] text-slate-500">{fmtDateTime(r.created_at)} · used {r.uses}×</span>
                <span className="flex-1" />
                {r.is_active && <button className="btn-outline btn-sm" onClick={() => copy(r.token)}><Copy size={13} />Copy link</button>}
                <button className="btn-ghost btn-sm" onClick={() => setActive(r.id, !r.is_active)}>{r.is_active ? <><Pause size={13} />Stop</> : <><Play size={13} />Start</>}</button>
              </div>
              <div className="mt-1 text-xs text-slate-600">{r.access.map((a: any) => `${a.project}: ${MODS.filter(([m]) => a[m]).map(([, l]) => l).join(", ")}`).join(" | ")}</div>
              {r.joined.length > 0 && <div className="mt-1 flex flex-wrap items-center gap-1.5 text-xs"><Users size={12} />{r.joined.map((u: any) => <Badge key={u.id} color={u.status === "active" ? "green" : "amber"}>{u.full_name} ({u.status})</Badge>)}</div>}
            </li>
          ))}
        </ul>
      )}
      <Modal open={open} onClose={() => setOpen(false)} title="Create invite link" wide>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Role / job title"><select className="input" value={job} onChange={(e) => applyPreset(e.target.value)}>{Object.keys(PRESETS).map((p) => <option key={p}>{p}</option>)}</select></Field>
          <Field label="Name for this link (only you see it)"><input className="input" placeholder="e.g. Thanjavur site team" value={label} onChange={(e) => setLabel(e.target.value)} /></Field>
        </div>
        <div className="mt-3 text-xs font-semibold text-slate-500">Projects and what they can use</div>
        <div className="mt-1 max-h-80 overflow-auto rounded-lg border border-line">
          <table className="w-full"><thead><tr><th className="table-th">Project</th>{MODS.map(([, l]) => <th key={l} className="table-th text-center">{l}</th>)}</tr></thead>
            <tbody>{projects.map((p) => (
              <tr key={p.id}>
                <td className="table-td"><label className="flex items-center gap-2"><input type="checkbox" checked={!!acc[p.id]} onChange={(e) => toggleProject(p.id, e.target.checked)} />{p.code} · {p.name}</label></td>
                {MODS.map(([m]) => <td key={m} className="table-td text-center"><input type="checkbox" disabled={!acc[p.id]} checked={!!acc[p.id]?.[m]} onChange={(e) => setAcc({ ...acc, [p.id]: { ...acc[p.id], [m]: e.target.checked } })} /></td>)}
              </tr>
            ))}</tbody></table>
        </div>
        <div className="mt-4 flex justify-end gap-2"><button className="btn-ghost" onClick={() => setOpen(false)}>Cancel</button>
          <button className="btn-primary" disabled={!Object.keys(acc).length} onClick={create}><Link2 size={16} />Create & copy link</button></div>
      </Modal>
    </Card>
  );
}
