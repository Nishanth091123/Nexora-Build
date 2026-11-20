// 1.27 Design catalog: elevation styles (1,600) and interior designs (636), pictures drawn by Nexora on this project's proportions.
// "Use" writes the style into the drawing (elevation) or into the interior estimate (wardrobe, TV unit, kitchen, pooja, ceiling).
// "AI render" turns the picture into a photo-like concept with the free AI render service.
import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, Sparkles } from "lucide-react";
import { Badge, Card, Modal, PillTabs, toast } from "../components/ui";
import { api } from "../lib/api";
import AIRender from "../components/design/AIRender";

type Facets = { elevation: any; interior: any };
const SEL = "input !py-1 !text-xs";

async function svgToPng(svg: string, w = 900): Promise<string> {
  const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  try {
    const img = await new Promise<HTMLImageElement>((ok, bad) => { const i = new Image(); i.onload = () => ok(i); i.onerror = bad; i.src = url; });
    const k = w / (img.width || w);
    const c = document.createElement("canvas");
    c.width = w; c.height = Math.round((img.height || w) * k);
    const g = c.getContext("2d")!;
    g.fillStyle = "#ffffff"; g.fillRect(0, 0, c.width, c.height);
    g.drawImage(img, 0, 0, c.width, c.height);
    return c.toDataURL("image/png");
  } finally { URL.revokeObjectURL(url); }
}

function Pager({ page, total, size, set }: { page: number; total: number; size: number; set: (n: number) => void }) {
  const pages = Math.max(1, Math.ceil(total / size));
  return (
    <div className="mt-3 flex items-center justify-center gap-3 text-sm">
      <button className="btn-outline" disabled={page <= 1} onClick={() => set(page - 1)}>Previous</button>
      <span className="text-slate-600">Page {page} of {pages} · {total} designs</span>
      <button className="btn-outline" disabled={page >= pages} onClick={() => set(page + 1)}>Next</button>
    </div>
  );
}

export function useFacets() {
  const [f, setF] = useState<Facets | null>(null);
  useEffect(() => { api<Facets>("/api/catalog/facets").then(setF).catch(() => {}); }, []);
  return f;
}

