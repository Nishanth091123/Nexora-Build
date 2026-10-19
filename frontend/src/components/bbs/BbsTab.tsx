import { useCallback, useEffect, useState } from "react";
import { Calculator, Download, FileSpreadsheet, Plus, Save, Trash2, TriangleAlert, X } from "lucide-react";
import { Badge, Card, Empty, toast } from "../ui";
import OwnerDelete from "../OwnerDelete";
import { api, ApiError, downloadFile, num } from "../../lib/api";

type Bars = { dia: number | string; nos: number | string }[];
type Member = Record<string, any> & { type: string; mark: string };
type Row = { member: string; mark: string; desc: string; shape: string; dims: Record<string, number>; dia: number; per_member: number;
  members: number; nos: number; cut_mm: number; total_m: number; kg: number };
type Result = { rows: Row[]; summary: { dia: number; kg_per_m: number; total_m: number; kg: number; kg_with_wastage: number; bars_12m: number }[];
  total_kg: number; wastage_pct: number; assumptions: string[]; drawings: any[] };

const DIAS = [6, 8, 10, 12, 16, 20, 25, 32];
// field: [key, label, placeholder]
const FIELDS: Record<string, [string, string, string][]> = {
  column: [["count", "No. of such columns", "e.g. 12"], ["b", "Width b (mm)", "230"], ["d", "Depth D (mm)", "380"], ["height", "Floor-to-floor height (mm)", "3000"],
    ["floors", "Floors (lifts)", "2"], ["cover", "Clear cover (mm)", ""], ["tie_dia", "Tie dia (mm)", "8"], ["tie_spacing", "Tie spacing (mm)", "150"],
    ["tie_end_spacing", "Tie spacing near beams (mm) – blank = IS 13920", ""], ["footing_depth", "Footing depth (mm)", "450"], ["bottom_bend", "L-bend in footing (mm)", "e.g. 300"],
    ["lap_factor", "Lap (× dia) – blank = 50", ""]],
  beam: [["count", "No. of such beams", ""], ["span", "Clear span (mm)", "3600"], ["support", "Support / column width (mm)", "230"], ["b", "Width b (mm)", "230"],
    ["d", "Depth D (mm)", "380"], ["cover", "Clear cover (mm)", ""], ["stirrup_dia", "Stirrup dia (mm)", "8"], ["stirrup_spacing", "Stirrup spacing (mm)", "150"],
    ["stirrup_end_spacing", "Spacing near supports (mm) – blank = IS 13920", ""]],
  footing: [["count", "No. of such footings", ""], ["length", "Length L (mm)", "1500"], ["width", "Width B (mm)", "1500"], ["depth", "Depth (mm)", "450"],
    ["cover", "Clear cover (mm)", ""], ["dia_l", "Bar dia along L (mm)", "12"], ["spacing_l", "Spacing along L (mm)", "150"], ["dia_b", "Bar dia along B (mm)", "12"],
    ["spacing_b", "Spacing along B (mm)", "150"], ["bend_up", "End bend-up (mm)", "e.g. 150"]],
  slab: [["count", "No. of such panels", ""], ["lx", "Short span Lx (mm)", "3600"], ["ly", "Long span Ly (mm)", "4200"], ["thickness", "Thickness (mm)", "125"],
    ["cover", "Clear cover (mm)", ""], ["support", "Beam width at supports (mm)", "230"], ["main_dia", "Main bar dia (mm)", "10"], ["main_spacing", "Main spacing (mm)", "150"],
    ["dist_dia", "Distribution dia (mm)", "8"], ["dist_spacing", "Distribution spacing (mm)", "200"]],
};
const BAR_GROUPS: Record<string, [string, string][]> = { column: [["main", "Main bars"]], beam: [["bottom", "Bottom bars"], ["top", "Top bars"]] };
const COVER: Record<string, number> = { column: 40, beam: 25, footing: 50, slab: 20 };  // IS 456 typical nominal cover
const LABEL: Record<string, string> = { column: "Column", beam: "Beam", footing: "Footing", slab: "Slab" };

