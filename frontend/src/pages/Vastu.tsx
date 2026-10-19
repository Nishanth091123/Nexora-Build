import { useCallback, useEffect, useState, type ReactNode } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import {
  Bath, BedDouble, BedSingle, Box, Car, ChevronRight, CircleCheck, CircleX, Compass, CookingPot, DoorOpen, Download,
  FileUp, Flower2, Layers, LayoutGrid, PenSquare, Save, Sofa, Sparkles, Sun, TriangleAlert, Utensils,
} from "lucide-react";
import Page from "../components/Page";
import OwnerDelete from "../components/OwnerDelete";
import DrawingImport from "../components/design/DrawingImport";
import NorthDial from "../components/design/NorthDial";
import Plan3D from "../components/design/Plan3D";
import PlanSvg from "../components/design/PlanSvg";
import { Badge, Card, Empty, Modal, toast } from "../components/ui";
import { api, downloadFile, fmtDateTime, inr } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";
import type { Plan } from "../lib/plan";

type Check = { rule: string; title: string; room: string; room_id: string | null; level: number; level_name: string; zone: string;
  status: "matched" | "partly" | "not_matched"; message: string; why: string };
type Result = { checks: Check[]; overview: Record<string, { status: string; rooms: string[] }>;
  summary: { matched: number; partly: number; not_matched: number; total: number; label: string };
  suggestions: string[]; tips: string[]; north_deg: number; facing: string; note: string };
type DesignRow = { id: number; version: number; title: string; source: string; builtup_sqft: number; created_at: string };

const ICON: Record<string, any> = { entrance: DoorOpen, hall: Sofa, kitchen: CookingPot, master: BedDouble, bedroom: BedSingle,
  toilet: Bath, pooja: Flower2, stair: Layers, dining: Utensils, parking: Car, brahmasthan: LayoutGrid, ne_light: Sun, sw_heavy: LayoutGrid, shape: LayoutGrid };
const STATUS_TONE: Record<string, string> = { Excellent: "bg-emerald-50 text-emerald-700", Good: "bg-brand-50 text-brand-700", "Needs Attention": "bg-amber-50 text-amber-700" };
const ZONE_FULL: Record<string, string> = { N: "North", NE: "North-East", E: "East", SE: "South-East", S: "South", SW: "South-West", W: "West", NW: "North-West", C: "Centre" };

function StatusIcon({ s }: { s: Check["status"] }) {
  if (s === "matched") return <CircleCheck size={18} className="shrink-0 text-emerald-600" />;
  if (s === "partly") return <TriangleAlert size={18} className="shrink-0 text-amber-500" />;
  return <CircleX size={18} className="shrink-0 text-red-500" />;
}

function Ring({ matched, total }: { matched: number; total: number }) {
  const R = 46, C = 2 * Math.PI * R, f = total ? matched / total : 0;
  return (
    <svg width="120" height="120" viewBox="0 0 120 120" className="shrink-0">
      <circle cx="60" cy="60" r={R} fill="none" stroke="#e2e8f0" strokeWidth="11" />
      <circle cx="60" cy="60" r={R} fill="none" stroke={f >= 0.75 ? "#16a34a" : f >= 0.5 ? "#2563eb" : "#f59e0b"} strokeWidth="11"
        strokeDasharray={`${f * C} ${C}`} strokeLinecap="round" transform="rotate(-90 60 60)" />
      <text x="60" y="58" textAnchor="middle" fontSize="24" fontWeight="800" className="fill-navy-ink">{matched}/{total}</text>
      <text x="60" y="76" textAnchor="middle" fontSize="10" className="fill-slate-500">rules matched</text>
    </svg>
  );
}

