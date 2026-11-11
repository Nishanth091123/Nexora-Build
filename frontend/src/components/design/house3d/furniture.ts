/** 1.21 – Furniture engine. ONE set of rules decides what goes in every room and where, straight from the plan
 *  (room sizes, doors, windows, open sides). The 2D rendered plan and the 3D model both draw from this list, so
 *  they always match. Rules: nothing in a door swing or a walking gap, tall pieces never in front of a window,
 *  small rooms get smaller pieces (or none) – nothing is ever squeezed in. Pure (no three.js). Units: feet,
 *  building coordinates (x → right, y → away from the road). */
import type { Plan } from "../../../lib/plan";

type Lv = Plan["levels"][number];
type Room = Lv["rooms"][number];
export type Side = "s" | "n" | "w" | "e";
export type Rect = { x0: number; y0: number; x1: number; y1: number };
/** (x, y, w, d) = the piece's footprint; `back` = the wall side it stands against (its local v = 0 edge) */
export type FItem = { kind: string; room: string; x: number; y: number; w: number; d: number; back: Side; v?: string; n?: number;
  /** flat = lies on the floor under other things (rug, shower tray); top = sits on a counter (sink, hob) */
  flat?: boolean; top?: boolean };

const EPS = 0.05, INSET = 0.42;
const OPP: Record<Side, Side> = { s: "n", n: "s", w: "e", e: "w" };
const SIDES: Side[] = ["s", "n", "w", "e"];
const isWin = (t: string) => t === "window" || t === "vent";
const hit = (a: Rect, b: Rect, pad = 0) => a.x0 < b.x1 + pad - 0.02 && a.x1 > b.x0 - pad + 0.02 && a.y0 < b.y1 + pad - 0.02 && a.y1 > b.y0 - pad + 0.02;

/** local (u along the back wall, v out from it) → building coordinates */
export function localToWorld(it: { x: number; y: number; w: number; d: number; back: Side }, u: number, v: number): [number, number] {
  switch (it.back) {
    case "s": return [it.x + u, it.y + v];
    case "n": return [it.x + it.w - u, it.y + it.d - v];
    case "w": return [it.x + v, it.y + it.d - u];
    default: return [it.x + it.w - v, it.y + u];
  }
}
/** size in the local frame: [along the wall, out from the wall] */
export const localSize = (it: { w: number; d: number; back: Side }): [number, number] => (it.back === "s" || it.back === "n" ? [it.w, it.d] : [it.d, it.w]);

