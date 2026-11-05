/** 1.15 – Material Library panel (3D tab): pick a colour / material for every part of the house (and per room),
 *  add your OWN items (shade code + colour, or a photo of a tile / stone / wood – uploaded or from a web link),
 *  and a Showcase of everything picked (download PNG / print to PDF). */
import { useMemo, useRef, useState } from "react";
import { Download, ImagePlus, Link2, Palette, Plus, Printer, RotateCcw, Sparkles, X } from "lucide-react";
import { Modal, toast } from "../ui";
import { api } from "../../lib/api";
import type { Plan } from "../../lib/plan";
import { CAT_LABEL, SLOTS, type Cat, type Item, type Picks, type Slot } from "./house3d/catalog";

type Props = {
  plan: Plan; picks: Picks; items: Item[]; swatch: (it: Item) => string; isOwner: boolean; code: string;
  onPick: (slot: Slot, ref: string | null) => void; onRoomPick: (roomId: string, kind: "wall" | "floor", ref: string | null) => void;
  onLibraryChanged: () => void; shot: () => string | null;
};

export default function MaterialPanel({ plan, picks, items, swatch, isOwner, code, onPick, onRoomPick, onLibraryChanged, shot }: Props) {
  const [slot, setSlot] = useState<Slot>("ext_wall");
  const [room, setRoom] = useState("");  // "" = whole house
  const [roomKind, setRoomKind] = useState<"wall" | "floor">("wall");
  const [q, setQ] = useState("");
  const [addOpen, setAddOpen] = useState(false);
  const [show, setShow] = useState(false);
  const byRef = useMemo(() => new Map(items.map((i) => [i.ref, i])), [items]);
  // room keys are "floor:room id" – the same id (stair_1…) exists on every floor
  const rooms = plan.levels.flatMap((lv, li) => lv.rooms.filter((r) => !["terrace", "balcony", "sitout", "parking"].includes(r.type)).map((r) => ({ lv: lv.name, r, key: `${li}:${r.id}` })));
  const slotDef = SLOTS.find((x) => x.key === slot)!;
  const cats: Cat[] = room ? (roomKind === "floor" ? ["flooring"] : ["paint", "wall_tile", "cladding"]) : slotDef.cats;
  const list = items.filter((i) => cats.includes(i.cat) && (!q || `${i.name} ${i.brand || ""} ${i.code || ""}`.toLowerCase().includes(q.toLowerCase())));
  const current = room ? picks.rooms?.[room]?.[roomKind] : picks.mat?.[slot];
  const apply = (ref: string | null) => (room ? onRoomPick(room, roomKind, ref) : onPick(slot, ref));
  const chip = (ref?: string) => { const it = ref ? byRef.get(ref) : undefined; return it ? <img src={swatch(it)} alt="" className="h-5 w-5 rounded border border-slate-300 object-cover" /> : <span className="h-5 w-5 rounded border border-dashed border-slate-300" />; };

  return (
    <div className="rounded-lg border border-line p-3 text-sm">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span className="text-xs font-semibold text-navy-ink"><Palette size={13} className="mr-1 inline" />Material library</span>
        <span className="flex-1" />
        {isOwner && <button className="btn-outline btn-sm" onClick={() => setAddOpen(true)}><Plus size={14} />Add your own</button>}
        <button className="btn-primary btn-sm" onClick={() => setShow(true)}><Sparkles size={14} />Showcase</button>
      </div>
      <div className="grid gap-3 lg:grid-cols-[220px_1fr]">
        <div className="space-y-2">
          {(["Exterior", "Interior"] as const).map((grp) => (
            <div key={grp}>
              <div className="mb-1 text-[11px] font-semibold uppercase text-slate-400">{grp}</div>
              {SLOTS.filter((x) => x.group === grp).map((x) => (
                <button key={x.key} onClick={() => { setSlot(x.key); setRoom(""); }}
                  className={`mb-1 flex w-full items-center gap-2 rounded-md px-2 py-1 text-left text-xs ${!room && slot === x.key ? "bg-brand-600 text-white" : "hover:bg-slate-50"}`}>
                  {chip(picks.mat?.[x.key])}<span className="flex-1 truncate">{x.label}</span>
                </button>
              ))}
            </div>
          ))}
          <div>
            <div className="mb-1 text-[11px] font-semibold uppercase text-slate-400">One room only</div>
            <select className="input py-1 text-xs" value={room} onChange={(e) => setRoom(e.target.value)}>
              <option value="">— choose a room —</option>
              {rooms.map(({ lv, r, key }) => <option key={key} value={key}>{lv}: {r.name}</option>)}
            </select>
            {room && (
              <div className="mt-1 flex gap-1">
                {(["wall", "floor"] as const).map((k) => (
                  <button key={k} onClick={() => setRoomKind(k)} className={`flex flex-1 items-center justify-center gap-1 rounded-md px-2 py-1 text-xs font-semibold ${roomKind === k ? "bg-brand-600 text-white" : "bg-slate-100"}`}>
                    {chip(picks.rooms?.[room]?.[k])}{k === "wall" ? "Walls" : "Floor"}</button>
                ))}
              </div>
            )}
          </div>
        </div>
        <div className="min-w-0">
          <div className="mb-2 flex flex-wrap items-center gap-2">
            <b className="text-xs text-navy-ink">{room ? `${rooms.find((x) => x.key === room)?.r.name} – ${roomKind}` : slotDef.label}</b>
            <input className="input w-auto flex-1 py-1 text-xs" placeholder="Search name / brand / shade code…" value={q} onChange={(e) => setQ(e.target.value)} />
            {current && <button className="btn-ghost btn-sm" onClick={() => apply(null)}><RotateCcw size={13} />{room ? "Same as house" : "Style default"}</button>}
          </div>
          <div className="grid max-h-[260px] grid-cols-3 gap-2 overflow-auto sm:grid-cols-4 xl:grid-cols-6">
            {list.map((it) => (
              <button key={it.ref} onClick={() => apply(it.ref)} title={`${it.name}${it.brand ? ` · ${it.brand}` : ""}${it.code ? ` · ${it.code}` : ""}`}
                className={`rounded-lg border p-1 text-left ${current === it.ref ? "border-brand-500 ring-2 ring-brand-500" : "border-line hover:border-brand-300"}`}>
                <img src={swatch(it)} alt="" className="h-12 w-full rounded object-cover" />
                <div className="mt-0.5 truncate text-[10px] font-medium text-navy-ink">{it.name}</div>
                <div className="truncate text-[9px] text-slate-500">{it.custom ? `${it.brand || "Your item"}${it.code ? ` · ${it.code}` : ""}` : CAT_LABEL[it.cat]}</div>
              </button>
            ))}
            {!list.length && <div className="col-span-full text-xs text-slate-500">Nothing here yet{isOwner ? " – use “Add your own”." : "."}</div>}
          </div>
          <p className="mt-2 text-[11px] text-slate-500">The 3D view changes as you click. Picks are saved with the design (press Save).</p>
        </div>
      </div>
      <AddItem open={addOpen} onClose={() => setAddOpen(false)} onSaved={onLibraryChanged} defaultCat={cats[0]} />
      <Showcase open={show} onClose={() => setShow(false)} plan={plan} picks={picks} byRef={byRef} swatch={swatch} code={code} shot={shot} />
    </div>
  );
}

