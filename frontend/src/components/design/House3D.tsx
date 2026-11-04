/** 1.11 – Real 3D (three.js / WebGL) built from the plan: plinth, walls with door & window openings, glass,
 *  doors, sunshades, slabs, stairs, parapet, head room, furniture, compound wall, road and trees.
 *  Views: Exterior / Interior (roof off, cut floor) / Walkthrough (eye height) / Exploded; camera presets
 *  (front, sides, rear, top), day / night, section cut, wireframe; colours for walls, floor, doors, frames;
 *  export PNG, GLB (3D model) and a WebM video (turntable).
 *  Units: 1 = 1 foot. World: X = plan x (left→right), Y = up, Z = −plan y (road / front towards +Z). */
import { useEffect, useMemo, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";
import { Camera, Download, Film, Footprints, Layers3, Moon, RotateCcw, Sun } from "lucide-react";
import { toast } from "../ui";
import { WALL_T, type Plan } from "../../lib/plan";

const PLINTH = 1.5, SLAB = 0.42, PARAPET = 3, HEADROOM = 8, EYE = 5.4;
const SILL: Record<string, number> = { window: 3, vent: 5.5 };

export type Finishes = { ext: string; int: string; floor: string; door: string; frame: string; roof: string; plinth: string };
export const DEFAULT_FINISH: Finishes = { ext: "#f3eadb", int: "#fbfaf7", floor: "#e7e0d3", door: "#8b5a2b", frame: "#f8fafc", roof: "#cfcac2", plinth: "#8d8d8d" };
export const SWATCHES: Record<keyof Finishes, [string, string][]> = {
  ext: [["#f3eadb", "Cream"], ["#ffffff", "White"], ["#d9d4cc", "Grey"], ["#e9d7b9", "Beige"], ["#cfe3f2", "Light blue"], ["#b5654a", "Brick"], ["#a39e93", "Stone"]],
  int: [["#fbfaf7", "Off-white"], ["#fff7e6", "Ivory"], ["#eef5ec", "Mint"], ["#f1ecf7", "Lilac"], ["#f7ecec", "Blush"]],
  floor: [["#e7e0d3", "Vitrified beige"], ["#f5f5f4", "White marble"], ["#9ca3af", "Granite grey"], ["#b08a62", "Wood"], ["#d6c7a1", "Kota stone"]],
  door: [["#8b5a2b", "Teak"], ["#5b3a1e", "Walnut"], ["#d2b48c", "Oak"], ["#e5e7eb", "White"]],
  frame: [["#f8fafc", "White UPVC"], ["#1f2937", "Black alu."], ["#8b5a2b", "Wood"]],
  roof: [["#cfcac2", "Concrete"], ["#b9473a", "Weathering tile"], ["#e5e7eb", "White coat"]],
  plinth: [["#8d8d8d", "Grey"], ["#6b4f3a", "Brown"], ["#2f2f2f", "Black granite"]],
};
const FIN_LABEL: Record<keyof Finishes, string> = { ext: "Exterior walls", int: "Interior walls", floor: "Flooring", door: "Doors", frame: "Window frames", roof: "Terrace", plinth: "Plinth" };

type Mode = "exterior" | "interior" | "walk" | "exploded";

function build(plan: Plan, fin: Finishes, o: { upTo: number; only: number | null; mode: Mode; furniture: boolean; surround: boolean; roof: boolean }) {
  const root = new THREE.Group();
  const H = plan.floor_height_ft || 10;
  const b = plan.building;
  const mats = new Map<string, THREE.Material>();
  const mat = (col: string, extra: Partial<THREE.MeshStandardMaterialParameters> = {}) => {
    const k = col + JSON.stringify(extra);
    if (!mats.has(k)) mats.set(k, new THREE.MeshStandardMaterial({ color: col, roughness: 0.85, metalness: 0, ...extra }));
    return mats.get(k)!;
  };
  const glass = new THREE.MeshPhysicalMaterial({ color: "#9fd3f5", transparent: true, opacity: 0.38, roughness: 0.05, metalness: 0.1 });
  const box = (x0: number, y0: number, z0: number, x1: number, y1: number, z1: number, m: THREE.Material, parent: THREE.Object3D, name = "") => {
    const w = Math.abs(x1 - x0), d = Math.abs(y1 - y0), h = Math.abs(z1 - z0);
    if (w < 0.01 || d < 0.01 || h < 0.01) return;
    const g = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), m);
    // plan (x, y, z-up) → world (X, Y-up, Z = −y), offset by the building position on the plot
    g.position.set(b.x + (x0 + x1) / 2, (z0 + z1) / 2, -(b.y + (y0 + y1) / 2));
    g.castShadow = true; g.receiveShadow = true; g.name = name;
    parent.add(g);
    return g;
  };
  const levels = plan.levels;
  const nShow = Math.min(levels.length, o.upTo);
  const gap = o.mode === "exploded" ? 6 : 0;
  // plinth
  const ext0 = extent(levels[0].rooms);
  box(ext0.x0 - 0.4, ext0.y0 - 0.4, 0, ext0.x1 + 0.4, ext0.y1 + 0.4, PLINTH, mat(fin.plinth), root, "plinth");
  for (let li = 0; li < nShow; li++) {
    if (o.only != null && li !== o.only) continue;
    const lv = levels[li];
    const g = new THREE.Group();
    g.name = lv.name;
    root.add(g);
    const z = PLINTH + li * H + li * gap;
    const e = extent(lv.rooms);
    const topLevel = li === nShow - 1 || o.only != null;
    const cutInterior = o.mode === "interior" && topLevel;
    const wallTop = cutInterior ? z + 4.5 : z + H - SLAB;
    // floors
    for (const r of lv.rooms) {
      const col = r.type === "parking" ? "#bdbdbd" : r.type === "toilet" || r.type === "common_toilet" ? "#dbe7ef" : r.type === "terrace" ? fin.roof : fin.floor;
      box(r.x, r.y, z - 0.05, r.x + r.w, r.y + r.d, z, mat(col, { roughness: 0.5 }), g, `floor ${r.name}`);
    }
    // walls with openings
    for (const w of lv.walls) {
      if (w.kind === "parapet") {
        alongWall(w, (s, e2, c0, horiz, th) => seg(horiz, s, e2, c0, th, z, z + PARAPET, mat(fin.ext), g));
        continue;
      }
      const th = (WALL_T[w.kind] || 0.5) / 2;
      const horiz = w.y1 === w.y2;
      const a0 = horiz ? Math.min(w.x1, w.x2) : Math.min(w.y1, w.y2);
      const a1 = horiz ? Math.max(w.x1, w.x2) : Math.max(w.y1, w.y2);
      const c0 = horiz ? w.y1 : w.x1;
      const m = mat(w.kind === "ext" ? fin.ext : fin.int);
      const ops = lv.openings.filter((op) => (horiz ? op.y1 === op.y2 && Math.abs(op.y1 - c0) < 0.01 : op.x1 === op.x2 && Math.abs(op.x1 - c0) < 0.01))
        .map((op) => ({ s: horiz ? Math.min(op.x1, op.x2) : Math.min(op.y1, op.y2), e: horiz ? Math.max(op.x1, op.x2) : Math.max(op.y1, op.y2), op }))
        .filter((q) => q.e > a0 + 0.01 && q.s < a1 - 0.01).sort((p, q) => p.s - q.s);
      let cur = a0;
      for (const { s, e: e2, op } of ops) {
        seg(horiz, cur, Math.max(cur, s), c0, th, z, wallTop, m, g);
        const isWin = op.type === "window" || op.type === "vent";
        const sill = isWin ? SILL[op.type] : 0;
        const head = Math.min(isWin ? sill + op.h : op.h, H - SLAB);
        const s2 = Math.max(cur, s), e3 = Math.min(e2, a1);
        seg(horiz, s2, e3, c0, th, z, z + Math.min(sill, wallTop - z), m, g);
        if (z + head < wallTop) seg(horiz, s2, e3, c0, th, z + head, wallTop, m, g);
        if (isWin && z + sill < wallTop) {
          const top = Math.min(z + head, wallTop);
          seg(horiz, s2, e3, c0, 0.06, z + sill, top, glass, g);
          // frame
          const fm = mat(fin.frame, { roughness: 0.4 });
          seg(horiz, s2, s2 + 0.18, c0, th * 0.6, z + sill, top, fm, g);
          seg(horiz, e3 - 0.18, e3, c0, th * 0.6, z + sill, top, fm, g);
          seg(horiz, s2, e3, c0, th * 0.6, z + sill, z + sill + 0.18, fm, g);
          seg(horiz, s2, e3, c0, th * 0.6, top - 0.18, top, fm, g);
          seg(horiz, (s2 + e3) / 2 - 0.06, (s2 + e3) / 2 + 0.06, c0, th * 0.6, z + sill, top, fm, g);
          // sunshade (chajja) on the outside of external walls
          if (w.kind === "ext" && !cutInterior) {
            const out = outward(lv, op.room, horiz, c0);
            if (horiz) box(s2 - 0.75, c0 + out * th, z + head + 0.35, e3 + 0.75, c0 + out * (th + 1.75), z + head + 0.6, mat("#bdb7ad"), g);
            else box(c0 + out * th, s2 - 0.75, z + head + 0.35, c0 + out * (th + 1.75), e3 + 0.75, z + head + 0.6, mat("#bdb7ad"), g);
          }
        } else if (!isWin && op.type !== "opening") {
          seg(horiz, s2, e3, c0, 0.12, z, z + Math.min(head, wallTop - z), mat(fin.door, { roughness: 0.6 }), g, true);
        }
        cur = Math.max(cur, e2);
      }
      seg(horiz, cur, a1, c0, th, z, wallTop, m, g);
    }
    // parking: columns + beam instead of walls on open sides
    for (const r of lv.rooms.filter((q) => q.type === "parking")) {
      for (const [cx, cy] of [[r.x, r.y], [r.x + r.w - 0.75, r.y], [r.x, r.y + r.d - 0.75], [r.x + r.w - 0.75, r.y + r.d - 0.75]])
        box(cx, cy, z, cx + 0.75, cy + 0.75, z + H - SLAB, mat("#e6e1d8"), g);
    }
    // stairs
    for (const r of lv.rooms.filter((q) => q.type === "stair" && q.d >= 7 && q.w >= 3)) {
      const steps = Math.max(8, Math.round(H / 0.5));
      const half = Math.ceil(steps / 2);
      const run = (r.d - 3.5) / half;
      const wHalf = r.w / 2 - 0.1;
      for (let k = 0; k < half; k++) { // up along +y on the left half, landing, back on the right half
        box(r.x + 0.1, r.y + 0.5 + k * run, z, r.x + 0.1 + wHalf, r.y + 0.5 + (k + 1) * run, z + (k + 1) * (H / steps), mat("#d6d3d1"), g);
      }
      box(r.x + 0.1, r.y + r.d - 3.0, z + half * (H / steps) - 0.4, r.x + r.w - 0.1, r.y + r.d - 0.1, z + half * (H / steps), mat("#d6d3d1"), g);
      for (let k = 0; k < steps - half; k++) {
        box(r.x + r.w / 2, r.y + r.d - 3.0 - (k + 1) * run, z + (half + k) * (H / steps), r.x + r.w - 0.1, r.y + r.d - 3.0 - k * run,
          z + (half + k + 1) * (H / steps), mat("#d6d3d1"), g);
      }
    }
    if (o.furniture) furnish(lv.rooms, z, box, mat, g);
    // slab over this floor
    const slabOn = !cutInterior && (li < nShow - 1 || o.roof);
    if (slabOn) {
      const stair = lv.rooms.find((r) => r.type === "stair");
      for (const r of lv.rooms) {
        if (r.type === "terrace" || r.type === "balcony" || r.type === "sitout") continue;
        if (stair && r.id === stair.id && li < levels.length - 1 && li < nShow - 1) continue; // stair opening
        box(r.x - 0.4, r.y - 0.4, z + H - SLAB, r.x + r.w + 0.4, r.y + r.d + 0.4, z + H, mat(li === nShow - 1 ? fin.roof : "#cfcac2"), g);
      }
    }
    // terrace parapet + head room on the top floor
    if (li === levels.length - 1 && topLevel && o.roof && o.mode !== "interior") {
      const zt = z + H;
      box(e.x0 - 0.4, e.y0 - 0.4, zt, e.x1 + 0.4, e.y0 + 0.1, zt + PARAPET, mat(fin.ext), g);
      box(e.x0 - 0.4, e.y1 - 0.1, zt, e.x1 + 0.4, e.y1 + 0.4, zt + PARAPET, mat(fin.ext), g);
      box(e.x0 - 0.4, e.y0, zt, e.x0 + 0.1, e.y1, zt + PARAPET, mat(fin.ext), g);
      box(e.x1 - 0.1, e.y0, zt, e.x1 + 0.4, e.y1, zt + PARAPET, mat(fin.ext), g);
      const st = lv.rooms.find((r) => r.type === "stair");
      if (st && levels.length > 1) {
        box(st.x, st.y, zt, st.x + st.w, st.y + st.d, zt + HEADROOM, mat(fin.ext), g);
        box(st.x - 0.6, st.y - 0.6, zt + HEADROOM, st.x + st.w + 0.6, st.y + st.d + 0.6, zt + HEADROOM + SLAB, mat(fin.roof), g);
      }
    }
  }
  if (o.surround) surroundings(plan, root, mat);
  return root;

  function seg(horiz: boolean, s: number, e2: number, c0: number, th: number, zb: number, zt: number, m: THREE.Material, parent: THREE.Object3D, door = false) {
    if (e2 - s < 0.02 || zt - zb < 0.02) return;
    const mesh = horiz ? box(s, c0 - th, zb, e2, c0 + th, zt, m, parent) : box(c0 - th, s, zb, c0 + th, e2, zt, m, parent);
    if (mesh && door) mesh.name = "door";
  }
}