class RoomCtx {
  inner: Rect; keep: Rect[] = []; placed: Rect[] = []; items: FItem[] = [];
  wins: Record<Side, [number, number][]> = { s: [], n: [], w: [], e: [] };
  doors: Record<Side, [number, number][]> = { s: [], n: [], w: [], e: [] };
  doorAt: [number, number] | null = null;
  constructor(public r: Room, lv: Lv) {
    const wet = r.type === "toilet" || r.type === "common_toilet";
    this.inner = { x0: r.x + INSET, y0: r.y + INSET, x1: r.x + r.w - INSET, y1: r.y + r.d - INSET };
    const edge = (side: Side) => (side === "s" ? r.y : side === "n" ? r.y + r.d : side === "w" ? r.x : r.x + r.w);
    const span = (side: Side): [number, number] => (side === "s" || side === "n" ? [r.x, r.x + r.w] : [r.y, r.y + r.d]);
    const strip = (side: Side, a: number, b: number, depth: number): Rect =>
      side === "s" ? { x0: a, x1: b, y0: r.y, y1: r.y + depth } : side === "n" ? { x0: a, x1: b, y0: r.y + r.d - depth, y1: r.y + r.d }
        : side === "w" ? { x0: r.x, x1: r.x + depth, y0: a, y1: b } : { x0: r.x + r.w - depth, x1: r.x + r.w, y0: a, y1: b };
    for (const side of SIDES) {
      const horiz = side === "s" || side === "n", c = edge(side), [e0, e1] = span(side);
      // doors & windows on this edge
      for (const op of lv.openings) {
        const oh = Math.abs(op.y1 - op.y2) < 1e-6;
        if (oh !== horiz || Math.abs((oh ? op.y1 : op.x1) - c) > EPS) continue;
        const a = oh ? Math.min(op.x1, op.x2) : Math.min(op.y1, op.y2), b = oh ? Math.max(op.x1, op.x2) : Math.max(op.y1, op.y2);
        if (Math.min(b, e1) - Math.max(a, e0) < 0.3) continue;
        if (isWin(op.type)) { if (op.type === "window") this.wins[side].push([a, b]); continue; }
        this.doors[side].push([a, b]);
        const mine = op.room === r.id;  // the leaf swings into its own room; the other side only needs a walking gap
        const small = Math.min(r.w, r.d) <= 6;  // small rooms: the leaf opens against the side wall – keep only the way in
        const depth = wet ? 1.7 : small ? 2.0 : mine ? Math.min(b - a + 0.3, 3.3) : 1.8;
        this.keep.push(strip(side, a - 0.15, b + 0.15, depth + INSET));
        if (!this.doorAt || op.type === "main_door" || mine) this.doorAt = horiz ? [(a + b) / 2, c] : [c, (a + b) / 2];
      }
      // open stretches (no wall on this edge → the room flows into the next one): keep a way through
      const walls = lv.walls.filter((w) => (horiz ? Math.abs(w.y1 - w.y2) < 1e-6 && Math.abs(w.y1 - c) < EPS : Math.abs(w.x1 - w.x2) < 1e-6 && Math.abs(w.x1 - c) < EPS))
        .map((w) => (horiz ? [Math.min(w.x1, w.x2), Math.max(w.x1, w.x2)] : [Math.min(w.y1, w.y2), Math.max(w.y1, w.y2)]) as [number, number])
        .sort((p, q) => p[0] - q[0]);
      let cur = e0;
      for (const [a, b] of [...walls, [e1, e1] as [number, number]]) {
        if (a - cur > 1.2) { this.keep.push(strip(side, cur, Math.min(a, e1), 1.2 + INSET)); this.doors[side].push([cur, Math.min(a, e1)]); }
        cur = Math.max(cur, b);
        if (cur >= e1) break;
      }
    }
    // a room drawn inside this one (rare) is never furnished over
    for (const q of lv.rooms) {
      if (q.id === r.id) continue;
      const o: Rect = { x0: q.x, y0: q.y, x1: q.x + q.w, y1: q.y + q.d };
      if (hit(o, this.inner, -0.3)) this.keep.push(o);
    }
  }
  get W() { return this.inner.x1 - this.inner.x0; }
  get D() { return this.inner.y1 - this.inner.y0; }
  range(side: Side): [number, number] { return side === "s" || side === "n" ? [this.inner.x0, this.inner.x1] : [this.inner.y0, this.inner.y1]; }
  across(side: Side) { return side === "s" || side === "n" ? this.D : this.W; }
  foot(side: Side, a: number, W: number, D: number): Rect {
    const i = this.inner;
    return side === "s" ? { x0: a, x1: a + W, y0: i.y0, y1: i.y0 + D } : side === "n" ? { x0: a, x1: a + W, y0: i.y1 - D, y1: i.y1 }
      : side === "w" ? { x0: i.x0, x1: i.x0 + D, y0: a, y1: a + W } : { x0: i.x1 - D, x1: i.x1, y0: a, y1: a + W };
  }
  ok(q: Rect, clear = 0.25) {
    const i = this.inner;
    if (q.x0 < i.x0 - 0.02 || q.y0 < i.y0 - 0.02 || q.x1 > i.x1 + 0.02 || q.y1 > i.y1 + 0.02) return false;
    return !this.keep.some((k) => hit(q, k)) && !this.placed.some((p) => hit(q, p, clear));
  }
  winClash(side: Side, a: number, b: number) { return this.wins[side].some(([s, e]) => Math.min(b, e) - Math.max(a, s) > 0.3); }
  add(kind: string, q: Rect, back: Side, extra: Partial<FItem> = {}, block = true) {
    const it: FItem = { kind, room: this.r.id, x: +q.x0.toFixed(3), y: +q.y0.toFixed(3), w: +(q.x1 - q.x0).toFixed(3), d: +(q.y1 - q.y0).toFixed(3), back, ...extra };
    this.items.push(it);
    if (block) this.placed.push(q);
    return it;
  }
  /** walls in the order they suit a piece: no door first, then (for tall pieces) no window, then the longer wall */
  order(noWin: boolean, prefer?: Side[]): Side[] {
    const score = (s: Side) => (prefer ? (prefer.indexOf(s) >= 0 ? 40 - prefer.indexOf(s) * 6 : 0) : 0)
      + (this.doors[s].length ? 0 : 10) + (noWin && this.wins[s].length ? 0 : 5) + (this.range(s)[1] - this.range(s)[0]) / 20;
    return [...SIDES].sort((a, b) => score(b) - score(a));
  }
  /** stand a W × D piece against a wall. at = wanted centre along the wall (default: middle); ends = try the corners first */
  wall(kind: string, W: number, D: number, o: { sides?: Side[]; prefer?: Side[]; noWin?: boolean; at?: number; ends?: boolean; clear?: number; extra?: Partial<FItem>; far?: boolean } = {}): FItem | null {
    for (const side of o.sides || this.order(!!o.noWin, o.prefer)) {
      const [lo, hi] = this.range(side);
      if (hi - lo < W - 0.01 || this.across(side) < D + 0.5) continue;
      let targets: number[];
      if (o.at != null) targets = [o.at - W / 2];
      else if (o.far && this.doorAt) {  // as far from the door as possible
        const dc = side === "s" || side === "n" ? this.doorAt[0] : this.doorAt[1];
        targets = [dc - lo > hi - dc ? lo : hi - W];
      } else if (o.ends) targets = [lo, hi - W];
      else targets = [(lo + hi - W) / 2];
      const cand: number[] = [];
      for (let a = lo; a <= hi - W + 0.001; a += 0.25) cand.push(a);
      cand.push(hi - W);
      cand.sort((p, q) => Math.min(...targets.map((t) => Math.abs(p - t))) - Math.min(...targets.map((t) => Math.abs(q - t))));
      for (const a of cand) {
        if (o.noWin && this.winClash(side, a, a + W)) continue;
        const q = this.foot(side, a, W, D);
        if (this.ok(q, o.clear)) return this.add(kind, q, side, o.extra);
      }
    }
    return null;
  }
  /** longest free stretch along a wall for a strip `D` deep (counters, shelves, wardrobes) */
  run(side: Side, D: number, noWin = false): [number, number] | null {
    const [lo, hi] = this.range(side);
    if (this.across(side) < D + 1.4) return null;
    let best: [number, number] | null = null, s: number | null = null;
    const step = 0.25;
    for (let a = lo; a <= hi + 0.001; a += step) {
      const free = a + step <= hi + 0.001 && this.ok(this.foot(side, a, step, D), 0) && !(noWin && this.winClash(side, a - 0.3, a + step + 0.3));
      if (free && s == null) s = a;
      if (!free && s != null) { if (!best || a - s > best[1] - best[0]) best = [s, a]; s = null; }
    }
    return best;
  }
  /** free-standing piece near (cx, cy) */
  free(kind: string, W: number, D: number, cx: number, cy: number, back: Side, o: { reach?: number; clear?: number; extra?: Partial<FItem>; block?: boolean } = {}): FItem | null {
    const reach = o.reach ?? 3;
    const pts: [number, number][] = [];
    for (let dx = -reach; dx <= reach + 0.01; dx += 0.5) for (let dy = -reach; dy <= reach + 0.01; dy += 0.5) pts.push([dx, dy]);
    pts.sort((a, b) => Math.hypot(a[0], a[1]) - Math.hypot(b[0], b[1]));
    for (const [dx, dy] of pts) {
      const q = { x0: cx + dx - W / 2, y0: cy + dy - D / 2, x1: cx + dx + W / 2, y1: cy + dy + D / 2 };
      if (this.ok(q, o.clear ?? 0.4)) return this.add(kind, q, back, o.extra, o.block ?? true);
    }
    return null;
  }
}

