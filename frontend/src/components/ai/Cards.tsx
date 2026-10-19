import { useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Box, Calculator, ChevronDown, ChevronRight, CircleCheck, Compass, Download, ExternalLink, FileSpreadsheet, FileText,
  HardHat, Layers, Lightbulb, Pencil, Ruler, Send, TriangleAlert,
} from "lucide-react";
import Plan3D from "../design/Plan3D";
import PlanSvg from "../design/PlanSvg";
import { PhotoResultView } from "../site/PhotoCheck";
import { Badge, Modal, toast } from "../ui";
import { api, downloadFile, inr, lakhs, num, rupees } from "../../lib/api";
import type { CalcCardT, Card, EstimateCardT, Field, Links, SendOpts, Source } from "./types";

export type CardCtx = {
  msgId: number; pid: number | null; code: string; perms: Record<string, boolean>; active: boolean;
  send: (o: SendOpts) => void; onLinked: (l: Links) => void;
};

// ---------------------------------------------------------------- saving helpers (design / estimate from a chat card)
async function linkMsg(msgId: number, l: Links) {
  try { await api(`/api/ai/messages/${msgId}/links`, { body: l }); } catch { /* not critical */ }
}

function useSavers(card: { links?: Links }, ctx: CardCtx) {
  const [links, setLinks] = useState<Links>(card.links || {});
  const [busy, setBusy] = useState("");
  const need = () => {
    if (!ctx.pid) { toast("Choose a project first (top bar) to save this.", "err"); return false; }
    return true;
  };
  const saveDesign = async (plan: any, title: string, prompt: string, spec: string, state: string): Promise<number | null> => {
    if (links.design_id) return links.design_id;
    if (!need()) return null;
    if (!ctx.perms.design) { toast("You need Design access on this project to save plans.", "err"); return null; }
    const d = await api<any>(`/api/projects/${ctx.pid}/designs`, { body: { plan, title: title.slice(0, 120), prompt, source: "ai", spec_level: spec, state } });
    const l = { ...links, design_id: d.id };
    setLinks(l); ctx.onLinked(l); linkMsg(ctx.msgId, { design_id: d.id });
    toast(`Saved as design v${d.version}`);
    return d.id;
  };
  const saveEstimate = async (inputs: any, state: string, title: string): Promise<number | null> => {
    if (links.estimate_id) return links.estimate_id;
    if (!need()) return null;
    if (!ctx.perms.estimate) { toast("You need Estimate access on this project to save estimates.", "err"); return null; }
    const e = await api<any>(`/api/projects/${ctx.pid}/estimates`, { body: { inputs, state, title: title.slice(0, 120) } });
    const l = { ...links, estimate_id: e.id };
    setLinks(l); ctx.onLinked(l); linkMsg(ctx.msgId, { estimate_id: e.id });
    toast(`Saved as estimate v${e.version}`);
    return e.id;
  };
  const run = async (key: string, fn: () => Promise<void>) => {
    if (busy) return;
    setBusy(key);
    try { await fn(); } catch (e: any) { if (e.message) toast(e.message, "err"); } finally { setBusy(""); }
  };
  return { links, busy, run, saveDesign, saveEstimate };
}

const ActBtn = ({ icon: I, label, onClick, busy, tone = "" }: { icon: any; label: string; onClick: () => void; busy?: boolean; tone?: string }) => (
  <button onClick={onClick} disabled={busy}
    className={`inline-flex items-center gap-1.5 rounded-lg border border-line bg-white px-3 py-2 text-xs font-semibold text-navy-ink shadow-card transition hover:border-brand-100 hover:bg-brand-50 disabled:opacity-60 ${tone}`}>
    <I size={15} className={tone ? "" : "text-brand-600"} />{busy ? "Working…" : label}
  </button>
);

