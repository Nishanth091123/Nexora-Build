// 1.19 Site tools: marking guide, water services (RWH / sump / septic), change requests, steel cutting, handover pack.
import { useCallback, useEffect, useState } from "react";
import { Download, Droplets, FileSignature, Ruler, Scissors, PackageCheck, RotateCcw } from "lucide-react";
import { Badge, Card, Empty, Field, SegTabs, toast } from "../ui";
import { api, downloadFile, downloadPost } from "../../lib/api";

type T = "marking" | "services" | "variations" | "cutting" | "handover";
const rs = (v: number | null | undefined) => (v == null ? "–" : "₹" + new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 }).format(v));

export default function SiteTools({ pid, code, canWrite }: { pid: number; code: string; canWrite: boolean }) {
  const [t, setT] = useState<T>("marking");
  return (
    <div className="space-y-4">
      <SegTabs tabs={[{ id: "marking", label: "Marking guide" }, { id: "services", label: "Water & septic" }, { id: "variations", label: "Change requests" },
        { id: "cutting", label: "Steel cutting" }, { id: "handover", label: "Handover pack" }]} value={t} onChange={setT} />
      {t === "marking" && <Marking pid={pid} code={code} canWrite={canWrite} />}
      {t === "services" && <Services pid={pid} code={code} canWrite={canWrite} />}
      {t === "variations" && <Variations pid={pid} code={code} canWrite={canWrite} />}
      {t === "cutting" && <Cutting pid={pid} code={code} />}
      {t === "handover" && <Handover pid={pid} code={code} canWrite={canWrite} />}
    </div>
  );
}

function useLoad<X>(path: string) {
  const [d, setD] = useState<X | null>(null);
  const [err, setErr] = useState("");
  const load = useCallback(async () => {
    try { setD(await api<X>(path)); setErr(""); } catch (e: any) { setErr(e.message); }
  }, [path]);
  useEffect(() => { load(); }, [load]);
  return { d, err, load };
}

function Src({ s }: { s?: string }) {
  if (!s) return null;
  return <Badge color={s === "manual" ? "purple" : s === "auto" ? "blue" : "amber"}>{s}</Badge>;
}

