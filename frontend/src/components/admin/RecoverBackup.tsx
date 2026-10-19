import { useEffect, useState } from "react";
import { CheckCircle2, History } from "lucide-react";
import { Modal, toast } from "../ui";
import { api, fmtDateTime } from "../../lib/api";
import { useAuth } from "../../lib/auth";

type Row = { table: string; label: string; in_backup: number; missing: number; sample: string[] };

/** Owner: bring back rows that are in a backup but were deleted permanently. Existing data is never changed. */
export default function RecoverBackup({ backup, onClose }: { backup: any | null; onClose: () => void }) {
  const { reloadProjects } = useAuth();
  const [rows, setRows] = useState<Row[] | null>(null);
  const [err, setErr] = useState("");
  const [pick, setPick] = useState<Record<string, boolean>>({});
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<any>(null);

  useEffect(() => {
    setRows(null); setErr(""); setDone(null); setPick({});
    if (!backup) return;
    api<any>(`/api/admin/backups/${backup.id}/compare`).then((r) => {
      const miss = (r.tables as Row[]).filter((t) => t.missing > 0);
      setRows(miss);
      setPick(Object.fromEntries(miss.map((t) => [t.table, true])));
    }).catch((e) => setErr(e.message));
  }, [backup]);

  const recover = async () => {
    setBusy(true);
    try {
      const r = await api<any>(`/api/admin/backups/${backup.id}/recover`, { body: { tables: Object.keys(pick).filter((k) => pick[k]) } });
      setDone(r); reloadProjects();
      toast(`${r.total} item(s) recovered`);
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const chosen = Object.values(pick).filter(Boolean).length;

  return (
    <Modal open={!!backup} onClose={onClose} title="Recover from backup" wide>
      {backup && <p className="text-sm text-slate-600">Backup of <b>{fmtDateTime(backup.created_at)}</b> ({backup.kind}). Items that are in this backup but
        missing now (deleted permanently) can be added back. Nothing that exists now is changed or overwritten.</p>}
      {err ? <p className="mt-3 text-sm text-red-600">{err}</p> : done ? (
        <div className="mt-3 space-y-2 text-sm">
          <p className="flex items-center gap-2 font-semibold text-emerald-700"><CheckCircle2 size={18} />{done.total} item(s) recovered.</p>
          <p className="text-slate-600">Recovered items that were in the Recycle Bin are back in the <b>Recycle Bin</b> – open it and press <b>Restore</b>.</p>
          {Object.keys(done.skipped || {}).length > 0 && <p className="text-amber-700">Some rows were skipped because their parent item was not recovered
            ({Object.entries(done.skipped).map(([k, v]) => `${k}: ${v}`).join(", ")}). Tick the parent (e.g. Projects) too and recover again.</p>}
          {done.files_missing > 0 && <p className="text-amber-700">{done.files_missing} document(s) came back, but their stored file was already deleted – re-upload them.</p>}
          <div className="flex justify-end"><button className="btn-primary" onClick={onClose}>Close</button></div>
        </div>
      ) : !rows ? <p className="mt-3 text-sm text-slate-500">Comparing the backup with the database…</p> : !rows.length ? (
        <p className="mt-3 flex items-center gap-2 text-sm text-emerald-700"><CheckCircle2 size={18} />Nothing is missing – everything in this backup is still in the database.</p>
      ) : (
        <>
          <div className="mt-3 max-h-80 overflow-auto rounded-lg border border-line">
            <table className="w-full"><thead><tr><th className="table-th w-8" /><th className="table-th">What</th><th className="table-th text-right">Missing now</th><th className="table-th">Examples</th></tr></thead>
              <tbody>{rows.map((t) => (
                <tr key={t.table}>
                  <td className="table-td"><input type="checkbox" checked={!!pick[t.table]} onChange={(e) => setPick({ ...pick, [t.table]: e.target.checked })} /></td>
                  <td className="table-td font-medium text-navy-ink">{t.label}</td>
                  <td className="table-td text-right">{t.missing} <span className="text-xs text-slate-400">of {t.in_backup}</span></td>
                  <td className="table-td text-xs text-slate-600">{t.sample.join(", ")}{t.missing > t.sample.length ? " …" : ""}</td>
                </tr>
              ))}</tbody></table>
          </div>
          <div className="mt-4 flex justify-end gap-2">
            <button className="btn-ghost" onClick={onClose}>Cancel</button>
            <button className="btn-primary" disabled={!chosen || busy} onClick={recover}><History size={16} />{busy ? "Recovering…" : `Recover ${chosen} type(s)`}</button>
          </div>
        </>
      )}
    </Modal>
  );
}
