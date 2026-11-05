/** 1.13 – builds the three.js house from the plan.
 *  Styles: basic (as before), modern (stone + wood cladding, black frames, deep roof overhang with wood soffit
 *  and downlights, glass balcony rails, entrance canopy), contemporary (two-tone, tile cladding, fins, pergola),
 *  traditional Tamil Nadu (sloped tile roof, thinnai + pillars at the entrance, arched window hoods).
 *  Doors and windows are ALWAYS at the plan positions / sizes – the same as the 2D drawings.
 *  Units: 1 = 1 ft. World: X = plan x, Y = up, Z = −plan y (road / front towards +Z). */
import * as THREE from "three";
import { mergeGeometries } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { WALL_T, type Plan } from "../../../lib/plan";
import { Grid, type R } from "./raster";
import * as T from "./textures";
import type { Look, Slot } from "./catalog";

export const PLINTH = 1.5, SLAB = 0.42, PARAPET = 3, HEADROOM = 8;
const SILL: Record<string, number> = { window: 3, vent: 5.5 };
const OPEN = new Set(["terrace", "balcony", "sitout", "parking", "portico"]);
const NO_SLAB = new Set(["terrace", "balcony", "sitout"]);
const DOORS = new Set(["main_door", "door", "toilet_door", "pooja_door"]);

export type Style = "basic" | "modern" | "contemporary" | "traditional";
export type LightMode = "day" | "dusk" | "night";
export type Mode = "exterior" | "interior" | "walk" | "exploded" | "structure";
export type Finishes = { ext: string; int: string; floor: string; door: string; frame: string; roof: string; plinth: string; style?: Style;
  mat?: Partial<Record<Slot, string>>; rooms?: Record<string, { wall?: string; floor?: string }> };

export const DEFAULT_FINISH: Finishes = { ext: "#f3eadb", int: "#fbfaf7", floor: "#e7e0d3", door: "#8b5a2b", frame: "#f8fafc", roof: "#cfcac2", plinth: "#8d8d8d", style: "modern" };
export const STYLE_FINISH: Record<Style, Partial<Finishes>> = {
  basic: { ext: "#f3eadb", frame: "#f8fafc", door: "#8b5a2b", plinth: "#8d8d8d", roof: "#cfcac2" },
  modern: { ext: "#efe7d8", frame: "#1d2024", door: "#9a6a3f", plinth: "#3b3a38", roof: "#d6d2ca" },
  contemporary: { ext: "#f5f5f3", frame: "#3a3f46", door: "#5b3a1e", plinth: "#55595f", roof: "#d9d9d6" },
  traditional: { ext: "#f2deb0", frame: "#6b3f1f", door: "#6b3f1f", plinth: "#7a2e1f", roof: "#cfcac2" },
};

export type BuildOpts = {
  upTo: number; only: number | null; mode: Mode; furniture: boolean; surround: boolean; roof: boolean; edges: boolean;
  structure?: any; style: Style; light: LightMode;
  /** 1.15 material library: what you picked for a part of the house (and per room); null = style default */
  look?: (slot: Slot, roomId?: string) => Look | null;
};
export type Built = { root: THREE.Group; lights: THREE.Light[] };

type Lv = Plan["levels"][number];
type Room = Lv["rooms"][number];

export function extent(rooms: { x: number; y: number; w: number; d: number }[]) {
  return { x0: Math.min(...rooms.map((r) => r.x)), x1: Math.max(...rooms.map((r) => r.x + r.w)), y0: Math.min(...rooms.map((r) => r.y)), y1: Math.max(...rooms.map((r) => r.y + r.d)) };
}

export function roomAt(rooms: Room[], x: number, y: number) {
  return rooms.find((r) => x >= r.x - 0.01 && x <= r.x + r.w + 0.01 && y >= r.y - 0.01 && y <= r.y + r.d + 0.01);
}

/** which side of a wall is outside (-1 = smaller x/y side, +1 = larger, 0 = both rooms) */
function wallOut(lv: Lv, w: Lv["walls"][number]) {
  const ra = w.a ? lv.rooms.find((r) => r.id === w.a) : undefined;
  const rb = w.b ? lv.rooms.find((r) => r.id === w.b) : undefined;
  const openA = !ra || OPEN.has(ra.type), openB = !rb || OPEN.has(rb.type);
  if (openA && !openB) return -1;
  if (openB && !openA) return 1;
  return 0;
}