function alongWall(w: { x1: number; y1: number; x2: number; y2: number }, fn: (s: number, e: number, c0: number, horiz: boolean, th: number) => void) {
  const horiz = w.y1 === w.y2;
  fn(horiz ? Math.min(w.x1, w.x2) : Math.min(w.y1, w.y2), horiz ? Math.max(w.x1, w.x2) : Math.max(w.y1, w.y2), horiz ? w.y1 : w.x1, horiz, 0.25);
}

function extent(rooms: { x: number; y: number; w: number; d: number }[]) {
  return { x0: Math.min(...rooms.map((r) => r.x)), x1: Math.max(...rooms.map((r) => r.x + r.w)), y0: Math.min(...rooms.map((r) => r.y)), y1: Math.max(...rooms.map((r) => r.y + r.d)) };
}

function outward(lv: Plan["levels"][number], roomId: string, horiz: boolean, c0: number) {
  const r = lv.rooms.find((q) => q.id === roomId);
  if (!r) return -1;
  return horiz ? (r.y + r.d / 2 > c0 ? -1 : 1) : (r.x + r.w / 2 > c0 ? -1 : 1);
}

function furnish(rooms: Plan["levels"][number]["rooms"], z: number,
  box: (x0: number, y0: number, z0: number, x1: number, y1: number, z1: number, m: THREE.Material, p: THREE.Object3D, n?: string) => any,
  mat: (c: string, e?: any) => THREE.Material, g: THREE.Object3D) {
  for (const r of rooms) {
    const { x, y, w, d, type } = r;
    if (type === "bedroom" && w >= 8 && d >= 8) {
      const bw = Math.min(5, w - 3), bl = Math.min(6.5, d - 2.5), bx = x + (w - bw) / 2, by = y + d - bl - 0.6;
      box(bx, by, z, bx + bw, by + bl, z + 1.6, mat("#e8dcc8"), g, "bed");
      box(bx, by + bl - 0.4, z, bx + bw, by + bl, z + 3.2, mat("#7a5230"), g, "headboard");
      box(bx + 0.3, by + bl - 1.6, z + 1.6, bx + bw - 0.3, by + bl - 0.6, z + 2.0, mat("#ffffff"), g, "pillow");
      if (w >= 10) box(x + 0.4, y + 0.6, z, x + 2.3, y + 4.6, z + 7, mat("#a0714f"), g, "wardrobe");
    } else if ((type === "hall" || type === "lounge") && w >= 8 && d >= 8) {
      box(x + 0.6, y + 1, z, x + 3.1, y + Math.min(8, d - 1.5), z + 2.6, mat("#6b7a99"), g, "sofa");
      box(x + 4, y + d / 2 - 1, z, x + 6.5, y + d / 2 + 1, z + 1.4, mat("#7a5230"), g, "table");
      box(x + w - 1.4, y + d / 2 - 2.5, z, x + w - 0.6, y + d / 2 + 2.5, z + 2.0, mat("#3f3f46"), g, "tv unit");
    } else if (type === "dining" && w >= 7 && d >= 7) {
      box(x + w / 2 - 2, y + d / 2 - 1.25, z, x + w / 2 + 2, y + d / 2 + 1.25, z + 2.5, mat("#8b5a2b"), g, "dining");
    } else if (type === "kitchen") {
      box(x + 0.3, y + 0.3, z, x + 2.3, y + d - 0.3, z + 2.8, mat("#4b5563"), g, "counter");
      box(x + 0.3, y + d - 2.3, z, x + Math.max(2.4, w - 0.3), y + d - 0.3, z + 2.8, mat("#4b5563"), g, "counter");
    } else if ((type === "toilet" || type === "common_toilet") && w >= 3.5 && d >= 4) {
      box(x + w - 2, y + d - 2.6, z, x + w - 0.6, y + d - 0.6, z + 1.4, mat("#ffffff"), g, "wc");
      box(x + 0.4, y + d - 1.6, z + 2.4, x + 2, y + d - 0.4, z + 2.9, mat("#ffffff"), g, "basin");
    } else if (type === "parking" && w >= 9 && d >= 14) {
      const cx = x + (w - 6) / 2, cy = y + (d - 13.5) / 2;
      box(cx, cy, z + 0.6, cx + 6, cy + 13.5, z + 3.2, mat("#b91c1c", { roughness: 0.35, metalness: 0.4 }), g, "car");
      box(cx + 0.5, cy + 3.5, z + 3.2, cx + 5.5, cy + 9.5, z + 4.8, mat("#1f2937", { roughness: 0.2 }), g, "car roof");
    }
  }
}