function CompassCard({ north }: { north: number }) {
  // the compass is drawn in true directions (N up); the small arrow shows where north is on the plan
  return (
    <svg viewBox="-80 -80 160 160" className="h-44 w-44 shrink-0">
      <circle r="70" fill="#f0fdf4" stroke="#bbf7d0" />
      <circle r="48" fill="#dcfce7" stroke="#bbf7d0" />
      <circle r="26" fill="white" stroke="#bbf7d0" />
      {[0, 90, 180, 270].map((a) => { const t = (a * Math.PI) / 180; return <line key={a} x1={Math.sin(t) * 28} y1={-Math.cos(t) * 28} x2={Math.sin(t) * 62} y2={-Math.cos(t) * 62} stroke="#64748b" strokeWidth="1.5" />; })}
      <text y="-66" dy="-2" textAnchor="middle" fontSize="16" fontWeight="800" fill="#dc2626">N</text>
      <text x="74" y="5" textAnchor="middle" fontSize="15" fontWeight="800" fill="#dc2626">E</text>
      <text y="78" textAnchor="middle" fontSize="15" fontWeight="800" fill="#0f172a">S</text>
      <text x="-74" y="5" textAnchor="middle" fontSize="15" fontWeight="800" fill="#0f172a">W</text>
      <path d="M-16 4 L0 -12 L16 4 V18 H-16 Z" fill="#f59e0b" stroke="#b45309" strokeWidth="1.5" />
      <rect x="-4" y="8" width="8" height="10" fill="#92400e" />
      <text y="64" textAnchor="middle" fontSize="8" fill="#64748b">plan north {Math.round(north)}°</text>
    </svg>
  );
}