function newMember(type: string, n: number): Member {
  const m: Member = { type, mark: `${type[0].toUpperCase()}${n}`, cover: COVER[type] };
  (BAR_GROUPS[type] || []).forEach(([k]) => (m[k] = [{ dia: "", nos: "" }]));
  return m;
}

// ---------------------------------------------------------------- drawings
export function BarShape({ shape, dims }: { shape: string; dims: Record<string, number> }) {
  const s = "#1d4ed8";
  if (shape === "straight") return <svg viewBox="0 0 120 30" className="h-7 w-28"><line x1="6" y1="18" x2="114" y2="18" stroke={s} strokeWidth="3" /><text x="60" y="12" fontSize="9" textAnchor="middle">{dims.a}</text></svg>;
  if (shape === "L") return <svg viewBox="0 0 120 34" className="h-8 w-28"><polyline points="8,30 8,8 114,8" fill="none" stroke={s} strokeWidth="3" /><text x="12" y="30" fontSize="8">{dims.a}</text><text x="62" y="20" fontSize="9" textAnchor="middle">{dims.b}</text></svg>;
  if (shape === "U") return <svg viewBox="0 0 120 34" className="h-8 w-28"><polyline points="8,6 8,28 112,28 112,6" fill="none" stroke={s} strokeWidth="3" /><text x="60" y="22" fontSize="9" textAnchor="middle">{dims.b}</text><text x="12" y="12" fontSize="8">{dims.a}</text></svg>;
  if (shape === "stirrup") {
    const a = dims.a || 1, b = dims.b || 1, k = Math.min(70 / a, 26 / b), w = a * k, h = b * k;
    return <svg viewBox="0 0 120 34" className="h-8 w-28"><rect x="6" y={4} width={w} height={h} fill="none" stroke={s} strokeWidth="3" />
      <line x1="6" y1="4" x2="14" y2="12" stroke={s} strokeWidth="3" /><line x1="10" y1="4" x2="18" y2="12" stroke={s} strokeWidth="3" />
      <text x={w + 12} y="20" fontSize="8">{dims.a}×{dims.b}</text></svg>;
  }
  return null;
}