function surroundings(plan: Plan, root: THREE.Object3D, mat: (c: string, e?: any) => THREE.Material) {
  const P = plan.plot;
  const ground = new THREE.Mesh(new THREE.PlaneGeometry(P.w + 80, P.d + 80), mat("#8fbf73"));
  ground.rotation.x = -Math.PI / 2; ground.position.set(P.w / 2, -0.02, -P.d / 2); ground.receiveShadow = true; root.add(ground);
  const site = new THREE.Mesh(new THREE.PlaneGeometry(P.w, P.d), mat("#cbbf9f"));
  site.rotation.x = -Math.PI / 2; site.position.set(P.w / 2, 0.0, -P.d / 2); site.receiveShadow = true; root.add(site);
  const road = new THREE.Mesh(new THREE.PlaneGeometry(P.w + 80, 22), mat("#4b5563", { roughness: 0.95 }));
  road.rotation.x = -Math.PI / 2; road.position.set(P.w / 2, 0.01, 11 + 3); root.add(road);
  const cw = mat("#e7e1d6");
  const add = (x0: number, z0: number, x1: number, z1: number, h: number) => {
    const m = new THREE.Mesh(new THREE.BoxGeometry(Math.abs(x1 - x0) || 0.5, h, Math.abs(z1 - z0) || 0.5), cw);
    m.position.set((x0 + x1) / 2, h / 2, -(z0 + z1) / 2); m.castShadow = true; m.receiveShadow = true; root.add(m);
  };
  const gate = Math.min(12, P.w * 0.4), g0 = P.w / 2 - gate / 2;
  add(0, 0, g0, 0, 3.5); add(g0 + gate, 0, P.w, 0, 3.5); // front with gate opening
  add(0, P.d, P.w, P.d, 3.5); add(0, 0, 0, P.d, 3.5); add(P.w, 0, P.w, P.d, 3.5);
  const gateM = new THREE.Mesh(new THREE.BoxGeometry(gate, 3.2, 0.15), mat("#1f2937", { metalness: 0.6, roughness: 0.4 }));
  gateM.position.set(P.w / 2, 1.6, 0); root.add(gateM);
  for (const [tx, tz] of [[-6, 4], [P.w + 6, 6], [-8, -P.d * 0.6], [P.w + 7, -P.d * 0.7]]) { // simple trees
    const trunk = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.45, 6), mat("#6b4f3a")); trunk.position.set(tx, 3, tz); root.add(trunk);
    const top = new THREE.Mesh(new THREE.SphereGeometry(3.6, 14, 10), mat("#3f7d3a")); top.position.set(tx, 8, tz); top.castShadow = true; root.add(top);
  }
}

