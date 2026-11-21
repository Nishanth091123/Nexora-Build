/** 1.21 – Rendered plan (2D): the floor plan as a furnished, coloured top view – floor finishes, furniture, car,
 *  staircase, plants around the house, glowing windows, door swings, room names with sizes. Everything comes from
 *  the plan (exact sizes) and the finishes / style chosen in 3D, through the same furniture engine as the 3D model.
 *  Vector drawing, so the PNG / PDF stays sharp at any print size. */
import { useMemo, type ReactNode, type Ref } from "react";
import { WALL_T, northVector, type Plan } from "../../lib/plan";
import { dimText, furnitureFor, furnPalette, localSize, planFrame, roomLabels, siteLayout, stairPlan, type FItem, type FurnPalette } from "./house3d/furniture";
import { placePlants, plantsOf, type Plants } from "./house3d/plants";

type Lv = Plan["levels"][number];
type Room = Lv["rooms"][number];
export type FloorLook = { color: string; image?: string | null; tile: number };

const WET = new Set(["toilet", "common_toilet"]);
const OPENAIR = new Set(["terrace", "balcony", "sitout"]);
const shade = (hex: string, k: number) => {
  const n = parseInt(hex.replace("#", "").padEnd(6, "0").slice(0, 6), 16);
  const f = (v: number) => Math.max(0, Math.min(255, Math.round(k >= 0 ? v + (255 - v) * k : v * (1 + k))));
  return `rgb(${f(n >> 16)},${f((n >> 8) & 255)},${f(n & 255)})`;
};