// ------------------------------------------------------------------ 16 marking guide
function Marking({ pid, code, canWrite }: { pid: number; code: string; canWrite: boolean }) {
  const { d, err, load } = useLoad<any>(`/api/projects/${pid}/site-marking`);
  const [v, setV] = useState<Record<string, string>>({});
  useEffect(() => { if (d) { const i = d.guide.inputs; setV({ egl_mm: i.egl_mm ?? "", plinth_mm: i.plinth_mm ?? "", parking_mm: i.parking_mm ?? "", sunken_mm: i.sunken_mm ?? "", sewer_mm: i.sewer_mm ?? "", bm_note: i.bm_note ?? "" }); } }, [d]);
  if (err) return <Empty icon={<Ruler className="text-slate-400" />} text={err} />;
  if (!d) return <p className="text-sm text-slate-500">Loading…</p>;
  const g = d.guide;
  const save = async (reset?: string) => {
    const values: any = {};
    for (const [k, x] of Object.entries(v)) values[k] = k === "bm_note" ? x : x === "" ? null : Number(x);
    if (reset) values[reset] = null;
    try { await api(`/api/projects/${pid}/site-data/levels`, { method: "PUT", body: { values } }); toast("Saved"); load(); } catch (e: any) { toast(e.message, "err"); }
  };
  const inp = (k: string, label: string) => (
    <Field label={label}>
      <div className="flex items-center gap-1">
        <input className="input" type="number" value={v[k] ?? ""} onChange={(e) => setV({ ...v, [k]: e.target.value })} disabled={!canWrite} />
        <Src s={g.sources[k]} />
        {g.sources[k] === "manual" && canWrite && <button title="Back to auto" className="text-slate-500" onClick={() => save(k)}><RotateCcw size={14} /></button>}
      </div>
    </Field>
  );
  return (
    <div className="space-y-4">
      <Card title={`Site marking guide – ${d.design.title} v${d.design.version}`} icon={<Ruler size={20} />}
        action={<button className="btn-primary btn-sm" onClick={() => downloadFile(`/api/projects/${pid}/site-marking.pdf`, `${code}_Site_Marking_Guide.pdf`).catch((e) => toast(e.message, "err"))}><Download size={14} />PDF (print)</button>}>
        <p className="mb-3 text-sm text-slate-600">BM = road crown at the gate (±0.000). All levels in mm from the BM. Site values are asked – never guessed; <b>auto</b> values can be changed (<b>manual</b>).</p>
        <div className="grid gap-3 sm:grid-cols-3">
          {inp("egl_mm", "Existing ground level (mm, + above road)")}
          {inp("plinth_mm", "Ground floor FFL above road (mm)")}
          {inp("parking_mm", "Car parking level above road (mm)")}
          {inp("sunken_mm", "Sunken toilet depth (mm)")}
          {inp("sewer_mm", "Sewer invert level (mm, − below road)")}
          <Field label="BM description (where it is painted)"><input className="input" value={v.bm_note ?? ""} onChange={(e) => setV({ ...v, bm_note: e.target.value })} disabled={!canWrite} /></Field>
        </div>
        {canWrite && <div className="mt-3 flex justify-end"><button className="btn-primary btn-sm" onClick={() => save()}>Save values</button></div>}
        {g.questions.length > 0 && <div className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900"><b>Still to measure:</b><ul className="list-disc pl-5">{g.questions.map((q: string) => <li key={q}>{q}</li>)}</ul></div>}
        {g.warnings.length > 0 && <ul className="mt-2 space-y-1 text-sm text-red-700">{g.warnings.map((w: string) => <li key={w}>⚠ {w}</li>)}</ul>}
        {!d.has_structure && <p className="mt-2 text-xs text-slate-500">Footing pits need the structural design of this drawing (Design → Structure, asks soil SBC and seismic zone).</p>}
      </Card>
      <Card title="1. Setting out">
        <ol className="list-decimal space-y-1 pl-5 text-sm">{g.reference.steps.map((s: string) => <li key={s}>{s}</li>)}</ol>
        <div className="mt-3 grid gap-3 md:grid-cols-2">
          <Tbl head={["Grid", "From first", "ft-in", "From left boundary"]} rows={g.grid.x.map((c: any) => [c.name, `${c.from_first_mm} mm`, c.ftin, `${c.from_left_boundary_mm} mm`])} />
          <Tbl head={["Grid", "From first", "ft-in", "From front boundary"]} rows={g.grid.y.map((c: any) => [c.name, `${c.from_first_mm} mm`, c.ftin, `${c.from_front_boundary_mm} mm`])} />
        </div>
      </Card>
      {g.footings.length > 0 && <Card title="2. Footing pits"><Tbl head={["Footing", "Grid", "Centre x, y (mm)", "Footing", "PCC", "Pit", "Depth mm"]}
        rows={g.footings.map((f: any) => [f.mark, f.grid, `${f.x_mm}, ${f.y_mm}`, f.footing_m, f.pcc_m, f.pit_m, f.pit_depth_mm ?? "?"])} /></Card>}
      <Card title="3. Level table"><Tbl head={["Item", "From BM (m)", "From GF FFL (m)"]} rows={g.levels.map((r: any) => [r.item, r.from_bm, r.from_ffl])} /></Card>
      <Card title="4. Room marking (doors & windows)">
        <p className="mb-2 text-xs text-slate-500">{g.rooms_note}</p>
        <Tbl head={["Floor", "Room", "Corner x, y (mm)", "Size", "Diagonal", "Openings"]} rows={g.rooms.map((r: any) => [r.floor, r.room + (r.unit ? ` · ${r.unit}` : ""), `${r.x_mm}, ${r.y_mm}`, r.size, `${r.diag_mm} mm`,
          r.openings.map((o: any) => `${o.type} ${o.mark || ""} ${o.wall} @${o.from_corner_mm} w${o.width_mm} sill ${o.sill_mm}`).join("; ") || "—"])} />
      </Card>
      {g.sunken.length > 0 && <Card title="5. Sunken toilets"><Tbl head={["Floor", "Toilet", "Sunk", "Slope", "Trap"]} rows={g.sunken.map((s: any) => [s.floor, `${s.room} (${s.size})`, `${s.sunk_mm} mm`, s.slope, s.trap])} /></Card>}
      {g.ramp && <Card title="6. Car parking ramp"><ul className="list-disc space-y-1 pl-5 text-sm">{[...g.ramp.steps, g.ramp.entry_steps].filter(Boolean).map((s: string) => <li key={s}>{s}</li>)}</ul></Card>}
      {g.stair && <Card title="7. Staircase marking">
        <p className="text-sm">{g.stair.type}: {g.stair.risers} risers × {Math.round(g.stair.riser_mm)} mm, tread {g.stair.tread_mm} mm, waist {g.stair.waist_mm} mm. {g.stair.start}</p>
        <ol className="mt-2 list-decimal space-y-1 pl-5 text-sm">{g.stair.steps.map((s: string) => <li key={s}>{s}</li>)}</ol>
        <div className="mt-2"><Tbl head={["Step", "Flight", "Along wall mm", "Height mm", "Level (BM)"]} rows={g.stair.table.map((x: any) => [x.step, x.flight, x.along_mm, x.height_mm, x.level])} /></div>
      </Card>}
      {g.terrace && <Card title="8. Terrace slope"><p className="text-sm">{g.terrace.slope}; farthest point {g.terrace.far_mm} mm → fall {g.terrace.fall_mm} mm. {g.terrace.screed}</p>
        <p className="mt-1 text-sm">Outlets: {g.terrace.outlets.map((o: any) => o.where).join(", ")}</p></Card>}
      {g.drainage?.chambers?.length > 0 && <Card title="9. Drainage chambers & invert levels">
        <p className="mb-2 text-sm">Line on the {g.drainage.side} side · {g.drainage.slope}{g.drainage.sewer ? ` · ${g.drainage.sewer}` : ""}</p>
        <Tbl head={["Chamber", "From left", "From front", "Serves", "Invert (BM)", "Depth"]} rows={g.drainage.chambers.map((c: any) => [c.chamber, `${c.from_left_mm} mm`, `${c.from_front_mm} mm`, c.rooms, c.invert, c.depth_mm ? `${c.depth_mm} mm` : "?"])} />
      </Card>}
      {g.compound && <Card title="10. Gate & compound wall"><ul className="list-disc pl-5 text-sm">{g.compound.gates.map((x: any) => <li key={x.what}>{x.what}: {x.width_mm} mm wide, from {x.from_left_mm} mm (left boundary)</li>)}<li>Compound wall ≈ {g.compound.wall_length_m} m. {g.compound.note}</li></ul>
        <p className="mt-1 text-xs text-slate-500">Sump / septic / RWH positions: see “Water & septic”.</p></Card>}
    </div>
  );
}

function Tbl({ head, rows }: { head: string[]; rows: any[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead><tr>{head.map((h) => <th key={h} className="table-th">{h}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className="table-td">{c}</td>)}</tr>)}</tbody>
      </table>
    </div>
  );
}

