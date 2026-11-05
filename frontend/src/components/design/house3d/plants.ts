/** 1.16 – trees and plants around the house, chosen by the user (Material panel → Trees & plants).
 *  Coconut (thennai), neem (vembu), mango (maa), areca palm (paakku), shrubs / flowering plants, potted plants at
 *  the entrance and the lawn. Each type: ON/OFF, how many and where (front / sides / rear / along the compound).
 *  They are ALWAYS placed outside the house and its roof overhang (checked against every floor).
 *  Models are made from many small pieces (fronds with leaflets, leafy clumps) so they look like real trees,
 *  not balls. Everything is merged later by optimize(), so it costs only a few draw calls. Units: 1 = 1 ft. */
import * as THREE from "three";
import { mergeVertices } from "three/examples/jsm/utils/BufferGeometryUtils.js";

export type PlantKind = "coconut" | "neem" | "mango" | "areca" | "shrubs" | "potted";
export type Place = "front" | "sides" | "rear" | "edge";
export type PlantOpt = { on: boolean; count?: number; place?: Place };
export type Plants = Partial<Record<PlantKind | "lawn", PlantOpt>>;

export const PLANT_LABEL: Record<PlantKind | "lawn", string> = {
  coconut: "Coconut tree (Thennai)", neem: "Neem tree (Vembu)", mango: "Mango tree (Maa)", areca: "Areca palm (Paakku)",
  shrubs: "Shrubs / flowering plants", potted: "Potted plants at entrance", lawn: "Lawn (grass)",
};
export const PLANT_MAX: Record<PlantKind, number> = { coconut: 12, neem: 6, mango: 6, areca: 16, shrubs: 40, potted: 12 };
export const PLACE_LABEL: Record<Place, string> = { front: "Front yard", sides: "Sides", rear: "Rear yard", edge: "Along compound wall" };
export const DEFAULT_PLANTS: Required<Plants> = {
  coconut: { on: true, count: 2, place: "rear" }, neem: { on: true, count: 1, place: "front" },
  mango: { on: false, count: 1, place: "rear" }, areca: { on: false, count: 4, place: "edge" },
  shrubs: { on: true, count: 12, place: "edge" }, potted: { on: true, count: 2, place: "front" }, lawn: { on: true },
};
export const plantsOf = (p?: Plants | null): Required<Plants> => ({ ...DEFAULT_PLANTS, ...(p || {}) }) as Required<Plants>;

/** canopy radius (ft) – used to keep the whole tree clear of the house */
const RADIUS: Record<PlantKind, number> = { coconut: 9, areca: 4, neem: 8, mango: 8.5, shrubs: 1.3, potted: 0.9 };

type Piece = { geo: THREE.BufferGeometry; mat: string; shadow: boolean };
export type MatFor = (key: string) => THREE.Material;

// ------------------------------------------------------------------ small helpers
function rng(seed: number) {
  let s = ((Math.round(seed) * 9301 + 49297) % 233280 + 233280) % 233280;  // always positive (seeds can be negative)
  return () => { s = (s * 9301 + 49297) % 233280; return s / 233280; };
}
const hash3 = (x: number, y: number, z: number) => {
  const h = Math.sin(x * 12.9898 + y * 78.233 + z * 37.719) * 43758.5453;
  return h - Math.floor(h);
};