// ------------------------------------------------------------------ furniture symbols (local feet: u along the wall, v out from it)
function Symbol({ it, P }: { it: FItem; P: FurnPalette }) {
  const [W, D] = localSize(it);
  const R = (x: number, y: number, w: number, h: number, fill: string, rx = 0.08, o: Record<string, any> = {}) =>
    <rect x={x} y={y} width={Math.max(0, w)} height={Math.max(0, h)} rx={rx} fill={fill} {...o} />;
  const line = { stroke: "rgba(0,0,0,0.28)", strokeWidth: 0.035 };
  const leaf = (cx: number, cy: number, r: number) => <g>
    {[0, 1, 2, 3, 4, 5, 6].map((k) => <ellipse key={k} cx={cx + Math.cos(k * 0.9) * r * 0.42} cy={cy + Math.sin(k * 0.9) * r * 0.42} rx={r * 0.52} ry={r * 0.26}
      transform={`rotate(${k * 51} ${cx + Math.cos(k * 0.9) * r * 0.42} ${cy + Math.sin(k * 0.9) * r * 0.42})`} fill={k % 2 ? P.leaf : P.leaf2} />)}
    <circle cx={cx} cy={cy} r={r * 0.2} fill={shade(P.leaf, 0.25)} />
  </g>;
  const chair = (cx: number, cy: number, s: number, backDown: boolean, fill = P.wood) => <g>
    {R(cx - s / 2, cy - s / 2, s, s, shade(fill, 0.18), s * 0.22, line)}
    {R(cx - s / 2, backDown ? cy + s / 2 - s * 0.2 : cy - s / 2, s, s * 0.2, shade(fill, -0.25), s * 0.08)}
  </g>;
  switch (it.kind) {
    case "bed": {
      const single = it.v === "single";
      return <g>
        {R(0, 0, W, D, P.woodDark, 0.14)}
        {R(0.1, 0.38, W - 0.2, D - 0.5, P.linen, 0.16)}
        {R(-0.04, 0, W + 0.08, 0.36, shade(P.woodDark, -0.25), 0.1)}
        {(single ? [[0.35, W - 0.7]] : [[0.3, W / 2 - 0.42], [W / 2 + 0.12, W / 2 - 0.42]]).map(([x, w], k) => <g key={k}>{R(x, 0.55, w, 1.15, "#ffffff", 0.3, line)}</g>)}
        {R(0.1, 2.5, W - 0.2, D - 2.62, P.blanket, 0.16)}
        {R(0.1, 2.5, W - 0.2, 0.7, shade(P.blanket, 0.28), 0.16)}
        <path d={`M0.4 ${D - 1.4} Q${W / 2} ${D - 2.2} ${W - 0.4} ${D - 1.2}`} fill="none" stroke={shade(P.blanket, -0.18)} strokeWidth="0.05" />
      </g>;
    }
    case "side_table": return <g>{R(0, 0, W, D, P.wood, 0.1, line)}<circle cx={W / 2} cy={D / 2} r={0.62} fill="#ffe7a8" opacity="0.45" /><circle cx={W / 2} cy={D / 2} r={0.36} fill="#fff4d2" stroke="#caa55a" strokeWidth="0.05" /></g>;
    case "wardrobe": case "shelf": {
      const n = Math.max(1, it.n || Math.round(W / 1.5)), col = it.kind === "shelf" ? P.woodLight : P.wood;
      return <g>{R(0, 0, W, D, col, 0.06, line)}
        {Array.from({ length: n - 1 }, (_, k) => <line key={k} x1={((k + 1) * W) / n} y1={0.05} x2={((k + 1) * W) / n} y2={D - 0.05} stroke={shade(col, -0.35)} strokeWidth="0.05" />)}
        {R(0, D - 0.16, W, 0.16, shade(col, -0.22), 0.04)}
        {it.kind === "shelf" && Array.from({ length: n }, (_, k) => <rect key={"b" + k} x={(k * W) / n + 0.2} y={0.2} width={W / n - 0.4} height={D - 0.55} rx={0.06} fill={k % 2 ? "#c9b08a" : "#8fa3b8"} opacity="0.75" />)}
      </g>;
    }
    case "desk": return <g>
      {R(0, 0, W, 1.8, P.woodLight, 0.08, line)}{R(W / 2 - 0.7, 0.35, 1.4, 0.9, "#2b2f36", 0.06)}{R(W / 2 - 0.62, 0.42, 1.24, 0.6, "#8fb8d8", 0.03)}
      <circle cx={W - 0.55} cy={0.55} r={0.3} fill="#fff4d2" stroke="#caa55a" strokeWidth="0.05" />
      {chair(W / 2, 2.55, 1.5, true, P.sofa)}
    </g>;
    case "sofa": case "armchair": {
      const n = it.kind === "armchair" ? 1 : it.n || 3, arm = it.kind === "armchair" ? 0.45 : 0.6;
      const sw = (W - 2 * arm) / n;
      return <g>
        {R(0, 0, W, D, shade(P.sofa, -0.12), 0.34)}
        {R(0, 0, W, 0.85, shade(P.sofa, -0.24), 0.3)}
        {R(0, 0.2, arm, D - 0.2, shade(P.sofa, -0.2), 0.26)}{R(W - arm, 0.2, arm, D - 0.2, shade(P.sofa, -0.2), 0.26)}
        {Array.from({ length: n }, (_, k) => <g key={k}>{R(arm + k * sw + 0.05, 0.85, sw - 0.1, D - 0.95, P.cushion, 0.2, line)}</g>)}
        {n >= 2 && <>{R(arm + 0.15, 0.55, 0.95, 0.85, P.accent, 0.22, { transform: `rotate(-12 ${arm + 0.6} 1)` })}{R(W - arm - 1.1, 0.55, 0.95, 0.85, P.accent2, 0.22, { transform: `rotate(12 ${W - arm - 0.6} 1)` })}</>}
      </g>;
    }
    case "coffee_table": return <g>{R(0, 0, W, D, P.woodDark, 0.14)}{R(0.1, 0.1, W - 0.2, D - 0.2, shade(P.woodDark, 0.16), 0.1)}{leaf(W / 2, D / 2, Math.min(W, D) * 0.34)}</g>;
    case "rug": return <g opacity="0.92">{R(0, 0, W, D, P.rug, 0.1)}{R(0.3, 0.3, W - 0.6, D - 0.6, "none", 0.06, { stroke: shade(P.rug, -0.2), strokeWidth: 0.07 })}{R(0.55, 0.55, W - 1.1, D - 1.1, "none", 0.05, { stroke: shade(P.rug, 0.3), strokeWidth: 0.04 })}</g>;
    case "tv_unit": case "sideboard": return <g>{R(0, 0, W, D, P.woodDark, 0.08, line)}{R(0.08, 0.08, W - 0.16, D - 0.3, shade(P.woodDark, 0.14), 0.05)}
      {it.kind === "tv_unit" ? R(W * 0.14, 0.32, W * 0.72, 0.2, "#0b0b0d", 0.04) : <>{leaf(W * 0.25, D / 2, 0.42)}<circle cx={W * 0.7} cy={D / 2} r={0.3} fill="#e9dcc3" stroke="#b79c6b" strokeWidth="0.04" /></>}</g>;
    case "plant": case "planter": return <g><circle cx={W / 2} cy={D / 2} r={Math.min(W, D) * 0.34} fill={P.pot} stroke={shade(P.pot, -0.3)} strokeWidth="0.05" />{leaf(W / 2, D / 2, Math.min(W, D) * 0.62)}</g>;
    case "dining": {
      const n = it.n || 4, td = n === 2 ? 2.6 : 3, ty = (D - td) / 2, per = Math.max(1, n / 2), cs = Math.min(1.45, (W - 0.3) / per - 0.15);
      return <g>
        {Array.from({ length: per }, (_, k) => { const cx = ((k + 0.5) * W) / per; return <g key={k}>{chair(cx, ty - cs / 2 + 0.35, cs, false)}{chair(cx, ty + td + cs / 2 - 0.35, cs, true)}</g>; })}
        {R(0, ty, W, td, P.wood, 0.16, line)}{R(0.12, ty + 0.12, W - 0.24, td - 0.24, shade(P.wood, 0.14), 0.12)}
        {Array.from({ length: per }, (_, k) => { const cx = ((k + 0.5) * W) / per; return <g key={"p" + k}>
          <circle cx={cx} cy={ty + 0.62} r={0.36} fill="#ffffff" stroke="#cbd5e1" strokeWidth="0.04" /><circle cx={cx} cy={ty + td - 0.62} r={0.36} fill="#ffffff" stroke="#cbd5e1" strokeWidth="0.04" /></g>; })}
        {leaf(W / 2, D / 2, 0.42)}
      </g>;
    }
    case "counter": return <g>{R(0, 0, W, D, P.counter, 0.05)}{R(0.06, 0.06, W - 0.12, D - 0.2, shade(P.counter, 0.12), 0.04)}
      <line x1={0.1} y1={D - 0.07} x2={W - 0.1} y2={D - 0.07} stroke="rgba(255,255,255,0.35)" strokeWidth="0.05" /></g>;
    case "sink": case "wash_sink": return <g>
      {it.kind === "wash_sink" && R(0, 0, W, D, P.cabinet, 0.06)}
      {R(0.1, 0.32, W - 0.2, D - 0.62, P.steel, 0.14, line)}{R(0.22, 0.44, W / 2 - 0.3, D - 0.86, shade(P.steel, -0.18), 0.12)}{R(W / 2 + 0.08, 0.44, W / 2 - 0.3, D - 0.86, shade(P.steel, -0.18), 0.12)}
      <circle cx={W / 2} cy={0.2} r={0.11} fill="#6b7280" /></g>;
    case "hob": return <g>{R(0.1, 0.3, W - 0.2, D - 0.6, "#0d0e10", 0.1)}
      {[[0.32, 0.36], [0.68, 0.36], [0.32, 0.66], [0.68, 0.66]].map(([fx, fy], k) => <g key={k}><circle cx={W * fx} cy={D * fy} r={0.26} fill="none" stroke="#9ca3af" strokeWidth="0.06" /><circle cx={W * fx} cy={D * fy} r={0.09} fill="#6b7280" /></g>)}</g>;
    case "fridge": return <g>{R(0, 0, W, D, "#d5d9de", 0.12, line)}{R(0.1, 0.1, W - 0.2, D - 0.34, "#eceff2", 0.08)}{R(0, D - 0.2, W, 0.2, "#aeb4bb", 0.06)}{R(W * 0.12, D - 0.14, 0.7, 0.07, "#6b7280", 0.03)}</g>;
    case "wc": return <g>{R(W * 0.08, 0, W * 0.84, 0.72, P.white, 0.1, line)}<ellipse cx={W / 2} cy={Math.min(D - 0.75, 1.5)} rx={W * 0.4} ry={Math.min(0.9, (D - 0.72) / 2)} fill={P.white} stroke="rgba(0,0,0,0.3)" strokeWidth="0.04" />
      <ellipse cx={W / 2} cy={Math.min(D - 0.75, 1.5) + 0.05} rx={W * 0.25} ry={Math.min(0.58, (D - 0.72) / 3.2)} fill="#e3edf3" /></g>;
    case "basin": return <g>{R(0, 0, W, D, P.white, 0.2, line)}<ellipse cx={W / 2} cy={D / 2 + 0.08} rx={W * 0.33} ry={D * 0.3} fill="#dfe9ef" stroke="rgba(0,0,0,0.2)" strokeWidth="0.03" /><circle cx={W / 2} cy={0.2} r={0.1} fill="#6b7280" /></g>;
    case "shower": return <g>{R(0, 0, W, D, "#ffffff", 0.05, { opacity: 0.38 })}
      <path d={`M${W} 0V${D}H0`} fill="none" stroke="#7fd6ee" strokeWidth="0.1" opacity="0.9" />
      <circle cx={W / 2} cy={D / 2} r={0.2} fill="#9ca3af" /><circle cx={W / 2} cy={D / 2} r={0.09} fill="#4b5563" />
      <circle cx={0.5} cy={0.5} r={0.36} fill="#c7cdd4" stroke="#6b7280" strokeWidth="0.05" /></g>;
    case "mandapam": return <g>{R(0, 0, W, D, P.woodDark, 0.08, line)}{R(0.2, 0.15, W - 0.4, D - 0.5, "#e9c46a", 0.06)}{R(W / 2 - 0.35, 0.3, 0.7, D - 0.85, "#c0392b", 0.08)}
      {[0.22, 0.78].map((f) => <g key={f}><circle cx={W * f} cy={D - 0.3} r={0.3} fill="#ffb347" opacity="0.4" /><circle cx={W * f} cy={D - 0.3} r={0.13} fill="#ffdd88" stroke="#b7791f" strokeWidth="0.03" /></g>)}</g>;
    case "washer": return <g>{R(0, 0, W, D, P.white, 0.16, line)}<circle cx={W / 2} cy={D / 2 + 0.1} r={Math.min(W, D) * 0.3} fill="#cfd8e0" stroke="#6b7280" strokeWidth="0.06" />{R(0.2, 0.14, W - 0.4, 0.22, "#d1d5db", 0.06)}</g>;
    case "sitset": return <g>{chair(1.0, D / 2, 1.8, false, P.woodLight)}{chair(W - 1.0, D / 2, 1.8, false, P.woodLight)}<circle cx={W / 2} cy={D / 2} r={0.7} fill={P.wood} stroke="rgba(0,0,0,0.3)" strokeWidth="0.04" /><circle cx={W / 2} cy={D / 2} r={0.22} fill="#ffffff" /></g>;
    case "chair": return chair(W / 2, D / 2, Math.min(W, D) * 0.9, false, P.woodLight);
    case "car": {
      const body = P.car;
      return <g>
        {[[0.02, D * 0.2], [W - 0.5, D * 0.2], [0.02, D * 0.76], [W - 0.5, D * 0.76]].map(([x, y], k) => <g key={k}>{R(x, y - 1.1, 0.48, 2.2, "#15171a", 0.2)}</g>)}
        <path d={`M${W * 0.14} 0.35 Q${W / 2} -0.1 ${W * 0.86} 0.35 L${W - 0.18} ${D * 0.2} L${W - 0.12} ${D * 0.84} Q${W - 0.2} ${D - 0.1} ${W / 2} ${D} Q0.2 ${D - 0.1} 0.12 ${D * 0.84} L0.18 ${D * 0.2}Z`} fill={body} stroke="rgba(0,0,0,0.35)" strokeWidth="0.05" />
        <path d={`M${W * 0.18} ${D * 0.6} Q${W / 2} ${D * 0.56} ${W * 0.82} ${D * 0.6} L${W * 0.76} ${D * 0.73} Q${W / 2} ${D * 0.76} ${W * 0.24} ${D * 0.73}Z`} fill="#1e2a36" />
        <path d={`M${W * 0.22} ${D * 0.16} Q${W / 2} ${D * 0.13} ${W * 0.78} ${D * 0.16} L${W * 0.8} ${D * 0.24} Q${W / 2} ${D * 0.22} ${W * 0.2} ${D * 0.24}Z`} fill="#1e2a36" />
        {R(W * 0.2, D * 0.25, W * 0.6, D * 0.34, shade(body, 0.35), 0.5)}
        {R(W * 0.13, D * 0.27, 0.12, D * 0.3, "#1e2a36", 0.05)}{R(W * 0.87 - 0.12, D * 0.27, 0.12, D * 0.3, "#1e2a36", 0.05)}
        <ellipse cx={-0.02} cy={D * 0.64} rx={0.3} ry={0.18} fill={shade(body, -0.25)} /><ellipse cx={W + 0.02} cy={D * 0.64} rx={0.3} ry={0.18} fill={shade(body, -0.25)} />
        {R(W * 0.14, D - 0.5, 0.9, 0.24, "#fff6d5", 0.1)}{R(W * 0.86 - 0.9, D - 0.5, 0.9, 0.24, "#fff6d5", 0.1)}
        {R(W * 0.16, 0.3, 0.8, 0.2, "#c0392b", 0.08)}{R(W * 0.84 - 0.8, 0.3, 0.8, 0.2, "#c0392b", 0.08)}
      </g>;
    }
    case "bike": return <g>{R(W / 2 - 0.2, 0, 0.4, 1.7, "#15171a", 0.18)}{R(W / 2 - 0.2, D - 1.7, 0.4, 1.7, "#15171a", 0.18)}
      {R(W / 2 - 0.42, 1.2, 0.84, D - 2.6, "#b23a2e", 0.35)}{R(W / 2 - 0.36, 1.5, 0.72, 2.0, "#1f2328", 0.3)}{R(W / 2 - 1.0, D - 2.0, 2.0, 0.16, "#3f4652", 0.08)}</g>;
    default: return R(0, 0, W, D, P.woodLight, 0.1, line);
  }
}

