import { useCallback, useEffect, useRef, useState } from "react";
import { ClipboardList, Download, FileText, Paperclip, Plus, Save, Stamp } from "lucide-react";
import { Badge, Card, Field, toast } from "./ui";
import { api, downloadFile, inr } from "../lib/api";

type Item = { key: string; name: string; status: string; file_id: number | null; file_name?: string | null; note: string; custom: boolean };
type Fee = { name: string; amount: number | null; paid: boolean; receipt: string };
type Data = {
  authority: string; authority_label: string; authorities: Record<string, string>; items: Item[]; fees: Fee[];
  application_no: string; approval_no: string; approval_date: string | null; approved_file_id: number | null;
  approved_file_name: string | null; notes: string; progress: number; done: number; total: number; cess_hint: number | null; disclaimer: string;
};
const ST: [string, string, string][] = [["pending", "Pending", "gray"], ["collected", "Collected", "blue"], ["submitted", "Submitted", "amber"],
  ["approved", "Approved", "green"], ["not_needed", "Not needed", "gray"]];

/** Plan approval (building permit) document checklist for one project – tracking only, it does not submit anything. */
export default function PermitChecklist({ pid, canEdit }: { pid: number; canEdit: boolean }) {
  const [d, setD] = useState<Data | null>(null);
  const [busy, setBusy] = useState(false);
  const [newItem, setNewItem] = useState("");
  const fileFor = useRef<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const load = useCallback(() => api<Data>(`/api/projects/${pid}/permit`).then(setD).catch((e) => toast(e.message, "err")), [pid]);
  useEffect(() => { load(); }, [load]);
  if (!d) return <Card><p className="text-sm text-slate-500">Loading…</p></Card>;

  const save = async (patch: Partial<Data>, msg = "Saved") => {
    setBusy(true);
    try { setD(await api<Data>(`/api/projects/${pid}/permit`, { method: "PUT", body: patch })); toast(msg); }
    catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const setItem = (k: string, p: Partial<Item>) => save({ items: d.items.map((i) => (i.key === k ? { ...i, ...p } : i)) });
  const upload = async (f: File) => {
    const key = fileFor.current;
    if (!key) return;
    try {
      const fd = new FormData(); fd.append("category", "contract"); fd.append("file", f);
      const r = await api<any>(`/api/files/project/${pid}`, { form: fd });
      if (key === "__approved") await save({ approved_file_id: r.id }, "Approved plan saved");
      else await save({ items: d.items.map((i) => (i.key === key ? { ...i, file_id: r.id, status: i.status === "pending" ? "collected" : i.status } : i)) }, "Document attached");
    } catch (e: any) { toast(e.message, "err"); }
  };
  const pick = (key: string) => { fileFor.current = key; input.current?.click(); };

  return (
    <div className="grid gap-4 xl:grid-cols-[1fr_380px]">
      <Card title="Plan approval – documents" icon={<ClipboardList size={20} />}
        action={<button className="btn-outline btn-sm" onClick={() => downloadFile(`/api/projects/${pid}/permit/pack.zip`, `Plan_Approval_Pack.zip`).catch((e) => toast(e.message, "err"))}><Download size={14} />Document pack (ZIP)</button>}>
        <div className="mb-3 flex flex-wrap items-end gap-3">
          <Field label="Approving authority">
            <select className="input" value={d.authority} disabled={!canEdit || busy} onChange={(e) => save({ authority: e.target.value }, "Checklist changed")}>
              {Object.entries(d.authorities).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          </Field>
          <div className="min-w-[180px] flex-1">
            <div className="flex justify-between text-xs"><span className="font-semibold text-slate-600">Documents ready</span><span>{d.done} / {d.total}</span></div>
            <div className="mt-1 h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-emerald-500" style={{ width: `${d.progress}%` }} /></div>
          </div>
        </div>
        <ul className="divide-y divide-line rounded-lg border border-line">
          {d.items.map((i, n) => (
            <li key={i.key} className="flex flex-wrap items-center gap-2 px-3 py-2">
              <span className="w-6 text-xs font-bold text-slate-400">{n + 1}</span>
              <span className="min-w-[200px] flex-1 text-sm text-navy-ink">{i.name}
                {i.file_name && <button className="ml-2 inline-flex items-center gap-1 text-xs text-brand-600 underline" onClick={() => downloadFile(`/api/files/${i.file_id}/download`, i.file_name!)}><FileText size={12} />{i.file_name}</button>}</span>
              {canEdit && <button className="btn-ghost btn-sm" title="Attach file" onClick={() => pick(i.key)}><Paperclip size={14} /></button>}
              <select className={`rounded-md border border-line px-2 py-1 text-xs ${i.status === "approved" ? "bg-emerald-50" : ""}`} value={i.status} disabled={!canEdit || busy}
                onChange={(e) => setItem(i.key, { status: e.target.value })}>
                {ST.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
            </li>
          ))}
        </ul>
        {canEdit && (
          <form className="mt-2 flex gap-2" onSubmit={(e) => { e.preventDefault(); if (newItem.trim()) { save({ items: [...d.items, { key: `c${Date.now()}`, name: newItem.trim(), status: "pending", file_id: null, note: "", custom: true }] }, "Added"); setNewItem(""); } }}>
            <input className="input" placeholder="Add another document asked by your local body" value={newItem} onChange={(e) => setNewItem(e.target.value)} />
            <button className="btn-outline shrink-0"><Plus size={15} />Add</button>
          </form>
        )}
        <p className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">{d.disclaimer}</p>
      </Card>

      <div className="space-y-4">
        <Card title="Application & approval" icon={<Stamp size={20} />}>
          <div className="grid gap-2">
            <Field label="Application / file number"><input className="input" defaultValue={d.application_no} disabled={!canEdit} onBlur={(e) => e.target.value !== d.application_no && save({ application_no: e.target.value })} /></Field>
            <Field label="Approval / permit number"><input className="input" defaultValue={d.approval_no} disabled={!canEdit} onBlur={(e) => e.target.value !== d.approval_no && save({ approval_no: e.target.value })} /></Field>
            <Field label="Approval date"><input type="date" className="input" defaultValue={d.approval_date || ""} disabled={!canEdit} onBlur={(e) => e.target.value && e.target.value !== d.approval_date && save({ approval_date: e.target.value })} /></Field>
            <div className="text-sm">Approved plan copy: {d.approved_file_name
              ? <button className="link" onClick={() => downloadFile(`/api/files/${d.approved_file_id}/download`, d.approved_file_name!)}>{d.approved_file_name}</button>
              : <span className="text-slate-500">not uploaded</span>}
              {canEdit && <button className="btn-ghost btn-sm ml-1" onClick={() => pick("__approved")}><Paperclip size={14} />Upload</button>}</div>
            {d.approval_no && <Badge color="green">Approved – {d.approval_no}</Badge>}
          </div>
        </Card>
        <Card title="Fees">
          <div className="space-y-2">
            {d.fees.map((f, i) => (
              <div key={i} className="grid grid-cols-[1fr_100px_auto] items-center gap-2 text-sm">
                <span className="text-slate-700">{f.name}</span>
                <input className="input py-1 text-right" inputMode="decimal" placeholder="₹" defaultValue={f.amount ?? ""} disabled={!canEdit}
                  onBlur={(e) => { const v = e.target.value === "" ? null : Number(e.target.value); if (v !== f.amount) save({ fees: d.fees.map((x, j) => (j === i ? { ...x, amount: v } : x)) }); }} />
                <label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={f.paid} disabled={!canEdit} onChange={(e) => save({ fees: d.fees.map((x, j) => (j === i ? { ...x, paid: e.target.checked } : x)) })} />Paid</label>
              </div>
            ))}
            <div className="flex justify-between border-t border-line pt-2 text-sm font-semibold"><span>Total</span><span>₹{inr(d.fees.reduce((a, f) => a + (f.amount || 0), 0))}</span></div>
            {d.cess_hint != null && <p className="text-[11px] text-slate-500">Labour cess at 1% of your latest estimate ≈ ₹{inr(d.cess_hint)} (check the local body's calculation).</p>}
          </div>
        </Card>
        <Card title="Notes">
          <textarea className="input" rows={3} defaultValue={d.notes} disabled={!canEdit} onBlur={(e) => e.target.value !== d.notes && save({ notes: e.target.value })} />
          {canEdit && <p className="mt-1 flex items-center gap-1 text-[11px] text-slate-400"><Save size={11} />Saved when you leave the box</p>}
        </Card>
      </div>
      <input ref={input} type="file" hidden accept=".pdf,.png,.jpg,.jpeg,.webp,.docx,.xlsx,.dxf" onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) upload(f); }} />
    </div>
  );
}
