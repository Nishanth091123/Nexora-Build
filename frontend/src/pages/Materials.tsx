/** 1.18 – Material Library: every material of a house, stage by stage → market brands (names only) → variants →
 *  your own rate. Brands are tagged A / B / C: A = Premium, B = Standard, C = Basic estimates. A variant can be
 *  chosen for the current project ("Use in project") – that project's estimate then uses its rate. */
import { useEffect, useMemo, useState } from "react";
import { ChevronDown, ChevronRight, Download, FileUp, Library, Plus, Search, Star, X } from "lucide-react";
import Page from "../components/Page";
import OwnerDelete from "../components/OwnerDelete";
import { Badge, Card, Empty, Modal, toast } from "../components/ui";
import { api, downloadFile } from "../lib/api";
import { useAuth } from "../lib/auth";

type Category = { key: string; name: string; stage: string; unit: string; rate_code: string | null };
type Brand = { id: number; category: string; name: string; tier: "" | "A" | "B" | "C"; is_default: boolean; notes: string };
type Variant = { id: number; brand_id: number; category: string; name: string; code: string; spec: Record<string, any>; color: string; unit: string;
  rate: number | null; gst_pct: number | null; rate_date: string | null; rate_code: string | null };
type Lib = { categories: Category[]; brands: Brand[]; variants: Variant[]; tiers: Record<string, Record<string, { rate: number; n: number; names: string[] }>>;
  rates_locked: boolean; can_edit: boolean };

const TIER_LABEL: Record<string, string> = { A: "Premium", B: "Standard", C: "Basic" };
const TIER_CLS: Record<string, string> = { A: "bg-amber-500 text-white", B: "bg-brand-600 text-white", C: "bg-slate-500 text-white", "": "bg-slate-100 text-slate-500" };
const specChips = (s: Record<string, any>) => Object.entries(s || {}).filter(([k]) => !["rate_code", "factor"].includes(k))
  .map(([k, v]) => Array.isArray(v) ? `${k.replace("_mm", "")}: ${v.join(", ")} mm` : `${v}${k === "mm" ? " mm" : k === "weight_kg" ? " kg" : k === "litres" ? " L" : k === "hp" ? " HP" : k === "sq_mm" ? " sq mm" : ""}`);