export default function RenderedPlan({ plan, level, style, floorLook, plants, floorColor, terraceColor, metric = false, labels = true, svgRef, className = "" }: {
  plan: Plan; level: number; style: string; floorLook?: (roomKey: string, wet: boolean) => FloorLook | null; plants?: Plants | null;
  floorColor?: string; terraceColor?: string; metric?: boolean; labels?: boolean; svgRef?: Ref<SVGSVGElement>; className?: string;
}) {
  const lv = plan.levels[level];
  const P = useMemo(() => furnPalette(style), [style]);
  const items = useMemo(() => (lv ? furnitureFor(lv) : []), [lv]);
  const lbls = useMemo(() => roomLabels(plan, level, metric, items), [plan, level, metric, items]);
  const site = useMemo(() => siteLayout(plan, style), [plan, style]);
  const green = useMemo(() => (level === 0 ? placePlants(plants, { plotW: plan.plot.w, plotD: plan.plot.d, clear: site.clear, blocked: site.blocked, house: site.house, ov: site.ov, door: site.door }) : []), [plan, plants, site, level]);
  if (!lv) return null;
  const b = plan.building, plot = plan.plot;
  const F = planFrame(plan, level);
  const X = (x: number) => x, Y = (y: number) => -y;  // plot feet → svg (y up → y down)
  const bx = (x: number) => b.x + x, by = (y: number) => -(b.y + y);
  const lux = style === "luxury" || style === "modern";
  const lawn = plantsOf(plants).lawn.on;
  const poly: number[][] | null = plot.poly && plot.poly.length >= 3 ? plot.poly : null;
  const fdef = floorColor || "#e7e0d3";
  const uid = `rp${level}`;

  // ---- floors
  const pats: ReactNode[] = [];
  const floorFill = (r: Room): string => {
    const wet = WET.has(r.type);
    if (r.type === "parking" || r.type === "stilt_open") return `url(#${uid}pav)`;
    if (r.type === "stair") return "#d9d4ca";
    if (OPENAIR.has(r.type)) return `url(#${uid}ter)`;
    const lk = floorLook?.(`${level}:${r.id}`, wet);
    if (lk) {
      const id = `${uid}f${r.id}`;
      const t = Math.max(1, lk.tile || 2);
      pats.push(<pattern key={id} id={id} width={t} height={t} patternUnits="userSpaceOnUse">
        <rect width={t} height={t} fill={lk.color} />
        {lk.image ? <image href={lk.image} width={t} height={t} preserveAspectRatio="none" /> : <path d={`M${t} 0H0V${t}`} fill="none" stroke="rgba(0,0,0,0.12)" strokeWidth="0.05" />}
      </pattern>);
      return `url(#${id})`;
    }
    return wet ? `url(#${uid}wet)` : `url(#${uid}tile)`;
  };
  const floors = lv.rooms.map((r) => <rect key={r.id} x={bx(r.x)} y={by(r.y + r.d)} width={r.w} height={r.d} fill={floorFill(r)} />);

  // ---- walls / openings
  const wallBox = (w: { x1: number; y1: number; x2: number; y2: number }, th: number, ext = 0) => {
    const x1 = Math.min(w.x1, w.x2), x2 = Math.max(w.x1, w.x2), y1 = Math.min(w.y1, w.y2), y2 = Math.max(w.y1, w.y2);
    return Math.abs(w.y1 - w.y2) < 1e-6 ? { x: bx(x1) - ext, y: by(y1) - th / 2, width: x2 - x1 + 2 * ext, height: th } : { x: bx(x1) - th / 2, y: by(y2) - ext, width: th, height: y2 - y1 + 2 * ext };
  };
  const solid = lv.walls.filter((w) => w.kind !== "parapet");
  const wallEls = (fill: string, extra: Record<string, any> = {}) => solid.map((w, i) => { const th = WALL_T[w.kind] ?? 0.5; return <rect key={i} {...wallBox(w, th, th / 2)} fill={fill} {...extra} />; });
  const doorCol = P.wood;
  const openings = lv.openings.map((o) => {
    const horiz = Math.abs(o.y1 - o.y2) < 1e-6;
    const a = horiz ? Math.min(o.x1, o.x2) : Math.min(o.y1, o.y2), e = horiz ? Math.max(o.x1, o.x2) : Math.max(o.y1, o.y2), c = horiz ? o.y1 : o.x1, w = e - a;
    if (o.type === "window" || o.type === "vent") {
      return <g key={o.id}>
        <rect {...wallBox(o, 0.8)} fill="#e8f6fb" />
        <rect {...wallBox(o, 0.34)} fill="#39d5f5" filter={`url(#${uid}glow)`} />
        <rect {...wallBox(o, 0.12)} fill="#ffffff" opacity="0.85" />
      </g>;
    }
    const r = lv.rooms.find((q) => q.id === o.room);
    const dir = r ? (horiz ? (r.y + r.d / 2 > c ? 1 : -1) : (r.x + r.w / 2 > c ? 1 : -1)) : 1;
    const pt = (al: number, pe: number): [number, number] => (horiz ? [bx(al), by(c + pe)] : [bx(c + pe), by(al)]);
    const pie = (h: number, t: number, len: number) => {  // hinge at h, closed tip towards t
      const [hx, hy] = pt(h, 0), [tx, ty] = pt(t, 0), [ox, oy] = pt(h, dir * len);
      const cw = (tx - hx) * (oy - hy) - (ty - hy) * (ox - hx) > 0 ? 0 : 1;
      return <g><path d={`M${hx} ${hy}L${ox} ${oy}A${len} ${len} 0 0 ${cw} ${tx} ${ty}Z`} fill={doorCol} opacity="0.55" />
        <line x1={hx} y1={hy} x2={ox} y2={oy} stroke={shade(doorCol, -0.35)} strokeWidth="0.16" strokeLinecap="round" /></g>;
    };
    const dbl = o.type === "main_door" && w >= 3.9;
    return <g key={o.id}>
      <rect {...wallBox(o, 0.82)} fill={o.type === "main_door" ? "#cdb892" : "#ded6c8"} />
      {dbl ? <>{pie(a, (a + e) / 2, w / 2)}{pie(e, (a + e) / 2, w / 2)}</> : pie(a, e, w)}
    </g>;
  });

  // ---- furniture
  const furn = (layer: "flat" | "std" | "top") => items.filter((i) => (i.flat ? "flat" : i.top ? "top" : "std") === layer).map((it, k) => {
    const o: [number, number] = it.back === "s" ? [it.x, it.y] : it.back === "n" ? [it.x + it.w, it.y + it.d] : it.back === "w" ? [it.x, it.y + it.d] : [it.x + it.w, it.y];
    const u: [number, number] = it.back === "s" ? [1, 0] : it.back === "n" ? [-1, 0] : it.back === "w" ? [0, -1] : [0, 1];
    const v: [number, number] = it.back === "s" ? [0, 1] : it.back === "n" ? [0, -1] : it.back === "w" ? [1, 0] : [-1, 0];
    return <g key={`${it.room}${it.kind}${k}`} transform={`matrix(${u[0]} ${-u[1]} ${v[0]} ${-v[1]} ${bx(o[0])} ${by(o[1])})`}><Symbol it={it} P={P} /></g>;
  });

  // ---- stairs
  const stairs = lv.rooms.filter((r) => r.type === "stair").map((r) => {
    const s = stairPlan(plan, r); if (!s) return null;
    const pts = s.arrow.map(([x, y]) => `${bx(x)},${by(y)}`).join(" ");
    const [ax, ay] = s.arrow[0], [qx, qy] = s.arrow[1];
    const dl = Math.hypot(qx - ax, qy - ay) || 1, tx = bx(ax + ((qx - ax) / dl) * 1.3), ty = by(ay + ((qy - ay) / dl) * 1.3);
    return <g key={r.id}>
      {s.steps.map((q, k) => <rect key={k} x={bx(q.x0)} y={by(q.y1)} width={q.x1 - q.x0} height={q.y1 - q.y0} fill={k % 2 ? "#efeae1" : "#e4ded3"} stroke="rgba(0,0,0,0.28)" strokeWidth="0.04" />)}
      {s.landing && <rect x={bx(s.landing.x0)} y={by(s.landing.y1)} width={s.landing.x1 - s.landing.x0} height={s.landing.y1 - s.landing.y0} fill="#ebe6dc" stroke="rgba(0,0,0,0.28)" strokeWidth="0.04" />}
      <polyline points={pts} fill="none" stroke="#b45309" strokeWidth="0.12" markerEnd={`url(#${uid}arr)`} />
      <circle cx={bx(ax)} cy={by(ay)} r="0.22" fill="#b45309" />
      <text x={tx + (Math.abs(qx - ax) < 0.01 ? 0.95 : 0)} y={ty + (Math.abs(qx - ax) < 0.01 ? 0.25 : -0.45)} fontSize="0.72" fontWeight="800" textAnchor="middle" fill="#7c2d12" stroke="#ffffff" strokeWidth="0.18" paintOrder="stroke">UP</text>
    </g>;
  });

  // ---- 1.27.8 staircase outside the building (ground floor only): flight rising towards the rear, landing at the terrace
  const extStair = (() => {
    const e: any = (plan as any).ext_stair;
    if (!e || !e.on || level !== 0) return null;
    const xs = lv.rooms.flatMap((r) => [r.x, r.x + r.w]), ys = lv.rooms.map((r) => r.y);
    const sw = Number(e.w) || 3, sl = Number(e.len) || 18.8, N = Math.max(8, Number(e.risers) || 20);
    const sx = e.side === "left" ? Math.min(...xs) - 0.05 - sw : Math.max(...xs) + 0.05, sy = Math.min(...ys) + 2.0;
    const run = (sl - 3.0) / (N - 1), cx = sx + sw / 2;
    return <g key="extstair">
      <rect x={bx(sx)} y={by(sy + sl)} width={sw} height={sl} fill="#e6e0d5" stroke="rgba(0,0,0,0.5)" strokeWidth="0.1" />
      {Array.from({ length: N - 1 }, (_, k) => <line key={k} x1={bx(sx)} x2={bx(sx + sw)} y1={by(sy + k * run)} y2={by(sy + k * run)} stroke="rgba(0,0,0,0.3)" strokeWidth="0.05" />)}
      <rect x={bx(sx)} y={by(sy + sl)} width={sw} height={3.0} fill="#ebe6dc" stroke="rgba(0,0,0,0.5)" strokeWidth="0.1" />
      <line x1={bx(sx + 0.12)} x2={bx(sx + 0.12)} y1={by(sy)} y2={by(sy + sl)} stroke="#2a2c30" strokeWidth="0.1" />
      <line x1={bx(sx + sw - 0.12)} x2={bx(sx + sw - 0.12)} y1={by(sy)} y2={by(sy + sl)} stroke="#2a2c30" strokeWidth="0.1" />
      <polyline points={`${bx(cx)},${by(sy + 0.6)} ${bx(cx)},${by(sy + sl - 3.4)}`} fill="none" stroke="#b45309" strokeWidth="0.12" markerEnd={`url(#${uid}arr)`} />
      <text x={bx(cx)} y={by(sy - 0.7)} fontSize="0.72" fontWeight="800" textAnchor="middle" fill="#7c2d12" stroke="#ffffff" strokeWidth="0.18" paintOrder="stroke">EXTERNAL STAIR UP</text>
    </g>;
  })();

  // ---- outside (ground floor): lawn, driveway, path, compound wall + gate, trees & plants, garden lights
  const outside = () => {
    const g = site.gate, park = site.park, door = site.door;
    const plotShape = poly ? <polygon points={poly.map(([x, y]) => `${X(x)},${Y(y)}`).join(" ")} fill={lawn ? `url(#${uid}grass)` : "#d6cba9"} />
      : <rect x={0} y={-plot.d} width={plot.w} height={plot.d} fill={lawn ? `url(#${uid}grass)` : "#d6cba9"} />;
    let wallPath = `M${g.x + g.w} 0H${plot.w}V${-plot.d}H0V0H${g.x}`;
    if (poly) {  // irregular plot: the wall follows every side; the gate is on the road side (first side)
      const fwd = poly[0][0] <= poly[1][0];
      const ring = fwd ? [poly[1], ...poly.slice(2), poly[0]] : [poly[0], ...poly.slice(2).reverse(), poly[1]];
      wallPath = `M${X(g.x + g.w)} ${Y(0)}` + ring.map(([x, y]) => `L${X(x)} ${Y(y)}`).join("") + `L${X(g.x)} ${Y(0)}`;
    }
    const lights: [number, number][] = [];
    if (style !== "basic") for (const [x0, x1] of [[0.9, site.house.x0 - 0.8], [site.house.x1 + 0.8, plot.w - 0.9]]) {
      if (x1 - x0 < 0.6) continue;
      for (let y = site.house.y0 + 3; y < site.house.y1 - 1; y += 9) lights.push([x0 < site.house.x0 ? x0 + 0.5 : x1 - 0.5, y]);
    }
    return <g>
      <rect x={F.x0} y={-F.y1} width={F.x1 - F.x0} height={F.y1 - F.y0} fill="#e9e6df" />
      <rect x={F.x0} y={1.6} width={F.x1 - F.x0} height={-F.y0 - 1.6} fill="#4b4f56" />
      <line x1={F.x0} y1={5.6} x2={F.x1} y2={5.6} stroke="#f3f4f6" strokeWidth="0.22" strokeDasharray="3 2.4" />
      <rect x={F.x0} y={0.4} width={F.x1 - F.x0} height={1.2} fill="#bdb8ad" />
      {plotShape}
      {park && <rect x={bx(park.x)} y={Y(b.y + park.y)} width={park.w} height={b.y + park.y + 0.4} fill={`url(#${uid}pav)`} />}
      {door && (!park || Math.abs(door.x - (b.x + park.x + park.w / 2)) > park.w / 2) && <rect x={door.x - 2} y={Y(door.y)} width={4} height={door.y + 0.4} fill={`url(#${uid}pav)`} />}
      <g filter={`url(#${uid}sh)`}>
        {green.filter((p) => p.kind === "shrubs" || p.kind === "potted").map((p, k) => <g key={"s" + k}>
          {p.kind === "potted" && <circle cx={X(p.x)} cy={Y(p.y)} r={0.8} fill={P.pot} />}
          {[0, 1, 2, 3, 4].map((j) => <circle key={j} cx={X(p.x) + Math.cos(j * 1.26 + k) * 0.55} cy={Y(p.y) + Math.sin(j * 1.26 + k) * 0.55} r={0.72} fill={j % 2 ? "#3f8a3a" : "#5aa646"} />)}
          {p.kind === "shrubs" && k % 3 === 0 && [0, 1, 2].map((j) => <circle key={"f" + j} cx={X(p.x) + Math.cos(j * 2.1) * 0.5} cy={Y(p.y) + Math.sin(j * 2.1) * 0.5} r={0.2} fill={k % 2 ? "#f472b6" : "#fbbf24"} />)}
        </g>)}
      </g>
      <g filter={`url(#${uid}shBig)`} opacity="0.93">
        {green.filter((p) => p.kind !== "shrubs" && p.kind !== "potted" && p.x > F.x0 + 1 && p.x < F.x1 - 1 && p.y < F.y1 - 1).map((p, k) => {
          const palm = p.kind === "coconut" || p.kind === "areca", R0 = p.kind === "coconut" ? 6.2 : p.kind === "areca" ? 3.2 : 5.6;
          return <g key={"t" + k} transform={`translate(${X(p.x)} ${Y(p.y)})`}>
            {palm ? Array.from({ length: 9 }, (_, j) => <ellipse key={j} cx={R0 * 0.5} cy={0} rx={R0 * 0.52} ry={R0 * 0.14} fill={j % 2 ? "#3d7a35" : "#4f9442"} transform={`rotate(${j * 40 + k * 13})`} />)
              : Array.from({ length: 8 }, (_, j) => <circle key={j} cx={Math.cos(j * 0.8 + k) * R0 * 0.45} cy={Math.sin(j * 0.8 + k) * R0 * 0.45} r={R0 * 0.5} fill={["#3f7d36", "#4c9140", "#35702f"][j % 3]} />)}
            <circle r={palm ? 0.5 : R0 * 0.34} fill={palm ? "#6b4a2e" : "#58a049"} />
          </g>;
        })}
      </g>
      {lights.map(([x, y], k) => <g key={"l" + k}><circle cx={X(x)} cy={Y(y)} r={1.5} fill="#ffe9a8" opacity="0.4" filter={`url(#${uid}glow)`} /><circle cx={X(x)} cy={Y(y)} r={0.24} fill="#fff6d5" stroke="#b7791f" strokeWidth="0.04" /></g>)}
      <path d={wallPath} fill="none" stroke={style === "traditional" ? "#8a5a3a" : lux ? "#2a2c30" : "#6b7280"} strokeWidth="0.75" strokeLinejoin="miter" filter={`url(#${uid}sh)`} />
      {[g.x - 0.4, g.x + g.w + 0.4].map((x, k) => <rect key={k} x={x - 0.75} y={-0.75} width={1.5} height={1.5} fill={lux ? "#8d8579" : "#9ca3af"} stroke="rgba(0,0,0,0.4)" strokeWidth="0.05" />)}
      <line x1={g.x + 0.4} y1={0.25} x2={g.x + g.w - 0.4} y2={0.25} stroke="#1d2024" strokeWidth="0.22" strokeDasharray="0.5 0.22" />
    </g>;
  };
  const below = level > 0 ? plan.levels[level - 1].rooms.map((r) => <rect key={"bl" + r.id} x={bx(r.x) - 0.4} y={by(r.y + r.d) - 0.4} width={r.w + 0.8} height={r.d + 0.8} fill="#d8d4cb" />) : null;

  // ---- overall dimensions
  const e = { x0: b.x + Math.min(...lv.rooms.map((r) => r.x)), x1: b.x + Math.max(...lv.rooms.map((r) => r.x + r.w)), y0: b.y + Math.min(...lv.rooms.map((r) => r.y)), y1: b.y + Math.max(...lv.rooms.map((r) => r.y + r.d)) };
  const dm = F.ground ? { x0: 0, x1: plot.w, y0: 0, y1: plot.d } : e;
  const dtx = (v: number) => (metric ? `${dimText(v, true)} m` : dimText(v));
  const [nx, ny] = northVector(plan);
  const VW = F.x1 - F.x0, VH = F.y1 - F.y0 + 3.2;

  return (
    <svg ref={svgRef} viewBox={`${F.x0} ${-F.y1 - 3.2} ${VW} ${VH}`} className={`h-full w-full select-none ${className}`} xmlns="http://www.w3.org/2000/svg" fontFamily="Arial, Helvetica, sans-serif">
      <defs>
        <pattern id={`${uid}tile`} width="2" height="2" patternUnits="userSpaceOnUse"><rect width="2" height="2" fill={fdef} /><rect width="1.96" height="1.96" fill={shade(fdef, 0.1)} /><path d="M2 0H0V2" fill="none" stroke="rgba(0,0,0,0.13)" strokeWidth="0.045" /></pattern>
        <pattern id={`${uid}wet`} width="1" height="1" patternUnits="userSpaceOnUse"><rect width="1" height="1" fill="#bcd3e6" /><rect x="0.04" y="0.04" width="0.92" height="0.92" fill="#cfe1ef" /></pattern>
        <pattern id={`${uid}ter`} width="1.5" height="1.5" patternUnits="userSpaceOnUse"><rect width="1.5" height="1.5" fill={terraceColor || "#cfcac2"} /><path d="M1.5 0H0V1.5" fill="none" stroke="rgba(0,0,0,0.16)" strokeWidth="0.04" /></pattern>
        <pattern id={`${uid}pav`} width="2" height="2" patternUnits="userSpaceOnUse"><rect width="2" height="2" fill="#8f8f8c" /><rect x="0.04" y="0.04" width="1.92" height="0.92" fill="#a9a59c" /><rect x="-0.96" y="1.04" width="1.92" height="0.92" fill="#9d9990" /><rect x="1.04" y="1.04" width="1.92" height="0.92" fill="#b0aca3" /></pattern>
        <pattern id={`${uid}grass`} width="3" height="3" patternUnits="userSpaceOnUse"><rect width="3" height="3" fill="#7ea957" />{[[0.4, 0.5], [1.7, 0.9], [2.5, 2.1], [0.9, 2.3], [1.4, 1.6], [2.6, 0.3]].map(([x, y], k) => <circle key={k} cx={x} cy={y} r={0.28} fill={k % 2 ? "#8ab964" : "#6f9a4b"} opacity="0.7" />)}</pattern>
        <filter id={`${uid}sh`} x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="0.16" dy="0.22" stdDeviation="0.22" floodColor="#000" floodOpacity="0.42" /></filter>
        <filter id={`${uid}shBig`} x="-30%" y="-30%" width="160%" height="160%"><feDropShadow dx="0.7" dy="0.9" stdDeviation="0.6" floodColor="#000" floodOpacity="0.35" /></filter>
        <filter id={`${uid}ao`} x="-10%" y="-10%" width="120%" height="120%"><feGaussianBlur stdDeviation="0.55" /></filter>
        <filter id={`${uid}glow`} x="-60%" y="-60%" width="220%" height="220%"><feGaussianBlur stdDeviation="0.28" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
        <marker id={`${uid}arr`} viewBox="0 0 10 10" refX="7" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse"><path d="M0 0L10 5L0 10z" fill="#b45309" /></marker>
        <clipPath id={`${uid}clip`}>{lv.rooms.map((r) => <rect key={r.id} x={bx(r.x)} y={by(r.y + r.d)} width={r.w} height={r.d} />)}</clipPath>
        {pats}
      </defs>
      <rect x={F.x0} y={-F.y1 - 3.2} width={VW} height={VH} fill="#f6f4ef" />
      {F.ground ? outside() : below}
      {/* soft ground shadow of the whole floor */}
      <g filter={`url(#${uid}shBig)`}>{lv.rooms.map((r) => <rect key={"gs" + r.id} x={bx(r.x) - 0.3} y={by(r.y + r.d) - 0.3} width={r.w + 0.6} height={r.d + 0.6} fill="#55524c" />)}</g>
      {floors}
      {/* contact shadows beside the walls */}
      <g clipPath={`url(#${uid}clip)`}><g filter={`url(#${uid}ao)`} opacity="0.4">{solid.map((w, i) => <rect key={i} {...wallBox(w, (WALL_T[w.kind] ?? 0.5) + 1.3, 0.4)} fill="#000" />)}</g></g>
      {stairs}
      {extStair}
      {furn("flat")}
      <g filter={`url(#${uid}sh)`}>{furn("std")}</g>
      {furn("top")}
      {lv.walls.filter((w) => w.kind === "parapet").map((w, i) => <g key={"p" + i}><rect {...wallBox(w, 0.42, 0.2)} fill="#8a8f96" /><rect {...wallBox(w, 0.16, 0.2)} fill="#cfe9f3" /></g>)}
      <g filter={`url(#${uid}sh)`}>{wallEls(P.wall)}</g>
      {wallEls(shade(P.wall, 0.12), { transform: "translate(-0.03 -0.03)", opacity: 0.55 })}
      {openings}
      {labels && <g data-labels="1">{lbls.map((l, k) => {
        const x = bx(l.x), y = by(l.y);
        return <g key={k} transform={l.rot ? `rotate(-90 ${x} ${y})` : undefined} textAnchor="middle" stroke="#ffffff" strokeWidth={l.fs * 0.26} paintOrder="stroke" strokeLinejoin="round">
          <text x={x} y={y - l.fs * 0.12} fontSize={l.fs} fontWeight="800" fill="#1b1f24" letterSpacing="0.02">{l.name}</text>
          <text x={x} y={y + l.fs * 0.86} fontSize={l.fs * 0.8} fontWeight="700" fill="#27303a">{l.size}</text>
        </g>;
      })}</g>}
      {/* overall sizes */}
      <g fontSize="1.25" fontWeight="700" fill="#111827" stroke="#111827" strokeWidth="0.07">
        <line x1={dm.x0} y1={-dm.y1 - 3.4 + (F.ground ? 0 : 0.4)} x2={dm.x1} y2={-dm.y1 - 3.4 + (F.ground ? 0 : 0.4)} />
        {[dm.x0, dm.x1].map((x) => <line key={x} x1={x} y1={-dm.y1 - 4.1 + (F.ground ? 0 : 0.4)} x2={x} y2={-dm.y1 - 2.7 + (F.ground ? 0 : 0.4)} />)}
        <text x={(dm.x0 + dm.x1) / 2} y={-dm.y1 - 4.0 + (F.ground ? 0 : 0.4)} textAnchor="middle" stroke="none">{dtx(dm.x1 - dm.x0)}</text>
        <line x1={dm.x0 - 3.2} y1={-dm.y0} x2={dm.x0 - 3.2} y2={-dm.y1} />
        {[dm.y0, dm.y1].map((y) => <line key={y} x1={dm.x0 - 3.9} y1={-y} x2={dm.x0 - 2.5} y2={-y} />)}
        <text x={dm.x0 - 3.8} y={-(dm.y0 + dm.y1) / 2} textAnchor="middle" stroke="none" transform={`rotate(-90 ${dm.x0 - 3.8} ${-(dm.y0 + dm.y1) / 2})`}>{dtx(dm.y1 - dm.y0)}</text>
      </g>
      {/* north */}
      <g transform={`translate(${F.x1 - 3.2} ${-F.y1 + 0.2})`}>
        <circle r="2.1" fill="#ffffff" stroke="#9ca3af" strokeWidth="0.08" opacity="0.92" />
        <line x1={-nx * 1.5} y1={-ny * 1.5} x2={nx * 1.5} y2={ny * 1.5} stroke="#111827" strokeWidth="0.2" />
        <circle cx={nx * 1.5} cy={ny * 1.5} r="0.36" fill="#ef4444" />
        <text x={0} y={0.4} fontSize="1.05" textAnchor="middle" fontWeight="800" fill="#ef4444" stroke="#fff" strokeWidth="0.2" paintOrder="stroke">N</text>
      </g>
      <text x={F.x0 + 0.8} y={-F.y1 - 1.3} fontSize="1.25" fontWeight="800" fill="#111827">{lv.name.toUpperCase()} PLAN</text>
      <text x={F.x0 + 0.8} y={-F.y1 - 0.1} fontSize="0.72" fill="#4b5563">Sizes from the drawing · furniture shown for layout idea</text>
    </svg>
  );
}

