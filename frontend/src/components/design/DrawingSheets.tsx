/** 1.10 – Drawing sheets: site plan, floor plans, front elevation, section A-A (SVG previews from the server),
 *  door & window schedule (sizes editable per type) and area details. Downloads: A3 PDF set + DXF. */
import { useEffect, useRef, useState } from "react";
import { Download, FileText, Ruler, Save } from "lucide-react";
import { Card, Empty, toast } from "../ui";
import { api, downloadFile, num } from "../../lib/api";
import { exportPlan, savePng, saveSvg } from "../../lib/designExport";
import type { Plan } from "../../lib/plan";

type Sched = { mark: string; type: string; label: string; w_ft: number; h_ft: number; size: string; sill_ft: number; material: string; per_level: Record<string, number>; count: number; rooms: string };
type Row = { w_ft: string; h_ft: string; material: string };
type Preview = { addon_questions?: string[]; schedule: Sched[]; area: any; svgs: Record<string, string>; svgs_cad?: Record<string, string>; levels: string[]; warnings: string[] };
const TYPE_LABEL: Record<string, string> = { main_door: "Main door", door: "Room door", pooja_door: "Pooja door", toilet_door: "Toilet door", opening: "Opening", window: "Window (all)", vent: "Ventilator" };

const DIRS = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"];
type KP = { on: boolean; place: string; taluk: string; district: string; survey_no: string; plot_no: string; ward: string; road_name: string;
  roads: { name: string; dir: string }[]; landmarks: { name: string; dir: string; dist_m: string }[] };
type CA = { on: boolean; sbc_kn_m2: string; seismic_zone: string; foundation_depth_m: string; fck: string; fy: string };