export default function MaterialsPage() {
  const { user, currentProject } = useAuth();
  const isOwner = user?.role === "owner";
  const [lib, setLib] = useState<Lib | null>(null);
  const [cat, setCat] = useState("cement");
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<Record<number, boolean>>({});
  const [choices, setChoices] = useState<Record<string, number>>({});
  const [addBrand, setAddBrand] = useState(false);
  const [addVar, setAddVar] = useState<Brand | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const pid = currentProject?.id;
  const canEst = !!currentProject?.permissions?.estimate;

  const load = () => api<Lib>("/api/market").then(setLib).catch((e) => toast(e.message, "err"));
  useEffect(() => { load(); }, []);
  useEffect(() => { if (pid) api<any>(`/api/projects/${pid}/brand-choices`).then((d) => setChoices(d.choices || {})).catch(() => setChoices({})); }, [pid]);

  const brandById = useMemo(() => new Map((lib?.brands || []).map((b) => [b.id, b])), [lib]);
  const catByKey = useMemo(() => new Map((lib?.categories || []).map((c) => [c.key, c])), [lib]);
  const stages = useMemo(() => Array.from(new Set((lib?.categories || []).map((c) => c.stage))), [lib]);
  const chosenIds = new Set(Object.values(choices).map(Number));

  // live search across everything: name, brand, code (a shade code like "09" lists 0901, 0902 …)
  const hits = useMemo(() => {
    const s = q.trim().toLowerCase();
    if (s.length < 2 || !lib) return [];
    return lib.variants.filter((v) => {
      const b = brandById.get(v.brand_id);
      return v.code.toLowerCase().startsWith(s) || `${v.name} ${b?.name || ""} ${v.code}`.toLowerCase().includes(s);
    }).sort((a, b) => Number(!a.code.toLowerCase().startsWith(s)) - Number(!b.code.toLowerCase().startsWith(s)) || a.code.localeCompare(b.code)).slice(0, 60);
  }, [q, lib, brandById]);

  if (!lib) return <Page title="Material Library" subtitle="Brands, variants and your rates"><div className="h-64 animate-pulse rounded-xl bg-slate-100" /></Page>;
  const c = catByKey.get(cat)!;
  const brands = lib.brands.filter((b) => b.category === cat).sort((a, b) => (a.tier || "Z").localeCompare(b.tier || "Z") || a.name.localeCompare(b.name));
  const tiers = c.rate_code ? lib.tiers[c.rate_code] : undefined;

  const saveBrand = async (b: Brand, patch: Partial<Brand>) => {
    try {
      const nb = await api<Brand>(`/api/market/brands/${b.id}`, { method: "PUT", body: { ...b, ...patch } });
      setLib((l) => l && { ...l, brands: l.brands.map((x) => (x.id === b.id ? nb : patch.is_default && x.category === b.category ? { ...x, is_default: false } : x)) });
      if (patch.tier !== undefined) load();
    } catch (e: any) { toast(e.message, "err"); }
  };
  const saveRate = async (v: Variant, rate: number | null, gst?: number | null) => {
    try {
      const nv = await api<Variant>(`/api/market/variants/${v.id}/rate`, { method: "PUT", body: { rate, gst_pct: gst ?? v.gst_pct } });
      setLib((l) => l && { ...l, variants: l.variants.map((x) => (x.id === v.id ? nv : x)) });
      toast("Rate saved");
    } catch (e: any) { toast(e.message, "err"); }
  };
  const choose = async (v: Variant, on: boolean) => {
    if (!pid) return toast("Choose a project first (top of the page)", "err");
    try {
      const key = v.rate_code || v.category;
      const d = await api<any>(`/api/projects/${pid}/brand-choices`, { method: "PUT", body: { category: key, variant_id: on ? v.id : null } });
      setChoices(d.choices || {});
      toast(on ? `${brandById.get(v.brand_id)?.name} · ${v.name} will be used in ${currentProject?.name}'s estimate` : "Removed from this project");
    } catch (e: any) { toast(e.message, "err"); }
  };

  const variantRow = (v: Variant, showBrand = false) => {
    const b = brandById.get(v.brand_id);
    const chosen = chosenIds.has(v.id);
    return (
      <tr key={v.id} className={chosen ? "bg-amber-50/70" : ""}>
        <td className="table-td">
          <div className="flex items-center gap-2">
            {v.color && <span className="h-5 w-5 shrink-0 rounded border border-slate-300" style={{ background: v.color }} title={v.color} />}
            <div className="min-w-0">
              <div className="font-semibold text-navy-ink">{showBrand && b ? `${b.name} · ` : ""}{v.name}</div>
              <div className="flex flex-wrap gap-1">{specChips(v.spec).map((s) => <span key={s} className="rounded bg-slate-100 px-1.5 text-[10px] text-slate-600">{s}</span>)}
                {showBrand && <span className="rounded bg-sky-50 px-1.5 text-[10px] text-sky-700">{catByKey.get(v.category)?.name}</span>}</div>
            </div>
          </div>
        </td>
        <td className="table-td font-mono text-xs">{v.code || "—"}</td>
        <td className="table-td text-xs">{v.unit}</td>
        <td className="table-td">
          {lib.rates_locked ? <span className="text-xs text-slate-400">owner only</span> : (
            <RateInput value={v.rate} onSave={(r) => saveRate(v, r)} />
          )}
        </td>
        <td className="table-td text-xs text-slate-500">{v.rate_date ? new Date(v.rate_date).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "2-digit" }) : ""}</td>
        <td className="table-td whitespace-nowrap text-right">
          {canEst && <button className={`btn-sm ${chosen ? "btn-primary" : "btn-ghost"}`} title={`Use this in ${currentProject?.name || "the project"}'s estimate`} onClick={() => choose(v, !chosen)}>
            <Star size={13} className={chosen ? "fill-white" : ""} />{chosen ? "In project" : "Use in project"}</button>}
          <OwnerDelete entity="market_variant" id={v.id} title={`${b?.name || ""} · ${v.name}`} onDone={load} />
        </td>
      </tr>
    );
  };
  const table = (rows: Variant[], showBrand = false) => (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[720px]">
        <thead><tr>{["Variant", "Code", "Unit", "Your rate (₹)", "Updated", ""].map((h) => <th key={h} className="table-th">{h}</th>)}</tr></thead>
        <tbody>{rows.map((v) => variantRow(v, showBrand))}</tbody>
      </table>
    </div>
  );

  return (
    <Page title="Material Library" subtitle="Every material of a house – market brands, variants and your own rates"
      actions={<div className="flex flex-wrap gap-2">
        <button className="btn-outline hidden sm:inline-flex" onClick={() => downloadFile("/api/market/template.csv", "Material_Library_Import_Template.csv")}><Download size={16} />Template</button>
        {isOwner && <button className="btn-outline" onClick={() => setImportOpen(true)}><FileUp size={16} />Import list</button>}
        {isOwner && <button className="btn-primary" onClick={() => setAddBrand(true)}><Plus size={16} />Add brand</button>}
      </div>}>
      <div className="card flex flex-wrap items-center gap-3 p-3">
        <div className="relative min-w-[240px] flex-1">
          <Search size={16} className="absolute left-3 top-2.5 text-slate-400" />
          <input className="input pl-9" placeholder="Search any material – name, brand or code (type a shade code like 09…)" value={q} onChange={(e) => setQ(e.target.value)} />
          {q && <button className="absolute right-2 top-2 rounded p-1 text-slate-400 hover:bg-slate-100" onClick={() => setQ("")}><X size={14} /></button>}
        </div>
        <div className="flex flex-wrap gap-1.5 text-[11px]">
          {(["A", "B", "C"] as const).map((t) => <span key={t} className={`rounded-full px-2 py-0.5 font-bold ${TIER_CLS[t]}`}>{t} = {TIER_LABEL[t]}</span>)}
        </div>
        {pid && <span className="text-xs text-slate-500">“Use in project” → <b className="text-navy-ink">{currentProject?.name}</b></span>}
      </div>

      {q.trim().length >= 2 ? (
        <Card title={`Search results (${hits.length}${hits.length === 60 ? "+" : ""})`} icon={<Search size={20} />}>
          {!hits.length ? <Empty text={`Nothing matches “${q}”. Shade / product codes come from your imported lists (Import list).`} /> : table(hits, true)}
        </Card>
      ) : (
        <div className="grid items-start gap-4 lg:grid-cols-[250px_1fr]">
          <div className="card p-2">
            {stages.map((st) => (
              <div key={st} className="mb-1">
                <div className="px-2 pb-1 pt-2 text-[11px] font-bold uppercase tracking-wide text-slate-400">{st}</div>
                {lib.categories.filter((x) => x.stage === st).map((x) => {
                  const nb = lib.brands.filter((b) => b.category === x.key).length;
                  const nr = lib.variants.filter((v) => v.category === x.key && v.rate != null).length;
                  return (
                    <button key={x.key} onClick={() => setCat(x.key)} className={`flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm ${cat === x.key ? "bg-brand-600 text-white" : "hover:bg-slate-50"}`}>
                      <span className="flex-1 truncate">{x.name}</span>
                      <span className={`text-[10px] ${cat === x.key ? "text-blue-100" : "text-slate-400"}`}>{nb}{nr ? ` · ₹${nr}` : ""}</span>
                    </button>
                  );
                })}
              </div>
            ))}
          </div>

          <div className="min-w-0 space-y-3">
            <div className="card p-4">
              <div className="flex flex-wrap items-center gap-2">
                <Library size={20} className="text-brand-600" /><h2 className="text-lg font-bold text-navy-ink">{c.name}</h2>
                <Badge color="gray">{c.stage}</Badge><span className="text-xs text-slate-500">per {c.unit}</span>
              </div>
              {c.rate_code ? (
                <div className="mt-3 grid gap-2 sm:grid-cols-3">
                  {(["A", "B", "C"] as const).map((t) => {
                    const lv = { A: "premium", B: "standard", C: "basic" }[t];
                    const info = tiers?.[lv];
                    return (
                      <div key={t} className="rounded-xl border border-line p-2.5">
                        <div className="flex items-center gap-1.5 text-xs font-bold text-navy-ink"><span className={`rounded px-1.5 ${TIER_CLS[t]}`}>{t}</span>{TIER_LABEL[t]} estimate</div>
                        <div className="mt-1 text-sm">{lib.rates_locked ? "—" : info ? <>avg <b>₹{info.rate.toLocaleString("en-IN")}</b> <span className="text-xs text-slate-500">({info.names.join(", ")})</span></> : <span className="text-xs text-slate-500">Tag {t} brands and enter their rates</span>}</div>
                      </div>
                    );
                  })}
                </div>
              ) : <p className="mt-2 text-xs text-slate-500">For specifications, BOQ notes and your price list – this material is not a separate estimate item.</p>}
            </div>

            {!brands.length ? <Empty text="No brands yet – add one." /> : brands.map((b) => {
              const vs = lib.variants.filter((v) => v.brand_id === b.id);
              const isOpen = open[b.id] ?? false;
              return (
                <div key={b.id} className="card overflow-hidden">
                  <div className="flex flex-wrap items-center gap-2 px-4 py-3">
                    <button className="flex min-w-0 flex-1 items-center gap-2 text-left" onClick={() => setOpen({ ...open, [b.id]: !isOpen })}>
                      {isOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                      <span className="truncate text-[15px] font-bold text-navy-ink">{b.name}</span>
                      {b.is_default && <Badge color="green">Default</Badge>}
                      <span className="text-xs text-slate-500">{vs.length} variant{vs.length === 1 ? "" : "s"}</span>
                      {vs.some((v) => chosenIds.has(v.id)) && <Badge color="amber">In project</Badge>}
                    </button>
                    <div className="flex items-center gap-1" title="A = Premium · B = Standard · C = Basic">
                      {(["A", "B", "C", ""] as const).map((t) => (
                        <button key={t || "none"} disabled={!isOwner} onClick={() => saveBrand(b, { tier: t })}
                          className={`h-7 min-w-7 rounded-md px-1.5 text-xs font-bold ${b.tier === t ? TIER_CLS[t] : "bg-slate-50 text-slate-400 hover:bg-slate-100"} disabled:cursor-default`}>{t || "–"}</button>
                      ))}
                    </div>
                    {isOwner && <button className={`btn-sm ${b.is_default ? "btn-primary" : "btn-ghost"}`} title="Default brand for new projects" onClick={() => saveBrand(b, { is_default: !b.is_default })}><Star size={13} /></button>}
                    {isOwner && <button className="btn-ghost btn-sm" onClick={() => { setAddVar(b); setOpen({ ...open, [b.id]: true }); }}><Plus size={13} />Variant</button>}
                    <OwnerDelete entity="market_brand" id={b.id} title={`${b.name} (${c.name})`} onDone={load} />
                  </div>
                  {isOpen && <div className="border-t border-line">{vs.length ? table(vs) : <p className="px-4 py-3 text-sm text-slate-500">No variants yet.</p>}</div>}
                </div>
              );
            })}
            <p className="text-[11px] text-slate-500">Rates are yours: enter them from your dealer’s price. Tag each brand A / B / C once – Premium estimates use the average of your A brands, Standard the B brands, Basic the C brands. “Use in project” fixes a brand for this project only.</p>
          </div>
        </div>
      )}

      <BrandModal open={addBrand} onClose={() => setAddBrand(false)} cats={lib.categories} cat={cat} onSaved={load} />
      <VariantModal brand={addVar} unit={addVar ? catByKey.get(addVar.category)?.unit || "" : ""} onClose={() => setAddVar(null)} onSaved={load} />
      <ImportModal open={importOpen} onClose={() => setImportOpen(false)} onDone={load} />
    </Page>
  );
}