/** tapered tube along points (radius r0 → r1) */
function tube(pts: THREE.Vector3[], r0: number, r1: number, sides = 8) {
  const pos: number[] = [], idx: number[] = [];
  const n = pts.length;
  for (let i = 0; i < n; i++) {
    const t = i / (n - 1), r = r0 + (r1 - r0) * t;
    const dir = (i < n - 1 ? pts[i + 1].clone().sub(pts[i]) : pts[i].clone().sub(pts[i - 1])).normalize();
    const a = Math.abs(dir.y) < 0.9 ? new THREE.Vector3(0, 1, 0) : new THREE.Vector3(1, 0, 0);
    const u = new THREE.Vector3().crossVectors(dir, a).normalize(), v = new THREE.Vector3().crossVectors(dir, u).normalize();
    for (let k = 0; k < sides; k++) {
      const ang = (k / sides) * Math.PI * 2;
      const p = pts[i].clone().addScaledVector(u, Math.cos(ang) * r).addScaledVector(v, Math.sin(ang) * r);
      pos.push(p.x, p.y, p.z);
    }
  }
  for (let i = 0; i < n - 1; i++) for (let k = 0; k < sides; k++) {
    const a = i * sides + k, b2 = i * sides + ((k + 1) % sides), c = a + sides, d = b2 + sides;
    idx.push(a, c, b2, b2, c, d);
  }
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.setIndex(idx);
  g.computeVertexNormals();
  return g;
}

/** leafy clump – a lumpy, slightly flattened ball (flat-shaded foliage reads like leaves, not a smooth ball) */
function clump(r: number, cx: number, cy: number, cz: number, seed: number, flat = 0.82) {
  let g: THREE.BufferGeometry = new THREE.IcosahedronGeometry(r, 2);
  g.deleteAttribute("normal"); g.deleteAttribute("uv");
  g = mergeVertices(g);
  const p = g.getAttribute("position") as THREE.BufferAttribute;
  for (let i = 0; i < p.count; i++) {
    const x = p.getX(i), y = p.getY(i), z = p.getZ(i);
    const k = 0.66 + 0.42 * hash3(x + seed, y - seed, z + seed * 0.5) + 0.18 * hash3(x * 3.1 - seed, y * 2.7, z * 3.3 + seed);
    p.setXYZ(i, x * k + cx, y * k * flat + cy, z * k + cz);
  }
  g.computeVertexNormals();
  return g;
}

/** one palm frond: a curved spine with pairs of narrow leaflets */
function frond(top: THREE.Vector3, az: number, elev: number, len: number, droop: number, width: number, segs = 22) {
  const pos: number[] = [];
  const dirH = new THREE.Vector3(Math.cos(az), 0, Math.sin(az));
  const side = new THREE.Vector3(-Math.sin(az), 0, Math.cos(az));
  const at = (s: number) => top.clone().addScaledVector(dirH, Math.cos(elev) * s * len)
    .add(new THREE.Vector3(0, Math.sin(elev) * s * len - droop * s * s * len, 0));
  for (let i = 1; i < segs; i++) {
    const s0 = i / segs, s1 = (i + 0.8) / segs;
    const a = at(s0), b2 = at(s1);
    const fwd = b2.clone().sub(a);
    const w = width * (0.35 + Math.sin(Math.PI * Math.min(1, s0 * 1.15)) * 0.9);
    for (const sg of [-1, 1]) {
      const tip = a.clone().addScaledVector(side, sg * w * 0.85).addScaledVector(fwd, 1.6).add(new THREE.Vector3(0, -0.55 * w, 0));
      pos.push(a.x, a.y, a.z, b2.x, b2.y, b2.z, tip.x, tip.y, tip.z);
    }
  }
  // spine
  const pts: THREE.Vector3[] = [];
  for (let i = 0; i <= 8; i++) pts.push(at(i / 8));
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.Float32BufferAttribute(pos, 3));
  g.computeVertexNormals();
  return { leaves: g, spine: tube(pts, 0.12, 0.04, 4) };
}

