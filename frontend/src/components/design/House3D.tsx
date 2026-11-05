/** 1.13 – 3D house (three.js) built from the plan.
 *  Elevation styles: Modern (stone + wood + black frames, deep overhangs with downlights), Contemporary
 *  (two-tone, tiles, fins, pergola), Traditional Tamil Nadu (tile roof, thinnai, pillars) and Basic.
 *  Light: Day / Evening / Night. Views: Exterior, Interior, Walkthrough (first person, walls stop you,
 *  doors open, stairs to other floors, jump to a room), Exploded, Structure.
 *  Stable view: no overlapping faces (no flicker), steady camera (resets only when the
 *  plan's shape or the view mode changes – not when a colour is picked), shadows drawn once.
 *  Downloads: current view PNG, Front / Left / Right / Rear images, one sheet with all views, GLB, video. */
import { useEffect, useMemo, useRef, useState, type PointerEvent as RPointerEvent } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { GLTFExporter } from "three/examples/jsm/exporters/GLTFExporter.js";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { api, fileObjectUrl } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import MaterialPanel from "./MaterialPanel";
import { BUILTIN, lookOf, procTex, type Item, type Look, type Slot } from "./house3d/catalog";
import {
  ArrowDown, ArrowLeft, ArrowRight, ArrowUp, Camera, ChevronsDown, ChevronsUp, Download, Film, Footprints, Images,
  Layers3, LogOut, Moon, RotateCcw, Sun, Sunset,
} from "lucide-react";
import { toast } from "../ui";
import type { Plan } from "../../lib/plan";
import {
  build, collide, DEFAULT_FINISH, extent, PLINTH, roomAt, STYLE_FINISH, walkSegments,
  type Finishes, type LightMode, type Mode, type Style,
} from "./house3d/build";
import * as T from "./house3d/textures";

export type { Finishes };
export { DEFAULT_FINISH };
const EYE = 5.3;

export const SWATCHES: Record<Exclude<keyof Finishes, "style" | "mat" | "rooms">, [string, string][]> = {
  ext: [["#efe7d8", "Cream"], ["#ffffff", "White"], ["#f5f5f3", "Off-white"], ["#d9d4cc", "Grey"], ["#f2deb0", "Sandal"], ["#e9d7b9", "Beige"], ["#cfe3f2", "Light blue"], ["#b5654a", "Brick"]],
  int: [["#fbfaf7", "Off-white"], ["#fff7e6", "Ivory"], ["#eef5ec", "Mint"], ["#f1ecf7", "Lilac"], ["#f7ecec", "Blush"]],
  floor: [["#e7e0d3", "Vitrified beige"], ["#f5f5f4", "White marble"], ["#9ca3af", "Granite grey"], ["#b08a62", "Wood"], ["#d6c7a1", "Kota stone"], ["#b5523a", "Red oxide"]],
  door: [["#9a6a3f", "Teak"], ["#5b3a1e", "Walnut"], ["#d2b48c", "Oak"], ["#6b3f1f", "Rosewood"], ["#e5e7eb", "White"]],
  frame: [["#1d2024", "Black alu."], ["#3a3f46", "Grey alu."], ["#f8fafc", "White UPVC"], ["#6b3f1f", "Wood"]],
  roof: [["#cfcac2", "Concrete"], ["#d6d2ca", "Light concrete"], ["#b9473a", "Weathering tile"], ["#e5e7eb", "White coat"]],
  plinth: [["#3b3a38", "Charcoal"], ["#8d8d8d", "Grey"], ["#6b4f3a", "Brown"], ["#7a2e1f", "Maroon"], ["#2f2f2f", "Black granite"]],
};
export const FIN_LABEL: Record<Exclude<keyof Finishes, "style" | "mat" | "rooms">, string> = { ext: "Exterior walls", int: "Interior walls", floor: "Flooring", door: "Doors", frame: "Window frames", roof: "Terrace", plinth: "Plinth" };
const STYLES: [Style, string, string][] = [
  ["modern", "Modern", "Stone + wood cladding, black frames, deep roof overhang with lights"],
  ["contemporary", "Contemporary", "Two-tone, grey tiles, wooden fins, terrace pergola"],
  ["traditional", "Traditional TN", "Tiled sloping roof, thinnai, round pillars, arches"],
  ["basic", "Basic", "Simple plaster finish (earlier look)"],
];
type View = "front" | "rear" | "left" | "right" | "top" | "iso";
type Ctx = {
  renderer: THREE.WebGLRenderer; scene: THREE.Scene; camera: THREE.PerspectiveCamera; controls: OrbitControls;
  model: THREE.Object3D | null; sun: THREE.DirectionalLight; hemi: THREE.HemisphereLight; raf: number; roomLights: THREE.Light[];
};

