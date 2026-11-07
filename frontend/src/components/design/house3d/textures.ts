/** 1.13 – procedural textures for the 3D house (made in code, no image files, same every time). */
import * as THREE from "three";

function rng(seed: number) {
  let s = seed >>> 0;
  return () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; };
}
const cache = new Map<string, THREE.Texture>();

function make(key: string, size: number, draw: (g: CanvasRenderingContext2D, r: () => number) => void, srgb = true) {
  const hit = cache.get(key);
  if (hit) return hit;
  const c = document.createElement("canvas"); c.width = c.height = size;
  const g = c.getContext("2d")!;
  draw(g, rng(key.split("").reduce((a, ch) => a * 31 + ch.charCodeAt(0), 7)));
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping;
  t.anisotropy = 16;  // 1.17: sharp at grazing angles (three.js uses the most the graphics card allows)
  if (srgb) t.colorSpace = THREE.SRGBColorSpace;
  cache.set(key, t);
  return t;
}

function speckle(g: CanvasRenderingContext2D, r: () => number, size: number, amount: number) {
  const img = g.getImageData(0, 0, size, size);
  for (let i = 0; i < img.data.length; i += 4) {
    const n = (r() - 0.5) * amount;
    img.data[i] += n; img.data[i + 1] += n; img.data[i + 2] += n;
  }
  g.putImageData(img, 0, 0);
}

/** white plaster (tinted by the material colour) – 1 texture = 4 ft */
export const plaster = () => make("plaster2", 512, (g, r) => {  // 1.17: 512 px – stays sharp when you walk close to a wall
  g.fillStyle = "#ffffff"; g.fillRect(0, 0, 512, 512); speckle(g, r, 512, 10);
  for (let i = 0; i < 900; i++) { g.fillStyle = `rgba(0,0,0,${0.015 + r() * 0.025})`; g.fillRect(r() * 512, r() * 512, 1 + r() * 2, 1 + r() * 2); }
});

/** 1.17 – soft contact shadow (ambient occlusion) strip: dark at the wall, fading out (used on floors / ceilings) */
export const aoStrip = () => make("aoStrip", 64, (g) => {
  const grd = g.createLinearGradient(0, 0, 0, 64);
  grd.addColorStop(0, "rgba(0,0,0,0.55)"); grd.addColorStop(0.35, "rgba(0,0,0,0.18)"); grd.addColorStop(1, "rgba(0,0,0,0)");
  g.clearRect(0, 0, 64, 64); g.fillStyle = grd; g.fillRect(0, 0, 64, 64);
}, false);

/** stacked natural stone cladding – 1 texture = 4 ft */
export const stone = () => make("stone", 512, (g, r) => {
  g.fillStyle = "#4a4740"; g.fillRect(0, 0, 512, 512);
  const tones = ["#8f8678", "#a39a8a", "#7d7466", "#b3a993", "#6f675b", "#9a8f7b", "#c2b8a3"];
  let y = 0;
  while (y < 512) {
    const h = 18 + r() * 30;
    let x = -r() * 60;
    while (x < 512) {
      const w = 40 + r() * 110;
      g.fillStyle = tones[Math.floor(r() * tones.length)];
      g.fillRect(x + 2, y + 2, w - 4, h - 4);
      g.fillStyle = "rgba(255,255,255,0.08)"; g.fillRect(x + 2, y + 2, w - 4, 3);
      x += w;
    }
    y += h;
  }
  speckle(g, r, 512, 22);
});

/** horizontal wood planks (cladding, soffit, doors) – 1 texture = 4 ft */
export const wood = (tone = "#9a6a3f") => make("wood" + tone, 512, (g, r) => {
  const base = new THREE.Color(tone);
  const n = 10;
  for (let i = 0; i < n; i++) {
    const c = base.clone().offsetHSL(0, 0, (r() - 0.5) * 0.08);
    g.fillStyle = `#${c.getHexString()}`; g.fillRect(0, (i * 512) / n, 512, 512 / n);
    g.strokeStyle = "rgba(0,0,0,0.12)";
    for (let k = 0; k < 14; k++) {  // grain
      g.beginPath();
      const yy = (i * 512) / n + r() * (512 / n);
      g.moveTo(0, yy);
      for (let x = 0; x <= 512; x += 32) g.lineTo(x, yy + Math.sin(x / 40 + k) * 1.5);
      g.stroke();
    }
    g.fillStyle = "rgba(0,0,0,0.45)"; g.fillRect(0, ((i + 1) * 512) / n - 3, 512, 3);  // joint
  }
});

/** large-format grey wall tiles (contemporary cladding) – 1 texture = 4 ft */
export const tiles = () => make("tiles", 256, (g, r) => {
  g.fillStyle = "#3d4046"; g.fillRect(0, 0, 256, 256);
  for (let y = 0; y < 2; y++) for (let x = 0; x < 2; x++) {
    const v = 120 + Math.floor(r() * 18);
    g.fillStyle = `rgb(${v},${v + 3},${v + 8})`; g.fillRect(x * 128 + 2, y * 128 + 2, 124, 124);
  }
  speckle(g, r, 256, 10);
});

