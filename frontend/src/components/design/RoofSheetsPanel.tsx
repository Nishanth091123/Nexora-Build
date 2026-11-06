/** 1.17 – Roofing sheets: full roof / shed on the terrace / staircase head room / part of a floor.
 *  Every sheet type, place and shape can be chosen. The drawings, approval sheet, estimate, structural notes,
 *  Vastu and the 3D all read plan.roof_sheets. Member sizes are written as entered. */
import { useState } from "react";
import { Plus, Trash2, Warehouse } from "lucide-react";
import type { Plan } from "../../lib/plan";

export type RoofSheet = {
  id: string; place: "full_roof" | "on_terrace" | "headroom" | "area"; level: number;
  x: number; y: number; w: number; d: number;
  sheet: "gi" | "galvalume" | "puff" | "acc" | "polycarbonate"; thk_mm: number; colour: string;
  shape: "gable" | "mono" | "hip"; ridge: "x" | "y"; high: "front" | "back" | "left" | "right";
  slope_deg: number; height_ft: number; overhang_ft: number; support: "truss" | "purlin";
  truss: { top: string; bottom: string; web: string; purlin: string; post: string; purlin_ft: number }; note?: string;
};

export const SHEET_TYPES: Record<RoofSheet["sheet"], { label: string; thk: number[]; unit: string; colour: string }> = {
  gi: { label: "GI sheet", thk: [0.4, 0.45, 0.5, 0.63], unit: "mm", colour: "#9ca3af" },
  galvalume: { label: "Galvalume colour-coated", thk: [0.4, 0.45, 0.47, 0.5], unit: "mm", colour: "#b91c1c" },
  puff: { label: "PUF insulated panel", thk: [30, 40, 50], unit: "mm", colour: "#e5e7eb" },
  acc: { label: "Fibre-cement (ACC)", thk: [4, 6], unit: "mm", colour: "#9ca3af" },
  polycarbonate: { label: "Polycarbonate", thk: [2, 3, 6], unit: "mm", colour: "#cfe8f7" },
};
const PLACES: Record<RoofSheet["place"], string> = {
  full_roof: "Full roof – instead of the RCC slab", on_terrace: "Shed on the RCC terrace", headroom: "Staircase head room (mumty)",
  area: "Part of a floor (sit-out / parking / utility / balcony)",
};
const COLOURS = ["#b91c1c", "#1d4ed8", "#15803d", "#9ca3af", "#e5e7eb", "#78350f", "#0f766e", "#f8fafc", "#cfe8f7"];
const DEFAULT_TRUSS = { top: "ISA 50x50x6", bottom: "ISA 50x50x6", web: "ISA 40x40x5", purlin: "40x40x2 mm SHS", post: "80 NB MS pipe", purlin_ft: 4 };
export const sheetLines = (p?: Plan | null) => ((p as any)?.roof_sheets || []).map((s: RoofSheet) =>
  `${SHEET_TYPES[s.sheet]?.label || s.sheet} ${s.thk_mm} mm · ${PLACES[s.place].split(" –")[0].split(" (")[0]} · ${Math.round(s.w * s.d)} sq ft`);

function rectFor(plan: Plan, place: RoofSheet["place"], level: number, roomId?: string) {
  const top = plan.levels.length - 1;
  const b = plan.building;
  if (place === "headroom") {
    const st = plan.levels[top].rooms.find((r) => r.type === "stair");
    return st ? { level: top, x: st.x, y: st.y, w: st.w, d: st.d } : null;
  }
  if (place === "area") {
    const r = plan.levels[level]?.rooms.find((q) => q.id === roomId);
    return r ? { level, x: r.x, y: r.y, w: r.w, d: r.d } : null;
  }
  const rooms = plan.levels[top].rooms;
  const x0 = Math.min(...rooms.map((r) => r.x)), x1 = Math.max(...rooms.map((r) => r.x + r.w));
  const y0 = Math.min(...rooms.map((r) => r.y)), y1 = Math.max(...rooms.map((r) => r.y + r.d));
  return { level: top, x: x0 || 0, y: y0 || 0, w: (x1 - x0) || b.w, d: (y1 - y0) || b.d };
}