function RateInput({ value, onSave }: { value: number | null; onSave: (v: number | null) => void }) {
  const [v, setV] = useState(value == null ? "" : String(value));
  useEffect(() => setV(value == null ? "" : String(value)), [value]);
  return (
    <input className="w-24 rounded-md border border-line bg-white px-2 py-1 text-right text-[13px] focus:border-brand-500 focus:outline-none" placeholder="₹ rate"
      value={v} inputMode="decimal" onChange={(e) => setV(e.target.value)}
      onBlur={() => { const n = v.trim() === "" ? null : Number(v); if (n !== null && (isNaN(n) || n < 0)) { setV(value == null ? "" : String(value)); return; } if (n !== value) onSave(n); }}
      onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />
  );
}

function BrandModal({ open, onClose, cats, cat, onSaved }: { open: boolean; onClose: () => void; cats: Category[]; cat: string; onSaved: () => void }) {
  const [f, setF] = useState({ category: cat, name: "", tier: "" });
  useEffect(() => { if (open) setF({ category: cat, name: "", tier: "" }); }, [open, cat]);
  const save = async () => {
    try { await api("/api/market/brands", { body: f }); toast(`${f.name} added`); onSaved(); onClose(); } catch (e: any) { toast(e.message, "err"); }
  };
  return (
    <Modal open={open} onClose={onClose} title="Add a brand">
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-xs"><span className="label">Material</span>
          <select className="input" value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>{cats.map((c) => <option key={c.key} value={c.key}>{c.stage} · {c.name}</option>)}</select></label>
        <label className="text-xs"><span className="label">Brand name *</span><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="e.g. Chettinad" /></label>
        <label className="text-xs"><span className="label">Grade</span>
          <select className="input" value={f.tier} onChange={(e) => setF({ ...f, tier: e.target.value })}><option value="">Not graded</option><option value="A">A – Premium</option><option value="B">B – Standard</option><option value="C">C – Basic</option></select></label>
      </div>
      <div className="mt-4 flex justify-end gap-2"><button className="btn-ghost" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={!f.name.trim()} onClick={save}>Add brand</button></div>
    </Modal>
  );
}