/** terracotta roof tiles (traditional) – 1 texture = 4 ft */
/** 1.17 – roofing sheet ribs (corrugation shading, tinted by the sheet colour) – repeats every 0.6 ft */
export const sheetRibs = () => make("sheetRibs", 128, (g) => {
  const grd = g.createLinearGradient(0, 0, 128, 0);
  grd.addColorStop(0, "#b8b8b8"); grd.addColorStop(0.2, "#ffffff"); grd.addColorStop(0.45, "#e6e6e6");
  grd.addColorStop(0.6, "#9a9a9a"); grd.addColorStop(0.8, "#d8d8d8"); grd.addColorStop(1, "#b8b8b8");
  g.fillStyle = grd; g.fillRect(0, 0, 128, 128);
});

export const roofTiles = () => make("roofTiles", 256, (g) => {
  for (let y = 0; y < 8; y++) {
    for (let x = 0; x < 8; x++) {
      const off = y % 2 ? 16 : 0;
      const grd = g.createLinearGradient(0, y * 32, 0, y * 32 + 32);
      grd.addColorStop(0, "#c2532f"); grd.addColorStop(0.7, "#a5402a"); grd.addColorStop(1, "#6e2a1c");
      g.fillStyle = grd; g.fillRect(x * 32 + off - 16, y * 32, 31, 32);
    }
  }
});

export const pavers = () => make("pavers", 256, (g, r) => {
  g.fillStyle = "#6b6760"; g.fillRect(0, 0, 256, 256);
  for (let y = 0; y < 8; y++) for (let x = 0; x < 4; x++) {
    const v = 150 + Math.floor(r() * 30);
    g.fillStyle = `rgb(${v},${v - 6},${v - 14})`;
    g.fillRect(x * 64 + (y % 2) * 32 + 2 - 32, y * 32 + 2, 60, 28);
    g.fillRect(x * 64 + (y % 2) * 32 + 2 + 224, y * 32 + 2, 60, 28);
  }
  speckle(g, r, 256, 14);
});

export const grass = () => make("grass", 256, (g, r) => {
  g.fillStyle = "#5d8f3e"; g.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 5000; i++) {
    const v = r();
    g.fillStyle = v > 0.6 ? "#7aa956" : v > 0.3 ? "#4f7d33" : "#689a45";
    g.fillRect(r() * 256, r() * 256, 1.5, 3);
  }
});

export const asphalt = () => make("asphalt", 256, (g, r) => { g.fillStyle = "#3b3f45"; g.fillRect(0, 0, 256, 256); speckle(g, r, 256, 30); });

export function sky(kind: "day" | "dusk" | "night") {
  return make("sky" + kind, 256, (g) => {
    const gr = g.createLinearGradient(0, 0, 0, 256);
    if (kind === "night") { gr.addColorStop(0, "#020617"); gr.addColorStop(0.7, "#0f1d36"); gr.addColorStop(1, "#1e2c45"); }
    else if (kind === "dusk") { gr.addColorStop(0, "#14244a"); gr.addColorStop(0.45, "#35538a"); gr.addColorStop(0.8, "#d98c5f"); gr.addColorStop(1, "#f3c08a"); }
    else { gr.addColorStop(0, "#4f9fe0"); gr.addColorStop(0.6, "#b9dcf5"); gr.addColorStop(1, "#eef6fb"); }
    g.fillStyle = gr; g.fillRect(0, 0, 256, 256);
  });
}

/** BoxGeometry UVs in world size (1 texture repeat = `tile` ft) so stone / wood are never stretched. */
export function worldUV(geo: THREE.BoxGeometry, w: number, h: number, d: number, tile = 4) {
  const uv = geo.getAttribute("uv") as THREE.BufferAttribute;
  const su = [d, d, w, w, w, w], sv = [h, h, d, d, h, h];
  for (let i = 0; i < uv.count; i++) {
    const f = Math.floor(i / 4);
    uv.setXY(i, (uv.getX(i) * su[f]) / tile, (uv.getY(i) * sv[f]) / tile);
  }
  uv.needsUpdate = true;
}

// ---------------------------------------------------------------- 1.15 material library textures
const tint = (hex: string, d: number) => `#${new THREE.Color(hex).offsetHSL(0, 0, d).getHexString()}`;

/** square floor / wall tiles: n x n per texture, joints in a darker shade */
export const floorTiles = (color: string, n = 2, joint = "#00000033") => make(`ft${color}${n}${joint}`, 256, (g, r) => {
  g.fillStyle = tint(color, -0.12); g.fillRect(0, 0, 256, 256);
  const s = 256 / n;
  for (let y = 0; y < n; y++) for (let x = 0; x < n; x++) {
    g.fillStyle = tint(color, (r() - 0.5) * 0.04); g.fillRect(x * s + 1.5, y * s + 1.5, s - 3, s - 3);
  }
  g.fillStyle = joint; for (let i = 0; i <= n; i++) { g.fillRect(i * s - 1, 0, 2, 256); g.fillRect(0, i * s - 1, 256, 2); }
  speckle(g, r, 256, 6);
});

