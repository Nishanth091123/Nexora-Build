/** 1.14 – Part 6: Building approval.
 *  Site & owner details → rule check (setbacks / height / FSI / coverage, required vs provided) → ONE approval
 *  drawing sheet (A1 / A2 / A3 PDF, CAD colours, DXF) → fee calculator (your own rates) → approval stages →
 *  documents checklist. Nothing is guessed: missing details are asked for. */
import { useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2, CircleAlert, CircleHelp, Download, Eye, FileText, IndianRupee, ListChecks, MapPin, Save, Stamp } from "lucide-react";
import { Card, Empty, Field, toast } from "../ui";
import { api, API_BASE, getToken, inr } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import type { Plan } from "../../lib/plan";
import PermitChecklist from "../PermitChecklist";

type Info = Record<string, any>;
type Stage = { key: string; label: string; done: boolean; date: string; ref: string };
type Fee = { name: string; basis: string; rate: number | null; amount?: number | null; basis_label?: string };
type Data = { site_info: Info; authority: string; authorities: Record<string, string>; stages: Stage[]; fee_rates: Fee[]; fee_basis: Record<string, string>; required: { key: string; label: string }[] };
type Row = { item: string; required: string; provided: string; status: "ok" | "fail" | "check" };
type Check = { rows: Row[]; fails: number; checks: number; missing: string[]; note: string; fees: Fee[]; fee_total: number; estimate_total: number | null; estimate_label: string; area: any };

const FIELDS: [string, string, string?][] = [
  ["owner_name", "Owner name * (as in patta / deed)"], ["co_owner", "Co-owner (if any)"], ["owner_address", "Owner address"],
  ["survey_no", "Survey / S.F. No. *"], ["subdivision", "Sub-division"], ["patta_no", "Patta No."], ["door_no", "Door No."],
  ["plot_no", "Plot No."], ["layout_name", "Layout / Nagar name"], ["layout_approval_no", "Layout approval No."],
  ["village", "Village *"], ["taluk", "Taluk *"], ["district", "District *"], ["ward", "Ward / Block"],
  ["road_name", "Road / street name"], ["landmark", "Landmark (key plan)"], ["authority_place", "Local body name (e.g. Kilvelur Town Panchayat)"],
  ["engineer_name", "Licensed engineer / surveyor"], ["engineer_reg_no", "Reg. No."],
];

async function postBlob(path: string, body: any): Promise<Blob> {
  const token = getToken();
  const res = await fetch(API_BASE + path, { method: "POST", headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: JSON.stringify(body) });
  if (!res.ok) {
    let msg = "Download failed", qs: string[] = [];
    try { const d = await res.json(); msg = typeof d.detail === "string" ? d.detail : d.detail?.message || msg; qs = d.detail?.questions || []; } catch { /* ignore */ }
    throw Object.assign(new Error(qs.length ? `${msg}: ${qs.join(" ")}` : msg), { questions: qs });
  }
  return res.blob();
}
const save = (blob: Blob, name: string) => {
  const url = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = url; a.download = name;
  document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 5000);
};