/** 1.27.9 – optional drawings, each switched on only when the client asks: key plan / location plan and column & footing layout + calculation */
function AddonsCard({ plan, questions, onApply }: { plan: Plan; questions: string[]; onApply: (a: { keyplan: any; column_addon: any }) => void }) {
  const k0: any = plan.keyplan || {}, c0: any = plan.column_addon || {};
  const [kp, setKp] = useState<KP>({ on: !!k0.on, place: k0.place || "", taluk: k0.taluk || "", district: k0.district || "", survey_no: k0.survey_no || "", plot_no: k0.plot_no || "",
    ward: k0.ward || "", road_name: k0.road_name || "", roads: k0.roads || [], landmarks: (k0.landmarks || []).map((m: any) => ({ ...m, dist_m: m.dist_m == null ? "" : String(m.dist_m) })) });
  const [ca, setCa] = useState<CA>({ on: !!c0.on, sbc_kn_m2: c0.sbc_kn_m2 != null ? String(c0.sbc_kn_m2) : "", seismic_zone: c0.seismic_zone || "",
    foundation_depth_m: c0.foundation_depth_m != null ? String(c0.foundation_depth_m) : "", fck: c0.fck ? String(c0.fck) : "", fy: c0.fy ? String(c0.fy) : "" });
  const apply = () => {
    const keyplan = kp.on ? { ...kp, landmarks: kp.landmarks.map((m) => ({ ...m, dist_m: m.dist_m === "" ? null : Number(m.dist_m) })) } : null;
    const column_addon = ca.on ? Object.fromEntries(Object.entries(ca).filter(([, v]) => v !== "" && v !== undefined).map(([k, v]) => [k, k === "on" || k === "seismic_zone" ? v : Number(v)])) : null;
    onApply({ keyplan, column_addon });
    toast("Add-on drawings updated – they are in the drawing set only while switched on. Save the design to keep them.");
  };
  const Sw = ({ on, set, label }: { on: boolean; set: (v: boolean) => void; label: string }) => (
    <label className="flex cursor-pointer items-center gap-2 text-sm font-semibold text-navy-ink"><input type="checkbox" checked={on} onChange={(e) => set(e.target.checked)} />{label}</label>);
  const f = (k: keyof KP, label: string) => (
    <label className="text-xs text-slate-600">{label}<input className="input mt-0.5 py-1 text-xs" value={(kp as any)[k]} onChange={(e) => setKp({ ...kp, [k]: e.target.value })} /></label>);
  return (
    <Card title="Optional drawings (add only if the client asks)" icon={<FileText size={20} />}
      action={<button className="btn-primary btn-sm" onClick={apply}><Save size={14} />Apply</button>}>
      <div className="grid gap-4 xl:grid-cols-2">
        <div className="rounded-lg border border-line p-3">
          <Sw on={kp.on} set={(v) => setKp({ ...kp, on: v })} label="Key plan / Location plan" />
          <p className="mt-1 text-[11px] text-slate-500">Drawn only from what you type here (direction + distance as you enter them). It is a sketch, not to scale – nothing is guessed.</p>
          {kp.on && <div className="mt-2 space-y-2">
            <div className="grid grid-cols-2 gap-2">{f("place", "Place / village")}{f("taluk", "Taluk")}{f("district", "District")}{f("survey_no", "Survey no.")}{f("plot_no", "Plot no.")}{f("ward", "Ward / block")}</div>
            {f("road_name", "Name of the road in front of the plot")}
            <div className="text-xs font-semibold text-navy-ink">Other roads <button className="btn-ghost btn-sm" onClick={() => setKp({ ...kp, roads: [...kp.roads, { name: "", dir: "E" }].slice(0, 6) })}>+ add</button></div>
            {kp.roads.map((r, i) => <div key={i} className="grid grid-cols-[2fr_1fr_auto] gap-1.5">
              <input className="input py-1 text-xs" placeholder="Road name" value={r.name} onChange={(e) => setKp({ ...kp, roads: kp.roads.map((q, j) => j === i ? { ...q, name: e.target.value } : q) })} />
              <select className="input py-1 text-xs" value={r.dir} onChange={(e) => setKp({ ...kp, roads: kp.roads.map((q, j) => j === i ? { ...q, dir: e.target.value } : q) })}>{DIRS.map((d) => <option key={d}>{d}</option>)}</select>
              <button className="btn-ghost btn-sm" onClick={() => setKp({ ...kp, roads: kp.roads.filter((_, j) => j !== i) })}>✕</button></div>)}
            <div className="text-xs font-semibold text-navy-ink">Landmarks <button className="btn-ghost btn-sm" onClick={() => setKp({ ...kp, landmarks: [...kp.landmarks, { name: "", dir: "N", dist_m: "" }].slice(0, 12) })}>+ add</button></div>
            {kp.landmarks.map((m, i) => <div key={i} className="grid grid-cols-[2fr_1fr_1fr_auto] gap-1.5">
              <input className="input py-1 text-xs" placeholder="Landmark (school, temple…)" value={m.name} onChange={(e) => setKp({ ...kp, landmarks: kp.landmarks.map((q, j) => j === i ? { ...q, name: e.target.value } : q) })} />
              <select className="input py-1 text-xs" value={m.dir} onChange={(e) => setKp({ ...kp, landmarks: kp.landmarks.map((q, j) => j === i ? { ...q, dir: e.target.value } : q) })}>{DIRS.map((d) => <option key={d}>{d}</option>)}</select>
              <input className="input py-1 text-xs" type="number" min="0" placeholder="metres" value={m.dist_m} onChange={(e) => setKp({ ...kp, landmarks: kp.landmarks.map((q, j) => j === i ? { ...q, dist_m: e.target.value } : q) })} />
              <button className="btn-ghost btn-sm" onClick={() => setKp({ ...kp, landmarks: kp.landmarks.filter((_, j) => j !== i) })}>✕</button></div>)}
          </div>}
        </div>
        <div className="rounded-lg border border-line p-3">
          <Sw on={ca.on} set={(v) => setCa({ ...ca, on: v })} label="Column position + footing layout + design calculation" />
          <p className="mt-1 text-[11px] text-slate-500">Adds 3 sheets (column layout, footing layout, calculation). The soil bearing capacity and seismic zone are NOT assumed – enter them from the soil report / local code. The engineer's signature box stays blank.</p>
          {ca.on && <div className="mt-2 grid grid-cols-2 gap-2">
            <label className="text-xs text-slate-600">Safe bearing capacity (kN/m²) *<input className="input mt-0.5 py-1 text-xs" type="number" min="40" max="600" value={ca.sbc_kn_m2} onChange={(e) => setCa({ ...ca, sbc_kn_m2: e.target.value })} /></label>
            <label className="text-xs text-slate-600">Seismic zone *<select className="input mt-0.5 py-1 text-xs" value={ca.seismic_zone} onChange={(e) => setCa({ ...ca, seismic_zone: e.target.value })}><option value="">– select –</option>{["II", "III", "IV", "V"].map((z) => <option key={z}>{z}</option>)}</select></label>
            <label className="text-xs text-slate-600">Foundation depth (m)<input className="input mt-0.5 py-1 text-xs" type="number" step="0.1" min="0.9" max="4" placeholder="1.5" value={ca.foundation_depth_m} onChange={(e) => setCa({ ...ca, foundation_depth_m: e.target.value })} /></label>
            <label className="text-xs text-slate-600">Concrete / steel<span className="flex gap-1"><select className="input mt-0.5 py-1 text-xs" value={ca.fck} onChange={(e) => setCa({ ...ca, fck: e.target.value })}><option value="">M20</option><option>25</option><option>30</option></select><select className="input mt-0.5 py-1 text-xs" value={ca.fy} onChange={(e) => setCa({ ...ca, fy: e.target.value })}><option value="">Fe500</option><option>415</option><option>550</option></select></span></label>
          </div>}
          {questions.length > 0 && <ul className="mt-2 list-disc space-y-1 pl-5 text-[11px] text-amber-700">{questions.map((q) => <li key={q}>{q}</li>)}</ul>}
        </div>
      </div>
    </Card>
  );
}

