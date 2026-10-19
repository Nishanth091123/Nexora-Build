import { Fragment, useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  BarChart3, Calculator, CalendarClock, Check, ChevronDown, ChevronRight, ClipboardList, Download, FileImage, FileSpreadsheet, FileText, GitCompare, Hammer, HardHat, IndianRupee, Layers, LayoutDashboard, Library, Package, PenLine, Plus, Ruler, Save, Search, SlidersHorizontal, Trash2, TriangleAlert, Upload, Users,
} from "lucide-react";
import Page from "../components/Page";
import OwnerDelete from "../components/OwnerDelete";
import Plan3D from "../components/design/Plan3D";
import BbsTab from "../components/bbs/BbsTab";
import RateLibrary, { type Rate } from "../components/RateLibrary";
import { INDIAN_STATES } from "../components/ProjectBits";
import { Badge, Card, Empty, Field, Modal, PillTabs, SegTabs, Toggle, toast } from "../components/ui";
import { api, ApiError, downloadFile, downloadPost, fmtDateTime, inr, lakhs, num, rupees } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

type Item = {
  sl: number; category: string; group: string; description: string; floor: string; qty: number; unit: string;
  rate: number; material_cost: number; labour_cost: number; equipment_cost: number; amount: number;
  materials: { name: string; qty: number; unit: string; rate: number; amount: number }[];
  labour: { name: string; days: number; rate: number; amount: number }[];
  equipment: { name: string; qty: number; unit: string; rate: number; amount: number }[];
};
type Result = {
  spec_level: string; structure: string; masonry: string; rates_state: string;
  items: Item[]; materials: any[]; labour: any[]; equipment: any[]; extras: any[]; floors: any[];
  breakdown: { group: string; amount: number; pct: number }[]; totals: Record<string, number>;
  assumptions: string[]; warnings: string[]; note: string;
};
type Version = { id: number; version: number; title: string; spec_level: string; grand_total: number; cost_per_sqft: number; builtup_sqft: number; created_at: string; rate_state: string };

const DONUT = ["#1d5ae0", "#ef4444", "#f59e0b", "#14b8a6", "#8b5cf6", "#f97316", "#64748b", "#0ea5e9"];

