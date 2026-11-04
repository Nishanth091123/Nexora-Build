/** 1.13 – download what is on the screen now (saved or not): drawing set, one sheet, plan PDF / DXF, SVG / PNG. */
import { downloadPost } from "./api";
import type { Plan } from "./plan";

export function exportPlan(pid: number, plan: Plan, kind: "sheets_pdf" | "sheets_dxf" | "plan_pdf" | "plan_dxf", name: string,
  o: { style?: "paper" | "cad"; page?: string; version?: number | null } = {}) {
  const q = new URLSearchParams({ kind, style: o.style || "paper", ...(o.page ? { page: o.page } : {}) });
  return downloadPost(`/api/projects/${pid}/design/export?${q}`, { plan, version: o.version ?? null }, name);
}

function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a"); a.href = url; a.download = name; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

/** an <svg> string → .svg file */
export function saveSvg(svg: string, name: string) {
  save(new Blob([svg.startsWith("<?xml") ? svg : `<?xml version="1.0" encoding="UTF-8"?>\n${svg}`], { type: "image/svg+xml" }), name);
}

/** an <svg> element or string → PNG (white or given background), `width` px wide */
export async function savePng(svg: string | SVGSVGElement, name: string, width = 2400, bg = "#ffffff") {
  const el = typeof svg === "string" ? new DOMParser().parseFromString(svg, "image/svg+xml").documentElement as unknown as SVGSVGElement : svg;
  const clone = el.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("xmlns", "http://www.w3.org/2000/svg");
  const vb = (clone.getAttribute("viewBox") || "").split(/[\s,]+/).map(Number);
  const r = el instanceof SVGSVGElement && el.isConnected ? el.getBoundingClientRect() : null;
  const ratio = vb.length === 4 && vb[2] > 0 ? vb[3] / vb[2] : r && r.width ? r.height / r.width : 0.75;
  const w = width, h = Math.round(width * ratio);
  clone.setAttribute("width", String(w)); clone.setAttribute("height", String(h));
  const data = new XMLSerializer().serializeToString(clone);
  const img = new Image();
  await new Promise<void>((ok, bad) => { img.onload = () => ok(); img.onerror = () => bad(new Error("Could not draw the image")); img.src = "data:image/svg+xml;charset=utf-8," + encodeURIComponent(data); });
  const c = document.createElement("canvas"); c.width = w; c.height = h;
  const g = c.getContext("2d")!; g.fillStyle = bg; g.fillRect(0, 0, w, h); g.drawImage(img, 0, 0, w, h);
  await new Promise<void>((ok) => c.toBlob((b) => { if (b) save(b, name); ok(); }, "image/png"));
}