export default function DrawingSheets({ pid, plan, saved, dirty, code, onSpecs, onAddons }: {
  pid: number; plan: Plan; saved: { id: number; version: number } | null; dirty: boolean; code: string;
  onSpecs: (specs: Record<string, { w_ft?: number; h_ft?: number; material?: string }>) => void;
  onAddons: (a: { keyplan: any; column_addon: any }) => void;
}) {
  const [pv, setPv] = useState<Preview | null>(null);
  const [sheet, setSheet] = useState("elevation");
  const [cad, setCad] = useState(false);
  const [edit, setEdit] = useState<Record<string, { w_ft: string; h_ft: string; material: string }>>({});
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      api<Preview>(`/api/projects/${pid}/design/sheets-preview`, { body: { plan } }).then(setPv).catch((e) => toast(e.message, "err"));
    }, 400);
  }, [pid, JSON.stringify(plan.levels.map((l) => l.rooms)), JSON.stringify(plan.opening_specs || {}), JSON.stringify(plan.keyplan || null), JSON.stringify(plan.column_addon || null), JSON.stringify(plan.ext_stair || null)]);

  useEffect(() => {  // one editable row per opening TYPE (all windows share one size row)
    const s = plan.opening_specs || {};
    const e: Record<string, { w_ft: string; h_ft: string; material: string }> = {};
    for (const r of pv?.schedule || []) {
      if (e[r.type]) continue;
      e[r.type] = { w_ft: s[r.type]?.w_ft != null ? String(s[r.type]!.w_ft) : "", h_ft: s[r.type]?.h_ft != null ? String(s[r.type]!.h_ft) : "", material: s[r.type]?.material || "" };
    }
    setEdit(e);
  }, [pv]);

  const apply = () => {
    const out: Record<string, { w_ft?: number; h_ft?: number; material?: string }> = {};
    for (const [k, v] of Object.entries(edit) as [string, Row][]) {
      const o: { w_ft?: number; h_ft?: number; material?: string } = {};
      if (v.w_ft !== "") o.w_ft = Number(v.w_ft);
      if (v.h_ft !== "") o.h_ft = Number(v.h_ft);
      if (v.material.trim()) o.material = v.material.trim();
      if (Object.keys(o).length) out[k] = o;
    }
    onSpecs(out);
    toast("Sizes applied – plan, quantities and estimate updated. Save the design to keep them.");
  };
  // 1.13: downloads are made from the plan on the screen – no need to save first
  const tag = saved && !dirty ? `v${saved.version}` : "draft";
  const dl = async (kind: "pdf" | "dxf" | "cad", page = "") => {
    const nm = page ? (sheets.find((x) => x[0] === page)?.[1] || page).replace(/[^A-Za-z0-9]+/g, "_") : "Drawing_Set";
    try {
      if (kind === "dxf") await exportPlan(pid, plan, "sheets_dxf", `${code}_Drawing_Set_${tag}.dxf`, { version: saved && !dirty ? saved.version : null });
      else await exportPlan(pid, plan, "sheets_pdf", `${code}_${nm}_${tag}${kind === "cad" ? "_CAD" : ""}.pdf`,
        { style: kind === "cad" ? "cad" : "paper", page, version: saved && !dirty ? saved.version : null });
    } catch (e: any) { toast(e.message, "err"); }
  };

  if (!pv) return <Card><Empty text="Preparing drawing sheets..." /></Card>;
  const sheets: [string, string][] = [["site", "A-02 Site Plan"], ...pv.levels.map((l, i) => [`plan_${i}`, `A-${String(3 + i).padStart(2, "0")} ${l} Plan`] as [string, string]),
    ["elevation", `A-${String(3 + pv.levels.length).padStart(2, "0")} Front Elevation`], ["section", `A-${String(4 + pv.levels.length).padStart(2, "0")} Section A-A`],
    ...(pv.svgs.roof ? [["roof", `A-${String(5 + pv.levels.length).padStart(2, "0")} Roof Plan (sheet roof)`], ["truss", `A-${String(6 + pv.levels.length).padStart(2, "0")} Truss & Purlin Detail`]] as [string, string][] : []),
    ...(pv.svgs.keyplan ? [["keyplan", "Key Plan / Location Plan"]] as [string, string][] : []),
    ...(pv.svgs.column ? [["column", "Column Position Layout"], ["footing", "Footing Layout"]] as [string, string][] : []),
    ...(pv.svgs.stair ? [["stair", `A-${String(5 + pv.levels.length + (pv.svgs.roof ? 2 : 0)).padStart(2, "0")} Staircase Detail`]] as [string, string][] : [])];
  const a = pv.area;
  return (
    <div className="space-y-4">
      <Card title="Drawing Sheets (auto generated)" icon={<FileText size={20} />}
        action={<div className="flex gap-2">
          <button className="btn-primary btn-sm" onClick={() => dl("pdf")}><Download size={14} />Drawing Set PDF (A3)</button>
          <button className={`btn-sm ${cad ? "btn-primary" : "btn-outline"}`} onClick={() => setCad(!cad)}>{cad ? "CAD colours (black)" : "Paper colours"}</button>
          <button className="btn-outline btn-sm" onClick={() => dl("cad")}><Download size={14} />PDF (CAD black)</button>
          <button className="btn-outline btn-sm" onClick={() => dl("dxf")}><Download size={14} />DXF (AutoCAD)</button>
          <button className="btn-outline btn-sm" title="Drawing set + latest saved estimate in ONE PDF" onClick={() => {
            if (!saved || dirty) return toast("Save the design first (Save button)", "err");
            downloadFile(`/api/projects/${pid}/project-pdf?design_id=${saved.id}`, `${code}_Project_Drawings_and_Estimate.pdf`).catch((e) => toast(e.message, "err"));
          }}><Download size={14} />Complete PDF (drawings + estimate)</button>
        </div>}>
        <div className="mb-3 flex flex-wrap gap-1.5">
          {sheets.map(([k, l]) => <button key={k} onClick={() => setSheet(k)} className={`rounded-md px-3 py-1.5 text-xs font-semibold ${sheet === k ? "bg-brand-600 text-white" : "bg-brand-50 text-navy-ink"}`}>{l}</button>)}
        </div>
        <div className="mb-2 flex flex-wrap items-center gap-1.5 text-xs">
          <span className="font-semibold text-slate-500">This sheet:</span>
          <button className="btn-outline btn-sm" onClick={() => dl(cad ? "cad" : "pdf", sheet)}><Download size={13} />PDF (A3)</button>
          <button className="btn-outline btn-sm" onClick={() => savePng((cad ? pv.svgs_cad?.[sheet] : pv.svgs[sheet]) || "", `${code}_${sheet}.png`, 3000, cad ? "#000000" : "#ffffff").catch((e) => toast(e.message, "err"))}><Download size={13} />PNG</button>
          <button className="btn-outline btn-sm" onClick={() => saveSvg((cad ? pv.svgs_cad?.[sheet] : pv.svgs[sheet]) || "", `${code}_${sheet}.svg`)}><Download size={13} />SVG</button>
          <span className="flex-1" />
          <button className="btn-ghost btn-sm" onClick={() => dl("pdf", "title")}><Download size={13} />Title sheet</button>
          <button className="btn-ghost btn-sm" onClick={() => dl("pdf", "schedule")}><Download size={13} />Door &amp; window schedule</button>
          {(!saved || dirty) && <span className="text-[11px] text-amber-700">Not saved – downloads show what is on the screen (marked “draft”).</span>}
        </div>
        <div className={`overflow-auto rounded-lg border border-line p-2 ${cad ? "bg-black" : "bg-white"}`}>
          <div className="mx-auto max-w-4xl" dangerouslySetInnerHTML={{ __html: (cad ? pv.svgs_cad?.[sheet] : pv.svgs[sheet]) || "" }} />
        </div>
        <p className="mt-2 text-xs text-slate-500">The PDF set also has A-01 Title sheet (drawing list, area statement, FSI, coverage) and the Door &amp; Window Schedule sheet, with your firm's title block on every sheet. Signature boxes are left empty to sign by hand.</p>
      </Card>

      <AddonsCard key={JSON.stringify([plan.keyplan || null, plan.column_addon || null])} plan={plan} questions={pv.addon_questions || []} onApply={onAddons} />

      <div className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
        <Card title="Door & Window Schedule" icon={<Ruler size={20} />}
          action={<button className="btn-primary btn-sm" onClick={apply}><Save size={14} />Apply sizes</button>}>
          <div className="overflow-x-auto rounded-lg border border-line">
            <table className="w-full min-w-[640px] text-sm">
              <thead className="bg-slate-50 text-left text-xs text-slate-500"><tr>
                <th className="px-2 py-2">Mark</th><th className="px-2 py-2">Type</th><th className="px-2 py-2">Size (W x H)</th><th className="px-2 py-2">Sill</th>
                {pv.levels.map((l) => <th key={l} className="px-2 py-2 text-center">{l.replace(" Floor", "")}</th>)}<th className="px-2 py-2 text-center">Total</th><th className="px-2 py-2">Material</th></tr></thead>
              <tbody>
                {pv.schedule.map((s) => (
                  <tr key={s.mark} className="border-t border-line">
                    <td className="px-2 py-1.5 font-bold text-brand-700">{s.mark}</td><td className="px-2 py-1.5">{s.label}</td><td className="px-2 py-1.5">{s.size}</td>
                    <td className="px-2 py-1.5">{s.sill_ft ? `${s.sill_ft}'` : "–"}</td>
                    {pv.levels.map((l) => <td key={l} className="px-2 py-1.5 text-center">{s.per_level[l] || "–"}</td>)}
                    <td className="px-2 py-1.5 text-center font-semibold">{s.count}</td><td className="px-2 py-1.5 text-slate-600">{s.material}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div className="mt-4 text-xs font-semibold text-navy-ink">Change sizes for a type (feet; blank = automatic size)</div>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {(Object.entries(edit) as [string, Row][]).map(([k, v]) => (
              <div key={k} className="rounded-lg border border-line p-2 text-xs">
                <div className="mb-1 font-semibold">{TYPE_LABEL[k] || k}</div>
                <div className="grid grid-cols-[1fr_1fr_2fr] gap-1.5">
                  <input className="input py-1 text-xs" type="number" step="0.25" min="1.5" max="16" placeholder="Width" value={v.w_ft} onChange={(e) => setEdit({ ...edit, [k]: { ...v, w_ft: e.target.value } })} />
                  <input className="input py-1 text-xs" type="number" step="0.25" min="1" max="10" placeholder="Height" value={v.h_ft} onChange={(e) => setEdit({ ...edit, [k]: { ...v, h_ft: e.target.value } })} />
                  <input className="input py-1 text-xs" placeholder="Material (optional)" value={v.material} onChange={(e) => setEdit({ ...edit, [k]: { ...v, material: e.target.value } })} />
                </div>
              </div>
            ))}
          </div>
          {pv.warnings.length > 0 && <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-amber-700">{pv.warnings.slice(0, 6).map((w) => <li key={w}>{w}</li>)}</ul>}
        </Card>

        <Card title="Area Details" icon={<Ruler size={20} />}>
          <div className="overflow-hidden rounded-lg border border-line text-sm">
            <table className="w-full">
              <thead className="bg-slate-50 text-left text-xs text-slate-500"><tr><th className="px-2 py-2">Floor</th><th className="px-2 py-2 text-right">Built-up</th><th className="px-2 py-2 text-right">Carpet</th></tr></thead>
              <tbody>
                {a.rows.map((r: any) => <tr key={r.floor} className="border-t border-line"><td className="px-2 py-1.5">{r.floor}</td><td className="px-2 py-1.5 text-right">{num(r.builtup_sqft, 0)}</td><td className="px-2 py-1.5 text-right">{num(r.carpet_sqft, 0)}</td></tr>)}
                <tr className="border-t border-line bg-brand-50 font-bold"><td className="px-2 py-1.5">Total (sq ft)</td><td className="px-2 py-1.5 text-right">{num(a.total_builtup_sqft, 0)}</td><td className="px-2 py-1.5 text-right">{num(a.rows.reduce((s: number, r: any) => s + r.carpet_sqft, 0), 0)}</td></tr>
              </tbody>
            </table>
          </div>
          <div className="mt-3 space-y-1.5 text-sm">
            {[["Plot area", `${num(a.plot_sqft, 0)} sq ft (${a.plot_m2} m²)`], ["FSI achieved", a.fsi], ["Ground coverage", `${a.coverage_pct}%`],
              ["Open space", `${num(a.open_space_sqft, 0)} sq ft (${a.open_space_pct}%)`], ["Building height", `${a.height_m} m`]].map(([k, v]) => (
              <div key={k} className="flex justify-between"><span className="text-slate-500">{k}</span><b className="text-navy-ink">{v}</b></div>
            ))}
          </div>
          <p className="mt-2 text-[11px] text-slate-500">{a.note}</p>
        </Card>
      </div>
    </div>
  );
}