function Donut({ data, total }: { data: { group: string; amount: number; pct: number }[]; total: number }) {
  const R = 70, C = 2 * Math.PI * R;
  let off = 0;
  return (
    <div className="flex flex-wrap items-center gap-5">
      <svg width="190" height="190" viewBox="0 0 190 190" className="shrink-0">
        <circle cx="95" cy="95" r={R} fill="none" stroke="#eef2f7" strokeWidth="30" />
        {data.map((d, i) => {
          const len = (d.pct / 100) * C;
          const el = <circle key={d.group} cx="95" cy="95" r={R} fill="none" stroke={DONUT[i % DONUT.length]} strokeWidth="30"
            strokeDasharray={`${len} ${C - len}`} strokeDashoffset={-off} transform="rotate(-90 95 95)" />;
          off += len;
          return el;
        })}
        <text x="95" y="90" textAnchor="middle" className="fill-navy-ink" fontSize="19" fontWeight="800">{lakhs(total)}</text>
        <text x="95" y="110" textAnchor="middle" className="fill-slate-500" fontSize="11">Total Cost</text>
      </svg>
      <ul className="min-w-[220px] flex-1 space-y-2 text-sm">
        {data.map((d, i) => (
          <li key={d.group} className="flex items-center gap-2">
            <span className="h-3 w-3 rounded-full" style={{ background: DONUT[i % DONUT.length] }} />
            <span className="flex-1 text-slate-700">{d.group}</span>
            <span className="w-12 text-right text-slate-500">{d.pct}%</span>
            <span className="w-24 text-right font-semibold text-navy-ink">{rupees(d.amount)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Steps({ step }: { step: number }) {
  const steps = [["Select Input", "Drawing / Plan / Manual"], ["Auto Takeoff", "Quantity extraction"], ["Review & Edit", "Modify if needed"],
    ["Estimate", "Material + Labour + Cost"], ["Generate BOQ", "Export & Reports"]];
  return (
    <div className="card flex flex-wrap items-center justify-between gap-3 p-4">
      {steps.map(([t, s], i) => (
        <div key={t} className="flex items-center gap-3">
          <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-sm font-bold ${i < step ? "bg-emerald-600 text-white" : i === step ? "bg-brand-600 text-white" : "bg-slate-200 text-slate-600"}`}>
            {i < step ? <Check size={18} /> : i + 1}
          </div>
          <div className="leading-tight"><div className="whitespace-nowrap text-sm font-bold text-navy-ink">{t}</div><div className="hidden text-xs text-slate-500 min-[1800px]:block">{s}</div></div>
          {i < steps.length - 1 && <ChevronRight size={16} className="hidden text-brand-600 min-[1800px]:block" />}
        </div>
      ))}
    </div>
  );
}

function SummaryCard({ tone, icon, label, value, sub, extra }: { tone: string; icon: ReactNode; label: string; value: ReactNode; sub: string; extra?: ReactNode }) {
  return (
    <div className={`flex items-center gap-4 rounded-xl p-4 ${tone}`}>
      <div className="shrink-0">{icon}</div>
      <div className="min-w-0">
        <div className="text-sm font-semibold">{label}</div>
        <div className="text-2xl font-extrabold text-navy-ink">{value}</div>
        <div className="text-sm text-slate-600">{sub}</div>{extra}
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ inputs modal
function Est3D({ designId, onPick }: { designId?: number; onPick: () => void }) {
  const [plan, setPlan] = useState<any>(null);
  useEffect(() => {
    setPlan(null);
    if (designId) api<any>(`/api/designs/${designId}`).then((d) => setPlan(d.plan)).catch(() => {});
  }, [designId]);
  if (!designId) return (
    <div className="text-sm text-slate-600">The 3D model is shown when the estimate comes from a drawing.
      <div className="mt-2"><button className="btn-outline btn-sm" onClick={onPick}><PenLine size={14} />Use 2D Drawing input</button></div></div>
  );
  return plan ? <div className="h-72"><Plan3D plan={plan} /></div> : <p className="text-sm text-slate-500">Loading…</p>;
}

function ExcelModal({ open, onClose, pid, code, inputs, state, isOwner, onImported, onRatesChanged }: {
  open: boolean; onClose: () => void; pid: number; code: string; inputs: any; state: string; isOwner: boolean;
  onImported: (inp: any) => void; onRatesChanged: () => void;
}) {
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState<string[]>([]);
  const download = async () => {
    setBusy("d");
    try {
      const x = { ...(inputs || {}) }; delete x.geometry;
      await downloadPost(`/api/projects/${pid}/estimate/excel-template`, { inputs: x, state }, `${code}_Estimate_Inputs.xlsx`);
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(""); }
  };
  const upload = async (f: File) => {
    setBusy("u"); setMsg([]);
    try {
      const fd = new FormData(); fd.append("file", f); fd.append("state", state);
      const r = await api<any>(`/api/projects/${pid}/estimate/excel-import`, { form: fd });
      const notes = [...r.warnings];
      if (r.rates_changed) { notes.unshift(`${r.rates_changed} rate(s) updated in the ${r.rates_state} rate library.`); onRatesChanged(); }
      setMsg(notes);
      toast("Excel read – calculating");
      onImported(r.inputs);
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(""); }
  };
  return (
    <Modal open={open} onClose={onClose} title="Estimate from Excel (BOQ / Rates)">
      <ol className="list-decimal space-y-3 pl-5 text-sm text-slate-700">
        <li>
          <b>Download the template</b> – it is filled with your current inputs and the {state} rates.
          <div className="mt-1.5"><button className="btn-outline btn-sm" onClick={download} disabled={!!busy}><Download size={14} />{busy === "d" ? "Preparing…" : "Download Excel template"}</button></div>
        </li>
        <li>
          <b>Fill it in Excel</b>:
          <ul className="mt-1 list-disc pl-5 text-[13px] text-slate-600">
            <li><b>Inputs</b> sheet: floor areas (ground first, e.g. <i>1200, 1150</i>), bedrooms, toilets, specification…</li>
            <li><b>Extra Items</b> sheet: your own BOQ items – rate code + quantity.</li>
            <li><b>Rates</b> sheet: {isOwner ? "change any rate – it updates your rate library (logged)." : "view only (only the owner can change rates)."}</li>
          </ul>
        </li>
        <li>
          <b>Upload it back</b> – the estimate is calculated at once. Nothing is saved until you press Save.
          <div className="mt-1.5">
            <label className={`btn-primary btn-sm cursor-pointer ${busy ? "opacity-60" : ""}`}><Upload size={14} />{busy === "u" ? "Reading…" : "Upload filled Excel"}
              <input type="file" hidden accept=".xlsx,.xlsm" disabled={!!busy} onChange={(e) => { const f = e.target.files?.[0]; e.target.value = ""; if (f) upload(f); }} /></label>
          </div>
        </li>
      </ol>
      {msg.length > 0 && <div className="mt-3 rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">{msg.map((m) => <div key={m}>• {m}</div>)}</div>}
    </Modal>
  );
}

function InputsModal({ open, onClose, inputs, setInputs, state, setState, onCalculate, rates, needs }: {
  open: boolean; onClose: () => void; inputs: any; setInputs: (v: any) => void; state: string; setState: (s: string) => void;
  onCalculate: () => void; rates: Rate[]; needs: string[];
}) {
  if (!inputs) return null;
  const set = (k: string, v: any) => setInputs({ ...inputs, [k]: v });
  const n = (k: string) => (e: any) => set(k, e.target.value === "" ? "" : Number(e.target.value));
  const levels: number = inputs.floor_areas_sqft.length;
  const levelName = (i: number) => (inputs.stilt && i === 0 ? "Stilt / Parking" : ["Ground", "First", "Second", "Third", "Fourth", "Fifth"][i - (inputs.stilt ? 1 : 0)] + " floor");
  const setLevels = (cnt: number) => {
    const arr = [...inputs.floor_areas_sqft];
    while (arr.length < cnt) arr.push(arr[arr.length - 1] || 0);
    set("floor_areas_sqft", arr.slice(0, cnt));
  };
  const extra: { code: string; qty: number; note?: string }[] = inputs.extra_items || [];
  const sel = (k: string, opts: [string, string][]) => <select className="input" value={inputs[k]} onChange={(e) => set(k, e.target.value)}>{opts.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>;
  const tog = (k: string, l: string) => <label className="flex items-center justify-between gap-3 rounded-lg border border-line px-3 py-2 text-sm"><span>{l}</span><Toggle checked={!!inputs[k]} onChange={(v) => set(k, v)} /></label>;
  return (
    <Modal open={open} onClose={onClose} title={inputs.geometry ? "Estimate Inputs – from 2D Drawing" : "Estimate Inputs – Manual Enter Sizes"} wide>
      {inputs.geometry && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-brand-100 bg-brand-50 px-4 py-3 text-sm text-navy-ink">
          <span><b>Quantities from design{inputs.design_id ? ` #${inputs.design_id}` : ""}:</b> walls, doors, windows, rooms and floor areas are measured from the drawing. Services, structure and extras below are still yours to set.</span>
          <button className="btn-outline btn-sm" onClick={() => { const x = { ...inputs }; delete x.geometry; delete x.design_id; setInputs(x); }}>Use manual sizes instead</button>
        </div>
      )}
      {needs.length > 0 && (
        <div className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <div className="mb-1 flex items-center gap-2 font-semibold"><TriangleAlert size={16} />Please confirm:</div>
          <ul className="list-disc pl-5">{needs.map((q) => <li key={q}>{q}</li>)}</ul>
        </div>
      )}
      <h4 className="mb-2 text-sm font-bold text-navy-ink">1. Floors & area</h4>
      <div className="grid gap-3 sm:grid-cols-4">
        <Field label="Number of floors"><select className="input" value={levels} onChange={(e) => setLevels(Number(e.target.value))}>{[1, 2, 3, 4, 5, 6].map((x) => <option key={x} value={x}>{x === 1 ? "G" : `G+${x - 1}`}</option>)}</select></Field>
        <label className="flex items-end gap-2 pb-2 text-sm"><input type="checkbox" className="accent-brand-600" checked={!!inputs.stilt} onChange={(e) => set("stilt", e.target.checked)} />Ground is stilt parking</label>
        <Field label="Floor height (ft)"><input className="input" type="number" value={inputs.floor_height_ft} onChange={n("floor_height_ft")} /></Field>
        <div />
        {inputs.floor_areas_sqft.map((a: number, i: number) => (
          <Field key={i} label={`${levelName(i)} – built-up sq ft *`}>
            <input className={`input ${!a ? "border-amber-400" : ""}`} type="number" min="0" value={a || ""} placeholder="confirm"
              onChange={(e) => { const arr = [...inputs.floor_areas_sqft]; arr[i] = Number(e.target.value); set("floor_areas_sqft", arr); }} />
          </Field>
        ))}
      </div>
      <h4 className="mb-2 mt-5 text-sm font-bold text-navy-ink">2. Rooms (whole building) & plot</h4>
      <div className="grid gap-3 sm:grid-cols-4">
        <Field label="Bedrooms *"><input className={`input ${!inputs.bedrooms && !inputs.toilets ? "border-amber-400" : ""}`} type="number" min="0" value={inputs.bedrooms} onChange={n("bedrooms")} /></Field>
        <Field label="Toilets *"><input className="input" type="number" min="0" value={inputs.toilets} onChange={n("toilets")} /></Field>
        <Field label="Kitchens"><input className="input" type="number" min="0" value={inputs.kitchens} onChange={n("kitchens")} /></Field>
        <Field label="Halls"><input className="input" type="number" min="0" value={inputs.halls} onChange={n("halls")} /></Field>
        <Field label="Plot width (ft)"><input className="input" type="number" value={inputs.plot_width_ft ?? ""} onChange={(e) => set("plot_width_ft", e.target.value ? Number(e.target.value) : null)} /></Field>
        <Field label="Plot length (ft)"><input className="input" type="number" value={inputs.plot_length_ft ?? ""} onChange={(e) => set("plot_length_ft", e.target.value ? Number(e.target.value) : null)} /></Field>
        <Field label="Parking / sit-out paving (sq ft)"><input className="input" type="number" value={inputs.parking_area_sqft} onChange={n("parking_area_sqft")} /></Field>
      </div>
      <h4 className="mb-2 mt-5 text-sm font-bold text-navy-ink">3. Structure & specification</h4>
      <div className="grid gap-3 sm:grid-cols-4">
        <Field label="Structure">{sel("structure", [["rcc_framed", "RCC framed"], ["load_bearing", "Load bearing"]])}</Field>
        <Field label="Specification">{sel("spec_level", [["basic", "Basic"], ["standard", "Standard"], ["premium", "Premium"]])}</Field>
        <Field label="Masonry">{sel("masonry", [["brick", "Bricks"], ["aac", "AAC blocks"], ["solid_block", "Solid blocks"]])}</Field>
        <Field label="Rates of state"><select className="input" value={state} onChange={(e) => setState(e.target.value)}>{INDIAN_STATES.map((s) => <option key={s}>{s}</option>)}</select></Field>
      </div>
      <h4 className="mb-2 mt-5 text-sm font-bold text-navy-ink">4. Services & external works</h4>
      <div className="grid gap-2 sm:grid-cols-3">
        {tog("staircase", "Staircase (upper floors / terrace)")}{tog("rwh", "Rain water harvesting")}{tog("septic_tank", "Septic tank + soak pit")}
        {tog("compound_wall", "Compound wall")}{tog("gate", "MS gate")}
        <Field label="Sump (litres, 0 = none)"><input className="input" type="number" value={inputs.sump_litres} onChange={n("sump_litres")} /></Field>
        <Field label="Overhead tank (litres, blank = auto)"><input className="input" type="number" value={inputs.oh_tank_litres ?? ""} onChange={(e) => set("oh_tank_litres", e.target.value === "" ? null : Number(e.target.value))} /></Field>
        {inputs.compound_wall && <Field label="Compound wall length (m, blank = plot)"><input className="input" type="number" value={inputs.compound_wall_length_m ?? ""} onChange={(e) => set("compound_wall_length_m", e.target.value === "" ? null : Number(e.target.value))} /></Field>}
      </div>
      <h4 className="mb-2 mt-5 text-sm font-bold text-navy-ink">5. Extras</h4>
      <div className="grid gap-3 sm:grid-cols-4">
        <Field label="Contractor margin %"><input className="input" type="number" value={inputs.contractor_margin_pct} onChange={n("contractor_margin_pct")} /></Field>
        <Field label="GST %"><input className="input" type="number" value={inputs.gst_pct} onChange={n("gst_pct")} /></Field>
        <Field label="Contingency % (blank = library)"><input className="input" type="number" value={inputs.contingency_pct ?? ""} onChange={(e) => set("contingency_pct", e.target.value === "" ? null : Number(e.target.value))} /></Field>
        <Field label="Plan approval & fees ₹"><input className="input" type="number" value={inputs.approval_fees} onChange={n("approval_fees")} /></Field>
      </div>
      <h4 className="mb-2 mt-5 text-sm font-bold text-navy-ink">6. Additional items (from rate library)</h4>
      <div className="space-y-2">
        {extra.map((x, i) => (
          <div key={i} className="flex flex-wrap items-center gap-2">
            <select className="input min-w-[220px] flex-1" value={x.code} onChange={(e) => { const a = [...extra]; a[i] = { ...x, code: e.target.value }; set("extra_items", a); }}>
              <option value="">— choose —</option>
              {rates.filter((r) => r.kind !== "extra").map((r) => <option key={r.code} value={r.code}>{r.name} ({r.unit})</option>)}
            </select>
            <input className="input w-28" type="number" placeholder="Qty" value={x.qty || ""} onChange={(e) => { const a = [...extra]; a[i] = { ...x, qty: Number(e.target.value) }; set("extra_items", a); }} />
            <input className="input w-48" placeholder="Note" value={x.note || ""} onChange={(e) => { const a = [...extra]; a[i] = { ...x, note: e.target.value }; set("extra_items", a); }} />
            <button className="btn-ghost btn-sm text-red-600" onClick={() => set("extra_items", extra.filter((_, j) => j !== i))} aria-label="Remove"><Trash2 size={14} /></button>
          </div>
        ))}
        <button className="btn-outline btn-sm" onClick={() => set("extra_items", [...extra, { code: "", qty: 0 }])}><Plus size={14} />Add item</button>
      </div>
      <div className="mt-6 flex justify-end gap-2">
        <button className="btn-ghost" onClick={onClose}>Close</button>
        <button className="btn-primary" onClick={onCalculate}><Calculator size={16} />Calculate Estimate</button>
      </div>
    </Modal>
  );
}

// ------------------------------------------------------------------ page
export default function EstimatePage() {
  const { t } = useI18n();
  const nav = useNavigate();
  const { currentProject, user } = useAuth();
  const [tab, setTab] = useState("overview");
  const [tableTab, setTableTab] = useState("takeoff");
  const [inputs, setInputs] = useState<any>(null);
  const [state, setState] = useState("Tamil Nadu");
  const [needs, setNeeds] = useState<string[]>([]);
  const [result, setResult] = useState<Result | null>(null);
  const [saved, setSaved] = useState<{ id: number; version: number; title: string } | null>(null);
  const [dirty, setDirty] = useState(false);
  const [versions, setVersions] = useState<Version[]>([]);
  const [rates, setRates] = useState<Rate[]>([]);
  const [showInputs, setShowInputs] = useState(false);
  const [busy, setBusy] = useState(false);
  const [cat, setCat] = useState("all");
  const [floor, setFloor] = useState("all");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<number | null>(null);
  const [cmp, setCmp] = useState<Record<string, Result> | null>(null);
  const [exportOpen, setExportOpen] = useState(false);
  const [designPick, setDesignPick] = useState<any[] | null>(null);
  const [params] = useSearchParams();
  const designParam = params.get("design");
  const allowed = !!currentProject?.permissions?.estimate;
  const pid = currentProject?.id;

  const loadVersions = useCallback(async () => {
    if (!pid) return [];
    const v = await api<Version[]>(`/api/projects/${pid}/estimates`);
    setVersions(v);
    return v;
  }, [pid]);

  const [defaults, setDefaults] = useState<any>(null);
  const openVersion = async (id: number, base?: any) => {
    const e = await api<any>(`/api/estimates/${id}`);
    setInputs({ ...(base || defaults || {}), ...e.inputs }); setNeeds([]); setResult(e.result); setState(e.rate_state); setSaved({ id: e.id, version: e.version, title: e.title }); setDirty(false);
  };

  useEffect(() => {
    if (!pid || !allowed) return;
    setResult(null); setSaved(null); setCmp(null);
    (async () => {
      try {
        const d = await api<any>(`/api/projects/${pid}/estimate-defaults`);
        setInputs(d.inputs); setDefaults(d.inputs); setState(d.state); setNeeds(d.needs_confirmation);
        const v = await loadVersions();
        if (designParam) await applyDesign(Number(designParam), d.inputs);
        else if (v.length) await openVersion(v[0].id, d.inputs);
        else setShowInputs(true);
      } catch (e: any) { toast(e.message, "err"); }
    })();
  }, [pid, allowed]);

  useEffect(() => { api(`/api/rates?state=${encodeURIComponent(state)}`).then((d) => setRates(d.items)).catch(() => {}); }, [state]);

  const applyDesign = async (id: number, base?: any) => {
    setDesignPick(null);
    try {
      const d = await api<any>(`/api/designs/${id}/estimate-inputs`);
      const inp = { ...(base || defaults || inputs || {}), ...d.inputs };
      setInputs(inp); setNeeds([]); setSaved(null);
      toast(`Using design v${d.design.version} – quantities measured from the drawing`);
      await calculate(undefined, inp);
    } catch (e: any) { toast(e.message, "err"); }
  };
  const pickDesign = async () => {
    try {
      const list = await api<any[]>(`/api/projects/${pid}/designs`);
      if (!list.length) { toast("No saved design yet – create one in Design Studio", "err"); return nav("/design"); }
      setDesignPick(list);
    } catch (e: any) { toast(e.message, "err"); }
  };

  const [showExcel, setShowExcel] = useState(false);
  const fromExcel = async (inp: any) => {
    const x = { ...(defaults || {}), ...(inputs || {}), ...inp, source: "excel" };
    delete x.geometry; delete x.design_id;
    setInputs(x); setSaved(null); setShowExcel(false);
    await calculate(undefined, x);
  };

  const calculate = async (spec?: string, override?: any) => {
    if (!pid) return null;
    setBusy(true);
    const base = override || inputs;
    try {
      const body = { inputs: spec ? { ...base, spec_level: spec } : base, state };
      const r = await api<Result>(`/api/projects/${pid}/estimate/calculate`, { body });
      if (!spec) { setResult(r); setNeeds([]); setDirty(true); setShowInputs(false); setSaved(null); }
      return r;
    } catch (e: any) {
      if (e instanceof ApiError && e.questions.length) { setNeeds(e.questions); setShowInputs(true); }
      toast(e.message, "err");
      return null;
    } finally { setBusy(false); }
  };

  const save = async () => {
    if (!pid || !result) return;
    const title = window.prompt("Name for this estimate version", `${result.spec_level[0].toUpperCase()}${result.spec_level.slice(1)} estimate`);
    if (title === null) return;
    try {
      const e = await api<any>(`/api/projects/${pid}/estimates`, { body: { inputs, state, title } });
      setSaved({ id: e.id, version: e.version, title: e.title }); setResult(e.result); setDirty(false);
      await loadVersions(); toast(`Saved as version ${e.version}`);
    } catch (e: any) { toast(e.message, "err"); }
  };

  const doExport = async (kind: "excel" | "pdf") => {
    setExportOpen(false);
    if (!saved || dirty) return toast("Save this estimate first (Save button) – exports come from a saved version", "err");
    const ext = kind === "excel" ? "xlsx" : "pdf";
    try { await downloadFile(`/api/estimates/${saved.id}/${kind}`, `${currentProject?.code}_${kind === "excel" ? "BOQ" : "Estimate"}_v${saved.version}.${ext}`); }
    catch (e: any) { toast(e.message, "err"); }
  };

  const runCompare = async () => {
    const out: Record<string, Result> = {};
    for (const s of ["basic", "standard", "premium"]) { const r = await calculate(s); if (!r) return; out[s] = r; }
    setCmp(out);
  };

  const items = useMemo(() => (result?.items || []).filter((i) => (cat === "all" || i.category === cat) && (floor === "all" || i.floor === floor) &&
    (!q || i.description.toLowerCase().includes(q.toLowerCase()))), [result, cat, floor, q]);
  const cats = useMemo(() => [...new Set((result?.items || []).map((i) => i.category))], [result]);
  const floors = useMemo(() => [...new Set((result?.items || []).map((i) => i.floor))], [result]);
  const tt = result?.totals;
  const step = !inputs ? 0 : !result ? 1 : dirty ? 3 : saved ? 5 : 3;

  const header = (
    <>
      <button className="btn-outline hidden sm:inline-flex" onClick={save} disabled={!result || !dirty}><Save size={16} />Save</button>
      <div className="relative hidden sm:block">
        <button className="btn-outline" onClick={() => setExportOpen(!exportOpen)} disabled={!result}><Upload size={16} />Export<ChevronDown size={14} /></button>
        {exportOpen && (
          <div className="absolute right-0 z-30 mt-2 w-48 rounded-xl border border-line bg-white p-1 shadow-xl">
            <button className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-slate-50" onClick={() => doExport("excel")}><FileSpreadsheet size={16} className="text-emerald-600" />BOQ (Excel)</button>
            <button className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-slate-50" onClick={() => doExport("pdf")}><FileText size={16} className="text-red-500" />Estimate (PDF)</button>
          </div>
        )}
      </div>
    </>
  );

  if (!currentProject) return <Page title={t("Estimate & BOQ")} subtitle="Calculate quantities, material, labour and cost"><Empty text="Create a project first (Projects page)." /></Page>;
  if (!allowed) return <Page title={t("Estimate & BOQ")} subtitle="Calculate quantities, material, labour and cost"><Empty text="You don't have Estimate access for this project. Ask the owner." /></Page>;

  const tabs = [
    { id: "overview", label: "Overview", icon: <LayoutDashboard size={18} /> }, { id: "takeoff", label: "Quantity Takeoff", icon: <Ruler size={18} /> },
    { id: "material", label: "Material Estimate", icon: <Package size={18} /> }, { id: "cost", label: "Cost Analysis", icon: <IndianRupee size={18} /> },
    { id: "boq", label: "BOQ", icon: <ClipboardList size={18} /> }, { id: "rates", label: "Rate Library", icon: <Library size={18} /> },
    { id: "compare", label: "Comparisons", icon: <GitCompare size={18} /> }, { id: "reports", label: "Reports", icon: <FileText size={18} /> },
    { id: "bbs", label: "BBS (Steel)", icon: <Ruler size={18} /> },
  ];

  const noResult = (
    <Card><Empty icon={<Calculator className="text-slate-400" />} text="No estimate yet – enter the sizes and calculate.">
      <button className="btn-primary btn-sm mt-1" onClick={() => setShowInputs(true)}><SlidersHorizontal size={14} />Enter sizes</button></Empty></Card>
  );

  const filters = (
    <div className="mb-3 flex flex-wrap gap-2">
      <select className="input w-auto" value={cat} onChange={(e) => setCat(e.target.value)}><option value="all">All Categories</option>{cats.map((c) => <option key={c}>{c}</option>)}</select>
      <select className="input w-auto" value={floor} onChange={(e) => setFloor(e.target.value)}><option value="all">All Floors</option>{floors.map((f) => <option key={f}>{f}</option>)}</select>
      <div className="relative min-w-[180px] flex-1"><Search size={16} className="absolute left-3 top-2.5 text-slate-400" /><input className="input pl-9" placeholder="Search items..." value={q} onChange={(e) => setQ(e.target.value)} /></div>
      <span className="input w-auto bg-slate-50 text-slate-600">Units: Metric</span>
    </div>
  );

  const takeoffTable = (
    <div className="overflow-x-auto rounded-lg border border-line">
      <table className="w-full min-w-[720px]">
        <thead><tr><th className="table-th">#</th><th className="table-th">Item</th><th className="table-th">Floor</th><th className="table-th text-right">Quantity</th><th className="table-th">Unit</th><th className="table-th text-right">Rate (₹)</th><th className="table-th text-right">Amount (₹)</th></tr></thead>
        <tbody>{items.map((i) => (
          <tr key={i.sl}><td className="table-td">{i.sl}</td><td className="table-td text-navy-ink">{i.description}</td><td className="table-td text-xs text-slate-500">{i.floor}</td>
            <td className="table-td text-right">{num(i.qty)}</td><td className="table-td">{i.unit}</td><td className="table-td text-right">{inr(i.rate)}</td><td className="table-td text-right font-semibold">{inr(i.amount)}</td></tr>
        ))}</tbody>
      </table>
    </div>
  );

  const materialTable = (
    <div className="overflow-x-auto rounded-lg border border-line">
      <table className="w-full min-w-[560px]">
        <thead><tr><th className="table-th">Material (incl. wastage)</th><th className="table-th text-right">Quantity</th><th className="table-th">Unit</th><th className="table-th text-right">Rate (₹)</th><th className="table-th text-right">Amount (₹)</th></tr></thead>
        <tbody>{result?.materials.map((m) => (
          <tr key={m.code}><td className="table-td font-semibold text-navy-ink">{m.name}</td><td className="table-td text-right">{num(m.qty)}</td><td className="table-td">{m.unit}</td><td className="table-td text-right">{inr(m.rate)}</td><td className="table-td text-right font-semibold">{inr(m.amount)}</td></tr>
        ))}</tbody>
        <tfoot><tr><td className="table-td font-bold" colSpan={4}>Total materials</td><td className="table-td text-right font-bold">{inr(tt?.materials)}</td></tr></tfoot>
      </table>
    </div>
  );

  const labourTable = (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full min-w-[520px]">
          <thead><tr><th className="table-th">Labour trade</th><th className="table-th text-right">Man-days</th><th className="table-th text-right">Day wage (₹)</th><th className="table-th text-right">Amount (₹)</th></tr></thead>
          <tbody>{result?.labour.map((l) => (
            <tr key={l.code}><td className="table-td font-semibold text-navy-ink">{l.name}</td><td className="table-td text-right">{num(l.qty, 1)}</td><td className="table-td text-right">{inr(l.rate)}</td><td className="table-td text-right font-semibold">{inr(l.amount)}</td></tr>
          ))}</tbody>
          <tfoot><tr><td className="table-td font-bold">Total labour</td><td className="table-td text-right font-bold">{num(tt?.man_days || 0, 0)}</td><td className="table-td" /><td className="table-td text-right font-bold">{inr(tt?.labour)}</td></tr></tfoot>
        </table>
      </div>
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full min-w-[520px]">
          <thead><tr><th className="table-th">Equipment hire</th><th className="table-th text-right">Qty</th><th className="table-th">Unit</th><th className="table-th text-right">Rate (₹)</th><th className="table-th text-right">Amount (₹)</th></tr></thead>
          <tbody>{result?.equipment.map((e) => (
            <tr key={e.code}><td className="table-td font-semibold text-navy-ink">{e.name}</td><td className="table-td text-right">{num(e.qty, 1)}</td><td className="table-td">{e.unit}</td><td className="table-td text-right">{inr(e.rate)}</td><td className="table-td text-right font-semibold">{inr(e.amount)}</td></tr>
          ))}</tbody>
        </table>
      </div>
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full min-w-[520px]">
          <thead><tr><th className="table-th">Extras</th><th className="table-th">Basis</th><th className="table-th text-right">Amount (₹)</th></tr></thead>
          <tbody>{result?.extras.map((e) => (
            <tr key={e.name}><td className="table-td font-semibold text-navy-ink">{e.name}</td><td className="table-td">{e.basis}</td><td className="table-td text-right font-semibold">{inr(e.amount)}</td></tr>
          ))}</tbody>
        </table>
      </div>
    </div>
  );

  const boqTable = (
    <div className="overflow-x-auto rounded-lg border border-line">
      <table className="w-full min-w-[900px]">
        <thead><tr><th className="table-th w-8" /><th className="table-th">#</th><th className="table-th">Description</th><th className="table-th">Floor</th><th className="table-th text-right">Qty</th><th className="table-th">Unit</th>
          <th className="table-th text-right">Material</th><th className="table-th text-right">Labour</th><th className="table-th text-right">Equip.</th><th className="table-th text-right">Amount (₹)</th></tr></thead>
        <tbody>{items.map((i) => (
          <Fragment key={i.sl}>
            <tr className="cursor-pointer hover:bg-slate-50" onClick={() => setOpen(open === i.sl ? null : i.sl)}>
              <td className="table-td">{open === i.sl ? <ChevronDown size={14} /> : <ChevronRight size={14} />}</td>
              <td className="table-td">{i.sl}</td><td className="table-td text-navy-ink">{i.description}</td><td className="table-td text-xs text-slate-500">{i.floor}</td>
              <td className="table-td text-right">{num(i.qty)}</td><td className="table-td">{i.unit}</td>
              <td className="table-td text-right">{inr(i.material_cost)}</td><td className="table-td text-right">{inr(i.labour_cost)}</td><td className="table-td text-right">{inr(i.equipment_cost)}</td>
              <td className="table-td text-right font-semibold">{inr(i.amount)}</td>
            </tr>
            {open === i.sl && (
              <tr><td colSpan={10} className="border-t border-line bg-slate-50/70 px-6 py-3 text-xs text-slate-600">
                <div className="mb-1 font-bold text-navy-ink">Rate analysis – {rupees(i.rate)} per {i.unit}</div>
                {i.materials.map((m) => <div key={m.name}>Material: {m.name} – {num(m.qty, 3)} {m.unit} × ₹{inr(m.rate)} = ₹{inr(m.amount)}</div>)}
                {i.labour.map((l) => <div key={l.name}>Labour: {l.name} – {num(l.days)} days × ₹{inr(l.rate)} = ₹{inr(l.amount)}</div>)}
                {i.equipment.map((e) => <div key={e.name}>Equipment: {e.name} – {num(e.qty)} {e.unit} × ₹{inr(e.rate)} = ₹{inr(e.amount)}</div>)}
              </td></tr>
            )}
          </Fragment>
        ))}</tbody>
        <tfoot><tr><td className="table-td" colSpan={6}><b>Total (before extras)</b></td><td className="table-td text-right font-bold">{inr(tt?.materials)}</td><td className="table-td text-right font-bold">{inr(tt?.labour)}</td><td className="table-td text-right font-bold">{inr(tt?.equipment)}</td><td className="table-td text-right font-bold">{inr((tt?.materials || 0) + (tt?.labour || 0) + (tt?.equipment || 0))}</td></tr></tfoot>
      </table>
    </div>
  );

  const floorTable = result && (
    <div className="overflow-x-auto rounded-lg border border-line">
      <table className="w-full min-w-[520px]">
        <thead><tr><th className="table-th">Floor</th><th className="table-th text-right">Built-up Area</th><th className="table-th text-right">Material Cost</th><th className="table-th text-right">Labour Cost</th><th className="table-th text-right">Total Cost</th></tr></thead>
        <tbody>{result.floors.map((f) => (
          <tr key={f.floor}><td className="table-td">{f.floor}</td><td className="table-td text-right">{f.builtup_sqft ? `${inr(f.builtup_sqft)} sq ft` : "—"}</td><td className="table-td text-right">{rupees(f.material_cost)}</td><td className="table-td text-right">{rupees(f.labour_cost)}</td><td className="table-td text-right font-semibold">{rupees(f.total)}</td></tr>
        ))}</tbody>
        <tfoot><tr><td className="table-td font-bold">Total</td><td className="table-td text-right font-bold">{inr(tt?.builtup_sqft)} sq ft</td><td className="table-td text-right font-bold">{rupees(tt?.materials)}</td><td className="table-td text-right font-bold">{rupees(tt?.labour)}</td><td className="table-td text-right font-bold">{rupees((tt?.materials || 0) + (tt?.labour || 0) + (tt?.equipment || 0))}</td></tr></tfoot>
      </table>
      <p className="px-3 py-2 text-[11px] text-slate-500">Extras ({rupees(tt?.extras)}) are added on the total, not per floor.</p>
    </div>
  );

  const notes = result && (result.warnings.length > 0 || result.assumptions.length > 0) && (
    <Card title="Assumptions & checks" icon={<TriangleAlert size={20} />}>
      {result.warnings.map((w) => <p key={w} className="mb-1 rounded-md bg-amber-50 px-3 py-1.5 text-sm text-amber-800">⚠ {w}</p>)}
      <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-600">{result.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
      <p className="mt-2 text-xs text-slate-500">{result.note}</p>
    </Card>
  );

  const exportsCard = (
    <Card title="Export & Reports" icon={<Download size={20} />}>
      <ul className="divide-y divide-line">
        {([["Download BOQ (Excel)", "excel", FileSpreadsheet, "text-emerald-600"], ["PDF Estimate Report", "pdf", FileText, "text-red-500"],
          ["Detailed Quantity Report (Excel)", "excel", Ruler, "text-brand-600"], ["Material List (Excel)", "excel", Package, "text-violet-600"],
          ["Rate Analysis Report (Excel)", "excel", BarChart3, "text-amber-600"], ["Project Summary (PDF)", "pdf", FileText, "text-brand-600"]] as const).map(([l, k, I, c]) => (
          <li key={l}><button className="flex w-full items-center gap-3 py-2.5 text-left text-sm hover:text-brand-600" onClick={() => doExport(k)}><I size={18} className={c} /><span className="flex-1">{l}</span><ChevronRight size={16} className="text-slate-400" /></button></li>
        ))}
      </ul>
      {(!saved || dirty) && <p className="mt-2 text-xs text-amber-700">Save the estimate first – reports come from a saved version.</p>}
    </Card>
  );

  return (
    <Page title={t("Estimate & BOQ")} subtitle="Calculate quantities, material, labour and cost" actions={header}>
      <PillTabs tabs={tabs} value={tab} onChange={setTab} />

      {tab === "overview" && (
        <>
          <div className="grid gap-4 2xl:grid-cols-[1fr_420px]">
            <Steps step={step} />
            <div className="card p-4">
              <div className="mb-2 flex items-center gap-2 text-sm font-bold text-navy-ink"><Layers size={18} />Input Methods</div>
              <div className="grid grid-cols-5 gap-2 text-center text-[11px]">
                <button onClick={pickDesign} className={`rounded-lg p-2 ${inputs?.geometry ? "border-2 border-brand-600 bg-brand-50" : "border border-line hover:border-brand-100"}`}><PenLine size={20} className="mx-auto text-brand-600" /><div className="mt-1 font-bold text-navy-ink">2D Drawing</div><div className="text-slate-500">From Design</div></button>
                {([["Image", "JPG/PNG", FileImage], ["PDF Plan", "PDF/DXF", FileText]] as [string, string, any][]).map(([l, sub, I]) => (
                  <button key={l} onClick={() => nav("/design?tab=upload")} title="Upload in Design Studio – the plan is read, you confirm it, then estimate from it" className="rounded-lg border border-line p-2 hover:border-brand-100"><I size={20} className="mx-auto text-brand-600" /><div className="mt-1 font-bold text-navy-ink">{l}</div><div className="text-slate-500">{sub}</div></button>
                ))}
                <button onClick={() => setShowExcel(true)} title="Download the Excel template, fill it, upload it back" className={`rounded-lg p-2 ${inputs?.source === "excel" ? "border-2 border-brand-600 bg-brand-50" : "border border-line hover:border-brand-100"}`}><FileSpreadsheet size={20} className="mx-auto text-emerald-600" /><div className="mt-1 font-bold text-navy-ink">Excel</div><div className="text-slate-500">BOQ/Rate</div></button>
                <button onClick={() => setShowInputs(true)} className={`rounded-lg p-2 ${!inputs?.geometry ? "border-2 border-brand-600 bg-brand-50" : "border border-line hover:border-brand-100"}`}><SlidersHorizontal size={20} className="mx-auto text-brand-600" /><div className="mt-1 font-bold text-navy-ink">Manual</div><div className="text-slate-500">Enter Sizes</div></button>
              </div>
            </div>
          </div>

          <div className="grid gap-4 xl:grid-cols-[1fr_2fr]">
            <Card title="Project Overview" icon={<ClipboardList size={20} />}>
              <div className="flex gap-4">
                <img src="/images/estimate_house.jpg" alt="" className="h-28 w-36 shrink-0 rounded-lg object-cover" />
                <dl className="grid flex-1 grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
                  <dt className="text-slate-500">Project</dt><dd className="font-semibold text-navy-ink">{currentProject.name}</dd>
                  <dt className="text-slate-500">Built-up Area</dt><dd>{tt ? `${inr(tt.builtup_sqft)} sq ft` : "—"}</dd>
                  <dt className="text-slate-500">Floors</dt><dd>{inputs ? (inputs.floor_areas_sqft.length === 1 ? "G" : `${inputs.stilt ? "Stilt" : "G"} + ${inputs.floor_areas_sqft.length - 1}`) : currentProject.floors}</dd>
                  <dt className="text-slate-500">Source</dt><dd>{inputs?.geometry ? <Badge color="blue">2D Drawing{inputs.design_id ? ` #${inputs.design_id}` : ""}</Badge> : <Badge>Manual sizes</Badge>}</dd>
                  <dt className="text-slate-500">Structure</dt><dd>{inputs?.structure === "load_bearing" ? "Load bearing" : "RCC (framed)"}</dd>
                  <dt className="text-slate-500">Location</dt><dd>{[currentProject.location, currentProject.state === "Tamil Nadu" ? "TN" : currentProject.state].filter(Boolean).join(", ") || "—"}</dd>
                </dl>
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                <button className="btn-outline btn-sm" onClick={() => setShowInputs(true)}><SlidersHorizontal size={14} />Edit Estimate Inputs</button>
                <button className="btn-ghost btn-sm" onClick={() => nav("/projects")}>Edit Project Details</button>
              </div>
              {versions.length > 0 && (
                <div className="mt-3">
                  <span className="label">Saved versions</span>
                  <select className="input" value={saved?.id ?? ""} onChange={(e) => e.target.value && openVersion(Number(e.target.value))}>
                    <option value="">{dirty ? "— unsaved calculation —" : "— choose —"}</option>
                    {versions.map((v) => <option key={v.id} value={v.id}>v{v.version} · {v.title} · {lakhs(v.grand_total)}</option>)}
                  </select>
                </div>
              )}
            </Card>
            <Card title="Estimate Summary" icon={<FileText size={20} />}
              action={result && <div className="flex items-center gap-2">{dirty ? <Badge color="amber">Not saved</Badge> : saved && <Badge color="green">Saved v{saved.version}</Badge>}<Badge color="blue">{result.spec_level}</Badge></div>}>
              {!result ? <Empty text="Enter sizes and calculate to see the estimate." /> : (
                <div className="grid gap-3 sm:grid-cols-2 min-[1800px]:grid-cols-4">
                  <SummaryCard tone="bg-brand-50" icon={<Package size={40} className="text-brand-600" />} label="Total Quantity (Major Items)" value={inr(tt!.cement_bags)} sub="Cement Bags" extra={<Badge color="green">incl. 2% wastage</Badge>} />
                  <SummaryCard tone="bg-emerald-50" icon={<div className="flex h-11 w-11 items-center justify-center rounded-full bg-emerald-600 text-xl font-bold text-white">₹</div>} label="Total Cost (Estimated)" value={rupees(tt!.grand_total)} sub="Including Material + Labour" />
                  <SummaryCard tone="bg-orange-50" icon={<BarChart3 size={40} className="text-orange-500" />} label="Cost per sq ft" value={rupees(tt!.cost_per_sqft)} sub="(Built-up Area)" />
                  <SummaryCard tone="bg-violet-50" icon={<CalendarClock size={40} className="text-violet-600" />} label="Project Duration (Est.)" value={`${tt!.duration_months}`} sub="Months" />
                </div>
              )}
              {result && (
                <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
                  {[["Steel", `${inr(tt!.steel_kg)} kg`], ["Bricks", `${inr(tt!.bricks)} nos`], ["M-Sand", `${tt!.msand_m3} m³`], ["Labour", `${inr(tt!.man_days)} man-days`]].map(([k, v]) => (
                    <div key={k} className="rounded-lg bg-slate-50 px-3 py-2"><div className="text-slate-500">{k}</div><div className="font-bold text-navy-ink">{v}</div></div>
                  ))}
                </div>
              )}
            </Card>
          </div>

          {!result ? noResult : (
            <>
              <div className="grid gap-4 2xl:grid-cols-[1.7fr_1fr]">
                <Card>
                  <div className="-mx-5 -mt-0 mb-4 flex flex-wrap gap-2 border-b border-line px-5 pt-4 pb-3">
                    <SegTabs value={tableTab} onChange={setTableTab} tabs={[{ id: "takeoff", label: "Quantity Takeoff" }, { id: "material", label: "Material Estimate" }, { id: "labour", label: "Labour Cost" }, { id: "boq", label: "Combined BOQ" }]} />
                  </div>
                  {(tableTab === "takeoff" || tableTab === "boq") && filters}
                  <div className="max-h-[520px] overflow-y-auto">
                    {tableTab === "takeoff" && takeoffTable}{tableTab === "material" && materialTable}{tableTab === "labour" && labourTable}{tableTab === "boq" && boqTable}
                  </div>
                </Card>
                <div className="space-y-4">
                  <Card title="3D Model" icon={<HardHat size={20} />}><Est3D designId={inputs?.design_id} onPick={pickDesign} /></Card>
                  {notes}
                </div>
              </div>
              <div className="grid gap-4 xl:grid-cols-[1fr_1.2fr_0.8fr]">
                <Card title="Cost Breakdown" icon={<IndianRupee size={20} />}><Donut data={result.breakdown} total={tt!.grand_total} /></Card>
                <Card title="Floor-wise Summary" icon={<Layers size={20} />}>{floorTable}</Card>
                {exportsCard}
              </div>
            </>
          )}
        </>
      )}

      {tab === "takeoff" && (result ? <Card title="Quantity Takeoff" icon={<Ruler size={20} />}>{filters}{takeoffTable}</Card> : noResult)}
      {tab === "material" && (result ? <Card title="Material Estimate" icon={<Package size={20} />}>{materialTable}</Card> : noResult)}
      {tab === "cost" && (result ? <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]"><Card title="Labour, Equipment & Extras" icon={<Users size={20} />}>{labourTable}</Card>
        <div className="space-y-4"><Card title="Cost Breakdown" icon={<IndianRupee size={20} />}><Donut data={result.breakdown} total={tt!.grand_total} /></Card><Card title="Floor-wise Summary" icon={<Layers size={20} />}>{floorTable}</Card></div></div> : noResult)}
      {tab === "boq" && (result ? <Card title="Bill of Quantities (click a row for rate analysis)" icon={<ClipboardList size={20} />}>{filters}{boqTable}</Card> : noResult)}
      {tab === "rates" && <RateLibrary defaultState={state} />}
      {tab === "bbs" && pid && <BbsTab pid={pid} code={currentProject?.code || "Nexora"} />}
      {tab === "compare" && (
        <div className="space-y-4">
          <Card title="Specification comparison (same building)" icon={<GitCompare size={20} />}
            action={<button className="btn-primary btn-sm" onClick={runCompare} disabled={busy || !inputs}><Hammer size={14} />Compare Basic / Standard / Premium</button>}>
            {!cmp ? <p className="text-sm text-slate-500">Runs the same inputs at all three spec levels. Quantities stay the same – only material quality/brand rates change.</p> : (
              <div className="overflow-x-auto rounded-lg border border-line">
                <table className="w-full min-w-[560px]">
                  <thead><tr><th className="table-th" />{["basic", "standard", "premium"].map((s) => <th key={s} className="table-th text-right capitalize">{s}</th>)}</tr></thead>
                  <tbody>
                    {[["Total cost", "grand_total"], ["Cost per sq ft", "cost_per_sqft"], ["Materials", "materials"], ["Labour", "labour"], ["Extras", "extras"]].map(([l, k]) => (
                      <tr key={k}><td className="table-td font-semibold">{l}</td>{["basic", "standard", "premium"].map((s) => <td key={s} className="table-td text-right">{rupees(cmp[s].totals[k])}</td>)}</tr>
                    ))}
                    {cmp.standard.breakdown.map((b) => (
                      <tr key={b.group}><td className="table-td text-slate-600">{b.group}</td>{["basic", "standard", "premium"].map((s) => <td key={s} className="table-td text-right text-slate-600">{rupees(cmp[s].breakdown.find((x) => x.group === b.group)?.amount)}</td>)}</tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
          <Card title="Saved versions" icon={<ClipboardList size={20} />}>
            {!versions.length ? <Empty text="No saved versions yet." /> : (
              <div className="overflow-x-auto rounded-lg border border-line">
                <table className="w-full min-w-[640px]">
                  <thead><tr><th className="table-th">Version</th><th className="table-th">Title</th><th className="table-th">Spec</th><th className="table-th">Rates</th><th className="table-th text-right">Total</th><th className="table-th text-right">₹/sq ft</th><th className="table-th">Saved</th><th className="table-th" /></tr></thead>
                  <tbody>{versions.map((v) => (
                    <tr key={v.id}><td className="table-td font-bold">v{v.version}</td><td className="table-td">{v.title}</td><td className="table-td capitalize">{v.spec_level}</td><td className="table-td">{v.rate_state}</td>
                      <td className="table-td text-right">{rupees(v.grand_total)}</td><td className="table-td text-right">{rupees(v.cost_per_sqft)}</td><td className="table-td text-xs">{fmtDateTime(v.created_at)}</td>
                      <td className="table-td text-right"><button className="btn-ghost btn-sm" onClick={() => { openVersion(v.id); setTab("overview"); }}>Open</button>
                        <OwnerDelete entity="estimate" id={v.id} title={`v${v.version} · ${v.title}`} onDone={() => { if (saved?.id === v.id) setSaved(null); loadVersions(); }} /></td></tr>
                  ))}</tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      )}
      {tab === "reports" && <div className="grid gap-4 lg:grid-cols-2">{exportsCard}{notes || <Card><Empty text="Calculate an estimate first." /></Card>}</div>}

      {pid && <ExcelModal open={showExcel} onClose={() => setShowExcel(false)} pid={pid} code={currentProject?.code || "Nexora"} inputs={inputs} state={state}
        isOwner={user?.role === "owner"} onImported={fromExcel} onRatesChanged={() => api(`/api/rates?state=${encodeURIComponent(state)}`).then((d) => setRates(d.items)).catch(() => {})} />}
      <InputsModal open={showInputs} onClose={() => setShowInputs(false)} inputs={inputs} setInputs={(v) => { setInputs(v); }}
        state={state} setState={setState} onCalculate={() => calculate()} rates={rates} needs={needs} />
      <Modal open={!!designPick} onClose={() => setDesignPick(null)} title="Estimate from a 2D drawing (Design Studio)">
        <p className="mb-3 text-sm text-slate-600">Choose a saved design – walls, doors, windows, rooms and floor areas are measured from it.</p>
        <ul className="divide-y divide-line rounded-lg border border-line">
          {(designPick || []).map((d) => (
            <li key={d.id}>
              <button className="flex w-full items-center gap-3 px-4 py-3 text-left text-sm hover:bg-slate-50" onClick={() => applyDesign(d.id)}>
                <span className="font-bold text-navy-ink">v{d.version}</span>
                <span className="flex-1">{d.title}<span className="block text-xs text-slate-500">{inr(d.builtup_sqft)} sq ft · {d.summary?.bedrooms} bed / {d.summary?.toilets} toilet · {fmtDateTime(d.created_at)}</span></span>
                <span className="font-semibold text-navy-ink">{rupees(d.estimate_total)}</span>
              </button>
            </li>
          ))}
        </ul>
        <div className="mt-4 flex justify-between"><button className="btn-ghost" onClick={() => nav("/design")}>Open Design Studio</button><button className="btn-ghost" onClick={() => setDesignPick(null)}>Close</button></div>
      </Modal>
      {busy && <div className="fixed bottom-4 left-1/2 z-50 -translate-x-1/2 rounded-full bg-navy-900 px-4 py-2 text-sm text-white shadow-lg">Calculating…</div>}
    </Page>
  );
}