export default function House3D({ plan, finishes, onFinishes, pid, designId }: {
  plan: Plan; finishes?: Partial<Finishes>; onFinishes?: (f: Finishes) => void; pid?: number; designId?: number;
}) {
  const host = useRef<HTMLDivElement>(null);
  const ctx = useRef<Ctx | null>(null);
  const [mode, setMode] = useState<Mode>("exterior");
  const [upTo, setUpTo] = useState(plan.levels.length);
  const [only, setOnly] = useState<number | null>(null);
  const [inFloor, setInFloor] = useState(0);  // 1.15: Interior view shows ONE floor at a time
  const [light, setLight] = useState<LightMode>("day");
  const [furniture, setFurniture] = useState(true);
  const [surround, setSurround] = useState(true);
  const [roof, setRoof] = useState(true);
  const [wire, setWire] = useState(false);
  const [cut, setCut] = useState(false);
  const [rotate, setRotate] = useState(false);
  const [recording, setRecording] = useState(false);
  const [edges, setEdges] = useState(false);
  const [flat, setFlat] = useState(false);
  const [structure, setStructure] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [walkInfo, setWalkInfo] = useState<{ level: number; room: string; stair: boolean }>({ level: 0, room: "", stair: false });
  const fin: Finishes = { ...DEFAULT_FINISH, ...(finishes || {}) };
  const style: Style = (fin.style as Style) || "modern";
  // 1.15 material library: your own items (with their photos) + built-ins → what each part of the house looks like
  const user = useAuth()?.user;
  const [custom, setCustom] = useState<Item[]>([]);
  const photos = useRef(new Map<string, THREE.Texture>());
  const [photoVer, setPhotoVer] = useState(0);
  const loadLibrary = () => api<any>("/api/materials").then(async (r) => {
    const its: Item[] = (r.items || []).map((i: any) => ({ ref: i.ref, id: i.id, cat: i.category, name: i.name, brand: i.brand, code: i.code, color: i.color,
      tile: i.tile_ft, finish: i.finish, rate: i.rate, unit: i.unit, custom: true, image: null as string | null, _url: i.image_url }));
    setCustom(its);
    await Promise.all((r.items || []).map(async (i: any, k: number) => {
      if (!i.image_url) return;
      try {
        const url = await fileObjectUrl(i.image_url);
        its[k].image = url;
        photos.current.set(i.ref, await new THREE.TextureLoader().loadAsync(url));
      } catch { /* picture missing – the colour is used */ }
    }));
    setCustom([...its]); setPhotoVer((v) => v + 1);
  }).catch(() => {});
  useEffect(() => { loadLibrary(); }, []);  // eslint-disable-line react-hooks/exhaustive-deps
  const items = useMemo(() => [...BUILTIN, ...custom], [custom]);
  const byRef = useMemo(() => new Map(items.map((i) => [i.ref, i])), [items]);
  const swatches = useRef(new Map<string, string>());
  const swatch = (it: Item) => {
    if (it.image) return it.image;
    if (!swatches.current.has(it.ref)) swatches.current.set(it.ref, T.swatchUrl(procTex(it), it.color));
    return swatches.current.get(it.ref)!;
  };
  const looks = useRef(new Map<string, Look>());
  useEffect(() => { looks.current.clear(); }, [photoVer]);
  const lookFor = (slot: Slot, roomId?: string): Look | null => {
    let ref: string | undefined;
    const rp = roomId ? fin.rooms?.[roomId] : undefined;
    if (rp) {
      if ((slot === "floor" || slot === "wet_floor") && rp.floor) ref = rp.floor;
      if (slot === "int_wall" && rp.wall) ref = rp.wall;
      if (slot === "wet_wall" && rp.wall && byRef.get(rp.wall)?.cat === "wall_tile") ref = rp.wall;
    }
    ref = ref || fin.mat?.[slot];
    if (!ref) return null;
    const it = byRef.get(ref);
    if (!it) return null;
    if (!looks.current.has(ref)) { const l = lookOf(it, photos.current); if (l) looks.current.set(ref, l); }
    return looks.current.get(ref) || null;
  };
  const finKey = JSON.stringify(fin);
  const keys = useRef<Record<string, boolean>>({});
  const walk = useRef({ li: 0, x: 0, y: 0, yaw: 0, pitch: 0, h: 0, segs: new Map<number, ReturnType<typeof walkSegments>>(), label: "" });
  const smooth = useRef({ x: 0, y: 0, h: 0, yaw: 0, pitch: 0 });

  // geometry key: the camera is reset only when the SHAPE of the plan changes (not on colour changes)
  const planKey = useMemo(() => JSON.stringify({ l: plan.levels.map((l) => [l.rooms, l.openings, l.walls]), b: plan.building, p: plan.plot, h: plan.floor_height_ft }), [plan]);
  const planRef = useRef(plan); planRef.current = plan;
  const lightRef = useRef(light); lightRef.current = light;
  const centre = useMemo(() => {
    const e = extent(plan.levels[0].rooms);
    return new THREE.Vector3(plan.building.x + (e.x0 + e.x1) / 2, 0, -(plan.building.y + (e.y0 + e.y1) / 2));
  }, [planKey]);  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {  // latest saved structural design of this floor plan (for the Structure view)
    if (mode !== "structure" || !pid) return;
    api<any[]>(`/api/projects/${pid}/structural`).then(async (list) => {
      const v = list.find((x) => !designId || x.design_id === designId) || list[0];
      if (!v) { toast("No structural design yet – make one in the Structural tab and Save", "err"); setMode("exterior"); return; }
      setStructure((await api<any>(`/api/structural/${v.id}`)).result);
    }).catch((e) => toast(e.message, "err"));
  }, [mode, pid, designId]);

  // ------------------------------------------------------------------ scene (once)
  useEffect(() => {
    const el = host.current!;
    // no logarithmic depth: the model has no overlapping faces any more, and log depth made every pixel slow
    const renderer = new THREE.WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    const maxPR = Math.min(2, window.devicePixelRatio || 1);
    renderer.setPixelRatio(maxPR);
    renderer.setSize(el.clientWidth, el.clientHeight, false);
    Object.assign(renderer.domElement.style, { width: "100%", height: "100%", display: "block" });
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    renderer.shadowMap.autoUpdate = false;  // the house does not move: shadows are drawn once, no shimmer
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    el.appendChild(renderer.domElement);
    const scene = new THREE.Scene();
    const pmrem = new THREE.PMREMGenerator(renderer);
    scene.environment = pmrem.fromScene(new RoomEnvironment(), 0.04).texture;
    const camera = new THREE.PerspectiveCamera(45, el.clientWidth / Math.max(1, el.clientHeight), 1, 2500);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.09;
    controls.rotateSpeed = 0.65;
    controls.zoomSpeed = 0.9;
    controls.panSpeed = 0.8;
    controls.minDistance = 6;
    controls.maxDistance = 900;
    controls.maxPolarAngle = Math.PI * 0.495;
    controls.screenSpacePanning = true;
    const hemi = new THREE.HemisphereLight("#ffffff", "#8a8a7a", 0.7);
    const sun = new THREE.DirectionalLight("#fff6e5", 2.4);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    sun.shadow.bias = -0.0006;
    sun.shadow.normalBias = 0.06;
    scene.add(hemi, sun, sun.target);
    // 1.15: no extra room lights at all – every light is computed for every pixel, so lights made the walkthrough slow.
    // Inside, the soft sky light (hemisphere) + reflections light the rooms evenly.
    const c: Ctx = { renderer, scene, camera, controls, model: null, sun, hemi, raf: 0, roomLights: [] };
    ctx.current = c;
    const clock = new THREE.Clock();
    // adaptive sharpness: if the laptop is slow, draw fewer pixels (smooth), and go back up when it is fast again
    let frames = 0, acc = 0, pr = maxPR;
    const loop = () => {
      const raw = clock.getDelta();
      const dt = Math.min(0.1, raw);
      frames++; acc += raw;
      if (acc > 1.0) {
        const fps = frames / acc; frames = 0; acc = 0;
        const want = fps < 40 ? Math.max(0.75, pr - 0.25) : fps > 57 ? Math.min(maxPR, pr + 0.25) : pr;
        if (want !== pr) { pr = want; renderer.setPixelRatio(pr); renderer.setSize(el.clientWidth, el.clientHeight, false); }
      }
      if (camera.userData.walk) walkStep(dt);
      else {
        if (camera.userData.spin) {
          const off = camera.position.clone().sub(controls.target).applyAxisAngle(new THREE.Vector3(0, 1, 0), 0.3 * dt);
          camera.position.copy(controls.target).add(off);
        }
        if (controls.target.y < 0) controls.target.y = 0;
        controls.update();
      }
      renderer.render(scene, camera);
      c.raf = requestAnimationFrame(loop);
    };
    loop();
    const onResize = () => {
      const w = el.clientWidth, h = el.clientHeight;
      if (!w || !h) return;
      const cur = renderer.getSize(new THREE.Vector2());
      if (Math.abs(cur.x - w) < 1 && Math.abs(cur.y - h) < 1) return;  // no resize loop (was a cause of shaking)
      renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix();
    };
    const ro = new ResizeObserver(onResize); ro.observe(el);
    const typing = (e: KeyboardEvent) => { const t = e.target as HTMLElement; return t && (t.tagName === "INPUT" || t.tagName === "SELECT" || t.tagName === "TEXTAREA"); };
    const kd = (e: KeyboardEvent) => {
      if (typing(e)) return;
      const k = e.key.toLowerCase();
      if (camera.userData.walk) {
        if (["arrowup", "arrowdown", "arrowleft", "arrowright", " "].includes(k)) e.preventDefault();
        if (k === "escape") { setMode("exterior"); return; }
        if (k === "e") stairGo(1);
        if (k === "q") stairGo(-1);
      }
      keys.current[k] = true;
    };
    const ku = (e: KeyboardEvent) => { keys.current[e.key.toLowerCase()] = false; };
    window.addEventListener("keydown", kd); window.addEventListener("keyup", ku);
    // drag to look around in the walkthrough
    let drag: { x: number; y: number } | null = null;
    const pd = (e: PointerEvent) => { if (camera.userData.walk) { drag = { x: e.clientX, y: e.clientY }; renderer.domElement.setPointerCapture(e.pointerId); } };
    const pm = (e: PointerEvent) => {
      if (!drag || !camera.userData.walk) return;
      const w = walk.current;
      w.yaw += (e.clientX - drag.x) * 0.0042; w.pitch = Math.max(-1.1, Math.min(1.1, w.pitch - (e.clientY - drag.y) * 0.0035));
      drag = { x: e.clientX, y: e.clientY };
    };
    const pu = () => { drag = null; };
    renderer.domElement.addEventListener("pointerdown", pd); renderer.domElement.addEventListener("pointermove", pm);
    window.addEventListener("pointerup", pu);
    return () => {
      cancelAnimationFrame(c.raf); ro.disconnect();
      window.removeEventListener("keydown", kd); window.removeEventListener("keyup", ku); window.removeEventListener("pointerup", pu);
      controls.dispose(); disposeModel(c.model); renderer.dispose(); pmrem.dispose();
      if (renderer.domElement.parentElement === el) el.removeChild(renderer.domElement);
      ctx.current = null;
    };
  }, []);

  function disposeModel(m: THREE.Object3D | null) {
    if (!m) return;
    m.traverse((o: any) => {
      o.geometry?.dispose?.();
      const ms = Array.isArray(o.material) ? o.material : o.material ? [o.material] : [];
      ms.forEach((x: THREE.Material) => x.dispose());  // textures are shared and kept
    });
  }

  // ------------------------------------------------------------------ (re)build the model
  // the walkthrough shows the same model as the default exterior view, so switching to it needs no rebuild
  const walkingNow = mode === "walk";
  const buildKey = JSON.stringify(walkingNow
    ? { m: "exterior", u: plan.levels.length, o: null, f: true, r: true }
    : mode === "interior" ? { m: mode, u: plan.levels.length, o: inFloor, f: furniture, r: false }
    : { m: mode, u: upTo, o: only, f: furniture, r: roof });
  function setDoors(root: THREE.Object3D, open: boolean) {
    root.traverse((o: any) => { if (o.userData?.openAngle != null) o.rotation.y = open ? o.userData.openAngle : 0; });
    const c = ctx.current; if (c) c.renderer.shadowMap.needsUpdate = true;
  }
  useEffect(() => {
    const c = ctx.current; if (!c) return;
    if (c.model) { c.scene.remove(c.model); disposeModel(c.model); c.model = null; }
    if (mode === "structure" && !structure) return;
    const walking = mode === "walk";
    const { root } = build(plan, fin, {
      upTo: walking || mode === "interior" ? plan.levels.length : upTo, only: walking ? null : mode === "interior" ? inFloor : only,
      mode: walking ? "exterior" : mode, furniture: walking || furniture,
      surround: surround && mode !== "structure", roof: walking || (mode !== "interior" && roof), edges, structure, style, light, look: lookFor,
    });
    setDoors(root, walking);
    if (wire) root.traverse((o: any) => { const ms = Array.isArray(o.material) ? o.material : o.material ? [o.material] : []; ms.forEach((m: any) => { m.wireframe = true; }); });
    c.scene.add(root); c.model = root;
    applyClip();
    c.renderer.shadowMap.needsUpdate = true;
    walk.current.segs.clear();
  }, [planKey, finKey, buildKey, surround, wire, edges, structure, style, light, photoVer, custom.length]);  // eslint-disable-line react-hooks/exhaustive-deps
  // entering / leaving the walkthrough only opens / closes the doors – no rebuild (no waiting)
  useEffect(() => { const c = ctx.current; if (c?.model) setDoors(c.model, mode === "walk"); }, [mode]);

  // ------------------------------------------------------------------ sky & light
  useEffect(() => {
    const c = ctx.current; if (!c) return;
    const P = plan.plot;
    const span = Math.max(P.w, P.d) / 2 + 40;
    c.scene.background = T.sky(light);
    const fogCol = light === "night" ? "#0b1324" : light === "dusk" ? "#3a4a70" : "#cfe6f7";
    c.scene.fog = new THREE.Fog(fogCol, 260, 900);
    const walking = mode === "walk";
    if (light === "day") {
      c.hemi.color.set("#ffffff"); c.hemi.groundColor.set("#8a8a7a"); c.hemi.intensity = walking ? 1.35 : 0.75;
      c.sun.color.set("#fff4e0"); c.sun.intensity = 2.5; c.renderer.toneMappingExposure = 1.0; c.scene.environmentIntensity = 0.55;
      c.sun.position.set(centre.x + 70, 110, centre.z + 80);
    } else if (light === "dusk") {
      c.hemi.color.set("#7c8fc4"); c.hemi.groundColor.set("#3b3226"); c.hemi.intensity = walking ? 1.1 : 0.35;
      c.sun.color.set("#ffae6b"); c.sun.intensity = 0.9; c.renderer.toneMappingExposure = 1.15; c.scene.environmentIntensity = 0.25;
      c.sun.position.set(centre.x - 110, 32, centre.z + 50);
    } else {
      c.hemi.color.set("#41507a"); c.hemi.groundColor.set("#14161c"); c.hemi.intensity = walking ? 0.9 : 0.16;
      c.sun.color.set("#9db4ff"); c.sun.intensity = 0.3; c.renderer.toneMappingExposure = 1.05; c.scene.environmentIntensity = 0.1;
      c.sun.position.set(centre.x + 40, 120, centre.z - 60);
    }
    c.sun.target.position.copy(centre);
    const sc = c.sun.shadow.camera;
    sc.left = -span; sc.right = span; sc.top = span; sc.bottom = -span; sc.near = 1; sc.far = 600;
    sc.updateProjectionMatrix();
    c.renderer.shadowMap.needsUpdate = true;
  }, [light, centre, plan.plot, mode]);

  useEffect(() => { const c = ctx.current; if (c) c.camera.userData.spin = rotate; }, [rotate]);
  useEffect(() => { applyClip(); }, [cut]);
  // camera: only when the view mode or the plan's shape changes
  useEffect(() => {
    if (mode === "walk") startWalk();
    else { const c = ctx.current; if (c) { c.camera.userData.walk = false; c.controls.enabled = true; clearRoomLights(); } if (mode === "interior") floorView(inFloor); else view("iso"); }
  }, [mode, planKey]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (mode === "interior") floorView(inFloor); }, [inFloor]);  // eslint-disable-line react-hooks/exhaustive-deps

  function applyClip() {
    const c = ctx.current; if (!c || !c.model) return;
    const plane = new THREE.Plane(new THREE.Vector3(0, 0, -1), centre.z);
    c.model.traverse((o: any) => {
      const ms = Array.isArray(o.material) ? o.material : o.material ? [o.material] : [];
      ms.forEach((m: any) => { m.clippingPlanes = cut ? [plane] : []; m.needsUpdate = true; });
    });
    c.renderer.localClippingEnabled = cut;
    c.renderer.shadowMap.needsUpdate = true;
  }

  function camFor(v: View) {
    const p = planRef.current;
    const H = p.levels.length * (p.floor_height_ft || 10) + PLINTH;
    const R = Math.max(p.plot.w, p.plot.d) * 1.15 + H;
    const t = centre.clone().setY(H / 2.2);
    const pos: Record<View, THREE.Vector3> = {
      front: new THREE.Vector3(t.x, H * 0.45, t.z + R), rear: new THREE.Vector3(t.x, H * 0.45, t.z - R),
      left: new THREE.Vector3(t.x - R, H * 0.45, t.z), right: new THREE.Vector3(t.x + R, H * 0.45, t.z),
      top: new THREE.Vector3(t.x, R * 1.4, t.z + 1.5), iso: new THREE.Vector3(t.x + R * 0.62, H * 0.6 + R * 0.28, t.z + R * 0.78),  // top: road at the bottom
    };
    return { pos: pos[v], target: t, R, H };
  }

  function view(v: View) {
    const c = ctx.current; if (!c) return;
    c.camera.userData.walk = false; c.controls.enabled = true;
    c.controls.maxPolarAngle = v === "top" ? Math.PI : Math.PI * 0.495;
    const { pos, target } = camFor(v);
    c.camera.position.copy(pos); c.controls.target.copy(target);
    c.camera.fov = 45; c.camera.near = 1; c.camera.far = 2500; c.camera.updateProjectionMatrix();
    c.controls.update();
  }

  /** Interior: look down into ONE floor (walls cut at 4.5 ft, nothing above it) */
  function floorView(li: number) {
    const c = ctx.current; if (!c) return;
    const p = planRef.current;
    const e = extent(p.levels[li].rooms);
    const z = PLINTH + li * (p.floor_height_ft || 10);
    const span = Math.max(e.x1 - e.x0, e.y1 - e.y0);
    const t = new THREE.Vector3(p.building.x + (e.x0 + e.x1) / 2, z + 1.5, -(p.building.y + (e.y0 + e.y1) / 2));
    c.camera.userData.walk = false; c.controls.enabled = true; c.controls.maxPolarAngle = Math.PI * 0.495;
    c.camera.position.set(t.x + span * 0.35, z + span * 1.25, t.z + span * 0.85);
    c.controls.target.copy(t);
    c.camera.fov = 45; c.camera.near = 1; c.camera.far = 2500; c.camera.updateProjectionMatrix();
    c.controls.update();
  }

  // ------------------------------------------------------------------ walkthrough
  function segsFor(li: number) {
    const w = walk.current;
    if (!w.segs.has(li)) w.segs.set(li, walkSegments(planRef.current, li));
    return w.segs.get(li)!;
  }
  function floorZ(li: number) { const p = planRef.current; return PLINTH + li * (p.floor_height_ft || 10) + 0.04; }
  function baseHeight(li: number, x: number, y: number) {
    const p = planRef.current;
    if (li > 0) return floorZ(li);
    const lx = x - p.building.x, ly = y - p.building.y;
    if (roomAt(p.levels[0].rooms, lx, ly)) return floorZ(0);
    const e = extent(p.levels[0].rooms);
    const dIn = Math.max(e.x0 - lx, lx - e.x1, e.y0 - ly, ly - e.y1, 0);
    return dIn < 0.5 ? PLINTH : dIn < 3.4 ? PLINTH * (1 - (dIn - 0.5) / 2.9) : 0;  // the entrance steps
  }
  function startWalk() {
    const c = ctx.current; if (!c) return;
    const p = planRef.current;
    const lv = p.levels[0];
    const door = lv.openings.find((o) => o.type === "main_door") || lv.openings.find((o) => o.type === "door");
    const e = extent(lv.rooms);
    const w = walk.current;
    w.li = 0; w.pitch = -0.04; w.yaw = 0;
    // start just inside the gate, in line with the main door, looking at the house
    w.x = p.building.x + (door && Math.abs(door.y1 - door.y2) < 1e-6 ? (door.x1 + door.x2) / 2 : (e.x0 + e.x1) / 2);
    w.y = Math.min(3, Math.max(1.5, p.building.y - 1.5));
    const park = lv.rooms.find((r) => r.type === "parking" && r.w >= 9 && r.d >= 14);
    if (park) {  // do not start inside the car: walk beside it
      const cx = p.building.x + park.x + park.w / 2;
      if (Math.abs(w.x - cx) < 4.2) w.x = cx + (w.x >= cx ? 4.2 : -4.2);
    }
    w.h = baseHeight(0, w.x, w.y);
    c.camera.userData.walk = true; c.controls.enabled = false;
    c.camera.fov = 70; c.camera.near = 0.3; c.camera.far = 900; c.camera.updateProjectionMatrix();
    placeCam();
    roomLightsFor(0);
  }
  /** dt = 0 → jump straight there (start, stairs, go to room); otherwise glide smoothly (no shaking) */
  function placeCam(dt = 0) {
    const c = ctx.current; if (!c) return;
    const w = walk.current, sm = smooth.current;
    const k = dt ? 1 - Math.exp(-dt * 12) : 1, ka = dt ? 1 - Math.exp(-dt * 16) : 1;
    sm.x += (w.x - sm.x) * k; sm.y += (w.y - sm.y) * k; sm.h += (w.h + EYE - sm.h) * k;
    let dyaw = w.yaw - sm.yaw; while (dyaw > Math.PI) dyaw -= 2 * Math.PI; while (dyaw < -Math.PI) dyaw += 2 * Math.PI;
    sm.yaw += dyaw * ka; sm.pitch += (w.pitch - sm.pitch) * ka;
    c.camera.position.set(sm.x, sm.h, -sm.y);
    const dir = new THREE.Vector3(Math.sin(sm.yaw) * Math.cos(sm.pitch), Math.sin(sm.pitch), -Math.cos(sm.yaw) * Math.cos(sm.pitch));
    c.camera.lookAt(c.camera.position.clone().add(dir));
  }
  function walkStep(dt: number) {
    const w = walk.current, k = keys.current;
    const f = (k.w || k.arrowup ? 1 : 0) - (k.s || k.arrowdown ? 1 : 0);
    const st = (k.d ? 1 : 0) - (k.a ? 1 : 0);
    const turn = (k.arrowright || k.l ? 1 : 0) - (k.arrowleft || k.j ? 1 : 0);
    w.yaw += turn * 1.7 * dt;
    if (f || st) {
      const sp = (k.shift ? 13 : 6.5) * dt;
      const dx = (f * Math.sin(w.yaw) + st * Math.cos(w.yaw)) * sp, dy = (f * Math.cos(w.yaw) - st * Math.sin(w.yaw)) * sp;
      [w.x, w.y] = collide(segsFor(w.li), w.x, w.y, dx, dy, 0.85);
    }
    w.h = baseHeight(w.li, w.x, w.y);  // the camera glides to it (placeCam smoothing)
    placeCam(dt);
    // where am I?
    const p = planRef.current;
    const r = roomAt(p.levels[w.li].rooms, w.x - p.building.x, w.y - p.building.y);
    const label = `${w.li}|${r ? r.name : ""}|${r?.type === "stair" ? 1 : 0}`;
    if (label !== w.label) { w.label = label; setWalkInfo({ level: w.li, room: r ? r.name : w.li === 0 ? "Outside" : "", stair: r?.type === "stair" }); }
  }
  function stairGo(dir: 1 | -1) {
    const p = planRef.current, w = walk.current;
    const to = w.li + dir;
    if (to < 0 || to >= p.levels.length) return;
    const here = roomAt(p.levels[w.li].rooms, w.x - p.building.x, w.y - p.building.y);
    if (!here || here.type !== "stair") { toast("Walk to the staircase first, then go up / down"); return; }
    const st = p.levels[to].rooms.find((r) => r.type === "stair") || p.levels[to].rooms[0];
    w.li = to;
    w.x = p.building.x + st.x + st.w / 2; w.y = p.building.y + st.y + Math.min(st.d - 1.5, 2.5);
    w.h = floorZ(to); w.label = "";
    faceCentre(to);
    placeCam();
    roomLightsFor(to);
  }
  function goRoom(v: string) {
    const [li, id] = v.split(":"); const p = planRef.current;
    const r = p.levels[Number(li)]?.rooms.find((q) => q.id === id); if (!r) return;
    const w = walk.current;
    w.li = Number(li); w.x = p.building.x + r.x + r.w / 2; w.y = p.building.y + r.y + r.d / 2; w.h = floorZ(w.li); w.label = "";
    faceCentre(w.li);
    placeCam();
    roomLightsFor(w.li);
  }
  function faceCentre(li: number) {  // look towards the middle of the floor (you see the door, not a blank wall)
    const p = planRef.current, w = walk.current;
    const e = extent(p.levels[li].rooms);
    const cx = p.building.x + (e.x0 + e.x1) / 2, cy = p.building.y + (e.y0 + e.y1) / 2;
    if (Math.hypot(cx - w.x, cy - w.y) > 1.5) w.yaw = Math.atan2(cx - w.x, cy - w.y);
    w.pitch = -0.05;
  }
  function clearRoomLights() { /* 1.15: no room lights (kept as a no-op) */ }
  function roomLightsFor(_li: number) { /* 1.15: rooms are lit by the soft sky light */ }
  const hold = (k: string) => ({
    onPointerDown: (e: RPointerEvent) => { e.preventDefault(); keys.current[k] = true; },
    onPointerUp: () => { keys.current[k] = false; }, onPointerLeave: () => { keys.current[k] = false; }, onPointerCancel: () => { keys.current[k] = false; },
  });

  // ------------------------------------------------------------------ downloads
  const fileBase = () => `Nexora_3D_${style}`;
  const save = (url: string, name: string) => { const a = document.createElement("a"); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove(); };
  const png = () => {
    const c = ctx.current; if (!c) return;
    c.renderer.render(c.scene, c.camera);
    save(c.renderer.domElement.toDataURL("image/png"), `${fileBase()}_view.png`);
  };
  /** render one preset view at a fixed size; returns a PNG data URL */
  function shot(v: View, W = 1800, Hh = 1100): string {
    const c = ctx.current!;
    const r = c.renderer, size = r.getSize(new THREE.Vector2()), pr = r.getPixelRatio();
    const { pos, target, R, H } = camFor(v);
    let cam: THREE.Camera;
    if (flat && v !== "iso" && v !== "top") {  // true elevation: no perspective
      const half = Math.max(R * 0.42, H * 0.9);
      const o = new THREE.OrthographicCamera(-half * (W / Hh), half * (W / Hh), half, -half, 0.5, 3000);
      o.position.copy(pos).setY(H * 0.45); o.lookAt(target.clone().setY(H * 0.45)); cam = o;
    } else {
      const p = new THREE.PerspectiveCamera(v === "iso" ? 42 : 38, W / Hh, 0.5, 3000);
      p.position.copy(pos); p.lookAt(target); cam = p;
    }
    r.setPixelRatio(1); r.setSize(W, Hh, false);
    r.render(c.scene, cam);
    const url = r.domElement.toDataURL("image/png");
    r.setPixelRatio(pr); r.setSize(size.x, size.y, false);
    return url;
  }
  const views = async (sheet: boolean) => {
    const c = ctx.current; if (!c || mode === "walk") return toast("Leave the walkthrough first", "err");
    setBusy(true);
    try {
      const list: [View, string][] = [["front", "Front Elevation"], ["left", "Left Side Elevation"], ["right", "Right Side Elevation"], ["rear", "Rear Elevation"], ["iso", "3D View"]];
      const shots = list.map(([v, l]) => [shot(v), l] as [string, string]);
      if (!sheet) {
        for (const [i, [u, l]] of shots.entries()) { save(u, `${fileBase()}_${l.replace(/\s+/g, "_")}.png`); await new Promise((r) => setTimeout(r, 350 + i * 50)); }
        toast("5 images downloaded (front, left, right, rear, 3D)");
        return;
      }
      const W = 1800, Hh = 1100, pad = 40, head = 110;
      const cv = document.createElement("canvas"); cv.width = W * 2 + pad * 3; cv.height = head + (Hh + 70) * 3 + pad;
      const g = cv.getContext("2d")!;
      g.fillStyle = "#ffffff"; g.fillRect(0, 0, cv.width, cv.height);
      g.fillStyle = "#0f2350"; g.font = "bold 54px Arial"; g.fillText("3D Elevation Views", pad, 72);
      g.font = "28px Arial"; g.fillStyle = "#475569";
      g.fillText(`${STYLES.find((s) => s[0] === style)?.[1]} style · ${light === "day" ? "Day" : light === "dusk" ? "Evening" : "Night"} · concept visual from the plan`, pad + 560, 70);
      const imgs = await Promise.all(shots.map(([u]) => new Promise<HTMLImageElement>((res) => { const im = new Image(); im.onload = () => res(im); im.src = u; })));
      imgs.forEach((im, i) => {
        const col = i % 2, row = Math.floor(i / 2);
        const x = i === 4 ? pad + (W + pad) / 2 : pad + col * (W + pad), y = head + row * (Hh + 70);
        g.drawImage(im, x, y, W, Hh);
        g.strokeStyle = "#cbd5e1"; g.lineWidth = 2; g.strokeRect(x, y, W, Hh);
        g.fillStyle = "#0f2350"; g.font = "bold 32px Arial"; g.fillText(shots[i][1], x, y + Hh + 44);
      });
      save(cv.toDataURL("image/png"), `${fileBase()}_All_Views.png`);
    } finally { setBusy(false); }
  };
  const glb = () => {
    const c = ctx.current; if (!c?.model) return;
    new GLTFExporter().parse(c.model, (res: any) => {
      save(URL.createObjectURL(new Blob([res as ArrayBuffer], { type: "model/gltf-binary" })), `${fileBase()}_model.glb`);
    }, (err: any) => toast(String(err), "err"), { binary: true });
  };
  const video = async () => {
    const c = ctx.current; if (!c) return;
    const canvas = c.renderer.domElement as HTMLCanvasElement & { captureStream?: (fps: number) => MediaStream };
    if (!canvas.captureStream || typeof MediaRecorder === "undefined") return toast("This browser cannot record video – use Chrome or Edge", "err");
    const rec = new MediaRecorder(canvas.captureStream(30), { mimeType: MediaRecorder.isTypeSupported("video/webm;codecs=vp9") ? "video/webm;codecs=vp9" : "video/webm" });
    const chunks: Blob[] = [];
    rec.ondataavailable = (e) => chunks.push(e.data);
    rec.onstop = () => { save(URL.createObjectURL(new Blob(chunks, { type: "video/webm" })), `${fileBase()}_walkaround.webm`); setRecording(false); setRotate(false); };
    view("iso"); setRotate(true); setRecording(true); rec.start();
    toast("Recording a 20 s turntable video…");
    setTimeout(() => rec.stop(), 20000);
  };

  const pickStyle = (s: Style) => onFinishes?.({ ...fin, ...STYLE_FINISH[s], style: s });
  const modes: [Mode, string, any][] = [["exterior", "Exterior", Layers3], ["interior", "Interior", Layers3], ["walk", "Walkthrough", Footprints],
    ["exploded", "Exploded", Layers3], ["structure", "Structure (RCC)", Layers3]];
  const lvName = plan.levels[walkInfo.level]?.name || "";
  return (
    <div className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        {STYLES.map(([s, l, d]) => (
          <button key={s} onClick={() => pickStyle(s)} disabled={!onFinishes}
            className={`rounded-lg border p-2.5 text-left transition ${style === s ? "border-brand-500 bg-brand-50 ring-2 ring-brand-500" : "border-line bg-white hover:bg-slate-50"}`}>
            <div className="text-sm font-bold text-navy-ink">{l}</div><div className="text-[11px] leading-snug text-slate-500">{d}</div>
          </button>
        ))}
      </div>
      <div className="flex flex-wrap items-center gap-1.5">
        {modes.map(([m, l, I]) => (
          <button key={m} onClick={() => setMode(m)} className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-sm font-semibold ${mode === m ? "bg-brand-600 text-white" : "bg-brand-50 text-navy-ink"}`}><I size={15} />{l}</button>
        ))}
        <span className="flex-1" />
        <div className="inline-flex overflow-hidden rounded-lg border border-line text-sm">
          {([["day", "Day", Sun], ["dusk", "Evening", Sunset], ["night", "Night", Moon]] as [LightMode, string, any][]).map(([k, l, I]) => (
            <button key={k} onClick={() => setLight(k)} className={`inline-flex items-center gap-1 px-2.5 py-1.5 font-semibold ${light === k ? "bg-navy-ink text-white" : "bg-white text-navy-ink"}`}><I size={14} />{l}</button>
          ))}
        </div>
      </div>
      {mode === "interior" && (
        <div className="flex flex-wrap items-center gap-1.5 rounded-lg bg-brand-50 p-2 text-sm">
          <span className="mr-1 text-xs font-semibold text-navy-ink">Interior – floor:</span>
          {plan.levels.map((l, i) => (
            <button key={i} onClick={() => setInFloor(i)} className={`rounded-md px-3 py-1 text-xs font-semibold ${inFloor === i ? "bg-brand-600 text-white" : "bg-white text-navy-ink"}`}>{l.name}</button>
          ))}
          <span className="text-[11px] text-slate-500">Only this floor is shown, walls cut at 4½ ft so you can see the rooms and furniture.</span>
        </div>
      )}
      <div className="relative overflow-hidden rounded-lg border border-line bg-slate-900">
        <div ref={host} className="h-[560px] w-full touch-none select-none" />
        {mode === "walk" ? (
          <>
            <div className="absolute left-3 top-3 rounded-lg bg-black/60 px-3 py-1.5 text-sm text-white">
              <b>{walkInfo.room || "—"}</b>{lvName && <span className="text-white/70"> · {lvName}</span>}
            </div>
            <div className="absolute right-3 top-3 flex flex-col items-end gap-2">
              <button className="inline-flex items-center gap-1 rounded-lg bg-white/90 px-2.5 py-1.5 text-xs font-semibold text-navy-ink" onClick={() => setMode("exterior")}><LogOut size={14} />Exit (Esc)</button>
              <select className="rounded-lg bg-white/90 px-2 py-1.5 text-xs" value="" onChange={(e) => { if (e.target.value) goRoom(e.target.value); }}>
                <option value="">Go to room…</option>
                {plan.levels.map((l, li) => <optgroup key={li} label={l.name}>{l.rooms.map((r) => <option key={r.id} value={`${li}:${r.id}`}>{r.name}</option>)}</optgroup>)}
              </select>
            </div>
            {walkInfo.stair && (
              <div className="absolute left-1/2 top-3 flex -translate-x-1/2 gap-2">
                {walkInfo.level < plan.levels.length - 1 && <button className="inline-flex items-center gap-1 rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-bold text-white" onClick={() => stairGo(1)}><ChevronsUp size={15} />Up to {plan.levels[walkInfo.level + 1].name} (E)</button>}
                {walkInfo.level > 0 && <button className="inline-flex items-center gap-1 rounded-lg bg-brand-600 px-3 py-1.5 text-xs font-bold text-white" onClick={() => stairGo(-1)}><ChevronsDown size={15} />Down to {plan.levels[walkInfo.level - 1].name} (Q)</button>}
              </div>
            )}
            <div className="absolute bottom-3 right-3 grid grid-cols-3 gap-1 opacity-90">
              <span /><button className="rounded-lg bg-white/85 p-2.5" {...hold("w")}><ArrowUp size={18} /></button><span />
              <button className="rounded-lg bg-white/85 p-2.5" {...hold("arrowleft")}><ArrowLeft size={18} /></button>
              <button className="rounded-lg bg-white/85 p-2.5" {...hold("s")}><ArrowDown size={18} /></button>
              <button className="rounded-lg bg-white/85 p-2.5" {...hold("arrowright")}><ArrowRight size={18} /></button>
            </div>
            <div className="absolute bottom-3 left-3 max-w-[60%] rounded bg-black/55 px-2 py-1 text-[11px] text-white">
              W / S walk · A / D step sideways · ← → turn · drag to look · Shift = faster · walls stop you, doors are open · stairs: E up / Q down
            </div>
          </>
        ) : (
          <div className="absolute bottom-2 left-3 rounded bg-white/85 px-2 py-1 text-xs text-slate-600">Drag to rotate · scroll / pinch to zoom · right-drag to pan</div>
        )}
        {recording && <div className="absolute right-3 top-3 rounded bg-red-600 px-2 py-1 text-xs font-bold text-white">● REC</div>}
      </div>
      <div className="flex flex-wrap items-center gap-1.5 text-sm">
        <span className="mr-1 text-xs font-semibold text-slate-500"><Camera size={13} className="mr-1 inline" />Camera</span>
        {(["iso", "front", "left", "right", "rear", "top"] as const).map((v) => (
          <button key={v} className="btn-outline btn-sm" disabled={mode === "walk"} onClick={() => view(v)}>{{ iso: "3D", front: "Front", left: "Left side", right: "Right side", rear: "Rear", top: "Top" }[v]}</button>
        ))}
        <button className="btn-ghost btn-sm" disabled={mode === "walk"} onClick={() => view("iso")}><RotateCcw size={14} />Reset</button>
      </div>
      <div className="flex flex-wrap items-center gap-1.5 rounded-lg border border-line bg-slate-50 p-2 text-sm">
        <span className="mr-1 text-xs font-semibold text-slate-500"><Download size={13} className="mr-1 inline" />Download</span>
        <button className="btn-outline btn-sm" onClick={png}><Download size={14} />This view (PNG)</button>
        <button className="btn-outline btn-sm" disabled={busy} onClick={() => views(false)}><Images size={14} />Front · Sides · Rear · 3D (5 PNG)</button>
        <button className="btn-outline btn-sm" disabled={busy} onClick={() => views(true)}><Images size={14} />All views on one sheet</button>
        <label className="ml-1 flex items-center gap-1.5 text-xs"><input type="checkbox" className="h-4 w-4 accent-brand-600" checked={flat} onChange={(e) => setFlat(e.target.checked)} />Flat elevations (no perspective)</label>
        <span className="flex-1" />
        <button className="btn-outline btn-sm" onClick={glb}><Download size={14} />3D model (GLB)</button>
        <button className="btn-outline btn-sm" disabled={recording || mode === "walk"} onClick={video}><Film size={14} />Video</button>
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
            {([["Furniture & car", furniture, setFurniture], ["Surroundings (garden, road, gate)", surround, setSurround], ["Roof / terrace", roof, setRoof],
              ["Section cut (half)", cut, setCut], ["Wireframe", wire, setWire], ["Auto rotate", rotate, setRotate], ["Edge lines (line drawing look)", edges, setEdges]] as [string, boolean, (v: boolean) => void][]).map(([l, v, f]) => (
              <label key={l} className="flex items-center gap-2"><input type="checkbox" className="h-4 w-4 accent-brand-600" checked={v} onChange={(e) => f(e.target.checked)} />{l}</label>
            ))}
          </div>
        </div>
        <div className="rounded-lg border border-line p-3 text-sm">
          <div className="mb-2 text-xs font-semibold text-navy-ink">Quick colours (the library below gives every option)</div>
          <div className="space-y-1.5">
            {(["ext", "int"] as const).map((k) => (
              <div key={k} className="flex flex-wrap items-center gap-1.5">
                <span className="w-28 shrink-0 text-xs text-slate-500">{FIN_LABEL[k]}</span>
                {SWATCHES[k].map(([col, name]) => (
                  <button key={col} title={name} onClick={() => onFinishes?.({ ...fin, [k]: col })}
                    className={`h-6 w-6 rounded-md border ${fin[k] === col ? "ring-2 ring-brand-500 ring-offset-1" : "border-slate-300"}`} style={{ background: col }} />
                ))}
              </div>
            ))}
          </div>
          <p className="mt-2 text-[11px] text-slate-500">Style and colours are saved with the design (press Save). Doors and windows are exactly where the plan and the 2D elevation show them.</p>
          <details className="mt-2 text-[11px] text-slate-600">
            <summary className="cursor-pointer font-semibold text-navy-ink">Need a photo-quality render? (free, Blender)</summary>
            <ol className="ml-4 mt-1 list-decimal space-y-0.5">
              <li>Download <b>3D model (GLB)</b> here.</li>
              <li>Install Blender (free, blender.org) → File → Import → glTF 2.0 → pick the .glb.</li>
              <li>Render Properties → Render Engine: <b>Cycles</b>. World → Color → use a sky texture (Nishita) for daylight or dusk.</li>
              <li>Add a Camera in front of the house (Numpad 0 to look through it), then Render → Render Image (F12) → Image → Save As.</li>
            </ol>
            <p className="mt-1">The browser view is a clear, accurate concept visual of your plan; Blender gives real-photo lighting.</p>
          </details>
        </div>
      </div>
      <MaterialPanel plan={plan} picks={{ mat: fin.mat, rooms: fin.rooms }} items={items} swatch={swatch} isOwner={user?.role === "owner"}
        code={`Nexora_3D_${style}`} onLibraryChanged={loadLibrary}
        onPick={(slot, ref) => { const mat = { ...(fin.mat || {}) }; if (ref) mat[slot] = ref; else delete mat[slot]; onFinishes?.({ ...fin, mat }); }}
        onRoomPick={(rid, kind, ref) => {
          const rooms = { ...(fin.rooms || {}) }; const one = { ...(rooms[rid] || {}) };
          if (ref) one[kind] = ref; else delete one[kind];
          if (Object.keys(one).length) rooms[rid] = one; else delete rooms[rid];
          onFinishes?.({ ...fin, rooms });
        }}
        shot={() => { const c = ctx.current; if (!c || mode === "walk") return null; c.renderer.render(c.scene, c.camera); return c.renderer.domElement.toDataURL("image/png"); }} />
    </div>
  );
}
