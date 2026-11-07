/** 1.18 – Plot shape: rectangle (frontage × depth) or ANY shape: 4 sides + one diagonal (from the survey / FMB sketch),
 *  sides + corner angles, or corner points. A missing measurement is asked – never guessed. A live sketch shows it. */
import { useMemo } from "react";

export type PlotShape = { mode: "rect" | "quad" | "angles" | "points"; sides?: number[]; diagonal?: number; angles?: number[]; points?: number[][] };

function sketch(sh: PlotShape): number[][] | null {
  try {
    if (sh.mode === "quad") {
      const [f, r, b, l] = (sh.sides || []).map(Number); const dg = Number(sh.diagonal);
      if (![f, r, b, l, dg].every((v) => v > 0)) return null;
      const tri = (ax: number, ay: number, bx: number, by: number, ra: number, rb: number) => {
        const dx = bx - ax, dy = by - ay, d = Math.hypot(dx, dy);
        if (ra + rb < d || Math.abs(ra - rb) > d) return null;
        const x = (ra * ra - rb * rb + d * d) / (2 * d), h = Math.sqrt(Math.max(0, ra * ra - x * x)), ux = dx / d, uy = dy / d;
        return [ax + ux * x - uy * h, ay + uy * x + ux * h];
      };
      const C = tri(0, 0, f, 0, dg, r); if (!C) return null;
      const D = tri(0, 0, C[0], C[1], l, b); if (!D) return null;
      return [[0, 0], [f, 0], C, D];
    }
    if (sh.mode === "angles") {
      const s = (sh.sides || []).map(Number), a = (sh.angles || []).map(Number);
      if (s.length < 3 || s.some((v) => !(v > 0)) || a.length < s.length - 1) return null;
      const pts = [[0, 0]]; let x = 0, y = 0, hd = 0;
      for (let i = 0; i < s.length - 1; i++) { x += s[i] * Math.cos(hd); y += s[i] * Math.sin(hd); pts.push([x, y]); hd += Math.PI - ((a[i + 1] ?? a[a.length - 1]) * Math.PI) / 180; }
      return pts;
    }
    if (sh.mode === "points") return (sh.points || []).length >= 3 ? sh.points! : null;
  } catch { /* incomplete */ }
  return null;
}

export default function PlotShapePanel({ shape, onChange }: { shape: PlotShape; onChange: (s: PlotShape) => void }) {
  const pts = useMemo(() => sketch(shape), [shape]);
  const area = pts ? Math.abs(pts.reduce((a, p, i) => a + p[0] * pts[(i + 1) % pts.length][1] - pts[(i + 1) % pts.length][0] * p[1], 0) / 2) : 0;
  const numIn = (v: any, set: (n: number | undefined) => void, ph: string) => (
    <input className="input py-1" type="number" min={0} step={0.25} placeholder={ph} value={v ?? ""} onChange={(e) => set(e.target.value === "" ? undefined : Number(e.target.value))} />
  );
  const side = (i: number, label: string) => (
    <label className="text-xs"><span className="label">{label}</span>{numIn(shape.sides?.[i], (n) => { const s = [...(shape.sides || [])]; s[i] = n as any; onChange({ ...shape, sides: s }); }, "ft")}</label>
  );
  const view = (() => {
    if (!pts) return null;
    const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
    const x0 = Math.min(...xs), y0 = Math.min(...ys), w = Math.max(...xs) - x0 || 1, h = Math.max(...ys) - y0 || 1, k = 150 / Math.max(w, h);
    const P = pts.map((p) => [(p[0] - x0) * k + 10, 170 - (p[1] - y0) * k]);
    return (
      <svg viewBox="0 0 180 200" className="h-40 w-36 shrink-0 rounded-lg border border-line bg-white">
        <polygon points={P.map((p) => p.join(",")).join(" ")} fill="#e0f2fe" stroke="#0f2350" strokeWidth={1.5} />
        <line x1={P[0][0]} y1={P[0][1] + 6} x2={P[1][0]} y2={P[1][1] + 6} stroke="#64748b" strokeWidth={3} />
        <text x={(P[0][0] + P[1][0]) / 2} y={P[0][1] + 18} fontSize={9} textAnchor="middle" fill="#475569">ROAD</text>
      </svg>
    );
  })();
  return (
    <div className="rounded-lg border border-line p-3">
      <div className="mb-2 flex flex-wrap items-center gap-2 text-xs">
        <b className="text-navy-ink">Plot shape</b>
        {([["rect", "Rectangle"], ["quad", "4 sides + diagonal"], ["angles", "Sides + angles"], ["points", "Corner points"]] as const).map(([k, l]) => (
          <button key={k} type="button" onClick={() => onChange({ ...shape, mode: k })} className={`rounded-full px-2.5 py-1 font-semibold ${shape.mode === k ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-600"}`}>{l}</button>
        ))}
      </div>
      {shape.mode === "rect" ? <p className="text-xs text-slate-500">Rectangular plot – frontage × depth above.</p> : (
        <div className="flex flex-wrap gap-3">
          <div className="grid min-w-[240px] flex-1 grid-cols-2 gap-2">
            {shape.mode === "quad" && <>
              {side(0, "Front – road side (ft)")}{side(1, "Right side (ft)")}{side(2, "Rear (ft)")}{side(3, "Left side (ft)")}
              <label className="col-span-2 text-xs"><span className="label">Diagonal: front-left corner → rear-right corner (ft) *</span>
                {numIn(shape.diagonal, (n) => onChange({ ...shape, diagonal: n }), "needed – 4 sides alone don't fix the shape")}</label>
            </>}
            {shape.mode === "angles" && <>
              <label className="col-span-2 text-xs"><span className="label">Sides in order, from the road side (ft, comma separated)</span>
                <input className="input py-1" placeholder="30, 52, 36, 50" defaultValue={(shape.sides || []).join(", ")} onBlur={(e) => onChange({ ...shape, sides: e.target.value.split(/[ ,]+/).filter(Boolean).map(Number) })} /></label>
              <label className="col-span-2 text-xs"><span className="label">Corner angles (°) at the start of each side</span>
                <input className="input py-1" placeholder="90, 92, 88, 90" defaultValue={(shape.angles || []).join(", ")} onBlur={(e) => onChange({ ...shape, angles: e.target.value.split(/[ ,]+/).filter(Boolean).map(Number) })} /></label>
            </>}
            {shape.mode === "points" && (
              <label className="col-span-2 text-xs"><span className="label">Corner points x,y in ft (x along the road, y away from it) – one per line, anticlockwise from front-left</span>
                <textarea className="input h-24 py-1 font-mono" placeholder={"0,0\n40,0\n48,45\n0,55"} defaultValue={(shape.points || []).map((p) => p.join(",")).join("\n")}
                  onBlur={(e) => onChange({ ...shape, points: e.target.value.split("\n").map((l) => l.split(/[ ,]+/).filter(Boolean).map(Number)).filter((p) => p.length === 2 && p.every((v) => !isNaN(v))) })} /></label>
            )}
            <p className="col-span-2 text-[11px] text-slate-500">{pts ? <>Area ≈ <b>{area.toFixed(0)} sq ft</b> ({(area / 435.6).toFixed(2)} cents). Setbacks are kept from every side; the house is the biggest rectangle that fits, the odd corners stay for garden / parking / sump.</>
              : "Enter all the measurements – the shape is drawn when it closes."}</p>
          </div>
          {view}
        </div>
      )}
    </div>
  );
}