export default function VastuPage() {
  const { t } = useI18n();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const { currentProject } = useAuth();
  const pid = currentProject?.id;
  const allowed = !!currentProject?.permissions?.vastu;
  const [designs, setDesigns] = useState<DesignRow[]>([]);
  const [designId, setDesignId] = useState<number | null>(null);
  const [plan, setPlan] = useState<Plan | null>(null);
  const [res, setRes] = useState<Result | null>(null);
  const [north, setNorth] = useState<number | null>(null);
  const [level, setLevel] = useState(0);
  const [view, setView] = useState<"2d" | "3d">("2d");
  const [open, setOpen] = useState<string | null>(null);
  const [upload, setUpload] = useState(false);
  const [improved, setImproved] = useState<any>(null);
  const [step, setStep] = useState(1);
  const [busy, setBusy] = useState("");
  const [northEdit, setNorthEdit] = useState(false);
  const [reports, setReports] = useState<any[]>([]);

  const loadDesigns = useCallback(async () => {
    if (!pid) return [];
    const d = await api<DesignRow[]>(`/api/projects/${pid}/designs`);
    setDesigns(d);
    return d;
  }, [pid]);

  const analyse = async (id: number | null, nd: number | null = null) => {
    if (!pid || !id) return;
    setBusy("an");
    try {
      const r = await api<{ plan: Plan; result: Result }>(`/api/projects/${pid}/vastu/analyse`, { body: { design_id: id, north_deg: nd } });
      setPlan(r.plan); setRes(r.result); setNorth(r.result.north_deg); setLevel(0); setStep(2); setImproved(null);
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(""); }
  };

  useEffect(() => {
    if (!pid || !allowed) return;
    setPlan(null); setRes(null); setStep(1);
    const want = Number(params.get("design")) || 0;
    loadDesigns().then((d) => {
      const pick = d.find((x) => x.id === want) || d[0];
      if (pick) { setDesignId(pick.id); analyse(pick.id); }
    }).catch((e) => toast(e.message, "err"));
    api<any[]>(`/api/projects/${pid}/vastu/reports`).then(setReports).catch(() => {});
  }, [pid, allowed]);

  const saveReport = async (download: boolean) => {
    if (!pid || !designId) return;
    try {
      const r = await api<any>(`/api/projects/${pid}/vastu/reports`, { body: { design_id: designId, north_deg: north } });
      setReports([r, ...reports]);
      if (download) await downloadFile(`/api/vastu/reports/${r.id}/pdf`, `${currentProject?.code}_Vastu_Report_${r.id}.pdf`);
      else toast("Vastu report saved");
    } catch (e: any) { toast(e.message, "err"); }
  };
  const improve = async () => {
    if (!pid || !designId) return;
    setBusy("imp");
    try {
      const r = await api<any>(`/api/projects/${pid}/vastu/apply`, { body: { design_id: designId, north_deg: north } });
      setImproved(r); setStep(4);
      if (!r.changes.length) toast(r.message || "No automatic improvement found", "err");
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(""); }
  };
  const saveImproved = async () => {
    if (!pid || !improved) return;
    const d = designs.find((x) => x.id === designId);
    try {
      const s = await api<any>(`/api/projects/${pid}/designs`, { body: { plan: improved.plan, title: `${d?.title || "Design"} (Vastu improved)`, source: "edited",
        prompt: "Vastu suggestions applied", state: currentProject?.state || "Tamil Nadu", parent_id: designId } });
      toast(`Saved as design v${s.version}`); setImproved(null);
      await loadDesigns(); setDesignId(s.id); analyse(s.id);
    } catch (e: any) { toast(e.message, "err"); }
  };

  if (!currentProject) return <Page title={t("Vastu Intelligence")} subtitle="Analyze your plan and get Vastu recommendations"><Empty text="Create a project first (Projects page)." /></Page>;
  if (!allowed) return <Page title={t("Vastu Intelligence")} subtitle="Analyze your plan and get Vastu recommendations"><Empty text="You don't have Vastu access for this project. Ask the owner." /></Page>;

  const steps = ["Upload Drawing", "Analyze & Evaluate", "Get Recommendations", "Apply Suggestions"];
  const highlight: Record<string, string> = {};
  res?.checks.forEach((c) => { if (c.room_id && c.level === level) highlight[c.room_id] = c.status === "matched" ? "#16a34a" : c.status === "partly" ? "#f59e0b" : "#ef4444"; });
  const roomChecks = (res?.checks || []).filter((c) => c.rule !== "shape");
  const g = plan?.levels[0]?.summary;

  return (
    <Page title={t("Vastu Intelligence")} subtitle="Analyze your plan and get Vastu recommendations">
      <div className="flex flex-wrap items-center justify-center gap-2">
        {steps.map((s, i) => (
          <div key={s} className="flex items-center gap-2">
            <button onClick={() => { if (i === 0) setUpload(true); else if (i === 2) document.getElementById("vastu-rooms")?.scrollIntoView({ behavior: "smooth" }); else if (i === 3) improve(); }}
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
                <select className="input w-auto py-2 text-sm" value={designId ?? ""} onChange={(e) => { const id = Number(e.target.value); setDesignId(id); analyse(id); }}>
                  {designs.map((d) => <option key={d.id} value={d.id}>v{d.version} – {d.title}{d.source === "upload" ? " (from drawing)" : ""}</option>)}
                </select>
              )}
            </div>
          </div>

          <Card title="Analyzed Plan" icon={<Compass size={20} />}
            action={<div className="flex gap-2">
              <button className={view === "2d" ? "btn-primary btn-sm" : "btn-outline btn-sm"} onClick={() => setView("2d")}>2D View</button>
              <button className={view === "3d" ? "btn-primary btn-sm" : "btn-outline btn-sm"} onClick={() => setView("3d")}><Box size={14} />3D View</button>
              <button className="btn-outline btn-sm" onClick={() => nav(`/design?tab=editor&design=${designId}`)} disabled={!designId}><PenSquare size={14} />Edit Plan</button>
            </div>}>
            {!plan || !res ? <Empty icon={<Compass className="text-slate-400" />} text={busy ? "Analysing…" : "Upload a drawing or make a plan in Design Studio – then the Vastu check runs here."} /> : (
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-[1.35fr_1fr]">
                <div className="min-w-0">
                  {plan.levels.length > 1 && <div className="mb-2 flex flex-wrap gap-2">{plan.levels.map((l, i) => <button key={i} onClick={() => setLevel(i)} className={`rounded-lg px-3 py-1 text-xs font-medium ${i === level ? "bg-navy-900 text-white" : "bg-slate-100"}`}>{l.name}</button>)}</div>}
                  {view === "2d" ? <div className="aspect-[4/5] w-full rounded-lg border border-line bg-white p-1"><PlanSvg plan={plan} level={level} vastuGrid highlight={highlight} /></div>
                    : <Plan3D plan={plan} />}
                  <div className="mt-2 flex flex-wrap gap-3 text-xs text-slate-600">
                    <span className="flex items-center gap-1"><span className="h-3 w-3 rounded-sm border-2 border-emerald-600" />matched</span>
                    <span className="flex items-center gap-1"><span className="h-3 w-3 rounded-sm border-2 border-amber-500" />partly</span>
                    <span className="flex items-center gap-1"><span className="h-3 w-3 rounded-sm border-2 border-red-500" />not matched</span>
                    <span className="flex items-center gap-1"><span className="h-3 w-3 rounded-sm border-2 border-dashed border-orange-500" />Vastu grid (8 zones + centre)</span>
                  </div>
                </div>
                <div className="space-y-4">
                  <div className="rounded-xl bg-slate-50 p-4">
                    <div className="mb-2 flex items-center gap-2 text-sm font-bold text-navy-ink"><LayoutGrid size={16} />Plan Details</div>
                    <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1.5 text-sm">
                      <dt className="text-slate-500">Plot Size</dt><dd>{plan.plot.w}' × {plan.plot.d}' ({inr(plan.plot.w * plan.plot.d)} sq ft)</dd>
                      <dt className="text-slate-500">Facing</dt><dd className="capitalize">{plan.facing.replace("-", " ")}</dd>
                      <dt className="text-slate-500">North arrow</dt><dd>{Math.round(north ?? 0)}° <button className="link ml-1 text-xs" onClick={() => setNorthEdit(true)}>change</button></dd>
                      <dt className="text-slate-500">Built-up Area</dt><dd>{inr(plan.summary.builtup_sqft)} sq ft</dd>
                      <dt className="text-slate-500">Floors</dt><dd>{plan.levels.length}</dd>
                      <dt className="text-slate-500">Bedrooms</dt><dd>{plan.summary.bedrooms}</dd>
                      <dt className="text-slate-500">Toilets</dt><dd>{plan.summary.toilets}</dd>
                    </dl>
                    {g && <div className="mt-1 text-xs text-slate-400">Ground floor {inr(g.builtup_sqft)} sq ft</div>}
                  </div>
                  <div className="rounded-xl border border-line p-4">
                    <div className="mb-2 flex items-center gap-2 text-sm font-bold text-navy-ink"><Sparkles size={16} />Vastu Analysis Result</div>
                    <div className="flex items-center gap-3">
                      <Ring matched={res.summary.matched} total={res.summary.total} />
                      <div className="text-sm">
                        <div className="font-bold text-navy-ink">{res.summary.label}</div>
                        <div className="text-slate-500">{res.summary.partly} partly · {res.summary.not_matched} not matched</div>
                      </div>
                    </div>
                    <div className="mt-3 flex gap-2 rounded-lg bg-emerald-50 px-3 py-2 text-xs text-emerald-800"><CircleCheck size={15} className="shrink-0" />{res.note}</div>
                  </div>
                </div>
              </div>
            )}
          </Card>
        </div>

        <div className="min-w-0 space-y-4">
          <Card title="Vastu Direction Overview" icon={<CircleCheck size={20} className="text-emerald-600" />}
            action={<button className="link" onClick={() => setNorthEdit(!northEdit)}>{northEdit ? "Done" : "Adjust north →"}</button>}>
            {!res ? <p className="text-sm text-slate-500">—</p> : (
              <>
                <div className="flex flex-wrap items-center gap-4">
                  <CompassCard north={north ?? 0} />
                  <dl className="min-w-[200px] flex-1 divide-y divide-line text-sm">
                    {(["North", "East", "South", "West"] as const).map((k) => (
                      <div key={k} className="flex items-center justify-between py-2">
                        <dt className="font-semibold text-navy-ink">{k}</dt>
                        <dd><span className={`rounded-full px-3 py-1 text-xs font-semibold ${STATUS_TONE[res.overview[k]?.status] || ""}`}>{res.overview[k]?.status}</span></dd>
                      </div>
                    ))}
                  </dl>
                </div>
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

          <Card title="Room-wise Vastu Suggestions" icon={<Sun size={20} className="text-amber-500" />}>
            <div id="vastu-rooms" />
            {!res ? <p className="text-sm text-slate-500">—</p> : (
              <ul className="space-y-2">
                {roomChecks.map((c, i) => {
                  const I = ICON[c.rule === "bedroom" ? "bedroom" : c.rule] || LayoutGrid;
                  const k = `${c.rule}-${i}`;
                  return (
                    <li key={k} className="rounded-xl border border-line">
                      <button className="flex w-full items-center gap-3 px-3 py-2.5 text-left" onClick={() => { setOpen(open === k ? null : k); setStep(Math.max(step, 3)); }}>
                        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-600"><I size={18} /></span>
                        <span className="w-32 shrink-0 text-sm font-bold text-navy-ink">{c.title}{c.level > 0 && <span className="block text-[11px] font-normal text-slate-500">{c.level_name}</span>}</span>
                        <StatusIcon s={c.status} />
                        <span className="flex-1 text-sm text-slate-700">{c.message}</span>
                        <ChevronRight size={16} className={`shrink-0 text-slate-400 transition ${open === k ? "rotate-90" : ""}`} />
                      </button>
                      {open === k && <div className="border-t border-line px-4 py-2 text-xs text-slate-600">{c.room !== "—" && <b>{c.room}: </b>}{c.why}{c.zone && ` (zone: ${ZONE_FULL[c.zone] || c.zone})`}</div>}
                    </li>
                  );
                })}
              </ul>
            )}
          </Card>

          <div className="card bg-linear-to-br from-violet-50 to-brand-50 p-5">
            <div className="mb-3 flex items-center gap-2 text-[15px] font-bold text-navy-ink"><Sparkles size={20} className="text-violet-600" />Vastu Recommendations</div>
            {!res ? <p className="text-sm text-slate-500">—</p> : (
              <ul className="space-y-2 text-sm text-slate-700">
                {[...res.suggestions.slice(0, 5), ...res.tips.slice(0, Math.max(2, 6 - res.suggestions.length))].map((s, i) => (
                  <li key={i} className="flex gap-2"><CircleCheck size={16} className="mt-0.5 shrink-0 text-emerald-600" />{s}</li>
                ))}
              </ul>
            )}
            <div className="mt-4 flex justify-end"><button className="btn-primary" onClick={improve} disabled={!res || busy !== ""}><Sparkles size={16} />{busy === "imp" ? "Working…" : "Generate Vastu Plan"}</button></div>
          </div>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <button className="btn-outline px-6 py-3" onClick={() => saveReport(true)} disabled={!res}><Download size={18} />Download Report</button>
        <button className="btn-outline px-6 py-3" onClick={() => saveReport(false)} disabled={!res}><Save size={18} />Save Analysis</button>
        {reports.length > 0 && <span className="inline-flex items-center gap-1 text-xs text-slate-500">Last saved: {fmtDateTime(reports[0].created_at)} ({reports[0].summary?.matched}/{reports[0].summary?.total})
          <OwnerDelete entity="vastu_report" id={reports[0].id} title={`Vastu report of ${fmtDateTime(reports[0].created_at)}`} onDone={() => setReports(reports.slice(1))} /></span>}
        <button className="btn-primary ml-auto px-6 py-3" onClick={improve} disabled={!res || busy !== ""}><Sparkles size={18} />Get Vastu Improved Plan with Suggestions</button>
      </div>

      <Modal open={upload} onClose={() => setUpload(false)} title="Upload drawing for Vastu check" wide="xl">
        {pid && <DrawingImport projectId={pid} designs={designs} onSaved={async (d) => { setUpload(false); await loadDesigns(); setDesignId(d.id); analyse(d.id); }} />}
      </Modal>

      <Modal open={!!improved} onClose={() => setImproved(null)} title="Vastu improved plan" wide>
        {improved && (
          <div className="space-y-3">
            {(improved.remaining?.length || 0) > 0 && (
              <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                <div className="mb-1 font-semibold">Still to fix by hand (2D editor):</div>
                <ul className="list-disc pl-5">{improved.remaining.map((r: string) => <li key={r}>{r}</li>)}</ul>
                {improved.remaining.some((r: string) => r.startsWith("Main Entrance")) && <p className="mt-1 text-xs">The entrance follows the road side – it can only change with a different door position / plot facing.</p>}
              </div>
            )}
            {improved.changes.length === 0 ? <p className="text-sm text-amber-800">{improved.message}</p> : (
              <>
                <div className="flex flex-wrap gap-2 text-sm">
                  <Badge color="gray">Before: {improved.before.matched}/{improved.before.total} matched</Badge>
                  <Badge color="green">After: {improved.after.matched}/{improved.after.total} matched</Badge>
                </div>
                <ul className="space-y-1 text-sm text-slate-700">{improved.changes.map((c: string) => <li key={c}>• {c}</li>)}</ul>
                <div className="grid grid-cols-2 gap-2">
                  <div><div className="mb-1 text-xs font-semibold text-slate-500">Before</div><div className="aspect-square rounded-lg border border-line bg-white"><PlanSvg plan={plan!} level={0} vastuGrid showDims={false} /></div></div>
                  <div><div className="mb-1 text-xs font-semibold text-slate-500">After</div><div className="aspect-square rounded-lg border border-line bg-white"><PlanSvg plan={improved.plan} level={0} vastuGrid showDims={false} /></div></div>
                </div>
                <p className="text-xs text-slate-500">Only whole rooms of suitable size were swapped. Check doors and furniture in the 2D editor after saving.</p>
                <div className="flex justify-end gap-2"><button className="btn-ghost" onClick={() => setImproved(null)}>Close</button><button className="btn-primary" onClick={saveImproved}><Save size={16} />Save as new design version</button></div>
              </>
            )}
          </div>
        )}
      </Modal>
    </Page>
  );
}
