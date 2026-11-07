/** 1.18 – Staircase design: type, width, riser / tread (auto from the floor height and the staircase room), rule
 *  checks, IS 456 waist slab, bar bending schedule and quantities. Choices are saved in plan.stair; the drawing set
 *  (Staircase Detail sheet), estimate, 3D and Vastu use the same result. */
import { useEffect, useState } from "react";
import { Check, TriangleAlert } from "lucide-react";
import { api } from "../../lib/api";
import type { Plan } from "../../lib/plan";

export type StairOpts = { type?: string; width_ft?: number; riser_mm?: number; tread_mm?: number; waist_mm?: number; finish?: string; railing?: string; internal?: boolean };
const TYPES: [string, string][] = [["auto", "Auto (best fit)"], ["dog_legged", "Dog-legged"], ["straight", "Straight"], ["l_shape", "L-shape"],
  ["u_shape", "U / open-well"], ["spiral", "Spiral"]];

export default function StairPanel({ plan, pid, onChange }: { plan: Plan; pid: number; onChange: (o: StairOpts) => void }) {
  const opts: StairOpts = (plan as any).stair || {};
  const [res, setRes] = useState<any>(null);
  const [err, setErr] = useState("");
  const hasStair = plan.levels.some((l) => l.rooms.some((r) => r.type === "stair"));
  const key = JSON.stringify([opts, plan.floor_height_ft, plan.levels.map((l) => l.rooms.filter((r) => r.type === "stair").map((r) => [r.w, r.d])), (plan as any).roof_sheets?.length]);
  useEffect(() => {
    if (!hasStair || plan.levels.length < 2) return;
    const t = setTimeout(() => api(`/api/projects/${pid}/design/stair`, { body: { plan, opts: {} } }).then((r) => { setRes(r); setErr(""); }).catch((e) => setErr(e.message)), 300);
    return () => clearTimeout(t);
  }, [key]);  // eslint-disable-line react-hooks/exhaustive-deps
  if (!hasStair || plan.levels.length < 2) return <p className="text-sm text-slate-500">A staircase is designed when the plan has 2 or more floors and a staircase room.</p>;
  const set = (k: keyof StairOpts, v: any) => onChange({ ...opts, [k]: v === "" ? undefined : v });
  const num = (k: keyof StairOpts, label: string, ph: string, step = 1) => (
    <label className="text-xs"><span className="label">{label}</span>
      <input className="input py-1" type="number" step={step} placeholder={ph} value={(opts as any)[k] ?? ""} onChange={(e) => set(k, e.target.value === "" ? "" : Number(e.target.value))} /></label>
  );
  const s = res?.structure;
  return (
    <div className="space-y-3 text-sm">
      <div className="grid grid-cols-2 gap-2">
        <label className="col-span-2 text-xs"><span className="label">Type</span>
          <select className="input py-1" value={opts.type || "auto"} onChange={(e) => set("type", e.target.value)}>{TYPES.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
        {num("width_ft", "Width (ft) – auto", res ? (res.width_mm / 304.8).toFixed(2) : "auto", 0.25)}
        {num("riser_mm", "Riser (mm) – auto", res ? String(Math.round(res.riser_mm)) : "auto")}
        {num("tread_mm", "Tread (mm)", "250")}
        {num("waist_mm", "Waist slab (mm) – auto", s ? String(s.waist_mm) : "auto", 5)}
        <label className="text-xs"><span className="label">Step finish</span>
          <select className="input py-1" value={opts.finish || "granite"} onChange={(e) => set("finish", e.target.value)}><option value="granite">Granite</option><option value="tiles">Vitrified tiles</option><option value="kota">Kota stone</option><option value="cement">Cement finish</option></select></label>
        <label className="text-xs"><span className="label">Railing</span>
          <select className="input py-1" value={opts.railing || "ss"} onChange={(e) => set("railing", e.target.value)}><option value="ss">Stainless steel</option><option value="ms">MS painted</option><option value="glass">Glass + SS</option><option value="wood">Wood</option></select></label>
      </div>
      {err && <p className="text-xs text-red-600">{err}</p>}
      {res && (
        <>
          <div className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-navy-ink"><b>{res.type_name}</b> · {res.risers} risers × {res.riser_mm} mm · tread {res.tread_mm} mm · width {res.width_mm} mm
            {res.landing_mm ? ` · landing ${res.landing_mm} mm` : ""} · flights {res.flights.map((f: any) => f.risers).join(" + ")}</div>
          <ul className="space-y-0.5 text-xs">
            {res.checks.map((c: any) => (
              <li key={c.item} className={`flex items-start gap-1.5 ${c.ok ? "text-emerald-700" : "text-amber-800"}`}>
                {c.ok ? <Check size={13} className="mt-0.5 shrink-0" /> : <TriangleAlert size={13} className="mt-0.5 shrink-0" />}
                <span><b>{c.item}</b>: {String(c.value)} <span className="text-slate-500">({c.limit})</span>{c.note && ` – ${c.note}`}</span>
              </li>
            ))}
          </ul>
          {s && <div className="rounded-lg border border-line px-3 py-2 text-xs">
            <div className="font-semibold text-navy-ink">Waist slab (IS 456) – M{s.fck} / Fe{s.fy}</div>
            <div>Span {s.span_m} m · waist {s.waist_mm} mm (d {s.d_mm}, needs {s.d_req_mm}) · Mu {s.mu_knm} kN·m/m</div>
            <div>Main {s.main.dia} mm @ {s.main.spacing} c/c · distribution 8 mm @ {s.dist.spacing} c/c · top bars at supports</div>
            <div className={s.ok ? "text-emerald-700" : "text-red-600"}>{s.note}</div>
          </div>}
          <div className="rounded-lg border border-line px-3 py-2 text-xs">
            <div className="font-semibold text-navy-ink">Per floor: concrete {res.per_floor.concrete_m3} m³ · steel {res.per_floor.steel_kg} kg · shuttering {res.per_floor.formwork_m2} m² · finish {res.per_floor.finish_m2} m² · railing {res.per_floor.railing_m} m</div>
            <table className="mt-1 w-full"><thead><tr className="text-left text-slate-500"><th>Bar</th><th>Ø</th><th>Nos</th><th>Length</th><th>kg</th></tr></thead>
              <tbody>{res.bbs.map((b: any) => <tr key={b.mark}><td>{b.mark}</td><td>{b.dia}</td><td>{b.nos}</td><td>{b.length_m} m</td><td>{b.kg}</td></tr>)}</tbody></table>
          </div>
          <p className="text-[11px] text-slate-500">Used in: Drawing set (Staircase Detail sheet), Estimate (concrete, steel, finish, railing), 3D. Limits are the usual ones for houses – the approving authority’s rules decide.</p>
        </>
      )}
    </div>
  );
}