export default function ApprovalPanel({ pid, plan, saved, dirty, code, canEdit }: {
  pid: number; plan: Plan; saved: { id: number; version: number } | null; dirty: boolean; code: string; canEdit: boolean;
}) {
  const { user } = useAuth();
  const isOwner = user?.role === "owner";
  const [d, setD] = useState<Data | null>(null);
  const [info, setInfo] = useState<Info>({});
  const [infoDirty, setInfoDirty] = useState(false);
  const [chk, setChk] = useState<Check | null>(null);
  const [size, setSize] = useState("A1");
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState("");
  const [qs, setQs] = useState<string[]>([]);
  const [rates, setRates] = useState<Fee[]>([]);
  const [ratesDirty, setRatesDirty] = useState(false);
  const [permitKey, setPermitKey] = useState(0);
  const timer = useRef<number | null>(null);

  const load = useCallback(() => api<Data>(`/api/projects/${pid}/approval`).then((r) => {
    setD(r); setInfo(r.site_info); setSize(r.site_info.sheet_size || "A1"); setRates(r.fee_rates); setInfoDirty(false); setRatesDirty(false);
  }).catch((e) => toast(e.message, "err")), [pid]);
  useEffect(() => { load(); }, [load]);

  const runCheck = useCallback(() => {
    api<Check>(`/api/projects/${pid}/approval/check`, { body: { plan, site_info: info } }).then(setChk).catch((e) => toast(e.message, "err"));
  }, [pid, plan, info]);
  useEffect(() => {
    if (!d) return;
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(runCheck, 500);
  }, [d, JSON.stringify(plan.levels.map((l) => l.rooms)), info.allowed_fsi, info.allowed_coverage_pct, info.rwh]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  if (!d) return <Card><Empty text="Loading approval details…" /></Card>;
  const set = (k: string, v: any) => { setInfo({ ...info, [k]: v }); setInfoDirty(true); };
  const saveInfo = async (authority?: string) => {
    setBusy("info");
    try {
      const r = await api<Data>(`/api/projects/${pid}/approval`, { method: "PUT", body: { site_info: { ...info, sheet_size: size }, ...(authority ? { authority } : {}) } });
      setD(r); setInfo(r.site_info); setInfoDirty(false); setQs([]); toast("Approval details saved"); if (authority) setPermitKey((k) => k + 1);
      runCheck();
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(""); }
  };
  const tag = saved && !dirty ? `v${saved.version}` : "draft";
  const sheet = async (kind: "pdf" | "cad" | "dxf" | "preview") => {
    setBusy(kind); setQs([]);
    try {
      if (infoDirty) await api(`/api/projects/${pid}/approval`, { method: "PUT", body: { site_info: { ...info, sheet_size: size } } });
      const q = new URLSearchParams({ kind: kind === "dxf" ? "dxf" : "pdf", style: kind === "cad" ? "cad" : "paper", size, version: saved && !dirty ? String(saved.version) : "draft" });
      const blob = await postBlob(`/api/projects/${pid}/approval/sheet?${q}`, { plan, site_info: info });
      if (kind === "preview") { if (preview) URL.revokeObjectURL(preview); setPreview(URL.createObjectURL(blob)); }
      else save(blob, `${code}_Approval_Drawing_${kind === "dxf" ? "" : size + "_"}${tag}${kind === "cad" ? "_CAD" : ""}.${kind === "dxf" ? "dxf" : "pdf"}`);
      setInfoDirty(false);
    } catch (e: any) { setQs(e.questions || []); toast(e.message, "err"); } finally { setBusy(""); }
  };
  const saveRates = async () => {
    try { await api(`/api/approval/fee-rates`, { method: "PUT", body: { authority: d.authority, rows: rates } }); setRatesDirty(false); toast("Fee rates saved"); runCheck(); }
    catch (e: any) { toast(e.message, "err"); }
  };
  const copyFees = async () => {
    if (!chk) return;
    try {
      const cur = await api<any>(`/api/projects/${pid}/permit`);
      const old: Record<string, any> = Object.fromEntries((cur.fees || []).map((f: any) => [f.name, f]));
      const fees = chk.fees.filter((f) => f.amount != null).map((f) => ({ name: f.name, amount: f.amount, paid: !!old[f.name]?.paid, receipt: old[f.name]?.receipt || "" }));
      const rest = (cur.fees || []).filter((f: any) => !fees.some((x) => x.name === f.name));
      await api(`/api/projects/${pid}/permit`, { method: "PUT", body: { fees: [...fees, ...rest] } });
      setPermitKey((k) => k + 1); toast("Fee amounts copied to the approval checklist");
    } catch (e: any) { toast(e.message, "err"); }
  };
  const stage = async (s: Stage, patch: Partial<Stage>) => {
    const n = { ...s, ...patch };
    try {
      const r = await api<{ stages: Stage[] }>(`/api/projects/${pid}/approval/stage`, { method: "PUT", body: { key: n.key, done: n.done, date: n.done ? n.date || null : null, ref: n.ref } });
      setD({ ...d, stages: r.stages });
    } catch (e: any) { toast(e.message, "err"); }
  };
  const icon = (s: string) => s === "ok" ? <CheckCircle2 size={15} className="text-emerald-600" /> : s === "fail" ? <CircleAlert size={15} className="text-red-600" /> : <CircleHelp size={15} className="text-amber-600" />;
  const missing = d.required.filter((r) => !String(info[r.key] || "").trim());

  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-[1.25fr_1fr]">
        <Card title="Site & owner details (for the approval drawing)" icon={<MapPin size={20} />}
          action={<button className="btn-primary btn-sm" disabled={!canEdit || !infoDirty || busy === "info"} onClick={() => saveInfo()}><Save size={14} />Save</button>}>
          <div className="mb-3 grid gap-3 sm:grid-cols-3">
            <Field label="Approval authority">
              <select className="input" value={d.authority} disabled={!canEdit} onChange={(e) => saveInfo(e.target.value)}>
                {Object.entries(d.authorities).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
              </select>
            </Field>
            <Field label="Owner title">
              <select className="input" value={info.owner_title || ""} onChange={(e) => set("owner_title", e.target.value)}>
                <option value="">Thiru./Tmt.</option><option value="mr">Thiru.</option><option value="mrs">Tmt.</option><option value="ms">Selvi.</option>
              </select>
            </Field>
            <Field label="Sheet size"><select className="input" value={size} onChange={(e) => { setSize(e.target.value); setInfoDirty(true); }}>{["A1", "A2", "A3"].map((s) => <option key={s}>{s}</option>)}</select></Field>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {FIELDS.map(([k, l]) => (
              <Field key={k} label={l}><input className={`input ${l.includes("*") && !String(info[k] || "").trim() ? "border-amber-400" : ""}`} value={info[k] || ""} onChange={(e) => set(k, e.target.value)} /></Field>
            ))}
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <Field label="Permitted FSI (from the local body)"><input className="input" type="number" step="0.05" min="0" value={info.allowed_fsi ?? ""} onChange={(e) => set("allowed_fsi", e.target.value)} placeholder="blank = not checked" /></Field>
            <Field label="Permitted plot coverage %"><input className="input" type="number" step="1" min="0" max="100" value={info.allowed_coverage_pct ?? ""} onChange={(e) => set("allowed_coverage_pct", e.target.value)} placeholder="blank = not checked" /></Field>
          </div>
          <div className="mt-3 flex flex-wrap gap-4 text-sm">
            {([["rwh", "Rain water harvesting pit"], ["sump", "Sump"], ["septic", "Septic tank"]] as [string, string][]).map(([k, l]) => (
              <label key={k} className="flex items-center gap-2"><input type="checkbox" className="h-4 w-4 accent-brand-600" checked={k === "rwh" ? info.rwh !== false : !!info[k]} onChange={(e) => set(k, e.target.checked)} />{l} on site plan</label>
            ))}
          </div>
          <Field label="Extra note on the drawing (optional)" className="mt-3"><input className="input" value={info.extra_note || ""} onChange={(e) => set("extra_note", e.target.value)} /></Field>
          {missing.length > 0 && <p className="mt-2 text-xs text-amber-700">Needed before the drawing can be made: {missing.map((m) => m.label).join(", ")}.</p>}
        </Card>

        <Card title={`Rule check${chk ? (chk.fails ? ` · ${chk.fails} not OK` : " · all OK") : ""}`} icon={<ListChecks size={20} />}>
          {!chk ? <Empty text="Checking…" /> : (
            <>
              <div className="overflow-hidden rounded-lg border border-line text-sm">
                <table className="w-full">
                  <thead className="bg-slate-50 text-left text-xs text-slate-500"><tr><th className="px-2 py-1.5">Item</th><th className="px-2 py-1.5">Required</th><th className="px-2 py-1.5">Provided</th><th /></tr></thead>
                  <tbody>{chk.rows.map((r) => (
                    <tr key={r.item} className={`border-t border-line ${r.status === "fail" ? "bg-red-50" : ""}`}>
                      <td className="px-2 py-1.5">{r.item}</td><td className="px-2 py-1.5 text-slate-600">{r.required}</td>
                      <td className="px-2 py-1.5 font-medium">{r.provided}</td><td className="px-2 py-1.5">{icon(r.status)}</td>
                    </tr>))}</tbody>
                </table>
              </div>
              <p className="mt-2 text-[11px] text-slate-500">{chk.note}</p>
              {chk.fails > 0 && <p className="mt-1 text-xs font-semibold text-red-700">Fix the items marked red in the 2D editor (move / resize rooms) before submitting.</p>}
            </>
          )}
        </Card>
      </div>

      <Card title="Approval drawing (one sheet)" icon={<Stamp size={20} />}
        action={<div className="flex flex-wrap gap-2">
          <button className="btn-outline btn-sm" disabled={!!busy} onClick={() => sheet("preview")}><Eye size={14} />{busy === "preview" ? "Making…" : "Preview"}</button>
          <button className="btn-primary btn-sm" disabled={!!busy} onClick={() => sheet("pdf")}><Download size={14} />PDF ({size})</button>
          <button className="btn-outline btn-sm" disabled={!!busy} onClick={() => sheet("cad")}><Download size={14} />PDF (CAD colours)</button>
          <button className="btn-outline btn-sm" disabled={!!busy} onClick={() => sheet("dxf")}><Download size={14} />DXF (AutoCAD)</button>
        </div>}>
        <p className="text-sm text-slate-600">Site plan with the setbacks you actually provide, every floor plan, front elevation, section A-A, key plan, area statement,
          setback check, door &amp; window schedule, notes, owner and licensed-engineer signature boxes and an empty “for office use” box. No seal or signature is printed.
          {(!saved || dirty) && <span className="text-amber-700"> Not saved – the sheet is marked “draft”.</span>}</p>
        {qs.length > 0 && <div className="mt-2 rounded-lg bg-amber-50 p-3 text-sm text-amber-900"><b>Please fill:</b><ul className="ml-4 list-disc">{qs.map((q) => <li key={q}>{q}</li>)}</ul></div>}
        {preview && <iframe title="Approval drawing preview" src={preview} className="mt-3 h-[640px] w-full rounded-lg border border-line" />}
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card title={`Fee calculator · ${d.authorities[d.authority] || d.authority}`} icon={<IndianRupee size={20} />}
          action={isOwner && <button className="btn-outline btn-sm" disabled={!ratesDirty} onClick={saveRates}><Save size={14} />Save my rates</button>}>
          <p className="mb-2 text-xs text-slate-500">Enter the rates from the local body's current fee order – the app never assumes a rate. Saved once per authority, used for every project.</p>
          <div className="overflow-x-auto rounded-lg border border-line">
            <table className="w-full min-w-[560px] text-sm">
              <thead className="bg-slate-50 text-left text-xs text-slate-500"><tr><th className="px-2 py-1.5">Fee</th><th className="px-2 py-1.5">Basis</th><th className="w-24 px-2 py-1.5">Rate</th><th className="px-2 py-1.5 text-right">Amount (₹)</th></tr></thead>
              <tbody>{rates.map((f, i) => {
                const calc = chk?.fees[i];
                return (
                  <tr key={i} className="border-t border-line">
                    <td className="px-2 py-1"><input className="input py-1 text-sm" disabled={!isOwner} value={f.name} onChange={(e) => { setRates(rates.map((x, j) => (j === i ? { ...x, name: e.target.value } : x))); setRatesDirty(true); }} /></td>
                    <td className="px-2 py-1"><select className="input py-1 text-xs" disabled={!isOwner} value={f.basis} onChange={(e) => { setRates(rates.map((x, j) => (j === i ? { ...x, basis: e.target.value } : x))); setRatesDirty(true); }}>
                      {Object.entries(d.fee_basis).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></td>
                    <td className="px-2 py-1"><input className="input py-1 text-right text-sm" type="number" min="0" step="0.01" disabled={!isOwner} value={f.rate ?? ""} onChange={(e) => { setRates(rates.map((x, j) => (j === i ? { ...x, rate: e.target.value === "" ? null : Number(e.target.value) } : x))); setRatesDirty(true); }} /></td>
                    <td className="px-2 py-1 text-right font-semibold">{!ratesDirty && calc?.amount != null ? inr(calc.amount) : "—"}</td>
                  </tr>
                );
              })}
                <tr className="border-t border-line bg-brand-50 font-bold"><td className="px-2 py-1.5" colSpan={3}>Total</td><td className="px-2 py-1.5 text-right">{chk && !ratesDirty ? inr(chk.fee_total) : "—"}</td></tr>
              </tbody>
            </table>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
            {isOwner && <button className="btn-ghost btn-sm" onClick={() => { setRates([...rates, { name: "New fee", basis: "fixed", rate: null }]); setRatesDirty(true); }}>+ Add fee</button>}
            <span>Built-up {chk ? `${inr(chk.area.total_builtup_m2)} m²` : "—"} · plot {chk ? `${inr(chk.area.plot_m2)} m²` : "—"} · cost: {chk?.estimate_total ? `₹${inr(chk.estimate_total)} (${chk.estimate_label})` : chk?.estimate_label}</span>
            <span className="flex-1" />
            <button className="btn-outline btn-sm" disabled={!chk || ratesDirty || !canEdit} onClick={copyFees}>Copy amounts to the checklist</button>
          </div>
        </Card>

        <Card title="Approval progress" icon={<FileText size={20} />}>
          <ol className="space-y-2">
            {d.stages.map((s, i) => (
              <li key={s.key} className={`flex flex-wrap items-center gap-2 rounded-lg border px-3 py-2 text-sm ${s.done ? "border-emerald-200 bg-emerald-50" : "border-line"}`}>
                <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${s.done ? "bg-emerald-600 text-white" : "bg-slate-200 text-slate-600"}`}>{i + 1}</span>
                <label className="flex min-w-[180px] flex-1 items-center gap-2 font-medium text-navy-ink">
                  <input type="checkbox" className="h-4 w-4 accent-brand-600" disabled={!canEdit} checked={s.done} onChange={(e) => stage(s, { done: e.target.checked })} />{s.label}
                </label>
                <input type="date" className="input w-auto py-1 text-xs" disabled={!canEdit || !s.done} value={s.date} onChange={(e) => stage(s, { date: e.target.value })} />
                {["applied", "fee_paid", "approved"].includes(s.key) && (
                  <input className="input w-40 py-1 text-xs" disabled={!canEdit} placeholder={s.key === "applied" ? "Application No." : s.key === "fee_paid" ? "Receipt No." : "Permit / approval No."}
                    defaultValue={s.ref} onBlur={(e) => e.target.value !== s.ref && stage(s, { ref: e.target.value })} />
                )}
              </li>
            ))}
          </ol>
          <p className="mt-2 text-[11px] text-slate-500">"Approval drawing ready" and "Application submitted" are saved with the project.</p>
        </Card>
      </div>

      <PermitChecklist key={permitKey} pid={pid} canEdit={canEdit} />
    </div>
  );
}
