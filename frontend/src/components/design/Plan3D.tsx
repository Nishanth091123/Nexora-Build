import { useMemo, useRef, useState } from "react";
import { ROOM_FILL, WALL_T, type Plan } from "../../lib/plan";

type Face = { pts: [number, number][]; fill: string; depth: number; stroke?: string; order: number; lvl: number; floor?: boolean };

const shade = (hex: string, k: number) => {
  const n = parseInt(hex.slice(1), 16);
  const c = (v: number) => Math.max(0, Math.min(255, Math.round(v * k)));
  return `rgb(${c((n >> 16) & 255)},${c((n >> 8) & 255)},${c(n & 255)})`;
};

/** Simple 3D preview drawn in SVG: walls extruded per floor (door / window gaps kept), slabs, parapets. */
export default function Plan3D({ plan, showRoof = false, visibleLevels }: { plan: Plan; showRoof?: boolean; visibleLevels?: number }) {
  const [yaw, setYaw] = useState(35);
  const [pitch, setPitch] = useState(32);
  const drag = useRef<{ x: number; y: number; yaw: number; pitch: number } | null>(null);
  const H = plan.floor_height_ft || 10;
  const nLv = Math.min(plan.levels.length, visibleLevels ?? plan.levels.length);

  const faces = useMemo(() => {
    const out: Face[] = [];
    const t = (yaw * Math.PI) / 180, p = (pitch * Math.PI) / 180;
    const ct = Math.cos(t), st = Math.sin(t), sp = Math.sin(p), cp = Math.cos(p);
    const cx = plan.building.w / 2, cy = plan.building.d / 2;
    const proj = (x: number, y: number, z: number): [number, number, number] => {
      const X = (x - cx) * ct - (y - cy) * st;
      const Yd = (x - cx) * st + (y - cy) * ct; // depth away from the viewer
      return [X, -(Yd * sp + z * cp), Yd];
    };
    let order = 0;
    const box = (x0: number, y0: number, x1: number, y1: number, z0: number, z1: number, col: string, lvl: number) => {
      const c = [[x0, y0], [x1, y0], [x1, y1], [x0, y1]] as [number, number][];
      const sides: [number, number][] = [[0, 1], [1, 2], [2, 3], [3, 0]];
      for (const [a, bb] of sides) {
        const pa = c[a], pb = c[bb];
        const pts = [proj(pa[0], pa[1], z0), proj(pb[0], pb[1], z0), proj(pb[0], pb[1], z1), proj(pa[0], pa[1], z1)];
        const dep = pts.reduce((s, q) => s + q[2], 0) / 4;
        const nxv = pb[1] - pa[1], nyv = -(pb[0] - pa[0]); // outward-ish normal for light
        const light = 0.8 + 0.2 * ((nxv * 0.6 + nyv * 0.8) / (Math.hypot(nxv, nyv) || 1));
        out.push({ pts: pts.map((q) => [q[0], q[1]]), fill: shade(col, light), depth: dep, order: order++, lvl });
      }
      const top = c.map((q) => proj(q[0], q[1], z1));
      out.push({ pts: top.map((q) => [q[0], q[1]]), fill: shade(col, 1.08), depth: top.reduce((s, q) => s + q[2], 0) / 4 - 0.01, order: order++, lvl });
    };
    for (let li = 0; li < nLv; li++) {
      const lv = plan.levels[li];
      const z = li * H;
      // floor of each room
      for (const r of lv.rooms) {
        const pts = [proj(r.x, r.y, z), proj(r.x + r.w, r.y, z), proj(r.x + r.w, r.y + r.d, z), proj(r.x, r.y + r.d, z)];
        out.push({ pts: pts.map((q) => [q[0], q[1]]), fill: ROOM_FILL[r.type] || "#ffffff", depth: 0, order: order++, stroke: "#cbd5e1", lvl: li, floor: true });
      }
      // walls with openings cut out
      for (const w of lv.walls) {
        const th = (WALL_T[w.kind] || 0.5) / 2;
        const horiz = w.y1 === w.y2;
        const a0 = horiz ? Math.min(w.x1, w.x2) : Math.min(w.y1, w.y2);
        const a1 = horiz ? Math.max(w.x1, w.x2) : Math.max(w.y1, w.y2);
        const c0 = horiz ? w.y1 : w.x1;
        const top = w.kind === "parapet" ? z + 3 : z + H;
        const ops = lv.openings.filter((o) => (horiz ? o.y1 === o.y2 && Math.abs(o.y1 - c0) < 0.01 : o.x1 === o.x2 && Math.abs(o.x1 - c0) < 0.01))
          .map((o) => ({ s: horiz ? Math.min(o.x1, o.x2) : Math.min(o.y1, o.y2), e: horiz ? Math.max(o.x1, o.x2) : Math.max(o.y1, o.y2), o }))
          .filter((o) => o.e > a0 + 0.01 && o.s < a1 - 0.01).sort((p1, p2) => p1.s - p2.s);
        const col = w.kind === "parapet" ? "#b5c99a" : w.kind === "ext" ? "#f1e4d3" : "#fafaf9";
        const seg = (s: number, e: number, zb: number, zt: number, c: string) => {
          if (e - s < 0.02 || zt - zb < 0.02) return;
          if (horiz) box(s, c0 - th, e, c0 + th, zb, zt, c, li);
          else box(c0 - th, s, c0 + th, e, zb, zt, c, li);
        };
        let cur = a0;
        for (const { s, e, o } of ops) {
          seg(cur, Math.max(cur, s), z, top, col);
          const isWin = o.type === "window" || o.type === "vent";
          const sill = isWin ? (o.type === "vent" ? 5.5 : 3) : 0;
          const head = isWin ? sill + o.h : 7;
          seg(Math.max(cur, s), Math.min(e, a1), z, z + sill, col);
          seg(Math.max(cur, s), Math.min(e, a1), z + Math.min(head, H), top, col);
          if (isWin) seg(Math.max(cur, s), Math.min(e, a1), z + sill, z + Math.min(head, H), "#7dd3fc");
          cur = Math.max(cur, e);
        }
        seg(cur, a1, z, top, col);
      }
      // slab above this floor (only for upper floors' floors or roof)
      const showSlab = li < nLv - 1 ? false : showRoof;
      if (showSlab) box(0, 0, plan.building.w, plan.building.d, z + H - 0.4, z + H, "#d6d3d1", li + 0.5);
    }
    out.sort((a, b) => a.lvl - b.lvl || Number(!!b.floor) - Number(!!a.floor) || b.depth - a.depth || a.order - b.order);
    return out;
  }, [plan, yaw, pitch, nLv, showRoof, H]);

  const xs = faces.flatMap((f) => f.pts.map((q) => q[0])), ys = faces.flatMap((f) => f.pts.map((q) => q[1]));
  const minX = Math.min(...xs, 0) - 3, maxX = Math.max(...xs, 0) + 3, minY = Math.min(...ys, 0) - 3, maxY = Math.max(...ys, 0) + 3;
  return (
    <div className="space-y-3">
      <div className="relative overflow-hidden rounded-lg border border-line bg-linear-to-b from-sky-50 to-slate-100">
        <svg viewBox={`${minX} ${minY} ${maxX - minX} ${maxY - minY}`} className="h-[480px] w-full cursor-grab touch-none active:cursor-grabbing"
          onPointerDown={(e) => { (e.target as Element).setPointerCapture?.(e.pointerId); drag.current = { x: e.clientX, y: e.clientY, yaw, pitch }; }}
          onPointerMove={(e) => { const d = drag.current; if (!d) return; setYaw(d.yaw + (e.clientX - d.x) * 0.4); setPitch(Math.max(10, Math.min(80, d.pitch + (e.clientY - d.y) * 0.25))); }}
          onPointerUp={() => { drag.current = null; }}>
          {faces.map((f, i) => (
            <polygon key={i} points={f.pts.map((q) => q.join(",")).join(" ")} fill={f.fill} stroke={f.stroke || "rgba(51,65,85,0.35)"} strokeWidth="0.05" strokeLinejoin="round" />
          ))}
        </svg>
        <div className="absolute bottom-2 left-3 text-xs text-slate-500">Drag to rotate · concept massing (walls, openings, parapet)</div>
      </div>
      <div className="flex flex-wrap items-center gap-3 text-sm">
        <button className="btn-outline btn-sm" onClick={() => setYaw(yaw - 45)}>⟲ 45°</button>
        <button className="btn-outline btn-sm" onClick={() => setYaw(yaw + 45)}>⟳ 45°</button>
        <label className="flex items-center gap-2">Rotate<input type="range" min={-180} max={180} value={((yaw + 540) % 360) - 180} onChange={(e) => setYaw(Number(e.target.value))} /></label>
        <label className="flex items-center gap-2">Tilt<input type="range" min={10} max={80} value={pitch} onChange={(e) => setPitch(Number(e.target.value))} /></label>
        <button className="btn-ghost btn-sm" onClick={() => { setYaw(35); setPitch(32); }}>Reset view</button>
      </div>
    </div>
  );
}