// ---------------------------------------------------------------- add your own item
function AddItem({ open, onClose, onSaved, defaultCat }: { open: boolean; onClose: () => void; onSaved: () => void; defaultCat: Cat }) {
  const blank = { category: defaultCat as string, name: "", brand: "", code: "", color: "#d9d4cc", finish: "matt", tile_ft: "2", rate: "", unit: "", url: "" };
  const [f, setF] = useState(blank);
  const [busy, setBusy] = useState(false);
  const file = useRef<HTMLInputElement>(null);
  const [img, setImg] = useState<File | null>(null);
  const set = (k: keyof typeof blank) => (e: any) => setF({ ...f, [k]: e.target.value });
  const save = async () => {
    if (!f.name.trim()) return toast("Give the item a name", "err");
    setBusy(true);
    try {
      const it = await api<any>("/api/materials", { body: { category: f.category, name: f.name, brand: f.brand, code: f.code, color: f.color, finish: f.finish,
        tile_ft: Number(f.tile_ft) || 2, rate: f.rate === "" ? null : Number(f.rate), unit: f.unit, source_url: f.url } });
      if (img) { const fd = new FormData(); fd.append("file", img); await api(`/api/materials/${it.id}/image`, { form: fd }); }
      else if (f.url.trim()) {
        try { await api(`/api/materials/${it.id}/image-from-url`, { body: { url: f.url.trim() } }); }
        catch (e: any) { toast(`Saved without a photo: ${e.message}`, "err"); }
      }
      toast(`${f.name} added to your library`); setF(blank); setImg(null); onSaved(); onClose();
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  return (
    <Modal open={open} onClose={onClose} title="Add your own colour / material">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-xs"><span className="label">Category</span>
          <select className="input" value={f.category} onChange={set("category")}>{Object.entries(CAT_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
        <label className="text-xs"><span className="label">Name *</span><input className="input" value={f.name} onChange={set("name")} placeholder="e.g. Royale Lemon Tart / Kajaria 60x60" /></label>
        <label className="text-xs"><span className="label">Brand</span><input className="input" value={f.brand} onChange={set("brand")} placeholder="Asian Paints / Berger / Kajaria…" /></label>
        <label className="text-xs"><span className="label">Shade / product code</span><input className="input" value={f.code} onChange={set("code")} placeholder="e.g. 7896" /></label>
        <label className="text-xs"><span className="label">Colour (used when there is no photo)</span>
          <div className="flex gap-2"><input type="color" className="h-9 w-12 rounded border border-line" value={f.color} onChange={set("color")} /><input className="input" value={f.color} onChange={set("color")} /></div></label>
        <label className="text-xs"><span className="label">Finish</span><select className="input" value={f.finish} onChange={set("finish")}><option value="matt">Matt</option><option value="satin">Satin</option><option value="gloss">Gloss</option></select></label>
        <div className="sm:col-span-2 rounded-lg border-2 border-dashed border-brand-100 p-3 text-xs">
          <div className="mb-2 font-semibold text-navy-ink">Photo of the tile / stone / wood (optional)</div>
          <div className="flex flex-wrap items-center gap-2">
            <button className="btn-outline btn-sm" onClick={() => file.current?.click()}><ImagePlus size={14} />{img ? img.name : "Upload photo"}</button>
            <span className="text-slate-400">or</span>
            <div className="relative min-w-[220px] flex-1"><Link2 size={14} className="absolute left-2 top-2.5 text-slate-400" />
              <input className="input pl-7" value={f.url} onChange={set("url")} placeholder="Picture link from a website (right-click → Copy image address)" /></div>
          </div>
          <label className="mt-2 flex items-center gap-2">The photo covers <input className="input w-16 py-1" type="number" min="0.25" step="0.25" value={f.tile_ft} onChange={set("tile_ft")} /> ft (one tile = 2 ft for 60x60 cm)</label>
          <input ref={file} type="file" hidden accept=".jpg,.jpeg,.png,.webp" onChange={(e) => { setImg(e.target.files?.[0] || null); e.target.value = ""; }} />
        </div>
        <label className="text-xs"><span className="label">Rate (optional)</span><input className="input" type="number" min="0" value={f.rate} onChange={set("rate")} placeholder="₹" /></label>
        <label className="text-xs"><span className="label">Per</span><input className="input" value={f.unit} onChange={set("unit")} placeholder="sq ft / litre / box" /></label>
      </div>
      <div className="mt-4 flex justify-end gap-2">
        <button className="btn-ghost" onClick={onClose}>Cancel</button>
        <button className="btn-primary" disabled={busy} onClick={save}>{busy ? "Saving…" : "Add to library"}</button>
      </div>
      <p className="mt-2 text-[11px] text-slate-500">Your items stay in your library for every project. Remove one from Settings → Recycle Bin.</p>
    </Modal>
  );
}

// ---------------------------------------------------------------- showcase of what is picked
function Showcase({ open, onClose, plan, picks, byRef, swatch, code, shot }: {
  open: boolean; onClose: () => void; plan: Plan; picks: Picks; byRef: Map<string, Item>; swatch: (it: Item) => string; code: string; shot: () => string | null;
}) {
  const rows: { where: string; it: Item }[] = [];
  for (const sl of SLOTS) { const r = picks.mat?.[sl.key]; const it = r ? byRef.get(r) : undefined; if (it) rows.push({ where: sl.label, it }); }
  for (const [li, lv] of plan.levels.entries()) for (const rm of lv.rooms) {
    const p = picks.rooms?.[`${li}:${rm.id}`];
    if (!p) continue;
    for (const k of ["wall", "floor"] as const) { const it = p[k] ? byRef.get(p[k]!) : undefined; if (it) rows.push({ where: `${lv.name} · ${rm.name} – ${k === "wall" ? "walls" : "floor"}`, it }); }
  }
  const sheet = async (kind: "png" | "print") => {
    const img3d = shot();
    const W = 1600, rowH = 86, head = img3d ? 760 : 140;
    const cv = document.createElement("canvas"); cv.width = W; cv.height = head + rows.length * rowH + 80;
    const g = cv.getContext("2d")!;
    g.fillStyle = "#fff"; g.fillRect(0, 0, W, cv.height);
    g.fillStyle = "#0f2350"; g.font = "bold 40px Arial"; g.fillText("Material & Colour Showcase", 40, 60);
    g.font = "22px Arial"; g.fillStyle = "#475569"; g.fillText(`${code} · ${new Date().toLocaleDateString("en-IN")}`, 40, 96);
    if (img3d) { const im = await load(img3d); g.drawImage(im, 40, 120, W - 80, (W - 80) * im.height / im.width > 600 ? 600 : (W - 80) * im.height / im.width); }
    let y = head;
    for (const { where, it } of rows) {
      const sw = await load(it.image || swatch(it)).catch(() => null);
      g.fillStyle = it.color; g.fillRect(40, y, 120, 70);
      if (sw) g.drawImage(sw, 40, y, 120, 70);
      g.strokeStyle = "#cbd5e1"; g.strokeRect(40, y, 120, 70);
      g.fillStyle = "#0f2350"; g.font = "bold 24px Arial"; g.fillText(where, 190, y + 28);
      g.fillStyle = "#111827"; g.font = "22px Arial";
      g.fillText(`${it.name}${it.brand ? ` · ${it.brand}` : ""}${it.code ? ` · code ${it.code}` : ""}${it.custom ? "" : ` (${CAT_LABEL[it.cat]})`}`, 190, y + 58);
      y += rowH;
    }
    const url = cv.toDataURL("image/png");
    if (kind === "png") { const a = document.createElement("a"); a.href = url; a.download = `${code}_Material_Showcase.png`; a.click(); return; }
    const w = window.open("", "_blank");
    if (!w) return toast("Allow pop-ups to print", "err");
    w.document.write(`<title>${code} Material Showcase</title><img src="${url}" style="width:100%" onload="setTimeout(()=>print(),300)">`);
    w.document.close();
  };
  return (
    <Modal open={open} onClose={onClose} title="Showcase – your picks">
      {!rows.length ? <p className="text-sm text-slate-500">Nothing picked yet – choose colours / materials in the library first.</p> : (
        <ul className="max-h-[420px] divide-y divide-line overflow-auto rounded-lg border border-line">
          {rows.map(({ where, it }, i) => (
            <li key={i} className="flex items-center gap-3 px-3 py-2 text-sm">
              <img src={it.image || swatch(it)} alt="" className="h-12 w-16 rounded border border-line object-cover" />
              <div className="min-w-0 flex-1"><div className="font-semibold text-navy-ink">{where}</div>
                <div className="truncate text-xs text-slate-600">{it.name}{it.brand ? ` · ${it.brand}` : ""}{it.code ? ` · code ${it.code}` : ""}{it.rate ? ` · ₹${it.rate}${it.unit ? `/${it.unit}` : ""}` : ""}</div></div>
            </li>
          ))}
        </ul>
      )}
      <div className="mt-4 flex flex-wrap justify-end gap-2">
        <button className="btn-ghost" onClick={onClose}><X size={14} />Close</button>
        <button className="btn-outline" disabled={!rows.length} onClick={() => sheet("png")}><Download size={14} />Download (PNG)</button>
        <button className="btn-primary" disabled={!rows.length} onClick={() => sheet("print")}><Printer size={14} />Print / Save as PDF</button>
      </div>
    </Modal>
  );
}

function load(src: string): Promise<HTMLImageElement> {
  return new Promise((ok, bad) => { const im = new Image(); im.onload = () => ok(im); im.onerror = bad; im.src = src; });
}