const centreAlong = (it: FItem) => (it.back === "s" || it.back === "n" ? it.x + it.w / 2 : it.y + it.d / 2);

// ------------------------------------------------------------------ room recipes
function bedroom(c: RoomCtx) {
  const sizes: [number, number, string][] = [[6, 6.6, "king"], [5, 6.6, "queen"], [4, 6.4, "double"], [3.2, 6.3, "single"]];
  let bed: FItem | null = null;
  for (const [W, D, v] of sizes) {
    if (v !== "single" && Math.min(c.W, c.D) < 7.5) continue;
    const fit = (s: Side) => c.range(s)[1] - c.range(s)[0] >= W + (v === "single" ? 0.5 : 2) && c.across(s) >= D + 2;
    const sides = c.order(false).filter(fit);
    if (!sides.length) continue;
    // head against a wall without a window when there is one
    sides.sort((a, b) => Number(c.wins[a].length > 0) - Number(c.wins[b].length > 0) || Number(c.doors[a].length > 0) - Number(c.doors[b].length > 0));
    bed = c.wall("bed", W, D, { sides, ends: v === "single", extra: { v } });
    if (bed) break;
  }
  if (bed && bed.v !== "single") {
    const [bw] = localSize(bed);
    for (const sgn of [-1, 1]) {
      const at = centreAlong(bed) + sgn * (bw / 2 + 0.85);
      c.wall("side_table", 1.5, 1.5, { sides: [bed.back], at, clear: 0.05 });
    }
  }
  for (const W of [6, 5, 4, 3]) if (c.wall("wardrobe", W, 2, { noWin: true, ends: true, extra: { n: Math.round(W / 1.5) } })) break;
  if (c.W * c.D >= 105) {
    const want = SIDES.filter((s) => c.wins[s].length);  // a desk likes the window
    c.wall("desk", 3.6, 3.5, { prefer: want, ends: true });
  }
}