// ------------------------------------------------------------------ the models (local coords, base at 0,0,0)
function coconut(seed: number): Piece[] {
  const R = rng(seed), out: Piece[] = [];
  const h = 26 + R() * 8, lean = 1.5 + R() * 2.5, la = R() * Math.PI * 2;
  const pts: THREE.Vector3[] = [];
  for (let i = 0; i <= 14; i++) {
    const t = i / 14;
    pts.push(new THREE.Vector3(Math.cos(la) * lean * t * t, h * t, Math.sin(la) * lean * t * t));
  }
  out.push({ geo: tube(pts, 0.62, 0.38, 9), mat: "palmTrunk", shadow: true });
  const top = pts[pts.length - 1];
  for (let k = 0; k < 6; k++) {  // coconuts
    const a = (k / 6) * Math.PI * 2 + R();
    out.push({ geo: new THREE.SphereGeometry(0.42, 7, 6).translate(top.x + Math.cos(a) * 0.6, top.y - 0.7 - R() * 0.4, top.z + Math.sin(a) * 0.6), mat: "nut", shadow: true });
  }
  const n = 15;
  for (let k = 0; k < n; k++) {
    const az = (k / n) * Math.PI * 2 + R() * 0.3;
    const lower = k % 3 === 0;
    const f = frond(top, az, lower ? 0.1 : 0.4 + R() * 0.5, 9 + R() * 2, lower ? 1.0 : 0.8, 1.35);
    out.push({ geo: f.leaves, mat: k % 5 === 0 ? "frondOld" : "frond", shadow: true });
    out.push({ geo: f.spine, mat: "frondSpine", shadow: false });
  }
  return out;
}

function areca(seed: number): Piece[] {
  const R = rng(seed), out: Piece[] = [];
  const h = 20 + R() * 7;
  const pts = [0, 0.5, 1].map((t) => new THREE.Vector3(0.3 * t * t, h * t, 0));
  out.push({ geo: tube(pts, 0.32, 0.26, 8), mat: "arecaTrunk", shadow: true });
  out.push({ geo: tube([pts[2], pts[2].clone().add(new THREE.Vector3(0, 3, 0))], 0.34, 0.3, 8), mat: "crownShaft", shadow: true });
  const top = pts[2].clone().add(new THREE.Vector3(0, 3, 0));
  for (let k = 0; k < 8; k++) {
    const f = frond(top, (k / 8) * Math.PI * 2 + R() * 0.4, 0.8 + R() * 0.35, 6 + R() * 1.5, 0.65, 1.0, 12);
    out.push({ geo: f.leaves, mat: "frond", shadow: true }, { geo: f.spine, mat: "frondSpine", shadow: false });
  }
  return out;
}

/** broad-leaf tree: trunk + branches + many leafy clumps in a dome */
function leafy(seed: number, o: { trunkH: number; trunkR: number; spread: number; height: number; clumps: number; mats: string[]; clumpR: [number, number] }): Piece[] {
  const R = rng(seed), out: Piece[] = [];
  out.push({ geo: tube([new THREE.Vector3(0, 0, 0), new THREE.Vector3(0.2, o.trunkH * 0.5, 0.1), new THREE.Vector3(0.1, o.trunkH, -0.1)], o.trunkR, o.trunkR * 0.7, 9), mat: "bark", shadow: true });
  const crownY = o.trunkH + o.height * 0.45;
  for (let k = 0; k < 4; k++) {  // branches into the crown
    const a = (k / 4) * Math.PI * 2 + R();
    const end = new THREE.Vector3(Math.cos(a) * o.spread * 0.55, crownY + R() * 1.5, Math.sin(a) * o.spread * 0.55);
    out.push({ geo: tube([new THREE.Vector3(0, o.trunkH * 0.9, 0), new THREE.Vector3(end.x * 0.5, (o.trunkH + end.y) / 2 + 0.6, end.z * 0.5), end], o.trunkR * 0.45, o.trunkR * 0.18, 6), mat: "bark", shadow: true });
  }
  for (let k = 0; k < o.clumps; k++) {
    // points spread over a flattened dome
    const u = R(), v = R();
    const th = u * Math.PI * 2, ph = Math.acos(1 - v * 1.25);
    const rr = 0.55 + 0.45 * R();
    const x = Math.sin(ph) * Math.cos(th) * o.spread * rr, z = Math.sin(ph) * Math.sin(th) * o.spread * rr;
    const y = crownY + Math.cos(ph) * o.height * 0.55 * rr;
    const cr = o.clumpR[0] + R() * (o.clumpR[1] - o.clumpR[0]);
    out.push({ geo: clump(cr, x, y, z, seed * 31 + k), mat: o.mats[k % o.mats.length], shadow: true });
  }
  return out;
}
const neem = (seed: number) => leafy(seed, { trunkH: 8, trunkR: 0.75, spread: 7, height: 8, clumps: 42, mats: ["neem1", "neem2", "neem3"], clumpR: [1.3, 2.2] });
const mango = (seed: number) => leafy(seed, { trunkH: 5.5, trunkR: 1.0, spread: 8, height: 9, clumps: 48, mats: ["mango1", "mango2", "mango1"], clumpR: [1.6, 2.6] });