// ---------------------------------------------------------------- material table
function MaterialTable({ rows, note }: { rows: { label: string; qty: number; unit: string }[]; note?: string }) {
  return (
    <div>
      <div className="mb-1.5 text-[13px] font-bold text-navy-ink">Material Quantity (Estimated)</div>
      <div className="overflow-hidden rounded-lg border border-line">
        <table className="w-full">
          <thead><tr><th className="table-th">Item</th><th className="table-th text-right">Quantity</th><th className="table-th">Unit</th></tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.label}><td className="table-td py-1.5">{r.label}</td><td className="table-td py-1.5 text-right font-semibold">{num(r.qty, 1)}</td><td className="table-td py-1.5">{r.unit}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      {note && <p className="mt-1.5 text-[11px] leading-snug text-slate-500"><b>Note:</b> {note}</p>}
    </div>
  );
}

// ---------------------------------------------------------------- plan
export function PlanCard({ card, ctx }: { card: Extract<Card, { type: "plan" }>; ctx: CardCtx }) {
  const nav = useNavigate();
  const [lv, setLv] = useState(0);
  const [show3d, setShow3d] = useState(false);
  const s = useSavers(card, ctx);
  const est = card.estimate;
  const plan = card.plan;
  const saveD = () => s.saveDesign(plan, card.title, card.request, card.spec_level, card.state);
  return (
    <div className="space-y-3">
      <div>
        <div className="text-[15px] font-bold text-navy-ink">{card.title}</div>
        <div className="text-[13px] text-slate-500">{card.subtitle}</div>
      </div>
      <div className="grid gap-4 md:grid-cols-2">
        <div className="min-w-0 rounded-xl border border-line bg-slate-50/50 p-2">
          {plan.levels.length > 1 && (
            <div className="mb-2 flex flex-wrap gap-1.5">
              {plan.levels.map((l, i) => (
                <button key={i} onClick={() => setLv(i)} className={`rounded-md px-2.5 py-1 text-xs font-semibold ${lv === i ? "bg-brand-600 text-white" : "bg-white text-navy-ink ring-1 ring-line"}`}>{l.name}</button>
              ))}
            </div>
          )}
          <PlanSvg plan={plan} level={lv} className="max-h-[420px]" />
        </div>
        <div className="min-w-0 space-y-3">
          <div className="rounded-xl border border-line p-3">
            <div className="mb-1.5 text-[13px] font-bold text-navy-ink">Key Features</div>
            <ul className="space-y-1">
              {card.features.map((f) => <li key={f} className="flex items-start gap-2 text-[13px] text-slate-700"><CircleCheck size={15} className="mt-0.5 shrink-0 text-emerald-600" />{f}</li>)}
            </ul>
          </div>
          {est && (
            <div className="rounded-xl border border-line p-3">
              <MaterialTable rows={est.materials} note="Estimated from this layout with standard specifications. Actual quantities vary with the final structural design, materials and site conditions." />
              <div className="mt-2 flex flex-wrap items-baseline justify-between gap-2 rounded-lg bg-brand-50 px-3 py-2">
                <span className="text-xs font-semibold text-slate-600">Estimated cost ({est.spec_level}, {est.rates_state} rates)</span>
                <span className="text-[15px] font-bold text-navy-ink">{lakhs(est.totals.grand_total)} <span className="text-xs font-medium text-slate-500">· {rupees(est.totals.cost_per_sqft)}/sq ft</span></span>
              </div>
            </div>
          )}
        </div>
      </div>
      {(card.notes?.length > 0 || card.warnings?.length > 0) && (
        <div className="rounded-lg bg-amber-50 px-3 py-2 text-xs text-amber-800">
          {[...(card.notes || []), ...(card.warnings || [])].map((n) => <div key={n}>• {n}</div>)}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        <ActBtn icon={FileText} label="Download Plan (PDF)" tone="text-red-600" busy={s.busy === "pdf"} onClick={() => s.run("pdf", async () => {
          const id = await saveD(); if (id) await downloadFile(`/api/designs/${id}/pdf`, `${ctx.code || "Nexora"}_AI_Plan.pdf`);
        })} />
        <ActBtn icon={Box} label="View 3D Model" onClick={() => setShow3d(true)} />
        {est && <ActBtn icon={FileSpreadsheet} label="Generate BOQ (Excel)" tone="text-emerald-700" busy={s.busy === "boq"} onClick={() => s.run("boq", async () => {
          const id = await s.saveEstimate(est.inputs, est.state, `AI – ${card.title}`); if (id) await downloadFile(`/api/estimates/${id}/excel`, `${ctx.code || "Nexora"}_AI_BOQ.xlsx`);
        })} />}
        <ActBtn icon={Pencil} label="Modify Plan" busy={s.busy === "edit"} onClick={() => s.run("edit", async () => {
          const id = await saveD(); if (id) nav(`/design?tab=editor&design=${id}`);
        })} />
        <ActBtn icon={Compass} label="Check Vastu" onClick={() => ctx.send({ form: { tool: "vastu", label: "Check Vastu for this plan" } })} />
        {s.links.design_id ? <Badge color="green">Saved as design</Badge> : null}
      </div>
      <Modal open={show3d} onClose={() => setShow3d(false)} title={`3D – ${card.title}`} wide="xl">
        <div className="h-[60vh] min-h-[320px]"><Plan3D plan={plan} /></div>
      </Modal>
    </div>
  );
}

// ---------------------------------------------------------------- estimate
export function EstimateCard({ card, ctx }: { card: EstimateCardT; ctx: CardCtx }) {
  const s = useSavers(card, ctx);
  const [more, setMore] = useState(false);
  const t = card.totals;
  const max = Math.max(...card.breakdown.map((b) => b.amount), 1);
  const save = () => s.saveEstimate(card.inputs, card.state, card.title);
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <div className="text-[15px] font-bold text-navy-ink">{card.title}</div>
          <div className="text-xs text-slate-500">{card.spec_level} specification · {card.rates_state} rates · about {t.duration_months} months</div>
        </div>
        <div className="text-right">
          <div className="text-2xl font-bold text-navy-ink">{lakhs(t.grand_total)}</div>
          <div className="text-xs text-slate-500">{rupees(t.cost_per_sqft)}/sq ft · {num(t.builtup_sqft, 0)} sq ft</div>
        </div>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        <MaterialTable rows={card.materials} />
        <div>
          <div className="mb-1.5 text-[13px] font-bold text-navy-ink">Cost breakdown</div>
          <div className="space-y-1.5">
            {card.breakdown.map((b) => (
              <div key={b.group} className="text-xs">
                <div className="flex justify-between"><span className="text-slate-600">{b.group}</span><span className="font-semibold">₹{inr(b.amount)} <span className="text-slate-400">({b.pct}%)</span></span></div>
                <div className="mt-0.5 h-1.5 rounded-full bg-slate-100"><div className="h-1.5 rounded-full bg-brand-600" style={{ width: `${(100 * b.amount) / max}%` }} /></div>
              </div>
            ))}
          </div>
        </div>
      </div>
      {(card.warnings.length > 0 || card.assumptions.length > 0) && (
        <div>
          <button className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600" onClick={() => setMore(!more)}>
            {more ? <ChevronDown size={14} /> : <ChevronRight size={14} />}Assumptions ({card.warnings.length + card.assumptions.length})
          </button>
          {more && <ul className="mt-1 space-y-0.5 text-xs text-slate-600">{[...card.warnings, ...card.assumptions].map((a) => <li key={a}>• {a}</li>)}</ul>}
        </div>
      )}
      <div className="flex flex-wrap gap-2">
        <ActBtn icon={FileSpreadsheet} label="BOQ (Excel)" tone="text-emerald-700" busy={s.busy === "x"} onClick={() => s.run("x", async () => {
          const id = await save(); if (id) await downloadFile(`/api/estimates/${id}/excel`, `${ctx.code || "Nexora"}_AI_BOQ.xlsx`);
        })} />
        <ActBtn icon={Download} label="Estimate (PDF)" tone="text-red-600" busy={s.busy === "p"} onClick={() => s.run("p", async () => {
          const id = await save(); if (id) await downloadFile(`/api/estimates/${id}/pdf`, `${ctx.code || "Nexora"}_AI_Estimate.pdf`);
        })} />
        {(["basic", "standard", "premium"] as const).filter((x) => x !== card.spec_level).map((x) => (
          <ActBtn key={x} icon={Layers} label={`${x[0].toUpperCase() + x.slice(1)} spec`} onClick={() => ctx.send({ form: { tool: "estimate", label: `Estimate with ${x} specification`, answers: specAnswers(card, x) } })} />
        ))}
        {s.links.estimate_id ? <Badge color="green">Saved as estimate</Badge> : null}
      </div>
    </div>
  );
}

function specAnswers(card: EstimateCardT, spec: string) {
  const i = card.inputs || {};
  const areas: number[] = i.floor_areas_sqft || [];
  return { builtup_sqft: areas[0] || card.totals.builtup_sqft, area_basis: "per_floor", floors: areas.length || 1,
    bedrooms: i.bedrooms, toilets: i.toilets, spec_level: spec };
}

// ---------------------------------------------------------------- questions (forms instead of guessing)
export function QuestionsCard({ card, ctx }: { card: Extract<Card, { type: "questions" }>; ctx: CardCtx }) {
  const init = Object.fromEntries((card.fields || []).map((f) => [f.key, f.value ?? (f.type === "select" && f.key === "spec_level" ? "standard" : "")]));
  const [vals, setVals] = useState<Record<string, any>>(init);
  const [unit, setUnit] = useState(card.unit || "ft");
  const hasLen = (card.fields || []).some((f) => f.length);
  const submit = () => {
    const clean = Object.fromEntries(Object.entries(vals).filter(([, v]) => v !== "" && v != null).map(([k, v]) => [k, isNaN(Number(v)) || v === "" ? v : Number(v)]));
    if (card.tool === "calc") ctx.send({ form: { tool: "calc", kind: card.kind, params: { ...clean, unit }, label: "Calculation details" } });
    else ctx.send({ form: { tool: card.tool, answers: clean, label: "Answered: " + Object.entries(clean).map(([k, v]) => `${labelOf(card.fields, k)} ${v}`).join(", ") } });
  };
  return (
    <div className="space-y-3">
      <ol className="list-decimal space-y-1 pl-5 text-[13.5px] text-slate-700 marker:font-bold marker:text-brand-600">
        {card.questions.map((q) => <li key={q}>{q}</li>)}
      </ol>
      {card.understood && card.understood.length > 0 && (
        <div className="flex flex-wrap gap-1.5">{card.understood.map((u) => <span key={u} className="rounded-md bg-emerald-50 px-2 py-0.5 text-[11px] font-semibold text-emerald-700">✓ {u}</span>)}</div>
      )}
      {card.options && card.options.length > 0 && (
        <div className="grid gap-2 sm:grid-cols-3">
          {card.options.map((o) => (
            <button key={o.label} disabled={!ctx.active} onClick={() => ctx.send({ form: { tool: "plan", requirements: o.requirements, label: `Use option: ${o.label}` } })}
              className="rounded-xl border border-line bg-white p-3 text-left shadow-card transition hover:border-brand-600 disabled:opacity-60">
              <div className="text-[13px] font-bold text-navy-ink">{o.label}</div>
              {o.notes.slice(0, 2).map((n) => <div key={n} className="mt-1 text-[11px] leading-snug text-slate-500">{n}</div>)}
            </button>
          ))}
        </div>
      )}
      {card.fields && card.fields.length > 0 && ctx.active && (
        <div className="rounded-xl border border-brand-100 bg-brand-50/40 p-3">
          <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-3">
            {card.fields.map((f) => <FieldInput key={f.key} f={f} value={vals[f.key]} onChange={(v) => setVals({ ...vals, [f.key]: v })} unit={f.length ? unit : ""} />)}
            {hasLen && (
              <label className="text-xs"><span className="label">Length unit</span>
                <select className="input" value={unit} onChange={(e) => setUnit(e.target.value)}><option value="ft">feet</option><option value="m">metres</option></select>
              </label>
            )}
          </div>
          <div className="mt-3 flex justify-end"><button className="btn-primary btn-sm" onClick={submit}><Send size={14} />Continue</button></div>
        </div>
      )}
    </div>
  );
}

const labelOf = (fields: Field[], k: string) => (fields.find((f) => f.key === k)?.label || k).replace(/\s*\(.*\)/, "");

function FieldInput({ f, value, onChange, unit }: { f: Field; value: any; onChange: (v: any) => void; unit: string }) {
  return (
    <label className="text-xs">
      <span className="label">{f.label}{unit ? ` (${unit})` : ""}</span>
      {f.type === "select" ? (
        <select className="input" value={value ?? ""} onChange={(e) => onChange(e.target.value)}>
          <option value="">—</option>
          {(f.options || []).map((o, i) => <option key={o} value={o}>{f.labels?.[i] || o}</option>)}
        </select>
      ) : (
        <input className="input" inputMode="decimal" value={value ?? ""} onChange={(e) => onChange(e.target.value.replace(/[^0-9.]/g, ""))} />
      )}
    </label>
  );
}

// ---------------------------------------------------------------- calculator result
export function CalcCard({ card }: { card: CalcCardT }) {
  const [steps, setSteps] = useState(false);
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-[15px] font-bold text-navy-ink"><Calculator size={17} className="text-brand-600" />{card.title}</div>
      {card.inputs.length > 0 && <div className="flex flex-wrap gap-1.5">{card.inputs.map(([a, b]) => <span key={a} className="rounded-md bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600"><b>{a}:</b> {b}</span>)}</div>}
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        {card.results.map((r) => (
          <div key={r.label} className="rounded-xl border border-line bg-white p-3">
            <div className="text-[11px] font-semibold text-slate-500">{r.label}</div>
            <div className="text-lg font-bold text-navy-ink">{typeof r.value === "number" ? num(r.value, 2) : r.value}</div>
            <div className="text-[11px] text-slate-500">{r.unit}</div>
          </div>
        ))}
      </div>
      <button className="inline-flex items-center gap-1 text-xs font-semibold text-brand-600" onClick={() => setSteps(!steps)}>
        {steps ? <ChevronDown size={14} /> : <ChevronRight size={14} />}How it is calculated
      </button>
      {steps && (
        <div className="rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
          <ol className="list-decimal space-y-0.5 pl-4">{card.steps.map((s) => <li key={s}>{s}</li>)}</ol>
          {card.assumptions.length > 0 && <div className="mt-2 text-slate-500">{card.assumptions.map((a) => <div key={a}>• {a}</div>)}</div>}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- vastu
export function VastuCard({ card }: { card: Extract<Card, { type: "vastu" }> }) {
  const nav = useNavigate();
  const s = card.summary;
  const pct = Math.round((100 * (s.matched + s.partly * 0.5)) / Math.max(1, s.total));
  const tone: Record<string, string> = { Excellent: "green", Good: "blue", "Needs Attention": "amber" };
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-[15px] font-bold text-navy-ink"><Compass size={17} className="text-violet-600" />{card.title}</div>
      <div className="flex flex-wrap items-center gap-4">
        <div className="text-3xl font-bold text-navy-ink">{s.matched}<span className="text-base text-slate-400">/{s.total}</span></div>
        <div className="min-w-[180px] flex-1">
          <div className="text-xs font-semibold text-slate-600">{s.label}</div>
          <div className="mt-1 h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-violet-600" style={{ width: `${pct}%` }} /></div>
          <div className="mt-1 text-[11px] text-slate-500">{s.matched} matched · {s.partly} partly · {s.not_matched} not matched</div>
        </div>
      </div>
      {card.overview && (
        <div className="flex flex-wrap gap-1.5">
          {Object.entries(card.overview).map(([side, o]: any) => <Badge key={side} color={tone[o.status] || "gray"}>{side}: {o.status}</Badge>)}
        </div>
      )}
      {card.suggestions?.length > 0 && <ul className="space-y-1 text-[13px] text-slate-700">{card.suggestions.slice(0, 5).map((x) => <li key={x} className="flex gap-2"><Lightbulb size={14} className="mt-0.5 shrink-0 text-amber-500" />{x}</li>)}</ul>}
      <ActBtn icon={ExternalLink} label="Open Vastu page (improved plan, PDF)" onClick={() => nav(card.design_id ? `/vastu?design=${card.design_id}` : "/vastu")} />
    </div>
  );
}

// ---------------------------------------------------------------- site
export function SiteCard({ card }: { card: Extract<Card, { type: "site" }> }) {
  const nav = useNavigate();
  const p = card.progress;
  const v = p.variance_days || 0;
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-[15px] font-bold text-navy-ink"><HardHat size={17} className="text-amber-500" />{card.title}</div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[["Progress", `${Math.round(p.overall)}%`, p.planned != null ? `planned ${Math.round(p.planned)}%` : "no schedule"],
          ["Schedule", v >= 0 ? `${v} days ahead` : `${-v} days behind`, p.health === "delayed" ? "Delayed" : "On track"],
          ["On site today", `${card.cards.workers}`, `${card.cards.activities} activities`],
          ["Open issues", `${card.cards.issues}`, `material ${card.cards.material_pct}% received`]].map(([a, b, c]) => (
          <div key={a} className="rounded-xl border border-line p-3"><div className="text-[11px] font-semibold text-slate-500">{a}</div><div className="text-lg font-bold text-navy-ink">{b}</div><div className="text-[11px] text-slate-500">{c}</div></div>
        ))}
      </div>
      {card.insights.length > 0 && <ul className="space-y-1 text-[13px]">{card.insights.map((i) => <li key={i.text} className={`flex gap-2 ${i.kind === "risk" ? "text-red-700" : "text-slate-700"}`}>{i.kind === "risk" ? <TriangleAlert size={14} className="mt-0.5 shrink-0" /> : <Lightbulb size={14} className="mt-0.5 shrink-0 text-amber-500" />}{i.text}</li>)}</ul>}
      <ActBtn icon={ExternalLink} label="Open Site page" onClick={() => nav("/site")} />
    </div>
  );
}