export function build(plan: Plan, fin: Finishes, o: BuildOpts): Built {
  const root = new THREE.Group();
  const lights: THREE.Light[] = [];
  const H = plan.floor_height_ft || 10;
  const b = plan.building;
  const style = o.style;
  const lit = o.light !== "day";
  const mats = new Map<string, THREE.Material>();
  const M = (key: string, make: () => THREE.Material) => { if (!mats.has(key)) mats.set(key, make()); return mats.get(key)!; };
  const std = (col: string, p: Partial<THREE.MeshStandardMaterialParameters> = {}, tex: "plaster" | "none" = "plaster") =>
    M(`s${col}${JSON.stringify(p)}${tex}`, () => new THREE.MeshStandardMaterial({
      color: col, roughness: 0.88, metalness: 0, map: tex === "plaster" ? T.plaster() : null,
      polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1, ...p }));
  const texMat = (key: string, map: THREE.Texture, p: Partial<THREE.MeshStandardMaterialParameters> = {}) =>
    M(`t${key}${JSON.stringify(p)}`, () => new THREE.MeshStandardMaterial({ map, roughness: 0.85, polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1, ...p }));
  const stoneM = () => texMat("stone", T.stone(), { roughness: 0.95 });
  const woodM = (tone = "#9a6a3f") => texMat("wood" + tone, T.wood(tone), { roughness: 0.6 });
  const tileM = () => texMat("tiles", T.tiles(), { roughness: 0.55 });
  const lk = (slot: Slot, roomId?: string) => (o.look ? o.look(slot, roomId) : null);
  const lookMats = new Map<Look, THREE.Material>();
  const LM = (l: Look) => {
    if (!lookMats.has(l)) lookMats.set(l, new THREE.MeshStandardMaterial({ color: l.color, map: l.map, roughness: l.rough, metalness: l.metal,
      polygonOffset: true, polygonOffsetFactor: 1, polygonOffsetUnits: 1 }));
    return lookMats.get(l)!;
  };
  /** picked material for a slot, else the given default */
  const pick = (slot: Slot, dflt: () => THREE.Material, roomId?: string) => { const l = lk(slot, roomId); return l ? LM(l) : dflt(); };
  const glass = M("glass", () => new THREE.MeshPhysicalMaterial({
    color: lit ? "#ffd9a6" : "#9cc4dc", transparent: true, opacity: lit ? 0.85 : 0.42, roughness: 0.04, metalness: 0.15,
    emissive: lit ? new THREE.Color("#ffbf73") : new THREE.Color("#000000"), emissiveIntensity: o.light === "night" ? 1.1 : 0.75,
    depthWrite: false, side: THREE.DoubleSide }));
  const railGlass = M("rglass", () => new THREE.MeshPhysicalMaterial({ color: "#cfe7f2", transparent: true, opacity: 0.28, roughness: 0.05, depthWrite: false, side: THREE.DoubleSide }));
  const glow = M("glow", () => new THREE.MeshStandardMaterial({ color: "#fff3d6", emissive: new THREE.Color(lit ? "#ffe2a8" : "#666055"), emissiveIntensity: lit ? 2.2 : 0.2 }));
  const frameM = pick("frame", () => std(fin.frame, { roughness: 0.4, metalness: style === "modern" ? 0.3 : 0 }, "none"));
  const edgeMat = M("edge", () => new THREE.LineBasicMaterial({ color: "#3f3f46", transparent: true, opacity: 0.4 }));

  const box = (x0: number, y0: number, z0: number, x1: number, y1: number, z1: number, m: THREE.Material | THREE.Material[], parent: THREE.Object3D, name = "", shadow = true) => {
    const w = Math.abs(x1 - x0), d = Math.abs(y1 - y0), h = Math.abs(z1 - z0);
    if (w < 0.005 || d < 0.005 || h < 0.005) return undefined;
    const geo = new THREE.BoxGeometry(w, h, d);
    T.worldUV(geo, w, h, d);
    const g = new THREE.Mesh(geo, m);
    g.position.set(b.x + (x0 + x1) / 2, (z0 + z1) / 2, -(b.y + (y0 + y1) / 2));
    g.castShadow = shadow; g.receiveShadow = true; g.name = name;
    if (o.edges && !(m instanceof THREE.MeshPhysicalMaterial)) g.add(new THREE.LineSegments(new THREE.EdgesGeometry(geo), edgeMat));
    parent.add(g);
    return g;
  };
  /** wall-aligned box: along = s..e on the wall line, across = c0+a0..c0+a1 */
  const wbox = (horiz: boolean, s: number, e: number, c0: number, a0: number, a1: number, zb: number, zt: number, m: THREE.Material | THREE.Material[], p: THREE.Object3D, name = "") =>
    horiz ? box(s, c0 + Math.min(a0, a1), zb, e, c0 + Math.max(a0, a1), zt, m, p, name) : box(c0 + Math.min(a0, a1), s, zb, c0 + Math.max(a0, a1), e, zt, m, p, name);

  if (o.mode === "structure" && o.structure) { structureModel(plan, o.structure, root, box, std); return { root, lights }; }

  const levels = plan.levels;
  const nShow = Math.min(levels.length, o.upTo);
  const gap = o.mode === "exploded" ? 6 : 0;
  const zOf = (li: number) => PLINTH + li * H + li * gap;
  const ov = style === "modern" ? 2.25 : style === "contemporary" ? 1.4 : style === "traditional" ? 0.6 : 0.4;

  // ---------------- plinth (exact outline of the ground floor)
  const g0 = new Grid(levels[0].rooms, 2);
  levels[0].rooms.forEach((r) => g0.fill(r));
  const plinthGrid = g0.dilate(0.4);
  const plinthM = pick("plinth", () => (style === "modern" ? stoneM() : std(fin.plinth)));
  for (const r of plinthGrid.rects()) box(r.x, r.y, 0, r.x + r.w, r.y + r.d, PLINTH, plinthM, root, "plinth");

  let mainDoor: { op: Lv["openings"][number]; out: number } | null = null;

  for (let li = 0; li < nShow; li++) {
    if (o.only != null && li !== o.only) continue;
    const lv = levels[li];
    const g = new THREE.Group(); g.name = lv.name; root.add(g);
    const z = zOf(li);
    const topShown = li === nShow - 1 || o.only != null;
    const cutInterior = o.mode === "interior" && topShown;
    const wallTop = cutInterior ? z + 4.5 : z + H - SLAB;

    // ---------- floors (on top of the slab – never in the same plane)
    for (const r of lv.rooms) {
      const wet = r.type === "toilet" || r.type === "common_toilet";
      const m = r.type === "parking" ? (style === "basic" ? std("#bdbdbd") : texMat("pav", T.pavers()))
        : r.type === "terrace" ? pick("roof", () => std(fin.roof))
        : pick(wet ? "wet_floor" : "floor", () => (wet ? std("#dbe7ef", { roughness: 0.4 }) : std(fin.floor, { roughness: 0.45 })), `${li}:${r.id}`);
      box(r.x, r.y, z, r.x + r.w, r.y + r.d, z + 0.04, m, g, `floor ${r.name}`, false);
    }

    // ---------- walls with openings
    for (const w of lv.walls) {
      const horiz = Math.abs(w.y1 - w.y2) < 1e-6;
      const a0 = horiz ? Math.min(w.x1, w.x2) : Math.min(w.y1, w.y2);
      const a1 = horiz ? Math.max(w.x1, w.x2) : Math.max(w.y1, w.y2);
      const c0 = horiz ? w.y1 : w.x1;
      if (w.kind === "parapet") { railing(horiz, a0, a1, c0, z, g, lv, w); continue; }
      const th = (WALL_T[w.kind] || 0.5) / 2;
      const out = wallOut(lv, w);
      const front = horiz && out === -1;  // faces the road
      const skin = out !== 0 ? skinFor(li, front, lv, w) : null;
      const intM = std(fin.int);
      const ext = th - 0.004;
      const s0 = a0 - ext, s1 = a1 + ext;
      // 1.15: inside faces get the room's own finish (paint / tiles; toilets tiled to 7 ft)
      const sideRoom = (side: number) => { const id = side < 0 ? w.a : w.b; const r = id ? lv.rooms.find((q) => q.id === id) : undefined; return r && !OPEN.has(r.type) ? r : undefined; };
      const rooms2 = [-1, 1].map((sd) => [sd, sideRoom(sd)] as [number, Room | undefined]).filter(([sd, r]) => r && sd !== out);
      const piece = (s: number, e: number, zb: number, zt: number) => {
        if (e - s < 0.02 || zt - zb < 0.02) return;
        wbox(horiz, s, e, c0, -th, th, zb, zt, intM, g);
        if (skin) {
          const se = s <= s0 + 1e-6 ? s - 0.06 : s, ee = e >= s1 - 1e-6 ? e + 0.06 : e;
          wbox(horiz, se, ee, c0, out * th, out * (th + 0.06), zb, zt, skin(), g);
        }
        for (const [sd, r] of rooms2) {
          const wet = r!.type === "toilet" || r!.type === "common_toilet";
          const rk = `${li}:${r!.id}`;  // room ids repeat on every floor – the floor number makes them unique
          const paint = pick("int_wall", () => intM, rk);
          const a = sd * th, bb = sd * (th + 0.02);
          if (wet) {
            const tz = Math.min(zt, z + 7);
            if (tz > zb) wbox(horiz, s, e, c0, a, bb, zb, tz, pick("wet_wall", () => texMat("wtdef", T.floorTiles("#f2f2f0", 4), { roughness: 0.2 }), rk), g);
            if (zt > tz) wbox(horiz, s, e, c0, a, bb, Math.max(zb, tz), zt, paint, g);
          } else wbox(horiz, s, e, c0, a, bb, zb, zt, paint, g);
        }
      };
      const ops = lv.openings.filter((op) => (horiz ? Math.abs(op.y1 - op.y2) < 1e-6 && Math.abs(op.y1 - c0) < 0.01 : Math.abs(op.x1 - op.x2) < 1e-6 && Math.abs(op.x1 - c0) < 0.01))
        .map((op) => ({ s: horiz ? Math.min(op.x1, op.x2) : Math.min(op.y1, op.y2), e: horiz ? Math.max(op.x1, op.x2) : Math.max(op.y1, op.y2), op }))
        .filter((q) => q.e > a0 + 0.01 && q.s < a1 - 0.01).sort((p, q) => p.s - q.s);
      let cur = s0;
      for (const { s, e: e2, op } of ops) {
        const isWin = op.type === "window" || op.type === "vent";
        const sill = isWin ? SILL[op.type] ?? 3 : 0;
        const head = Math.min(isWin ? sill + op.h : op.h, H - SLAB - 0.3);
        const s2 = Math.max(cur, s), e3 = Math.min(e2, a1);
        piece(cur, s2, z, wallTop);
        if (sill > 0) piece(s2, e3, z, z + Math.min(sill, wallTop - z));
        if (z + head < wallTop) piece(s2, e3, z + head, wallTop);
        if (isWin && z + sill < wallTop) windowAt(horiz, s2, e3, c0, th, out, z + sill, Math.min(z + head, wallTop), op.type === "vent", w.kind === "ext" || out !== 0, li, front, g, cutInterior);
        else if (DOORS.has(op.type)) {
          doorAt(horiz, s2, e3, c0, th, z, z + Math.min(head, wallTop - z), op.type, g);
          if (op.type === "main_door" && li === 0) mainDoor = { op, out };
        }
        cur = Math.max(cur, e3);
      }
      piece(cur, s1, z, wallTop);
    }

    // ---------- parking: columns, beam, ramp
    for (const r of lv.rooms.filter((q) => q.type === "parking")) {
      const colM = style === "modern" ? stoneM() : std("#e6e1d8");
      for (const [cx, cy] of [[r.x, r.y], [r.x + r.w - 0.75, r.y]] as [number, number][])
        box(cx, cy, z, cx + 0.75, cy + 0.75, z + H - SLAB, colM, g, "column");
      if (li === 0 && r.y <= extent(lv.rooms).y0 + 0.01 && o.surround) ramp(r, g);
      if (o.furniture) car(r, z, g);
    }

    // ---------- stairs
    for (const r of lv.rooms.filter((q) => q.type === "stair" && q.d >= 7 && q.w >= 3)) stairs(r, z, g);
    if (o.furniture) furnish(lv.rooms, z, g);

    // ---------- slab + overhang over this floor
    const slabOn = !cutInterior && (li < nShow - 1 || o.roof);
    const isRoof = li === levels.length - 1 || li === nShow - 1;
    if (slabOn && !(isRoof && style === "traditional" && li === levels.length - 1)) slabOver(lv, li, z + H, isRoof && li === levels.length - 1, li < levels.length - 1 && li < nShow - 1, g);
    if (slabOn && isRoof && li === levels.length - 1 && style === "traditional") { slabOver(lv, li, z + H, false, false, g); hipRoof(lv, z + H, g); }
    if (li === levels.length - 1 && topShown && o.roof && o.mode !== "interior" && style !== "traditional") terrace(lv, z + H, g);
    if (lit) {  // warm light inside each floor (night / dusk)
      const e = extent(lv.rooms);
      const l = new THREE.PointLight("#ffd9a0", o.light === "night" ? 70 : 45, 45, 1.6);
      l.position.set(b.x + (e.x0 + e.x1) / 2, z + 7, -(b.y + (e.y0 + e.y1) / 2)); lights.push(l);
    }
  }

  if (mainDoor && o.mode !== "interior") entrance(mainDoor.op, mainDoor.out);
  if (o.surround) surroundings();
  if (!o.edges) optimize(root);
  lights.forEach((l) => root.add(l));
  return { root, lights };

  // =================================================================== parts
  function skinFor(li: number, front: boolean, lv: Lv, w: Lv["walls"][number]) {
    const room = lv.rooms.find((r) => r.id === (w.a || w.b));
    const extP = lk("ext_wall"), cladP = lk("cladding");
    const plain = () => (extP ? LM(extP) : std(fin.ext));
    const feature = (dflt: () => THREE.Material) => () => (cladP ? LM(cladP) : dflt());
    if (style === "modern") {
      if (front && li === 0 && room && room.type !== "parking") return feature(() => stoneM());
      if (front && li > 0 && room && (room.type === "bedroom" || room.type === "stair")) return feature(() => woodM("#8c5a33"));
      return plain;
    }
    if (style === "contemporary") {
      if (front && li === 0) return feature(() => tileM());
      if (front && room && room.type === "bedroom") return feature(() => std("#6b7078"));
      return plain;
    }
    if (cladP && front && li === 0 && room && room.type !== "parking") return feature(plain);  // basic / traditional: feature only when picked
    return plain;
  }

  function windowAt(horiz: boolean, s: number, e: number, c0: number, th: number, out: number, zs: number, zt: number, vent: boolean, outside: boolean, li: number, front: boolean, g: THREE.Object3D, cut: boolean) {
    const fo = out || 1;  // frame nearer the outside face
    wbox(horiz, s, e, c0, fo * th * 0.2 - 0.03, fo * th * 0.2 + 0.03, zs, zt, glass, g, "glass");
    const fd0 = fo * th * 0.05, fd1 = fo * th * 0.45, f = 0.16;
    wbox(horiz, s, s + f, c0, fd0, fd1, zs, zt, frameM, g);
    wbox(horiz, e - f, e, c0, fd0, fd1, zs, zt, frameM, g);
    wbox(horiz, s, e, c0, fd0, fd1, zs, zs + f, frameM, g);
    wbox(horiz, s, e, c0, fd0, fd1, zt - f, zt, frameM, g);
    const nV = vent ? 0 : Math.max(1, Math.round((e - s) / (style === "modern" ? 1.6 : 2.2)));
    for (let k = 1; k <= nV; k++) {
      const m = s + (k * (e - s)) / (nV + 1);
      wbox(horiz, m - 0.05, m + 0.05, c0, fd0, fd1, zs, zt, frameM, g);
    }
    if (!vent && (style === "modern" || style === "contemporary")) wbox(horiz, s, e, c0, fd0, fd1, zs + (zt - zs) * 0.68, zs + (zt - zs) * 0.68 + 0.1, frameM, g);
    if (vent) for (let k = 1; k < 3; k++) wbox(horiz, s, e, c0, fd0, fd1, zs + (k * (zt - zs)) / 3 - 0.04, zs + (k * (zt - zs)) / 3 + 0.04, frameM, g);
    // sill
    if (outside && out) wbox(horiz, s - 0.25, e + 0.25, c0, out * th, out * (th + 0.3), zs - 0.15, zs, std("#d6d0c4", { roughness: 0.5 }), g);
    if (!outside || !out || cut) return;
    const o2 = out * (th + 0.06);
    if (style === "modern" && !vent) {  // projecting box surround
      const bm = li === 0 && front ? std("#2a2c30", { roughness: 0.5 }, "none") : woodM("#7a4e2b");
      wbox(horiz, s - 0.45, e + 0.45, c0, o2, o2 + out * 1.1, zt, zt + 0.35, bm, g);
      wbox(horiz, s - 0.45, s - 0.1, c0, o2, o2 + out * 1.1, zs - 0.15, zt, bm, g);
      wbox(horiz, e + 0.1, e + 0.45, c0, o2, o2 + out * 1.1, zs - 0.15, zt, bm, g);
    } else if (style === "contemporary") {
      wbox(horiz, s - 0.6, e + 0.6, c0, o2, o2 + out * 1.6, zt + 0.3, zt + 0.5, std("#55595f", {}, "none"), g);
      if (front && li > 0 && !vent) {  // vertical fins
        const n = Math.max(3, Math.round((e - s) / 1.2) + 1);
        for (let k = 0; k < n; k++) {
          const m = s - 0.3 + (k * (e - s + 0.6)) / (n - 1);
          wbox(horiz, m - 0.08, m + 0.08, c0, o2 + out * 0.6, o2 + out * 1.4, zs - 0.6, zt + 0.3, woodM("#6b4a2e"), g);
        }
      }
    } else if (style === "traditional") {
      wbox(horiz, s - 0.6, e + 0.6, c0, o2, o2 + out * 1.6, zt + 0.35, zt + 0.55, std("#b9473a", {}, "none"), g);
      archHood(horiz, s, e, c0, o2, out, zt, g);
    } else {
      wbox(horiz, s - 0.75, e + 0.75, c0, o2, o2 + out * 1.75, zt + 0.35, zt + 0.6, std("#bdb7ad"), g);
    }
  }

  function archHood(horiz: boolean, s: number, e: number, c0: number, o2: number, out: number, zt: number, g: THREE.Object3D) {
    const rOut = (e - s) / 2 + 0.35, rIn = (e - s) / 2;
    const sh = new THREE.Shape();
    sh.absarc(0, 0, rOut, 0, Math.PI, false);
    sh.lineTo(-rIn, 0);
    sh.absarc(0, 0, rIn, Math.PI, 0, true);
    sh.lineTo(rOut, 0);
    const geo = new THREE.ExtrudeGeometry(sh, { depth: 0.25, bevelEnabled: false, curveSegments: 20 });
    const m = new THREE.Mesh(geo, std("#fff8e8"));
    const mid = (s + e) / 2;
    m.scale.set(1, 0.55, 1);
    if (horiz) { m.position.set(b.x + mid, zt + 0.05, -(b.y + c0 + o2 + (out < 0 ? 0 : 0.25))); }
    else { m.rotation.y = Math.PI / 2; m.position.set(b.x + c0 + o2 + (out < 0 ? -0.25 : 0), zt + 0.05, -(b.y + mid)); }
    m.castShadow = true; g.add(m);
  }

  function doorAt(horiz: boolean, s: number, e: number, c0: number, th: number, zb: number, zt: number, type: string, g: THREE.Object3D) {
    const dm = type === "toilet_door" ? std("#e8e4dc", { roughness: 0.5 }) : pick("door", () => woodM(fin.door));
    const fw = 0.22;  // frame (chowkat)
    const frm = woodM("#5a3a20");
    wbox(horiz, s - fw, s, c0, -th, th, zb, zt + fw, frm, g);
    wbox(horiz, e, e + fw, c0, -th, th, zb, zt + fw, frm, g);
    wbox(horiz, s - fw, e + fw, c0, -th, th, zt, zt + fw, frm, g);
    const leaves = type === "main_door" ? 2 : 1;
    const lw = (e - s) / leaves;
    for (let k = 0; k < leaves; k++) {
      const hingeAt = k === 0 ? s : e;
      const geo = new THREE.BoxGeometry(lw, zt - zb, 0.14);
      T.worldUV(geo, lw, zt - zb, 0.14);
      geo.translate(k === 0 ? lw / 2 : -lw / 2, (zt - zb) / 2, 0);
      const leaf = new THREE.Mesh(geo, dm);
      leaf.castShadow = true; leaf.receiveShadow = true; leaf.name = "door";
      const pivot = new THREE.Group();
      if (horiz) pivot.position.set(b.x + hingeAt, zb, -(b.y + c0));
      else { pivot.position.set(b.x + c0, zb, -(b.y + hingeAt)); pivot.rotation.y = Math.PI / 2; }
      leaf.userData.openAngle = k === 0 ? -1.35 : 1.35;  // the walkthrough opens doors without rebuilding
      leaf.userData.keep = true;  // not merged (it turns)
      leaf.name = "door leaf";
      pivot.add(leaf);
      // handle
      const hdl = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.6, 0.22), std("#c9a54a", { metalness: 0.8, roughness: 0.3 }, "none"));
      hdl.position.set(k === 0 ? lw - 0.35 : -lw + 0.35, 3.4, 0);
      leaf.add(hdl);
      g.add(pivot);
    }
  }

  function railing(horiz: boolean, s: number, e: number, c0: number, z: number, g: THREE.Object3D, lv: Lv, w: Lv["walls"][number]) {
    if (style === "modern" || style === "contemporary") {
      const ht = 3.4;
      wbox(horiz, s, e, c0, -0.03, 0.03, z + 0.15, z + ht - 0.15, railGlass, g, "glass rail");
      wbox(horiz, s, e, c0, -0.12, 0.12, z + ht - 0.15, z + ht, style === "modern" ? woodM("#8c5a33") : std("#3a3f46", {}, "none"), g);
      const n = Math.max(1, Math.round((e - s) / 4));
      for (let k = 0; k <= n; k++) {
        const m = s + (k * (e - s)) / n;
        wbox(horiz, m - 0.1, m + 0.1, c0, -0.1, 0.1, z, z + ht, style === "modern" ? woodM("#8c5a33") : std("#3a3f46", {}, "none"), g);
      }
      wbox(horiz, s, e, c0, -0.2, 0.2, z, z + 0.15, std(fin.ext), g);
      return;
    }
    if (style === "traditional") {  // balustrade
      wbox(horiz, s, e, c0, -0.25, 0.25, z, z + 0.4, std(fin.ext), g);
      wbox(horiz, s, e, c0, -0.3, 0.3, z + 2.8, z + 3.1, std(fin.ext), g);
      for (let m = s + 0.5; m < e - 0.3; m += 0.8) {
        const c = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.16, 2.4, 10), std("#fff8e8"));
        const [px, pz] = horiz ? [m, c0] : [c0, m];
        c.position.set(b.x + px, z + 1.6, -(b.y + pz)); c.castShadow = true; g.add(c);
      }
      return;
    }
    void lv; void w;
    wbox(horiz, s, e, c0, -0.25, 0.25, z, z + PARAPET, std(fin.ext), g);
  }

  function slabOver(lv: Lv, li: number, zTop: number, isRoof: boolean, keepStairHole: boolean, g: THREE.Object3D) {
    // the slab also carries the next floor's balconies / sit-outs (cantilevers)
    const above = li + 1 < levels.length ? levels[li + 1].rooms.filter((r) => NO_SLAB.has(r.type)) : [];
    const covered = [...lv.rooms.filter((r) => !NO_SLAB.has(r.type)), ...above];
    if (!covered.length) return;
    const grid = new Grid(covered, ov + 2);
    covered.forEach((r) => grid.fill(r));
    const stair = lv.rooms.find((r) => r.type === "stair");
    const slabG = new Grid(covered, ov + 2);
    covered.forEach((r) => slabG.fill(r));
    if (keepStairHole && stair) slabG.fill(stair, 0);
    const topM = isRoof ? pick("roof", () => std(fin.roof)) : std("#cfcac2");
    const under = pick("ceiling", () => std("#f4f2ee"));
    for (const r of slabG.rects()) box(r.x, r.y, zTop - SLAB, r.x + r.w, r.y + r.d, zTop, [under, under, topM, under, under, under], g, "slab");
    // overhang ring with fascia (+ wood soffit and downlights for modern)
    const thick = style === "modern" ? (isRoof ? 0.85 : 0.6) : style === "contemporary" ? 0.55 : SLAB;
    const ring = grid.dilate(isRoof ? ov : Math.min(ov, 1.0)).minus(grid);
    const fasc = std(style === "contemporary" ? "#55595f" : style === "modern" ? "#f2efe9" : fin.ext);
    const soff = style === "modern" ? woodM("#a06b3e") : under;
    for (const r of ring.rects()) {
      box(r.x, r.y, zTop - thick, r.x + r.w, r.y + r.d, zTop, [fasc, fasc, topM, soff, fasc, fasc], g, "overhang");
    }
    if (style === "modern" && lit) {  // downlights in the soffit
      let n = 0;
      for (const r of ring.rects()) {
        const long = Math.max(r.w, r.d);
        if (Math.min(r.w, r.d) < 0.9) continue;
        for (let t = 2; t < long - 1 && n < 60; t += 5) {
          const [px, py] = r.w >= r.d ? [r.x + t, r.y + r.d / 2] : [r.x + r.w / 2, r.y + t];
          const disc = new THREE.Mesh(new THREE.CylinderGeometry(0.22, 0.22, 0.04, 12), glow);
          disc.position.set(b.x + px, zTop - thick - 0.02, -(b.y + py)); g.add(disc);
          n++;
          if (n <= 3 && py < extent(lv.rooms).y0) {
            const sp = new THREE.SpotLight("#ffd59a", 40, 18, Math.PI / 5, 0.6, 1.5);
            sp.position.set(b.x + px, zTop - thick - 0.1, -(b.y + py));
            sp.target.position.set(b.x + px, zTop - thick - 8, -(b.y + py + 0.6));
            g.add(sp.target); lights.push(sp);
          }
        }
      }
    }
    void li;
  }

  function terrace(lv: Lv, zt: number, g: THREE.Object3D) {
    const covered = lv.rooms.filter((r) => !NO_SLAB.has(r.type));
    if (!covered.length) return;
    const grid = new Grid(covered, 2);
    covered.forEach((r) => grid.fill(r));
    const pm = std(fin.ext);
    const copeM = std(style === "modern" ? "#2a2c30" : style === "contemporary" ? "#55595f" : "#a1a1aa", {}, "none");
    const ph = style === "modern" ? 3.3 : PARAPET;
    for (const ed of grid.edges()) {
      const inS = ed.out === -1 ? 0.25 : -0.25;  // parapet stands just inside the edge
      wbox(ed.h, ed.s, ed.e, ed.c, 0, inS, zt, zt + ph, pm, g, "parapet");
      wbox(ed.h, ed.s - 0.02, ed.e + 0.02, ed.c, -inS * 0.2, inS * 1.15, zt + ph, zt + ph + 0.18, copeM, g);
    }
    const st = lv.rooms.find((r) => r.type === "stair");
    if (st && levels.length > 1) {  // head room
      const hm = style === "modern" ? stoneM() : style === "contemporary" ? tileM() : std(fin.ext);
      box(st.x, st.y, zt, st.x + st.w, st.y + st.d, zt + HEADROOM, hm, g, "head room");
      box(st.x - 0.9, st.y - 0.9, zt + HEADROOM, st.x + st.w + 0.9, st.y + st.d + 0.9, zt + HEADROOM + 0.6, [fascOf(), fascOf(), std(fin.roof), style === "modern" ? woodM("#a06b3e") : std("#f4f2ee"), fascOf(), fascOf()], g);
      // door to the terrace
      const dw = Math.min(3, st.w - 1);
      box(st.x + (st.w - dw) / 2, st.y + st.d, zt, st.x + (st.w + dw) / 2, st.y + st.d + 0.05, zt + 7, woodM(fin.door), g, "door");
    }
    if (style === "contemporary") {  // pergola over the front part of the terrace
      const e = extent(covered);
      const pw = Math.min(12, (e.x1 - e.x0) * 0.45), pd = Math.min(10, (e.y1 - e.y0) * 0.35);
      const px = st && st.x < (e.x0 + e.x1) / 2 ? e.x1 - pw - 0.6 : e.x0 + 0.6, py = e.y0 + 0.6;
      const pm2 = woodM("#6b4a2e");
      for (const [cx, cy] of [[px, py], [px + pw, py], [px, py + pd], [px + pw, py + pd]] as [number, number][]) box(cx - 0.25, cy - 0.25, zt, cx + 0.25, cy + 0.25, zt + 8.5, std("#3a3f46", {}, "none"), g);
      for (let x = px; x <= px + pw + 0.01; x += 1.2) box(x - 0.1, py - 0.6, zt + 8.5, x + 0.1, py + pd + 0.6, zt + 9.1, pm2, g, "pergola");
    }
  }
  function fascOf() { return std(style === "contemporary" ? "#55595f" : style === "modern" ? "#f2efe9" : fin.ext); }

  function hipRoof(lv: Lv, zt: number, g: THREE.Object3D) {
    const covered = lv.rooms.filter((r) => !NO_SLAB.has(r.type));
    const e = extent(covered.length ? covered : lv.rooms);
    const eave = 2.6;
    const x0 = e.x0 - eave, x1 = e.x1 + eave, y0 = e.y0 - eave, y1 = e.y1 + eave;
    const W = x1 - x0, D = y1 - y0;
    const rise = Math.min(W, D) * 0.5 * 0.62;
    const base = zt + 0.2;
    // world points (X, Y, Z)
    const P = (x: number, y: number, h: number) => new THREE.Vector3(b.x + x, base + h, -(b.y + y));
    const pos: THREE.Vector3[] = [];
    const tri = (a: THREE.Vector3, c: THREE.Vector3, d: THREE.Vector3) => pos.push(a, c, d);
    if (W >= D) {
      const r0 = P(x0 + D / 2, y0 + D / 2, rise), r1 = P(x1 - D / 2, y0 + D / 2, rise);
      const A = P(x0, y0, 0), B = P(x1, y0, 0), Cc = P(x1, y1, 0), Dd = P(x0, y1, 0);
      tri(A, B, r1); tri(A, r1, r0); tri(Cc, Dd, r0); tri(Cc, r0, r1); tri(B, Cc, r1); tri(Dd, A, r0);
    } else {
      const r0 = P(x0 + W / 2, y0 + W / 2, rise), r1 = P(x0 + W / 2, y1 - W / 2, rise);
      const A = P(x0, y0, 0), B = P(x1, y0, 0), Cc = P(x1, y1, 0), Dd = P(x0, y1, 0);
      tri(A, B, r0); tri(B, Cc, r1); tri(B, r1, r0); tri(Cc, Dd, r1); tri(Dd, A, r0); tri(Dd, r0, r1);
    }
    const geo = new THREE.BufferGeometry().setFromPoints(pos);
    const uv: number[] = [];
    pos.forEach((p) => uv.push(p.x / 4, (p.y - base) / 2.4 + p.z / 8));
    geo.setAttribute("uv", new THREE.Float32BufferAttribute(uv, 2));
    geo.computeVertexNormals();
    const m = new THREE.Mesh(geo, texMat("rooftile", T.roofTiles(), { side: THREE.DoubleSide, roughness: 0.75 }));
    m.castShadow = true; m.receiveShadow = true; m.name = "tiled roof"; g.add(m);
    // fascia board along the eaves
    const fm = woodM("#5a3a20");
    box(x0, y0 - 0.1, base - 0.5, x1, y0 + 0.1, base, fm, g); box(x0, y1 - 0.1, base - 0.5, x1, y1 + 0.1, base, fm, g);
    box(x0 - 0.1, y0, base - 0.5, x0 + 0.1, y1, base, fm, g); box(x1 - 0.1, y0, base - 0.5, x1 + 0.1, y1, base, fm, g);
  }

  function stairs(r: Room, z: number, g: THREE.Object3D) {
    const steps = Math.max(8, Math.round(H / 0.5));
    const half = Math.ceil(steps / 2);
    const run = (r.d - 3.5) / half;
    const wHalf = r.w / 2 - 0.1;
    const sm = style === "basic" ? std("#d6d3d1") : std("#e9e4dc", { roughness: 0.4 });
    for (let k = 0; k < half; k++)
      box(r.x + 0.1, r.y + 0.5 + k * run, z, r.x + 0.1 + wHalf, r.y + 0.5 + (k + 1) * run, z + (k + 1) * (H / steps), sm, g, "step");
    box(r.x + 0.1, r.y + r.d - 3.0, z + half * (H / steps) - 0.4, r.x + r.w - 0.1, r.y + r.d - 0.1, z + half * (H / steps), sm, g, "landing");
    for (let k = 0; k < steps - half; k++)
      box(r.x + r.w / 2, r.y + r.d - 3.0 - (k + 1) * run, z + (half + k) * (H / steps), r.x + r.w - 0.1, r.y + r.d - 3.0 - k * run, z + (half + k + 1) * (H / steps), sm, g, "step");
    // sloping hand rails along the inner edge of both flights
    const railM = std("#2a2c30", { metalness: 0.5, roughness: 0.4 }, "none");
    const rise = half * (H / steps), runL = half * run;
    const flight = (xr: number, yA: number, yB: number, zA: number, zB: number) => {
      const L = Math.hypot(yB - yA, zB - zA);
      const m = new THREE.Mesh(new THREE.BoxGeometry(0.12, 0.12, L), railM);
      m.position.set(b.x + xr, (zA + zB) / 2 + 3, -(b.y + (yA + yB) / 2));
      m.rotation.x = Math.atan2(zB - zA, yB - yA);
      g.add(m);
      for (let t = 0; t <= 1.001; t += 0.25) {  // balusters
        const yy = yA + (yB - yA) * t, zz = zA + (zB - zA) * t;
        box(xr - 0.04, yy - 0.04, zz, xr + 0.04, yy + 0.04, zz + 3, railM, g, "baluster");
      }
    };
    flight(r.x + 0.1 + wHalf, r.y + 0.5, r.y + 0.5 + runL, z, z + rise);
    flight(r.x + r.w / 2 + 0.05, r.y + r.d - 3.0, r.y + r.d - 3.0 - (steps - half) * run, z + rise, z + H);
  }

  function ramp(r: Room, g: THREE.Object3D) {
    const L = 4.5;
    const geo = new THREE.BoxGeometry(r.w, 0.3, Math.hypot(L, PLINTH));
    const m = new THREE.Mesh(geo, texMat("pav", T.pavers()));
    m.rotation.x = Math.atan2(PLINTH, L);
    m.position.set(b.x + r.x + r.w / 2, PLINTH / 2 - 0.1, -(b.y + r.y) + L / 2);
    m.receiveShadow = true; g.add(m);
  }

  function car(r: Room, z: number, g: THREE.Object3D) {
    if (r.w < 9 || r.d < 14) return;
    const cx = r.x + r.w / 2, cy = r.y + r.d / 2;
    const body = std("#9b1c1c", { roughness: 0.25, metalness: 0.6 }, "none");
    box(cx - 2.9, cy - 6.8, z + 1.0, cx + 2.9, cy + 6.8, z + 3.0, body, g, "car");
    box(cx - 2.5, cy - 3.2, z + 3.0, cx + 2.5, cy + 3.6, z + 4.5, std("#1d2430", { roughness: 0.1, metalness: 0.4 }, "none"), g, "car cabin");
    for (const [wx, wy] of [[-2.7, -4.4], [2.7, -4.4], [-2.7, 4.4], [2.7, 4.4]] as [number, number][]) {
      const w = new THREE.Mesh(new THREE.CylinderGeometry(1.05, 1.05, 0.7, 18), std("#111111", { roughness: 0.9 }, "none"));
      w.rotation.z = Math.PI / 2; w.position.set(b.x + cx + wx, z + 1.05, -(b.y + cy + wy)); w.castShadow = true; g.add(w);
    }
    if (lit) for (const wx of [-1.9, 1.9]) box(cx + wx - 0.5, cy - 6.85, z + 2.2, cx + wx + 0.5, cy - 6.8, z + 2.6, glow, g);
  }

  function entrance(op: Lv["openings"][number], out: number) {
    const lv = levels[0];
    const horiz = Math.abs(op.y1 - op.y2) < 1e-6;
    if (!horiz || out !== -1) return;  // only for a door facing the road
    const c0 = op.y1, s = Math.min(op.x1, op.x2), e = Math.max(op.x1, op.x2);
    const inFront = roomAt(lv.rooms, (s + e) / 2, c0 - 1);
    if (inFront) return;  // door opens onto a porch / sit-out / car porch – that already covers it
    const th = (WALL_T.ext || 0.755) / 2;
    const yF = c0 - th;
    const w = e - s + 4;
    const x0 = (s + e) / 2 - w / 2, x1 = (s + e) / 2 + w / 2;
    // landing + 2 steps down to the ground
    const stepM = style === "traditional" ? std("#9c9a94") : std("#cfc9bd", { roughness: 0.5 });
    const ground = 0;
    box(x0, yF - 1.4, 0, x1, yF, PLINTH, stepM, root, "landing");
    for (let k = 1; k <= 2; k++) box(x0, yF - 1.4 - k * 1.0, 0, x1, yF - 1.4 - (k - 1) * 1.0, (PLINTH * (3 - k)) / 3, stepM, root, "step");
    const ch = 8.6, depth = 4.5;
    if (style === "traditional") {
      // thinnai (raised sit-outs) on both sides + round pillars + tiled sloping canopy
      const tw = 4.5;
      if (s - tw - 0.5 > extent(lv.rooms).x0 - 6) box(s - 0.6 - tw, yF - 3.2, PLINTH, s - 0.6, yF, PLINTH + 1.8, std("#b9473a"), root, "thinnai");
      box(e + 0.6, yF - 3.2, PLINTH, e + 0.6 + tw, yF, PLINTH + 1.8, std("#b9473a"), root, "thinnai");
      for (const px of [s - 0.6 - tw + 0.6, x0 - 0.2, x1 + 0.2, e + 0.6 + tw - 0.6]) {
        const c = new THREE.Mesh(new THREE.CylinderGeometry(0.42, 0.48, ch - PLINTH, 16), std("#fff8e8"));
        c.position.set(b.x + px, PLINTH + (ch - PLINTH) / 2, -(b.y + yF - depth + 0.6)); c.castShadow = true; root.add(c);
        box(px - 0.6, yF - depth + 0, PLINTH, px + 0.6, yF - depth + 1.2, PLINTH + 0.5, std("#fff8e8"), root);
      }
      const L = (e + 0.6 + tw) - (s - 0.6 - tw) + 1.5;
      const geo = new THREE.BoxGeometry(L, 0.25, depth + 2);
      T.worldUV(geo, L, 0.25, depth + 2);
      const m = new THREE.Mesh(geo, texMat("rooftile", T.roofTiles(), { side: THREE.DoubleSide, roughness: 0.75 }));
      m.rotation.x = -0.32;
      m.position.set(b.x + (s + e) / 2, ch + 0.6, -(b.y + yF - depth / 2 - 0.5)); m.castShadow = true; root.add(m);
      return;
    }
    // modern / contemporary / basic: flat canopy slab, pillars in front
    const cm = style === "modern" ? woodM("#a06b3e") : std("#f4f2ee");
    const top = std(fin.roof), fas = fascOf();
    box(x0 - 0.5, yF - depth, ch, x1 + 0.5, yF, ch + 0.55, [fas, fas, top, cm, fas, fas], root, "canopy");
    if (style !== "basic") {
      const pm = style === "modern" ? stoneM() : tileM();
      for (const px of [x0 - 0.2, x1 - 0.9]) box(px, yF - depth + 0.1, ground === 0 ? 0 : PLINTH, px + 1.1, yF - depth + 1.2, ch, pm, root, "pillar");
    }
    if (lit) {
      const l = new THREE.PointLight("#ffcf8a", 35, 16, 1.6);
      l.position.set(b.x + (s + e) / 2, ch - 0.6, -(b.y + yF - 2)); lights.push(l);
      box((s + e) / 2 - 0.25, yF - 2.25, ch - 0.06, (s + e) / 2 + 0.25, yF - 1.75, ch, glow, root);
      for (const px of [s - 0.9, e + 0.6]) box(px, yF - 0.12, PLINTH + 5.2, px + 0.3, yF, PLINTH + 6.0, glow, root, "wall light");
    }
  }

  function furnish(rooms: Room[], z: number, g: THREE.Object3D) {
    const fab = (c: string) => std(c, { roughness: 0.95 });
    for (const r of rooms) {
      const { x, y, w, d, type } = r;
      if (type === "bedroom" && w >= 8 && d >= 8) {
        const bw = Math.min(5, w - 3), bl = Math.min(6.5, d - 2.5), bx = x + (w - bw) / 2, by = y + d - bl - 0.6;
        box(bx, by, z, bx + bw, by + bl, z + 1.0, woodM("#6b4a2e"), g, "bed");
        box(bx + 0.1, by + 0.1, z + 1.0, bx + bw - 0.1, by + bl - 0.1, z + 1.7, fab("#f1ece2"), g, "mattress");
        box(bx, by + bl - 0.4, z, bx + bw, by + bl, z + 3.4, woodM("#5a3a20"), g, "headboard");
        box(bx + 0.3, by + bl - 1.6, z + 1.7, bx + bw - 0.3, by + bl - 0.6, z + 2.1, fab("#ffffff"), g, "pillow");
        box(bx + 0.1, by + 0.1, z + 1.7, bx + bw - 0.1, by + bl * 0.45, z + 1.78, fab("#7b8fae"), g, "blanket");
        if (w >= 10) box(x + 0.4, y + 0.6, z, x + 2.3, y + 4.6, z + 7, woodM("#8c6a4a"), g, "wardrobe");
      } else if ((type === "hall" || type === "lounge") && w >= 8 && d >= 8) {
        box(x + 0.6, y + 1, z, x + 3.1, y + Math.min(8, d - 1.5), z + 1.4, fab("#5d6b85"), g, "sofa");
        box(x + 0.6, y + 1, z + 1.4, x + 1.2, y + Math.min(8, d - 1.5), z + 2.8, fab("#5d6b85"), g, "sofa back");
        box(x + 4, y + d / 2 - 1, z, x + 6.5, y + d / 2 + 1, z + 1.4, woodM("#5a3a20"), g, "table");
        box(x + w - 1.4, y + d / 2 - 2.5, z, x + w - 0.6, y + d / 2 + 2.5, z + 2.0, std("#2f2f33", {}, "none"), g, "tv unit");
        box(x + w - 1.0, y + d / 2 - 2.0, z + 3.2, x + w - 0.9, y + d / 2 + 2.0, z + 5.6, std("#0b0b0d", { roughness: 0.2 }, "none"), g, "tv");
        box(x + 3.6, y + d / 2 - 2.5, z, x + 7.2, y + d / 2 + 2.5, z + 0.03, fab("#b9a27f"), g, "rug");
      } else if (type === "dining" && w >= 7 && d >= 7) {
        box(x + w / 2 - 2, y + d / 2 - 1.25, z + 2.35, x + w / 2 + 2, y + d / 2 + 1.25, z + 2.5, woodM("#6b4a2e"), g, "dining");
        for (const [px, py] of [[-1.8, -1.05], [1.6, -1.05], [-1.8, 0.85], [1.6, 0.85]] as [number, number][]) box(x + w / 2 + px, y + d / 2 + py, z, x + w / 2 + px + 0.2, y + d / 2 + py + 0.2, z + 2.35, woodM("#5a3a20"), g);
      } else if (type === "kitchen") {
        const km = std("#3f4652", { roughness: 0.5 }, "none"), top = pick("counter", () => std("#1f2328", { roughness: 0.25 }, "none"));
        box(x + 0.3, y + 0.3, z, x + 2.3, y + d - 0.3, z + 2.7, km, g, "counter");
        box(x + 0.3, y + 0.3, z + 2.7, x + 2.3, y + d - 0.3, z + 2.85, top, g);
        box(x + 0.3, y + d - 2.3, z, x + Math.max(2.4, w - 0.3), y + d - 0.3, z + 2.7, km, g, "counter");
        box(x + 0.3, y + d - 2.3, z + 2.7, x + Math.max(2.4, w - 0.3), y + d - 0.3, z + 2.85, top, g);
      } else if ((type === "toilet" || type === "common_toilet") && w >= 3.5 && d >= 4) {
        box(x + w - 2, y + d - 2.6, z, x + w - 0.6, y + d - 0.6, z + 1.4, std("#ffffff", { roughness: 0.2 }, "none"), g, "wc");
        box(x + 0.4, y + d - 1.6, z + 2.4, x + 2, y + d - 0.4, z + 2.9, std("#ffffff", { roughness: 0.2 }, "none"), g, "basin");
      }
    }
  }

  /** plot-coordinate point (x, y) is at least `r` ft away from the building footprint (all floors + overhang) */
  function clearOfHouse(x: number, y: number, r: number) {
    let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
    for (const lv of levels) for (const q of lv.rooms) {
      x0 = Math.min(x0, b.x + q.x); x1 = Math.max(x1, b.x + q.x + q.w); y0 = Math.min(y0, b.y + q.y); y1 = Math.max(y1, b.y + q.y + q.d);
    }
    const pad = r + ov + 0.5;
    return x < x0 - pad || x > x1 + pad || y < y0 - pad || y > y1 + pad;
  }

  function surroundings() {
    const P = plan.plot;
    const lv0 = levels[0];
    const add = (geo: THREE.BufferGeometry, m: THREE.Material, x: number, y: number, z: number, shadow = false) => {
      const me = new THREE.Mesh(geo, m); me.position.set(x, y, z); me.receiveShadow = true; me.castShadow = shadow; root.add(me); return me;
    };
    const plane = (w: number, d: number, m: THREE.Material, cx: number, cz: number, y: number) => {
      const geo = new THREE.PlaneGeometry(w, d);
      const uv = geo.getAttribute("uv") as THREE.BufferAttribute;
      for (let i = 0; i < uv.count; i++) uv.setXY(i, (uv.getX(i) * w) / 8, (uv.getY(i) * d) / 8);
      const me = add(geo, m, cx, y, cz); me.rotation.x = -Math.PI / 2; return me;
    };
    const flat = (k: string, t: THREE.Texture) => texMat(k, t, { roughness: 0.95, polygonOffset: false });
    // ground layers are kept well apart in height so they never flicker
    plane(P.w + 160, P.d + 160, std("#6f8f55", { roughness: 1 }), P.w / 2, -P.d / 2, -0.15);
    plane(P.w, P.d, style === "basic" ? std("#cbbf9f", { roughness: 1 }) : flat("grass", T.grass()), P.w / 2, -P.d / 2, -0.05);
    plane(P.w + 160, 22, flat("asphalt", T.asphalt()), P.w / 2, 14, 0.0);
    for (let x = -70; x < P.w + 70; x += 12) plane(5, 0.4, std("#f1f1f1", { roughness: 0.6 }, "none"), x, 14, 0.06);  // lane marks
    plane(P.w + 160, 3, std("#b7b2a8"), P.w / 2, 1.5, 0.04);  // footpath
    // driveway (to the parking or the front) and a path to the main door
    const park = lv0.rooms.find((r) => r.type === "parking");
    const pave = style === "basic" ? std("#bcb6aa") : flat("pav", T.pavers());
    const bx0 = b.x, by0 = b.y;
    if (park) plane(park.w, by0 + park.y, pave, bx0 + park.x + park.w / 2, -(by0 + park.y) / 2, 0.03);
    const md = lv0.openings.find((q) => q.type === "main_door");
    if (md && (!park || Math.abs((md.x1 + md.x2) / 2 - (park.x + park.w / 2)) > park.w / 2)) {
      const mx = bx0 + (md.x1 + md.x2) / 2;
      plane(4, by0 + Math.min(md.y1, md.y2), pave, mx, -(by0 + Math.min(md.y1, md.y2)) / 2, 0.035);
    }
    // compound wall + gate
    const gateW = park ? Math.min(Math.max(10, park.w), P.w * 0.5) : Math.min(12, P.w * 0.4);
    const gx = park ? Math.min(Math.max(bx0 + park.x + park.w / 2 - gateW / 2, 1.5), P.w - gateW - 1.5) : P.w / 2 - gateW / 2;
    const wallH = style === "modern" ? 5 : 4.5;
    const cwPick = lk("compound");
    const cw = style === "traditional" ? std("#fbf3e0") : style === "contemporary" ? std("#f5f5f3") : style === "modern" ? std("#2a2c30", { roughness: 0.6 }, "none") : std("#e7e1d6");
    const cwPlain = cwPick ? LM(cwPick) : null;
    const seg = (x0: number, z0: number, x1: number, z1: number, front: boolean) => {
      const len = Math.hypot(x1 - x0, z1 - z0);
      if (len < 0.3) return;
      const along = Math.abs(x1 - x0) > Math.abs(z1 - z0);
      const mk = (w: number, h: number, d: number, m: THREE.Material, cx: number, cy: number, cz: number) => {
        const geo = new THREE.BoxGeometry(w, h, d); T.worldUV(geo, w, h, d); add(geo, m, cx, cy, cz, true);
      };
      const cx = (x0 + x1) / 2, cz = -(z0 + z1) / 2;
      if (style === "modern" && front) {  // stone base + black slats + stone pillars
        mk(along ? len : 0.8, 1.2, along ? 0.8 : len, cwPlain || stoneM(), cx, 0.6, cz);
        for (let k = 0; k < 5; k++) mk(along ? len : 0.12, 0.35, along ? 0.12 : len, cw, cx, 1.6 + k * 0.7, cz);
        const n = Math.max(1, Math.round(len / 10));
        for (let k = 0; k <= n; k++) {
          const t = k / n, px = x0 + (x1 - x0) * t, pz = -(z0 + (z1 - z0) * t);
          mk(1.4, wallH + 0.4, 1.4, stoneM(), px, (wallH + 0.4) / 2, pz);
          if (lit) { const lamp = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.3, 0.5), glow); lamp.position.set(px, wallH + 0.55, pz); root.add(lamp); }
        }
      } else {
        mk(along ? len : 0.75, wallH, along ? 0.75 : len, cwPlain || (style === "modern" ? std("#e9e4db") : cw), cx, wallH / 2, cz);
        const cap = style === "traditional" ? std("#b9473a", {}, "none") : style === "contemporary" ? std("#55595f", {}, "none") : std("#c9c3b8");
        mk(along ? len + 0.2 : 1.0, 0.25, along ? 1.0 : len + 0.2, cap, cx, wallH + 0.12, cz);
        if (style === "contemporary" && front) mk(along ? len : 0.8, 1.2, along ? 0.8 : len, tileM(), cx, 0.6, cz);
      }
    };
    seg(0, 0, gx, 0, true); seg(gx + gateW, 0, P.w, 0, true);
    seg(0, P.d, P.w, P.d, false); seg(0, 0, 0, P.d, false); seg(P.w, 0, P.w, P.d, false);
    // gate pillars + gate
    const gpm = style === "modern" ? stoneM() : style === "traditional" ? std("#fbf3e0") : style === "contemporary" ? tileM() : std("#d6d0c4");
    for (const px of [gx - 0.75, gx + gateW + 0.75]) {
      const geo = new THREE.BoxGeometry(1.5, wallH + 1, 1.5); T.worldUV(geo, 1.5, wallH + 1, 1.5); add(geo, gpm, px, (wallH + 1) / 2, 0, true);
      if (style === "traditional") add(new THREE.ConeGeometry(1.1, 1.0, 4), std("#b9473a", {}, "none"), px, wallH + 1.5, 0, true).rotation.y = Math.PI / 4;
    }
    const gm = std(style === "contemporary" ? "#3a3f46" : "#1d2024", { metalness: 0.5, roughness: 0.45 }, "none");
    const slats = style === "basic" ? 1 : 7;
    for (let k = 0; k < slats; k++) {
      const h = slats === 1 ? wallH - 0.6 : 0.42;
      const yy = slats === 1 ? 0.3 + h / 2 : 0.5 + k * ((wallH - 0.6) / slats) + h / 2;
      add(new THREE.BoxGeometry(gateW, h, 0.15), gm, gx + gateW / 2, yy, 0.6, true);
    }
    // plants: shrubs along the inside of the compound, a few trees, path lights
    if (style !== "basic") {
      const shrubM = std("#3f6b2c", { roughness: 1 }, "none"), shrub2 = std("#557f36", { roughness: 1 }, "none");
      for (let x = 2; x < P.w - 1; x += 3.2) {
        if (x > gx - 1.5 && x < gx + gateW + 1.5) continue;
        if (md && Math.abs(x - (bx0 + (md.x1 + md.x2) / 2)) < 3) continue;
        if (!clearOfHouse(x, 1.6, 1.3)) continue;
        add(new THREE.SphereGeometry(1.2, 10, 8), x % 2 > 1 ? shrubM : shrub2, x, 1.0, -1.6, true).scale.set(1, 0.8, 1);
      }
      for (let zz = 4; zz < P.d - 2; zz += 3.5) {
        for (const xx of [1.6, P.w - 1.6]) if (clearOfHouse(xx, zz, 1.2)) add(new THREE.SphereGeometry(1.1, 10, 8), shrubM, xx, 1.0, -zz, true).scale.set(1, 0.85, 1);
      }
      if (lit && md) {
        const mx = bx0 + (md.x1 + md.x2) / 2;
        for (let k = 1; k * 4 < by0 + md.y1 - 2; k++) for (const sx of [-2.4, 2.4]) {
          const post = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 1.4, 8), std("#1d2024", {}, "none"));
          post.position.set(mx + sx, 0.7, -k * 4); root.add(post);
          const head = new THREE.Mesh(new THREE.BoxGeometry(0.35, 0.25, 0.35), glow); head.position.set(mx + sx, 1.45, -k * 4); root.add(head);
        }
      }
    }
    const trunkM = std("#5b4332", { roughness: 1 }, "none"), leafM = std("#2f6b33", { roughness: 1 }, "none"), leaf2 = std("#3f7d3a", { roughness: 1 }, "none");
    // 1.15: trees only where they cannot touch the house (outside the compound, away from the building + overhang)
    for (const [tx, tz, s] of [[-7, 5, 1.1], [P.w + 7, 6, 1], [-9, -P.d * 0.6, 1.25], [P.w + 8, -P.d * 0.7, 1.15], [-8, -P.d - 6, 1.0]] as [number, number, number][]) {
      if (!clearOfHouse(tx, -tz, 5 * s)) continue;
      add(new THREE.CylinderGeometry(0.35 * s, 0.5 * s, 7 * s, 8), trunkM, tx, 3.5 * s, tz, true);
      add(new THREE.SphereGeometry(3.4 * s, 14, 10), leafM, tx, 8.5 * s, tz, true);
      add(new THREE.SphereGeometry(2.6 * s, 12, 9), leaf2, tx + 1.6 * s, 9.6 * s, tz - 0.8 * s, true);
      add(new THREE.SphereGeometry(2.3 * s, 12, 9), leaf2, tx - 1.4 * s, 10.2 * s, tz + 0.9 * s, true);
    }
  }
}

