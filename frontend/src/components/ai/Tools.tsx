import { useEffect, useState, type ReactNode } from "react";
import {
  BookOpen, Calculator, ChevronDown, ChevronRight, FileUp, HardHat, Library, Loader2, RefreshCw, Search, Send, Upload, Wand2,
} from "lucide-react";
import { Badge, Card, Empty, toast } from "../ui";
import { api, fmtBytes, fmtDateTime, rupees } from "../../lib/api";
import { CalcCard } from "./Cards";
import type { CalcCardT, Meta, SendOpts } from "./types";

type Go = (o: SendOpts) => void;

function AskBox({ placeholder, onAsk, label = "Ask" }: { placeholder: string; onAsk: (q: string) => void; label?: string }) {
  const [q, setQ] = useState("");
  return (
    <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); if (q.trim()) { onAsk(q.trim()); setQ(""); } }}>
      <input className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder={placeholder} />
      <button className="btn-primary shrink-0" disabled={!q.trim()}><Send size={16} />{label}</button>
    </form>
  );
}

// ---------------------------------------------------------------- Drawing Analysis
export function DrawingTab({ pid, go }: { pid: number | null; go: Go }) {
  const [files, setFiles] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (pid) api<any[]>(`/api/files/project/${pid}?category=drawing`).then((f) => setFiles(f.filter((x) => /\.(dxf|pdf|png|jpe?g|webp)$/i.test(x.name)))).catch(() => setFiles([]));
  }, [pid]);
  const upload = async (f: File) => {
    setBusy(true);
    try {
      const fd = new FormData();
      if (pid) fd.append("project_id", String(pid));
      fd.append("file", f);
      const r = await api<any>("/api/ai/upload", { form: fd });
      go({ text: "Analyse this drawing – list the rooms and sizes", attachment: { id: r.id, name: r.name }, agent: "drawing" });
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  return (
    <Card title="Drawing Analysis" icon={<FileUp size={19} className="text-violet-600" />}>
      <p className="mb-3 text-sm text-slate-600">Upload a floor plan – <b>DXF</b> (best), vector <b>PDF</b> or a <b>photo / scan</b>. Nexora reads rooms, sizes, scale and the north arrow, then you can check Vastu, estimate the cost or save it as a design.</p>
      <label className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-brand-100 bg-brand-50/40 p-8 text-center ${busy ? "opacity-60" : "hover:border-brand-600"}`}>
        {busy ? <Loader2 className="animate-spin text-brand-600" /> : <Upload className="text-brand-600" />}
        <span className="text-sm font-semibold text-navy-ink">{busy ? "Uploading…" : "Choose a drawing (DXF / PDF / JPG / PNG)"}</span>
        <span className="text-xs text-slate-500">DWG? Save it as DXF 2018 first.</span>
        <input type="file" hidden accept=".dxf,.pdf,.png,.jpg,.jpeg,.webp" disabled={busy} onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
      </label>
      {files.length > 0 && (
        <div className="mt-4">
          <div className="mb-1.5 text-xs font-bold text-navy-ink">Drawings already in this project</div>
          <ul className="divide-y divide-line rounded-lg border border-line">
            {files.slice(0, 8).map((f) => (
              <li key={f.id} className="flex items-center gap-2 px-3 py-2 text-sm">
                <span className="min-w-0 flex-1 truncate">{f.name} <span className="text-xs text-slate-400">v{f.version} · {fmtDateTime(f.created_at)}</span></span>
                <button className="btn-outline btn-sm" onClick={() => go({ text: "Analyse this drawing – list the rooms and sizes", attachment: { id: f.id, name: f.name }, agent: "drawing" })}>Analyse</button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------- Document Q&A
export function DocsTab({ pid, go }: { pid: number | null; go: Go }) {
  const [rows, setRows] = useState<any[] | null>(null);
  const [emb, setEmb] = useState(false);
  const [busy, setBusy] = useState(false);
  const load = () => pid && api<any>(`/api/ai/docs?project_id=${pid}`).then((r) => { setRows(r.files); setEmb(r.embeddings); }).catch((e) => toast(e.message, "err"));
  useEffect(() => { load(); /* eslint-disable-next-line */ }, [pid]);
  if (!pid) return <Card><Empty text="Choose a project first – Document Q&A answers from that project's documents." /></Card>;
  const index = async () => {
    setBusy(true);
    try { const r = await api<any>(`/api/ai/docs/index?project_id=${pid}`, { method: "POST" }); setRows(r.files); toast(`${r.indexed} document(s) ready`); }
    catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const upload = async (f: File) => {
    setBusy(true);
    try {
      const fd = new FormData(); fd.append("project_id", String(pid)); fd.append("file", f);
      await api("/api/ai/upload", { form: fd });
      const r = await api<any>(`/api/ai/docs/index?project_id=${pid}`, { method: "POST" }); setRows(r.files);
      toast("Document added");
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const tone: Record<string, string> = { indexed: "green", waiting: "amber", empty: "gray", failed: "red", not_text: "gray" };
  const label: Record<string, string> = { indexed: "Ready", waiting: "Not read yet", empty: "No text", failed: "Failed", not_text: "Picture / drawing" };
  return (
    <Card title="Document Q&A" icon={<BookOpen size={19} className="text-brand-600" />}
      action={<div className="flex gap-2">
        <label className="btn-outline btn-sm cursor-pointer"><Upload size={14} />Add document<input type="file" hidden accept=".pdf,.docx,.xlsx,.csv,.txt" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} /></label>
        <button className="btn-outline btn-sm" onClick={index} disabled={busy}>{busy ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}Read new documents</button>
      </div>}>
      <p className="mb-3 text-sm text-slate-600">Ask questions about your contract, specification, soil report, BOQ or any PDF / Word / Excel file in this project. Answers quote the document and page. {emb ? "Meaning-based search is on (Gemini embeddings)." : "Keyword search (add GEMINI_API_KEY for meaning-based search)."}</p>
      <AskBox placeholder="e.g. What grade of steel does the specification ask for?" onAsk={(q) => go({ text: q, form: { tool: "docs", args: { query: q } }, agent: "general" })} />
      <div className="mt-4 overflow-x-auto rounded-lg border border-line">
        <table className="w-full min-w-[520px]">
          <thead><tr><th className="table-th">Document</th><th className="table-th">Size</th><th className="table-th">Status</th><th className="table-th text-right">Parts</th></tr></thead>
          <tbody>
            {(rows || []).map((r) => (
              <tr key={r.file_id}>
                <td className="table-td"><div className="font-medium text-navy-ink">{r.name}</div>{r.error && <div className="text-[11px] text-slate-500">{r.error}</div>}</td>
                <td className="table-td">{fmtBytes(r.size_bytes)}</td>
                <td className="table-td"><Badge color={tone[r.status] || "gray"}>{label[r.status] || r.status}</Badge>{r.embedded && <span className="ml-1 text-[10px] text-emerald-700">+ meaning</span>}</td>
                <td className="table-td text-right">{r.chunks || "–"}</td>
              </tr>
            ))}
            {rows && !rows.length && <tr><td className="table-td text-center text-slate-500" colSpan={4}>No documents yet – add one above or in Projects → Docs.</td></tr>}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

// ---------------------------------------------------------------- Quantity Calculator
export function QtyTab({ meta, go }: { meta: Meta | null; go: Go }) {
  const [kind, setKind] = useState("concrete");
  const [vals, setVals] = useState<Record<string, string>>({});
  const [unit, setUnit] = useState("ft");
  const [res, setRes] = useState<CalcCardT | null>(null);
  const [busy, setBusy] = useState(false);
  const calc = meta?.calculators.find((c) => c.key === kind);
  const params = () => ({ ...Object.fromEntries(Object.entries(vals).filter(([, v]) => v !== "").map(([k, v]) => [k, isNaN(Number(v)) ? v : Number(v)])), unit });
  const run = async () => {
    setBusy(true);
    try {
      const r = await api<CalcCardT>("/api/ai/calc", { body: { kind, params: params() } });
      if (r.missing.length) { toast(`Please give: ${r.missing.join(", ")}`, "err"); setRes(null); } else setRes({ ...r, type: "calc" });
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  if (!meta) return <Card><p className="text-sm text-slate-500">Loading…</p></Card>;
  return (
    <div className="grid gap-4 lg:grid-cols-[260px_1fr]">
      <Card title="Calculators" icon={<Calculator size={19} className="text-emerald-600" />} bodyClass="px-3 pb-3">
        <div className="space-y-1">
          {meta.calculators.map((c) => (
            <button key={c.key} onClick={() => { setKind(c.key); setVals({}); setRes(null); }}
              className={`w-full rounded-lg px-3 py-2 text-left text-sm ${kind === c.key ? "bg-brand-600 text-white" : "text-navy-ink hover:bg-slate-50"}`}>
              <div className="font-semibold">{c.name}</div><div className={`text-[11px] ${kind === c.key ? "text-blue-100" : "text-slate-500"}`}>{c.name_ta}</div>
            </button>
          ))}
        </div>
      </Card>
      <div className="min-w-0 space-y-4">
        <Card title={calc?.name} icon={<Calculator size={19} className="text-brand-600" />}>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {calc?.params.map((f) => (
              <label key={f.key} className="text-xs"><span className="label">{f.label}{f.length ? ` (${unit})` : ""}</span>
                {f.type === "select" ? (
                  <select className="input" value={vals[f.key] ?? ""} onChange={(e) => setVals({ ...vals, [f.key]: e.target.value })}>
                    <option value="">Default</option>{(f.options || []).map((o) => <option key={o}>{o}</option>)}
                  </select>
                ) : <input className="input" inputMode="decimal" value={vals[f.key] ?? ""} onChange={(e) => setVals({ ...vals, [f.key]: e.target.value.replace(/[^0-9.]/g, "") })} />}
              </label>
            ))}
            {calc?.params.some((f) => f.length) && (
              <label className="text-xs"><span className="label">Length unit</span>
                <select className="input" value={unit} onChange={(e) => setUnit(e.target.value)}><option value="ft">feet</option><option value="m">metres</option></select></label>
            )}
          </div>
          <div className="mt-4 flex flex-wrap justify-end gap-2">
            <button className="btn-outline" disabled={!res} onClick={() => go({ form: { tool: "calc", kind, params: params(), label: `${calc?.name}: explain this` }, agent: "quantity" })}><Send size={15} />Explain in chat</button>
            <button className="btn-primary" onClick={run} disabled={busy}>{busy ? <Loader2 size={16} className="animate-spin" /> : <Calculator size={16} />}Calculate</button>
          </div>
        </Card>
        {res && <Card><CalcCard card={res} /></Card>}
        <Card title="Whole-house quantities & cost" icon={<Wand2 size={19} className="text-amber-500" />}>
          <p className="mb-3 text-sm text-slate-600">For a complete BOQ, give the built-up area or the plot size – Nexora asks for anything missing (floors, bedrooms, toilets) instead of guessing.</p>
          <AskBox placeholder="e.g. 1200 sq ft per floor, G+1, 3 bedrooms, 3 toilets – cost and materials?" onAsk={(q) => go({ text: q, agent: "quantity" })} />
        </Card>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------- Design Suggestions
export function DesignTab({ project, go }: { project: any; go: Go }) {
  const toFt = project?.unit === "m" ? 3.28084 : 1;
  const [f, setF] = useState<Record<string, any>>({
    plot_w_ft: project?.plot_width ? Math.round(project.plot_width * toFt * 100) / 100 : "", plot_d_ft: project?.plot_length ? Math.round(project.plot_length * toFt * 100) / 100 : "",
    facing: project?.facing || "", road_width_ft: project?.road_width ? Math.round(project.road_width / 0.3048) : "", floors: "", bedrooms: "", toilets: "",
    parking_car: false, pooja: false, dining: true,
  });
  const set = (k: string, v: any) => setF({ ...f, [k]: v });
  const missing = ["plot_w_ft", "plot_d_ft", "facing", "road_width_ft", "floors", "bedrooms"].filter((k) => f[k] === "" || f[k] == null);
  const submit = () => {
    const a: Record<string, any> = {};
    Object.entries(f).forEach(([k, v]) => { if (v !== "" && v !== false) a[k] = typeof v === "string" && !isNaN(Number(v)) ? Number(v) : v; });
    go({ form: { tool: "plan", answers: a, label: `Plan: ${f.plot_w_ft}×${f.plot_d_ft} ft, ${f.facing} facing, ${f.bedrooms} bedrooms, ${["", "G", "G+1", "G+2", "G+3"][Number(f.floors)] || ""}` }, agent: "design" });
  };
  const num = (k: string, l: string) => <label className="text-xs"><span className="label">{l}</span><input className="input" inputMode="decimal" value={f[k]} onChange={(e) => set(k, e.target.value.replace(/[^0-9.]/g, ""))} /></label>;
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <Card title="Generate a floor plan" icon={<Wand2 size={19} className="text-amber-500" />}>
        <div className="grid gap-3 sm:grid-cols-2">
          {num("plot_w_ft", "Plot frontage (ft)")}{num("plot_d_ft", "Plot depth (ft)")}
          <label className="text-xs"><span className="label">Road side (facing)</span>
            <select className="input" value={f.facing} onChange={(e) => set("facing", e.target.value)}><option value="">—</option>{["east", "west", "north", "south", "north-east", "north-west", "south-east", "south-west"].map((x) => <option key={x}>{x}</option>)}</select></label>
          {num("road_width_ft", "Road width (ft)")}
          <label className="text-xs"><span className="label">Floors</span>
            <select className="input" value={f.floors} onChange={(e) => set("floors", e.target.value)}><option value="">—</option><option value="1">G only</option><option value="2">G+1</option><option value="3">G+2</option><option value="4">G+3</option></select></label>
          {num("bedrooms", "Bedrooms (total)")}{num("toilets", "Toilets (optional)")}
          <div className="flex flex-wrap items-end gap-3 text-sm">
            {[["parking_car", "Car parking"], ["pooja", "Pooja room"], ["dining", "Dining"]].map(([k, l]) => (
              <label key={k} className="inline-flex items-center gap-1.5"><input type="checkbox" checked={!!f[k]} onChange={(e) => set(k, e.target.checked)} />{l}</label>
            ))}
          </div>
        </div>
        <p className="mt-3 text-xs text-slate-500">Tamil Nadu setbacks (TNCDBR 2019) are applied automatically. If the rooms don't fit, you get options to choose from.</p>
        <div className="mt-3 flex justify-end"><button className="btn-primary" disabled={missing.length > 0} onClick={submit}><Wand2 size={16} />Generate plan + quantities</button></div>
        {missing.length > 0 && <p className="mt-1 text-right text-[11px] text-slate-400">Fill all fields to continue</p>}
      </Card>
      <Card title="Or just describe it" icon={<Send size={18} className="text-brand-600" />}>
        <p className="mb-3 text-sm text-slate-600">Type it the way you'd say it – English, தமிழ் or Tanglish. Example: <i>"30x40 east facing 2BHK, car parking, G+1, 30 ft road"</i>.</p>
        <AskBox placeholder="Describe the house you want…" onAsk={(q) => go({ text: q, agent: "design" })} label="Design" />
        <div className="mt-4 space-y-2 text-sm">
          {["What room sizes are good for a 3BHK?", "How to plan cross ventilation in a 30x40 house?", "Setback for 30x50 plot, 40 ft road, G+2"].map((x) => (
            <button key={x} onClick={() => go({ text: x, agent: "design" })} className="flex w-full items-center justify-between rounded-lg border border-line px-3 py-2 text-left text-navy-ink hover:border-brand-600">{x}<ChevronRight size={15} className="text-slate-400" /></button>
          ))}
        </div>
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------- knowledge lists (Site Troubleshooting / Code & Standards)
function KbList({ category, go, agent, intro, icon, title, extra }: { category: string; go: Go; agent: string; intro: string; icon: ReactNode; title: string; extra?: ReactNode }) {
  const [rows, setRows] = useState<any[]>([]);
  const [q, setQ] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => {
    const id = setTimeout(() => api<any[]>(`/api/ai/kb?category=${category}&q=${encodeURIComponent(q)}`).then(setRows).catch(() => setRows([])), q ? 250 : 0);
    return () => clearTimeout(id);
  }, [q, category]);
  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
      <Card title={title} icon={icon} action={<div className="relative w-56 max-w-[45vw]"><Search size={15} className="absolute left-2.5 top-2.5 text-slate-400" /><input className="input pl-8" placeholder="Search" value={q} onChange={(e) => setQ(e.target.value)} /></div>}>
        <p className="mb-3 text-sm text-slate-600">{intro}</p>
        <div className="space-y-2">
          {rows.map((r) => (
            <div key={r.id} className="rounded-xl border border-line">
              <button className="flex w-full items-start gap-2 px-3 py-2.5 text-left" onClick={() => setOpen(open === r.id ? null : r.id)}>
                {open === r.id ? <ChevronDown size={16} className="mt-0.5 text-brand-600" /> : <ChevronRight size={16} className="mt-0.5 text-slate-400" />}
                <span className="min-w-0 flex-1"><span className="block text-sm font-semibold text-navy-ink">{r.title}</span><span className="text-xs text-slate-500">{r.title_ta} · {r.source}</span></span>
              </button>
              {open === r.id && (
                <div className="border-t border-line px-4 py-3 text-[13px] leading-relaxed text-slate-700">
                  {r.text}
                  <div className="mt-2"><button className="link text-xs" onClick={() => go({ text: `Explain: ${r.title}`, agent })}>Ask the assistant about this →</button></div>
                </div>
              )}
            </div>
          ))}
          {!rows.length && <p className="text-sm text-slate-500">Nothing found – ask the assistant on the right.</p>}
        </div>
      </Card>
      <div className="space-y-4">
        <Card title="Ask your question">
          <AskBox placeholder="Type your question…" onAsk={(x) => go({ text: x, agent })} />
          <p className="mt-2 text-xs text-slate-500">Answers cite the sources used. Structural decisions must be confirmed by a qualified engineer.</p>
        </Card>
        {extra}
      </div>
    </div>
  );
}

export function SiteTab({ go, pid }: { go: Go; pid: number | null }) {
  return <KbList category="site" agent="site" go={go} title="Site Troubleshooting" icon={<HardHat size={19} className="text-amber-500" />}
    intro="Common site problems with causes, step-by-step fixes and when an engineer must check. Describe your own problem on the right – you can attach a site photo in the chat."
    extra={pid ? <Card title="This project's site"><button className="btn-outline w-full" onClick={() => go({ form: { tool: "site", label: "How is my site doing today?" }, agent: "site" })}><HardHat size={16} />Today's site status & advice</button></Card> : undefined} />;
}

export function CodeTab({ go }: { go: Go }) {
  return <KbList category="code" agent="code" go={go} title="Code & Standards" icon={<BookOpen size={19} className="text-brand-600" />}
    intro="IS 456, IS 1786, IS 13920, NBC 2016, TNCDBR 2019 and more – the key rules a house builder needs, with the clause references." />;
}

// ---------------------------------------------------------------- Material Guide
export function MaterialTab({ meta, go }: { meta: Meta | null; go: Go }) {
  const [sel, setSel] = useState("cement");
  if (!meta) return <Card><p className="text-sm text-slate-500">Loading…</p></Card>;
  const g = meta.material_guide.find((x) => x.key === sel) || meta.material_guide[0];
  return (
    <div className="space-y-4">
      <div className="no-scrollbar flex gap-2 overflow-x-auto pb-1">
        {meta.material_guide.map((m) => (
          <button key={m.key} onClick={() => setSel(m.key)} className={`pill-tab ${sel === m.key ? "pill-tab-active" : ""}`}>{m.name}<span className={`text-[11px] ${sel === m.key ? "text-blue-100" : "text-slate-400"}`}>{m.name_ta}</span></button>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-[1fr_320px]">
        <Card title={`${g.name} – types & where to use`} icon={<Library size={19} className="text-emerald-600" />}>
          <div className="overflow-x-auto rounded-lg border border-line">
            <table className="w-full min-w-[640px]">
              <thead><tr><th className="table-th">Type</th><th className="table-th">Standard</th><th className="table-th">Use for</th><th className="table-th">Good</th><th className="table-th">Watch out</th></tr></thead>
              <tbody>{g.items.map((i) => <tr key={i.name}><td className="table-td font-semibold text-navy-ink">{i.name}</td><td className="table-td whitespace-nowrap">{i.standard}</td><td className="table-td">{i.use}</td><td className="table-td text-emerald-700">{i.pros}</td><td className="table-td text-amber-800">{i.cons}</td></tr>)}</tbody>
            </table>
          </div>
          <div className="mt-3 space-y-1 text-[13px] text-slate-700">{g.tips.map((t) => <div key={t}>• {t}</div>)}</div>
        </Card>
        <div className="space-y-4">
          {g.rate && (
            <Card title={`Current rate (${meta.rates_state})`}>
              <div className="text-xs text-slate-500">{g.rate.name}</div>
              <div className="mt-2 grid grid-cols-3 gap-2 text-center">
                {(["basic", "standard", "premium"] as const).map((k) => <div key={k} className="rounded-lg bg-slate-50 p-2"><div className="text-[11px] capitalize text-slate-500">{k}</div><div className="font-bold text-navy-ink">{rupees(g.rate[k])}</div><div className="text-[10px] text-slate-400">per {g.rate.unit}</div></div>)}
              </div>
              <p className="mt-2 text-[11px] text-slate-400">From your rate library (Estimate → Rates). Update it there for your town.</p>
            </Card>
          )}
          <Card title="Ask the Material Expert">
            <AskBox placeholder={`e.g. Which ${g.name.toLowerCase()} for a coastal house?`} onAsk={(q) => go({ text: q, agent: "material" })} />
            <div className="mt-3 space-y-1.5">
              {[`${g.name}: how to check quality at site?`, `Compare the ${g.name.toLowerCase()} types for my house`].map((x) => (
                <button key={x} onClick={() => go({ text: x, agent: "material" })} className="flex w-full items-center justify-between rounded-lg border border-line px-3 py-2 text-left text-xs text-navy-ink hover:border-brand-600">{x}<ChevronRight size={14} className="text-slate-400" /></button>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  );
}