function living(c: RoomCtx, lv: Lv) {
  let sofa: FItem | null = null;
  for (const [W, n] of [[7.2, 3], [5.6, 2]] as [number, number][]) {
    const sides = c.order(false).filter((s) => c.range(s)[1] - c.range(s)[0] >= W + 1 && c.across(s) >= 7.5);
    if (!sides.length) continue;
    sofa = c.wall("sofa", W, 2.9, { sides, extra: { n } });
    if (sofa) break;
  }
  if (!sofa) { c.wall("armchair", 2.7, 2.7, { ends: true }); return; }
  const [sw] = localSize(sofa);
  const at = centreAlong(sofa);
  const tv = c.wall("tv_unit", Math.min(6, sw), 1.5, { sides: [OPP[sofa.back]], at, noWin: true })
    || c.wall("tv_unit", 4.5, 1.5, { sides: [OPP[sofa.back]], at }) || c.wall("tv_unit", 4.5, 1.5, { noWin: true }) || c.wall("tv_unit", 3.5, 1.5, {});
  // coffee table + rug in front of the sofa
  const gap = c.across(sofa.back) - 2.9 - (tv && tv.back === OPP[sofa.back] ? 1.5 : 0);
  if (gap >= 5.2) {
    const [cx, cy] = localToWorld(sofa, sw / 2, 2.9 + 1.3 + 1.0);
    const horiz = sofa.back === "s" || sofa.back === "n";
    const tw = Math.min(3.4, sw - 2.4);
    const t = c.free("coffee_table", horiz ? tw : 2, horiz ? 2 : tw, cx, cy, sofa.back, { reach: 0.5, clear: 0.9 });
    if (t) {
      const rw = Math.min(sw + 0.6, 8), rd = Math.min(gap - 0.6, 6);
      const [rx, ry] = localToWorld(sofa, sw / 2, 2.0 + rd / 2);
      c.add("rug", horiz ? { x0: rx - rw / 2, x1: rx + rw / 2, y0: ry - rd / 2, y1: ry + rd / 2 } : { x0: rx - rd / 2, x1: rx + rd / 2, y0: ry - rw / 2, y1: ry + rw / 2 }, sofa.back, { flat: true }, false);
    }
  }
  if (Math.min(c.W, c.D) >= 10.5) {  // an armchair beside the sofa set
    const horiz = sofa.back === "s" || sofa.back === "n";
    const [px, py] = localToWorld(sofa, 0, 2.9 + 2.4);
    c.wall("armchair", 2.7, 2.7, { sides: (horiz ? ["w", "e"] : ["s", "n"]) as Side[], at: horiz ? py : px, clear: 0.5 });
  }
  // dining set inside a big hall when this house has no separate dining room
  const unit = (c.r as any).unit;
  const hasDining = lv.rooms.some((q) => q.type === "dining" && (q as any).unit === unit);
  if (!hasDining && c.W * c.D >= 190) {
    const [sx, sy] = [sofa.x + sofa.w / 2, sofa.y + sofa.d / 2];
    const i = c.inner;
    const spots: [number, number][] = [[i.x0 + c.W * 0.27, i.y0 + c.D * 0.27], [i.x0 + c.W * 0.73, i.y0 + c.D * 0.27], [i.x0 + c.W * 0.27, i.y0 + c.D * 0.73], [i.x0 + c.W * 0.73, i.y0 + c.D * 0.73]];
    spots.sort((a, b) => Math.hypot(b[0] - sx, b[1] - sy) - Math.hypot(a[0] - sx, a[1] - sy));
    for (const [px, py] of spots.slice(0, 2)) if (c.free("dining", 3.6, 6.4, px, py, "s", { reach: 1.5, clear: 1.4, extra: { n: 4 } }) || c.free("dining", 6.4, 3.6, px, py, "w", { reach: 1.5, clear: 1.4, extra: { n: 4 } })) break;
  }
  for (const s of ["n", "s"] as Side[]) if (c.wall("plant", 1.5, 1.5, { sides: [s], ends: true, clear: 0.3 })) break;
}

function dining(c: RoomCtx) {
  const alongX = c.W >= c.D;
  const i = c.inner, cx = (i.x0 + i.x1) / 2, cy = (i.y0 + i.y1) / 2;
  let ok = false;
  for (const [L, n] of [[5.6, 6], [3.6, 4], [2.6, 2]] as [number, number][]) {
    const dep = n === 2 ? 5.6 : 6.4;
    for (const ax of [alongX, !alongX]) {
      const W = ax ? L : dep, D = ax ? dep : L;
      if (c.W < W + 1.2 || c.D < D + 1.2) continue;
      if (c.free("dining", W, D, cx, cy, ax ? "s" : "w", { reach: 2, clear: 0.6, extra: { n } })) { ok = true; break; }
    }
    if (ok) break;
  }
  if (!ok && c.W >= 4.2 && c.D >= 4.2) ok = !!(c.free("dining", 2.6, 5.6, cx, cy, "s", { reach: 2.5, clear: 0.2, extra: { n: 2 } }) || c.free("dining", 5.6, 2.6, cx, cy, "w", { reach: 2.5, clear: 0.2, extra: { n: 2 } }));
  if (ok && c.W * c.D >= 110) c.wall("sideboard", 4, 1.5, { noWin: true, clear: 0.9 });
}

