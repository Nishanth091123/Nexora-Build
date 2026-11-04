/** 1.10 – Drawing sheets: site plan, floor plans, front elevation, section A-A (SVG previews from the server),
 *  door & window schedule (sizes editable per type) and area details. Downloads: A3 PDF set + DXF. */
import { useEffect, useRef, useState } from "react";
import { Download, FileText, Ruler, Save } from "lucide-react";
import { Card, Empty, toast } from "../ui";
import { api, downloadFile, num } from "../../lib/api";
import type { Plan } from "../../lib/plan";

type Sched = { mark: string; type: string; label: string; w_ft: number; h_ft: number; size: string; sill_ft: number; material: string; per_level: Record<string, number>; count: number; rooms: string };
type Row = { w_ft: string; h_ft: string; material: string };
type Preview = { schedule: Sched[]; area: any; svgs: Record<string, string>; levels: string[]; warnings: string[] };
const TYPE_LABEL: Record<string, string> = { main_door: "Main door", door: "Room door", pooja_door: "Pooja door", toilet_door: "Toilet door", opening: "Opening", window: "Window (all)", vent: "Ventilator" };

export default function DrawingSheets({ pid, plan, saved, dirty, code, onSpecs }: {
  pid: number; plan: Plan; saved: { id: number; version: number } | null; dirty: boolean; code: string;
  onSpecs: (specs: Record<string, { w_ft?: number; h_ft?: number; material?: string }>) => void;
}) {
  const [pv, setPv] = useState<Preview | null>(null);
  const [sheet, setSheet] = useState("elevation");
  const [edit, setEdit] = useState<Record<string, { w_ft: string; h_ft: string; material: string }>>({});
  const timer = useRef<number | null>(null);

  useEffect(() => {
    if (timer.current) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      api<Preview>(`/api/projects/${pid}/design/sheets-preview`, { body: { plan } }).then(setPv).catch((e) => toast(e.message, "err"));
    }, 400);
  }, [pid, JSON.stringify(plan.levels.map((l) => l.rooms)), JSON.stringify(plan.opening_specs || {})]);

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
  const dl = async (kind: "pdf" | "dxf") => {
    if (!saved || dirty) return toast("Save the design first (Save button) – the drawing set is made from a saved version", "err");
    try { await downloadFile(`/api/designs/${saved.id}/sheets.${kind}`, `${code}_Drawing_Set_v${saved.version}.${kind}`); }
    catch (e: any) { toast(e.message, "err"); }
  };

  if (!pv) return <Card><Empty text="Preparing drawing sheets..." /></Card>;
  const sheets: [string, string][] = [["site", "A-02 Site Plan"], ...pv.levels.map((l, i) => [`plan_${i}`, `A-${String(3 + i).padStart(2, "0")} ${l} Plan`] as [string, string]),
    ["elevation", `A-${String(3 + pv.levels.length).padStart(2, "0")} Front Elevation`], ["section", `A-${String(4 + pv.levels.length).padStart(2, "0")} Section A-A`]];
  const a = pv.area;
  return (
    <div className="space-y-4">
      <Card title="Drawing Sheets (auto generated)" icon={<FileText size={20} />}
        action={<div className="flex gap-2">
          <button className="btn-primary btn-sm" onClick={() => dl("pdf")}><Download size={14} />Drawing Set PDF (A3)</button>
          <button className="btn-outline btn-sm" onClick={() => dl("dxf")}><Download size={14} />DXF (AutoCAD)</button>
          <button className="btn-outline btn-sm" title="Drawing set + latest saved estimate in ONE PDF" onClick={() => {
            if (!saved || dirty) return toast("Save the design first (Save button)", "err");
            downloadFile(`/api/projects/${pid}/project-pdf?design_id=${saved.id}`, `${code}_Project_Drawings_and_Estimate.pdf`).catch((e) => toast(e.message, "err"));
          }}><Download size={14} />Complete PDF (drawings + estimate)</button>
        </div>}>
        <div className="mb-3 flex flex-wrap gap-1.5">
          {sheets.map(([k, l]) => <button key={k} onClick={() => setSheet(k)} className={`rounded-md px-3 py-1.5 text-xs font-semibold ${sheet === k ? "bg-brand-600 text-white" : "bg-brand-50 text-navy-ink"}`}>{l}</button>)}
        </div>
        <div className="overflow-auto rounded-lg border border-line bg-white p-2">
          <div className="mx-auto max-w-4xl" dangerouslySetInnerHTML={{ __html: pv.svgs[sheet] || "" }} />
        </div>
        <p className="mt-2 text-xs text-slate-500">The PDF set also has A-01 Title sheet (drawing list, area statement, FSI, coverage) and the Door &amp; Window Schedule sheet, with your firm's title block on every sheet. Signature boxes are left empty to sign by hand.</p>
      </Card>

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
