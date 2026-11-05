import { useCallback, useEffect, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Bath, BedDouble, BedSingle, Box, Car, ChevronRight, CircleCheck, CircleHelp, CircleX, Compass, CookingPot, DoorOpen, Download,
  FileUp, Flower2, Languages, Layers, LayoutGrid, PenSquare, Printer, RotateCcw, Save, Settings2, Sofa, Sparkles, Sun, TriangleAlert, Utensils,
} from "lucide-react";
import Page from "../components/Page";
import OwnerDelete from "../components/OwnerDelete";
import DrawingImport from "../components/design/DrawingImport";
import NorthDial from "../components/design/NorthDial";
import Plan3D from "../components/design/Plan3D";
import PlanSvg from "../components/design/PlanSvg";
import { Badge, Card, Empty, Modal, toast } from "../components/ui";
import { api, downloadFile, downloadPost, fmtDateTime, getToken, API_BASE, inr } from "../lib/api";
import { savePng, saveSvg } from "../lib/designExport";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";
import type { Plan } from "../lib/plan";

type Status = "matched" | "partly" | "not_matched";
type Check = { rule: string; title: string; room: string; room_id: string | null; level: number; level_name: string; zone: string;
  status: Status; message: string; why: string; current?: string; better?: string; remedy?: string };
type Floor = { level: number; name: string; score: number; matched: number; partly: number; not_matched: number; total: number };
type Door = { side: string; side_name: string; code: string; name: string; status: Status; advice: string; move_ft: number; target: string; pada_ft: number; side_ft: number; padas: Record<string, string[]> };
type Question = { key: string; question: string; kind: string; options: string[] };
type Result = { checks: Check[]; overview: Record<string, { status: string; rooms: string[] }>;
  overview8?: Record<string, { status: string; items: string[] }>; floors?: Floor[]; score?: number; door?: Door | null;
  mandala?: { after: string; dx: number; dy: number }[]; questions?: Question[];
  summary: { matched: number; partly: number; not_matched: number; total: number; label: string };
  suggestions: string[]; tips: string[]; north_deg: number; facing: string; note: string };
type DesignRow = { id: number; version: number; title: string; source: string; builtup_sqft: number; created_at: string };
type Option = { label: string; changes: string[]; plan: Plan; score: number; summary: Result["summary"]; floors: Floor[]; remaining: string[] };

const ICON: Record<string, any> = { entrance: DoorOpen, door_pada: DoorOpen, hall: Sofa, kitchen: CookingPot, master: BedDouble, bedroom: BedSingle,
  toilet: Bath, pooja: Flower2, stair: Layers, dining: Utensils, parking: Car, brahmasthan: LayoutGrid, ne_light: Sun, sw_heavy: LayoutGrid, shape: LayoutGrid };
const TONE: Record<string, string> = { Excellent: "bg-emerald-50 text-emerald-700 ring-emerald-200", Good: "bg-brand-50 text-brand-700 ring-brand-100", "Needs Attention": "bg-amber-50 text-amber-700 ring-amber-200" };
const Z8 = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
const ZN: Record<string, [string, string]> = { N: ["North", "வடக்கு"], NE: ["North-East", "வடகிழக்கு"], E: ["East", "கிழக்கு"], SE: ["South-East", "தென்கிழக்கு"],
  S: ["South", "தெற்கு"], SW: ["South-West", "தென்மேற்கு"], W: ["West", "மேற்கு"], NW: ["North-West", "வடமேற்கு"], C: ["Centre", "மையம்"] };
const L = (ta: boolean, en: string, t: string) => (ta ? t : en);

function StatusIcon({ s }: { s: Status }) {
  if (s === "matched") return <CircleCheck size={18} className="shrink-0 text-emerald-600" />;
  if (s === "partly") return <TriangleAlert size={18} className="shrink-0 text-amber-500" />;
  return <CircleX size={18} className="shrink-0 text-red-500" />;
}

function Ring({ score, sub }: { score: number; sub: string }) {
  const R = 46, C = 2 * Math.PI * R, f = score / 100;
  return (
    <svg width="120" height="120" viewBox="0 0 120 120" className="shrink-0">
      <circle cx="60" cy="60" r={R} fill="none" stroke="#e2e8f0" strokeWidth="11" />
      <circle cx="60" cy="60" r={R} fill="none" stroke={f >= 0.75 ? "#16a34a" : f >= 0.5 ? "#2563eb" : "#f59e0b"} strokeWidth="11"
        strokeDasharray={`${f * C} ${C}`} strokeLinecap="round" transform="rotate(-90 60 60)" />
      <text x="60" y="60" textAnchor="middle" fontSize="28" fontWeight="800" className="fill-navy-ink">{score}</text>
      <text x="60" y="78" textAnchor="middle" fontSize="10" className="fill-slate-500">{sub}</text>
    </svg>
  );
}