function shrub(seed: number, flowering: boolean): Piece[] {
  const R = rng(seed), out: Piece[] = [];
  const n = 3 + Math.floor(R() * 3);
  for (let k = 0; k < n; k++) {
    const a = R() * Math.PI * 2, d = R() * 0.6;
    out.push({ geo: clump(0.65 + R() * 0.45, Math.cos(a) * d, 0.75 + R() * 0.5, Math.sin(a) * d, seed * 7 + k, 0.9), mat: k % 2 ? "shrub1" : "shrub2", shadow: true });
  }
  if (flowering) {
    const col = ["flowerPink", "flowerYellow", "flowerRed"][seed % 3];
    for (let k = 0; k < 14; k++) {
      const a = R() * Math.PI * 2, el = R() * 1.2;
      out.push({ geo: new THREE.IcosahedronGeometry(0.14, 0).translate(Math.cos(a) * 1.0 * Math.cos(el), 1.0 + Math.sin(el) * 0.9, Math.sin(a) * 1.0 * Math.cos(el)), mat: col, shadow: false });
    }
  }
  return out;
}

function potted(seed: number): Piece[] {
  const R = rng(seed), out: Piece[] = [];
  const prof = [[0.42, 0], [0.48, 0.08], [0.62, 1.5], [0.7, 1.55], [0.7, 1.7], [0.6, 1.7], [0.55, 1.6]].map(([x, y]) => new THREE.Vector2(x, y));
  out.push({ geo: new THREE.LatheGeometry(prof, 14), mat: "pot", shadow: true });
  out.push({ geo: new THREE.CircleGeometry(0.56, 12).rotateX(-Math.PI / 2).translate(0, 1.55, 0), mat: "soil", shadow: false });
  if (seed % 2) {  // snake-plant style tall leaves
    for (let k = 0; k < 7; k++) {
      const a = (k / 7) * Math.PI * 2 + R(), tilt = 0.08 + R() * 0.15, h = 1.6 + R() * 1.1;
      const g = new THREE.BoxGeometry(0.22, h, 0.05).translate(0, h / 2, 0).rotateZ(tilt).rotateY(a).translate(Math.cos(a) * 0.2, 1.55, Math.sin(a) * 0.2);
      out.push({ geo: g, mat: "potLeaf", shadow: true });
    }
  } else {
    for (let k = 0; k < 3; k++) out.push({ geo: clump(0.45 + R() * 0.2, (R() - 0.5) * 0.4, 2.1 + R() * 0.4, (R() - 0.5) * 0.4, seed * 5 + k, 0.95), mat: "shrub1", shadow: true });
  }
  return out;
}

