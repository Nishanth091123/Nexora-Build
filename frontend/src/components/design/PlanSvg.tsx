import { useRef, useState, type PointerEvent as RPE } from "react";
import { ROOM_FILL, WALL_T, northVector, type Plan, type Room } from "../../lib/plan";

type DragState = {
  mode: "move" | "e" | "w" | "n" | "s"; id: string; start: [number, number]; orig: Room[];
};

/** 2D floor plan (feet). Road at the bottom. Editable: drag rooms, drag edge handles to resize. */
export default function PlanSvg({ plan, level, editable = false, selected, onSelect, onChange, grid = 0.5, stale = false,
  showDims = true, className = "", vastuGrid = false, highlight }: {
  plan: Plan; level: number; editable?: boolean; selected?: string | null; onSelect?: (id: string | null) => void;
  onChange?: (rooms: Room[], commit: boolean) => void; grid?: number; stale?: boolean; showDims?: boolean; className?: string;
  vastuGrid?: boolean; highlight?: Record<string, string>;
}) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [drag, setDrag] = useState<DragState | null>(null);
  const lv = plan.levels[level];
  if (!lv) return null;
  const { plot, building: b, setbacks: sb } = plan;
  const M = 9;
  const D = plot.d;
  const Y = (y: number) => D - y; // plan y (away from road) -> svg y
  const rooms = lv.rooms;

  const toWorld = (e: { clientX: number; clientY: number }): [number, number] => {
    const svg = svgRef.current!;
    const pt = svg.createSVGPoint();
    pt.x = e.clientX; pt.y = e.clientY;
    const m = svg.getScreenCTM();
    const p = m ? pt.matrixTransform(m.inverse()) : pt;
    return [p.x - b.x, D - p.y - b.y]; // building coords
  };

  const startDrag = (e: RPE, id: string, mode: DragState["mode"]) => {
    if (!editable) return;
    e.stopPropagation();
    (e.target as Element).setPointerCapture?.(e.pointerId);
    onSelect?.(id);
    setDrag({ mode, id, start: toWorld(e), orig: rooms.map((r) => ({ ...r })) });
  };

  const sn = (v: number) => Math.round(v / grid) * grid;
  const apply = (e: RPE, commit: boolean) => {
    if (!drag || !onChange) return;
    const [wx, wy] = toWorld(e);
    const dx = sn(wx - drag.start[0]);
    const dy = sn(wy - drag.start[1]);
    const next = drag.orig.map((r) => ({ ...r }));
    const r = next.find((x) => x.id === drag.id)!;
    const o = drag.orig.find((x) => x.id === drag.id)!;
    if (drag.mode === "move") {
      const mx = Math.min(Math.max(dx, -o.x), b.w - o.x - o.w);
      const my = Math.min(Math.max(dy, -o.y), b.d - o.y - o.d);
      for (const k of next) {
        if (k.id === drag.id || k.parent === drag.id) {
          const ko = drag.orig.find((x) => x.id === k.id)!;
          k.x = +(ko.x + mx).toFixed(2); k.y = +(ko.y + my).toFixed(2);
        }
      }
    } else if (drag.mode === "e") r.w = +Math.min(Math.max(2, o.w + dx), b.w - o.x).toFixed(2);
    else if (drag.mode === "w") { const nx = Math.min(Math.max(0, o.x + dx), o.x + o.w - 2); r.x = +nx.toFixed(2); r.w = +(o.x + o.w - nx).toFixed(2); }
    else if (drag.mode === "n") r.d = +Math.min(Math.max(2, o.d + dy), b.d - o.y).toFixed(2);
    else if (drag.mode === "s") { const ny = Math.min(Math.max(0, o.y + dy), o.y + o.d - 2); r.y = +ny.toFixed(2); r.d = +(o.y + o.d - ny).toFixed(2); }
    onChange(next, commit);
    if (commit) setDrag(null);
  };

  const [nx, ny] = northVector(plan);
  const sel = rooms.find((r) => r.id === selected);
  const fs = Math.max(1.1, Math.min(2.2, Math.max(plot.w, plot.d) / 30));

  const wallRect = (w: { x1: number; y1: number; x2: number; y2: number; kind: string }, key: string, fill: string, t?: number) => {
    const th = t ?? WALL_T[w.kind] ?? 0.5;
    const x1 = b.x + Math.min(w.x1, w.x2), x2 = b.x + Math.max(w.x1, w.x2);
    const y1 = b.y + Math.min(w.y1, w.y2), y2 = b.y + Math.max(w.y1, w.y2);
    if (w.y1 === w.y2) return <rect key={key} x={x1} y={Y(y1) - th / 2} width={x2 - x1} height={th} fill={fill} />;
    return <rect key={key} x={x1 - th / 2} y={Y(y2)} width={th} height={y2 - y1} fill={fill} />;
  };

  return (
    <svg ref={svgRef} viewBox={`${-M} ${-M} ${plot.w + 2 * M} ${plot.d + 2 * M}`} className={`h-full w-full select-none ${className}`}
      onPointerMove={(e) => drag && apply(e, false)} onPointerUp={(e) => drag && apply(e, true)}
      onPointerDown={() => editable && onSelect?.(null)} style={{ touchAction: "none" }}>
      <defs>
        <pattern id="grid1" width="1" height="1" patternUnits="userSpaceOnUse"><path d="M1 0H0V1" fill="none" stroke="#eef2f7" strokeWidth="0.04" /></pattern>
        <pattern id="hatch" width="1.2" height="1.2" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="1.2" stroke="#cbd5e1" strokeWidth="0.15" /></pattern>
      </defs>
      {/* road */}
      <rect x={-M} y={D + 1.2} width={plot.w + 2 * M} height={M - 1.2} fill="#e2e8f0" />
      <text x={plot.w / 2} y={D + 5.6} textAnchor="middle" fontSize={fs * 1.1} fontWeight="700" fill="#475569" letterSpacing="0.4">{sb.road_width_m > 0 ? `ROAD · ${Math.round(sb.road_width_m / 0.3048)} ft (${sb.road_width_m} m)` : "ROAD SIDE"}</text>
      {/* plot & setback zone */}
      <rect x={0} y={0} width={plot.w} height={plot.d} fill="url(#hatch)" stroke="#334155" strokeWidth="0.25" />
      <rect x={b.x} y={Y(b.y + b.d)} width={b.w} height={b.d} fill="white" />
      {editable && <rect x={b.x} y={Y(b.y + b.d)} width={b.w} height={b.d} fill="url(#grid1)" />}
      <rect x={b.x} y={Y(b.y + b.d)} width={b.w} height={b.d} fill="none" stroke="#f97316" strokeWidth="0.18" strokeDasharray="0.8 0.5" />

      {/* rooms */}
      {rooms.map((r) => {
        const x = b.x + r.x, y = Y(b.y + r.y + r.d);
        const isSel = r.id === selected;
        const small = Math.min(r.w, r.d) < 6;
        return (
          <g key={r.id} onPointerDown={(e) => startDrag(e, r.id, "move")} style={{ cursor: editable ? "move" : "default" }}>
            <rect x={x} y={y} width={r.w} height={r.d} fill={ROOM_FILL[r.type] || "#fff"} stroke={isSel ? "#1d5ae0" : "#94a3b8"}
              strokeWidth={isSel ? 0.3 : 0.08} />
            {highlight?.[r.id] && <rect x={x + 0.15} y={y + 0.15} width={Math.max(0, r.w - 0.3)} height={Math.max(0, r.d - 0.3)} fill="none"
              stroke={highlight[r.id]} strokeWidth="0.45" strokeDasharray="1 0.5" />}
            <text x={x + r.w / 2} y={y + r.d / 2 - (small ? 0 : fs * 0.25)} textAnchor="middle" fontSize={small ? fs * 0.62 : fs * 0.85} fontWeight="700" fill="#0f172a">
              {r.w < 5.5 && r.name.length > 8 ? r.name.split(" ")[0] : r.name}
            </text>
            {!small && <text x={x + r.w / 2} y={y + r.d / 2 + fs * 0.85} textAnchor="middle" fontSize={fs * 0.7} fill="#475569">{`${r.w}' × ${r.d}'`}</text>}
          </g>
        );
      })}

      {/* walls & openings (derived) */}
      {!stale && <g pointerEvents="none">
        {lv.walls.map((w, i) => wallRect(w, `w${i}`, w.kind === "parapet" ? "#65a30d" : w.kind === "int115" ? "#475569" : "#1e293b"))}
        {lv.openings.map((o) => {
          if (o.type === "window" || o.type === "vent") return wallRect({ ...o, kind: "ext" }, o.id, "#38bdf8", 0.5);
          const g = wallRect({ ...o, kind: "ext" }, o.id + "g", "white", 0.9);
          return <g key={o.id}>{g}{wallRect({ ...o, kind: "ext" }, o.id + "l", o.type === "main_door" ? "#f97316" : "#94a3b8", 0.18)}</g>;
        })}
      </g>}
      {stale && rooms.map((r) => <rect key={"o" + r.id} pointerEvents="none" x={b.x + r.x} y={Y(b.y + r.y + r.d)} width={r.w} height={r.d} fill="none" stroke="#1e293b" strokeWidth="0.35" />)}

      {/* selection handles */}
      {editable && sel && (() => {
        const x = b.x + sel.x, y = Y(b.y + sel.y + sel.d), h = 0.9;
        const hs: [DragState["mode"], number, number, string][] = [["e", x + sel.w, y + sel.d / 2, "ew-resize"], ["w", x, y + sel.d / 2, "ew-resize"],
          ["n", x + sel.w / 2, y, "ns-resize"], ["s", x + sel.w / 2, y + sel.d, "ns-resize"]];
        return hs.map(([m, cx, cy, cur]) => (
          <rect key={m} x={cx - h / 2} y={cy - h / 2} width={h} height={h} rx={0.15} fill="#1d5ae0" stroke="white" strokeWidth="0.12"
            style={{ cursor: cur }} onPointerDown={(e) => startDrag(e, sel.id, m)} />
        ));
      })()}

      {/* dimensions */}
      {showDims && <g fontSize={fs * 0.75} fill="#c2410c" pointerEvents="none">
        <line x1={b.x} y1={-3.2} x2={b.x + b.w} y2={-3.2} stroke="#64748b" strokeWidth="0.08" />
        <text x={b.x + b.w / 2} y={-3.8} textAnchor="middle" fill="#334155">{`${b.w}'`} building</text>
        <line x1={plot.w + 3.2} y1={Y(b.y)} x2={plot.w + 3.2} y2={Y(b.y + b.d)} stroke="#64748b" strokeWidth="0.08" />
        <text x={plot.w + 4.2} y={Y(b.y + b.d / 2)} fill="#334155" transform={`rotate(90 ${plot.w + 4.2} ${Y(b.y + b.d / 2)})`} textAnchor="middle">{`${b.d}'`}</text>
        {sb.ft.front > 0 && <text x={plot.w / 2} y={D - b.y / 2 + fs * 0.3} textAnchor="middle">front {sb.ft.front}' ({sb.m.front} m)</text>}
        {sb.ft.rear > 0 && <text x={plot.w / 2} y={(plot.d - b.y - b.d) / 2 + fs * 0.3} textAnchor="middle">rear {sb.ft.rear}'</text>}
        {sb.ft.left > 0 && <text x={b.x / 2} y={D / 2} textAnchor="middle" transform={`rotate(-90 ${b.x / 2} ${D / 2})`}>side {sb.ft.left}'</text>}
        {sb.ft.right > 0 && <text x={plot.w - sb.ft.right / 2} y={D / 2} textAnchor="middle" transform={`rotate(90 ${plot.w - sb.ft.right / 2} ${D / 2})`}>side {sb.ft.right}'</text>}
        <text x={-M + 0.6} y={D + 0.8} fill="#334155">{`Plot ${plot.w}' × ${plot.d}'`}</text>
      </g>}

      {vastuGrid && <g pointerEvents="none">
        {[1, 2].map((i) => <line key={"vx" + i} x1={b.x + (b.w * i) / 3} y1={Y(b.y)} x2={b.x + (b.w * i) / 3} y2={Y(b.y + b.d)} stroke="#f97316" strokeWidth="0.12" strokeDasharray="0.8 0.6" />)}
        {[1, 2].map((i) => <line key={"vy" + i} x1={b.x} y1={Y(b.y + (b.d * i) / 3)} x2={b.x + b.w} y2={Y(b.y + (b.d * i) / 3)} stroke="#f97316" strokeWidth="0.12" strokeDasharray="0.8 0.6" />)}
        {[0, 1, 2].flatMap((i) => [0, 1, 2].map((j) => {
          const zx = (i - 1) * 2 / 3, zy = (j - 1) * 2 / 3;
          let z = "C";
          if (i !== 1 || j !== 1) {
            const e = zx * plan.compass.right[0] + zy * plan.compass.up[0], n = zx * plan.compass.right[1] + zy * plan.compass.up[1];
            const ang = (Math.atan2(e, n) * 180 / Math.PI + 360) % 360;
            z = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"][Math.floor(((ang + 22.5) % 360) / 45)];
          }
          return <text key={`z${i}${j}`} x={b.x + (b.w * i) / 3 + 0.6} y={Y(b.y + (b.d * (j + 1)) / 3) + fs * 0.9} fontSize={fs * 0.75} fontWeight="800" fill="#ea580c" opacity="0.85">{z}</text>;
        }))}
      </g>}

      {/* north arrow */}
      <g transform={`translate(${plot.w + M - 3.5} ${-M + 4})`} pointerEvents="none">
        <circle r="2.6" fill="white" stroke="#cbd5e1" strokeWidth="0.1" />
        <line x1={-nx * 1.9} y1={-ny * 1.9} x2={nx * 1.9} y2={ny * 1.9} stroke="#0f172a" strokeWidth="0.25" />
        <circle cx={nx * 1.9} cy={ny * 1.9} r="0.45" fill="#ef4444" />
        <text x={nx * 1.9 + nx * 1.3} y={ny * 1.9 + ny * 1.3 + 0.45} fontSize="1.3" textAnchor="middle" fontWeight="800" fill="#ef4444">N</text>
      </g>
    </svg>
  );
}
