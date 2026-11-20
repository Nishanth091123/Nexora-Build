import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Download, FileSpreadsheet, FileText, Lightbulb, Droplets, Paintbrush, Save, Sparkles } from "lucide-react";
import Page from "../components/Page";
import { Badge, Card, Empty, PillTabs, toast } from "../components/ui";
import { api, downloadFile, inr } from "../lib/api";
import { useAuth } from "../lib/auth";

type Rate = { key: string; label: string; unit: string; low: number; default: number; high: number; source: string; rate: number; edited: boolean; on: boolean };
type Item = { id: string; floor: string; room: string; key: string; item: string; unit: string; qty: number; auto_qty: number; rate: number; amount: number; note: string };
type Loose = { item: string; qty: number; rate: number | null; amount: number | null };
type Interior = { items: Item[]; loose: Loose[]; rates: Rate[]; totals: { searched_items: number; loose_entered: number; grand: number; by_floor: Record<string, number> };
  checked: string; notes: string[]; saved: any };
type Mep = { electrical: any; plumbing: any };
type Tab = "interior" | "electrical" | "plumbing";
const OPTIONAL = ["ceiling_cove", "fluted_panel", "study_table"];

export default function InteriorPage() {
  const { currentProject } = useAuth();
  const nav = useNavigate();
  const pid = currentProject?.id;
  const [tab, setTab] = useState<Tab>("interior");
  const [data, setData] = useState<Interior | null>(null);
  const [mep, setMep] = useState<Mep | null>(null);
  const [err, setErr] = useState("");
  const [rates, setRates] = useState<Record<string, string>>({});
  const [qty, setQty] = useState<Record<string, string>>({});
  const [loose, setLoose] = useState<Record<string, string>>({});
  const [on, setOn] = useState<string[]>([]);
  const [off, setOff] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);

  const apply = (d: Interior) => {
    setData(d);
    const s = d.saved || {};
    setRates(Object.fromEntries(Object.entries(s.rates || {}).map(([k, v]) => [k, String(v)])));
    setQty(Object.fromEntries(Object.entries(s.qty || {}).map(([k, v]) => [k, String(v)])));
    setLoose(Object.fromEntries(Object.entries(s.loose_rates || {}).map(([k, v]) => [k, String(v)])));
    setOn(s.on || []); setOff(s.off || []);
  };
  const load = useCallback(async () => {
    if (!pid) return;
    setErr("");
    try {
      apply(await api<Interior>(`/api/projects/${pid}/interior`));
      setMep(await api<Mep>(`/api/projects/${pid}/mep`));
    } catch (e: any) { setErr(e.message || "Could not load"); setData(null); }
  }, [pid]);
  useEffect(() => { load(); }, [load]);

  const num = (v: string) => (v.trim() === "" ? null : Number(v));
  const save = async () => {
    if (!pid) return;
    setBusy(true);
    try {
      const body = {
        rates: Object.fromEntries(Object.entries(rates).map(([k, v]) => [k, num(v)])),
        qty: Object.fromEntries(Object.entries(qty).map(([k, v]) => [k, num(v)])),
        loose_rates: Object.fromEntries(Object.entries(loose).map(([k, v]) => [k, num(v)])),
        on, off,
      };
      apply(await api<Interior>(`/api/projects/${pid}/interior`, { method: "PUT", body }));
      toast("Saved");
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const dl = (path: string, name: string) => downloadFile(`/api/projects/${pid}/${path}`, `${currentProject?.code}_${name}`).catch((e) => toast(e.message, "err"));
  const toggle = (k: string, v: boolean) => {
    if (OPTIONAL.includes(k)) setOn(v ? [...on, k] : on.filter((x) => x !== k));
    else setOff(v ? off.filter((x) => x !== k) : [...off, k]);
  };

  if (!currentProject) return <Page title="Interior & Services" subtitle="Interior package, electrical and plumbing drawings"><Empty text="Create a project first (Projects page)." /></Page>;

  const Down = ({ items }: { items: [string, string, string, any][] }) => (
    <div className="flex flex-wrap gap-2">{items.map(([label, path, name, Icon]) => (
      <button key={label} className="btn-outline" onClick={() => dl(path, name)}><Icon size={16} />{label}</button>))}</div>
  );

  return (
    <Page title="Interior & Services" subtitle="Interior package with editable rates, electrical and plumbing drawings from the active drawing">
      <PillTabs tabs={[{ id: "interior", label: "Interior", icon: <Paintbrush size={16} /> }, { id: "electrical", label: "Electrical", icon: <Lightbulb size={16} /> },
        { id: "plumbing", label: "Plumbing", icon: <Droplets size={16} /> }]} value={tab} onChange={setTab} />
      {err && <Card title="Drawing needed"><p className="text-sm text-slate-600">{err}</p><button className="btn-primary mt-3" onClick={() => nav("/design")}>Open Design</button></Card>}

      {data && tab === "interior" && (<>
        <Card title="Interior estimate (suggested package)" icon={<Paintbrush size={20} />}
          action={<div className="flex gap-2"><button className="btn-primary" onClick={save} disabled={busy}><Save size={16} />{busy ? "Saving…" : "Save changes"}</button></div>}>
          <p className="mb-3 text-xs text-slate-500">Rates are <b>suggested default rates</b> from Tamil Nadu (Chennai / Coimbatore) public price pages, checked {data.checked}. Change any rate or quantity, then Save. The vendor's written quote is final.</p>
          <div className="mb-4 grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl bg-emerald-50 p-3"><div className="text-xs text-slate-500">Priced items</div><div className="text-xl font-bold">₹ {inr(data.totals.searched_items)}</div></div>
            <div className="rounded-xl bg-slate-50 p-3"><div className="text-xs text-slate-500">Loose furniture (your rates)</div><div className="text-xl font-bold">₹ {inr(data.totals.loose_entered)}</div></div>
            <div className="rounded-xl bg-brand-50 p-3"><div className="text-xs text-slate-500">Total</div><div className="text-xl font-bold">₹ {inr(data.totals.grand)}</div></div>
          </div>
          <div className="overflow-x-auto"><table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-slate-500"><th className="table-th">Use</th><th className="table-th">Item</th><th className="table-th">Unit</th><th className="table-th">Rate (₹) – default · low–high</th><th className="table-th">Where from</th></tr></thead>
            <tbody>{data.rates.map((r) => (
              <tr key={r.key} className="border-t border-line">
                <td className="table-td"><input type="checkbox" checked={r.on} onChange={(e) => toggle(r.key, e.target.checked)} /></td>
                <td className="table-td font-medium">{r.label}{OPTIONAL.includes(r.key) && <Badge color="blue">optional</Badge>}</td>
                <td className="table-td text-xs">{r.unit}</td>
                <td className="table-td"><input className="input w-28" inputMode="decimal" placeholder={String(r.default)} value={rates[r.key] ?? ""} onChange={(e) => setRates({ ...rates, [r.key]: e.target.value })} />
                  <div className="text-[11px] text-slate-500">suggested default {inr(r.default)} · seen {inr(r.low)}–{inr(r.high)}</div></td>
                <td className="table-td text-xs text-slate-500">{r.source}</td>
              </tr>))}</tbody></table></div>
        </Card>
        <Card title="Room-wise items" icon={<FileText size={20} />}>
          <div className="overflow-x-auto"><table className="w-full text-sm">
            <thead><tr className="text-left text-xs text-slate-500"><th className="table-th">Floor / room</th><th className="table-th">Item</th><th className="table-th">Qty</th><th className="table-th">Unit</th><th className="table-th text-right">Amount ₹</th></tr></thead>
            <tbody>{data.items.map((i) => (
              <tr key={i.id} className="border-t border-line">
                <td className="table-td">{i.floor} – {i.room}</td><td className="table-td">{i.item}<div className="text-[11px] text-slate-500">{i.note}</div></td>
                <td className="table-td"><input className="input w-20" inputMode="decimal" placeholder={String(i.auto_qty)} value={qty[i.id] ?? ""} onChange={(e) => setQty({ ...qty, [i.id]: e.target.value })} /></td>
                <td className="table-td text-xs">{i.unit}</td><td className="table-td text-right">{inr(i.amount)}</td></tr>))}</tbody></table></div>
        </Card>
        {data.loose.length > 0 && <Card title="Loose furniture and extras – type your rate (not priced by the app)" icon={<Sparkles size={20} />}>
          <div className="space-y-2">{data.loose.map((x) => (
            <div key={x.item} className="flex flex-wrap items-center gap-3 text-sm"><span className="min-w-[220px] flex-1">{x.item} × {x.qty}</span>
              <input className="input w-32" inputMode="decimal" placeholder="rate ₹" value={loose[x.item] ?? ""} onChange={(e) => setLoose({ ...loose, [x.item]: e.target.value })} />
              <span className="w-24 text-right">{x.amount != null ? inr(x.amount) : "–"}</span></div>))}</div>
        </Card>}
        <Card title="Download" icon={<Download size={20} />}>
          <Down items={[["Interior estimate (PDF)", "interior/pdf", "Interior_Estimate.pdf", FileText], ["Interior estimate (Excel, live formulas)", "interior/excel", "Interior_Estimate.xlsx", FileSpreadsheet]]} />
          <p className="mt-3 text-xs text-slate-500">Save your edits first – the download uses the saved rates and quantities.</p>
        </Card>
        <Card title="See it" icon={<Sparkles size={20} />}>
          <p className="text-sm text-slate-600">Furnished plan view, interior walk-through and the AI concept render are in Design → 3D. Pick a room style there, press <b>AI Render</b>; the picture is stamped “AI concept render – not to scale”.</p>
          <button className="btn-outline mt-3" onClick={() => nav("/design")}>Open Design → 3D</button>
        </Card>
      </>)}

      {data && mep && tab === "electrical" && (<>
        <Card title="Electrical layout" icon={<Lightbulb size={20} />}>
          <div className="mb-3 grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl bg-amber-50 p-3"><div className="text-xs text-slate-500">Connected load</div><div className="text-xl font-bold">{mep.electrical.connected_kw} kW</div></div>
            <div className="rounded-xl bg-slate-50 p-3"><div className="text-xs text-slate-500">After diversity</div><div className="text-xl font-bold">{mep.electrical.demand_kw} kW</div></div>
            <div className="rounded-xl bg-brand-50 p-3"><div className="text-xs text-slate-500">Supply (usual)</div><div className="text-xl font-bold capitalize">{mep.electrical.phase}</div></div>
          </div>
          <div className="mb-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">{Object.entries(mep.electrical.totals as Record<string, number>).map(([k, v]) => (
            <div key={k} className="rounded-lg bg-slate-50 px-3 py-2"><div className="text-slate-500">{mep.electrical.labels[k] || k}</div><div className="font-bold text-navy-ink">{v}</div></div>))}</div>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">{mep.electrical.notes.map((n: string, i: number) => <li key={i}>{n}</li>)}</ul>
          <div className="mt-4"><Down items={[["Electrical PDF", "mep/pdf?kind=electrical", "Electrical_Layout.pdf", FileText], ["Electrical DXF (AutoCAD)", "mep/dxf?kind=electrical", "Electrical_Layout.dxf", Download],
            ["Electrical + Plumbing PDF", "mep/pdf?kind=both", "Electrical_Plumbing_Layout.pdf", FileText]]} /></div>
        </Card>
      </>)}

      {data && mep && tab === "plumbing" && (<>
        <Card title="Plumbing layout" icon={<Droplets size={20} />}>
          <div className="mb-3 grid gap-3 sm:grid-cols-3">
            <div className="rounded-xl bg-sky-50 p-3"><div className="text-xs text-slate-500">Water per day</div><div className="text-xl font-bold">{inr(mep.plumbing.water.daily_l)} L</div></div>
            <div className="rounded-xl bg-slate-50 p-3"><div className="text-xs text-slate-500">Overhead tank</div><div className="text-xl font-bold">{inr(mep.plumbing.water.oht_l)} L</div></div>
            <div className="rounded-xl bg-brand-50 p-3"><div className="text-xs text-slate-500">Sump</div><div className="text-xl font-bold">{inr(mep.plumbing.water.sump_l)} L</div></div>
          </div>
          <div className="mb-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">{Object.entries(mep.plumbing.totals as Record<string, number>).map(([k, v]) => (
            <div key={k} className="rounded-lg bg-slate-50 px-3 py-2"><div className="text-slate-500">{mep.plumbing.labels[k] || k}</div><div className="font-bold text-navy-ink">{v}</div></div>))}</div>
          <ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">{mep.plumbing.notes.map((n: string, i: number) => <li key={i}>{n}</li>)}</ul>
          <div className="mt-4"><Down items={[["Plumbing PDF", "mep/pdf?kind=plumbing", "Plumbing_Layout.pdf", FileText], ["Plumbing DXF (AutoCAD)", "mep/dxf?kind=plumbing", "Plumbing_Layout.dxf", Download],
            ["Electrical + Plumbing PDF", "mep/pdf?kind=both", "Electrical_Plumbing_Layout.pdf", FileText]]} /></div>
        </Card>
      </>)}
    </Page>
  );
}