/** 8 directions around a compass – like the mockup (Excellent / Good / Needs attention) */
function Directions8({ ov, ta, north }: { ov: NonNullable<Result["overview8"]>; ta: boolean; north: number }) {
  const cell = (z: string) => {
    const o = ov[z] || { status: "Good", items: [] };
    return (
      <div key={z} className={`rounded-xl p-2 ring-1 ${TONE[o.status] || ""}`} title={o.items.join("\n")}>
        <div className="text-xs font-bold">{L(ta, ZN[z][0], ZN[z][1])}</div>
        <div className="text-[11px] font-semibold">{ta ? ({ Excellent: "மிகச் சிறப்பு", Good: "நல்லது", "Needs Attention": "கவனம் தேவை" } as any)[o.status] : o.status}</div>
        <div className="mt-0.5 line-clamp-2 text-[10px] opacity-80">{o.items.slice(0, 2).join(", ")}</div>
      </div>
    );
  };
  return (
    <div className="grid grid-cols-3 gap-2">
      {cell("NW")}{cell("N")}{cell("NE")}
      {cell("W")}
      <div className="flex items-center justify-center rounded-xl bg-slate-50">
        <svg viewBox="-40 -40 80 80" className="h-20 w-20"><circle r="34" fill="#f0fdf4" stroke="#bbf7d0" />
          <text y="-22" textAnchor="middle" fontSize="11" fontWeight="800" fill="#dc2626">N</text><text x="26" y="4" textAnchor="middle" fontSize="10" fontWeight="800">E</text>
          <text y="31" textAnchor="middle" fontSize="10" fontWeight="800">S</text><text x="-26" y="4" textAnchor="middle" fontSize="10" fontWeight="800">W</text>
          <text y="4" textAnchor="middle" fontSize="7" fill="#64748b">{Math.round(north)}°</text></svg>
      </div>
      {cell("E")}
      {cell("SW")}{cell("S")}{cell("SE")}
    </div>
  );
}

