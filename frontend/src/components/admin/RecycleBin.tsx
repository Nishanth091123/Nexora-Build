import { useCallback, useEffect, useMemo, useState } from "react";
import { Archive, RotateCcw, Trash2 } from "lucide-react";
import { Badge, Card, Empty, Modal, toast } from "../ui";
import { api, fmtDateTime } from "../../lib/api";
import { useAuth } from "../../lib/auth";

type Item = { entity: string; label: string; id: number; title: string; project: string; deleted_at: string | null; deleted_by: string };

/** Owner only: items moved to the bin can be restored or deleted for ever (a backup is taken first). */
export default function RecycleBin() {
  const { reloadProjects } = useAuth();
  const [data, setData] = useState<{ items: Item[]; archived_projects: { id: number; title: string }[] } | null>(null);
  const [kind, setKind] = useState("all");
  const [confirm, setConfirm] = useState<{ item?: Item; all?: boolean } | null>(null);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => api<any>("/api/trash").then(setData).catch((e) => toast(e.message, "err")), []);
  useEffect(() => { load(); }, [load]);
  const kinds = useMemo(() => Array.from(new Set((data?.items || []).map((i) => i.label))), [data]);
  const rows = (data?.items || []).filter((i) => kind === "all" || i.label === kind);

  const restore = async (i: Item) => {
    try { await api(`/api/trash/${i.entity}/${i.id}/restore`, { method: "POST" }); toast("Restored"); load(); if (i.entity === "project") reloadProjects(); }
    catch (e: any) { toast(e.message, "err"); }
  };
  const purge = async () => {
    if (!confirm) return;
    setBusy(true);
    try {
      const r = confirm.all
        ? await api<any>("/api/trash/empty", { body: { confirm: typed } })
        : await api<any>(`/api/trash/${confirm.item!.entity}/${confirm.item!.id}/purge`, { method: "POST" });
      toast(`${r.deleted} item(s) deleted permanently (backup taken first)`);
      setConfirm(null); setTyped(""); load();
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const binArchived = async (id: number, title: string) => {
    try { await api(`/api/trash/project/${id}`, { method: "POST" }); toast(`${title} moved to the bin`); load(); } catch (e: any) { toast(e.message, "err"); }
  };
  const unarchive = async (id: number) => {
    try { await api(`/api/projects/${id}`, { method: "PATCH", body: { status: "ongoing" } }); toast("Project is active again"); load(); reloadProjects(); } catch (e: any) { toast(e.message, "err"); }
  };

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_340px]">
      <Card title={`Recycle Bin (${data?.items.length ?? 0})`} icon={<Trash2 size={20} className="text-red-600" />}
        action={!!data?.items.length && <button className="btn bg-red-600 btn-sm text-white hover:bg-red-700" onClick={() => setConfirm({ all: true })}><Trash2 size={14} />Empty bin</button>}>
        <p className="mb-3 text-sm text-slate-600">Deleted items stay here until you restore them or delete them permanently. Before a permanent delete,
          a full backup is taken automatically, so even a mistake can be recovered: <b>Settings → Backups → Recover</b> on the “predelete” backup.</p>
        {kinds.length > 1 && (
          <div className="mb-3 flex flex-wrap gap-1.5">
            {["all", ...kinds].map((k) => <button key={k} onClick={() => setKind(k)} className={`rounded-lg px-3 py-1.5 text-xs font-semibold ${kind === k ? "bg-brand-600 text-white" : "bg-slate-100 text-navy-ink"}`}>{k === "all" ? "All" : k}</button>)}
          </div>
        )}
        {!data ? <p className="text-sm text-slate-500">Loading…</p> : !rows.length ? <Empty text="The Recycle Bin is empty." /> : (
          <div className="overflow-x-auto rounded-lg border border-line">
            <table className="w-full min-w-[640px]">
              <thead><tr><th className="table-th">Item</th><th className="table-th">Type</th><th className="table-th">Project</th><th className="table-th">Deleted</th><th className="table-th" /></tr></thead>
              <tbody>{rows.map((i) => (
                <tr key={`${i.entity}${i.id}`}>
                  <td className="table-td font-medium text-navy-ink">{i.title}</td>
                  <td className="table-td"><Badge color={i.entity === "project" ? "red" : "gray"}>{i.label}</Badge></td>
                  <td className="table-td text-xs">{i.project || "—"}</td>
                  <td className="table-td text-xs">{i.deleted_at ? fmtDateTime(i.deleted_at) : "earlier"}{i.deleted_by && ` · ${i.deleted_by}`}</td>
                  <td className="table-td whitespace-nowrap text-right">
                    <button className="btn-ghost btn-sm" onClick={() => restore(i)}><RotateCcw size={14} />Restore</button>
                    <button className="btn-ghost btn-sm text-red-600" onClick={() => setConfirm({ item: i })}><Trash2 size={14} />Delete permanently</button>
                  </td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </Card>
      <Card title="Archived projects" icon={<Archive size={20} />}>
        <p className="mb-2 text-xs text-slate-500">Archived projects are hidden from lists (e.g. old SMOKE TEST projects). Make them active again, or move them to the bin.</p>
        {!data?.archived_projects.length ? <Empty text="No archived projects." /> : (
          <ul className="divide-y divide-line">
            {data.archived_projects.map((p) => (
              <li key={p.id} className="flex items-center gap-2 py-2 text-sm">
                <span className="min-w-0 flex-1 truncate">{p.title}</span>
                <button className="btn-ghost btn-sm" onClick={() => unarchive(p.id)}>Unarchive</button>
                <button className="btn-ghost btn-sm text-red-600" onClick={() => binArchived(p.id, p.title)}><Trash2 size={14} /></button>
              </li>
            ))}
          </ul>
        )}
      </Card>
      <Modal open={!!confirm} onClose={() => { setConfirm(null); setTyped(""); }} title="Delete permanently?">
        <p className="text-sm text-slate-700">{confirm?.all ? <>All <b>{data?.items.length}</b> items in the bin will be removed for ever, with their stored files.</>
          : <><b>{confirm?.item?.title}</b> will be removed for ever{confirm?.item?.entity === "project" && ", with everything inside the project"}.</>}</p>
        <p className="mt-1 text-xs text-slate-500">A full backup is taken first. Type <b>DELETE</b> to confirm.</p>
        <input className="input mt-3" value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="DELETE" />
        <div className="mt-4 flex justify-end gap-2">
          <button className="btn-ghost" onClick={() => { setConfirm(null); setTyped(""); }}>Cancel</button>
          <button className="btn bg-red-600 text-white hover:bg-red-700" disabled={typed !== "DELETE" || busy} onClick={purge}><Trash2 size={16} />{busy ? "Backing up & deleting…" : "Delete permanently"}</button>
        </div>
      </Modal>
    </div>
  );
}