function kitchen(c: RoomCtx) {
  const D = 2.0;
  const runs = SIDES.map((s) => ({ s, r: c.run(s, D) })).filter((q) => q.r && q.r[1] - q.r[0] >= 4) as { s: Side; r: [number, number] }[];
  if (!runs.length) return;
  // the main counter likes the window wall (sink under the window) and the longest free wall
  runs.sort((a, b) => (c.wins[b.s].length ? 3 : 0) + (b.r[1] - b.r[0]) / 4 - ((c.wins[a.s].length ? 3 : 0) + (a.r[1] - a.r[0]) / 4));
  const main = runs[0];
  let [m0, m1] = main.r;
  // fridge at one end of the main run when the run is long (tall – never in front of the window)
  const winMid = c.wins[main.s].length ? (c.wins[main.s][0][0] + c.wins[main.s][0][1]) / 2 : null;
  let fridgeAt: number | null = null;
  if (m1 - m0 >= 8.5) {
    const atEnd = winMid != null ? Math.abs(winMid - m0) > Math.abs(winMid - m1) : true;
    const a = atEnd ? m0 : m1 - 2.5;
    if (!c.winClash(main.s, a, a + 2.5)) { fridgeAt = a; if (atEnd) m0 += 2.5; else m1 -= 2.5; }
  }
  const mainIt = c.add("counter", c.foot(main.s, m0, m1 - m0, D), main.s);
  if (fridgeAt != null) c.add("fridge", c.foot(main.s, fridgeAt + 0.05, 2.4, 2.4), main.s);
  // second leg (L or parallel kitchen)
  let leg: FItem | null = null;
  const others = SIDES.filter((s) => s !== main.s && (s !== OPP[main.s] || c.across(main.s) >= 8.5));
  let bestLeg: { s: Side; r: [number, number] } | null = null;
  for (const s of others) { const r = c.run(s, D); if (r && r[1] - r[0] >= 3.5 && (!bestLeg || r[1] - r[0] > bestLeg.r[1] - bestLeg.r[0])) bestLeg = { s, r }; }
  if (bestLeg) leg = c.add("counter", c.foot(bestLeg.s, bestLeg.r[0], Math.min(bestLeg.r[1] - bestLeg.r[0], 9), D), bestLeg.s);
  if (fridgeAt == null) c.wall("fridge", 2.4, 2.4, { noWin: true, ends: true, clear: 0 });
  // sink under the window (else a third along), hob on the other leg (else well away from the sink)
  const onTop = (host: FItem, at: number, W: number, kind: string) => {
    const [lo, hi] = [host.back === "s" || host.back === "n" ? host.x : host.y, host.back === "s" || host.back === "n" ? host.x + host.w : host.y + host.d];
    const a = Math.max(lo + 0.3, Math.min(hi - W - 0.3, at - W / 2));
    if (hi - lo < W + 0.6) return null;
    return c.add(kind, c.foot(host.back, a, W, D), host.back, { top: true }, false);
  };
  const sinkAt = winMid != null && winMid > m0 && winMid < m1 ? winMid : m0 + (m1 - m0) * 0.3;
  onTop(mainIt, sinkAt, 2.2, "sink");
  if (leg) { const [lw] = localSize(leg); const lo = leg.back === "s" || leg.back === "n" ? leg.x : leg.y; onTop(leg, lo + lw / 2, 2.2, "hob"); }
  else if (m1 - m0 >= 6.5) onTop(mainIt, sinkAt - m0 > m1 - sinkAt ? m0 + 1.5 : m1 - 1.5, 2.2, "hob");
}

function toilet(c: RoomCtx) {
  const long = Math.max(c.W, c.D), short = Math.min(c.W, c.D);
  if (short < 2.6 || long < 3.6) return;
  // WC away from the door, basin near it, shower in the corner that is left (only when there is room for it)
  const wc = c.wall("wc", 1.7, 2.4, { far: true, clear: 0.15 }) || c.wall("wc", 1.6, 2.2, { far: true, clear: 0 }) || c.wall("wc", 1.6, 2.2, { clear: 0 });
  const near = (s: Side) => { if (!c.doorAt) return undefined; const [lo, hi] = c.range(s); const dc = s === "s" || s === "n" ? c.doorAt[0] : c.doorAt[1]; return Math.max(lo, Math.min(hi, dc)); };
  let basin: FItem | null = null;
  for (const s of wc ? [wc.back, ...SIDES.filter((q) => q !== wc.back)] : SIDES) { basin = c.wall("basin", 1.8, 1.4, { sides: [s], at: near(s), clear: 0.2 }); if (basin) break; }
  if (!basin) c.wall("basin", 1.5, 1.2, { clear: 0, ends: true });
  if (long >= 6.3) for (const S of [3, 2.6, 2.2]) { if (S > short + 0.01) continue; if (c.wall("shower", S, S, { far: true, clear: 0.1, extra: { flat: true } })) break; }
}

function rackRoom(c: RoomCtx, kind: string, D: number, max = 2) {
  const runs = SIDES.map((s) => ({ s, r: c.run(s, D, kind === "wardrobe") })).filter((q) => q.r && q.r[1] - q.r[0] >= 2.5) as { s: Side; r: [number, number] }[];
  runs.sort((a, b) => b.r[1] - b.r[0] - (a.r[1] - a.r[0]));
  let n = 0;
  for (const { s } of runs) {
    if (n >= max) break;
    const r = c.run(s, D, kind === "wardrobe");  // again – the first rack may have taken a corner
    if (!r || r[1] - r[0] < 2.5) continue;
    const W = Math.min(r[1] - r[0], 10);
    c.add(kind, c.foot(s, r[0], W, D), s, { n: Math.max(1, Math.round(W / 1.5)) }); n++;
  }
}

