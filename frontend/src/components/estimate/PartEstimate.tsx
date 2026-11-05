import { useEffect, useState } from "react";
import { Download, FileSpreadsheet, FileText, Puzzle } from "lucide-react";
import { Card, Empty, toast } from "../ui";
import { api, downloadPost, num, rupees } from "../../lib/api";

/** 1.16: file name = project code + name + what it is, e.g. P-001_Kumar_House_Ground_Floor_Slab_Estimate.pdf */
export function fileStem(code: string, name: string, ...parts: string[]) {
  const clean = (x: string) => (x || "").replace(/[^A-Za-z0-9-]+/g, "_").replace(/_+/g, "_").replace(/^[_-]+|[_-]+$/g, "");
  return [code, name, ...parts].map(clean).filter(Boolean).join("_");
}

const TAB_FILE: Record<string, string> = {
  overview: "Overview", floorboq: "Floor-wise BOQ", takeoff: "Quantity Takeoff", material: "Material Estimate",
  cost: "Cost Analysis", boq: "BOQ", payment: "Payment Schedule", compare: "Spec Comparison",
};
export const DOWNLOAD_TABS = Object.keys(TAB_FILE);

/** Download bar shown under every Estimate tab (PDF / Excel of exactly that tab). Works unsaved (draft). */
export function TabDownload({ pid, tab, code, name, inputs, state, label }: {
  pid: number; tab: string; code: string; name: string; inputs: any; state: string; label: string;
}) {
  const [busy, setBusy] = useState("");
  const go = async (fmt: "pdf" | "excel") => {
    if (!inputs) return toast("Calculate the estimate first", "err");
    setBusy(fmt);
    try {
      await downloadPost(`/api/projects/${pid}/estimate/tab-export?tab=${tab}&fmt=${fmt}`, { inputs, state, label },
        `${fileStem(code, name, TAB_FILE[tab], "Estimate")}.${fmt === "excel" ? "xlsx" : "pdf"}`);
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(""); }
  };
  return (
    <div className="mt-4 flex flex-wrap items-center gap-2 rounded-xl border border-line bg-white px-4 py-3">
      <Download size={16} className="text-brand-600" />
      <span className="text-sm font-semibold text-navy-ink">Download this tab – {TAB_FILE[tab]}</span>
      <span className="text-xs text-slate-500">({label || "draft"})</span>
      <div className="ml-auto flex gap-2">
        <button className="btn-outline btn-sm" disabled={!!busy} onClick={() => go("pdf")}><FileText size={14} className="text-red-500" />{busy === "pdf" ? "Preparing…" : "PDF"}</button>
        <button className="btn-outline btn-sm" disabled={!!busy} onClick={() => go("excel")}><FileSpreadsheet size={14} className="text-emerald-600" />{busy === "excel" ? "Preparing…" : "Excel"}</button>
      </div>
    </div>
  );
}

type Part = {
  floor_label: string; work_label: string; file_label: string; floors: string[]; works: Record<string, string>;
  items: { sl: number; description: string; floor: string; qty: number; unit: string; rate: number; amount: number }[];
  materials: { name: string; qty: number; unit: string; rate: number; amount: number }[];
  labour: { name: string; qty: number; rate: number; amount: number }[];
  key_materials: { name: string; qty: number; unit: string }[];
  totals: { materials: number; labour: number; equipment: number; total: number; items: number }; note: string;
};

