/** 1.12 – Structural (preliminary RCC design, IS 456): inputs → columns, beams, slabs, footings, schedules,
 *  drawings (paper / CAD colours), PDF + DXF. Gravity loads only – to be checked by a structural engineer. */
import { useEffect, useState } from "react";
import { Building2, Calculator, Download, Save, TriangleAlert } from "lucide-react";
import { Badge, Card, Empty, Field, toast } from "../ui";
import { api, ApiError, downloadPost, fmtDateTime, num } from "../../lib/api";
import { savePng } from "../../lib/designExport";

type Prev = Record<string, { paper: string; cad: string; title: string }>;
type Res = any;

export default function StructuralPanel({ pid, saved, dirty, code }: {
  pid: number; saved: { id: number; version: number } | null; dirty: boolean; code: string;
}) {
  const [f, setF] = useState({ fck: "20", fy: "500", sbc_kn_m2: "", seismic_zone: "", foundation_depth_m: "1.5", live_load: "2" });
  const [res, setRes] = useState<Res | null>(null);
  const [prev, setPrev] = useState<Prev>({});
  const [sid, setSid] = useState<{ id: number; version: number } | null>(null);
  const [qs, setQs] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [sheet, setSheet] = useState("columns");
  const [cad, setCad] = useState(false);
  const [versions, setVersions] = useState<any[]>([]);
  const loadVersions = () => api<any[]>(`/api/projects/${pid}/structural`).then(setVersions).catch(() => {});
  useEffect(() => { loadVersions(); }, [pid]);

  const show = (r: any) => { setRes(r.result); setPrev(r.previews); if (r.id) setSid({ id: r.id, version: r.version }); };
  const body = () => ({ design_id: saved?.id, inputs: { ...f, sbc_kn_m2: f.sbc_kn_m2 === "" ? null : Number(f.sbc_kn_m2) } });
  const run = async (store: boolean) => {
    if (!saved || dirty) return toast("Save the floor plan first (Save button) – the structure is designed from a saved version", "err");
    setBusy(true); setQs([]);
    try {
      const r = await api<any>(store ? `/api/projects/${pid}/structural` : `/api/projects/${pid}/structural/calculate`, { body: body() });
      show(r); if (store) { toast(`Saved as structural v${r.version}`); loadVersions(); } else setSid(null);
    } catch (e: any) {
      if (e instanceof ApiError && e.questions.length) setQs(e.questions);
      toast(e.message, "err");
    } finally { setBusy(false); }
  };
  const open = async (id: number) => {
    try { const r = await api<any>(`/api/structural/${id}`); show(r); const i = r.result.inputs; setF({ fck: String(i.fck), fy: String(i.fy), sbc_kn_m2: String(i.sbc_kn_m2), seismic_zone: i.seismic_zone, foundation_depth_m: String(i.foundation_depth_m), live_load: String(i.live_load) }); }
    catch (e: any) { toast(e.message, "err"); }
  };
  // 1.13: downloads come from the design on the screen (saved or not), the whole set or one sheet
  const dl = (kind: "pdf" | "cadpdf" | "dxf", page = "") => {
    if (!saved) return toast("Save the floor plan first (Design → Save) – the structure is designed from a saved plan", "err");
    const q = new URLSearchParams({ kind: kind === "dxf" ? "dxf" : "pdf", style: kind === "cadpdf" ? "cad" : "paper", ...(page ? { page } : {}) });
    const tag = sid ? `v${sid.version}` : "draft";
    const nm = page ? `Structural_${(prev[page]?.title || page).replace(/[^A-Za-z0-9]+/g, "_")}` : "Structural";
    downloadPost(`/api/projects/${pid}/structural/export?${q}`, body(), `${code}_${nm}_${tag}${kind === "cadpdf" ? "_CAD" : ""}.${kind === "dxf" ? "dxf" : "pdf"}`)
      .catch((e) => toast(e.message, "err"));
  };
  const set = (k: string) => (e: any) => setF({ ...f, [k]: e.target.value });
  const s = res?.summary;
  const sheets = Object.entries(prev) as [string, { paper: string; cad: string; title: string }][];
  const tbl = (head: string[], rows: (string | number)[][]) => (
    <div className="overflow-x-auto rounded-lg border border-line">
      <table className="w-full min-w-[480px] text-sm">
        <thead className="bg-slate-50 text-left text-xs text-slate-500"><tr>{head.map((h) => <th key={h} className="px-2 py-2">{h}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i} className="border-t border-line">{r.map((v, j) => <td key={j} className={`px-2 py-1.5 ${j === 0 ? "font-bold text-red-700" : ""}`}>{v}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
  return (
    <div className="space-y-4">
      <div className="grid gap-4 xl:grid-cols-[340px_1fr]">
        <Card title="Structural Inputs" icon={<Building2 size={20} />}>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <Field label="Concrete"><select className="input" value={f.fck} onChange={set("fck")}><option value="20">M20</option><option value="25">M25</option><option value="30">M30</option></select></Field>
              <Field label="Steel"><select className="input" value={f.fy} onChange={set("fy")}><option value="500">Fe500 / 500D</option><option value="415">Fe415</option><option value="550">Fe550</option></select></Field>
              <Field label="Soil SBC (kN/m²) *"><input className="input" type="number" min="40" max="600" placeholder="from soil test" value={f.sbc_kn_m2} onChange={set("sbc_kn_m2")} /></Field>
              <Field label="Seismic zone *"><select className="input" value={f.seismic_zone} onChange={set("seismic_zone")}><option value="">— select —</option>{["II", "III", "IV", "V"].map((z) => <option key={z} value={z}>Zone {z}</option>)}</select></Field>
              <Field label="Foundation depth (m)"><input className="input" type="number" step="0.1" min="0.9" max="4" value={f.foundation_depth_m} onChange={set("foundation_depth_m")} /></Field>
              <Field label="Live load (kN/m²)"><input className="input" type="number" step="0.5" min="1.5" max="5" value={f.live_load} onChange={set("live_load")} /></Field>
            </div>
            {qs.length > 0 && <div className="rounded-lg bg-amber-50 p-3 text-xs text-amber-800"><b>Please give:</b><ul className="ml-4 list-disc">{qs.map((q) => <li key={q}>{q}</li>)}</ul></div>}
            <div className="flex gap-2">
              <button className="btn-outline flex-1" disabled={busy} onClick={() => run(false)}><Calculator size={16} />Calculate</button>
              <button className="btn-primary flex-1" disabled={busy || !res} onClick={() => run(true)}><Save size={16} />Save</button>
            </div>
            <p className="text-[11px] text-slate-500">Design is made from the saved floor plan{saved ? ` (design v${saved.version})` : ""}. Soil SBC and seismic zone are never assumed.</p>
            {versions.length > 0 && (
              <div className="border-t border-line pt-2 text-xs">
                <div className="mb-1 font-semibold text-navy-ink">Saved structural versions</div>
                {versions.map((v) => <button key={v.id} onClick={() => open(v.id)} className="block w-full truncate rounded px-2 py-1 text-left hover:bg-slate-50">v{v.version} · {v.title} · {fmtDateTime(v.created_at)}</button>)}
              </div>
            )}
          </div>
        </Card>
        {!res ? <Card><Empty text="Enter the soil SBC and seismic zone, then Calculate." /></Card> : (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 2xl:grid-cols-6">
              {[["Columns", s.columns], ["Beams", s.beams], ["Slab panels", s.slabs], ["Footings", s.footings], ["Concrete", `${num(s.concrete_m3, 1)} m³`], ["Steel (approx.)", `${num(s.steel_kg, 0)} kg`]].map(([k, v]) => (
                <div key={k} className="card p-3 text-center"><div className="text-xs text-slate-500">{k}</div><div className="text-xl font-extrabold text-navy-ink">{v}</div></div>
              ))}
            </div>
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
              <TriangleAlert size={13} className="mr-1 inline" />For your study and reference – gravity loads only (IS 456); wind / earthquake not included. (This note is only on screen, not on the drawings.)
              {res.warnings.length > 0 && <ul className="mt-1 ml-4 list-disc">{res.warnings.map((w: string) => <li key={w}>{w}</li>)}</ul>}
            </div>
            <Card title="Drawings" action={<div className="flex flex-wrap gap-2">
              <button className={`btn-sm ${cad ? "btn-primary" : "btn-outline"}`} onClick={() => setCad(!cad)}>{cad ? "CAD colours (black)" : "Paper colours"}</button>
              <button className="btn-outline btn-sm" onClick={() => dl("pdf")}><Download size={14} />PDF</button>
              <button className="btn-outline btn-sm" onClick={() => dl("cadpdf")}><Download size={14} />PDF (CAD black)</button>
              <button className="btn-outline btn-sm" onClick={() => dl("dxf")}><Download size={14} />DXF</button>
            </div>}>
              <div className="mb-3 flex flex-wrap gap-1.5">
                {sheets.map(([k, v]) => <button key={k} onClick={() => setSheet(k)} className={`rounded-md px-3 py-1.5 text-xs font-semibold ${sheet === k ? "bg-brand-600 text-white" : "bg-brand-50 text-navy-ink"}`}>{v.title}</button>)}
              </div>
              <div className={`overflow-auto rounded-lg border border-line p-2 ${cad ? "bg-black" : "bg-white"}`}>
                <div className="mx-auto max-w-4xl" dangerouslySetInnerHTML={{ __html: prev[sheet]?.[cad ? "cad" : "paper"] || "" }} />
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-1.5 text-xs">
                <span className="font-semibold text-slate-500">This sheet:</span>
                <button className="btn-outline btn-sm" onClick={() => dl(cad ? "cadpdf" : "pdf", sheet)}><Download size={13} />PDF (A3)</button>
                <button className="btn-outline btn-sm" onClick={() => savePng(prev[sheet]?.[cad ? "cad" : "paper"] || "", `${code}_${sheet.replace(/[^A-Za-z0-9]+/g, "_")}.png`, 3000, cad ? "#000000" : "#ffffff").catch((e) => toast(e.message, "err"))}><Download size={13} />PNG</button>
                <button className="btn-ghost btn-sm" onClick={() => dl("pdf", "notes")}><Download size={13} />Notes &amp; quantities sheet</button>
                {!sid && <span className="text-[11px] text-amber-700">Not saved – downloads are marked “draft”.</span>}
              </div>
            </Card>
            <div className="grid gap-4 2xl:grid-cols-2">
              <Card title="Column Schedule">{tbl(["Mark", "Size (mm)", "Main bars", "Ties", "Pu (kN)", "Nos"], res.column_schedule.map((r: any) => [r.mark, `${r.b_mm} x ${r.D_mm}`, r.bars, r.ties, r.Pu_kn, r.count]))}</Card>
              <Card title="Footing Schedule">{tbl(["Mark", "Size (m)", "Depth (mm)", "Steel", "Nos"], res.footing_schedule.map((r: any) => [r.mark, `${r.B_m} x ${r.B_m}`, r.D_mm, r.steel, r.count]))}</Card>
              <Card title="Beam Schedule">{tbl(["Mark", "b x D", "Bottom", "Top", "Stirrups", "Nos"], res.beam_schedule.map((r: any) => [r.mark, `${r.b_mm}x${r.D_mm}`, r.bottom, r.top, r.stirrups, r.count]))}</Card>
              <Card title="Slab Schedule">{tbl(["Mark", "D (mm)", "Type", "Main (short)", "Long / dist.", "Nos"], res.slab_schedule.map((r: any) => [r.mark, r.D_mm, r.type, r.short_steel, r.long_steel, r.count]))}</Card>
            </div>
            <Card title="Quantities & notes">
              {tbl(["Member", "Concrete (m³)", "Steel (kg, approx.)"], res.quantities.map((q: any) => [q.member, q.concrete_m3, q.steel_kg]))}
              <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-slate-600">{res.notes.map((n: string) => <li key={n}>{n}</li>)}</ul>
              <div className="mt-2"><Badge color="amber">Use the BBS tab (Estimate → BBS) for bar bending schedules of these members.</Badge></div>
            </Card>
          </div>
        )}
      </div>
    </div>
  );
}