export default function RoofSheetsPanel({ plan, onChange, disabled }: { plan: Plan; onChange: (list: RoofSheet[]) => void; disabled?: boolean }) {
  const list: RoofSheet[] = ((plan as any).roof_sheets || []) as RoofSheet[];
  const [open, setOpen] = useState<string | null>(list[0]?.id || null);
  const top = plan.levels.length - 1;
  const hasStair = plan.levels[top]?.rooms.some((r) => r.type === "stair");
  const areaRooms = plan.levels.flatMap((lv, li) => lv.rooms.filter((r) => ["sitout", "parking", "utility", "balcony", "terrace", "passage"].includes(r.type)).map((r) => ({ li, r, lv })));

  const add = (place: RoofSheet["place"]) => {
    const pick = place === "area" ? areaRooms[0] : null;
    const rc = rectFor(plan, place, pick?.li ?? top, pick?.r.id);
    if (!rc) return;
    const id = `rs${Date.now() % 100000}`;
    const s: RoofSheet = {
      id, place, ...rc, sheet: place === "area" ? "polycarbonate" : "galvalume", thk_mm: place === "area" ? 3 : 0.47,
      colour: place === "area" ? "#cfe8f7" : "#b91c1c", shape: place === "headroom" || place === "area" ? "mono" : "gable",
      ridge: "x", high: "back", slope_deg: 15, height_ft: place === "on_terrace" ? 9 : 9, overhang_ft: place === "full_roof" ? 2 : 1.5,
      support: place === "area" ? "purlin" : "truss", truss: { ...DEFAULT_TRUSS },
    };
    onChange([...list, s]); setOpen(id);
  };
  const set = (id: string, v: Partial<RoofSheet>) => onChange(list.map((s) => (s.id === id ? { ...s, ...v } : s)));
  const num = (v: string, d: number) => (Number.isFinite(Number(v)) && v !== "" ? Number(v) : d);

  return (
    <div className="space-y-3 text-sm">
      <p className="text-xs text-slate-500">Choose where a sheet roof goes. Sizes start from the room / building – change them if needed. Member sizes are written on the drawing as you enter them.</p>
      <div className="flex flex-wrap gap-1.5">
        <button className="btn-outline btn-sm" disabled={disabled || list.some((s) => s.place === "full_roof")} onClick={() => add("full_roof")}><Plus size={13} />Full roof</button>
        <button className="btn-outline btn-sm" disabled={disabled} onClick={() => add("on_terrace")}><Plus size={13} />Terrace shed</button>
        <button className="btn-outline btn-sm" disabled={disabled || !hasStair || list.some((s) => s.place === "headroom")} onClick={() => add("headroom")} title={hasStair ? "" : "No staircase on the top floor"}><Plus size={13} />Head room</button>
        <button className="btn-outline btn-sm" disabled={disabled || !areaRooms.length} onClick={() => add("area")} title={areaRooms.length ? "" : "Add a sit-out / parking / utility / balcony room first"}><Plus size={13} />Sit-out / parking / utility</button>
      </div>
      {!list.length && <p className="rounded-lg bg-slate-50 px-3 py-2 text-xs text-slate-500">No sheet roof – the roof is the RCC slab.</p>}
      {list.map((s) => {
        const T = SHEET_TYPES[s.sheet];
        const isOpen = open === s.id;
        return (
          <div key={s.id} className="rounded-xl border border-line">
            <button className="flex w-full items-center gap-2 px-3 py-2 text-left" onClick={() => setOpen(isOpen ? null : s.id)}>
              <span className="h-4 w-4 rounded" style={{ background: s.colour }} />
              <span className="flex-1"><b className="text-navy-ink">{PLACES[s.place].split(" –")[0].split(" (")[0]}</b><span className="ml-1 text-xs text-slate-500">{T.label} {s.thk_mm} mm · {s.shape} {s.slope_deg}° · {plan.levels[s.level]?.name}</span></span>
              <span role="button" className="text-red-500" onClick={(e) => { e.stopPropagation(); if (!disabled) onChange(list.filter((q) => q.id !== s.id)); }}><Trash2 size={14} /></span>
            </button>
            {isOpen && (
              <div className="grid grid-cols-2 gap-2 border-t border-line p-3">
                <label className="col-span-2"><span className="label">Where</span>
                  <select className="input" disabled={disabled} value={s.place} onChange={(e) => {
                    const place = e.target.value as RoofSheet["place"]; const rc = rectFor(plan, place, s.level, areaRooms[0]?.r.id);
                    if (rc) set(s.id, { place, ...rc });
                  }}>{(Object.keys(PLACES) as RoofSheet["place"][]).map((p) => <option key={p} value={p} disabled={p === "headroom" && !hasStair}>{PLACES[p]}</option>)}</select></label>
                {s.place === "area" && (
                  <label className="col-span-2"><span className="label">Room</span>
                    <select className="input" disabled={disabled} value={`${s.level}:${areaRooms.find((a) => a.li === s.level && a.r.x === s.x && a.r.y === s.y)?.r.id || ""}`}
                      onChange={(e) => { const [li, rid] = e.target.value.split(":"); const rc = rectFor(plan, "area", Number(li), rid); if (rc) set(s.id, rc); }}>
                      <option value="">— choose —</option>
                      {areaRooms.map((a) => <option key={`${a.li}:${a.r.id}`} value={`${a.li}:${a.r.id}`}>{a.lv.name} – {a.r.name}</option>)}
                    </select></label>
                )}
                <label><span className="label">Sheet</span>
                  <select className="input" disabled={disabled} value={s.sheet} onChange={(e) => { const k = e.target.value as RoofSheet["sheet"]; set(s.id, { sheet: k, thk_mm: SHEET_TYPES[k].thk[1] ?? SHEET_TYPES[k].thk[0], colour: SHEET_TYPES[k].colour }); }}>
                    {(Object.keys(SHEET_TYPES) as RoofSheet["sheet"][]).map((k) => <option key={k} value={k}>{SHEET_TYPES[k].label}</option>)}</select></label>
                <label><span className="label">Thickness ({T.unit})</span>
                  <select className="input" disabled={disabled} value={s.thk_mm} onChange={(e) => set(s.id, { thk_mm: Number(e.target.value) })}>
                    {T.thk.map((t) => <option key={t} value={t}>{t}</option>)}</select></label>
                <div className="col-span-2"><span className="label">Colour</span>
                  <div className="flex flex-wrap items-center gap-1.5">{COLOURS.map((c) => <button key={c} disabled={disabled} onClick={() => set(s.id, { colour: c })} className={`h-6 w-6 rounded border ${s.colour === c ? "ring-2 ring-brand-500" : "border-line"}`} style={{ background: c }} />)}
                    <input type="color" disabled={disabled} value={s.colour} onChange={(e) => set(s.id, { colour: e.target.value })} className="h-7 w-9" /></div></div>
                <label><span className="label">Shape</span>
                  <select className="input" disabled={disabled} value={s.shape} onChange={(e) => set(s.id, { shape: e.target.value as RoofSheet["shape"] })}>
                    <option value="gable">Gable (two slopes)</option><option value="mono">Mono-pitch (one slope)</option><option value="hip">Hip (four slopes)</option></select></label>
                {s.shape === "mono" ? (
                  <label><span className="label">High side</span>
                    <select className="input" disabled={disabled} value={s.high} onChange={(e) => set(s.id, { high: e.target.value as RoofSheet["high"] })}>
                      <option value="back">Back (slopes to road)</option><option value="front">Front (road side)</option><option value="left">Left</option><option value="right">Right</option></select></label>
                ) : (
                  <label><span className="label">Ridge runs</span>
                    <select className="input" disabled={disabled} value={s.ridge} onChange={(e) => set(s.id, { ridge: e.target.value as RoofSheet["ridge"] })}>
                      <option value="x">Left ↔ right (slopes front/back)</option><option value="y">Front ↔ back (gable faces the road)</option></select></label>
                )}
                <label><span className="label">Slope (°)</span><input className="input" type="number" disabled={disabled} defaultValue={s.slope_deg} onBlur={(e) => set(s.id, { slope_deg: num(e.target.value, 15) })} /></label>
                <label><span className="label">Overhang (ft)</span><input className="input" type="number" step={0.25} disabled={disabled} defaultValue={s.overhang_ft} onBlur={(e) => set(s.id, { overhang_ft: num(e.target.value, 1.5) })} /></label>
                {(s.place === "on_terrace" || s.place === "area") && (
                  <label className="col-span-2"><span className="label">Clear height at the eave (ft) – above the {s.place === "on_terrace" ? "terrace" : "floor"}</span><input className="input" type="number" disabled={disabled} defaultValue={s.height_ft} onBlur={(e) => set(s.id, { height_ft: num(e.target.value, 9) })} /></label>
                )}
                {(["x", "y", "w", "d"] as const).map((k) => (
                  <label key={k}><span className="label">{{ x: "From left (ft)", y: "From front (ft)", w: "Width (ft)", d: "Depth (ft)" }[k]}</span>
                    <input className="input" type="number" step={0.25} disabled={disabled} key={`${s.id}${k}${s[k]}`} defaultValue={s[k]} onBlur={(e) => set(s.id, { [k]: num(e.target.value, s[k]) } as any)} /></label>
                ))}
                <label className="col-span-2"><span className="label">Support</span>
                  <select className="input" disabled={disabled} value={s.support} onChange={(e) => set(s.id, { support: e.target.value as RoofSheet["support"] })}>
                    <option value="truss">MS steel truss + purlins</option><option value="purlin">Purlins only (on posts / walls – small spans)</option></select></label>
                {([["top", "Top chord"], ["bottom", "Bottom chord"], ["web", "Web members"], ["purlin", "Purlin"], ["post", "Posts"]] as const)
                  .filter(([k]) => s.support === "truss" || !["top", "bottom", "web"].includes(k)).map(([k, l]) => (
                  <label key={k}><span className="label">{l}</span><input className="input" disabled={disabled} defaultValue={(s.truss as any)[k]} onBlur={(e) => set(s.id, { truss: { ...s.truss, [k]: e.target.value } })} /></label>
                ))}
                <label><span className="label">Purlin spacing (ft)</span><input className="input" type="number" step={0.5} disabled={disabled} defaultValue={s.truss.purlin_ft} onBlur={(e) => set(s.id, { truss: { ...s.truss, purlin_ft: num(e.target.value, 4) } })} /></label>
                <p className="col-span-2 text-[11px] text-amber-700">Member sizes are shown as entered on the truss sheet – confirm them with your structural engineer.</p>
              </div>
            )}
          </div>
        );
      })}
      {list.length > 0 && <p className="flex items-center gap-1 text-[11px] text-slate-500"><Warehouse size={12} />Drawings get a Roof Plan + Truss sheet; the estimate gets sheet, ridge, steel, paint, gutter and bolts.</p>}
    </div>
  );
}