// ------------------------------------------------------------------ elevation
export function ElevationCatalog({ pid }: { pid: number }) {
  const nav = useNavigate();
  const facets = useFacets();
  const [flt, setFlt] = useState({ family: "", palette: "", top: "", clad: "", win: "", feature: "" });
  const [fit, setFit] = useState(true);
  const [page, setPage] = useState(1);
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");
  const [sel, setSel] = useState<any>(null);
  const [big, setBig] = useState<{ svg: string; prompt: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [render, setRender] = useState<{ base: string; prompt: string; style: string } | null>(null);
  const [done, setDone] = useState<any>(null);
  const q = useMemo(() => new URLSearchParams({ ...flt, fit: String(fit), page: String(page), size: "24" }).toString(), [flt, page, fit]);
  const load = useCallback(async () => {
    try { setData(await api<any>(`/api/projects/${pid}/catalog/elevation?${q}`)); setErr(""); } catch (e: any) { setErr(e.message || "Could not load"); }
  }, [pid, q]);
  useEffect(() => { load(); }, [load]);
  const setF = (k: string) => (e: any) => { setFlt((x) => ({ ...x, [k]: e.target.value })); setPage(1); };
  const open = async (it: any) => {
    setSel(it); setBig(null); setDone(null);
    try { setBig(await api<any>(`/api/projects/${pid}/catalog/elevation/${it.id}/svg`)); } catch (e: any) { toast(e.message, "err"); }
  };
  const apply = async () => {
    setBusy(true);
    try {
      const r = await api<any>(`/api/projects/${pid}/catalog/elevation/${sel.id}/apply`, { method: "POST", body: {} });
      setDone(r); toast("Elevation style applied – saved as a new drawing version"); load();
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const aiRender = async () => {
    if (!big) return;
    try { setRender({ base: await svgToPng(big.svg), prompt: big.prompt, style: sel.family }); } catch { toast("Could not prepare the picture", "err"); }
  };
  if (err) return <Card title="Drawing needed"><p className="text-sm text-slate-600">{err}</p><button className="btn-primary mt-3" onClick={() => nav("/design")}>Open Design</button></Card>;
  const items: any[] = data?.items || [];
  return (
    <Card title={`Elevation styles${data ? ` – ${data.total} of ${facets?.elevation?.total ?? 1600}` : ""}`} icon={<Sparkles size={20} />}>
      <p className="mb-3 text-sm text-slate-600">Every picture is drawn on <b>your house</b> ({data?.floors ?? "–"} floor{data?.floors === 1 ? "" : "s"}, {Math.round(data?.width_ft ?? 0)} ft wide). Pick one – the front elevation drawing, the 3D model and the PDFs follow it. Applying saves a <b>new version</b> of the drawing; nothing is overwritten.</p>
      {data?.has_drawing && (
        <label className="mb-3 flex items-center gap-2 text-sm text-slate-700">
          <input type="checkbox" checked={fit} onChange={(e) => { setFit(e.target.checked); setPage(1); }} />
          Only styles made for this plan ({data.floors === 1 ? "ground floor only" : `G+${data.floors - 1} and above`}) – untick to see all {facets?.elevation?.total ?? 1600}
        </label>)}
      <div className="mb-3 grid grid-cols-2 gap-2 sm:grid-cols-6">
        <select className={SEL} value={flt.family} onChange={setF("family")}><option value="">All families</option>{facets?.elevation.families.map((x: any) => <option key={x.id} value={x.id}>{x.label}</option>)}</select>
        <select className={SEL} value={flt.palette} onChange={setF("palette")}><option value="">All colours</option>{facets?.elevation.palettes.map((x: any) => <option key={x.id} value={x.id}>{x.label}</option>)}</select>
        <select className={SEL} value={flt.top} onChange={setF("top")}><option value="">Any top</option>{facets?.elevation.tops.map((x: any) => <option key={x.id} value={x.id}>{x.label}</option>)}</select>
        <select className={SEL} value={flt.clad} onChange={setF("clad")}><option value="">Any cladding</option>{facets?.elevation.claddings.map((x: any) => <option key={x.id} value={x.id}>{x.label}</option>)}</select>
        <select className={SEL} value={flt.win} onChange={setF("win")}><option value="">Any windows</option>{facets?.elevation.windows.map((x: any) => <option key={x.id} value={x.id}>{x.label}</option>)}</select>
        <select className={SEL} value={flt.feature} onChange={setF("feature")}><option value="">Any feature</option>{facets?.elevation.features?.map((x: any) => <option key={x.id} value={x.id}>{x.label}</option>)}</select>
      </div>
      {!data?.has_drawing && data && <p className="mb-2 rounded-lg bg-amber-50 p-2 text-xs text-amber-800">No saved drawing yet – pictures use a sample 30 ft, 2-floor house. Save a drawing in Design to apply a style.</p>}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
        {items.map((it) => (
          <button key={it.id} onClick={() => open(it)} className={`overflow-hidden rounded-xl border bg-white text-left shadow-sm transition hover:shadow-md ${data?.current?.id === it.id ? "border-brand-600 ring-2 ring-brand-200" : "border-line"}`}>
            <div className="w-full [&>svg]:h-auto [&>svg]:w-full" dangerouslySetInnerHTML={{ __html: it.svg }} />
            <div className="p-2"><div className="flex items-center justify-between gap-1"><span className="text-[11px] font-semibold text-slate-500">{it.id}</span>
              <span className="flex gap-1">{data?.current?.id === it.id && <Badge color="green">In use</Badge>}<Badge>{it.family}</Badge></span></div>
              <div className="mt-1 line-clamp-2 text-xs text-slate-700">{it.name}</div></div>
          </button>))}
      </div>
      {data && <Pager page={page} total={data.total} size={data.size} set={setPage} />}
      <Modal open={!!sel} title={sel ? `${sel.id} – ${sel.family} elevation` : ""} onClose={() => setSel(null)} wide="xl">
        {sel && <>
          <div className="mx-auto max-w-3xl [&>svg]:h-auto [&>svg]:w-full" dangerouslySetInnerHTML={{ __html: big?.svg || "" }} />
          <p className="mt-2 text-sm text-slate-700">{sel.name}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <button className="btn-primary" disabled={busy || !data?.has_drawing} onClick={apply}><Check size={16} />Use this elevation</button>
            <button className="btn-outline" disabled={!big} onClick={aiRender}><Sparkles size={16} />AI photo-like render</button>
            {done && <button className="btn-outline" onClick={() => nav("/design")}>Open Design (see 2D + 3D)</button>}
          </div>
          {done && <div className="mt-3 rounded-lg bg-emerald-50 p-3 text-sm text-emerald-900">Saved as drawing version {done.version}. The 2D front elevation, 3D view and PDFs now use this style.
            {done.notes?.length > 0 && <ul className="mt-1 list-disc pl-5 text-xs">{done.notes.map((n: string, i: number) => <li key={i}>{n}</li>)}</ul>}</div>}
          <p className="mt-2 text-xs text-slate-500">Cladding and pergola are listed as quantities only – add their rates in the estimate extras. The AI render is a concept picture, marked “AI concept render – not to scale”.</p>
        </>}
      </Modal>
      {render && <AIRender pid={pid} base={render.base} kind="exterior" style={render.style} light="day" extra0={render.prompt} onClose={() => setRender(null)} />}
    </Card>
  );
}

// ------------------------------------------------------------------ interior
const TYPE_ICON: Record<string, string> = { wardrobe: "Wardrobe", tv_unit: "TV unit", kitchen: "Modular kitchen", pooja: "Pooja unit", ceiling: "False ceiling" };

export function InteriorCatalog({ pid, onChanged }: { pid: number; onChanged: () => void }) {
  const nav = useNavigate();
  const facets = useFacets();
  const [type, setType] = useState("wardrobe");
  const [flt, setFlt] = useState({ scheme: "", tier: "" });
  const [page, setPage] = useState(1);
  const [data, setData] = useState<any>(null);
  const [err, setErr] = useState("");
  const [sel, setSel] = useState<any>(null);
  const [big, setBig] = useState<{ svg: string; prompt: string } | null>(null);
  const [rooms, setRooms] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const [render, setRender] = useState<{ base: string; prompt: string } | null>(null);
  const q = useMemo(() => new URLSearchParams({ type, ...flt, page: String(page), size: "24" }).toString(), [type, flt, page]);
  const load = useCallback(async () => {
    try { setData(await api<any>(`/api/projects/${pid}/catalog/interior?${q}`)); setErr(""); } catch (e: any) { setErr(e.message || "Could not load"); }
  }, [pid, q]);
  useEffect(() => { load(); }, [load]);
  const myRooms: any[] = (data?.rooms || []).filter((r: any) => r.type === type);
  const picks: Record<string, string> = data?.picks || {};
  const open = async (it: any) => {
    setSel(it); setBig(null);
    setRooms(myRooms.filter((r) => picks[`${r.id}|${type}`] === it.id).map((r) => r.id));
    try { setBig(await api<any>(`/api/projects/${pid}/catalog/interior/${it.id}/svg`)); } catch (e: any) { toast(e.message, "err"); }
  };
  const save = async (use: boolean) => {
    if (!rooms.length) { toast("Tick at least one room", "err"); return; }
    setBusy(true);
    try {
      const body = { picks: Object.fromEntries(rooms.map((r) => [`${r}|${type}`, use ? sel.id : null])) };
      await api(`/api/projects/${pid}/catalog/interior/picks`, { method: "PUT", body });
      toast(use ? "Design chosen – the interior estimate now uses it" : "Removed"); await load(); onChanged();
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const aiRender = async () => {
    if (!big) return;
    try { setRender({ base: await svgToPng(big.svg), prompt: big.prompt }); } catch { toast("Could not prepare the picture", "err"); }
  };
  if (err) return <Card title="Drawing needed"><p className="text-sm text-slate-600">{err}</p><button className="btn-primary mt-3" onClick={() => nav("/design")}>Open Design</button></Card>;
  const priced = type === "wardrobe" || type === "tv_unit" || type === "kitchen";
  return (
    <Card title={`Interior designs – ${facets?.interior?.total ?? 636}`} icon={<Sparkles size={20} />}>
      <p className="mb-3 text-sm text-slate-600">Choose a design for each room. <b>Wardrobe, TV unit and kitchen</b> change the quantity (layout) and the price tier of the interior estimate (economy → low, standard → default, premium → high of the searched rate; a rate you typed always wins). Pooja unit and false ceiling are shown in the PDF only – no searched rate.</p>
      <PillTabs tabs={Object.entries(TYPE_ICON).map(([id, label]) => ({ id, label: `${label}${facets ? ` (${facets.interior.counts[id]})` : ""}` }))} value={type} onChange={(v) => { setType(v); setPage(1); }} />
      <div className="my-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <select className={SEL} value={flt.scheme} onChange={(e) => { setFlt((x) => ({ ...x, scheme: e.target.value })); setPage(1); }}><option value="">All colours</option>{facets?.interior.schemes.map((x: any) => <option key={x.id} value={x.id}>{x.label}</option>)}</select>
        <select className={SEL} value={flt.tier} onChange={(e) => { setFlt((x) => ({ ...x, tier: e.target.value })); setPage(1); }}><option value="">All price tiers</option><option value="economy">Economy</option><option value="standard">Standard</option><option value="premium">Premium</option></select>
      </div>
      {myRooms.length === 0 && data && <p className="mb-2 rounded-lg bg-amber-50 p-2 text-xs text-amber-800">This drawing has no room for this item yet – you can still look and render, but cannot choose.</p>}
      <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-4">
        {(data?.items || []).map((it: any) => {
          const used = myRooms.filter((r) => picks[`${r.id}|${type}`] === it.id).length;
          return (
            <button key={it.id} onClick={() => open(it)} className={`overflow-hidden rounded-xl border bg-white text-left shadow-sm transition hover:shadow-md ${used ? "border-brand-600 ring-2 ring-brand-200" : "border-line"}`}>
              <div className="w-full [&>svg]:h-auto [&>svg]:w-full" dangerouslySetInnerHTML={{ __html: it.svg }} />
              <div className="p-2"><div className="flex items-center justify-between"><span className="text-[11px] font-semibold text-slate-500">{it.id}</span>
                <span className="flex gap-1">{used > 0 && <Badge color="green">{used} room{used > 1 ? "s" : ""}</Badge>}<Badge>{it.tier}</Badge></span></div>
                <div className="mt-1 line-clamp-2 text-xs text-slate-700">{it.name}</div></div>
            </button>);
        })}
      </div>
      {data && <Pager page={page} total={data.total} size={data.size} set={setPage} />}
      <Modal open={!!sel} title={sel ? `${sel.id} – ${TYPE_ICON[type]}` : ""} onClose={() => setSel(null)} wide="xl">
        {sel && <>
          <div className="mx-auto max-w-2xl [&>svg]:h-auto [&>svg]:w-full" dangerouslySetInnerHTML={{ __html: big?.svg || "" }} />
          <p className="mt-2 text-sm text-slate-700">{sel.name} · <b>{sel.tier}</b> tier{priced ? "" : " · not priced (no searched rate)"}</p>
          {myRooms.length > 0 && <div className="mt-3 rounded-xl border border-slate-200 p-3">
            <div className="mb-1 text-sm font-semibold text-navy-ink">Use in which rooms?</div>
            <div className="flex flex-wrap gap-3">{myRooms.map((r) => (
              <label key={r.id} className="flex items-center gap-1 text-sm"><input type="checkbox" checked={rooms.includes(r.id)} onChange={(e) => setRooms((x) => e.target.checked ? [...x, r.id] : x.filter((y) => y !== r.id))} />
                {r.floor} – {r.name}{picks[`${r.id}|${type}`] && picks[`${r.id}|${type}`] !== sel.id ? <span className="text-xs text-slate-400"> (has {picks[`${r.id}|${type}`]})</span> : null}</label>))}</div>
            <div className="mt-2 flex flex-wrap gap-2"><button className="btn-primary" disabled={busy} onClick={() => save(true)}><Check size={16} />Use this design</button>
              <button className="btn-outline" disabled={busy} onClick={() => save(false)}>Remove from ticked rooms</button></div>
          </div>}
          <div className="mt-3"><button className="btn-outline" disabled={!big} onClick={aiRender}><Sparkles size={16} />AI photo-like render</button></div>
          <p className="mt-2 text-xs text-slate-500">After choosing, open the <b>Interior</b> tab: the table shows the design name, quantity and rate, and the PDF gets a “Selected designs” page with these pictures.</p>
        </>}
      </Modal>
      {render && <AIRender pid={pid} base={render.base} kind="interior" style="modern" light="day" extra0={render.prompt} onClose={() => setRender(null)} />}
    </Card>
  );
}
