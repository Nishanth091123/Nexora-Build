import { useCallback, useEffect, useMemo, useState } from "react";
import { Camera, Download, FileSpreadsheet, FileText, Plus, Save, ShieldAlert, Upload, UserPlus } from "lucide-react";
import AuthImg from "../AuthImg";
import OwnerDelete from "../OwnerDelete";
import PhotoCheckButton from "./PhotoCheck";
import PhotoPicker, { compressImage, quickGps } from "./PhotoPicker";
import { Badge, Card, Empty, Field, Modal, toast } from "../ui";
import { api, downloadFile, inr } from "../../lib/api";
import { useSchedule } from "../pm/PmPanels";
import { Bar, Pill, n0, prettyDate, today, type Activity, type MatRow, type Photo, type QC } from "./common";

const WEATHER = ["Sunny", "Cloudy", "Light rain", "Heavy rain", "Hot", "Windy"];

// ---------------------------------------------------------------- activity modal (shared)
export function ActivityModal({ open, onClose, pid, day, onSaved, edit }: {
  open: boolean; onClose: () => void; pid: number; day: string; onSaved: () => void; edit?: Activity | null;
}) {
  const { sch } = useSchedule(open ? pid : undefined);
  const blank = { title: "", location: "", stage_id: "", status: "in_progress", progress: 0, notes: "", updateStage: false, stage_progress: 0 };
  const [f, setF] = useState<any>(blank);
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (!open) return;
    setFile(null);
    setF(edit ? { ...blank, ...edit, stage_id: edit.stage_id ?? "" } : blank);
  }, [open, edit?.id]);
  const stage = sch?.stages.find((s) => String(s.id) === String(f.stage_id));
  const save = async () => {
    if (!f.title.trim()) return toast("Enter the activity name", "err");
    setBusy(true);
    try {
      let photo_file_id = edit?.photo_file_id ?? null;
      if (file) {
        const fd = new FormData(); fd.append("file", file); fd.append("caption", f.title); fd.append("taken_on", day); fd.append("location", f.location || "");
        try {
          const ph = await api<any>(`/api/projects/${pid}/site/photos`, { form: fd });
          photo_file_id = ph.file_id;
        } catch (e: any) { if (!e?.detail?.queued) throw e; }  // offline: photo is queued separately
      }
      const body: any = { title: f.title, location: f.location, stage_id: f.stage_id ? Number(f.stage_id) : null, status: f.status,
        progress: Number(f.progress) || 0, notes: f.notes, photo_file_id, work_date: day };
      if (f.updateStage && f.stage_id) body.stage_progress = Number(f.stage_progress);
      if (edit) await api(`/api/site/activities/${edit.id}`, { method: "PATCH", body });
      else await api(`/api/projects/${pid}/site/activities`, { body });
      toast(edit ? "Activity updated" : "Activity added"); onSaved(); onClose();
    } catch (e: any) { if (e?.detail?.queued) onClose(); else toast(e.message, "err"); } finally { setBusy(false); }
  };
  return (
    <Modal open={open} onClose={onClose} title={edit ? "Update activity" : `Add activity – ${prettyDate(day)}`}>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Activity" className="sm:col-span-2"><input className="input" placeholder="e.g. RCC Column Casting" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} /></Field>
        <Field label="Location (block / floor / area)"><input className="input" value={f.location} onChange={(e) => setF({ ...f, location: e.target.value })} /></Field>
        <Field label="Schedule stage"><select className="input" value={f.stage_id} onChange={(e) => { const st = sch?.stages.find((s) => String(s.id) === e.target.value); setF({ ...f, stage_id: e.target.value, stage_progress: st?.progress ?? 0 }); }}>
          <option value="">— none —</option>{sch?.stages.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></Field>
        <Field label="Status"><select className="input" value={f.status} onChange={(e) => setF({ ...f, status: e.target.value })}><option value="pending">Pending</option><option value="in_progress">In Progress</option><option value="completed">Completed</option></select></Field>
        <Field label={`Activity progress: ${f.progress}%`}><input type="range" min={0} max={100} step={5} value={f.progress} onChange={(e) => setF({ ...f, progress: Number(e.target.value) })} className="w-full" /></Field>
        {stage && (
          <label className="flex flex-col gap-1 rounded-lg border border-line p-2 text-sm sm:col-span-2">
            <span className="flex items-center gap-2"><input type="checkbox" className="accent-brand-600" checked={f.updateStage} onChange={(e) => setF({ ...f, updateStage: e.target.checked })} />Also set “{stage.name}” progress (now {stage.progress}%)</span>
            {f.updateStage && <span className="flex items-center gap-2"><input type="range" min={0} max={100} step={5} value={f.stage_progress} onChange={(e) => setF({ ...f, stage_progress: Number(e.target.value) })} className="flex-1" /><b>{f.stage_progress}%</b></span>}
          </label>
        )}
        <Field label="Photo" className="sm:col-span-2">
          <div className="flex flex-wrap items-center gap-3">
            <PhotoPicker small multiple={false} onFiles={async (fs) => setFile(await compressImage(fs[0]))} />
            {file && <span className="text-xs text-slate-600">✓ {file.name} ({Math.round(file.size / 1024)} KB) <button className="link text-xs" onClick={() => setFile(null)}>remove</button></span>}
          </div>
        </Field>
        <Field label="Notes" className="sm:col-span-2"><textarea className="input" rows={2} value={f.notes} onChange={(e) => setF({ ...f, notes: e.target.value })} /></Field>
      </div>
      <div className="mt-4 flex justify-end gap-2"><button className="btn-ghost" onClick={onClose}>Cancel</button><button className="btn-primary" onClick={save} disabled={busy}><Save size={16} />{busy ? "Saving…" : "Save"}</button></div>
    </Modal>
  );
}

