// 1.20 Realistic shading for still pictures (HD photo, AI-render base): ambient occlusion (GTAO) – corners, joints,
// window reveals and the ground under the house get soft contact shadows. Only used for one-off pictures, never
// for the live view (keeps rotating smooth). If anything fails, the plain render is used – never a broken picture.
import * as THREE from "three";

export async function renderRealistic(r: THREE.WebGLRenderer, scene: THREE.Scene, cam: THREE.Camera, W: number, H: number): Promise<boolean> {
  try {
    const [{ EffectComposer }, { RenderPass }, { GTAOPass }, { OutputPass }] = await Promise.all([
      import("three/examples/jsm/postprocessing/EffectComposer.js"),
      import("three/examples/jsm/postprocessing/RenderPass.js"),
      import("three/examples/jsm/postprocessing/GTAOPass.js"),
      import("three/examples/jsm/postprocessing/OutputPass.js"),
    ]);
    const comp = new EffectComposer(r);
    comp.setPixelRatio(1);
    comp.setSize(W, H);
    comp.addPass(new RenderPass(scene, cam));
    const ao = new GTAOPass(scene, cam, W, H);
    ao.blendIntensity = 0.9;
    ao.updateGtaoMaterial({ radius: 2.5, distanceExponent: 1.5, thickness: 2.5, scale: 1.2, samples: 16 });
    comp.addPass(ao);
    comp.addPass(new OutputPass());
    comp.render();
    const ok = notBlank(r.domElement);
    comp.dispose();
    if (!ok) { r.render(scene, cam); return false; }
    return true;
  } catch (e) {
    console.warn("Realistic shading not available – plain render used", e);
    r.render(scene, cam);
    return false;
  }
}

/** a black / empty picture means the effect failed on this graphics card */
function notBlank(c: HTMLCanvasElement): boolean {
  try {
    const t = document.createElement("canvas"); t.width = t.height = 16;
    const g = t.getContext("2d")!; g.drawImage(c, 0, 0, 16, 16);
    const d = g.getImageData(0, 0, 16, 16).data;
    let s = 0;
    for (let i = 0; i < d.length; i += 4) s += d[i] + d[i + 1] + d[i + 2];
    return s / (d.length / 4) > 30;
  } catch { return true; }
}

/** stamp a label on a picture (AI renders are always marked) */
export function stampLabel(dataUrl: string, text: string): Promise<string> {
  return new Promise((res) => {
    const im = new Image();
    im.onload = () => {
      const c = document.createElement("canvas"); c.width = im.width; c.height = im.height;
      const g = c.getContext("2d")!; g.drawImage(im, 0, 0);
      const fs = Math.max(12, Math.round(im.width / 55));
      g.font = `600 ${fs}px Arial`;
      const w = g.measureText(text).width + fs;
      g.fillStyle = "rgba(15,23,42,0.62)"; g.fillRect(im.width - w - fs / 2, im.height - fs * 2, w, fs * 1.6);
      g.fillStyle = "#ffffff"; g.fillText(text, im.width - w - fs / 2 + fs / 2, im.height - fs * 0.85);
      res(c.toDataURL("image/png"));
    };
    im.onerror = () => res(dataUrl);
    im.src = dataUrl;
  });
}

/** 1.21 a room label to stamp on a picture: position and letter height as fractions of the picture */
export type Stamp = { fx: number; fy: number; name: string; size: string; fs: number; rot: boolean };

/** room names + sizes written on a plan picture (after an AI polish – the AI never writes the words) */
export function stampPlanLabels(dataUrl: string, stamps: Stamp[]): Promise<string> {
  return new Promise((res) => {
    const im = new Image();
    im.onload = () => {
      const c = document.createElement("canvas"); c.width = im.width; c.height = im.height;
      const g = c.getContext("2d")!; g.drawImage(im, 0, 0);
      g.textAlign = "center"; g.textBaseline = "middle"; g.lineJoin = "round";
      for (const s of stamps) {
        const px = Math.max(7, s.fs * im.height);
        g.save(); g.translate(s.fx * im.width, s.fy * im.height); if (s.rot) g.rotate(-Math.PI / 2);
        const put = (t: string, y: number, size: number, w: number, fill: string) => {
          g.font = `${w} ${size}px Arial, Helvetica, sans-serif`;
          g.lineWidth = size * 0.3; g.strokeStyle = "rgba(255,255,255,0.95)"; g.strokeText(t, 0, y);
          g.fillStyle = fill; g.fillText(t, 0, y);
        };
        put(s.name, -px * 0.45, px, 800, "#1b1f24"); put(s.size, px * 0.55, px * 0.8, 700, "#27303a");
        g.restore();
      }
      res(c.toDataURL("image/png"));
    };
    im.onerror = () => res(dataUrl);
    im.src = dataUrl;
  });
}
