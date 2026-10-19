import { useCallback, useEffect, useMemo, useState } from "react";
import { Copy, EyeOff, Eye, Library, Plus, Search } from "lucide-react";
import { api, inr } from "../lib/api";
import { useAuth } from "../lib/auth";
import { Badge, Card, Empty, Field, Modal, SegTabs, toast } from "./ui";
import { INDIAN_STATES } from "./ProjectBits";

export type Rate = {
  id: number; state: string; code: string; kind: string; category: string; name: string; unit: string;
  basic: number; standard: number; premium: number; note: string; is_custom: boolean; is_active: boolean;
};

const KIND_TABS = [
  { id: "material", label: "Material Rates" }, { id: "labour", label: "Labour Rates" },
  { id: "equipment", label: "Equipment Hire" }, { id: "extra", label: "Extras" },
];

function RateCell({ value, editable, onSave }: { value: number; editable: boolean; onSave: (v: number) => void }) {
  const [v, setV] = useState(String(value));
  useEffect(() => setV(String(value)), [value]);
  if (!editable) return <span>{inr(value)}</span>;
  return (
    <input className="w-24 rounded-md border border-transparent bg-transparent px-2 py-1 text-right text-[13px] hover:border-line focus:border-brand-500 focus:bg-white focus:outline-none"
      value={v} inputMode="decimal" onChange={(e) => setV(e.target.value)}
      onBlur={() => { const n = Number(v); if (!isNaN(n) && n >= 0 && n !== value) onSave(n); else setV(String(value)); }}
      onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }} />
  );
}