function openSit(c: RoomCtx, big: boolean) {
  const short = Math.min(c.W, c.D);
  if (short >= 3.6 && Math.max(c.W, c.D) >= 6) c.wall("sitset", 5.2, 2.6, { clear: 0.3 }) || c.wall("sitset", 5.2, 2.6, { sides: SIDES, clear: 0 });
  else if (short >= 2.6) c.wall("chair", 2, 2, { ends: true });
  let n = 0;
  for (const s of SIDES) { if (n >= (big ? 3 : 2)) break; if (c.wall("planter", 1.4, 1.4, { sides: [s], ends: true, clear: 0.2 })) n++; }
}

function parking(c: RoomCtx) {
  const r = c.r;
  const put = (kind: string, q: Rect, back: Side) => c.add(kind, q, back);
  if (r.d >= 14.5 && r.w >= 8) {  // nose to the road
    const n = r.w >= 17 ? 2 : 1, L = Math.min(14.6, r.d - 1), slot = r.w / n;
    for (let k = 0; k < n; k++) { const cx = r.x + slot * (k + 0.5), y0 = r.y + Math.min(1.2, (r.d - L) / 2); put("car", { x0: cx - 3, x1: cx + 3, y0, y1: y0 + L }, "n"); }
    if (n === 1 && r.w >= 12.5) put("bike", { x0: r.x + r.w - 3.3, x1: r.x + r.w - 0.9, y0: r.y + r.d - 7.6, y1: r.y + r.d - 1 }, "n");
  } else if (r.w >= 14.5 && r.d >= 8) {
    const L = Math.min(14.6, r.w - 1), cy = r.y + r.d / 2, x0 = r.x + (r.w - L) / 2;
    put("car", { x0, x1: x0 + L, y0: cy - 3, y1: cy + 3 }, "e");
  } else if (r.d >= 7.5 && r.w >= 4) {
    const n = Math.min(3, Math.floor((r.w - 1) / 3));
    for (let k = 0; k < n; k++) { const cx = r.x + 1 + 1.5 + k * 3; put("bike", { x0: cx - 1.2, x1: cx + 1.2, y0: r.y + 0.8, y1: r.y + 7.4 }, "n"); }
  } else if (r.w >= 7.5 && r.d >= 4) put("bike", { x0: r.x + 0.8, x1: r.x + 7.4, y0: r.y + r.d / 2 - 1.2, y1: r.y + r.d / 2 + 1.2 }, "e");
}

/** every piece of furniture for one floor – from the plan alone */
export function furnitureFor(lv: Lv): FItem[] {
  const out: FItem[] = [];
  for (const r of lv.rooms) {
    if (r.w < 2.5 || r.d < 2.5) continue;
    const c = new RoomCtx(r, lv);
    switch (r.type) {
      case "bedroom": bedroom(c); break;
      case "hall": case "lounge": living(c, lv); break;
      case "dining": dining(c); break;
      case "kitchen": kitchen(c); break;
      case "toilet": case "common_toilet": toilet(c); break;
      case "pooja": { const W = Math.min(3.2, Math.min(c.W, c.D) - 0.3); if (W >= 1.5) c.wall("mandapam", W, Math.min(1.7, W), { prefer: SIDES.filter((s) => c.doors[OPP[s]].length), clear: 0 }) || c.wall("mandapam", Math.min(W, 2.2), 1.4, { prefer: SIDES.filter((s) => c.doors[OPP[s]].length), clear: 0 }); break; }
      case "store": rackRoom(c, "shelf", 1.3); break;
      case "dress": rackRoom(c, "wardrobe", 1.7, 2); break;
      case "utility": c.wall("washer", 2.3, 2.3, { ends: true, clear: 0.1 }); c.wall("wash_sink", 2.2, 1.7, { ends: true, clear: 0.2 }); break;
      case "balcony": case "sitout": openSit(c, false); break;
      case "terrace": if (r.w * r.d >= 60) openSit(c, true); break;
      case "parking": parking(c); break;
      default: break;  // stairs, passages, open stilt: nothing stands in the way
    }
    out.push(...c.items);
  }
  return out;
}