export default function VastuPage() {
  const { t, lang, setLang } = useI18n();
  const ta = lang === "ta";
  const nav = useNavigate();
  const [params] = useSearchParams();
  const { currentProject, user } = useAuth();
  const isOwner = user?.role === "owner";
  const pid = currentProject?.id;
  const allowed = !!currentProject?.permissions?.vastu;
  const [designs, setDesigns] = useState<DesignRow[]>([]);
  const [designId, setDesignId] = useState<number | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [res, setRes] = useState<Result | null>(null);
  const [north, setNorth] = useState<number | null>(null);
  const [level, setLevel] = useState(0);
  const [view, setView] = useState<"2d" | "3d">("2d");
  const [zones16, setZones16] = useState(true);
  const [open, setOpen] = useState<string | null>(null);
  const [upload, setUpload] = useState(false);
  const [opts, setOpts] = useState<{ current: { score: number; floors: Floor[] }; options: Option[]; message?: string } | null>(null);
  const [step, setStep] = useState(1);
  const [busy, setBusy] = useState("");
  const [northEdit, setNorthEdit] = useState(false);
  const [reports, setReports] = useState<any[]>([]);
  const [siteOpen, setSiteOpen] = useState(false);
  const [rulesOpen, setRulesOpen] = useState(false);

  const loadDesigns = useCallback(async () => {
    if (!pid) return [];
    const d = await api<DesignRow[]>(`/api/projects/${pid}/designs`);
    setDesigns(d);
    return d;
  }, [pid]);

  const analyse = async (id: number | null, nd: number | null = null, lg = lang) => {
    if (!pid || !id) return;
    setBusy("an");
    try {
      const r = await api<{ plan: Plan; result: Result }>(`/api/projects/${pid}/vastu/analyse`, { body: { design_id: id, north_deg: nd, lang: lg } });
      setPlan(r.plan); setRes(r.result); setNorth(r.result.north_deg); setStep((s) => Math.max(s, 2));
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(""); }
  };

  useEffect(() => {
    if (!pid || !allowed) return;
    setPlan(null); setRes(null); setStep(1); setLevel(0);
    const want = Number(params.get("design")) || 0;
    loadDesigns().then((d) => {
      const pick = d.find((x) => x.id === want) || d[0];
      if (pick) { setDesignId(pick.id); analyse(pick.id); }
    }).catch((e) => toast(e.message, "err"));
    api<any[]>(`/api/projects/${pid}/vastu/reports`).then(setReports).catch(() => {});
  }, [pid, allowed]);
  useEffect(() => { if (designId) analyse(designId, north, lang); }, [lang]);  // eslint-disable-line react-hooks/exhaustive-deps

  const fname = (x: string) => `${currentProject?.code}_${(currentProject?.name || "").replace(/[^A-Za-z0-9]+/g, "_")}_${x}`;
  const downloadPdf = () => pid && designId && downloadPost(`/api/projects/${pid}/vastu/report-pdf`, { design_id: designId, north_deg: north }, `${fname("Vastu_Report")}.pdf`)
    .catch((e) => toast(e.message, "err"));
  const printReport = async (lg: string) => {
    if (!pid || !designId) return;
    const w = window.open("", "_blank");
    if (!w) return toast("Allow pop-ups to open the report", "err");
    w.document.write("<p style='font-family:sans-serif'>Preparing the report…</p>");
    try {
      const token = getToken();
      const r = await fetch(`${API_BASE}/api/projects/${pid}/vastu/report-html`, { method: "POST", headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ design_id: designId, north_deg: north, lang: lg }) });
      if (!r.ok) throw new Error("Report failed");
      const html = await r.text();
      w.document.open(); w.document.write(html); w.document.close();
    } catch (e: any) { w.close(); toast(e.message, "err"); }
  };
  const saveReport = async () => {
    if (!pid || !designId) return;
    try {
      const r = await api<any>(`/api/projects/${pid}/vastu/reports`, { body: { design_id: designId, north_deg: north } });
      setReports([r, ...reports]); toast("Vastu report saved");
    } catch (e: any) { toast(e.message, "err"); }
  };
  const getOptions = async () => {
    if (!pid || !designId) return;
    setBusy("imp");
    try {
      const r = await api<any>(`/api/projects/${pid}/vastu/options`, { body: { design_id: designId, north_deg: north } });
      setOpts(r); setStep(4);
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(""); }
  };
  const saveOption = async (o: Option) => {
    if (!pid) return;
    const d = designs.find((x) => x.id === designId);
    try {
      const s = await api<any>(`/api/projects/${pid}/designs`, { body: { plan: o.plan, title: `${d?.title || "Design"} (Vastu ${o.score})`, source: "edited",
        prompt: `Vastu option: ${o.label}`, state: currentProject?.state || "Tamil Nadu", parent_id: designId } });
      toast(`Saved as design v${s.version}`); setOpts(null);
      await loadDesigns(); setDesignId(s.id); analyse(s.id);
    } catch (e: any) { toast(e.message, "err"); }
  };

  if (!currentProject) return <Page title={t("Vastu Intelligence")} subtitle="Analyze your plan and get Vastu recommendations"><Empty text="Create a project first (Projects page)." /></Page>;
  if (!allowed) return <Page title={t("Vastu Intelligence")} subtitle="Analyze your plan and get Vastu recommendations"><Empty text="You don't have Vastu access for this project. Ask the owner." /></Page>;

  const steps = ta ? ["வரைபடம்", "பகுப்பாய்வு", "பரிந்துரைகள்", "மேம்பட்ட திட்டங்கள்"] : ["Upload Drawing", "Analyze & Evaluate", "Get Recommendations", "Improved Plan Options"];
  const highlight: Record<string, string> = {};
  res?.checks.forEach((c) => { if (c.room_id && c.level === level && c.rule !== "door_pada" && c.rule !== "entrance") highlight[c.room_id] = c.status === "matched" ? "#16a34a" : c.status === "partly" ? "#f59e0b" : "#ef4444"; });
  const roomChecks = (res?.checks || []).filter((c) => c.rule !== "shape" && c.level !== -1 && (c.level === level || c.rule === "entrance" || c.rule === "door_pada"));
  const siteChecks = (res?.checks || []).filter((c) => c.level === -1);
  const score = res?.score ?? (res ? Math.round(100 * res.summary.matched / Math.max(1, res.summary.total)) : 0);

  return (
    <Page title={t("Vastu Intelligence")} subtitle="Analyze your plan and get Vastu recommendations"
      actions={<button className="btn-outline" onClick={() => setLang(ta ? "en" : "ta")}><Languages size={16} />{ta ? "English" : "தமிழ்"}</button>}>
      <div className="flex flex-wrap items-center justify-center gap-2">
        {steps.map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            <button onClick={() => { if (i === 0) setUpload(true); else if (i === 2) document.getElementById("vastu-rooms")?.scrollIntoView({ behavior: "smooth" }); else if (i === 3) getOptions(); }}
              className={`flex items-center gap-2 rounded-full px-4 py-2 text-sm font-semibold ${i + 1 === step ? "bg-white text-brand-700 shadow-card ring-1 ring-brand-100" : i + 1 < step ? "bg-white/70 text-navy-ink" : "bg-slate-100 text-slate-500"}`}>
              <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs text-white ${i + 1 <= step ? "bg-brand-600" : "bg-slate-400"}`}>{i + 1}</span>{s}
            </button>
            {i < steps.length - 1 && <ChevronRight size={18} className="text-brand-600" />}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-[1.15fr_1fr]">
        <div className="min-w-0 space-y-4">
          <div className="card flex flex-col items-center gap-2 border-2 border-dashed border-brand-100 p-5 text-center">
            <FileUp size={30} className="text-brand-600" />
            <div className="text-base font-semibold text-navy-ink">Upload Your Drawing (PDF, DXF, PNG, JPG)</div>
            <div className="text-xs text-slate-500">DWG: save as DXF 2018 first · or check a plan from Design Studio</div>
            <div className="mt-1 flex flex-wrap items-center justify-center gap-2">
              <button className="btn-primary" onClick={() => setUpload(true)}>Choose File</button>
              {designs.length > 0 && (
                <select className="input w-auto py-2 text-sm" value={designId ?? ""} onChange={(e) => { const id = Number(e.target.value); setDesignId(id); setLevel(0); analyse(id); }}>
                  {designs.map((d) => <option key={d.id} value={d.id}>v{d.version} – {d.title}{d.source === "upload" ? " (from drawing)" : ""}</option>)}
                </select>
              )}
            </div>
          </div>

          <Card title={L(ta, "Analyzed Plan", "பகுப்பாய்வு செய்த வரைபடம்")} icon={<Compass size={20} />}
            action={<div className="flex flex-wrap gap-2">
              <button className={view === "2d" ? "btn-primary btn-sm" : "btn-outline btn-sm"} onClick={() => setView("2d")}>2D</button>
              <button className={view === "3d" ? "btn-primary btn-sm" : "btn-outline btn-sm"} onClick={() => setView("3d")}><Box size={14} />3D</button>
              <button className="btn-outline btn-sm" onClick={() => nav(`/design?tab=editor&design=${designId}&vastu=1`)} disabled={!designId}><PenSquare size={14} />{L(ta, "Edit Plan", "திருத்து")}</button>
            </div>}>
            {!plan || !res ? <Empty icon={<Compass className="text-slate-400" />} text={busy ? "Analysing…" : "Upload a drawing or make a plan in Design Studio – then the Vastu check runs here."} /> : (
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.35fr_1fr]">
                <div className="min-w-0">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    {plan.levels.map((l, i) => {
                      const f = res.floors?.find((x) => x.level === i);
                      return <button key={i} onClick={() => setLevel(i)} className={`rounded-lg px-3 py-1 text-xs font-medium ${i === level ? "bg-navy-900 text-white" : "bg-slate-100"}`}>{l.name}{f && <b className="ml-1">{f.score}</b>}</button>;
                    })}
                    <label className="ml-auto flex items-center gap-1 text-xs text-slate-600"><input type="checkbox" className="accent-orange-500" checked={zones16} onChange={(e) => setZones16(e.target.checked)} />{L(ta, "16 zones", "16 பகுதிகள்")}</label>
                  </div>
                  {view === "2d" ? <>
                    <div id="vastu-plan" className="aspect-[4/5] w-full rounded-lg border border-line bg-white p-1">
                      <PlanSvg plan={plan} level={level} vastuGrid highlight={highlight} mandala={zones16 ? res.mandala : null} doorCode={res.door?.code} /></div>
                    <div className="mt-2 flex flex-wrap gap-1.5 text-xs">
                      <button className="btn-outline btn-sm" onClick={() => { const sv = document.querySelector("#vastu-plan svg") as SVGSVGElement | null; if (sv) savePng(sv, `${fname("Vastu_Plan")}_${plan.levels[level]?.name.replace(/\s+/g, "_")}.png`, 2400).catch((e) => toast(e.message, "err")); }}><Download size={13} />PNG</button>
                      <button className="btn-outline btn-sm" onClick={() => { const sv = document.querySelector("#vastu-plan svg"); if (sv) saveSvg(new XMLSerializer().serializeToString(sv), `${fname("Vastu_Plan")}.svg`); }}><Download size={13} />SVG</button>
                    </div></>
                    : <Plan3D plan={plan} />}
                  <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-600">
                    <span className="flex items-center gap-1"><span className="h-3 w-3 rounded-sm border-2 border-emerald-600" />{L(ta, "matched", "பொருந்துகிறது")}</span>
                    <span className="flex items-center gap-1"><span className="h-3 w-3 rounded-sm border-2 border-amber-500" />{L(ta, "partly", "பகுதியாக")}</span>
                    <span className="flex items-center gap-1"><span className="h-3 w-3 rounded-sm border-2 border-red-500" />{L(ta, "needs attention", "கவனம் தேவை")}</span>
                    <span className="flex items-center gap-1"><span className="h-3 w-3 rounded-sm border-2 border-dashed border-orange-500" />{L(ta, "16 zones + Brahmasthan", "16 பகுதிகள் + பிரம்மஸ்தானம்")}</span>
                  </div>
                </div>
                <div className="space-y-4">
                  <div className="rounded-xl border border-line p-4">
                    <div className="mb-2 flex items-center gap-2 text-sm font-bold text-navy-ink"><Sparkles size={16} />{L(ta, "Vastu Score", "வாஸ்து மதிப்பெண்")}</div>
                    <div className="flex items-center gap-3">
                      <Ring score={score} sub={L(ta, "out of 100", "100-க்கு")} />
                      <div className="text-sm">
                        <div className="font-bold text-navy-ink">{res.summary.label}</div>
                        <div className="text-slate-500">{res.summary.matched}/{res.summary.total} · {res.summary.partly} {L(ta, "partly", "பகுதி")} · {res.summary.not_matched} {L(ta, "need attention", "கவனம்")}</div>
                      </div>
                    </div>
                    {res.floors && <div className="mt-3 space-y-1.5">{res.floors.map((f) => (
                      <div key={f.level} className="flex items-center gap-2 text-xs">
                        <span className="w-32 truncate text-slate-600">{f.name}</span>
                        <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100"><div className={`h-2 ${f.score >= 75 ? "bg-emerald-500" : f.score >= 50 ? "bg-brand-500" : "bg-amber-500"}`} style={{ width: `${f.score}%` }} /></div>
                        <b className="w-8 text-right">{f.score}</b>
                      </div>))}</div>}
                  </div>
                  <div className="rounded-xl bg-slate-50 p-4">
                    <div className="mb-2 flex items-center gap-2 text-sm font-bold text-navy-ink"><LayoutGrid size={16} />{L(ta, "Plan Details", "வரைபட விவரம்")}</div>
                    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm">
                      <dt className="text-slate-500">Plot</dt><dd>{plan.plot.w}' × {plan.plot.d}' ({inr(plan.plot.w * plan.plot.d)} sq ft)</dd>
                      <dt className="text-slate-500">Facing</dt><dd className="capitalize">{plan.facing.replace("-", " ")}</dd>
                      <dt className="text-slate-500">North</dt><dd>{Math.round(north ?? 0)}° <button className="link ml-1 text-xs" onClick={() => setNorthEdit(true)}>change</button></dd>
                      <dt className="text-slate-500">Built-up</dt><dd>{inr(plan.summary.builtup_sqft)} sq ft · {plan.levels.length} floor(s)</dd>
                    </dl>
                  </div>
                </div>
              </div>
            )}
          </Card>

          {res?.door && (
            <Card title={L(ta, "Main Door – 32 Pada Check", "முதன்மை வாசல் – 32 பதம்")} icon={<DoorOpen size={20} />}>
              <div className="flex flex-wrap items-start gap-4">
                <div className={`rounded-xl px-4 py-3 text-center ring-1 ${res.door.status === "matched" ? "bg-emerald-50 ring-emerald-200" : res.door.status === "partly" ? "bg-amber-50 ring-amber-200" : "bg-red-50 ring-red-200"}`}>
                  <div className="text-2xl font-extrabold text-navy-ink">{res.door.code}</div><div className="text-xs font-semibold">{res.door.name}</div>
                </div>
                <div className="min-w-[220px] flex-1 text-sm">
                  <p className="font-semibold text-navy-ink">{res.door.advice}</p>
                  <div className="mt-2 flex flex-wrap gap-1">
                    {res.door.padas[res.door.side].map((p) => {
                      const code = p.split(" ")[0];
                      const good = ["3", "4"].includes(code.slice(1));
                      return <span key={p} className={`rounded px-1.5 py-0.5 text-[11px] ${code === res.door!.code ? "bg-navy-900 text-white" : good ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>{p}</span>;
                    })}
                  </div>
                  <p className="mt-1 text-[11px] text-slate-500">{res.door.side_name} wall {res.door.side_ft} ft = 8 padas × {res.door.pada_ft} ft (measured on the building wall). Green = preferred.</p>
                </div>
              </div>
            </Card>
          )}

          <Card title={L(ta, "Site & Fixtures", "மனை & பொருத்தங்கள்")} icon={<CircleHelp size={20} />}
            action={<button className="btn-outline btn-sm" onClick={() => setSiteOpen(true)} disabled={!res}>{L(ta, "Answer / change", "பதில் / மாற்று")}</button>}>
            {!res ? <p className="text-sm text-slate-500">—</p> : <>
              {(res.questions?.length || 0) > 0 && (
                <div className="mb-3 rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">
                  <b>{L(ta, "Not in the drawing – please tell:", "வரைபடத்தில் இல்லை – சொல்லவும்:")}</b> {res.questions!.map((q) => q.question).join(" · ")}
                  <button className="link ml-2 text-xs" onClick={() => setSiteOpen(true)}>{L(ta, "Answer now →", "இப்போது பதில் →")}</button>
                </div>)}
              <ul className="grid gap-2 sm:grid-cols-2">{siteChecks.map((c, i) => (
                <li key={i} className="flex items-start gap-2 rounded-lg border border-line px-3 py-2 text-sm"><StatusIcon s={c.status} />
                  <div><div className="font-semibold text-navy-ink">{c.title}</div><div className="text-xs text-slate-600">{c.message}</div>
                    {c.remedy && c.status !== "matched" && <div className="mt-0.5 text-[11px] text-emerald-800">{c.remedy}</div>}</div></li>))}</ul>
            </>}
          </Card>
        </div>

        <div className="min-w-0 space-y-4">
          <Card title={L(ta, "Vastu Direction Overview", "வாஸ்து திசை கண்ணோட்டம்")} icon={<CircleCheck size={20} className="text-emerald-600" />}
            action={<button className="link" onClick={() => setNorthEdit(!northEdit)}>{northEdit ? "Done" : "Adjust north →"}</button>}>
            {!res ? <p className="text-sm text-slate-500">—</p> : (
              <>
                {res.overview8 ? <Directions8 ov={res.overview8} ta={ta} north={north ?? 0} /> : null}
                {northEdit && (
                  <div className="mt-3 rounded-lg border border-line p-3">
                    <NorthDial value={north ?? 0} onChange={(v) => setNorth(v)} />
                    <button className="btn-primary btn-sm mt-2" onClick={() => analyse(designId, north)}>Re-check with this north</button>
                    <p className="mt-1 text-xs text-slate-500">Facing comes from the plan; change north only if the plot is not straight to the compass.</p>
                  </div>
                )}
              </>
            )}
          </Card>

          <Card title={L(ta, "Room-wise Vastu Guidance", "அறை வாரியான வழிகாட்டல்")} icon={<Sun size={20} className="text-amber-500" />}
            action={plan && plan.levels.length > 1 ? <span className="text-xs text-slate-500">{plan.levels[level]?.name}</span> : undefined}>
            <div id="vastu-rooms" />
            {!res ? <p className="text-sm text-slate-500">—</p> : (
              <ul className="space-y-2">
                {roomChecks.map((c, i) => {
                  const I = ICON[c.rule] || LayoutGrid;
                  const k = `${c.rule}-${c.level}-${i}`;
                  return (
                    <li key={k} className={`rounded-xl border ${c.status === "not_matched" ? "border-red-200" : c.status === "partly" ? "border-amber-200" : "border-line"}`}>
                      <button className="flex w-full items-center gap-3 px-3 py-2.5 text-left" onClick={() => { setOpen(open === k ? null : k); setStep(Math.max(step, 3)); }}>
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600"><I size={18} /></span>
                        <span className="w-32 shrink-0 text-sm font-bold text-navy-ink">{c.title}<span className="block truncate text-[11px] font-normal text-slate-500">{c.room !== "—" ? c.room : c.level_name}</span></span>
                        <StatusIcon s={c.status} />
                        <span className="flex-1 text-sm text-slate-700">{c.message}</span>
                        <ChevronRight size={16} className={`shrink-0 text-slate-400 transition ${open === k ? "rotate-90" : ""}`} />
                      </button>
                      {open === k && (
                        <div className="grid gap-2 border-t border-line px-4 py-3 text-xs text-slate-700 sm:grid-cols-2">
                          {c.better ? <div className="sm:col-span-2 flex flex-wrap items-center gap-2"><Badge color="gray">{L(ta, "Now", "இப்போது")}: {c.current}</Badge><ChevronRight size={14} /><Badge color="green">{L(ta, "Better", "சிறந்தது")}: {c.better}</Badge></div>
                            : <div className="sm:col-span-2"><Badge color="green">{L(ta, "Good as it is", "இப்படியே நல்லது")}</Badge></div>}
                          <div><b>{L(ta, "Why", "ஏன்")}: </b>{c.why}</div>
                          {c.remedy && <div className="rounded-lg bg-emerald-50 px-2 py-1 text-emerald-900"><b>{L(ta, "Simple remedy", "எளிய பரிகாரம்")}: </b>{c.remedy}</div>}
                        </div>
                      )}
                    </li>
                  );
                })}
              </ul>
            )}
          </Card>

          <div className="card bg-linear-to-br from-violet-50 to-brand-50 p-5">
            <div className="mb-3 flex items-center gap-2 text-[15px] font-bold text-navy-ink"><Sparkles size={20} className="text-violet-600" />{L(ta, "Vastu Recommendations", "வாஸ்து பரிந்துரைகள்")}</div>
            {!res ? <p className="text-sm text-slate-500">—</p> : (
              <ul className="space-y-2 text-sm text-slate-700">
                {[...res.suggestions.slice(0, 5), ...res.tips.slice(0, Math.max(2, 6 - res.suggestions.length))].map((s, i) => (
                  <li key={i} className="flex gap-2"><CircleCheck size={16} className="mt-0.5 shrink-0 text-emerald-600" />{s}</li>
                ))}
              </ul>
            )}
            <div className="mt-4 flex justify-end"><button className="btn-primary" onClick={getOptions} disabled={!res || busy !== ""}><Sparkles size={16} />{busy === "imp" ? "Working…" : L(ta, "Show improved plan options", "மேம்பட்ட திட்டங்கள்")}</button></div>
          </div>

          {isOwner && (
            <Card title={L(ta, "My Vastu Rules (owner)", "என் வாஸ்து விதிகள்")} icon={<Settings2 size={20} />}
              action={<button className="btn-outline btn-sm" onClick={() => setRulesOpen(true)}>{L(ta, "Edit", "திருத்து")}</button>}>
              <p className="text-xs text-slate-500">{L(ta, "Set your own preferred zones for each room (used in every check, options and reports).", "ஒவ்வொரு அறைக்கும் உங்கள் விருப்ப பகுதிகள் (எல்லா சோதனைகளிலும் பயன்படும்).")}</p>
            </Card>
          )}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button className="btn-outline px-5 py-3" onClick={downloadPdf} disabled={!res}><Download size={18} />{L(ta, "Report PDF (English)", "அறிக்கை PDF (ஆங்கிலம்)")}</button>
        <button className="btn-outline px-5 py-3" onClick={() => printReport("ta")} disabled={!res}><Printer size={18} />தமிழ் அறிக்கை (Print / PDF)</button>
        <button className="btn-outline px-5 py-3" onClick={() => printReport("en")} disabled={!res}><Printer size={18} />English (Print)</button>
        <button className="btn-outline px-5 py-3" onClick={saveReport} disabled={!res}><Save size={18} />{L(ta, "Save Analysis", "சேமி")}</button>
        {reports.length > 0 && <span className="inline-flex items-center gap-1 text-xs text-slate-500">Last saved: {fmtDateTime(reports[0].created_at)} ({reports[0].summary?.score ?? `${reports[0].summary?.matched}/${reports[0].summary?.total}`})
          <button className="link" onClick={() => downloadFile(`/api/vastu/reports/${reports[0].id}/pdf`, `${fname("Vastu_Report")}_${reports[0].id}.pdf`).catch((e) => toast(e.message, "err"))}>PDF</button>
          <OwnerDelete entity="vastu_report" id={reports[0].id} title={`Vastu report of ${fmtDateTime(reports[0].created_at)}`} onDone={() => setReports(reports.slice(1))} /></span>}
        <button className="btn-primary ml-auto px-6 py-3" onClick={getOptions} disabled={!res || busy !== ""}><Sparkles size={18} />{L(ta, "Improved plan options (2–3)", "மேம்பட்ட திட்டங்கள் (2–3)")}</button>
      </div>

      <Modal open={upload} onClose={() => setUpload(false)} title="Upload drawing for Vastu check" wide="xl">
        {pid && <DrawingImport projectId={pid} designs={designs} onSaved={async (d) => { setUpload(false); await loadDesigns(); setDesignId(d.id); analyse(d.id); }} />}
      </Modal>

      <Modal open={!!opts} onClose={() => setOpts(null)} title={L(ta, "Improved plan options – compare", "மேம்பட்ட திட்டங்கள் – ஒப்பிடு")} wide="xl">
        {opts && plan && (
          <div className="space-y-3">
            {!opts.options.length ? <p className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-900">{opts.message}</p> : (
              <div className={`grid gap-3 ${opts.options.length >= 2 ? "lg:grid-cols-4" : "lg:grid-cols-2"} sm:grid-cols-2`}>
                <div className="rounded-xl border border-line p-2">
                  <div className="mb-1 flex items-center justify-between text-sm"><b>{L(ta, "Now", "இப்போது")}</b><Badge color="gray">{opts.current.score}/100</Badge></div>
                  <div className="aspect-square rounded-lg border border-line bg-white"><PlanSvg plan={plan} level={level} vastuGrid showDims={false} /></div>
                  <ul className="mt-1 text-[11px] text-slate-500">{opts.current.floors.map((f) => <li key={f.level}>{f.name}: {f.score}</li>)}</ul>
                </div>
                {opts.options.map((o, i) => (
                  <div key={i} className="rounded-xl border-2 border-emerald-200 p-2">
                    <div className="mb-1 flex items-center justify-between text-sm"><b>{L(ta, "Option", "விருப்பம்")} {i + 1}</b><Badge color="green">{o.score}/100</Badge></div>
                    <div className="aspect-square rounded-lg border border-line bg-white"><PlanSvg plan={o.plan} level={Math.min(level, o.plan.levels.length - 1)} vastuGrid showDims={false} /></div>
                    <div className="mt-1 text-xs font-semibold text-navy-ink">{o.label}</div>
                    <ul className="text-[11px] text-slate-600">{o.changes.slice(0, 4).map((c) => <li key={c}>• {c}</li>)}</ul>
                    <ul className="mt-1 text-[11px] text-slate-500">{o.floors.map((f) => <li key={f.level}>{f.name}: {f.score}</li>)}</ul>
                    {o.remaining.length > 0 && <div className="mt-1 text-[11px] text-amber-800">{L(ta, "Still to fix", "இன்னும் சரிசெய்ய")}: {o.remaining.length}</div>}
                    <button className="btn-primary btn-sm mt-2 w-full" onClick={() => saveOption(o)}><Save size={14} />{L(ta, "Save as new version", "புதிய பதிப்பாக சேமி")}</button>
                  </div>
                ))}
              </div>
            )}
            <p className="text-xs text-slate-500">Only whole rooms of suitable size are moved; the building size and the room list stay the same. Check doors and furniture in the 2D editor after saving.</p>
          </div>
        )}
      </Modal>

      {siteOpen && pid && <SiteModal pid={pid} ta={ta} onClose={() => setSiteOpen(false)} onSaved={() => { setSiteOpen(false); analyse(designId, north); }} />}
      {rulesOpen && <RulesModal ta={ta} onClose={() => setRulesOpen(false)} onSaved={() => { setRulesOpen(false); analyse(designId, north); }} />}
    </Page>
  );
}