// ------------------------------------------------------------------ 19 water services
function Services({ pid, code, canWrite }: { pid: number; code: string; canWrite: boolean }) {
  const { d, err, load } = useLoad<any>(`/api/projects/${pid}/services`);
  const [v, setV] = useState<Record<string, string>>({});
  const [by, setBy] = useState("");
  useEffect(() => { if (d) { const i = d.inputs; setV({ soil: i.soil ?? "", sewer: i.sewer ?? "", well: i.well ?? "", persons: i.persons ?? "", lpcd: i.lpcd ?? "", sump_days: i.sump_days ?? "" }); } }, [d]);
  if (err) return <Empty icon={<Droplets className="text-slate-400" />} text={err} />;
  if (!d) return <p className="text-sm text-slate-500">Loading…</p>;
  const save = async () => {
    const values: any = {};
    for (const [k, x] of Object.entries(v)) values[k] = ["persons", "lpcd", "sump_days"].includes(k) ? (x === "" ? null : Number(x)) : x || null;
    try { await api(`/api/projects/${pid}/site-data/services`, { method: "PUT", body: { values } }); toast("Saved"); load(); } catch (e: any) { toast(e.message, "err"); }
  };
  const approve = async (status: string) => {
    try { await api(`/api/projects/${pid}/services/approval`, { body: { status, by } }); toast(status === "approved" ? "Approval recorded" : "Marked pending"); load(); } catch (e: any) { toast(e.message, "err"); }
  };
  const sel = (k: string, label: string, opts: string[]) => (
    <Field label={label}><select className="input" value={v[k] ?? ""} onChange={(e) => setV({ ...v, [k]: e.target.value })} disabled={!canWrite}>
      <option value="">— please choose —</option>{opts.map((o) => <option key={o} value={o}>{o}</option>)}</select></Field>
  );
  return (
    <div className="space-y-4">
      <Card title="Rain water harvesting · sump · tanks · septic" icon={<Droplets size={20} />}
        action={<button className="btn-primary btn-sm" onClick={() => downloadFile(`/api/projects/${pid}/services.pdf`, `${code}_Water_Services.pdf`).catch((e) => toast(e.message, "err"))}><Download size={14} />PDF</button>}>
        <div className="grid gap-3 sm:grid-cols-3">
          {sel("soil", "Soil type", ["sandy", "mixed", "clayey", "hard rock"])}
          {sel("sewer", "Sewer line in the road?", ["yes", "no"])}
          {sel("well", "Well / borewell in the plot?", ["none", "borewell", "open well"])}
          <Field label={`Persons (auto ${d.inputs.houses * 5})`}><input className="input" type="number" value={v.persons ?? ""} onChange={(e) => setV({ ...v, persons: e.target.value })} disabled={!canWrite} /></Field>
          <Field label="Litres / person / day"><input className="input" type="number" value={v.lpcd ?? ""} onChange={(e) => setV({ ...v, lpcd: e.target.value })} disabled={!canWrite} /></Field>
          <Field label="Sump storage (days)"><input className="input" type="number" step="0.5" value={v.sump_days ?? ""} onChange={(e) => setV({ ...v, sump_days: e.target.value })} disabled={!canWrite} /></Field>
        </div>
        {canWrite && <div className="mt-3 flex justify-end"><button className="btn-primary btn-sm" onClick={save}>Save & recalculate</button></div>}
        {d.questions.length > 0 && <div className="mt-3 rounded-lg bg-amber-50 p-3 text-sm text-amber-900"><b>Please confirm:</b><ul className="list-disc pl-5">{d.questions.map((q: string) => <li key={q}>{q}</li>)}</ul></div>}
      </Card>
      <Card title="Sizes">
        <Tbl head={["Item", "Size", "Details", "Basis"]} rows={[
          ["Underground sump", `${d.sump.litres.toLocaleString("en-IN")} L`, `${d.sump.inner_l_m} × ${d.sump.inner_b_m} m inside, ${d.sump.water_depth_m} m water + ${d.sump.freeboard_m} m`, d.sump.basis],
          ["Overhead tank", `${d.oht.litres.toLocaleString("en-IN")} L`, `${d.oht.count} tank(s)`, d.oht.basis],
          ...(d.septic.needed ? [["Septic tank", `${d.septic.users} users`, `${d.septic.inner_l_m} × ${d.septic.inner_b_m} m, liquid ${d.septic.liquid_depth_m} m + ${d.septic.freeboard_m} m; ${d.septic.chambers}`, d.septic.basis]] : []),
          ["Rain water harvesting", `${d.rwh.wells} well(s)`, `${d.rwh.type}; depth ${d.rwh.depth_m ? d.rwh.depth_m + " m" : "after soil type"}`, d.rwh.basis],
        ]} />
        {d.positions?.length > 0 && <div className="mt-3"><Tbl head={["Item", "From left", "From front", "Size", "Where"]} rows={d.positions.map((p: any) => [p.item, `${p.x.toFixed(1)} ft`, `${p.y.toFixed(1)} ft`, `${p.w.toFixed(1)} × ${p.d.toFixed(1)} ft`, p.where])} /></div>}
        {[...d.warnings, ...d.notes].length > 0 && <ul className="mt-2 space-y-1 text-sm text-amber-800">{[...d.warnings, ...d.notes].map((w: string) => <li key={w}>• {w}</li>)}</ul>}
      </Card>
      <Card title="Estimate (your rate library)">
        <Tbl head={["Item", "Qty", "Unit", "Rate", "Amount"]} rows={[...d.estimate.map((x: any) => [x.item, x.qty.toLocaleString("en-IN"), x.unit, x.rate == null ? "rate not set" : rs(x.rate), rs(x.amount)]), ["Total", "", "", "", rs(d.estimate_total)]]} />
      </Card>
      <Card title="Client approval">
        {d.approval?.status === "approved" ? <p className="text-sm">✅ Approved by <b>{d.approval.by}</b> on {d.approval.date}{d.approval.note ? ` – ${d.approval.note}` : ""}</p> : <p className="text-sm text-slate-600">Not approved yet.</p>}
        {canWrite && <div className="mt-2 flex flex-wrap items-end gap-2">
          <Field label="Approved by (client name)"><input className="input" value={by} onChange={(e) => setBy(e.target.value)} /></Field>
          <button className="btn-primary btn-sm" onClick={() => approve("approved")}>Record approval</button>
          {d.approval?.status === "approved" && <button className="btn-outline btn-sm" onClick={() => approve("pending")}>Back to pending</button>}
        </div>}
      </Card>
    </div>
  );
}