/** Part estimate – choose a floor and a work (e.g. Ground Floor + Slab). */
export function PartEstimate({ pid, code, name, inputs, state, label, result }: {
  pid: number; code: string; name: string; inputs: any; state: string; label: string; result: any;
}) {
  const [floor, setFloor] = useState("all");
  const [work, setWork] = useState("all");
  const [part, setPart] = useState<Part | null>(null);
  const [busy, setBusy] = useState(false);
  const floors: string[] = part?.floors || [...new Set<string>((result?.items || []).map((i: any) => i.floor))];

  useEffect(() => {
    if (!inputs || !result) return;
    let off = false;
    setBusy(true);
    api<Part>(`/api/projects/${pid}/estimate/part`, { body: { inputs, state, floor, work } })
      .then((p) => { if (!off) setPart(p); }).catch((e) => toast(e.message, "err")).finally(() => !off && setBusy(false));
    return () => { off = true; };
  }, [pid, inputs, state, floor, work, result]);

  const dl = async (fmt: "pdf" | "excel") => {
    try {
      await downloadPost(`/api/projects/${pid}/estimate/part?fmt=${fmt}`, { inputs, state, floor, work, label },
        `${fileStem(code, name, floor === "all" ? "" : floor, part?.file_label || "", "Estimate")}.${fmt === "excel" ? "xlsx" : "pdf"}`);
    } catch (e: any) { toast(e.message, "err"); }
  };

  if (!result) return <Card><Empty text="Calculate an estimate first – then choose a floor and a work." /></Card>;
  return (
    <div className="space-y-4">
      <Card title="Part Estimate – choose floor and work" icon={<Puzzle size={20} />}>
        <div className="flex flex-wrap items-end gap-3">
          <label className="text-sm"><span className="label">Floor</span>
            <select className="input min-w-[180px]" value={floor} onChange={(e) => setFloor(e.target.value)}>
              <option value="all">All floors</option>{floors.map((f) => <option key={f} value={f}>{f}</option>)}
            </select></label>
          <label className="text-sm"><span className="label">Work</span>
            <select className="input min-w-[240px]" value={work} onChange={(e) => setWork(e.target.value)}>
              {Object.entries(part?.works || { all: "All works" }).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select></label>
          {busy && <span className="text-xs text-slate-500">Calculating…</span>}
        </div>
        {part && (
          <div className="mt-4 grid gap-3 sm:grid-cols-4">
            {[["Materials", part.totals.materials], ["Labour", part.totals.labour], ["Equipment", part.totals.equipment], ["Total (direct)", part.totals.total]].map(([l, v]) => (
              <div key={l as string} className="rounded-xl border border-line p-3"><div className="text-xs text-slate-500">{l}</div><div className="text-lg font-bold text-navy-ink">{rupees(v as number)}</div></div>
            ))}
          </div>
        )}
      </Card>
      {part && (!part.items.length ? <Card><Empty text={`No items for ${part.work_label} on ${part.floor_label}.`} /></Card> : (
        <>
          <div className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
            <Card title={`Items – ${part.work_label} · ${part.floor_label}`}>
              <div className="overflow-x-auto rounded-lg border border-line"><table className="w-full min-w-[620px]">
                <thead><tr>{["#", "Description", "Floor", "Qty", "Unit", "Rate", "Amount"].map((h) => <th key={h} className="table-th">{h}</th>)}</tr></thead>
                <tbody>{part.items.map((i) => (
                  <tr key={i.sl}><td className="table-td">{i.sl}</td><td className="table-td">{i.description}</td><td className="table-td">{i.floor}</td>
                    <td className="table-td text-right">{num(i.qty)}</td><td className="table-td">{i.unit}</td><td className="table-td text-right">{rupees(i.rate)}</td><td className="table-td text-right font-semibold">{rupees(i.amount)}</td></tr>
                ))}</tbody>
              </table></div>
            </Card>
            <Card title="Materials needed">
              <table className="w-full"><tbody>{part.key_materials.map((k) => (
                <tr key={k.name}><td className={`table-td ${k.name.startsWith("  ") ? "pl-6 text-slate-500" : "font-semibold"}`}>{k.name.trim()}</td><td className="table-td text-right">{num(k.qty)}</td><td className="table-td">{k.unit}</td></tr>
              ))}</tbody></table>
              <p className="mt-2 text-[11px] text-slate-500">Steel dia split and water are approximate – exact bar split is in the BBS tab.</p>
            </Card>
          </div>
          <div className="grid gap-4 lg:grid-cols-2">
            <Card title="All materials (with wastage)"><table className="w-full"><tbody>{part.materials.map((m) => (
              <tr key={m.name}><td className="table-td">{m.name}</td><td className="table-td text-right">{num(m.qty)} {m.unit}</td><td className="table-td text-right">{rupees(m.amount)}</td></tr>))}</tbody></table></Card>
            <Card title="Labour"><table className="w-full"><tbody>{part.labour.map((l) => (
              <tr key={l.name}><td className="table-td">{l.name}</td><td className="table-td text-right">{num(l.qty)} man-days</td><td className="table-td text-right">{rupees(l.amount)}</td></tr>))}</tbody></table></Card>
          </div>
          <p className="text-xs text-slate-500">{part.note}</p>
          <div className="flex flex-wrap items-center gap-2 rounded-xl border border-line bg-white px-4 py-3">
            <Download size={16} className="text-brand-600" /><span className="text-sm font-semibold text-navy-ink">Download part estimate ({label || "draft"})</span>
            <div className="ml-auto flex gap-2">
              <button className="btn-primary btn-sm" onClick={() => dl("pdf")}><FileText size={14} />PDF</button>
              <button className="btn-outline btn-sm" onClick={() => dl("excel")}><FileSpreadsheet size={14} className="text-emerald-600" />Excel</button>
            </div>
          </div>
        </>
      ))}
    </div>
  );
}