/** 1.15: thousands of small boxes → a few big meshes (one per material). The graphics card draws ~60 pieces
 *  instead of ~3000, so the walkthrough and rotating stay smooth on ordinary laptops. Doors stay separate (they open). */
function optimize(root: THREE.Group) {
  root.updateMatrixWorld(true);
  const groups = new Map<string, { mat: THREE.Material; shadow: boolean; geos: THREE.BufferGeometry[] }>();
  const remove: THREE.Mesh[] = [];
  const skip = (o: THREE.Object3D) => { for (let p: THREE.Object3D | null = o; p; p = p.parent) if (p.userData?.keep) return true; return false; };
  const put = (mat: THREE.Material, shadow: boolean, g: THREE.BufferGeometry) => {
    const key = `${mat.uuid}|${shadow ? 1 : 0}`;
    if (!groups.has(key)) groups.set(key, { mat, shadow, geos: [] });
    groups.get(key)!.geos.push(g);
  };
  const slice = (g: THREE.BufferGeometry, start: number, count: number) => {  // vertices [start, start+count) of a non-indexed geometry
    const out = new THREE.BufferGeometry();
    for (const k of ["position", "normal", "uv"]) {
      const a = g.getAttribute(k) as THREE.BufferAttribute;
      out.setAttribute(k, new THREE.BufferAttribute((a.array as Float32Array).slice(start * a.itemSize, (start + count) * a.itemSize), a.itemSize));
    }
    return out;
  };
  root.traverse((o: any) => {
    if (!o.isMesh || skip(o) || o.children.some((c: any) => c.isLineSegments)) return;
    const g: THREE.BufferGeometry = o.geometry.index ? o.geometry.toNonIndexed() : o.geometry.clone();
    for (const k of Object.keys(g.attributes)) if (!["position", "normal", "uv"].includes(k)) g.deleteAttribute(k);
    if (!g.attributes.uv) g.setAttribute("uv", new THREE.Float32BufferAttribute(new Float32Array((g.attributes.position.count) * 2), 2));
    if (!g.attributes.normal) g.computeVertexNormals();
    g.applyMatrix4(o.matrixWorld);
    if (Array.isArray(o.material)) {  // slab / overhang boxes: one piece per face material
      for (const gr of g.groups) put(o.material[gr.materialIndex ?? 0], o.castShadow, slice(g, gr.start, gr.count));
      g.dispose();
    } else {
      g.clearGroups();
      put(o.material, o.castShadow, g);
    }
    remove.push(o);
  });
  for (const m of remove) { m.parent?.remove(m); if (m.geometry) m.geometry.dispose(); }
  for (const { mat, shadow, geos } of groups.values()) {
    const merged = mergeGeometries(geos, false);
    geos.forEach((g) => g.dispose());
    if (!merged) continue;
    const mesh = new THREE.Mesh(merged, mat);
    mesh.castShadow = shadow; mesh.receiveShadow = true;
    root.add(mesh);
  }
}