export function MemberDrawing({ d }: { d: any }) {
  const blue = "#1d4ed8";
  if (d.type === "column") {
    const H = 330, total = d.footing_depth + d.floors * d.h, k = (H - 55) / total, x = 70, w = 46, y0 = H - 15;
    const Y = (mm: number) => y0 - mm * k;
    return (
      <svg viewBox={`0 0 300 ${H}`} className="w-full max-w-sm">
        <rect x={x - 34} y={Y(d.footing_depth)} width={w + 68} height={d.footing_depth * k} fill="#f1f5f9" stroke="#94a3b8" />
        {Array.from({ length: d.floors }).map((_, i) => {
          const base = d.footing_depth + i * d.h;
          return (
            <g key={i}>
              <line x1={x - 14} x2={x + w + 14} y1={Y(base)} y2={Y(base)} stroke="#94a3b8" strokeDasharray="3 2" />
              {i < d.floors - 1 && <rect x={x} y={Y(base + d.h * 0.75)} width={w} height={d.h * 0.5 * k} fill="#fde68a" opacity="0.8" />}
              {i < d.floors - 1 && <text x={x + w + 8} y={Y(base + d.h * 0.5)} fontSize="9" fill="#dc2626">lap {d.lap_mm} mm (middle half)</text>}
              {[0, 1].map((e) => Array.from({ length: 4 }).map((__, j) => {
                const yy = e === 0 ? base + (j * d.l0) / 4 : base + d.h - (j * d.l0) / 4;
                return <line key={`${e}${j}`} x1={x} x2={x + w} y1={Y(yy)} y2={Y(yy)} stroke={blue} strokeWidth="1" />;
              }))}
              {Array.from({ length: 3 }).map((__, j) => <line key={`m${j}`} x1={x} x2={x + w} y1={Y(base + d.h / 2 + (j - 1) * d.spacing)} y2={Y(base + d.h / 2 + (j - 1) * d.spacing)} stroke={blue} strokeWidth="0.6" />)}
            </g>
          );
        })}
        <line x1={x + 8} x2={x + 8} y1={Y(60)} y2={Y(total - 40)} stroke={blue} strokeWidth="2.5" />
        <line x1={x + w - 8} x2={x + w - 8} y1={Y(60)} y2={Y(total - 40)} stroke={blue} strokeWidth="2.5" />
        <line x1={x + 8} x2={x - 22} y1={Y(60)} y2={Y(60)} stroke={blue} strokeWidth="2.5" />
        <line x1={x + w - 8} x2={x + w + 22} y1={Y(60)} y2={Y(60)} stroke={blue} strokeWidth="2.5" />
        <text x={x + w + 26} y={Y(60) + 3} fontSize="9">L-bend {d.bottom_bend} mm</text>
        <text x="8" y="14" fontSize="10" fontWeight="bold">{d.mark}: {d.b}×{d.d} mm</text>
        <text x="8" y="27" fontSize="9">ties {d.tie_dia} mm @ {d.end_spacing} mm for {d.l0} mm at ends, @ {d.spacing} mm middle</text>
      </svg>
    );
  }
  if (d.type === "beam") {
    const W = 300, k = (W - 20) / (d.span + 2 * d.support), y = 40, h = 46, sx = 10 + d.support * k, ex = 10 + (d.support + d.span) * k;
    const z = d.zone * k;
    return (
      <svg viewBox="0 0 300 120" className="w-full max-w-sm">
        <rect x="10" y={y - 10} width={d.support * k} height={h + 20} fill="#e2e8f0" /><rect x={ex} y={y - 10} width={d.support * k} height={h + 20} fill="#e2e8f0" />
        <rect x="10" y={y} width={(d.span + 2 * d.support) * k} height={h} fill="none" stroke="#94a3b8" />
        <polyline points={`14,${y + 18} 14,${y + 6} ${W - 14},${y + 6} ${W - 14},${y + 18}`} fill="none" stroke={blue} strokeWidth="2" />
        <polyline points={`14,${y + h - 18} 14,${y + h - 6} ${W - 14},${y + h - 6} ${W - 14},${y + h - 18}`} fill="none" stroke={blue} strokeWidth="2" />
        {Array.from({ length: 8 }).map((_, i) => <line key={`a${i}`} x1={sx + (i * z) / 8} x2={sx + (i * z) / 8} y1={y + 3} y2={y + h - 3} stroke={blue} />)}
        {Array.from({ length: 8 }).map((_, i) => <line key={`b${i}`} x1={ex - (i * z) / 8} x2={ex - (i * z) / 8} y1={y + 3} y2={y + h - 3} stroke={blue} />)}
        {Array.from({ length: 6 }).map((_, i) => <line key={`c${i}`} x1={sx + z + ((i + 1) * (ex - sx - 2 * z)) / 7} x2={sx + z + ((i + 1) * (ex - sx - 2 * z)) / 7} y1={y + 3} y2={y + h - 3} stroke={blue} strokeWidth="0.6" />)}
        <text x="8" y="14" fontSize="10" fontWeight="bold">{d.mark}: {d.b}×{d.d} mm, span {d.span} mm</text>
        <text x="8" y={y + h + 24} fontSize="9">stirrups @ {d.end_spacing} mm for {d.zone} mm at supports, @ {d.spacing} mm middle</text>
      </svg>
    );
  }
  const L = d.length || d.ly, B = d.width || d.lx, k = Math.min(260 / L, 150 / B), n1 = Math.min(d.nl || d.nd || 8, 24), n2 = Math.min(d.nb || d.nm || 8, 24);
  return (
    <svg viewBox="0 0 300 190" className="w-full max-w-sm">
      <text x="8" y="14" fontSize="10" fontWeight="bold">{d.mark}: {L} × {B} mm {d.type === "slab" ? `slab ${d.thickness} mm` : `footing ${d.depth} mm`}</text>
      <rect x="20" y="24" width={L * k} height={B * k} fill="none" stroke="#94a3b8" />
      {Array.from({ length: n1 }).map((_, i) => <line key={`h${i}`} x1="23" x2={17 + L * k} y1={27 + (i * (B * k - 6)) / Math.max(1, n1 - 1)} y2={27 + (i * (B * k - 6)) / Math.max(1, n1 - 1)} stroke={blue} strokeWidth="0.8" />)}
      {Array.from({ length: n2 }).map((_, i) => <line key={`v${i}`} y1="27" y2={21 + B * k} x1={23 + (i * (L * k - 6)) / Math.max(1, n2 - 1)} x2={23 + (i * (L * k - 6)) / Math.max(1, n2 - 1)} stroke="#dc2626" strokeWidth="0.8" />)}
    </svg>
  );
}

