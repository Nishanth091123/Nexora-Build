/** 1.8 – Estimate upgrade panels: Quick / Oral estimate, Floor-wise BOQ + Area statement + Key quantities,
 *  Payment schedule (editable) and Loan / official documents checklist. */
import { useCallback, useEffect, useRef, useState } from "react";
import { CheckCircle2, Clock, FileText, Home, Plus, RotateCcw, Trash2, UploadCloud } from "lucide-react";
import { Badge, Card, Empty, Field, toast } from "../ui";
import { api, ApiError, downloadFile, fmtDate, inr, lakhs, num, rupees } from "../../lib/api";

const BAR = ["#1d5ae0", "#ef4444", "#f59e0b", "#14b8a6", "#8b5cf6", "#f97316", "#64748b", "#0ea5e9"];
const cr = (n: number) => (n >= 1e7 ? `₹${(n / 1e7).toFixed(2)} Cr` : lakhs(n));

// ------------------------------------------------------------------ Quick / Oral estimate
export function QuickEstimate({ pid, defaults, state, onUseDetailed }: {
  pid: number; defaults: any; state: string; onUseDetailed: (inputs: any) => void;
}) {
  const levels = defaults?.floor_areas_sqft?.length || 1;
  const perFloor = Number(defaults?.floor_areas_sqft?.[0] || 0);
  const [f, setF] = useState({
    builtup_sqft: perFloor ? String(Math.round(perFloor * levels)) : "", floors: String(levels),
    bedrooms: "", toilets: "", structure: defaults?.structure || "rcc_framed", stilt: !!defaults?.stilt,
  });
  const [r, setR] = useState<any>(null);
  const [qs, setQs] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const go = async () => {
    setQs([]);
    const miss = [];
    if (!(Number(f.builtup_sqft) > 0)) miss.push("Total built-up area (sq ft) of all floors");
    if (f.bedrooms === "" || f.toilets === "") miss.push("Number of bedrooms and toilets in total");
    if (miss.length) { setQs(miss); return; }
    setBusy(true);
    try {
      const body = { builtup_sqft: Number(f.builtup_sqft), floors: Number(f.floors), bedrooms: Number(f.bedrooms),
        toilets: Number(f.toilets), structure: f.structure, stilt: f.stilt, state };
      setR(await api(`/api/projects/${pid}/estimate/quick`, { body }));
    } catch (e: any) {
      if (e instanceof ApiError && e.questions.length) setQs(e.questions);
      toast(e.message, "err");
    } finally { setBusy(false); }
  };
  const s = r?.specs;
  return (
    <div className="grid gap-4 xl:grid-cols-[340px_1fr]">
      <Card title="Quick / Oral Estimate" icon={<Home size={20} />}>
        <p className="mb-3 text-xs text-slate-500">Instant range for the first discussion with a client. The same engine as the detailed BOQ, run for Basic, Standard and Premium.</p>
        <div className="space-y-3">
          <Field label="Total built-up area (sq ft, all floors)"><input className="input" type="number" min="0" value={f.builtup_sqft} onChange={set("builtup_sqft")} /></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Floors"><select className="input" value={f.floors} onChange={set("floors")}>{[1, 2, 3, 4, 5, 6].map((n) => <option key={n} value={n}>{n === 1 ? "G" : `G+${n - 1}`}</option>)}</select></Field>
            <Field label="Structure"><select className="input" value={f.structure} onChange={set("structure")}><option value="rcc_framed">RCC (M20)</option><option value="load_bearing">Load bearing</option></select></Field>
            <Field label="Bedrooms (total)"><input className="input" type="number" min="0" value={f.bedrooms} onChange={set("bedrooms")} /></Field>
            <Field label="Toilets (total)"><input className="input" type="number" min="0" value={f.toilets} onChange={set("toilets")} /></Field>
          </div>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-brand-600" checked={f.stilt} onChange={set("stilt")} />Ground is stilt parking</label>
          <div className="text-xs text-slate-500">Location rates: <b>{state}</b></div>
          {qs.length > 0 && <div className="rounded-lg bg-amber-50 p-3 text-sm text-amber-800"><b>Please confirm:</b><ul className="ml-4 list-disc">{qs.map((q) => <li key={q}>{q}</li>)}</ul></div>}
          <button className="btn-primary w-full" disabled={busy} onClick={go}>{busy ? "Calculating..." : "Generate Oral Estimate"}</button>
        </div>
      </Card>
      {!r ? <Card><Empty text="Enter the area, floors, bedrooms and toilets, then Generate." /></Card> : (
        <div className="space-y-4">
          <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr_1fr_1fr]">
            <div className="card flex flex-col justify-center p-5">
              <div className="text-xs font-semibold text-slate-500">Estimated Cost Range</div>
              <div className="mt-1 text-2xl font-extrabold text-emerald-700">{cr(s.basic.grand_total)} – {cr(s.premium.grand_total)}</div>
              <div className="text-xs text-slate-500">(₹{inr(s.basic.cost_per_sqft)} – ₹{inr(s.premium.cost_per_sqft)} per sq ft · {num(r.builtup_sqft, 0)} sq ft)</div>
            </div>
            {(["basic", "standard", "premium"] as const).map((k) => (
              <div key={k} className={`card p-4 text-center ${k === "standard" ? "ring-2 ring-brand-500" : ""}`}>
                <div className={`text-sm font-bold ${k === "basic" ? "text-emerald-700" : k === "standard" ? "text-brand-700" : "text-amber-600"}`}>{k === "basic" ? "Economy" : k === "standard" ? "Standard" : "Premium"}</div>
                <div className="mt-1 text-xl font-extrabold text-navy-ink">{cr(s[k].grand_total)}</div>
                <div className="text-xs text-slate-500">₹{inr(s[k].cost_per_sqft)} / sq ft</div>
              </div>
            ))}
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="Cost Split (Standard)">
              <ul className="space-y-2 text-sm">
                {r.breakdown.map((g: any, i: number) => (
                  <li key={g.group}>
                    <div className="flex justify-between"><span>{g.group}</span><span className="font-semibold">{g.pct}% · {rupees(g.amount)}</span></div>
                    <div className="mt-1 h-2 rounded bg-slate-100"><div className="h-2 rounded" style={{ width: `${Math.min(100, g.pct)}%`, background: BAR[i % BAR.length] }} /></div>
                  </li>
                ))}
              </ul>
            </Card>
            <Card title="Main Materials (Standard)">
              <div className="overflow-hidden rounded-lg border border-line text-sm">
                {[["Estimated Cement", `${num(r.quantities.cement_bags, 0)} bags`], ["Estimated Steel", `${num(r.quantities.steel_kg, 0)} kg`],
                  ["M-Sand", `${r.quantities.msand_m3} m³`], ["P-Sand", `${r.quantities.psand_m3} m³`],
                  ["Aggregate", `${r.quantities.aggregate_m3} m³`], ["Bricks", `${num(r.quantities.bricks, 0)} nos`]].map(([k, v]) => (
                  <div key={k} className="flex justify-between border-b border-line px-3 py-2 last:border-b-0"><span className="text-slate-500">{k}</span><b className="text-navy-ink">{v}</b></div>
                ))}
              </div>
              <p className="mt-2 text-[11px] text-slate-500">{r.note}</p>
              <button className="btn-outline mt-3 w-full" onClick={() => onUseDetailed(r.inputs)}>Make the Detailed Estimate (BOQ) from this →</button>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

// ------------------------------------------------------------------ Floor-wise BOQ, area statement, key quantities
export function FloorBoqPanel({ result }: { result: any }) {
  const fb = result?.floor_boq;
  const [cat, setCat] = useState("all");
  if (!fb) return <Card><Empty text="Calculate the estimate again (Inputs → Calculate) to see the floor-wise BOQ." /></Card>;
  const cats = [...new Set<string>(fb.rows.map((x: any) => x.category))];
  const rows = fb.rows.filter((x: any) => cat === "all" || x.category === cat);
  const a = result.area_statement || [];
  const sum = (k: string) => a.reduce((s: number, x: any) => s + (x[k] || 0), 0);
  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-2">
        <Card title="Area Statement">
          <div className="overflow-x-auto rounded-lg border border-line">
            <table className="w-full min-w-[480px] text-sm">
              <thead className="bg-slate-50 text-left text-xs text-slate-500"><tr><th className="px-3 py-2">Floor</th><th className="px-3 py-2 text-right">Built-up (sq ft)</th><th className="px-3 py-2 text-right">Carpet (sq ft)</th><th className="px-3 py-2 text-right">Common</th><th className="px-3 py-2">Remarks</th></tr></thead>
              <tbody>
                {a.map((x: any) => <tr key={x.floor} className="border-t border-line"><td className="px-3 py-2 font-medium">{x.floor}</td><td className="px-3 py-2 text-right">{num(x.builtup_sqft, 0)}</td><td className="px-3 py-2 text-right">{num(x.carpet_sqft, 0)}</td><td className="px-3 py-2 text-right">{num(x.common_sqft, 0)}</td><td className="px-3 py-2 text-slate-600">{x.remarks}</td></tr>)}
                <tr className="border-t border-line bg-brand-50 font-bold"><td className="px-3 py-2">Total</td><td className="px-3 py-2 text-right">{num(sum("builtup_sqft"), 0)}</td><td className="px-3 py-2 text-right">{num(sum("carpet_sqft"), 0)}</td><td className="px-3 py-2 text-right">{num(sum("common_sqft"), 0)}</td><td /></tr>
              </tbody>
            </table>
          </div>
          <p className="mt-2 text-[11px] text-slate-500">Carpet area is approximate (built-up minus walls and staircase). Measure from the final drawing for official use.</p>
        </Card>
        <Card title="Key Quantities (Summary)">
          <div className="overflow-hidden rounded-lg border border-line text-sm">
            {(result.key_quantities || []).map((k: any) => (
              <div key={k.name} className="flex justify-between border-b border-line px-3 py-1.5 last:border-b-0"><span>{k.name}</span><span className="font-semibold text-navy-ink">{num(k.qty, 1)} {k.unit}</span></div>
            ))}
          </div>
        </Card>
      </div>
      <Card title="Detailed Estimation – Floor-wise BOQ">
        <div className="mb-3 flex flex-wrap gap-1.5">
          {["all", ...cats].map((c) => <button key={c} onClick={() => setCat(c)} className={`rounded-md px-3 py-1.5 text-xs font-semibold ${cat === c ? "bg-brand-600 text-white" : "bg-brand-50 text-navy-ink"}`}>{c === "all" ? "All" : c}</button>)}
        </div>
        <div className="max-h-[560px] overflow-auto rounded-lg border border-line">
          <table className="w-full min-w-[900px] text-sm">
            <thead className="sticky top-0 bg-slate-50 text-xs text-slate-500">
              <tr><th className="px-2 py-2 text-left">S.No</th><th className="px-2 py-2 text-left">Description</th><th className="px-2 py-2">Unit</th>
                {fb.columns.map((c: string) => <th key={c} className="px-2 py-2 text-right">{c.replace(" Floor", "")}</th>)}
                <th className="px-2 py-2 text-right">Total</th><th className="px-2 py-2 text-right">Rate (₹)</th><th className="px-2 py-2 text-right">Amount (₹)</th></tr>
            </thead>
            <tbody>
              {rows.map((x: any, i: number) => (
                <tr key={i} className="border-t border-line">
                  <td className="px-2 py-1.5 text-slate-500">{i + 1}</td>
                  <td className="px-2 py-1.5">{x.description}</td>
                  <td className="px-2 py-1.5 text-center text-slate-500">{x.unit}</td>
                  {fb.columns.map((c: string) => <td key={c} className="px-2 py-1.5 text-right">{x.qty[c] ? num(x.qty[c], 1) : "–"}</td>)}
                  <td className="px-2 py-1.5 text-right font-semibold">{num(x.total_qty, 1)}</td>
                  <td className="px-2 py-1.5 text-right">{inr(x.rate)}</td>
                  <td className="px-2 py-1.5 text-right font-semibold text-navy-ink">{inr(x.amount)}</td>
                </tr>
              ))}
              <tr className="sticky bottom-0 border-t border-line bg-brand-50 font-bold">
                <td /><td className="px-2 py-2" colSpan={2 + fb.columns.length + 2}>Total of shown items (before extras)</td>
                <td className="px-2 py-2 text-right">{inr(rows.reduce((s: number, x: any) => s + x.amount, 0))}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}

// ------------------------------------------------------------------ Payment schedule (editable)
export function PaymentSchedulePanel({ result, onApply, busy }: { result: any; onApply: (stages: { stage: string; pct: number }[] | null) => void; busy: boolean }) {
  const [rows, setRows] = useState<{ stage: string; pct: string }[]>([]);
  useEffect(() => { setRows((result?.payment_schedule || []).map((x: any) => ({ stage: x.stage, pct: String(x.pct) }))); }, [result]);
  if (!result?.payment_schedule) return <Card><Empty text="Calculate the estimate again to see the payment schedule." /></Card>;
  const grand = result.totals.grand_total;
  const total = rows.reduce((s, x) => s + (Number(x.pct) || 0), 0);
  const upd = (i: number, k: "stage" | "pct", v: string) => setRows(rows.map((x, j) => (j === i ? { ...x, [k]: v } : x)));
  return (
    <Card title="Payment Schedule (stage-wise)"
      action={<div className="flex gap-2">
        <button className="btn-ghost btn-sm" title="Typical schedule from the floors" onClick={() => onApply(null)}><RotateCcw size={14} />Default</button>
        <button className="btn-primary btn-sm" disabled={busy || Math.abs(total - 100) > 0.01} onClick={() => onApply(rows.map((x) => ({ stage: x.stage, pct: Number(x.pct) || 0 })))}>Apply</button>
      </div>}>
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full min-w-[560px] text-sm">
          <thead className="bg-slate-50 text-left text-xs text-slate-500"><tr><th className="px-3 py-2">Stage</th><th className="px-3 py-2">Description</th><th className="w-24 px-3 py-2 text-right">%</th><th className="px-3 py-2 text-right">Amount (₹)</th><th /></tr></thead>
          <tbody>
            {rows.map((x, i) => (
              <tr key={i} className="border-t border-line">
                <td className="px-3 py-1.5 text-slate-500">{i + 1}</td>
                <td className="px-3 py-1.5"><input className="input py-1" value={x.stage} onChange={(e) => upd(i, "stage", e.target.value)} /></td>
                <td className="px-3 py-1.5"><input className="input py-1 text-right" type="number" min="0" max="100" step="0.5" value={x.pct} onChange={(e) => upd(i, "pct", e.target.value)} /></td>
                <td className="px-3 py-1.5 text-right font-semibold">{inr(grand * (Number(x.pct) || 0) / 100)}</td>
                <td className="px-2"><button className="btn-ghost btn-sm text-red-600" onClick={() => setRows(rows.filter((_, j) => j !== i))}><Trash2 size={14} /></button></td>
              </tr>
            ))}
            <tr className={`border-t border-line font-bold ${Math.abs(total - 100) > 0.01 ? "bg-red-50 text-red-700" : "bg-brand-50"}`}>
              <td /><td className="px-3 py-2">Total {Math.abs(total - 100) > 0.01 && "– must be 100%"}</td><td className="px-3 py-2 text-right">{num(total, 1)}%</td><td className="px-3 py-2 text-right">{inr(grand * total / 100)}</td><td />
            </tr>
          </tbody>
        </table>
      </div>
      <div className="mt-3 flex items-center justify-between gap-2">
        <button className="btn-outline btn-sm" onClick={() => setRows([...rows, { stage: "New stage", pct: "0" }])}><Plus size={14} />Add stage</button>
        <span className="text-xs text-slate-500">Apply, then <b>Save</b> the estimate – the schedule goes into the PDF and Excel.</span>
      </div>
    </Card>
  );
}

// ------------------------------------------------------------------ Loan / official documents
export function LoanDocsPanel({ pid, canUpload }: { pid: number; canUpload: boolean }) {
  const [d, setD] = useState<any>(null);
  const [key, setKey] = useState("");
  const input = useRef<HTMLInputElement>(null);
  const load = useCallback(() => api(`/api/projects/${pid}/loan-docs`).then(setD).catch((e) => toast(e.message, "err")), [pid]);
  useEffect(() => { load(); }, [load]);
  const upload = async (file: File) => {
    const fd = new FormData(); fd.append("category", `loan_${key}`); fd.append("file", file);
    try { await api(`/api/files/project/${pid}`, { form: fd }); toast(`${file.name} uploaded`); load(); }
    catch (e: any) { toast(e.message, "err"); }
  };
  if (!d) return <Card><Empty text="Loading..." /></Card>;
  return (
    <Card title={`Document Upload (Loan / Official Use) · ${d.done} of ${d.total} ready`} icon={<FileText size={20} />}>
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full min-w-[620px] text-sm">
          <thead className="bg-slate-50 text-left text-xs text-slate-500"><tr><th className="px-3 py-2">Document</th><th className="px-3 py-2">File</th><th className="px-3 py-2">Date</th><th className="px-3 py-2">Status</th><th /></tr></thead>
          <tbody>
            {d.items.map((it: any) => {
              const f = it.files[0];
              return (
                <tr key={it.key} className="border-t border-line">
                  <td className="px-3 py-2 font-medium text-navy-ink">{it.label}</td>
                  <td className="px-3 py-2">{f ? <button className="link truncate" onClick={() => downloadFile(f.url, f.name).catch((e) => toast(e.message, "err"))}>{f.name}</button> : <span className="text-slate-400">—</span>}</td>
                  <td className="px-3 py-2 text-slate-600">{f ? fmtDate(f.created_at) : "—"}</td>
                  <td className="px-3 py-2">{it.status === "uploaded" ? <Badge color="green"><CheckCircle2 size={12} className="mr-1 inline" />Uploaded</Badge> : <Badge color="amber"><Clock size={12} className="mr-1 inline" />Pending</Badge>}</td>
                  <td className="px-3 py-2 text-right">{canUpload && <button className="btn-outline btn-sm" onClick={() => { setKey(it.key); input.current?.click(); }}><UploadCloud size={14} />{f ? "Replace" : "Upload"}</button>}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-slate-500">Tip: Estimate Report and BOQ – download them from Export (Bank Loan PDF / Excel) and upload here, so the full loan file is in one place.</p>
      <input ref={input} type="file" hidden accept=".pdf,.png,.jpg,.jpeg,.webp,.xlsx,.xls,.docx,.dxf"
        onChange={(e) => { const f = e.target.files?.[0]; if (f && key) upload(f); e.target.value = ""; }} />
    </Card>
  );
}

// ------------------------------------------------------------------ Settings card: estimate defaults (owner)
export function EstimateDefaultsCard() {
  const [v, setV] = useState({ gst_pct: "0", contractor_margin_pct: "0", contingency_pct: "" });
  useEffect(() => {
    api<any>("/api/estimate-settings").then((d) => setV({ gst_pct: String(d.gst_pct ?? 0), contractor_margin_pct: String(d.contractor_margin_pct ?? 0), contingency_pct: d.contingency_pct == null ? "" : String(d.contingency_pct) })).catch(() => {});
  }, []);
  const save = async () => {
    try {
      await api("/api/estimate-settings", { method: "PUT", body: { gst_pct: Number(v.gst_pct) || 0, contractor_margin_pct: Number(v.contractor_margin_pct) || 0, contingency_pct: v.contingency_pct === "" ? null : Number(v.contingency_pct) } });
      toast("Estimate defaults saved – used for new estimates");
    } catch (e: any) { toast(e.message, "err"); }
  };
  return (
    <Card title="Estimate defaults (new estimates)">
      <div className="grid gap-3 sm:grid-cols-3">
        <Field label="GST %"><input className="input" type="number" min="0" max="28" value={v.gst_pct} onChange={(e) => setV({ ...v, gst_pct: e.target.value })} /></Field>
        <Field label="Overhead & profit %"><input className="input" type="number" min="0" max="40" value={v.contractor_margin_pct} onChange={(e) => setV({ ...v, contractor_margin_pct: e.target.value })} /></Field>
        <Field label="Contingency % (blank = rate library)"><input className="input" type="number" min="0" max="20" value={v.contingency_pct} onChange={(e) => setV({ ...v, contingency_pct: e.target.value })} /></Field>
      </div>
      <div className="mt-3 flex justify-end"><button className="btn-primary btn-sm" onClick={save}>Save</button></div>
    </Card>
  );
}