// ---------------------------------------------------------------- drawing analysis
export function DrawingCard({ card, ctx }: { card: Extract<Card, { type: "drawing" }>; ctx: CardCtx }) {
  const nav = useNavigate();
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-[15px] font-bold text-navy-ink"><Ruler size={17} className="text-violet-600" />{card.file_name} <Badge color="purple">{card.method}</Badge></div>
      <div className="max-h-72 overflow-auto rounded-lg border border-line">
        <table className="w-full">
          <thead><tr><th className="table-th">Room</th><th className="table-th text-right">Size (ft)</th><th className="table-th text-right">Area (sq ft)</th></tr></thead>
          <tbody>
            {card.rooms.map((r, i) => (
              <tr key={i}><td className="table-td py-1.5">{r.name}</td><td className="table-td py-1.5 text-right">{num(r.w, 2)} × {num(r.d, 2)}</td><td className="table-td py-1.5 text-right">{num(r.w * r.d, 0)}</td></tr>
            ))}
          </tbody>
        </table>
      </div>
      {card.questions.length > 0 && <ul className="space-y-0.5 text-xs text-amber-800">{card.questions.map((q) => <li key={q}>• {q}</li>)}</ul>}
      <div className="flex flex-wrap gap-2">
        <ActBtn icon={ExternalLink} label="Confirm & save in Design" onClick={() => nav(`/design?tab=upload&analysis=${card.analysis_id}`)} />
        <ActBtn icon={Send} label="Explain this drawing" onClick={() => ctx.send({ text: "Explain this drawing – are the room sizes good?" })} />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- setbacks
export function SetbackCard({ card }: { card: Extract<Card, { type: "setback" }> }) {
  const rows: [string, string][] = [["front", "Front (road side)"], ["rear", "Rear"], ["left", "Left side"], ["right", "Right side"]];
  return (
    <div className="space-y-3">
      <div className="text-[15px] font-bold text-navy-ink">Tamil Nadu setbacks – {num(card.plot.w)} × {num(card.plot.d)} ft plot</div>
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="overflow-hidden rounded-lg border border-line">
          <table className="w-full"><tbody>
            {rows.map(([k, l]) => <tr key={k}><td className="table-td py-1.5">{l}</td><td className="table-td py-1.5 text-right font-semibold">{num(card.ft[k])} ft</td><td className="table-td py-1.5 text-right text-slate-500">{num(card.m[k])} m</td></tr>)}
          </tbody></table>
        </div>
        <div className="rounded-xl bg-brand-50 p-3 text-sm">
          <div className="text-xs font-semibold text-slate-500">Buildable per floor</div>
          <div className="text-xl font-bold text-navy-ink">{num(card.buildable.w)} × {num(card.buildable.d)} ft</div>
          <div className="text-xs text-slate-500">{num(card.buildable.w * card.buildable.d, 0)} sq ft · {card.coverage_pct}% of plot · road {num(card.road_width_m, 1)} m</div>
          <div className="mt-1 text-[11px] text-slate-500">{card.rule}</div>
        </div>
      </div>
      {card.notes?.length > 0 && <ul className="text-xs text-slate-600">{card.notes.map((n) => <li key={n}>• {n}</li>)}</ul>}
    </div>
  );
}

// ---------------------------------------------------------------- sources
export function Sources({ sources, open, setOpen }: { sources: Source[]; open: number | null; setOpen: (n: number | null) => void }) {
  const [all, setAll] = useState(false);
  if (!sources.length) return null;
  return (
    <div className="rounded-lg border border-line bg-slate-50/60 px-3 py-2">
      <button className="flex w-full items-center gap-1 text-xs font-bold text-navy-ink" onClick={() => setAll(!all)}>
        {all ? <ChevronDown size={14} /> : <ChevronRight size={14} />}Sources ({sources.length})
      </button>
      {(all || open != null) && (
        <ol className="mt-1.5 space-y-1.5">
          {sources.map((s) => (
            <li key={s.n} className={`rounded-md p-1.5 text-xs ${open === s.n ? "bg-white ring-1 ring-brand-100" : ""}`}>
              <button className="flex w-full items-start gap-2 text-left" onClick={() => setOpen(open === s.n ? null : s.n)}>
                <span className="mt-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded bg-brand-600 px-1 text-[10px] font-bold text-white">{s.n}</span>
                <span className="min-w-0 flex-1">
                  <span className="font-semibold text-navy-ink">{s.title}</span>
                  <span className="text-slate-500"> · {s.kind === "doc" ? `your document${s.page ? `, page ${s.page}` : ""}` : s.ref}</span>
                </span>
              </button>
              {open === s.n && (
                <div className="mt-1 pl-6 text-[12px] leading-relaxed text-slate-600">
                  {s.snippet}
                  {s.kind === "doc" && s.file_id && <button className="link ml-2 text-xs" onClick={() => downloadFile(`/api/files/${s.file_id}/download`, s.title).catch((e) => toast(e.message, "err"))}>Open file</button>}
                </div>
              )}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

export function CardView({ card, ctx }: { card: Card; ctx: CardCtx }) {
  switch (card.type) {
    case "plan": return <PlanCard card={card} ctx={ctx} />;
    case "estimate": return <EstimateCard card={card} ctx={ctx} />;
    case "questions": return <QuestionsCard card={card} ctx={ctx} />;
    case "calc": return <CalcCard card={card} />;
    case "vastu": return <VastuCard card={card} />;
    case "site": return <SiteCard card={card} />;
    case "drawing": return <DrawingCard card={card} ctx={ctx} />;
    case "setback": return <SetbackCard card={card} />;
    case "photo": return <PhotoResultView r={(card as any).result} />;
    default: return null;
  }
}