export default function RateLibrary({ defaultState = "Tamil Nadu" }: { defaultState?: string }) {
  const { user } = useAuth();
  const isOwner = user?.role === "owner";
  const [state, setState] = useState(defaultState);
  const [kind, setKind] = useState("material");
  const [q, setQ] = useState("");
  const [showHidden, setShowHidden] = useState(false);
  const [data, setData] = useState<{ rates_state: string; using_fallback: boolean; items: Rate[] } | null>(null);
  const [add, setAdd] = useState(false);
  const [form, setForm] = useState({ kind: "material", category: "Custom", name: "", unit: "nos", basic: "", standard: "", premium: "", note: "" });

  const load = useCallback(() => api(`/api/rates?state=${encodeURIComponent(state)}&include_hidden=${showHidden}`)
    .then(setData).catch((e) => toast(e.message, "err")), [state, showHidden]);
  useEffect(() => { load(); }, [load]);

  const rows = useMemo(() => (data?.items || []).filter((r) => r.kind === kind &&
    (!q || `${r.name} ${r.category} ${r.note}`.toLowerCase().includes(q.toLowerCase()))), [data, kind, q]);
  const editable = isOwner && !data?.using_fallback;

  const patch = async (r: Rate, body: Record<string, any>) => {
    try {
      const nr = await api<Rate>(`/api/rates/${r.id}`, { method: "PATCH", body });
      setData((d) => d ? { ...d, items: d.items.map((x) => (x.id === r.id ? nr : x)) } : d);
      toast("Rate saved");
    } catch (e: any) { toast(e.message, "err"); }
  };
  const copyState = async () => {
    try { await api("/api/rates/copy", { body: { from_state: "Tamil Nadu", to_state: state } }); toast(`Rates created for ${state}`); load(); }
    catch (e: any) { toast(e.message, "err"); }
  };
  const addRate = async () => {
    try {
      const n = (x: string) => Number(x || 0);
      await api("/api/rates", { body: { state, kind: form.kind, category: form.category, name: form.name, unit: form.unit,
        basic: n(form.basic), standard: n(form.standard || form.basic), premium: n(form.premium || form.standard || form.basic), note: form.note } });
      toast("Rate added"); setAdd(false); setKind(form.kind); load();
    } catch (e: any) { toast(e.message, "err"); }
  };

  return (
    <Card title="Material & Labour Rate Library" icon={<Library size={20} />}
      action={editable && <button className="btn-primary btn-sm" onClick={() => { setForm({ ...form, kind }); setAdd(true); }}><Plus size={14} />Add Rate</button>}>
      <div className="mb-3 flex flex-wrap items-end gap-3">
        <Field label="State" className="w-60">
          <select className="input" value={state} onChange={(e) => setState(e.target.value)}>
            {INDIAN_STATES.map((s) => <option key={s}>{s}</option>)}
          </select>
        </Field>
        <div className="relative min-w-[200px] flex-1"><Search size={16} className="absolute left-3 top-2.5 text-slate-400" />
          <input className="input pl-9" placeholder="Search rates..." value={q} onChange={(e) => setQ(e.target.value)} /></div>
        {isOwner && <label className="flex items-center gap-2 text-sm text-slate-600"><input type="checkbox" className="accent-brand-600" checked={showHidden} onChange={(e) => setShowHidden(e.target.checked)} />Show hidden</label>}
      </div>
      {data?.using_fallback && (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <span>No rates saved for <b>{state}</b> yet – showing <b>Tamil Nadu average</b> rates (used for estimates too).</span>
          {isOwner && <button className="btn-primary btn-sm" onClick={copyState}><Copy size={14} />Create {state} rates (copy TN)</button>}
        </div>
      )}
      <div className="mb-3"><SegTabs tabs={KIND_TABS} value={kind} onChange={setKind} /></div>
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full min-w-[720px]">
          <thead><tr>
            <th className="table-th">{kind === "labour" ? "Trade" : "Item"}</th><th className="table-th">Category</th><th className="table-th">Unit</th>
            {kind === "labour" || kind === "equipment" || kind === "extra"
              ? <th className="table-th text-right">{kind === "labour" ? "Day wage (₹)" : kind === "extra" ? "Value" : "Rate (₹)"}</th>
              : <><th className="table-th text-right">Basic (₹)</th><th className="table-th text-right">Standard (₹)</th><th className="table-th text-right">Premium (₹)</th></>}
            <th className="table-th">Note</th>{editable && <th className="table-th" />}
          </tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className={r.is_active ? "" : "opacity-50"}>
                <td className="table-td font-semibold text-navy-ink">{r.name} {r.is_custom && <Badge color="purple">custom</Badge>}</td>
                <td className="table-td">{r.category}</td><td className="table-td">{r.unit}</td>
                {kind === "material"
                  ? (["basic", "standard", "premium"] as const).map((k) => (
                    <td key={k} className="table-td text-right"><RateCell value={r[k]} editable={editable} onSave={(v) => patch(r, { [k]: v })} /></td>))
                  : <td className="table-td text-right"><RateCell value={r.standard} editable={editable} onSave={(v) => patch(r, { basic: v, standard: v, premium: v })} /></td>}
                <td className="table-td max-w-[280px] text-xs text-slate-500">{r.note}</td>
                {editable && <td className="table-td text-right">
                  <button className="btn-ghost btn-sm" title={r.is_active ? "Hide (not deleted)" : "Show again"} onClick={() => patch(r, { is_active: !r.is_active })}>
                    {r.is_active ? <EyeOff size={14} /> : <Eye size={14} />}</button></td>}
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && <div className="p-4"><Empty text="No rates in this list" /></div>}
      </div>
      <p className="mt-2 text-xs text-slate-500">
        Default values are approximate Tamil Nadu averages – edit them to your local market. {isOwner ? "Click a rate to edit; it saves when you leave the box." : "Only the owner can edit rates."} Spec level changes only material quality/brand – never quantities.
      </p>

      <Modal open={add} onClose={() => setAdd(false)} title={`Add rate – ${state}`}>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Type"><select className="input" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}>{KIND_TABS.slice(0, 3).map((k) => <option key={k.id} value={k.id}>{k.label}</option>)}</select></Field>
          <Field label="Category"><input className="input" value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} /></Field>
          <Field label="Name" className="sm:col-span-2"><input className="input" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder={form.kind === "labour" ? "Fabricator helper" : "Weathering course tiles"} /></Field>
          <Field label="Unit"><input className="input" value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} placeholder="nos / m2 / m3 / kg / day" /></Field>
          {form.kind === "material" ? (
            <>
              <Field label="Basic ₹"><input className="input" inputMode="decimal" value={form.basic} onChange={(e) => setForm({ ...form, basic: e.target.value })} /></Field>
              <Field label="Standard ₹"><input className="input" inputMode="decimal" value={form.standard} onChange={(e) => setForm({ ...form, standard: e.target.value })} /></Field>
              <Field label="Premium ₹"><input className="input" inputMode="decimal" value={form.premium} onChange={(e) => setForm({ ...form, premium: e.target.value })} /></Field>
            </>
          ) : <Field label={form.kind === "labour" ? "Day wage ₹" : "Rate ₹"}><input className="input" inputMode="decimal" value={form.basic} onChange={(e) => setForm({ ...form, basic: e.target.value })} /></Field>}
          <Field label="Note" className="sm:col-span-2"><input className="input" value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></Field>
        </div>
        <p className="mt-3 text-xs text-slate-500">Custom items can be added to an estimate under "Additional items".</p>
        <div className="mt-4 flex justify-end gap-2"><button className="btn-ghost" onClick={() => setAdd(false)}>Cancel</button><button className="btn-primary" onClick={addRate} disabled={!form.name || !form.unit}>Add</button></div>
      </Modal>
    </Card>
  );
}