export default function House3D({ plan, finishes, onFinishes }: { plan: Plan; finishes?: Partial<Finishes>; onFinishes?: (f: Finishes) => void }) {
  const host = useRef<HTMLDivElement>(null);
  const ctx = useRef<{ renderer: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.PerspectiveCamera; controls: OrbitControls; model: THREE.Object3D | null; sun: THREE.DirectionalLight; amb: THREE.HemisphereLight; raf: number } | null>(null);
  const [mode, setMode] = useState<Mode>("exterior");
  const [upTo, setUpTo] = useState(plan.levels.length);
  const [only, setOnly] = useState<number | null>(null);
  const [night, setNight] = useState(false);
  const [furniture, setFurniture] = useState(true);
  const [surround, setSurround] = useState(true);
  const [roof, setRoof] = useState(true);
  const [wire, setWire] = useState(false);
  const [cut, setCut] = useState(false);
  const [rotate, setRotate] = useState(false);
  const [recording, setRecording] = useState(false);
  const fin: Finishes = { ...DEFAULT_FINISH, ...(finishes || {}) };
  const finKey = JSON.stringify(fin);
  const keys = useRef<Record<string, boolean>>({});

  // scene once
  useEffect(() => {
    const el = host.current!;
    const renderer = new THREE.WebGLRenderer({ antialias: true, preserveDrawingBuffer: true });
    renderer.setPixelRatio(Math.min(2, window.devicePixelRatio));
    renderer.setSize(el.clientWidth, el.clientHeight);
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.localClippingEnabled = true;
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(45, el.clientWidth / el.clientHeight, 0.3, 2000);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.maxPolarAngle = Math.PI * 0.495;
    const amb = new THREE.HemisphereLight("#ffffff", "#8a8a7a", 0.9);
    scene.add(amb);
    const sun = new THREE.DirectionalLight("#fff6e5", 2.2);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    const sc = sun.shadow.camera as THREE.OrthographicCamera;
    sc.left = -90; sc.right = 90; sc.top = 90; sc.bottom = -90; sc.far = 400;
    scene.add(sun, sun.target);
    const c = { renderer, scene, camera, controls, model: null as THREE.Object3D | null, sun, amb, raf: 0 };
    ctx.current = c;
    const clock = new THREE.Clock();
    const loop = () => {
      const dt = Math.min(0.05, clock.getDelta());
      const k = keys.current;
      if (camera.userData.walk) { // walkthrough: W/S forward-back, A/D turn, arrows too
        const dir = new THREE.Vector3(); camera.getWorldDirection(dir); dir.y = 0; dir.normalize();
        const sp = 9 * dt;
        if (k.w || k.arrowup) { camera.position.addScaledVector(dir, sp); controls.target.addScaledVector(dir, sp); }
        if (k.s || k.arrowdown) { camera.position.addScaledVector(dir, -sp); controls.target.addScaledVector(dir, -sp); }
        if (k.a || k.arrowleft || k.d || k.arrowright) {
          const ang = (k.a || k.arrowleft ? 1 : -1) * 1.6 * dt;
          const off = controls.target.clone().sub(camera.position).applyAxisAngle(new THREE.Vector3(0, 1, 0), ang);
          controls.target.copy(camera.position).add(off);
        }
      }
      if (camera.userData.spin) {
        const off = camera.position.clone().sub(controls.target).applyAxisAngle(new THREE.Vector3(0, 1, 0), 0.35 * dt);
        camera.position.copy(controls.target).add(off);
      }
      controls.update();
      renderer.render(scene, camera);
      c.raf = requestAnimationFrame(loop);
    };
    loop();
    const onResize = () => { renderer.setSize(el.clientWidth, el.clientHeight); camera.aspect = el.clientWidth / el.clientHeight; camera.updateProjectionMatrix(); };
    const ro = new ResizeObserver(onResize); ro.observe(el);
    const kd = (e: KeyboardEvent) => { keys.current[e.key.toLowerCase()] = true; };
    const ku = (e: KeyboardEvent) => { keys.current[e.key.toLowerCase()] = false; };
    window.addEventListener("keydown", kd); window.addEventListener("keyup", ku);
    return () => {
      cancelAnimationFrame(c.raf); ro.disconnect(); window.removeEventListener("keydown", kd); window.removeEventListener("keyup", ku);
      controls.dispose(); renderer.dispose(); el.removeChild(renderer.domElement); ctx.current = null;
    };
  }, []);

  // (re)build the model
  const centre = useMemo(() => {
    const e = extent(plan.levels[0].rooms);
    return new THREE.Vector3(plan.building.x + (e.x0 + e.x1) / 2, 0, -(plan.building.y + (e.y0 + e.y1) / 2));
  }, [plan]);
  useEffect(() => {
    const c = ctx.current; if (!c) return;
    if (c.model) { c.scene.remove(c.model); c.model.traverse((o: any) => o.geometry?.dispose?.()); }
    const m = build(plan, fin, { upTo, only, mode, furniture, surround, roof });
    m.traverse((o: any) => {
      if (o.material) { o.material.wireframe = wire; }
    });
    c.scene.add(m); c.model = m;
    applyClip();
  }, [plan, finKey, upTo, only, mode, furniture, surround, roof, wire]);

  // sky & light
  useEffect(() => {
    const c = ctx.current; if (!c) return;
    c.scene.background = new THREE.Color(night ? "#0b1324" : "#cfe6f7");
    c.scene.fog = new THREE.Fog(night ? "#0b1324" : "#cfe6f7", 150, 420);
    c.amb.intensity = night ? 0.25 : 0.9;
    c.sun.intensity = night ? 0.25 : 2.2;
    c.sun.color.set(night ? "#9db4ff" : "#fff6e5");
    c.sun.position.set(centre.x + 60, 90, centre.z + 70); c.sun.target.position.copy(centre);
    c.scene.children.filter((o) => o.userData.lamp).forEach((o) => c.scene.remove(o));
    if (night) { // warm lights inside every floor
      plan.levels.forEach((lv, i) => {
        const e = extent(lv.rooms);
        const l = new THREE.PointLight("#ffd9a0", 60, 40, 1.6);
        l.position.set(plan.building.x + (e.x0 + e.x1) / 2, PLINTH + i * (plan.floor_height_ft || 10) + 7, -(plan.building.y + (e.y0 + e.y1) / 2));
        l.userData.lamp = true; c.scene.add(l);
      });
    }
  }, [night, centre, plan]);

  useEffect(() => { const c = ctx.current; if (c) c.camera.userData.spin = rotate; }, [rotate]);
  useEffect(() => { applyClip(); }, [cut]);
  useEffect(() => { view(mode === "walk" ? "walk" : mode === "interior" ? "top" : "iso"); }, [mode, plan]);

  function applyClip() {
    const c = ctx.current; if (!c || !c.model) return;
    const plane = new THREE.Plane(new THREE.Vector3(0, 0, -1), centre.z); // keeps the rear half: section cut through the middle
    c.model.traverse((o: any) => { if (o.material) { o.material.clippingPlanes = cut ? [plane] : []; o.material.needsUpdate = true; } });
  }

  function view(v: "front" | "rear" | "left" | "right" | "top" | "iso" | "walk") {
    const c = ctx.current; if (!c) return;
    const H = plan.levels.length * (plan.floor_height_ft || 10) + PLINTH;
    const R = Math.max(plan.plot.w, plan.plot.d) * 1.25 + H;
    const t = centre.clone().setY(H / 2);
    c.camera.userData.walk = v === "walk";
    c.controls.maxPolarAngle = v === "top" ? Math.PI : Math.PI * 0.495;
    const pos: Record<string, THREE.Vector3> = {
      front: new THREE.Vector3(t.x, H * 0.55, t.z + R), rear: new THREE.Vector3(t.x, H * 0.55, t.z - R),
      left: new THREE.Vector3(t.x - R, H * 0.55, t.z), right: new THREE.Vector3(t.x + R, H * 0.55, t.z),
      top: new THREE.Vector3(t.x + 0.01, R * 1.3, t.z + 0.01), iso: new THREE.Vector3(t.x + R * 0.72, H * 0.9 + R * 0.35, t.z + R * 0.72),
    };
    if (v === "walk") { // stand at the front door, eye height, looking in
      const lv = plan.levels[0];
      const door = lv.openings.find((o) => o.type === "main_door") || lv.openings[0];
      const dx = plan.building.x + (door ? (door.x1 + door.x2) / 2 : extent(lv.rooms).x0 + 3);
      const dy = plan.building.y + (door ? door.y1 : extent(lv.rooms).y0);
      c.camera.position.set(dx, PLINTH + EYE, -(dy - 4));
      c.controls.target.set(dx, PLINTH + EYE, -(dy + 6));
      c.camera.fov = 70;
    } else {
      c.camera.position.copy(pos[v]); c.controls.target.copy(t); c.camera.fov = 45;
    }
    c.camera.updateProjectionMatrix();
  }

  const png = () => {
    const c = ctx.current; if (!c) return;
    c.renderer.render(c.scene, c.camera);
    const a = document.createElement("a"); a.href = c.renderer.domElement.toDataURL("image/png"); a.download = "Nexora_3D_view.png"; a.click();
  };
  const glb = () => {
    const c = ctx.current; if (!c?.model) return;
    new GLTFExporter().parse(c.model, (res: any) => {
      const blob = new Blob([res as ArrayBuffer], { type: "model/gltf-binary" });
      const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = "Nexora_3D_model.glb"; a.click();
    }, (err: any) => toast(String(err), "err"), { binary: true });
  };
  const video = async () => {
    const c = ctx.current; if (!c) return;
    const canvas = c.renderer.domElement as HTMLCanvasElement & { captureStream?: (fps: number) => MediaStream };
    if (!canvas.captureStream || typeof MediaRecorder === "undefined") return toast("This browser cannot record video – use Chrome or Edge", "err");
    const rec = new MediaRecorder(canvas.captureStream(30), { mimeType: MediaRecorder.isTypeSupported("video/webm;codecs=vp9") ? "video/webm;codecs=vp9" : "video/webm" });
    const chunks: Blob[] = [];
    rec.ondataavailable = (e) => chunks.push(e.data);
    rec.onstop = () => {
      const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob(chunks, { type: "video/webm" })); a.download = "Nexora_3D_walkaround.webm"; a.click();
      setRecording(false); setRotate(false);
    };
    view("iso"); setRotate(true); setRecording(true); rec.start();
    toast("Recording a 15 s turntable video…");
    setTimeout(() => rec.stop(), 15000);
  };

  const modes: [Mode, string, any][] = [["exterior", "Exterior View", Layers3], ["interior", "Interior View", Layers3], ["walk", "Walkthrough", Footprints], ["exploded", "Exploded View", Layers3]];
  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        {modes.map(([m, l, I]) => (
          <button key={m} onClick={() => setMode(m)} className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-semibold ${mode === m ? "bg-brand-600 text-white" : "bg-brand-50 text-navy-ink"}`}><I size={15} />{l}</button>
        ))}
        <span className="flex-1" />
        <button className="btn-outline btn-sm" onClick={() => setNight(!night)}>{night ? <Sun size={14} /> : <Moon size={14} />}{night ? "Day" : "Night"}</button>
      </div>
      <div className="relative overflow-hidden rounded-lg border border-line">
        <div ref={host} className="h-[520px] w-full touch-none" />
        <div className="absolute bottom-2 left-3 rounded bg-white/80 px-2 py-1 text-xs text-slate-600">
          {mode === "walk" ? "Walkthrough: W / S or ↑ ↓ to walk, A / D or ← → to turn, drag to look" : "Drag to rotate · scroll / pinch to zoom · right-drag to pan"}
        </div>
        {recording && <div className="absolute right-3 top-3 rounded bg-red-600 px-2 py-1 text-xs font-bold text-white">● REC</div>}
      </div>
      <div className="flex flex-wrap items-center gap-1.5 text-sm">
        <span className="mr-1 text-xs font-semibold text-slate-500"><Camera size={13} className="mr-1 inline" />Camera</span>
        {(["iso", "front", "left", "right", "rear", "top"] as const).map((v) => (
          <button key={v} className="btn-outline btn-sm" onClick={() => view(v)}>{{ iso: "3D", front: "Front", left: "Left side", right: "Right side", rear: "Rear", top: "Top" }[v]}</button>
        ))}
        <button className="btn-ghost btn-sm" onClick={() => view("iso")}><RotateCcw size={14} />Reset</button>
        <span className="flex-1" />
        <button className="btn-outline btn-sm" onClick={png}><Download size={14} />Image (PNG)</button>
        <button className="btn-outline btn-sm" onClick={glb}><Download size={14} />3D model (GLB)</button>
        <button className="btn-outline btn-sm" disabled={recording} onClick={video}><Film size={14} />Video</button>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        <div className="rounded-lg border border-line p-3 text-sm">
          <div className="mb-2 text-xs font-semibold text-navy-ink">Floors &amp; display</div>
          <div className="mb-2 flex flex-wrap gap-1.5">
            {plan.levels.map((l, i) => (
              <button key={i} onClick={() => { setOnly(only === i ? null : i); setUpTo(plan.levels.length); }}
                className={`rounded-md px-2.5 py-1 text-xs font-semibold ${only === i ? "bg-brand-600 text-white" : "bg-slate-100 text-navy-ink"}`}>{l.name} only</button>
            ))}
            <label className="ml-1 flex items-center gap-1 text-xs">Up to
              <select className="input w-auto py-0.5 text-xs" value={upTo} onChange={(e) => { setUpTo(Number(e.target.value)); setOnly(null); }}>
                {plan.levels.map((l, i) => <option key={i} value={i + 1}>{l.name}</option>)}
              </select></label>
          </div>
          <div className="grid grid-cols-2 gap-1.5 text-xs">
            {([["Furniture", furniture, setFurniture], ["Surroundings (plot, road, trees)", surround, setSurround], ["Roof / terrace", roof, setRoof],
              ["Section cut (half)", cut, setCut], ["Wireframe", wire, setWire], ["Auto rotate", rotate, setRotate]] as [string, boolean, (v: boolean) => void][]).map(([l, v, f]) => (
              <label key={l} className="flex items-center gap-2"><input type="checkbox" className="h-4 w-4 accent-brand-600" checked={v} onChange={(e) => f(e.target.checked)} />{l}</label>
            ))}
          </div>
        </div>
        <div className="rounded-lg border border-line p-3 text-sm">
          <div className="mb-2 text-xs font-semibold text-navy-ink">Material &amp; colour options</div>
          <div className="space-y-1.5">
            {(Object.keys(SWATCHES) as (keyof Finishes)[]).map((k) => (
              <div key={k} className="flex flex-wrap items-center gap-1.5">
                <span className="w-28 shrink-0 text-xs text-slate-500">{FIN_LABEL[k]}</span>
                {SWATCHES[k].map(([col, name]) => (
                  <button key={col} title={name} onClick={() => onFinishes?.({ ...fin, [k]: col })}
                    className={`h-6 w-6 rounded-md border ${fin[k] === col ? "ring-2 ring-brand-500 ring-offset-1" : "border-slate-300"}`} style={{ background: col }} />
                ))}
              </div>
            ))}
          </div>
          <p className="mt-2 text-[11px] text-slate-500">Colours are saved with the design (press Save). Concept visual – not a photo-real render.</p>
        </div>
      </div>
    </div>
  );
}