// ------------------------------------------------------------------ 17 change requests
function Variations({ pid, code, canWrite }: { pid: number; code: string; canWrite: boolean }) {
  const { d, load } = useLoad<any>(`/api/projects/${pid}/variations`);
  const [designs, setDesigns] = useState<any[]>([]);
  const [rates, setRates] = useState<any[]>([]);
  const [f, setF] = useState<any>({ title: "", reason: "", requested_by: "", from: "", to: "", days: "", lines: [] as any[] });
  const [imp, setImp] = useState<any>(null);
  const [dec, setDec] = useState<Record<number, string>>({});
  useEffect(() => {
    api<any[]>(`/api/projects/${pid}/designs`).then(setDesigns).catch(() => setDesigns([]));
    api<any>(`/api/rates`).then((r) => setRates(Array.isArray(r) ? r : r.items || [])).catch(() => setRates([]));
  }, [pid]);
  const body = () => ({
    title: f.title, reason: f.reason, requested_by: f.requested_by,
    from_design_id: f.from ? Number(f.from) : null, to_design_id: f.to ? Number(f.to) : null, days: f.days === "" ? null : Number(f.days),
    lines: f.lines.filter((l: any) => l.desc).map((l: any) => ({ desc: l.desc, qty: Number(l.qty) || 0, unit: l.unit, code: l.code, rate: l.rate === "" || l.rate == null ? null : Number(l.rate), sign: l.sign })),
  });
  const preview = async () => { try { setImp(await api(`/api/projects/${pid}/variations/impact`, { body: body() })); } catch (e: any) { toast(e.message, "err"); } };
  const add = async () => {
    try { await api(`/api/projects/${pid}/variations`, { body: body() }); toast("Change request saved – send the PDF to the client");
      setF({ title: "", reason: "", requested_by: "", from: "", to: "", days: "", lines: [] }); setImp(null); load(); } catch (e: any) { toast(e.message, "err"); }
  };
  const decide = async (no: number, status: string) => {
    try { await api(`/api/projects/${pid}/variations/${no}/decision`, { body: { status, by: dec[no] || "" } }); load(); } catch (e: any) { toast(e.message, "err"); }
  };
  const setLine = (i: number, k: string, val: any) => { const ls = [...f.lines]; ls[i] = { ...ls[i], [k]: val }; setF({ ...f, lines: ls }); };
  return (
    <div className="space-y-4">
      {canWrite && <Card title="New change request (variation)" icon={<FileSignature size={20} />}>
        <div className="grid gap-3 sm:grid-cols-3">
          <Field label="Title"><input className="input" value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="e.g. Add a pooja room on FF" /></Field>
          <Field label="Requested by"><input className="input" value={f.requested_by} onChange={(e) => setF({ ...f, requested_by: e.target.value })} /></Field>
          <Field label="Reason"><input className="input" value={f.reason} onChange={(e) => setF({ ...f, reason: e.target.value })} /></Field>
          <Field label="Drawing before (optional)"><select className="input" value={f.from} onChange={(e) => setF({ ...f, from: e.target.value })}><option value="">—</option>{designs.map((x) => <option key={x.id} value={x.id}>{x.title} v{x.version}</option>)}</select></Field>
          <Field label="Drawing after (optional)"><select className="input" value={f.to} onChange={(e) => setF({ ...f, to: e.target.value })}><option value="">—</option>{designs.map((x) => <option key={x.id} value={x.id}>{x.title} v{x.version}</option>)}</select></Field>
          <Field label="Extra days (blank = auto)"><input className="input" type="number" value={f.days} onChange={(e) => setF({ ...f, days: e.target.value })} /></Field>
        </div>
        <div className="mt-3 space-y-2">
          {f.lines.map((l: any, i: number) => (
            <div key={i} className="grid grid-cols-2 gap-2 sm:grid-cols-6">
              <select className="input sm:col-span-2" value={l.code} onChange={(e) => { const r = rates.find((x) => x.code === e.target.value); const ls = [...f.lines]; ls[i] = { ...l, code: e.target.value, desc: l.desc || r?.name || "", unit: r?.unit || l.unit }; setF({ ...f, lines: ls }); }}>
                <option value="">Own item (type the rate)</option>{rates.filter((r) => r.is_active !== false).map((r) => <option key={r.code} value={r.code}>{r.name} ({r.unit})</option>)}
              </select>
              <input className="input sm:col-span-2" placeholder="Description" value={l.desc} onChange={(e) => setLine(i, "desc", e.target.value)} />
              <input className="input" type="number" placeholder="Qty" value={l.qty} onChange={(e) => setLine(i, "qty", e.target.value)} />
              <div className="flex gap-1">
                {!l.code && <input className="input" type="number" placeholder="Rate" value={l.rate ?? ""} onChange={(e) => setLine(i, "rate", e.target.value)} />}
                <select className="input" value={l.sign} onChange={(e) => setLine(i, "sign", Number(e.target.value))}><option value={1}>Extra</option><option value={-1}>Omit</option></select>
              </div>
            </div>
          ))}
          <button className="btn-outline btn-sm" onClick={() => setF({ ...f, lines: [...f.lines, { code: "", desc: "", qty: "", unit: "", rate: "", sign: 1 }] })}>+ Item</button>
        </div>
        {imp && <div className="mt-3 rounded-lg bg-brand-50 p-3 text-sm">Cost impact <b>{rs(imp.total)}</b> · time <b>{imp.days > 0 ? "+" : ""}{imp.days} days</b> ({imp.days_source})</div>}
        <div className="mt-3 flex justify-end gap-2"><button className="btn-outline btn-sm" onClick={preview}>Work out impact</button><button className="btn-primary btn-sm" onClick={add} disabled={!f.title}>Save change request</button></div>
      </Card>}
      <Card title="Change requests" action={d && <span className="text-sm text-slate-600">Approved: <b>{rs(d.approved_total)}</b>, {d.approved_days} days · {d.pending} pending</span>}>
        {!d?.items?.length ? <p className="text-sm text-slate-500">No change requests yet.</p> : (
          <div className="space-y-2">{d.items.map((v: any) => (
            <div key={v.no} className="rounded-lg border border-line p-3 text-sm">
              <div className="flex flex-wrap items-center gap-2">
                <b>VO-{String(v.no).padStart(3, "0")}</b> {v.title}
                <Badge color={v.status === "approved" ? "green" : v.status === "rejected" ? "red" : "amber"}>{v.status}</Badge>
                <span className="ml-auto">{rs(v.total)} · {v.days > 0 ? "+" : ""}{v.days} days</span>
                <button className="btn-outline btn-sm" onClick={() => downloadFile(`/api/projects/${pid}/variations/${v.no}/pdf`, `${code}_VO-${String(v.no).padStart(3, "0")}.pdf`).catch((e) => toast(e.message, "err"))}><Download size={14} />PDF</button>
              </div>
              {v.decided_by && <p className="mt-1 text-xs text-slate-500">{v.status} by {v.decided_by} on {v.decided_on}</p>}
              {canWrite && v.status === "pending" && <div className="mt-2 flex flex-wrap items-center gap-2">
                <input className="input w-48" placeholder="Client name" value={dec[v.no] || ""} onChange={(e) => setDec({ ...dec, [v.no]: e.target.value })} />
                <button className="btn-primary btn-sm" onClick={() => decide(v.no, "approved")}>Approved</button>
                <button className="btn-outline btn-sm" onClick={() => decide(v.no, "rejected")}>Rejected</button>
              </div>}
            </div>))}</div>)}
      </Card>
    </div>
  );
}