function structureModel(plan: Plan, st: any, root: THREE.Group,
  box: (x0: number, y0: number, z0: number, x1: number, y1: number, z1: number, m: THREE.Material, p: THREE.Object3D, n?: string) => any,
  mat: (c: string, e?: any) => THREE.Material) {
  const H = plan.floor_height_ft || 10, n = plan.levels.length, MM = 1 / 304.8;
  const depth = (st.inputs?.foundation_depth_m || 1.5) / 0.3048;
  const cM = mat("#e11d48", { roughness: 0.6 }), bM = mat("#2563eb", { roughness: 0.6 }), fM = mat("#f59e0b"), pM = mat("#a8a29e");
  const sM = new THREE.MeshStandardMaterial({ color: "#94a3b8", transparent: true, opacity: 0.35, roughness: 0.8, depthWrite: false });
  for (const f of st.footings || []) {
    const B = f.B_m / 0.3048, D = f.D_mm * MM;
    box(f.x - B / 2 - 0.33, f.y - B / 2 - 0.33, -depth - 0.33, f.x + B / 2 + 0.33, f.y + B / 2 + 0.33, -depth, pM, root, "PCC");
    box(f.x - B / 2, f.y - B / 2, -depth, f.x + B / 2, f.y + B / 2, -depth + D, fM, root, `footing ${f.mark}`);
  }
  for (const c of st.columns || []) {
    const bb = c.b_mm * MM, D = c.D_mm * MM;
    box(c.x - bb / 2, c.y - D / 2, -depth, c.x + bb / 2, c.y + D / 2, PLINTH + n * H, cM, root, `column ${c.mark}`);
  }
  const lvIndex: Record<string, number> = Object.fromEntries((st.levels || []).map((l: string, i: number) => [l, i]));
  for (const bm of st.beams || []) {
    const z = PLINTH + ((lvIndex[bm.level] ?? 0) + 1) * H, t = (bm.b_mm * MM) / 2, Dd = bm.D_mm * MM;
    if (bm.dir === "h") box(bm.x1, bm.y1 - t, z - Dd, bm.x2, bm.y1 + t, z, bM, root, `beam ${bm.mark}`);
    else box(bm.x1 - t, bm.y1, z - Dd, bm.x1 + t, bm.y2, z, bM, root, `beam ${bm.mark}`);
  }
  for (const sl of st.slabs || []) {
    const z = PLINTH + ((lvIndex[sl.level] ?? 0) + 1) * H;
    box(sl.x, sl.y, z - sl.D_mm * MM, sl.x + sl.w, sl.y + sl.d, z, sM, root, `slab ${sl.mark}`);
  }
  for (const bm of (st.beams || []).filter((x: any) => (lvIndex[x.level] ?? 0) === 0)) {
    if (bm.dir === "h") box(bm.x1, bm.y1 - 0.38, 0.5, bm.x2, bm.y1 + 0.38, 1.5, mat("#60a5fa"), root, "plinth beam");
    else box(bm.x1 - 0.38, bm.y1, 0.5, bm.x1 + 0.38, bm.y2, 1.5, mat("#60a5fa"), root, "plinth beam");
  }
  return root;
}