const OPT_LABEL: Record<string, [string, string]> = { regular: ["Regular (square / rectangle)", "சீரான (சதுரம் / செவ்வகம்)"], cut: ["Corner cut", "மூலை வெட்டு"],
  extension: ["Corner extended", "மூலை நீட்சி"], no: ["No", "இல்லை"], yes: ["Yes", "ஆம்"], none: ["Not there", "இல்லை"], clockwise: ["Clockwise", "கடிகார சுற்று"],
  anticlockwise: ["Anticlockwise", "எதிர் சுற்று"], straight: ["Straight flight", "நேரான படி"], "N-S": ["North–South", "வடக்கு–தெற்கு"], "E-W": ["East–West", "கிழக்கு–மேற்கு"] };

function SiteModal({ pid, ta, onClose, onSaved }: { pid: number; ta: boolean; onClose: () => void; onSaved: () => void }) {
  const [fields, setFields] = useState<any[]>([]);
  const [v, setV] = useState<Record<string, any>>({});
  useEffect(() => { api<any>(`/api/projects/${pid}/vastu/site`).then((r) => { setFields(r.fields); setV(r.site || {}); }).catch((e) => toast(e.message, "err")); }, [pid]);
  const lab = (o: string) => (OPT_LABEL[o] ? OPT_LABEL[o][ta ? 1 : 0] : ZN[o] ? ZN[o][ta ? 1 : 0] : o);
  const save = async () => {
    try { await api(`/api/projects/${pid}/vastu/site`, { method: "PUT", body: v }); toast("Saved"); onSaved(); } catch (e: any) { toast(e.message, "err"); }
  };
  const hide = (k: string) => (k === "shape_corner" && (!v.plot_shape || v.plot_shape === "regular")) || (k === "t_junction_zone" && v.t_junction !== "yes");
  return (
    <Modal open onClose={onClose} title={L(ta, "Site & fixtures – details not in the drawing", "மனை & பொருத்தங்கள் – வரைபடத்தில் இல்லாத விவரங்கள்")} wide>
      <p className="mb-3 text-xs text-slate-500">{L(ta, "Leave blank if you do not know yet – it will be asked, never guessed.", "தெரியாவிட்டால் காலியாக விடவும் – ஊகிக்கப்படாது, கேட்கப்படும்.")}</p>
      <div className="grid max-h-[60vh] gap-3 overflow-auto sm:grid-cols-2">
        {fields.filter((f) => !hide(f.key)).map((f) => (
          <label key={f.key} className="text-sm"><span className="label">{ta ? f.question_ta : f.question}</span>
            {f.kind === "multi" ? (
              <div className="flex flex-wrap gap-2">{f.options.map((o: string) => (
                <label key={o} className="flex items-center gap-1 text-xs"><input type="checkbox" checked={(v[f.key] || []).includes(o)}
                  onChange={(e) => setV({ ...v, [f.key]: e.target.checked ? [...(v[f.key] || []), o] : (v[f.key] || []).filter((x: string) => x !== o) })} />{lab(o)}</label>))}</div>
            ) : (
              <select className="input" value={v[f.key] || ""} onChange={(e) => setV({ ...v, [f.key]: e.target.value })}>
                <option value="">{L(ta, "— not known yet —", "— இன்னும் தெரியவில்லை —")}</option>
                {f.options.map((o: string) => <option key={o} value={o}>{lab(o)}</option>)}
              </select>
            )}
          </label>
        ))}
      </div>
      <div className="mt-4 flex justify-end gap-2"><button className="btn-ghost" onClick={onClose}>Cancel</button><button className="btn-primary" onClick={save}><Save size={16} />{L(ta, "Save & re-check", "சேமித்து மீண்டும் சோதி")}</button></div>
    </Modal>
  );
}