export const marble = (color = "#f2f0eb") => make("marble" + color, 512, (g, r) => {
  g.fillStyle = color; g.fillRect(0, 0, 512, 512);
  for (let k = 0; k < 14; k++) {  // veins
    g.strokeStyle = `rgba(90,90,100,${0.08 + r() * 0.18})`; g.lineWidth = 0.6 + r() * 2.2;
    g.beginPath(); let x = r() * 512, y = 0; g.moveTo(x, y);
    while (y < 512) { x += (r() - 0.5) * 40; y += 12 + r() * 20; g.lineTo(x, y); }
    g.stroke();
  }
  g.fillStyle = "rgba(0,0,0,0.25)"; g.fillRect(0, 255, 512, 2); g.fillRect(255, 0, 2, 512);  // 2 x 2 slabs
  speckle(g, r, 512, 5);
});

export const granite = (color = "#2f2f2f") => make("granite" + color, 256, (g, r) => {
  g.fillStyle = color; g.fillRect(0, 0, 256, 256);
  const c = new THREE.Color(color);
  for (let i = 0; i < 9000; i++) {
    const v = r();
    g.fillStyle = v > 0.92 ? "#e8e4dc" : v > 0.7 ? `#${c.clone().offsetHSL(0, 0, 0.18).getHexString()}` : `#${c.clone().offsetHSL(0, 0, -0.08).getHexString()}`;
    g.fillRect(r() * 256, r() * 256, 1 + r() * 2, 1 + r() * 2);
  }
});

export const brick = (color = "#a8553a") => make("brick" + color, 256, (g, r) => {
  g.fillStyle = "#cfc6b8"; g.fillRect(0, 0, 256, 256);
  for (let y = 0; y < 8; y++) for (let x = -1; x < 5; x++) {
    g.fillStyle = tint(color, (r() - 0.5) * 0.12);
    g.fillRect(x * 64 + (y % 2) * 32 + 2, y * 32 + 2, 60, 28);
  }
  speckle(g, r, 256, 16);
});

export const mosaic = (color = "#5b8fc9") => make("mosaic" + color, 256, (g, r) => {
  g.fillStyle = "#e9eef2"; g.fillRect(0, 0, 256, 256);
  for (let y = 0; y < 16; y++) for (let x = 0; x < 16; x++) { g.fillStyle = tint(color, (r() - 0.5) * 0.2); g.fillRect(x * 16 + 1, y * 16 + 1, 14, 14); }
});

/** a small picture of any texture / colour for the library cards (data URL) */
export function swatchUrl(t: THREE.Texture | null, color: string): string {
  const c = document.createElement("canvas"); c.width = c.height = 64;
  const g = c.getContext("2d")!;
  if (t && (t.image as any)?.getContext) g.drawImage(t.image as HTMLCanvasElement, 0, 0, 64, 64);
  else { g.fillStyle = color; g.fillRect(0, 0, 64, 64); }
  return c.toDataURL();
}

/** 1.20 realistic look: the same picture used as a bump map – stone joints, wood grain, paver joints get real relief */
const bumps = new Map<THREE.Texture, THREE.Texture>();
export function bumpOf(t: THREE.Texture): THREE.Texture {
  const hit = bumps.get(t);
  if (hit) return hit;
  const b = new THREE.CanvasTexture(t.image as HTMLCanvasElement);
  b.wrapS = b.wrapT = THREE.RepeatWrapping; b.anisotropy = 8; b.colorSpace = THREE.NoColorSpace;
  bumps.set(t, b);
  return b;
}

/** 1.20 CNC jaali screen (white pattern, see-through gaps) – 1 texture = 2 ft */
export const jaali = () => make("jaali", 256, (g) => {
  g.clearRect(0, 0, 256, 256);
  g.fillStyle = "#ffffff"; g.fillRect(0, 0, 256, 256);
  g.globalCompositeOperation = "destination-out";
  const cell = 64;
  for (let cy = 0; cy < 256; cy += cell) for (let cx = 0; cx < 256; cx += cell) {
    const x = cx + cell / 2, y = cy + cell / 2;
    for (let k = 0; k < 4; k++) {  // four petals
      const a = (k * Math.PI) / 2;
      g.beginPath(); g.ellipse(x + Math.cos(a) * 14, y + Math.sin(a) * 14, 11, 5, a, 0, Math.PI * 2); g.fill();
    }
    g.beginPath(); g.arc(x, y, 4, 0, Math.PI * 2); g.fill();
    for (const [dx, dy] of [[0, 0], [cell, 0], [0, cell], [cell, cell]]) {  // corner stars
      g.beginPath(); g.arc(cx + dx, cy + dy, 7, 0, Math.PI * 2); g.fill();
    }
  }
  g.globalCompositeOperation = "source-over";
}, false);