// ===================================================================== walkthrough collision
export type Seg = { h: boolean; c: number; s: number; e: number; t: number };
/** solid wall pieces of a level in PLOT coordinates (door / opening gaps left open, windows solid) */
export function walkSegments(plan: Plan, li: number): Seg[] {
  const lv = plan.levels[li], b = plan.building;
  const out: Seg[] = [];
  for (const w of lv.walls) {
    const horiz = Math.abs(w.y1 - w.y2) < 1e-6;
    const a0 = horiz ? Math.min(w.x1, w.x2) : Math.min(w.y1, w.y2), a1 = horiz ? Math.max(w.x1, w.x2) : Math.max(w.y1, w.y2);
    const c0 = horiz ? w.y1 : w.x1;
    const t = (WALL_T[w.kind] || 0.5) / 2;
    const gaps = lv.openings.filter((op) => (DOORS.has(op.type) || op.type === "opening") &&
      (horiz ? Math.abs(op.y1 - op.y2) < 1e-6 && Math.abs(op.y1 - c0) < 0.01 : Math.abs(op.x1 - op.x2) < 1e-6 && Math.abs(op.x1 - c0) < 0.01))
      .map((op) => horiz ? [Math.min(op.x1, op.x2), Math.max(op.x1, op.x2)] : [Math.min(op.y1, op.y2), Math.max(op.y1, op.y2)]).sort((p, q) => p[0] - q[0]);
    let cur = a0;
    const push = (s: number, e: number) => { if (e - s > 0.05) out.push({ h: horiz, c: c0 + (horiz ? b.y : b.x), s: s + (horiz ? b.x : b.y), e: e + (horiz ? b.x : b.y), t }); };
    for (const [s, e] of gaps) { push(cur, s); cur = Math.max(cur, e); }
    push(cur, a1);
  }
  if (li > 0) {  // upper floors: you cannot walk off the edge of the slab
    const covered = lv.rooms;
    const gr = new Grid(covered, 1);
    covered.forEach((r) => gr.fill(r));
    for (const ed of gr.edges()) out.push({ h: ed.h, c: ed.c + (ed.h ? b.y : b.x), s: ed.s + (ed.h ? b.x : b.y), e: ed.e + (ed.h ? b.x : b.y), t: 0.1 });
  }
  if (li === 0) for (const r of lv.rooms.filter((q) => q.type === "parking" && q.w >= 9 && q.d >= 14)) {  // the parked car
    const cx = b.x + r.x + r.w / 2, cy = b.y + r.y + r.d / 2;
    out.push({ h: true, c: cy - 6.8, s: cx - 2.9, e: cx + 2.9, t: 0.05 }, { h: true, c: cy + 6.8, s: cx - 2.9, e: cx + 2.9, t: 0.05 },
      { h: false, c: cx - 2.9, s: cy - 6.8, e: cy + 6.8, t: 0.05 }, { h: false, c: cx + 2.9, s: cy - 6.8, e: cy + 6.8, t: 0.05 });
  }
  const P = plan.plot;  // compound wall (gate gap is not needed – stay inside the plot)
  out.push({ h: true, c: 0.3, s: 0, e: P.w, t: 0.1 }, { h: true, c: P.d - 0.3, s: 0, e: P.w, t: 0.1 },
    { h: false, c: 0.3, s: 0, e: P.d, t: 0.1 }, { h: false, c: P.w - 0.3, s: 0, e: P.d, t: 0.1 });
  return out;
}

/** move a circle (radius r) from p by d, sliding along walls. p and d in plot coords (x, y). */
export function collide(segs: Seg[], px: number, py: number, dx: number, dy: number, r = 0.9): [number, number] {
  let x = px + dx, y = py + dy;
  for (let it = 0; it < 3; it++) {
    for (const s of segs) {
      // closest point on the wall's centre segment
      const [cx, cy] = s.h ? [Math.max(s.s, Math.min(s.e, x)), s.c] : [s.c, Math.max(s.s, Math.min(s.e, y))];
      const vx = x - cx, vy = y - cy;
      const dist = Math.hypot(vx, vy), need = r + s.t;
      if (dist < need) {
        if (dist < 1e-6) { if (s.h) y = s.c + (py >= s.c ? need : -need); else x = s.c + (px >= s.c ? need : -need); continue; }
        x = cx + (vx / dist) * need; y = cy + (vy / dist) * need;
      }
    }
  }
  return [x, y];
}

export type { R };