function RulesModal({ ta, onClose, onSaved }: { ta: boolean; onClose: () => void; onSaved: () => void }) {
  const [rules, setRules] = useState<any[]>([]);
  const [own, setOwn] = useState<Record<string, { good: string[]; ok: string[] }>>({});
  useEffect(() => { api<any>("/api/vastu/rules").then((r) => { setRules(r.rules); setOwn(r.own || {}); }).catch((e) => toast(e.message, "err")); }, []);
  const ZS = [...Z8, "C"];
  const stateOf = (k: string, z: string, r: any) => {
    const o = own[k];
    const g = o ? o.good : r.good, ok = o ? o.ok : r.ok;
    return g.includes(z) ? "good" : ok.includes(z) ? "ok" : "avoid";
  };
  const cycle = (k: string, z: string, r: any) => {
    const cur = own[k] || { good: [...r.good], ok: [...r.ok] };
    const s = stateOf(k, z, r);
    const good = cur.good.filter((x) => x !== z), ok = cur.ok.filter((x) => x !== z);
    if (s === "good") ok.push(z); else if (s === "avoid") good.push(z);
    setOwn({ ...own, [k]: { good, ok } });
  };
  const save = async (body: any) => {
    try { await api("/api/vastu/rules", { method: "PUT", body }); toast("Vastu rules saved"); onSaved(); } catch (e: any) { toast(e.message, "err"); }
  };
  const tone = { good: "bg-emerald-500 text-white", ok: "bg-amber-300 text-amber-950", avoid: "bg-slate-100 text-slate-400" } as const;
  return (
    <Modal open onClose={onClose} title={L(ta, "My Vastu rules – preferred zones per room", "என் வாஸ்து விதிகள் – அறை வாரியான விருப்ப பகுதிகள்")} wide="xl">
      <p className="mb-2 text-xs text-slate-500">{L(ta, "Click a zone: green = preferred → yellow = acceptable → grey = avoid. Used in every check, the options and the reports.",
        "பகுதியை கிளிக் செய்யவும்: பச்சை = சிறந்தது → மஞ்சள் = பரவாயில்லை → சாம்பல் = தவிர்க்கவும்.")}</p>
      <div className="overflow-x-auto"><table className="w-full min-w-[720px] text-sm">
        <thead><tr><th className="table-th">Room</th>{ZS.map((z) => <th key={z} className="table-th text-center">{z}</th>)}<th className="table-th" /></tr></thead>
        <tbody>{rules.map((r) => (
          <tr key={r.key}><td className="table-td font-semibold">{r.title}{own[r.key] && <span className="ml-1 text-[10px] text-brand-600">(yours)</span>}</td>
            {ZS.map((z) => { const s = stateOf(r.key, z, r); return <td key={z} className="table-td text-center"><button onClick={() => cycle(r.key, z, r)} className={`h-7 w-9 rounded text-[11px] font-bold ${tone[s]}`}>{s === "good" ? "✓" : s === "ok" ? "~" : "–"}</button></td>; })}
            <td className="table-td">{own[r.key] && <button className="btn-ghost btn-sm" onClick={() => { const n = { ...own }; delete n[r.key]; setOwn(n); }}><RotateCcw size={12} /></button>}</td></tr>
        ))}</tbody>
      </table></div>
      <div className="mt-4 flex flex-wrap justify-end gap-2">
        <button className="btn-ghost" onClick={() => save({})}><RotateCcw size={14} />{L(ta, "Back to built-in rules", "இயல்பு விதிகள்")}</button>
        <button className="btn-primary" onClick={() => save(own)}><Save size={16} />{L(ta, "Save my rules", "சேமி")}</button>
      </div>
    </Modal>
  );
}