export const PLANT_MATS: Record<string, [string, Partial<THREE.MeshStandardMaterialParameters>]> = {
  palmTrunk: ["#7d6b55", { roughness: 1 }], nut: ["#6f7a2a", { roughness: 0.7 }], frond: ["#3d7524", { roughness: 0.8, side: THREE.DoubleSide }],
  frondOld: ["#8c8a3a", { roughness: 0.9, side: THREE.DoubleSide }], frondSpine: ["#8d8a4a", { roughness: 0.9 }],
  arecaTrunk: ["#9a9a8e", { roughness: 0.95 }], crownShaft: ["#5f8a3a", { roughness: 0.7 }],
  bark: ["#5a4636", { roughness: 1 }], neem1: ["#35692a", { roughness: 0.9 }], neem2: ["#447a30", { roughness: 0.9 }],
  neem3: ["#2a5722", { roughness: 0.9 }], mango1: ["#1f4824", { roughness: 0.6 }], mango2: ["#2a5c2b", { roughness: 0.6 }],
  shrub1: ["#335f25", { roughness: 0.9 }], shrub2: ["#4a7531", { roughness: 0.9 }],
  flowerPink: ["#e0457b", { roughness: 0.7 }], flowerYellow: ["#f2c230", { roughness: 0.7 }], flowerRed: ["#e2462c", { roughness: 0.7 }],
  pot: ["#b5623a", { roughness: 0.9 }], soil: ["#4a3426", { roughness: 1 }], potLeaf: ["#4c7d34", { roughness: 0.8 }],
};

const MODEL: Record<PlantKind, (seed: number) => Piece[]> = {
  coconut, areca, neem, mango, shrubs: (s) => shrub(s, s % 2 === 0), potted,
};

// ------------------------------------------------------------------ placement
export type Site = {
  plotW: number; plotD: number;
  /** true when (x, y) in plot coords keeps radius r clear of every floor + roof overhang */
  clear: (x: number, y: number, r: number) => boolean;
  /** driveway / gate / main-door path (plot coords) – nothing is planted there */
  blocked: (x: number, y: number, r: number) => boolean;
  house: { x0: number; y0: number; x1: number; y1: number }; ov: number;
  door?: { x: number; y: number } | null;
};

function candidates(kind: PlantKind, place: Place, s: Site, r: number): [number, number][] {
  const { plotW: W, plotD: D, house: h, ov } = s;
  const pts: [number, number][] = [];
  const step = Math.max(2.2, r * 1.6);
  const off = Math.max(1.2, Math.min(r * 0.9, 3));  // distance from the compound wall
  const line = (x0: number, y0: number, x1: number, y1: number) => {
    const len = Math.hypot(x1 - x0, y1 - y0);
    if (len < 0) return;
    const n = Math.max(1, Math.floor(len / step));
    for (let i = 0; i <= n; i++) { const t = n ? i / n : 0.5; pts.push([x0 + (x1 - x0) * t, y0 + (y1 - y0) * t]); }
  };
  if (kind === "potted") {
    if (s.door) {  // pairs on both sides of the path to the main door, starting just outside the overhang
      for (let k = 0; k < 8; k++) {
        const y = s.door.y - ov - 1.2 - k * 2.6;
        if (y < 1) break;
        pts.push([s.door.x - 2.6, y], [s.door.x + 2.6, y]);
      }
    }
    line(off, off, W - off, off);
    return pts;
  }
  if (place === "edge") {
    line(off, off, W - off, off); line(off, D - off, W - off, D - off);
    line(off, off, off, D - off); line(W - off, off, W - off, D - off);
  } else if (place === "front") {
    const yA = off, yB = h.y0 - ov - 0.5;
    if (yB >= yA) line(off, (yA + yB) / 2, W - off, (yA + yB) / 2);
    if (yB - yA > step * 2) { line(off, yA + (yB - yA) * 0.2, W - off, yA + (yB - yA) * 0.2); line(off, yB, W - off, yB); }
  } else if (place === "rear") {
    const yA = h.y1 + ov + 0.5, yB = D - off;
    if (yB >= yA) { line(off, (yA + yB) / 2, W - off, (yA + yB) / 2); line(off, yB, W - off, yB); }
  } else {  // sides
    const xl = (off + h.x0 - ov - 0.5) / 2, xr = (h.x1 + ov + 0.5 + W - off) / 2;
    line(xl, h.y0, xl, h.y1); line(xr, h.y0, xr, h.y1);
    line(off, h.y0, off, h.y1); line(W - off, h.y0, W - off, h.y1);
  }
  return pts;
}