// ---------------------------------------------------------------- daily work
export function DailyWorkTab({ pid, day, canWrite, onChanged }: { pid: number; day: string; canWrite: boolean; onChanged: () => void }) {
  const [rep, setRep] = useState<any>(null);
  const [acts, setActs] = useState<Activity[]>([]);
  const [modal, setModal] = useState<{ open: boolean; edit: Activity | null }>({ open: false, edit: null });
  const load = useCallback(async () => {
    try {
      const [r, a] = await Promise.all([api(`/api/projects/${pid}/site/report?day=${day}`), api<Activity[]>(`/api/projects/${pid}/site/activities?day=${day}&days=7`)]);
      setRep(r); setActs(a);
    } catch (e: any) { toast(e.message, "err"); }
  }, [pid, day]);
  useEffect(() => { load(); }, [load]);
  const saveRep = async () => {
    try { setRep(await api(`/api/projects/${pid}/site/report`, { method: "PUT", body: { ...rep, report_date: day } })); toast("Daily report saved"); onChanged(); }
    catch (e: any) { toast(e.message, "err"); }
  };
  const byDay = useMemo(() => {
    const m: Record<string, Activity[]> = {};
    acts.forEach((a) => { (m[a.work_date] ||= []).push(a); });
    return Object.entries(m).sort((a, b) => b[0].localeCompare(a[0]));
  }, [acts]);
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_1.2fr]">
      <Card title={`Daily Progress Report – ${prettyDate(day)}`} icon={<FileText size={20} />}
        action={<button className="btn-outline btn-sm" onClick={() => downloadFile(`/api/projects/${pid}/site/dpr.pdf?day=${day}`, `DPR_${day}.pdf`).catch((e) => toast(e.message, "err"))}><Download size={14} />DPR PDF</button>}>
        {!rep ? <p className="text-sm text-slate-500">Loading…</p> : (
          <div className="space-y-3">
            <Field label="Weather"><div className="flex flex-wrap gap-2">{WEATHER.map((w) => <button key={w} disabled={!canWrite} onClick={() => setRep({ ...rep, weather: w })} className={`rounded-full px-3 py-1 text-xs font-semibold ${rep.weather === w ? "bg-brand-600 text-white" : "bg-slate-100 text-navy-ink"}`}>{w}</button>)}</div></Field>
            <Field label="Work done today"><textarea className="input" rows={4} disabled={!canWrite} value={rep.work_done} onChange={(e) => setRep({ ...rep, work_done: e.target.value })} placeholder="Column casting GF completed (12 nos), brick work 2nd layer…" /></Field>
            <Field label="Plan for tomorrow"><textarea className="input" rows={3} disabled={!canWrite} value={rep.next_plan} onChange={(e) => setRep({ ...rep, next_plan: e.target.value })} /></Field>
            <Field label="Remarks / hindrances"><textarea className="input" rows={2} disabled={!canWrite} value={rep.remarks} onChange={(e) => setRep({ ...rep, remarks: e.target.value })} /></Field>
            <div className="flex items-center justify-between"><span className="text-xs text-slate-500">{rep.saved ? "Saved" : "Not saved yet"}</span>{canWrite && <button className="btn-primary" onClick={saveRep}><Save size={16} />Save report</button>}</div>
          </div>
        )}
      </Card>
      <Card title="Activities (last 7 days)" icon={<FileText size={20} />} action={canWrite && <button className="btn-primary btn-sm" onClick={() => setModal({ open: true, edit: null })}><Plus size={14} />Add Activity</button>}>
        {!byDay.length ? <Empty text="No activities in the last 7 days." /> : byDay.map(([d, list]) => (
          <div key={d} className="mb-3">
            <div className="mb-1 text-xs font-bold uppercase text-slate-500">{prettyDate(d)}</div>
            <ul className="divide-y divide-line rounded-lg border border-line">
              {list.map((a) => (
                <li key={a.id} className="flex items-center gap-3 px-3 py-2">
                  {a.photo_url ? <AuthImg src={a.photo_url} className="h-12 w-16 shrink-0 rounded object-cover" /> : <span className="flex h-12 w-16 shrink-0 items-center justify-center rounded bg-slate-100"><Camera size={16} className="text-slate-400" /></span>}
                  <span className="min-w-0 flex-1 text-sm"><span className="font-semibold text-navy-ink">{a.title}</span><span className="block text-xs text-slate-500">{[a.location, a.stage].filter(Boolean).join(" · ")}</span></span>
                  <span className="w-24"><Bar value={a.progress} tone="bg-emerald-500" /><span className="text-[11px] text-slate-500">{a.progress}%</span></span>
                  <Pill s={a.status} />
                  {canWrite && <button className="btn-ghost btn-sm" onClick={() => setModal({ open: true, edit: a })}>Edit</button>}
                  <OwnerDelete entity="activity" id={a.id} title={a.title} onDone={() => { load(); onChanged(); }} />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </Card>
      <ActivityModal open={modal.open} edit={modal.edit} onClose={() => setModal({ open: false, edit: null })} pid={pid} day={modal.edit?.work_date || day} onSaved={() => { load(); onChanged(); }} />
    </div>
  );
}

// ---------------------------------------------------------------- photos
export function PhotosTab({ pid, day, canWrite, onChanged }: { pid: number; day: string; canWrite: boolean; onChanged: () => void }) {
  const [rows, setRows] = useState<Photo[] | null>(null);
  const [big, setBig] = useState<Photo | null>(null);
  const [caption, setCaption] = useState("");
  const [loc, setLoc] = useState("");
  const [busy, setBusy] = useState(false);
  const load = useCallback(async () => { try { setRows(await api<Photo[]>(`/api/projects/${pid}/site/photos?limit=300`)); } catch { setRows([]); } }, [pid]);
  useEffect(() => { load(); }, [load]);
  const upload = async (files: File[]) => {
    if (!files.length) return;
    setBusy(true);
    const gps = await quickGps();  // never waits more than 5 s for the location prompt
    let ok = 0;
    for (const raw of files) {
      const f = await compressImage(raw);
      const fd = new FormData(); fd.append("file", f); fd.append("caption", caption || f.name.replace(/\.[^.]+$/, "")); fd.append("taken_on", day); fd.append("location", loc);
      if (gps.lat != null) { fd.append("latitude", String(gps.lat)); fd.append("longitude", String(gps.lng)); }
      try { await api(`/api/projects/${pid}/site/photos`, { form: fd }); ok++; } catch (e: any) { toast(`${f.name}: ${e.message}`, "err"); }
    }
    setBusy(false); setCaption("");
    if (ok) { toast(`${ok} photo(s) uploaded`); load(); onChanged(); }
  };
  const groups = useMemo(() => {
    const m: Record<string, Photo[]> = {};
    (rows || []).forEach((p) => { (m[p.taken_on] ||= []).push(p); });
    return Object.entries(m).sort((a, b) => b[0].localeCompare(a[0]));
  }, [rows]);
  return (
    <div className="space-y-4">
      {canWrite && (
        <Card title="Upload site photos" icon={<Upload size={20} />}>
          <div className="grid gap-3 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
            <Field label="Caption (what is in the photo)"><input className="input" value={caption} onChange={(e) => setCaption(e.target.value)} placeholder="e.g. Column reinforcement – Block A" /></Field>
            <Field label="Location on site"><input className="input" value={loc} onChange={(e) => setLoc(e.target.value)} placeholder="e.g. Ground floor, rear" /></Field>
            <PhotoPicker busy={busy} onFiles={upload} />
          </div>
          <p className="mt-2 text-xs text-slate-500"><b>Camera</b> opens the phone camera (or the PC webcam); <b>Gallery</b> lets you pick several saved photos. Dated {prettyDate(day)} (change the date at the top). GPS is added when allowed.</p>
        </Card>
      )}
      {!rows ? <p className="text-sm text-slate-500">Loading…</p> : !rows.length ? <Card><Empty text="No site photos yet." /></Card> : groups.map(([d, list]) => (
        <Card key={d} title={prettyDate(d)} icon={<Camera size={18} />}>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4 2xl:grid-cols-6">
            {list.map((p) => (
              <button key={p.id} className="text-left" onClick={() => setBig(p)}>
                <AuthImg src={p.url} className="aspect-[4/3] w-full rounded-lg object-cover" />
                <div className="mt-1 truncate text-xs font-semibold text-navy-ink">{p.caption}</div>
                <div className="truncate text-[11px] text-slate-500">{p.location || "—"}</div>
              </button>
            ))}
          </div>
        </Card>
      ))}
      <Modal open={!!big} onClose={() => setBig(null)} title={big?.caption || ""} wide>
        {big && <>
          <AuthImg src={big.url} className="max-h-[70vh] w-full rounded-lg object-contain" />
          <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-sm text-slate-600">
            <span>{prettyDate(big.taken_on)} {big.location && `· ${big.location}`} {big.latitude != null && <a className="link ml-1" target="_blank" rel="noreferrer" href={`https://www.openstreetmap.org/?mlat=${big.latitude}&mlon=${big.longitude}#map=18/${big.latitude}/${big.longitude}`}>GPS map</a>}</span>
            <OwnerDelete entity="photo" id={big.id} title={big.caption || "photo"} label="Delete" onDone={() => { setBig(null); load(); onChanged(); }} />
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-2"><PhotoCheckButton fileId={big.file_id} /></div>
        </>}
      </Modal>
    </div>
  );
}

// ---------------------------------------------------------------- quality
export function QualityTab({ pid, canWrite, onChanged }: { pid: number; canWrite: boolean; onChanged: () => void }) {
  const [rows, setRows] = useState<QC[] | null>(null);
  const [add, setAdd] = useState({ item: "", stage: "structure", standard: "" });
  const load = useCallback(async () => { try { setRows(await api<QC[]>(`/api/projects/${pid}/site/quality`)); } catch (e: any) { toast(e.message, "err"); } }, [pid]);
  useEffect(() => { load(); }, [load]);
  const set = async (q: QC, body: any) => { try { await api(`/api/site/quality/${q.id}`, { method: "PATCH", body }); load(); onChanged(); } catch (e: any) { toast(e.message, "err"); } };
  const stages = ["foundation", "structure", "masonry", "services", "finishing"];
  const counts = { checked: rows?.filter((r) => r.status === "checked").length || 0, failed: rows?.filter((r) => r.status === "failed").length || 0, pending: rows?.filter((r) => r.status === "pending").length || 0 };
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap gap-2"><Badge color="green">{counts.checked} checked</Badge><Badge color="red">{counts.failed} failed</Badge><Badge color="amber">{counts.pending} pending</Badge></div>
      {!rows ? <p className="text-sm text-slate-500">Loading…</p> : stages.map((st) => {
        const list = rows.filter((r) => r.stage === st);
        if (!list.length) return null;
        return (
          <Card key={st} title={st[0].toUpperCase() + st.slice(1)} icon={<ShieldAlert size={18} />}>
            <ul className="divide-y divide-line">
              {list.map((q) => (
                <li key={q.id} className="grid gap-2 py-3 md:grid-cols-[1.4fr_1fr_auto] md:items-center">
                  <div><div className="text-sm font-semibold text-navy-ink">{q.item}</div><div className="text-xs text-slate-500">{q.standard}</div>
                    {q.checked_on && <div className="text-[11px] text-slate-400">{q.status} on {prettyDate(q.checked_on)}{q.checked_by && ` by ${q.checked_by}`}</div>}</div>
                  <input className="input py-1.5 text-sm" placeholder="Remarks / measured value" defaultValue={q.remarks} disabled={!canWrite} onBlur={(e) => e.target.value !== q.remarks && set(q, { remarks: e.target.value })} />
                  <div className="flex gap-1">
                    {(["checked", "failed", "pending"] as const).map((s) => (
                      <button key={s} disabled={!canWrite} onClick={() => set(q, { status: s })}
                        className={`rounded-lg px-2.5 py-1.5 text-xs font-semibold ${q.status === s ? (s === "checked" ? "bg-emerald-600 text-white" : s === "failed" ? "bg-red-600 text-white" : "bg-amber-500 text-white") : "bg-slate-100 text-navy-ink"}`}>{s === "checked" ? "OK" : s === "failed" ? "Fail" : "Pending"}</button>
                    ))}
                    <OwnerDelete entity="quality" id={q.id} title={q.item} onDone={load} />
                  </div>
                </li>
              ))}
            </ul>
          </Card>
        );
      })}
      {canWrite && (
        <Card title="Add a check" icon={<Plus size={18} />}>
          <div className="grid gap-3 sm:grid-cols-[2fr_1fr_2fr_auto] sm:items-end">
            <Field label="Check item"><input className="input" value={add.item} onChange={(e) => setAdd({ ...add, item: e.target.value })} /></Field>
            <Field label="Stage"><select className="input" value={add.stage} onChange={(e) => setAdd({ ...add, stage: e.target.value })}>{stages.map((s) => <option key={s}>{s}</option>)}</select></Field>
            <Field label="Standard / tolerance"><input className="input" value={add.standard} onChange={(e) => setAdd({ ...add, standard: e.target.value })} /></Field>
            <button className="btn-primary" onClick={async () => { try { await api(`/api/projects/${pid}/site/quality`, { body: add }); setAdd({ item: "", stage: add.stage, standard: "" }); load(); } catch (e: any) { toast(e.message, "err"); } }}><Plus size={16} />Add</button>
          </div>
        </Card>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- materials
export function MaterialsTab({ pid, day, canWrite, onChanged }: { pid: number; day: string; canWrite: boolean; onChanged: () => void }) {
  const [d, setD] = useState<any>(null);
  const [f, setF] = useState<any>({ code: "cement", kind: "received", qty: "", rate: "", supplier: "", bill_no: "", notes: "" });
  const load = useCallback(async () => { try { setD(await api(`/api/projects/${pid}/site/materials`)); } catch (e: any) { toast(e.message, "err"); } }, [pid]);
  useEffect(() => { load(); }, [load]);
  const save = async () => {
    if (!Number(f.qty)) return toast("Enter the quantity", "err");
    try { await api(`/api/projects/${pid}/site/materials`, { body: { ...f, qty: Number(f.qty), rate: f.rate ? Number(f.rate) : null, entry_date: day } });
      toast("Saved"); setF({ ...f, qty: "", bill_no: "", notes: "" }); load(); onChanged(); }
    catch (e: any) { toast(e.message, "err"); }
  };
  const lib = d?.library || [];
  const unit = lib.find((x: any) => x.code === f.code)?.unit || "";
  return (
    <div className="space-y-4">
      {canWrite && (
        <Card title={`Record material – ${prettyDate(day)}`} icon={<Plus size={18} />}>
          <div className="grid gap-3 sm:grid-cols-3 xl:grid-cols-7 xl:items-end">
            <Field label="Material" className="sm:col-span-2"><select className="input" value={f.code} onChange={(e) => setF({ ...f, code: e.target.value, rate: lib.find((x: any) => x.code === e.target.value)?.rate ?? "" })}>{lib.map((x: any) => <option key={x.code} value={x.code}>{x.name} ({x.unit})</option>)}</select></Field>
            <Field label="Type"><select className="input" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}><option value="received">Received at site</option><option value="used">Used / issued</option></select></Field>
            <Field label={`Quantity ${unit && `(${unit})`}`}><input className="input" type="number" value={f.qty} onChange={(e) => setF({ ...f, qty: e.target.value })} /></Field>
            <Field label="Rate ₹ (optional)"><input className="input" type="number" value={f.rate} onChange={(e) => setF({ ...f, rate: e.target.value })} /></Field>
            <Field label="Supplier / bill no"><input className="input" value={f.supplier} onChange={(e) => setF({ ...f, supplier: e.target.value })} placeholder="Supplier" /></Field>
            <button className="btn-primary" onClick={save}><Save size={16} />Save</button>
          </div>
        </Card>
      )}
      <Card title="Material tracking – planned vs received vs used" icon={<FileSpreadsheet size={18} />}>
        {!d ? <p className="text-sm text-slate-500">Loading…</p> : (
          <>
            <p className="mb-2 text-xs text-slate-500">{d.estimate ? `Planned quantities from estimate v${d.estimate.version} – ${d.estimate.title}.` : "No saved estimate – planned quantities appear after you save one in Estimate."}</p>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px]">
                <thead><tr>{["Material", "Planned", "Received", "Used", "Stock at site", "Received %"].map((h) => <th key={h} className="table-th">{h}</th>)}</tr></thead>
                <tbody>
                  {(d.items as MatRow[]).filter((m) => m.planned || m.received || m.used).map((m) => (
                    <tr key={m.name}>
                      <td className="table-td font-semibold text-navy-ink">{m.name}</td>
                      <td className="table-td">{m.planned ? `${n0(m.planned)} ${m.unit}` : "—"}</td>
                      <td className="table-td">{n0(m.received)}</td>
                      <td className="table-td">{n0(m.used)}</td>
                      <td className={`table-td font-semibold ${m.stock < 0 ? "text-red-600" : ""}`}>{n0(m.stock)}</td>
                      <td className="table-td w-48">{m.pct != null ? <div className="flex items-center gap-2"><Bar value={m.pct} /><span className="text-xs">{Math.round(m.pct)}%</span></div> : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </Card>
      <Card title="Entries" icon={<FileText size={18} />}>
        {!d?.entries?.length ? <Empty text="No entries yet." /> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px]">
              <thead><tr>{["Date", "Material", "Type", "Qty", "Rate", "Supplier", ""].map((h) => <th key={h} className="table-th">{h}</th>)}</tr></thead>
              <tbody>
                {d.entries.map((e: any) => (
                  <tr key={e.id}>
                    <td className="table-td">{prettyDate(e.entry_date)}</td><td className="table-td">{e.name}</td>
                    <td className="table-td"><Badge color={e.kind === "received" ? "green" : "blue"}>{e.kind}</Badge></td>
                    <td className="table-td">{n0(e.qty)} {e.unit}</td><td className="table-td">{e.rate ? `₹${inr(e.rate)}` : "—"}</td>
                    <td className="table-td">{[e.supplier, e.bill_no].filter(Boolean).join(" · ") || "—"}</td>
                    <td className="table-td"><OwnerDelete entity="material" id={e.id} title={`${e.name} ${e.kind} ${n0(e.qty)} ${e.unit}`} onDone={() => { load(); onChanged(); }} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------- manpower
export function ManpowerTab({ pid, day, canWrite, onChanged }: { pid: number; day: string; canWrite: boolean; onChanged: () => void }) {
  const [att, setAtt] = useState<any>(null);
  const [trades, setTrades] = useState<any[]>([]);
  const [marks, setMarks] = useState<Record<number, { status: string; ot_hours: number }>>({});
  const [nw, setNw] = useState<any>({ name: "", trade: "mason", day_wage: "", phone: "", contractor: "" });
  const [addOpen, setAddOpen] = useState(false);
  const load = useCallback(async () => {
    try {
      const [a, w] = await Promise.all([api<any>(`/api/projects/${pid}/site/attendance?day=${day}`), api<any>(`/api/projects/${pid}/site/workers`)]);
      setAtt(a); setTrades(w.trades);
      setMarks(Object.fromEntries(a.rows.map((r: any) => [r.id, { status: r.status || "", ot_hours: r.ot_hours || 0 }])));
    } catch (e: any) { toast(e.message, "err"); }
  }, [pid, day]);
  useEffect(() => { load(); }, [load]);
  const saveAtt = async () => {
    const entries = Object.entries(marks).filter(([, v]) => v.status).map(([id, v]) => ({ worker_id: Number(id), ...v }));
    if (!entries.length) return toast("Mark at least one worker", "err");
    try { setAtt(await api(`/api/projects/${pid}/site/attendance`, { body: { work_date: day, entries } })); toast("Attendance saved"); onChanged(); }
    catch (e: any) { toast(e.message, "err"); }
  };
  const allPresent = () => setMarks(Object.fromEntries(Object.entries(marks).map(([k, v]) => [k, { ...v, status: "present" }])));
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.5fr_1fr]">
      <Card title={`Attendance – ${prettyDate(day)}`} icon={<UserPlus size={18} />}
        action={canWrite && <div className="flex gap-2"><button className="btn-ghost btn-sm" onClick={allPresent}>All present</button><button className="btn-outline btn-sm" onClick={() => setAddOpen(true)}><Plus size={14} />Add worker</button></div>}>
        {!att ? <p className="text-sm text-slate-500">Loading…</p> : !att.rows.length ? <Empty text="No workers yet – add your masons, helpers (chithal), bar benders… once; then mark attendance daily." /> : (
          <>
            <ul className="divide-y divide-line">
              {att.rows.map((w: any) => (
                <li key={w.id} className="flex flex-wrap items-center gap-3 py-2">
                  <span className="flex h-9 w-9 items-center justify-center rounded-full bg-amber-100 text-sm font-bold text-amber-700">{w.name.slice(0, 1)}</span>
                  <span className="min-w-[140px] flex-1 text-sm"><b className="text-navy-ink">{w.name}</b><span className="block text-xs text-slate-500">{w.trade_name} · ₹{inr(w.day_wage || 0)}/day{w.contractor && ` · ${w.contractor}`}</span></span>
                  <div className="flex gap-1">
                    {([["present", "P"], ["half", "½"], ["absent", "A"]] as const).map(([s, l]) => (
                      <button key={s} disabled={!canWrite} onClick={() => setMarks({ ...marks, [w.id]: { ...(marks[w.id] || { ot_hours: 0 }), status: s } })}
                        className={`h-8 w-9 rounded-lg text-sm font-bold ${marks[w.id]?.status === s ? (s === "present" ? "bg-emerald-600 text-white" : s === "half" ? "bg-amber-500 text-white" : "bg-red-500 text-white") : "bg-slate-100 text-navy-ink"}`}>{l}</button>
                    ))}
                  </div>
                  <label className="flex items-center gap-1 text-xs text-slate-500">OT h<input type="number" min={0} max={8} className="input w-14 py-1" disabled={!canWrite} value={marks[w.id]?.ot_hours || 0} onChange={(e) => setMarks({ ...marks, [w.id]: { ...(marks[w.id] || { status: "" }), ot_hours: Number(e.target.value) } })} /></label>
                  <OwnerDelete entity="worker" id={w.id} title={w.name} onDone={() => { load(); onChanged(); }} />
                </li>
              ))}
            </ul>
            {canWrite && <div className="mt-3 flex justify-end"><button className="btn-primary" onClick={saveAtt}><Save size={16} />Save attendance</button></div>}
          </>
        )}
      </Card>
      <Card title="Today's manpower" icon={<UserPlus size={18} />}>
        {!att ? null : (
          <>
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-lg bg-slate-50 px-3 py-2"><div className="text-xs text-slate-500">Present</div><div className="text-xl font-extrabold text-navy-ink">{n0(att.summary.present)}</div></div>
              <div className="rounded-lg bg-slate-50 px-3 py-2"><div className="text-xs text-slate-500">Wages today</div><div className="text-xl font-extrabold text-navy-ink">₹{inr(att.summary.wages)}</div></div>
            </div>
            <ul className="mt-3 divide-y divide-line text-sm">{att.summary.by_trade.map((t: any) => <li key={t.trade} className="flex justify-between py-1.5"><span>{t.name}</span><b>{n0(t.count)}</b></li>)}</ul>
            <p className="mt-2 text-xs text-slate-500">Day wages come from the rate library (Settings / Estimate → Rate Library) unless you set a worker's own wage. Overtime = wage ÷ 8 per hour.</p>
          </>
        )}
      </Card>
      <Modal open={addOpen} onClose={() => setAddOpen(false)} title="Add worker">
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Name"><input className="input" value={nw.name} onChange={(e) => setNw({ ...nw, name: e.target.value })} /></Field>
          <Field label="Trade"><select className="input" value={nw.trade} onChange={(e) => setNw({ ...nw, trade: e.target.value })}>{trades.map((t) => <option key={t.code} value={t.code}>{t.name}</option>)}</select></Field>
          <Field label="Own day wage ₹ (blank = rate library)"><input className="input" type="number" value={nw.day_wage} onChange={(e) => setNw({ ...nw, day_wage: e.target.value })} /></Field>
          <Field label="Phone"><input className="input" value={nw.phone} onChange={(e) => setNw({ ...nw, phone: e.target.value })} /></Field>
          <Field label="Contractor / maistry" className="sm:col-span-2"><input className="input" value={nw.contractor} onChange={(e) => setNw({ ...nw, contractor: e.target.value })} /></Field>
        </div>
        <div className="mt-4 flex justify-end"><button className="btn-primary" onClick={async () => {
          try { await api(`/api/projects/${pid}/site/workers`, { body: { ...nw, day_wage: nw.day_wage ? Number(nw.day_wage) : null } }); setNw({ ...nw, name: "", phone: "" }); setAddOpen(false); load(); toast("Worker added"); }
          catch (e: any) { toast(e.message, "err"); }
        }}><Save size={16} />Add</button></div>
      </Modal>
    </div>
  );
}

// ---------------------------------------------------------------- safety & issues
const KIND_LABEL: Record<string, string> = { toolbox: "Toolbox talk", ppe: "PPE check", inspection: "Safety inspection", near_miss: "Near miss", incident: "Incident", issue: "Site issue", delay: "Delay" };

export function SafetyTab({ pid, day, canWrite, onChanged }: { pid: number; day: string; canWrite: boolean; onChanged: () => void }) {
  const [rows, setRows] = useState<any[] | null>(null);
  const [f, setF] = useState<any>({ kind: "toolbox", title: "", details: "", severity: "low", delay_days: "" });
  const load = useCallback(async () => { try { setRows(await api<any[]>(`/api/projects/${pid}/site/safety`)); } catch { setRows([]); } }, [pid]);
  useEffect(() => { load(); }, [load]);
  const save = async () => {
    if (!f.title.trim()) return toast("Enter a title", "err");
    try { await api(`/api/projects/${pid}/site/safety`, { body: { ...f, record_date: day, delay_days: Number(f.delay_days) || 0 } }); setF({ ...f, title: "", details: "", delay_days: "" }); load(); onChanged(); toast("Recorded"); }
    catch (e: any) { toast(e.message, "err"); }
  };
  const close = async (r: any) => { const action = window.prompt("Action taken / how it was closed", r.action || ""); if (action === null) return;
    try { await api(`/api/site/safety/${r.id}`, { method: "PATCH", body: { status: "closed", action } }); load(); onChanged(); } catch (e: any) { toast(e.message, "err"); } };
  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_1.5fr]">
      {canWrite && (
        <Card title={`Record – ${prettyDate(day)}`} icon={<ShieldAlert size={18} />}>
          <div className="grid gap-3">
            <Field label="Type"><select className="input" value={f.kind} onChange={(e) => setF({ ...f, kind: e.target.value })}>{Object.entries(KIND_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></Field>
            <Field label="Title"><input className="input" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder={f.kind === "delay" ? "e.g. Steel delivery late" : "e.g. Helmets & shoes checked"} /></Field>
            <Field label="Details"><textarea className="input" rows={3} value={f.details} onChange={(e) => setF({ ...f, details: e.target.value })} /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Severity"><select className="input" value={f.severity} onChange={(e) => setF({ ...f, severity: e.target.value })}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option></select></Field>
              {f.kind === "delay" && <Field label="Delay (days)"><input className="input" type="number" value={f.delay_days} onChange={(e) => setF({ ...f, delay_days: e.target.value })} /></Field>}
            </div>
            <button className="btn-primary" onClick={save}><Save size={16} />Save</button>
          </div>
        </Card>
      )}
      <Card title="Safety records, issues & delays" icon={<ShieldAlert size={18} />}>
        {!rows ? <p className="text-sm text-slate-500">Loading…</p> : !rows.length ? <Empty text="Nothing recorded yet." /> : (
          <ul className="divide-y divide-line">
            {rows.map((r) => (
              <li key={r.id} className="flex flex-wrap items-start gap-3 py-2.5">
                <span className="min-w-0 flex-1 text-sm"><b className="text-navy-ink">{r.title}</b>
                  <span className="block text-xs text-slate-500">{KIND_LABEL[r.kind]} · {prettyDate(r.record_date)} · {r.severity}{r.delay_days ? ` · ${r.delay_days} day delay` : ""}</span>
                  {r.details && <span className="block text-xs text-slate-600">{r.details}</span>}
                  {r.action && <span className="block text-xs text-emerald-700">Action: {r.action}</span>}</span>
                <Pill s={r.status} />
                {canWrite && r.status === "open" && <button className="btn-outline btn-sm" onClick={() => close(r)}>Close</button>}
                <OwnerDelete entity="safety" id={r.id} title={r.title} onDone={load} />
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------- reports
export function ReportsTab({ pid, day, code }: { pid: number; day: string; code: string }) {
  const [start, setStart] = useState(() => day.slice(0, 8) + "01");
  const [end, setEnd] = useState(day);
  const dl = (path: string, name: string) => downloadFile(path, name).catch((e) => toast(e.message, "err"));
  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
      <Card title="Daily Progress Report (DPR)" icon={<FileText size={18} />}>
        <p className="mb-3 text-sm text-slate-600">One-page PDF for {prettyDate(day)}: progress, work done, activities, manpower, materials, quality checks, safety, photos.</p>
        <button className="btn-primary" onClick={() => dl(`/api/projects/${pid}/site/dpr.pdf?day=${day}`, `${code}_DPR_${day}.pdf`)}><Download size={16} />Download DPR PDF</button>
      </Card>
      <Card title="Site report (Excel)" icon={<FileSpreadsheet size={18} />}>
        <p className="mb-3 text-sm text-slate-600">Schedule, activities, daily reports, materials, attendance with wages, quality and safety for a period.</p>
        <div className="flex flex-wrap items-end gap-2">
          <Field label="From"><input type="date" className="input" value={start} onChange={(e) => setStart(e.target.value)} /></Field>
          <Field label="To"><input type="date" className="input" value={end} onChange={(e) => setEnd(e.target.value)} /></Field>
          <button className="btn-primary" onClick={() => dl(`/api/projects/${pid}/site/report.xlsx?start=${start}&end=${end}`, `${code}_Site_${start}_${end}.xlsx`)}><Download size={16} />Download Excel</button>
        </div>
      </Card>
    </div>
  );
}

export { today };