// ------------------------------------------------------------------ staircase (same flights as the 3D model)
export type StairPlan = { steps: Rect[]; landing: Rect | null; arrow: [number, number][]; label: string };
export function stairPlan(plan: Plan, r: Room): StairPlan | null {
  if (Math.max(r.d, r.w) < 7 || Math.min(r.d, r.w) < 3) return null;
  const so: any = (plan as any).stair || {};
  const H = plan.floor_height_ft || 10;
  const steps = Math.max(8, Math.ceil((H * 304.8) / (Number(so.riser_mm) || 175) - 1e-6));
  const along = r.d >= r.w;
  const Lu = along ? r.d : r.w, Lw = along ? r.w : r.d;
  const U = (u: number, v: number): [number, number] => (along ? [r.x + v, r.y + u] : [r.x + u, r.y + Lw - v]);
  const rect = (u0: number, v0: number, u1: number, v1: number): Rect => {
    const [xa, ya] = U(u0, v0), [xb, yb] = U(u1, v1);
    return { x0: Math.min(xa, xb), y0: Math.min(ya, yb), x1: Math.max(xa, xb), y1: Math.max(ya, yb) };
  };
  const out: StairPlan = { steps: [], landing: null, arrow: [], label: `${steps}R` };
  if (so.type === "straight") {
    const run = Math.min((Number(so.tread_mm) || 250) / 304.8, (Lu - 0.6) / steps);
    for (let k = 0; k < steps; k++) out.steps.push(rect(0.3 + k * run, 0.1, 0.3 + (k + 1) * run, Lw - 0.1));
    out.arrow = [U(0.4, Lw / 2), U(0.3 + steps * run - 0.2, Lw / 2)];
    return out;
  }
  const half = Math.ceil(steps / 2), land = Math.min(3.0, Lw / 2 + 0.3);
  const run = Math.min((Number(so.tread_mm) || 250) / 304.8, (Lu - land - 0.5) / half);
  const vHalf = Lw / 2 - 0.1, uL = 0.5 + half * run;
  for (let k = 0; k < half; k++) out.steps.push(rect(0.5 + k * run, 0.1, 0.5 + (k + 1) * run, 0.1 + vHalf));
  out.landing = rect(uL, 0.1, Math.min(Lu - 0.1, uL + land), Lw - 0.1);
  for (let k = 0; k < steps - half; k++) out.steps.push(rect(uL - (k + 1) * run, Lw / 2, uL - k * run, Lw - 0.1));
  const m1 = 0.1 + vHalf / 2, m2 = (Lw / 2 + Lw - 0.1) / 2, uT = Math.min(Lu - 0.1, uL + land) - (Math.min(Lu - 0.1, uL + land) - uL) / 2;
  out.arrow = [U(0.6, m1), U(uT, m1), U(uT, m2), U(uL - (steps - half) * run + 0.3, m2)];
  return out;
}

// ------------------------------------------------------------------ the site around the house (same rules as the 3D model)
export type SiteLayout = {
  gate: { x: number; w: number }; park: Room | null; door: { x: number; y: number } | null;
  house: Rect; blocked: (x: number, y: number, r: number) => boolean; clear: (x: number, y: number, r: number) => boolean; ov: number;
};
export function siteLayout(plan: Plan, style: string): SiteLayout {
  const P = plan.plot, b = plan.building, lv0 = plan.levels[0];
  const ov = style === "modern" || style === "luxury" ? 2.25 : style === "contemporary" ? 1.4 : style === "traditional" ? 0.6 : 0.4;
  const park = lv0.rooms.find((r) => r.type === "parking") || null;
  const md = lv0.openings.find((q) => q.type === "main_door");
  const gateW = park ? Math.min(Math.max(10, park.w), P.w * 0.5) : Math.min(12, P.w * 0.4);
  let gx = park ? Math.min(Math.max(b.x + park.x + park.w / 2 - gateW / 2, 1.5), P.w - gateW - 1.5) : P.w / 2 - gateW / 2;
  const poly: number[][] | null = P.poly && P.poly.length >= 3 ? P.poly : null;
  if (poly) { const fx0 = Math.min(poly[0][0], poly[1][0]), fx1 = Math.max(poly[0][0], poly[1][0]); gx = Math.min(Math.max(gx, fx0 + 1.5), fx1 - gateW - 1.5); }
  const house: Rect = { x0: Infinity, y0: Infinity, x1: -Infinity, y1: -Infinity };
  for (const lv of plan.levels) for (const q of lv.rooms) {
    house.x0 = Math.min(house.x0, b.x + q.x); house.x1 = Math.max(house.x1, b.x + q.x + q.w);
    house.y0 = Math.min(house.y0, b.y + q.y); house.y1 = Math.max(house.y1, b.y + q.y + q.d);
  }
  const door = md ? { x: b.x + (md.x1 + md.x2) / 2, y: b.y + Math.min(md.y1, md.y2) } : null;
  const blocked = (x: number, y: number, r: number) =>
    (x > gx - r - 1 && x < gx + gateW + r + 1 && y < 6 + r) ||
    (!!park && x > b.x + park.x - r && x < b.x + park.x + park.w + r && y < b.y + park.y + r) ||
    (!!door && Math.abs(x - door.x) < 2 + r && y < door.y + r);
  const clear = (x: number, y: number, r: number) => { const pad = r + ov + 0.5; return x < house.x0 - pad || x > house.x1 + pad || y < house.y0 - pad || y > house.y1 + pad; };
  return { gate: { x: gx, w: gateW }, park, door, house, blocked, clear, ov };
}

/** 10.5 ft → 10'-6"  (or 3.20 m) */
export function dimText(ft: number, metric = false): string {
  if (metric) return (ft * 0.3048).toFixed(2);
  let f = Math.floor(ft + 1e-6), inch = Math.round((ft - f) * 12);
  if (inch === 12) { f += 1; inch = 0; }
  return `${f}'-${inch}"`;
}
export const sizeText = (w: number, d: number, metric = false) => (metric ? `${dimText(w, true)} × ${dimText(d, true)} m` : `${dimText(w)} X ${dimText(d)}`);