function VariantModal({ brand, unit, onClose, onSaved }: { brand: Brand | null; unit: string; onClose: () => void; onSaved: () => void }) {
  const blank = { name: "", code: "", color: "", unit: "", rate: "", gst_pct: "" };
  const [f, setF] = useState(blank);
  useEffect(() => { if (brand) setF({ ...blank, unit }); }, [brand]);  // eslint-disable-line react-hooks/exhaustive-deps
  const save = async () => {
    if (!brand) return;
    try {
      await api("/api/market/variants", { body: { brand_id: brand.id, name: f.name, code: f.code, color: f.color, unit: f.unit, spec: {},
        rate: f.rate === "" ? null : Number(f.rate), gst_pct: f.gst_pct === "" ? null : Number(f.gst_pct) } });
      toast(`${f.name} added to ${brand.name}`); onSaved(); onClose();
    } catch (e: any) { toast(e.message, "err"); }
  };
  const isColour = !!brand && /paint|enamel|tiles|granite/.test(brand.category);
  return (
    <Modal open={!!brand} onClose={onClose} title={`Add a variant – ${brand?.name || ""}`}>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="text-xs sm:col-span-2"><span className="label">Name *</span><input className="input" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="e.g. PPC / Fe 550D / 600x600 GVT / shade name" /></label>
        <label className="text-xs"><span className="label">Code (shade / product)</span><input className="input" value={f.code} onChange={(e) => setF({ ...f, code: e.target.value })} /></label>
        {isColour && <label className="text-xs"><span className="label">Colour (for 3D – the code alone cannot tell the colour)</span>
          <div className="flex gap-2"><input type="color" className="h-9 w-12 rounded border border-line" value={f.color || "#dddddd"} onChange={(e) => setF({ ...f, color: e.target.value })} /><input className="input" value={f.color} onChange={(e) => setF({ ...f, color: e.target.value })} placeholder="#efe3cf" /></div></label>}
        <label className="text-xs"><span className="label">Unit</span><input className="input" value={f.unit} onChange={(e) => setF({ ...f, unit: e.target.value })} /></label>
        <label className="text-xs"><span className="label">Your rate (₹)</span><input className="input" inputMode="decimal" value={f.rate} onChange={(e) => setF({ ...f, rate: e.target.value })} /></label>
        <label className="text-xs"><span className="label">GST %</span><input className="input" inputMode="decimal" value={f.gst_pct} onChange={(e) => setF({ ...f, gst_pct: e.target.value })} /></label>
      </div>
      <div className="mt-4 flex justify-end gap-2"><button className="btn-ghost" onClick={onClose}>Cancel</button><button className="btn-primary" disabled={!f.name.trim()} onClick={save}>Add</button></div>
    </Modal>
  );
}

