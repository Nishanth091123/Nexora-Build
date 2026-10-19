import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import DrawingImport from "../components/design/DrawingImport";
import {
  Box, Calculator, Check, Copy, Download, FileText, GitCompare, Layers, Lightbulb, MapPin, PenSquare, Plus,
  Redo2, RotateCcw, Ruler, Save, Sparkles, Trash2, TriangleAlert, Undo2, Upload, Wand2, Eye, EyeOff, Compass,
} from "lucide-react";
import Page from "../components/Page";
import OwnerDelete from "../components/OwnerDelete";
import PlanSvg from "../components/design/PlanSvg";
import Plan3D from "../components/design/Plan3D";
import { Badge, Card, Empty, Field, PhaseNote, PillTabs, Toggle, toast } from "../components/ui";
import { api, ApiError, downloadFile, fmtDateTime, inr, lakhs, num, rupees } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";
import { FACINGS, ROOM_TYPES, clone, type Plan, type Room } from "../lib/plan";

type Tab = "ai" | "editor" | "3d" | "upload" | "rev";
type Quick = { totals: Record<string, number>; breakdown: { group: string; amount: number; pct: number }[]; spec_level: string; rates_state: string; warnings: string[] };
type DesignRow = { id: number; version: number; title: string; prompt: string; source: string; spec_level: string; estimate_total: number; cost_per_sqft: number; builtup_sqft: number; summary: any; created_at: string; parent_id: number | null };
type Suggestion = { label: string; requirements: any; notes: string[] };

const EXAMPLES = [
  "30x40 east facing 2BHK, car parking, G+1, 30 ft road",
  "20x30 west facing 1 bedroom, 20 ft road, ground floor only",
  "40x60 south facing 3BHK with pooja and car parking, 40 ft road, G+1",
  "30x50 north east facing 4 bedroom 4 toilets stilt+2, 30 feet road",
];
const LEVEL_KEYS: [string, string, "n" | "b"][] = [["bedrooms", "Bedrooms", "n"], ["attached_toilets", "Attached toilets", "n"], ["common_toilets", "Common toilets", "n"],
  ["hall", "Hall", "b"], ["lounge", "Lounge", "b"], ["kitchen", "Kitchen", "b"], ["dining", "Dining", "b"], ["pooja", "Pooja", "b"], ["parking_car", "Car", "b"], ["parking_bike", "Bike", "b"]];

const defaultForm = { plot_w_ft: "", plot_d_ft: "", facing: "", road_width_m: "", floors: "", stilt: false, bedrooms: "", toilets: "",
  parking_car: false, parking_bike: false, pooja: false, dining: true, attached: true, corner: false, same_each_floor: false, area_type: "other", floor_height_ft: 10 };