/** colours of the furniture – one palette per elevation style, used by the 2D rendered plan AND the 3D model */
export type FurnPalette = { wall: string; wood: string; woodDark: string; woodLight: string; sofa: string; cushion: string; accent: string; accent2: string;
  linen: string; blanket: string; rug: string; counter: string; cabinet: string; steel: string; white: string; car: string; leaf: string; leaf2: string; pot: string };
export function furnPalette(style: string): FurnPalette {
  const base: FurnPalette = { wall: "#22252a", wood: "#7a5536", woodDark: "#5a3a20", woodLight: "#b08a62", sofa: "#5d6b85", cushion: "#6f7e9b", accent: "#d9853b", accent2: "#8fae5a",
    linen: "#f4efe6", blanket: "#6d7fa3", rug: "#b9a27f", counter: "#1f2328", cabinet: "#3f4652", steel: "#aab0b8", white: "#f8fafc", car: "#e6e8ec", leaf: "#4e8a3a", leaf2: "#3f6e2f", pot: "#b5623a" };
  if (style === "luxury") return { ...base, wall: "#1d2024", wood: "#8a5a34", woodDark: "#5f3d22", sofa: "#d8c8ad", cushion: "#e6d9c2", blanket: "#8fa36a", rug: "#b8a98c", counter: "#3a2f2a", cabinet: "#6b4a2e" };
  if (style === "contemporary") return { ...base, wall: "#3a3f46", sofa: "#8b8f97", cushion: "#a3a7ae", blanket: "#b0563c", rug: "#c9c4b8", cabinet: "#55595f", accent: "#c8553d" };
  if (style === "traditional") return { ...base, wall: "#5a3520", wood: "#6b3f1f", woodDark: "#4a2a14", woodLight: "#9a6a3f", sofa: "#8c4a2f", cushion: "#a85f3f", blanket: "#b5523a", rug: "#a8473a", cabinet: "#6b3f1f", counter: "#2f2f2f", accent: "#e0a030" };
  if (style === "basic") return { ...base, wall: "#334155" };
  return base;
}

export type PlanLabel = { x: number; y: number; name: string; size: string; fs: number; rot: boolean };

/** room name + size for one room (also used to stamp labels on an AI-polished picture) */
export function roomLabels(plan: Plan, level: number, metric: boolean, items?: FItem[]): PlanLabel[] {
  const lv = plan.levels[level]; if (!lv) return [];
  const its = items || furnitureFor(lv);
  const out: PlanLabel[] = [];
  for (const r of lv.rooms) {
    if (r.type === "stair") continue;
    const name = (r.w < 5.5 && r.name.length > 9 ? r.name.split(" ")[0] : r.name).toUpperCase();
    const size = sizeText(r.w, r.d, metric);
    const rot = r.w < 4.6 && r.d > r.w * 1.4;
    const span = rot ? r.d : r.w;
    const fs = Math.min(0.95, (span - 0.9) / Math.max(name.length * 0.76, size.length * 0.52));
    if (fs < 0.34) continue;
    // sit where the least furniture is
    const mine = its.filter((i) => i.room === r.id && !i.flat && !i.top);
    const cand: [number, number][] = [[0.5, 0.5], [0.5, 0.3], [0.5, 0.7], [0.5, 0.18], [0.5, 0.84], [0.3, 0.5], [0.7, 0.5]];
    let best = cand[0], bs = Infinity;
    const wide = Math.max(name.length * 0.76, size.length * 0.52) * fs > span * 0.55;  // a wide label stays centred – never over a wall
    for (const [fx, fy] of cand) {
      if (wide && (rot ? fy !== 0.5 : fx !== 0.5)) continue;
      const cx = r.x + r.w * fx, cy = r.y + r.d * fy, hw = (rot ? fs * 1.3 : span * 0.42), hh = rot ? span * 0.42 : fs * 1.3;
      let s = Math.abs(fx - 0.5) * 0.6 + Math.abs(fy - 0.5) * 0.6;
      for (const i of mine) {
        const ox = Math.min(cx + hw, i.x + i.w) - Math.max(cx - hw, i.x), oy = Math.min(cy + hh, i.y + i.d) - Math.max(cy - hh, i.y);
        if (ox > 0 && oy > 0) s += ox * oy;
      }
      if (s < bs - 1e-6) { bs = s; best = [fx, fy]; }
    }
    out.push({ x: r.x + r.w * best[0], y: r.y + r.d * best[1], name, size, fs, rot });
  }
  return out;
}

/** what the picture shows (plot / building feet) – the ground floor shows the whole plot and the road */
export function planFrame(plan: Plan, level: number) {
  const b = plan.building, P = plan.plot, lv = plan.levels[level];
  if (level === 0) return { x0: -6, y0: -9, x1: P.w + 6, y1: P.d + 6, ground: true };
  const rs = lv.rooms;
  const x0 = b.x + Math.min(...rs.map((r) => r.x)), x1 = b.x + Math.max(...rs.map((r) => r.x + r.w));
  const y0 = b.y + Math.min(...rs.map((r) => r.y)), y1 = b.y + Math.max(...rs.map((r) => r.y + r.d));
  return { x0: x0 - 7, y0: y0 - 7, x1: x1 + 7, y1: y1 + 7, ground: false };
}