/** where trees go when the chosen yard is too small: just outside the compound wall (still on your road side
 *  view), never on the road */
function outside(s: Site, r: number): [number, number][] {
  const pts: [number, number][] = [];
  for (let y = 4; y < s.plotD; y += r * 2.2) pts.push([-r - 2.5, y], [s.plotW + r + 2.5, y]);
  for (let x = 0; x < s.plotW; x += r * 2.2) pts.push([x, s.plotD + r + 2.5]);
  return pts;
}

export type Placed = { kind: PlantKind; x: number; y: number; outside: boolean };

/** choose positions for every switched-on plant type (big trees first). Pure – used by the builder and tests. */
export function placePlants(plants: Plants | null | undefined, s: Site): Placed[] {
  const P = plantsOf(plants);
  const done: { x: number; y: number; r: number }[] = [];
  const out: Placed[] = [];
  const order: PlantKind[] = ["mango", "neem", "coconut", "areca", "shrubs", "potted"];
  // big + big: canopies may touch a little; small + small: side by side; small under a big canopy: keep off the trunk
  const sep = (a: number, b: number) => (a >= 2 && b >= 2 ? (a + b) * 0.7 : a < 2 && b < 2 ? (a + b) * 0.95 : Math.min(a, b) + 1.5);
  const free = (x: number, y: number, r: number) => done.every((d) => Math.hypot(d.x - x, d.y - y) > sep(d.r, r));
  for (const kind of order) {
    const o = P[kind];
    const want = o?.on ? Math.max(0, Math.min(PLANT_MAX[kind], o.count ?? 0)) : 0;
    if (!want) continue;
    const r = RADIUS[kind];
    const inside = candidates(kind, (o.place as Place) || "edge", s, r)
      .filter(([x, y]) => x >= 0.6 && x <= s.plotW - 0.6 && y >= 0.6 && y <= s.plotD - 0.6);
    // spread the picks evenly over the candidate list
    let got = 0;
    const tryList = (list: [number, number][], isOut: boolean) => {
      if (got >= want || !list.length) return;
      const stride = Math.max(1, Math.floor(list.length / want));
      const orderIdx = [...list.keys()].sort((a, b) => (a % stride) - (b % stride) || a - b);
      for (const i of orderIdx) {
        if (got >= want) break;
        const [x, y] = list[i];
        if (!isOut && (!s.clear(x, y, r) || s.blocked(x, y, Math.min(r, 2)))) continue;
        if (!free(x, y, r)) continue;
        done.push({ x, y, r }); out.push({ kind, x, y, outside: isOut }); got++;
      }
    };
    tryList(inside, false);
    if (kind !== "shrubs" && kind !== "potted") tryList(outside(s, r), true);
  }
  return out;
}

/** add the chosen plants to the scene. World: X = plot x, Z = −plot y. */
export function addPlants(root: THREE.Object3D, plants: Plants | null | undefined, s: Site, mat: MatFor) {
  const placed = placePlants(plants, s);
  placed.forEach((p, i) => {
    const seed = Math.round(p.x * 13 + p.y * 7) + i * 17 + 3;
    const rot = (seed % 360) * (Math.PI / 180);
    const scale = p.kind === "potted" || p.kind === "shrubs" ? 1 : 0.9 + (seed % 20) / 100;
    for (const pc of MODEL[p.kind](seed)) {
      const m = new THREE.Mesh(pc.geo, mat(pc.mat));
      m.rotation.y = rot; m.scale.setScalar(scale);
      m.position.set(p.x, 0, -p.y);
      m.castShadow = pc.shadow; m.receiveShadow = true;
      root.add(m);
    }
  });
  return placed;
}