// ------------------------------------------------------------------ 18 steel cutting
function Cutting({ pid, code }: { pid: number; code: string }) {
  const [list, setList] = useState<any[]>([]);
  const [bid, setBid] = useState<number | "">("");
  const [stock, setStock] = useState(12000);
  const [res, setRes] = useState<any>(null);
  useEffect(() => { api<any[]>(`/api/projects/${pid}/bbs`).then((l) => { setList(l); if (l[0]) setBid(l[0].id); }).catch(() => setList([])); }, [pid]);
  const run = async () => { try { setRes(await api(`/api/projects/${pid}/steel-cutting`, { body: { bbs_id: bid, stock_mm: stock } })); } catch (e: any) { toast(e.message, "err"); } };
  if (!list.length) return <Empty icon={<Scissors className="text-slate-400" />} text="Make a Bar Bending Schedule first (Estimate → BBS); the cutting plan is made from it." />;
  return (
    <div className="space-y-4">
      <Card title="Steel cutting optimiser (12 m bars)" icon={<Scissors size={20} />}
        action={res && <button className="btn-primary btn-sm" onClick={() => downloadPost(`/api/projects/${pid}/steel-cutting/pdf`, { bbs_id: bid, stock_mm: stock }, `${code}_Steel_Cutting_Plan.pdf`).catch((e) => toast(e.message, "err"))}><Download size={14} />PDF</button>}>
        <div className="flex flex-wrap items-end gap-3">
          <Field label="BBS"><select className="input" value={bid} onChange={(e) => setBid(Number(e.target.value))}>{list.map((b) => <option key={b.id} value={b.id}>{b.title} ({Math.round(b.total_kg)} kg)</option>)}</select></Field>
          <Field label="Stock bar length (mm)"><input className="input w-32" type="number" value={stock} onChange={(e) => setStock(Number(e.target.value))} /></Field>
          <button className="btn-primary" onClick={run}>Make cutting plan</button>
        </div>
      </Card>
      {res && <>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="card p-4"><div className="text-xs text-slate-500">Bars to order</div><div className="text-2xl font-bold">{res.total_bars}</div><div className="text-xs text-slate-500">vs {res.total_bars_naive} cutting mark by mark</div></div>
          <div className="card p-4"><div className="text-xs text-slate-500">Steel saved</div><div className="text-2xl font-bold text-emerald-700">{res.saved_kg} kg</div></div>
          <div className="card p-4"><div className="text-xs text-slate-500">Money saved</div><div className="text-2xl font-bold text-emerald-700">{res.saved_rs == null ? "set steel rate" : rs(res.saved_rs)}</div></div>
        </div>
        {res.by_dia.map((x: any) => (
          <Card key={x.dia} title={`${x.dia} mm – ${x.bars_needed} bars, waste ${x.waste_pct}%`}>
            <Tbl head={["Bars", "Cut each bar into", "Off-cut"]} rows={x.patterns.map((p: any) => [p.bars, p.text, `${p.offcut_mm} mm`])} />
            {x.reusable_offcuts_mm.length > 0 && <p className="mt-1 text-xs text-slate-500">Re-usable off-cuts: {x.reusable_offcuts_mm.join(", ")} mm</p>}
          </Card>))}
        {res.laps.length > 0 && <Card title="Bars longer than the stock"><ul className="list-disc pl-5 text-sm">{res.laps.map((l: string) => <li key={l}>{l}</li>)}</ul></Card>}
      </>}
    </div>
  );
}