// ---------------------------------------------------------------- tab
export default function BbsTab({ pid, code }: { pid: number; code: string }) {
  const [list, setList] = useState<any[]>([]);
  const [id, setId] = useState<number | null>(null);
  const [title, setTitle] = useState("BBS – Block A");
  const [members, setMembers] = useState<Member[]>([]);
  const [wastage, setWastage] = useState(3);
  const [res, setRes] = useState<Result | null>(null);
  const [qs, setQs] = useState<string[]>([]);
  const [busy, setBusy] = useState(false);
  const loadList = useCallback(() => api<any[]>(`/api/projects/${pid}/bbs`).then(setList).catch(() => setList([])), [pid]);
  useEffect(() => { loadList(); }, [loadList]);

  const open = async (bid: number) => {
    try {
      const b = await api<any>(`/api/bbs/${bid}`);
      setId(b.id); setTitle(b.title); setMembers(b.members); setRes(b.result); setQs([]); setWastage(b.result?.wastage_pct ?? 3);
    } catch (e: any) { toast(e.message, "err"); }
  };
  const fresh = () => { setId(null); setTitle("BBS – Block A"); setMembers([]); setRes(null); setQs([]); };
  const add = (t: string) => setMembers([...members, newMember(t, members.filter((m) => m.type === t).length + 1)]);
  const upd = (i: number, p: Partial<Member>) => setMembers(members.map((m, j) => (j === i ? { ...m, ...p } : m)));
  const body = () => ({ title, members: members.map((m) => ({ ...m, ...Object.fromEntries(Object.entries(m).map(([k, v]) => [k, Array.isArray(v) ? v.filter((b: any) => b.dia && b.nos) : v])) })), wastage_pct: wastage });
  const run = async (save: boolean) => {
    setBusy(true); setQs([]);
    try {
      if (save) {
        const b = await api<any>(id ? `/api/bbs/${id}` : `/api/projects/${pid}/bbs`, { method: id ? "PUT" : "POST", body: body() });
        setId(b.id); setRes(b.result); toast(id ? "BBS updated" : "BBS saved"); loadList();
      } else setRes(await api<Result>(`/api/projects/${pid}/bbs/calculate`, { body: body() }));
    } catch (e: any) {
      if (e instanceof ApiError && e.questions.length) { setQs(e.questions); setRes(null); } else toast(e.message, "err");
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-4">
      <Card title="Bar Bending Schedule (BBS)" icon={<Calculator size={20} />}
        action={<div className="flex flex-wrap items-center gap-2">
          {list.length > 0 && <select className="input w-auto py-1.5 text-sm" value={id ?? ""} onChange={(e) => (e.target.value ? open(Number(e.target.value)) : fresh())}>
            <option value="">— new BBS —</option>{list.map((b) => <option key={b.id} value={b.id}>{b.title} · {num(b.total_kg, 0)} kg</option>)}</select>}
          {id && <OwnerDelete entity="bbs" id={id} title={title} onDone={() => { fresh(); loadList(); }} />}
        </div>}>
        <div className="grid gap-3 sm:grid-cols-[1fr_160px]">
          <label className="text-xs"><span className="label">Title</span><input className="input" value={title} onChange={(e) => setTitle(e.target.value)} /></label>
          <label className="text-xs"><span className="label">Cutting wastage %</span><input className="input" inputMode="decimal" value={wastage} onChange={(e) => setWastage(Number(e.target.value.replace(/[^0-9.]/g, "")) || 0)} /></label>
        </div>
        <p className="mt-2 text-xs text-slate-500">Enter sizes and bars <b>from your structural drawing</b>. Nothing is assumed – missing values are asked. Blank "IS 13920" fields use the code rule (shown under Assumptions).</p>
        <div className="mt-3 flex flex-wrap gap-2">
          {Object.keys(FIELDS).map((t) => <button key={t} className="btn-outline btn-sm" onClick={() => add(t)}><Plus size={14} />{LABEL[t]}</button>)}
        </div>
      </Card>

      {members.map((m, i) => (
        <Card key={i} title={<span className="flex items-center gap-2"><Badge color="blue">{LABEL[m.type]}</Badge>
          <input className="input w-28 py-1 text-sm" value={m.mark} onChange={(e) => upd(i, { mark: e.target.value })} /></span>}
          action={<button className="btn-ghost btn-sm text-red-600" onClick={() => setMembers(members.filter((_, j) => j !== i))}><Trash2 size={14} />Remove</button>}>
          <div className="grid gap-2.5 sm:grid-cols-2 lg:grid-cols-4">
            {FIELDS[m.type].map(([k, l, ph]) => (
              <label key={k} className="text-xs"><span className="label">{l}</span>
                <input className="input py-1.5" inputMode="decimal" placeholder={ph} value={m[k] ?? ""} onChange={(e) => upd(i, { [k]: e.target.value.replace(/[^0-9.]/g, "") })} /></label>
            ))}
          </div>
          {(BAR_GROUPS[m.type] || []).map(([g, gl]) => (
            <div key={g} className="mt-3">
              <div className="label">{gl}</div>
              <div className="flex flex-wrap gap-2">
                {(m[g] as Bars).map((b, j) => (
                  <span key={j} className="inline-flex items-center gap-1 rounded-lg border border-line p-1">
                    <select className="rounded border-0 bg-transparent text-sm" value={b.dia} onChange={(e) => upd(i, { [g]: (m[g] as Bars).map((x, q) => (q === j ? { ...x, dia: e.target.value } : x)) })}>
                      <option value="">dia</option>{DIAS.map((d) => <option key={d} value={d}>{d} mm</option>)}</select>
                    ×<input className="w-12 rounded border border-line px-1 py-0.5 text-sm" placeholder="nos" value={b.nos} onChange={(e) => upd(i, { [g]: (m[g] as Bars).map((x, q) => (q === j ? { ...x, nos: e.target.value.replace(/\D/g, "") } : x)) })} />
                    <button className="text-slate-400 hover:text-red-600" onClick={() => upd(i, { [g]: (m[g] as Bars).filter((_, q) => q !== j) })}><X size={13} /></button>
                  </span>
                ))}
                <button className="btn-ghost btn-sm" onClick={() => upd(i, { [g]: [...(m[g] as Bars), { dia: "", nos: "" }] })}><Plus size={13} />bar group</button>
              </div>
            </div>
          ))}
        </Card>
      ))}
      {!members.length && <Card><Empty text="Add a column, beam, footing or slab to start." /></Card>}

      {members.length > 0 && (
        <div className="flex flex-wrap justify-end gap-2">
          <button className="btn-outline" onClick={() => run(false)} disabled={busy}><Calculator size={16} />Calculate</button>
          <button className="btn-primary" onClick={() => run(true)} disabled={busy}><Save size={16} />{id ? "Update BBS" : "Save BBS"}</button>
        </div>
      )}
      {qs.length > 0 && (
        <div className="rounded-xl bg-amber-50 p-3 text-sm text-amber-900"><div className="mb-1 flex items-center gap-1 font-semibold"><TriangleAlert size={15} />Please fill these:</div>
          <ul className="list-disc pl-5">{qs.map((q) => <li key={q}>{q}</li>)}</ul></div>
      )}

      {res && (
        <>
          <Card title={`Schedule – ${num(res.total_kg, 0)} kg steel (with ${res.wastage_pct}% wastage)`} icon={<FileSpreadsheet size={20} />}
            action={id ? <div className="flex gap-2">
              <button className="btn-outline btn-sm" onClick={() => downloadFile(`/api/bbs/${id}/excel`, `${code}_BBS.xlsx`).catch((e) => toast(e.message, "err"))}><FileSpreadsheet size={14} />Excel</button>
              <button className="btn-outline btn-sm" onClick={() => downloadFile(`/api/bbs/${id}/pdf`, `${code}_BBS.pdf`).catch((e) => toast(e.message, "err"))}><Download size={14} />PDF (with drawings)</button>
            </div> : <span className="text-xs text-slate-500">Save to download Excel / PDF</span>}>
            <div className="overflow-x-auto rounded-lg border border-line">
              <table className="w-full min-w-[860px]">
                <thead><tr>{["Mark", "Description", "Shape", "Dia", "Nos/member", "Members", "Total nos", "Cut length (mm)", "Total (m)", "Weight (kg)"].map((h) => <th key={h} className="table-th">{h}</th>)}</tr></thead>
                <tbody>{res.rows.map((r, ri) => (
                  <tr key={`${r.mark}${ri}`}><td className="table-td font-semibold">{r.mark}</td><td className="table-td">{r.desc}</td><td className="table-td"><BarShape shape={r.shape} dims={r.dims} /></td>
                    <td className="table-td">{r.dia}</td><td className="table-td">{r.per_member}</td><td className="table-td">{r.members}</td><td className="table-td">{r.nos}</td>
                    <td className="table-td">{num(r.cut_mm, 0)}</td><td className="table-td">{num(r.total_m, 1)}</td><td className="table-td font-semibold">{num(r.kg, 1)}</td></tr>
                ))}</tbody>
              </table>
            </div>
          </Card>
          <div className="grid gap-4 lg:grid-cols-[1fr_1.4fr]">
            <Card title="Steel to order">
              <table className="w-full"><thead><tr>{["Dia", "Length (m)", "Weight (kg)", `+${res.wastage_pct}%`, "12 m bars"].map((h) => <th key={h} className="table-th">{h}</th>)}</tr></thead>
                <tbody>{res.summary.map((s) => <tr key={s.dia}><td className="table-td font-semibold">{s.dia} mm</td><td className="table-td">{num(s.total_m, 1)}</td><td className="table-td">{num(s.kg, 1)}</td><td className="table-td">{num(s.kg_with_wastage, 1)}</td><td className="table-td font-semibold">{s.bars_12m}</td></tr>)}
                  <tr><td className="table-td font-bold">Total</td><td className="table-td" /><td className="table-td" /><td className="table-td font-bold">{num(res.total_kg, 1)} kg</td><td className="table-td" /></tr></tbody></table>
              <ul className="mt-3 space-y-0.5 text-[11px] text-slate-500">{res.assumptions.map((a) => <li key={a}>• {a}</li>)}</ul>
            </Card>
            <Card title="Member drawings (laps, tie zones, mesh)">
              <div className="grid gap-4 sm:grid-cols-2">{res.drawings.map((d, i) => <div key={i} className="rounded-lg border border-line p-2"><MemberDrawing d={d} /></div>)}</div>
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