function ImportModal({ open, onClose, onDone }: { open: boolean; onClose: () => void; onDone: () => void }) {
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<any>(null);
  const go = async (file: File) => {
    setBusy(true); setRes(null);
    try { const fd = new FormData(); fd.append("file", file); const r = await api("/api/market/import", { form: fd }); setRes(r); onDone(); }
    catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  return (
    <Modal open={open} onClose={() => { setRes(null); onClose(); }} title="Import a brand list (Excel / CSV)">
      <ol className="list-decimal space-y-1 pl-5 text-sm text-slate-600">
        <li>Download the <b>Template</b> (top right). Columns: category, brand, name, code, colour, unit, rate, gst_pct.</li>
        <li>Fill it from the dealer’s shade card / price list – e.g. Asian Paints shade codes with their colour (#hex).</li>
        <li>Upload it here. Same brand + code updates the row; new rows are added. Nothing is deleted.</li>
      </ol>
      <label className="mt-3 flex cursor-pointer flex-col items-center gap-2 rounded-xl border-2 border-dashed border-brand-100 bg-brand-50/40 px-4 py-6 text-center text-sm hover:bg-brand-50">
        <FileUp size={26} className="text-brand-600" />{busy ? "Reading…" : "Choose the .xlsx / .csv file"}
        <input type="file" hidden accept=".csv,.xlsx" onChange={(e) => { const f = e.target.files?.[0]; if (f) go(f); e.target.value = ""; }} />
      </label>
      {res && <div className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{res.added} added · {res.updated} updated · {res.added_brands} new brands
        {res.skipped?.length > 0 && <ul className="mt-1 list-disc pl-5 text-xs text-amber-800">{res.skipped.map((s: string) => <li key={s}>{s}</li>)}</ul>}</div>}
    </Modal>
  );
}