/** the drawing → PNG / JPEG data URL, `long` px on the longer side */
export async function planImage(svg: SVGSVGElement, long = 3840, type: "image/png" | "image/jpeg" = "image/png", dropLabels = false): Promise<{ url: string; w: number; h: number }> {
  const clone = svg.cloneNode(true) as SVGSVGElement;
  if (dropLabels) clone.querySelectorAll("[data-labels]").forEach((n) => n.remove());
  const vb = (clone.getAttribute("viewBox") || "0 0 4 3").split(/[\s,]+/).map(Number);
  const ratio = vb[3] / vb[2];
  const w = ratio >= 1 ? Math.round(long / ratio) : long, h = ratio >= 1 ? long : Math.round(long * ratio);
  clone.setAttribute("width", String(w)); clone.setAttribute("height", String(h)); clone.removeAttribute("class");
  const data = new XMLSerializer().serializeToString(clone);
  const img = new Image();
  await new Promise<void>((ok, bad) => { img.onload = () => ok(); img.onerror = () => bad(new Error("Could not draw the plan picture")); img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(data); });
  const c = document.createElement("canvas"); c.width = w; c.height = h;
  const g = c.getContext("2d")!; g.fillStyle = "#f6f4ef"; g.fillRect(0, 0, w, h); g.drawImage(img, 0, 0, w, h);
  return { url: c.toDataURL(type, 0.93), w, h };
}