function Stat({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return <div className="rounded-lg bg-slate-50 px-3 py-2"><div className="text-xs text-slate-500">{label}</div><div className="text-lg font-extrabold text-navy-ink">{value}</div>{sub && <div className="text-xs text-slate-500">{sub}</div>}</div>;
}

export default function DesignPage() {
  const { t } = useI18n();
  const nav = useNavigate();
  const { currentProject } = useAuth();
  const pid = currentProject?.id;
  const allowed = !!currentProject?.permissions?.design;
  const [params] = useSearchParams();
  const [tab, setTab] = useState<Tab>(() => (["ai", "editor", "3d", "upload", "rev"].includes(params.get("tab") || "") ? params.get("tab") as Tab : "ai"));
  const [text, setText] = useState("");
  const [understood, setUnderstood] = useState<string[]>([]);
  const [questions, setQuestions] = useState<string[]>([]);
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [form, setForm] = useState<any>(defaultForm);
  const [req, setReq] = useState<any>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [aiPlan, setAiPlan] = useState<Plan | null>(null);
  const [level, setLevel] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);
  const [past, setPast] = useState<string[]>([]);
  const [future, setFuture] = useState<string[]>([]);
  const [stale, setStale] = useState(false);
  const [grid, setGrid] = useState(0.5);
  const [spec, setSpec] = useState("standard");
  const [quick, setQuick] = useState<Quick | null>(null);
  const [prevTotal, setPrevTotal] = useState<number | null>(null);
  const [saved, setSaved] = useState<{ id: number; version: number; title: string } | null>(null);
  const [dirty, setDirty] = useState(false);
  const [designs, setDesigns] = useState<DesignRow[]>([]);
  const [busy, setBusy] = useState("");
  const [newType, setNewType] = useState("bedroom");
  const [roof, setRoof] = useState(false);
  const [cmpA, setCmpA] = useState<number | "">("");
  const [cmpB, setCmpB] = useState<number | "">("");
  const [cmp, setCmp] = useState<any>(null);
  const recomputeTimer = useRef<number | null>(null);
  const planRef = useRef<Plan | null>(null);
  planRef.current = plan;

  const loadDesigns = useCallback(async () => {
    if (!pid) return [];
    const d = await api<DesignRow[]>(`/api/projects/${pid}/designs`);
    setDesigns(d);
    return d;
  }, [pid]);

  const formFromReq = (r: any) => {
    if (!r) return;
    const lv = r.levels || [];
    const stilt = lv.some((l: any) => l.stilt);
    const sum = (k: string) => lv.reduce((a: number, l: any) => a + Number(l[k] || 0), 0);
    setForm((f: any) => ({ ...f, plot_w_ft: r.plot_w_ft ?? f.plot_w_ft, plot_d_ft: r.plot_d_ft ?? f.plot_d_ft, facing: r.facing || f.facing,
      road_width_m: r.road_width_m ?? f.road_width_m, floors: lv.length || f.floors, stilt, bedrooms: sum("bedrooms"),
      toilets: sum("attached_toilets") + sum("common_toilets"), parking_car: lv.some((l: any) => l.parking_car && !l.stilt) || f.parking_car,
      pooja: lv.some((l: any) => l.pooja) || f.pooja, corner: !!r.corner, area_type: r.area_type || "other", floor_height_ft: r.floor_height_ft || 10 }));
  };
  const openDesign = async (id: number) => {
    const d = await api<any>(`/api/designs/${id}`);
    setPlan(d.plan); setAiPlan(d.plan); setReq(d.plan.requirements); formFromReq(d.plan.requirements); setSaved({ id: d.id, version: d.version, title: d.title });
    setDirty(false); setPast([]); setFuture([]); setLevel(0); setSelected(null); setStale(false); setText(d.prompt || ""); setSpec(d.spec_level || "standard");
    runQuick(d.plan, d.spec_level || "standard", true);
  };

  useEffect(() => {
    if (!pid || !allowed) return;
    setPlan(null); setSaved(null); setReq(null); setQuick(null); setCmp(null); setQuestions([]); setSuggestions([]);
    setForm({ ...defaultForm, plot_w_ft: currentProject?.plot_width && currentProject.unit === "ft" ? currentProject.plot_width : "",
      plot_d_ft: currentProject?.plot_length && currentProject.unit === "ft" ? currentProject.plot_length : "" });
    const want = Number(params.get("design")) || 0;
    loadDesigns().then((d) => { const pick = d.find((x) => x.id === want) || d[0]; if (pick) openDesign(pick.id); }).catch((e) => toast(e.message, "err"));
  }, [pid, allowed]);

  // ---------------------------------------------------------------- AI flow
  const runQuick = async (p: Plan, s = spec, initial = false) => {
    if (!pid) return;
    try {
      const q = await api<Quick>(`/api/projects/${pid}/design/quick-estimate`, { body: { plan: p, spec_level: s, state: currentProject?.state || "Tamil Nadu" } });
      setPrevTotal(initial ? null : quick?.totals.grand_total ?? null);
      setQuick(q);
    } catch (e: any) { toast(e.message, "err"); }
  };

  const showPlan = (p: Plan, source: "ai" | "edit") => {
    setPlan(p); setStale(false);
    if (source === "ai") { setAiPlan(p); setPast([]); setFuture([]); setLevel(0); setSelected(null); setSaved(null); setDirty(true); setQuick(null); }
    runQuick(p, spec, source === "ai");
  };

  const generate = async (requirements: any) => {
    if (!pid) return;
    setBusy("gen"); setSuggestions([]);
    try {
      const p = await api<Plan>(`/api/projects/${pid}/design/generate`, { body: { requirements } });
      setReq(p.requirements); setQuestions([]); formFromReq(p.requirements);
      showPlan(p, "ai");
      toast("Plan generated – setbacks applied automatically");
    } catch (e: any) {
      if (e instanceof ApiError && e.questions.length) { setQuestions(e.questions); setSuggestions(e.detail?.suggestions || []); }
      toast(e.message, "err");
    } finally { setBusy(""); }
  };

  const understand = async () => {
    if (!pid || !text.trim()) return toast("Type what you want to build", "err");
    setBusy("parse");
    try {
      const r = await api<any>(`/api/projects/${pid}/design/parse`, { body: { text } });
      setUnderstood(r.understood); setQuestions(r.questions); setSuggestions([]);
      setForm((f: any) => ({ ...f, ...Object.fromEntries(Object.entries(r.partial).filter(([k]) => !k.startsWith("_"))) }));
      if (r.requirements) { setReq(r.requirements); await generate(r.requirements); }
      else toast("Please answer the questions below", "err");
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(""); }
  };

  const buildFromForm = async () => {
    if (!pid) return;
    setBusy("form");
    try {
      const answers = { ...form, floors: Number(form.floors) || "", bedrooms: form.bedrooms === "" ? "" : Number(form.bedrooms) };
      const r = await api<any>(`/api/projects/${pid}/design/requirements`, { body: { answers } });
      setReq(r); await generate(r);
    } catch (e: any) {
      if (e instanceof ApiError && e.questions.length) setQuestions(e.questions.map((q: string) => `Please confirm: ${q}`));
      toast(e.message, "err");
    } finally { setBusy(""); }
  };

  // ---------------------------------------------------------------- editing
  const recompute = (p: Plan) => {
    if (recomputeTimer.current) window.clearTimeout(recomputeTimer.current);
    recomputeTimer.current = window.setTimeout(async () => {
      try {
        const r = await api<Plan>(`/api/projects/${pid}/design/recompute`, { body: { plan: p } });
        if (planRef.current && JSON.stringify(planRef.current.levels.map((l) => l.rooms)) !== JSON.stringify(p.levels.map((l) => l.rooms))) return; // newer edit pending
        showPlan(r, "edit");
      } catch (e: any) { toast(e.message, "err"); }
    }, 450);
  };

  const setRooms = (rooms: Room[], commit: boolean) => {
    if (!plan) return;
    const next = clone(plan);
    next.levels[level].rooms = rooms;
    setPlan(next); setStale(true);
    if (commit) {
      setPast((p) => [...p.slice(-40), JSON.stringify(plan)]); setFuture([]); setDirty(true);
      recompute(next);
    }
  };
  const undo = () => {
    if (!past.length || !plan) return;
    const prev = JSON.parse(past[past.length - 1]);
    setFuture((f) => [JSON.stringify(plan), ...f]); setPast((p) => p.slice(0, -1)); setPlan(prev); setStale(true); setDirty(true); recompute(prev);
  };
  const redo = () => {
    if (!future.length || !plan) return;
    const nxt = JSON.parse(future[0]);
    setPast((p) => [...p, JSON.stringify(plan)]); setFuture((f) => f.slice(1)); setPlan(nxt); setStale(true); setDirty(true); recompute(nxt);
  };
  const rooms = plan?.levels[level]?.rooms || [];
  const sel = rooms.find((r) => r.id === selected) || null;
  const updateSel = (patch: Partial<Room>) => {
    if (!sel) return;
    const b = plan!.building;
    const r = { ...sel, ...patch };
    r.w = Math.max(2, Math.min(r.w, b.w)); r.d = Math.max(2, Math.min(r.d, b.d));
    r.x = Math.max(0, Math.min(r.x, b.w - r.w)); r.y = Math.max(0, Math.min(r.y, b.d - r.d));
    setRooms(rooms.map((x) => (x.id === sel.id ? r : x)), true);
  };
  const addRoom = () => {
    if (!plan) return;
    const b = plan.building;
    const label = ROOM_TYPES.find(([v]) => v === newType)?.[1] || newType;
    const id = `${newType}_n${Date.now() % 100000}`;
    const w = Math.min(10, b.w), d = Math.min(10, b.d);
    setRooms([...rooms, { id, type: newType, name: label, x: Math.round((b.w - w) / 2), y: Math.round((b.d - d) / 2), w, d }], true);
    setSelected(id);
  };
  const delRoom = () => { if (sel) { setRooms(rooms.filter((r) => r.id !== sel.id && r.parent !== sel.id), true); setSelected(null); } };
  const dupRoom = () => {
    if (!sel || !plan) return;
    const id = `${sel.type}_c${Date.now() % 100000}`;
    setRooms([...rooms, { ...sel, id, parent: undefined, x: Math.min(sel.x + 2, plan.building.w - sel.w), y: Math.min(sel.y + 2, plan.building.d - sel.d) }], true);
    setSelected(id);
  };
  const copyLevelFrom = (src: number) => {
    if (!plan || src === level) return;
    setRooms(clone(plan.levels[src].rooms), true);
  };

  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if (tab !== "editor" || (e.target as HTMLElement)?.tagName?.match(/INPUT|SELECT|TEXTAREA/)) return;
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "z") { e.preventDefault(); e.shiftKey ? redo() : undo(); }
      else if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "y") { e.preventDefault(); redo(); }
      else if (e.key === "Delete" && sel) delRoom();
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  });

  // ---------------------------------------------------------------- save / export / compare
  const save = async () => {
    if (!pid || !plan) return;
    if (stale) return toast("Wait a moment – walls are being updated", "err");
    const title = window.prompt("Name for this design version", saved ? `${saved.title} (edited)` : "Concept plan");
    if (title === null) return;
    setBusy("save");
    try {
      const d = await api<any>(`/api/projects/${pid}/designs`, { body: { plan, title, prompt: text, source: past.length ? "edited" : "ai", spec_level: spec,
        state: currentProject?.state || "Tamil Nadu", parent_id: saved?.id ?? null } });
      setSaved({ id: d.id, version: d.version, title: d.title }); setPlan(d.plan); setDirty(false); setQuick(d.estimate);
      await loadDesigns(); toast(`Saved as design v${d.version}`);
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(""); }
  };
  const exportAs = async (id: number, v: number, kind: "pdf" | "dxf") => {
    try { await downloadFile(`/api/designs/${id}/${kind}`, `${currentProject?.code}_Plan_v${v}.${kind}`); } catch (e: any) { toast(e.message, "err"); }
  };
  const runCompare = async () => {
    if (!cmpA || !cmpB || cmpA === cmpB) return toast("Choose two different versions", "err");
    try { setCmp(await api(`/api/designs/compare?a=${cmpA}&b=${cmpB}`)); } catch (e: any) { toast(e.message, "err"); }
  };
  const toEstimate = () => {
    if (!saved || dirty) return toast("Save this design first – the estimate uses a saved version", "err");
    nav(`/estimate?design=${saved.id}`);
  };

  useEffect(() => { if (designs.length >= 2 && !cmpA) { setCmpA(designs[1].id); setCmpB(designs[0].id); } }, [designs]);

  const setF = (k: string, v: any) => setForm((f: any) => ({ ...f, [k]: v }));
  const roadFt = form.road_width_m ? Math.round((Number(form.road_width_m) / 0.3048) * 10) / 10 : "";
  const tt = quick?.totals;
  const delta = prevTotal != null && tt ? tt.grand_total - prevTotal : null;
  const lvl = plan?.levels[level];
  const allWarnings = useMemo(() => (plan ? plan.levels.flatMap((l) => l.warnings) : []), [plan]);

  if (!currentProject) return <Page title={t("Design Studio")} subtitle="AI floor plans, 2D editing, 3D preview and revisions"><Empty text="Create a project first (Projects page)." /></Page>;
  if (!allowed) return <Page title={t("Design Studio")} subtitle="AI floor plans, 2D editing, 3D preview and revisions"><Empty text="You don't have Design access for this project. Ask the owner." /></Page>;

  const tabs = [
    { id: "ai" as Tab, label: "AI Floor Plan", icon: <Wand2 size={18} /> }, { id: "editor" as Tab, label: "2D Editor", icon: <PenSquare size={18} /> },
    { id: "3d" as Tab, label: "3D View", icon: <Box size={18} /> }, { id: "upload" as Tab, label: "Drawing Upload", icon: <Upload size={18} /> },
    { id: "rev" as Tab, label: "Revisions", icon: <Layers size={18} /> },
  ];

  const header = (
    <>
      <button className="btn-outline hidden sm:inline-flex" onClick={save} disabled={!plan || busy === "save" || (!dirty && !!saved)}><Save size={16} />Save</button>
      <button className="btn-primary hidden sm:inline-flex" onClick={toEstimate} disabled={!plan}><Calculator size={16} />Estimate</button>
    </>
  );

  const levelTabs = plan && (
    <div className="flex flex-wrap gap-2">
      {plan.levels.map((l, i) => (
        <button key={i} onClick={() => { setLevel(i); setSelected(null); }}
          className={`rounded-lg px-3 py-1.5 text-sm font-medium ${i === level ? "bg-navy-900 text-white" : "bg-slate-100 text-navy-ink hover:bg-slate-200"}`}>{l.name}</button>
      ))}
    </div>
  );

  const quickCard = (
    <Card title="Quick Estimate (auto-updates)" icon={<Calculator size={20} />}>
      <div className="mb-3"><div className="inline-flex overflow-hidden rounded-lg border border-line text-xs font-semibold">
        {["basic", "standard", "premium"].map((s) => (
          <button key={s} onClick={() => { setSpec(s); if (plan && !stale) runQuick(plan, s, true); setDirty(true); }}
            className={`px-2.5 py-1.5 capitalize ${spec === s ? "bg-brand-600 text-white" : "bg-white text-navy-ink hover:bg-brand-50"}`}>{s}</button>
        ))}
      </div></div>
      {!tt ? <p className="text-sm text-slate-500">Generate a plan to see the cost.</p> : (
        <>
          <div className="flex flex-wrap items-end gap-3">
            <div className="text-3xl font-extrabold text-navy-ink">{lakhs(tt.grand_total)}</div>
            <div className="pb-1 text-sm text-slate-500">{rupees(tt.cost_per_sqft)} / sq ft · {quick?.spec_level}</div>
            {delta !== null && Math.abs(delta) >= 1 && <Badge color={delta > 0 ? "red" : "green"}>{delta > 0 ? "+" : "−"}{rupees(Math.abs(delta))} after last change</Badge>}
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <Stat label="Built-up" value={`${inr(tt.builtup_sqft)} sft`} />
            <Stat label="Cement" value={`${inr(tt.cement_bags)} bags`} sub={`${num(tt.cement_bags_per_sqft)} / sft`} />
            <Stat label="Steel" value={`${inr(tt.steel_kg)} kg`} sub={`${num(tt.steel_kg_per_sqft)} / sft`} />
            <Stat label="Duration" value={`${tt.duration_months} months`} />
          </div>
          <p className="mt-2 text-xs text-slate-500">Quantities measured from this drawing (walls, doors, windows, rooms). Rates: {quick?.rates_state}. Full BOQ → “Open in Estimate”.</p>
        </>
      )}
    </Card>
  );

  const planCard = plan && lvl && (
    <Card title={`Plan – ${lvl.name}`} icon={<Ruler size={20} />} action={levelTabs}>
      <div className="aspect-[4/5] max-h-[640px] w-full rounded-lg border border-line bg-white p-1 sm:aspect-square">
        <PlanSvg plan={plan} level={level} stale={stale} />
      </div>
      <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Stat label="Built-up (this floor)" value={`${inr(lvl.summary.builtup_sqft)} sft`} />
        <Stat label="Carpet" value={`${inr(lvl.summary.carpet_sqft)} sft`} />
        <Stat label="Walls ext / int" value={`${num(lvl.summary.ext_wall_ft, 0)}' / ${num(lvl.summary.int230_wall_ft + lvl.summary.int115_wall_ft, 0)}'`} />
        <Stat label="Doors / windows" value={`${lvl.summary.main_doors + lvl.summary.doors + lvl.summary.toilet_doors} / ${lvl.summary.windows}`} />
      </div>
    </Card>
  );

  const setbackCard = plan && (
    <Card title="Setbacks – applied automatically" icon={<MapPin size={20} />}>
      <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
        {(["front", "rear", "left", "right"] as const).map((k) => (
          <div key={k} className="rounded-lg bg-orange-50 px-3 py-2"><div className="text-xs capitalize text-orange-700">{k}</div><div className="font-bold text-navy-ink">{plan.setbacks.m[k]} m</div><div className="text-xs text-slate-500">{plan.setbacks.ft[k]} ft</div></div>
        ))}
      </div>
      <ul className="mt-3 space-y-1 text-xs text-slate-600">{plan.setbacks.notes.map((n) => <li key={n}>• {n}</li>)}</ul>
      <div className="mt-2 text-xs text-slate-500">Buildable {plan.building.w}' × {plan.building.d}' · coverage {plan.setbacks.coverage_pct}% · height ≈ {plan.setbacks.height_m} m</div>
    </Card>
  );

  const notesCard = plan && (plan.notes.length > 0 || allWarnings.length > 0) && (
    <Card title="Notes & checks" icon={<Lightbulb size={20} />}>
      {plan.notes.length > 0 && <ul className="space-y-1 text-sm text-slate-700">{plan.notes.map((n, i) => <li key={i} className="flex gap-2"><Check size={15} className="mt-0.5 shrink-0 text-brand-600" />{n}</li>)}</ul>}
      {allWarnings.length > 0 && <ul className="mt-2 space-y-1 text-sm text-amber-800">{allWarnings.map((n, i) => <li key={i} className="flex gap-2"><TriangleAlert size={15} className="mt-0.5 shrink-0" />{n}</li>)}</ul>}
    </Card>
  );

  const reqTable = req && (
    <Card title="Rooms per floor (edit & regenerate)" icon={<Layers size={20} />}
      action={<button className="btn-primary btn-sm" onClick={() => generate(req)} disabled={busy === "gen"}><RotateCcw size={14} />Regenerate</button>}>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px]">
          <thead><tr><th className="table-th">Floor</th>{LEVEL_KEYS.map(([, l]) => <th key={l} className="table-th text-center">{l}</th>)}</tr></thead>
          <tbody>
            {req.levels.map((lv: any, i: number) => (
              <tr key={i}>
                <td className="table-td font-semibold">{lv.name}{lv.stilt && <span className="ml-1 text-xs text-slate-500">(stilt)</span>}</td>
                {LEVEL_KEYS.map(([k, , kind]) => (
                  <td key={k} className="table-td text-center">
                    {lv.stilt && k !== "parking_car" && k !== "parking_bike" ? "—" : kind === "n"
                      ? <input type="number" min={0} max={8} className="input w-14 px-1 py-1 text-center" value={lv[k] ?? 0}
                          onChange={(e) => { const r = clone(req); r.levels[i][k] = Number(e.target.value); setReq(r); }} />
                      : <input type="checkbox" className="h-4 w-4 accent-brand-600" checked={!!lv[k]}
                          onChange={(e) => { const r = clone(req); r.levels[i][k] = e.target.checked; setReq(r); }} />}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-slate-500">Every change is yours to make – nothing is removed silently; if rooms don't fit, you'll see options.</p>
    </Card>
  );

  return (
    <Page title={t("Design Studio")} subtitle="AI floor plans, 2D editing, 3D preview and revisions" actions={header}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="min-w-0 max-w-full"><PillTabs tabs={tabs} value={tab} onChange={setTab} /></div>
        {saved && <Badge color={dirty ? "amber" : "green"}>{dirty ? `v${saved.version} + unsaved changes` : `Saved v${saved.version} – ${saved.title}`}</Badge>}
        {!saved && plan && <Badge color="amber">Not saved yet</Badge>}
      </div>
      <div className="flex gap-2 sm:hidden">
        <button className="btn-outline btn-sm" onClick={save} disabled={!plan || (!dirty && !!saved)}><Save size={14} />Save</button>
        <button className="btn-primary btn-sm" onClick={toEstimate} disabled={!plan}><Calculator size={14} />Estimate</button>
      </div>

      {tab === "ai" && (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_1.15fr]">
          <div className="min-w-0 space-y-4">
            <Card title="Describe the house" icon={<Sparkles size={20} />}>
              <textarea className="input min-h-[92px]" placeholder={'e.g. "30x40 east facing 2BHK, car parking, G+1, 30 ft road" – English / Tanglish'}
                value={text} onChange={(e) => setText(e.target.value)} />
              <div className="mt-2 flex flex-wrap gap-2">
                {EXAMPLES.map((x) => <button key={x} className="rounded-full bg-brand-50 px-3 py-1 text-xs text-brand-700 hover:bg-brand-100" onClick={() => setText(x)}>{x}</button>)}
              </div>
              <div className="mt-3 flex flex-wrap items-center gap-2">
                <button className="btn-primary" onClick={understand} disabled={busy !== ""}><Wand2 size={16} />{busy === "parse" || busy === "gen" ? "Working..." : "Generate Plan"}</button>
                <span className="text-xs text-slate-500">Never guesses: plot size, facing, road width, floors and bedrooms are confirmed with you.</span>
              </div>
              {understood.length > 0 && <div className="mt-3 flex flex-wrap gap-1.5">{understood.map((u) => <Badge key={u} color="blue">{u}</Badge>)}</div>}
            </Card>

            {(questions.length > 0 || suggestions.length > 0) && (
              <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
                <div className="mb-1 flex items-center gap-2 font-bold"><TriangleAlert size={16} />Please confirm</div>
                <ul className="list-disc space-y-0.5 pl-5">{questions.map((q) => <li key={q}>{q}</li>)}</ul>
                {suggestions.length > 0 && (
                  <div className="mt-3">
                    <div className="mb-1 font-semibold">These options fit the plot – choose one:</div>
                    <div className="flex flex-wrap gap-2">
                      {suggestions.map((s) => <button key={s.label} className="btn-outline btn-sm" onClick={() => { setReq(s.requirements); generate(s.requirements); }}>{s.label}</button>)}
                    </div>
                  </div>
                )}
              </div>
            )}

            <Card title="Confirm details" icon={<Compass size={20} />} action={<button className="btn-outline btn-sm" onClick={buildFromForm} disabled={busy !== ""}><Wand2 size={14} />Generate from form</button>}>
              <div className="grid gap-3 sm:grid-cols-3">
                <Field label="Plot frontage (ft) *"><input className={`input ${!form.plot_w_ft ? "border-amber-400" : ""}`} type="number" value={form.plot_w_ft} onChange={(e) => setF("plot_w_ft", e.target.value)} /></Field>
                <Field label="Plot depth (ft) *"><input className={`input ${!form.plot_d_ft ? "border-amber-400" : ""}`} type="number" value={form.plot_d_ft} onChange={(e) => setF("plot_d_ft", e.target.value)} /></Field>
                <Field label="Facing (road side) *">
                  <select className={`input ${!form.facing ? "border-amber-400" : ""}`} value={form.facing} onChange={(e) => setF("facing", e.target.value)}>
                    <option value="">— confirm —</option>{FACINGS.map((f) => <option key={f} value={f}>{f.replace("-", " ").replace(/\b\w/g, (c) => c.toUpperCase())}</option>)}
                  </select>
                </Field>
                <Field label="Road width (ft) *"><input className={`input ${!form.road_width_m ? "border-amber-400" : ""}`} type="number" value={roadFt}
                  onChange={(e) => setF("road_width_m", e.target.value ? Math.round(Number(e.target.value) * 0.3048 * 100) / 100 : "")} /></Field>
                <Field label="Floors *">
                  <select className={`input ${!form.floors ? "border-amber-400" : ""}`} value={form.floors} onChange={(e) => setF("floors", e.target.value)}>
                    <option value="">— confirm —</option>
                    {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{form.stilt ? (n === 1 ? "Stilt only" : `Stilt + ${n - 1}`) : n === 1 ? "G only" : `G + ${n - 1}`}</option>)}
                  </select>
                </Field>
                <Field label="Bedrooms (whole house) *"><input className={`input ${form.bedrooms === "" ? "border-amber-400" : ""}`} type="number" min={0} value={form.bedrooms} onChange={(e) => setF("bedrooms", e.target.value)} /></Field>
                <Field label="Toilets (blank = 1 per bedroom)"><input className="input" type="number" min={0} value={form.toilets ?? ""} onChange={(e) => setF("toilets", e.target.value)} /></Field>
                <Field label="Area type">
                  <select className="input" value={form.area_type} onChange={(e) => setF("area_type", e.target.value)}>
                    <option value="other">Other areas</option><option value="cba">Continuous Building Area</option><option value="ews">EWS area</option>
                  </select>
                </Field>
                <Field label="Floor height (ft)"><input className="input" type="number" value={form.floor_height_ft} onChange={(e) => setF("floor_height_ft", Number(e.target.value) || 10)} /></Field>
              </div>
              <div className="mt-3 grid gap-2 sm:grid-cols-3">
                {([["stilt", "Stilt parking"], ["parking_car", "Car parking"], ["parking_bike", "Two-wheeler"], ["pooja", "Pooja room"], ["dining", "Separate dining"],
                  ["attached", "Attached toilets"], ["corner", "Corner plot"], ["same_each_floor", "Same rooms each floor"]] as [string, string][]).map(([k, l]) => (
                  <label key={k} className="flex items-center justify-between gap-3 rounded-lg border border-line px-3 py-2 text-sm"><span>{l}</span><Toggle checked={!!form[k]} onChange={(v) => setF(k, v)} /></label>
                ))}
              </div>
            </Card>
            {reqTable}
          </div>

          <div className="min-w-0 space-y-4">
            {plan ? <>{planCard}{quickCard}{setbackCard}{notesCard}</> : (
              <Card title="Plan" icon={<Ruler size={20} />}>
                <img src="/images/proj_residential.jpg" alt="" className="mb-4 aspect-[16/8] w-full rounded-lg object-cover" />
                <Empty icon={<Wand2 className="text-slate-400" />} text="Describe the house or fill the form – the plan appears here with Tamil Nadu setbacks applied." />
              </Card>
            )}
          </div>
        </div>
      )}

      {tab === "editor" && (!plan ? <Card><Empty text="Generate or open a plan first (AI Floor Plan / Revisions)." /></Card> : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_340px]">
          <Card title="2D Editor" icon={<PenSquare size={20} />} action={levelTabs}>
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <button className="btn-outline btn-sm" onClick={undo} disabled={!past.length}><Undo2 size={14} />Undo</button>
              <button className="btn-outline btn-sm" onClick={redo} disabled={!future.length}><Redo2 size={14} />Redo</button>
              <select className="input w-auto py-1.5 text-xs" value={newType} onChange={(e) => setNewType(e.target.value)}>{ROOM_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
              <button className="btn-outline btn-sm" onClick={addRoom}><Plus size={14} />Add room</button>
              <button className="btn-outline btn-sm" onClick={dupRoom} disabled={!sel}><Copy size={14} />Duplicate</button>
              <button className="btn-ghost btn-sm text-red-600" onClick={delRoom} disabled={!sel}><Trash2 size={14} />Delete</button>
              <label className="ml-auto flex items-center gap-2 text-xs text-slate-600">Snap
                <select className="input w-auto py-1 text-xs" value={grid} onChange={(e) => setGrid(Number(e.target.value))}>{[0.25, 0.5, 1].map((g) => <option key={g} value={g}>{g === 0.25 ? '3"' : g === 0.5 ? '6"' : "1'"}</option>)}</select>
              </label>
              {aiPlan && <button className="btn-ghost btn-sm" onClick={() => { if (window.confirm("Go back to the AI plan? Your edits stay in Undo.")) { setPast((p) => [...p, JSON.stringify(plan)]); setPlan(clone(aiPlan)); setStale(false); setDirty(true); runQuick(aiPlan); } }}><RotateCcw size={14} />AI plan</button>}
            </div>
            <div className="aspect-[4/5] max-h-[720px] w-full rounded-lg border border-line bg-white p-1 sm:aspect-square">
              <PlanSvg plan={plan} level={level} editable selected={selected} onSelect={setSelected} onChange={setRooms} grid={grid} stale={stale} />
            </div>
            <p className="mt-2 text-xs text-slate-500">Drag a room to move it (its toilet & dress move with it); drag the blue handles to resize. Walls, doors, windows and the estimate update automatically. Ctrl+Z / Ctrl+Y, Delete key.</p>
          </Card>
          <div className="min-w-0 space-y-4">
            <Card title={sel ? `Room – ${sel.name}` : "Room properties"} icon={<Ruler size={20} />}>
              {!sel ? <p className="text-sm text-slate-500">Click a room to edit its name, type and exact size.</p> : (
                <div key={sel.id + JSON.stringify(sel)} className="grid grid-cols-2 gap-3">
                  <Field label="Name" className="col-span-2"><input className="input" defaultValue={sel.name} onBlur={(e) => e.target.value !== sel.name && updateSel({ name: e.target.value })} /></Field>
                  <Field label="Type" className="col-span-2"><select className="input" value={sel.type} onChange={(e) => updateSel({ type: e.target.value })}>{ROOM_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></Field>
                  {(["w", "d", "x", "y"] as const).map((k) => (
                    <Field key={k} label={{ w: "Width (ft)", d: "Depth (ft)", x: "From left (ft)", y: "From front (ft)" }[k]}>
                      <input className="input" type="number" step={grid} defaultValue={sel[k]} onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
                        onBlur={(e) => { const v = Number(e.target.value); if (!Number.isNaN(v) && v !== sel[k]) updateSel({ [k]: Math.round(v / 0.25) * 0.25 } as any); }} />
                    </Field>
                  ))}
                  <div className="col-span-2 text-xs text-slate-500">Area {num(sel.w * sel.d, 1)} sq ft · building {plan.building.w}' × {plan.building.d}'</div>
                </div>
              )}
            </Card>
            {plan.levels.length > 1 && (
              <Card title="Copy layout" icon={<Copy size={20} />}>
                <p className="mb-2 text-sm text-slate-600">Copy all rooms from another floor into {lvl?.name}:</p>
                <div className="flex flex-wrap gap-2">{plan.levels.map((l, i) => i !== level && <button key={i} className="btn-outline btn-sm" onClick={() => copyLevelFrom(i)}>{l.name}</button>)}</div>
              </Card>
            )}
            {quickCard}
            {lvl && lvl.warnings.length > 0 && (
              <Card title="Checks" icon={<TriangleAlert size={20} />}>
                <ul className="space-y-1 text-sm text-amber-800">{lvl.warnings.map((w, i) => <li key={i}>• {w}</li>)}</ul>
              </Card>
            )}
          </div>
        </div>
      ))}

      {tab === "3d" && (!plan ? <Card><Empty text="Generate or open a plan first." /></Card> : (
        <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1fr_320px]">
          <Card title="3D Preview" icon={<Box size={20} />} action={<button className="btn-outline btn-sm" onClick={() => setRoof(!roof)}>{roof ? <EyeOff size={14} /> : <Eye size={14} />}{roof ? "Hide roof" : "Show roof"}</button>}>
            <Plan3D plan={plan} showRoof={roof} />
          </Card>
          <div className="min-w-0 space-y-4">
            <Card title="Building" icon={<Layers size={20} />}>
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-sm">
                <dt className="text-slate-500">Floors</dt><dd>{plan.levels.map((l) => l.name).join(", ")}</dd>
                <dt className="text-slate-500">Built-up</dt><dd>{inr(plan.summary.builtup_sqft)} sq ft</dd>
                <dt className="text-slate-500">Carpet</dt><dd>{inr(plan.summary.carpet_sqft)} sq ft</dd>
                <dt className="text-slate-500">Bedrooms / toilets</dt><dd>{plan.summary.bedrooms} / {plan.summary.toilets}</dd>
                <dt className="text-slate-500">Height</dt><dd>≈ {plan.setbacks.height_m} m (max {plan.setbacks.max_height_m} m)</dd>
                <dt className="text-slate-500">Facing</dt><dd className="capitalize">{plan.facing.replace("-", " ")}</dd>
              </dl>
            </Card>
            {quickCard}
          </div>
        </div>
      ))}

      {tab === "upload" && pid && (
        <DrawingImport projectId={pid} designs={designs} onSaved={async (d) => { await loadDesigns(); await openDesign(d.id); setTab("editor"); }} />
      )}

      {tab === "rev" && (
        <div className="space-y-4">
          <Card title="Design versions" icon={<Layers size={20} />}>
            {designs.length === 0 ? <Empty text="No saved designs yet – generate a plan and press “Save version”." /> : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[860px]">
                  <thead><tr>{["Version", "Title", "Source", "Built-up", "Bed / Toilet", "Estimate", "Saved", ""].map((h) => <th key={h} className="table-th">{h}</th>)}</tr></thead>
                  <tbody>
                    {designs.map((d) => (
                      <tr key={d.id} className={saved?.id === d.id ? "bg-brand-50/50" : ""}>
                        <td className="table-td font-bold">v{d.version}</td>
                        <td className="table-td">{d.title}</td>
                        <td className="table-td"><Badge color={d.source === "ai" ? "blue" : d.source === "upload" ? "green" : "purple"}>{d.source === "ai" ? "AI" : d.source === "upload" ? "Drawing" : "Edited"}</Badge></td>
                        <td className="table-td">{inr(d.builtup_sqft)} sft</td>
                        <td className="table-td">{d.summary?.bedrooms} / {d.summary?.toilets}</td>
                        <td className="table-td font-semibold">{rupees(d.estimate_total)} <span className="text-xs font-normal text-slate-500">({d.spec_level})</span></td>
                        <td className="table-td text-xs">{fmtDateTime(d.created_at)}</td>
                        <td className="table-td whitespace-nowrap">
                          <button className="btn-ghost btn-sm" onClick={() => { openDesign(d.id); setTab("ai"); }}>Open</button>
                          <button className="btn-ghost btn-sm" title="Plan PDF" onClick={() => exportAs(d.id, d.version, "pdf")}><FileText size={14} />PDF</button>
                          <button className="btn-ghost btn-sm" title="AutoCAD DXF" onClick={() => exportAs(d.id, d.version, "dxf")}><Download size={14} />DXF</button>
                          <OwnerDelete entity="design" id={d.id} title={`${d.title} (v${d.version})`} onDone={loadDesigns} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
          <Card title="Compare revisions" icon={<GitCompare size={20} />}
            action={<div className="flex flex-wrap items-center gap-2">
              <select className="input w-auto py-1.5 text-sm" value={cmpA} onChange={(e) => setCmpA(Number(e.target.value))}><option value="">From…</option>{designs.map((d) => <option key={d.id} value={d.id}>v{d.version} – {d.title}</option>)}</select>
              <span className="text-slate-400">→</span>
              <select className="input w-auto py-1.5 text-sm" value={cmpB} onChange={(e) => setCmpB(Number(e.target.value))}><option value="">To…</option>{designs.map((d) => <option key={d.id} value={d.id}>v{d.version} – {d.title}</option>)}</select>
              <button className="btn-primary btn-sm" onClick={runCompare} disabled={designs.length < 2}><GitCompare size={14} />Compare</button>
            </div>}>
            {!cmp ? <p className="text-sm text-slate-500">{designs.length < 2 ? "Save at least two versions to compare them." : "Choose two versions and press Compare."}</p> : (
              <div className="min-w-0 space-y-4">
                <div className="grid gap-2 sm:grid-cols-4">
                  {([["builtup_sqft", "Built-up (sft)"], ["bedrooms", "Bedrooms"], ["toilets", "Toilets"], ["ext_wall_ft", "External wall (ft)"], ["int_wall_ft", "Internal wall (ft)"], ["carpet_sqft", "Carpet (sft)"], ["estimate", "Estimate (₹)"]] as [string, string][]).map(([k, l]) => {
                    const v = cmp.totals[k];
                    return (
                      <div key={k} className="rounded-lg bg-slate-50 px-3 py-2">
                        <div className="text-xs text-slate-500">{l}</div>
                        <div className="text-sm text-slate-600">{k === "estimate" ? `${lakhs(v.a)} → ${lakhs(v.b)}` : `${num(v.a, 1)} → ${num(v.b, 1)}`}</div>
                        <div className={`text-base font-extrabold ${v.change > 0 ? "text-red-600" : v.change < 0 ? "text-emerald-600" : "text-navy-ink"}`}>{v.change > 0 ? "+" : ""}{k === "estimate" ? rupees(v.change) : num(v.change, 1)}</div>
                      </div>
                    );
                  })}
                </div>
                {cmp.levels.map((l: any) => (
                  <div key={l.name}>
                    <div className="mb-1 text-sm font-bold text-navy-ink">{l.name}</div>
                    {l.added.length + l.removed.length + l.changed.length === 0 ? <p className="text-sm text-slate-500">No change</p> : (
                      <ul className="space-y-0.5 text-sm">
                        {l.added.map((r: any, i: number) => <li key={"a" + i} className="text-emerald-700">+ {r.name} ({r.size})</li>)}
                        {l.removed.map((r: any, i: number) => <li key={"r" + i} className="text-red-600">− {r.name} ({r.size})</li>)}
                        {l.changed.map((r: any, i: number) => <li key={"c" + i} className="text-slate-700">~ {r.name}: {r.from} → {r.to}{r.area_change ? ` (${r.area_change > 0 ? "+" : ""}${r.area_change} sft)` : ""}</li>)}
                      </ul>
                    )}
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}
    </Page>
  );
}