// ------------------------------------------------------------------ 21 handover
function Handover({ pid, code, canWrite }: { pid: number; code: string; canWrite: boolean }) {
  const { d, load } = useLoad<any>(`/api/projects/${pid}/handover`);
  const [h, setH] = useState<any>(null);
  useEffect(() => { if (d) setH(d.handover); }, [d]);
  if (!d || !h) return <p className="text-sm text-slate-500">Loading…</p>;
  const save = async () => { try { await api(`/api/projects/${pid}/site-data/handover`, { method: "PUT", body: { values: h } }); toast("Saved"); load(); } catch (e: any) { toast(e.message, "err"); } };
  const setW = (i: number, k: string, val: string) => { const w = [...h.warranties]; w[i] = { ...w[i], [k]: val }; setH({ ...h, warranties: w }); };
  return (
    <div className="space-y-4">
      <Card title="Handover pack" icon={<PackageCheck size={20} />}
        action={<button className="btn-primary btn-sm" onClick={() => downloadFile(`/api/projects/${pid}/handover.pdf`, `${code}_Handover_Pack.pdf`).catch((e) => toast(e.message, "err"))}><Download size={14} />PDF with drawings</button>}>
        <p className="mb-3 text-sm text-slate-600">As-built drawings (active drawing sheets), brands used, warranties, water services and a maintenance calendar – one PDF for the owner.</p>
        <div className="grid gap-3 sm:grid-cols-2">
          <Field label="Handover date"><input className="input" type="date" value={h.date || ""} onChange={(e) => setH({ ...h, date: e.target.value })} disabled={!canWrite} /></Field>
          <Field label="Keys & documents handed over"><input className="input" value={h.keys || ""} onChange={(e) => setH({ ...h, keys: e.target.value })} disabled={!canWrite} placeholder="e.g. 3 sets main door keys, EB card, warranty cards" /></Field>
          <Field label="As-built changes (what differs from the drawing)" className="sm:col-span-2"><textarea className="input min-h-[60px]" value={h.as_built_notes || ""} onChange={(e) => setH({ ...h, as_built_notes: e.target.value })} disabled={!canWrite} /></Field>
        </div>
      </Card>
      <Card title="Warranties" action={canWrite && <button className="btn-outline btn-sm" onClick={() => setH({ ...h, warranties: [...h.warranties, { item: "", brand: "", years: "", from: "", contact: "" }] })}>+ Row</button>}>
        <div className="space-y-2">
          {h.warranties.map((w: any, i: number) => (
            <div key={i} className="grid grid-cols-2 gap-2 sm:grid-cols-5">
              <input className="input" placeholder="Item" value={w.item || ""} onChange={(e) => setW(i, "item", e.target.value)} disabled={!canWrite} />
              <input className="input" placeholder="Brand / product" value={w.brand || ""} onChange={(e) => setW(i, "brand", e.target.value)} disabled={!canWrite} />
              <input className="input" type="number" placeholder="Years" value={w.years || ""} onChange={(e) => setW(i, "years", e.target.value)} disabled={!canWrite} />
              <input className="input" type="date" value={w.from || ""} onChange={(e) => setW(i, "from", e.target.value)} disabled={!canWrite} />
              <input className="input" placeholder="Service contact" value={w.contact || ""} onChange={(e) => setW(i, "contact", e.target.value)} disabled={!canWrite} />
            </div>))}
          {!h.warranties.length && <p className="text-sm text-slate-500">Pick brands in the Material Library for this project – they appear here; or add rows.</p>}
        </div>
        {canWrite && <div className="mt-3 flex justify-end"><button className="btn-primary btn-sm" onClick={save}>Save</button></div>}
      </Card>
      <Card title="Maintenance calendar (printed in the pack)"><Tbl head={["Item", "What", "When"]} rows={d.maintenance.map((m: any) => [m.item, m.what, m.when])} /></Card>
    </div>
  );
}
