import OwnerDelete from "../OwnerDelete";
import { useEffect, useMemo, useState } from "react";
import { Check, FileUp, Layers, RefreshCw, Ruler, Save, Sparkles, TriangleAlert, Upload } from "lucide-react";
import { Badge, Card, Empty, Field, toast } from "../ui";
import { api, ApiError, fileObjectUrl, fmtDateTime } from "../../lib/api";
import { ROOM_TYPES, clone, type Plan } from "../../lib/plan";
import NorthDial from "./NorthDial";
import PlanSvg from "./PlanSvg";

type XRoom = { id: string; type: string; name: string; x: number; y: number; w: number; d: number; placed: boolean;
  confidence?: number; note?: string; stated?: string; group?: number; include?: boolean };
type Analysis = {
  id: number; file_id: number; file_name: string; method: string; model: string; status: string; design_id: number | null;
  created_at: string; rooms: number;
  result?: { rooms: XRoom[]; groups?: { id: number; name: string; rooms: number }[]; notes: string[]; preview: number[][];
    to_ft: number | null; north_deg?: number | null; plot?: { w: number; d: number } | null };
  questions?: string[]; warnings?: string[]; info?: any;
};
const FLOOR_ORDER = ["Stilt / Parking", "Ground Floor", "First Floor", "Second Floor", "Third Floor"];
const METHOD: Record<string, string> = { dxf: "DXF – exact lines & text", pdf: "Vector PDF – lines & text", "pdf-vision": "Scanned PDF – AI vision", "image-vision": "Picture – AI vision" };

function LinesPreview({ lines }: { lines: number[][] }) {
  if (!lines.length) return <Empty text="No line preview for this file type." />;
  const xs = lines.flatMap((l) => [l[0], l[2]]), ys = lines.flatMap((l) => [l[1], l[3]]);
  const x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(...ys), y1 = Math.max(...ys);
  const pad = (x1 - x0) * 0.03 + 1;
  return (
    <svg viewBox={`${x0 - pad} ${-y1 - pad} ${x1 - x0 + 2 * pad} ${y1 - y0 + 2 * pad}`} className="h-[420px] w-full bg-white">
      {lines.map((l, i) => <line key={i} x1={l[0]} y1={-l[1]} x2={l[2]} y2={-l[3]} stroke="#1e293b" strokeWidth={(x1 - x0) / 900} />)}
    </svg>
  );
}

export default function DrawingImport({ projectId, onSaved, designs = [] }: {
  projectId: number; onSaved?: (d: any) => void; designs?: { id: number; version: number; title: string }[];
}) {
  const [busy, setBusy] = useState("");
  const [files, setFiles] = useState<any[]>([]);
  const [history, setHistory] = useState<Analysis[]>([]);
  const [an, setAn] = useState<Analysis | null>(null);
  const [rooms, setRooms] = useState<XRoom[]>([]);
  const [groupNames, setGroupNames] = useState<Record<number, string>>({});
  const [orig, setOrig] = useState<string | null>(null);
  const [opts, setOpts] = useState<any>({ north_deg: 0, road_side: "bottom", plot_w_ft: "", plot_d_ft: "", road_ft: "", front_gap_ft: "", left_gap_ft: "", floor_height_ft: 10 });
  const [northOk, setNorthOk] = useState(false);
  const [preview, setPreview] = useState<Plan | null>(null);
  const [pLevel, setPLevel] = useState(0);
  const [knownW, setKnownW] = useState("");
  const [appendTo, setAppendTo] = useState<number | "">("");
  const [page, setPage] = useState(0);

  const loadLists = async () => {
    try {
      setFiles((await api<any[]>(`/api/files/project/${projectId}?category=drawing`)).filter((f) => /\.(dxf|pdf|png|jpe?g|webp)$/i.test(f.name)));
      setHistory(await api<Analysis[]>(`/api/projects/${projectId}/analyses`));
    } catch { /* lists are optional */ }
  };
  useEffect(() => { loadLists(); }, [projectId]);
  useEffect(() => {  // opened from the AI assistant: /design?tab=upload&analysis=ID
    const id = Number(new URLSearchParams(window.location.search).get("analysis")) || 0;
    if (id) api<Analysis>(`/api/analyses/${id}`).then(take).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  const take = (a: Analysis) => {
    setAn(a); setPreview(null); setNorthOk(false);
    const rs = (a.result?.rooms || []).map((r) => ({ ...r, include: true }));
    setRooms(rs);
    setGroupNames(Object.fromEntries((a.result?.groups || [{ id: 0, name: "Ground Floor", rooms: rs.length }]).map((g) => [g.id, g.name])));
    if (a.result?.north_deg != null) setOpts((o: any) => ({ ...o, north_deg: Number(a.result!.north_deg) || 0 }));
    if (a.result?.plot) setOpts((o: any) => ({ ...o, plot_w_ft: a.result!.plot!.w, plot_d_ft: a.result!.plot!.d }));
    setOrig(null);
    if (a.file_id && !/\.dxf$/i.test(a.file_name)) fileObjectUrl(`/api/files/${a.file_id}/download`).then(setOrig).catch(() => {});
  };

  const upload = async (file: File) => {
    const fd = new FormData(); fd.append("file", file); fd.append("page", String(page));
    setBusy("upload");
    try { const a = await api<Analysis>(`/api/projects/${projectId}/drawings/upload`, { form: fd }); take(a); toast(`${a.rooms} rooms read from ${a.file_name}`); loadLists(); }
    catch (e: any) { toast(e instanceof ApiError && e.questions.length ? `${e.message} – ${e.questions.join(" ")}` : e.message, "err"); }
    finally { setBusy(""); }
  };
  const analyseExisting = async (id: number) => {
    setBusy("upload");
    try { const a = await api<Analysis>(`/api/files/${id}/analyse?page=${page}`, { method: "POST" }); take(a); loadLists(); }
    catch (e: any) { toast(e.message, "err"); } finally { setBusy(""); }
  };
  const rescale = async (body: any) => {
    if (!an) return;
    try { const a = await api<Analysis>(`/api/analyses/${an.id}/rescale`, { body }); take(a); toast("Re-measured"); }
    catch (e: any) { toast(e.message, "err"); }
  };

  const groups = an?.result?.groups?.length ? an.result.groups : [{ id: 0, name: "Ground Floor", rooms: rooms.length }];
  const levels = useMemo(() => {
    const gs = groups.filter((g) => groupNames[g.id] && groupNames[g.id] !== "skip");
    gs.sort((a, b) => FLOOR_ORDER.indexOf(groupNames[a.id]) - FLOOR_ORDER.indexOf(groupNames[b.id]));
    return gs.map((g) => ({ name: groupNames[g.id], rooms: rooms.filter((r) => (r.group ?? 0) === g.id && r.include) }));
  }, [groups, groupNames, rooms]);
  const body = () => ({
    levels, title: "",
    opts: { ...opts, road_width_m: opts.road_ft ? Math.round(Number(opts.road_ft) * 0.3048 * 100) / 100 : "", levels_count: levels.length },
  });
  const doPreview = async () => {
    if (!an) return;
    setBusy("preview");
    try { setPreview(await api<Plan>(`/api/analyses/${an.id}/preview`, { body: body() })); setPLevel(0); }
    catch (e: any) { toast(e.message, "err"); } finally { setBusy(""); }
  };
  const save = async () => {
    if (!an) return;
    if (!northOk) return toast("Confirm the north direction first (tick the box under the dial)", "err");
    if (an.result?.north_deg == null && Number(opts.north_deg) === 0 &&
        !window.confirm("North arrow is set to 0° (north = top of the drawing). Vastu results depend on this – is it correct?")) return;
    const title = window.prompt("Name for this design", `From drawing ${an.file_name}`);
    if (title === null) return;
    setBusy("save");
    try {
      const d = await api<any>(`/api/analyses/${an.id}/confirm`, { body: { ...body(), title, append_to_design_id: appendTo || null } });
      toast(`Saved as design v${d.version}`); loadLists(); onSaved?.(d);
    } catch (e: any) { toast(e.message, "err"); } finally { setBusy(""); }
  };
  const setRoom = (i: number, patch: Partial<XRoom>) => { const a = clone(rooms); a[i] = { ...a[i], ...patch }; setRooms(a); };

  return (
    <div className="space-y-4">
      <Card title="Upload Drawing" icon={<Upload size={20} />}>
        <label className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-brand-100 bg-brand-50/40 px-4 py-6 text-center hover:bg-brand-50"
          onDragOver={(e) => e.preventDefault()} onDrop={(e) => { e.preventDefault(); const f = e.dataTransfer.files?.[0]; if (f) upload(f); }}>
          <FileUp size={30} className="text-brand-600" />
          <div className="text-sm font-semibold text-navy-ink">Upload your drawing (DXF, PDF, PNG, JPG)</div>
          <div className="text-xs text-slate-500">or drag and drop here · DWG: save as DXF 2018 first · DXF gives exact sizes</div>
          <span className="btn-primary btn-sm mt-1">{busy === "upload" ? "Reading the drawing…" : "Choose File"}</span>
          <input type="file" className="hidden" accept=".dxf,.pdf,.png,.jpg,.jpeg,.webp" onChange={(e) => { const f = e.target.files?.[0]; if (f) upload(f); e.target.value = ""; }} />
        </label>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-sm">
          <span className="text-slate-500">Or use an uploaded drawing:</span>
          <select className="input w-auto min-w-[200px] flex-1 py-1.5" defaultValue="" onChange={(e) => e.target.value && analyseExisting(Number(e.target.value))}>
            <option value="">— choose —</option>{files.map((f) => <option key={f.id} value={f.id}>{f.name} (v{f.version})</option>)}
          </select>
          <label className="flex items-center gap-1 text-xs text-slate-500">PDF page<input type="number" min={1} className="input w-16 py-1" value={page + 1} onChange={(e) => setPage(Math.max(0, Number(e.target.value) - 1))} /></label>
        </div>
        {history.length > 0 && (
          <div className="mt-3 text-xs text-slate-500">Earlier reads:{" "}
            {history.slice(0, 6).map((h) => <span key={h.id} className="mr-2 inline-flex items-center"><button className="underline hover:text-brand-600" onClick={async () => take(await api(`/api/analyses/${h.id}`))}>{h.file_name} ({h.rooms} rooms, {fmtDateTime(h.created_at)}{h.status === "confirmed" ? ", saved" : ""})</button><OwnerDelete entity="analysis" id={h.id} title={h.file_name} onDone={loadLists} /></span>)}
          </div>
        )}
      </Card>

      {an && (
        <>
          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <Card title={`Your drawing – ${an.file_name}`} icon={<Layers size={20} />}>
              {/\.dxf$/i.test(an.file_name) || an.method === "pdf" ? <LinesPreview lines={an.result?.preview || []} />
                : orig ? (/\.pdf$/i.test(an.file_name) ? <iframe src={orig} className="h-[420px] w-full rounded-lg border border-line" title="drawing" />
                  : <img src={orig} alt="drawing" className="max-h-[420px] w-full rounded-lg object-contain" />) : <Empty text="Loading preview…" />}
            </Card>
            <Card title="What was read" icon={<Sparkles size={20} />}>
              <div className="flex flex-wrap gap-2"><Badge color="blue">{METHOD[an.method] || an.method}</Badge>{an.model && <Badge color="purple">{an.model}</Badge>}
                <Badge color="gray">{rooms.length} rooms</Badge>{an.info?.scale_source && <Badge color="green">Scale: {an.info.scale_source}</Badge>}</div>
              {(an.questions?.length || 0) > 0 && (
                <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
                  <div className="mb-1 flex items-center gap-2 font-semibold"><TriangleAlert size={15} />Please confirm</div>
                  <ul className="list-disc space-y-0.5 pl-5">{an.questions!.map((q) => <li key={q}>{q}</li>)}</ul>
                </div>
              )}
              {(an.result?.notes?.length || 0) > 0 && <ul className="mt-3 space-y-1 text-sm text-slate-600">{an.result!.notes.map((n) => <li key={n}>• {n}</li>)}</ul>}
              {(an.method === "dxf" || an.method === "pdf") && (
                <div className="mt-4 grid gap-3 sm:grid-cols-2">
                  {an.method === "dxf" && <Field label="Drawing units">
                    <div className="flex gap-2"><select className="input" defaultValue={an.info?.units || "ft"} id="dxfunits">{["mm", "cm", "m", "ft", "in"].map((u) => <option key={u}>{u}</option>)}</select>
                      <button className="btn-outline btn-sm" onClick={() => rescale({ units: (document.getElementById("dxfunits") as HTMLSelectElement).value })}>Apply</button></div>
                  </Field>}
                  <Field label="Known width of the first drawing (ft)">
                    <div className="flex gap-2"><input className="input" type="number" value={knownW} onChange={(e) => setKnownW(e.target.value)} placeholder="e.g. 24" />
                      <button className="btn-outline btn-sm" disabled={!knownW} onClick={() => rescale({ building_width_ft: Number(knownW) })}><Ruler size={14} />Scale</button></div>
                  </Field>
                </div>
              )}
              {groups.length > 0 && (
                <div className="mt-4">
                  <div className="mb-1 text-xs font-semibold text-slate-500">Floors on this sheet</div>
                  <div className="flex flex-wrap gap-2">
                    {groups.map((g) => (
                      <label key={g.id} className="flex items-center gap-2 rounded-lg border border-line px-2 py-1 text-sm">
                        Drawing {g.id + 1} ({g.rooms} rooms) =
                        <select className="input w-auto py-1 text-xs" value={groupNames[g.id] || "skip"} onChange={(e) => setGroupNames({ ...groupNames, [g.id]: e.target.value })}>
                          {FLOOR_ORDER.map((f) => <option key={f}>{f}</option>)}<option value="skip">Skip (not a floor)</option>
                        </select>
                      </label>
                    ))}
                  </div>
                </div>
              )}
            </Card>
          </div>

          <Card title="Rooms read – check every row" icon={<Check size={20} />}
            action={<button className="btn-outline btn-sm" onClick={() => setRooms([...rooms, { id: `n${Date.now() % 100000}`, type: "bedroom", name: "Bedroom", x: 0, y: 0, w: 10, d: 10, placed: false, include: true, group: groups[0]?.id ?? 0, note: "Added by you – place it in the 2D editor" }])}>+ Add room</button>}>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[900px]">
                <thead><tr>{["Use", "Floor", "Name", "Type", "Width ft", "Depth ft", "From left", "From bottom", "Written", "Note"].map((h) => <th key={h} className="table-th">{h}</th>)}</tr></thead>
                <tbody>
                  {rooms.map((r, i) => (
                    <tr key={r.id} className={(r.confidence ?? 1) < 0.6 ? "bg-amber-50" : ""}>
                      <td className="table-td"><input type="checkbox" className="h-4 w-4 accent-brand-600" checked={!!r.include} onChange={(e) => setRoom(i, { include: e.target.checked })} /></td>
                      <td className="table-td"><select className="input w-auto py-1 text-xs" value={r.group ?? 0} onChange={(e) => setRoom(i, { group: Number(e.target.value) })}>{groups.map((g) => <option key={g.id} value={g.id}>{groupNames[g.id] || `Drawing ${g.id + 1}`}</option>)}</select></td>
                      <td className="table-td"><input className="input py-1" value={r.name} onChange={(e) => setRoom(i, { name: e.target.value })} /></td>
                      <td className="table-td"><select className="input py-1 text-xs" value={r.type} onChange={(e) => setRoom(i, { type: e.target.value })}>{ROOM_TYPES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></td>
                      {(["w", "d", "x", "y"] as const).map((k) => (
                        <td key={k} className="table-td"><input type="number" step={0.25} className="input w-20 py-1" value={r[k]} onChange={(e) => setRoom(i, { [k]: Number(e.target.value) } as any)} /></td>
                      ))}
                      <td className="table-td text-xs">{r.stated || "—"}</td>
                      <td className="table-td max-w-[260px] text-xs text-amber-800">{r.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-[380px_1fr]">
            <Card title="Direction & plot" icon={<RefreshCw size={20} />}>
              <NorthDial value={opts.north_deg} onChange={(v) => { setOpts({ ...opts, north_deg: v }); setNorthOk(true); }} />
              <label className="mt-2 flex items-center gap-2 text-sm"><input type="checkbox" className="h-4 w-4 accent-brand-600" checked={northOk} onChange={(e) => setNorthOk(e.target.checked)} />I confirm the north direction</label>
              <div className="mt-3 grid grid-cols-2 gap-3">
                <Field label="Road is on the drawing's" className="col-span-2">
                  <select className="input" value={opts.road_side} onChange={(e) => setOpts({ ...opts, road_side: e.target.value })}>
                    <option value="bottom">Bottom side</option><option value="top">Top side</option><option value="left">Left side</option><option value="right">Right side</option>
                  </select>
                </Field>
                <Field label="Plot frontage ft"><input className="input" type="number" value={opts.plot_w_ft} onChange={(e) => setOpts({ ...opts, plot_w_ft: e.target.value })} placeholder="optional" /></Field>
                <Field label="Plot depth ft"><input className="input" type="number" value={opts.plot_d_ft} onChange={(e) => setOpts({ ...opts, plot_d_ft: e.target.value })} placeholder="optional" /></Field>
                <Field label="Road width ft"><input className="input" type="number" value={opts.road_ft} onChange={(e) => setOpts({ ...opts, road_ft: e.target.value })} placeholder="for setback check" /></Field>
                <Field label="Floor height ft"><input className="input" type="number" value={opts.floor_height_ft} onChange={(e) => setOpts({ ...opts, floor_height_ft: Number(e.target.value) || 10 })} /></Field>
                <Field label="Gap from road ft"><input className="input" type="number" value={opts.front_gap_ft} onChange={(e) => setOpts({ ...opts, front_gap_ft: e.target.value })} placeholder="auto" /></Field>
                <Field label="Gap on left ft"><input className="input" type="number" value={opts.left_gap_ft} onChange={(e) => setOpts({ ...opts, left_gap_ft: e.target.value })} placeholder="auto" /></Field>
              </div>
              <p className="mt-2 text-xs text-slate-500">With plot + road width, Tamil Nadu setbacks are checked against your drawing.</p>
            </Card>
            <Card title="Preview as a Nexora plan" icon={<Layers size={20} />}
              action={<div className="flex flex-wrap gap-2">
                <button className="btn-outline btn-sm" onClick={doPreview} disabled={busy !== ""}><RefreshCw size={14} />{busy === "preview" ? "Working…" : "Update preview"}</button>
                {designs.length > 0 && <select className="input w-auto py-1 text-xs" value={appendTo} onChange={(e) => setAppendTo(e.target.value ? Number(e.target.value) : "")}>
                  <option value="">Save as a new design</option>{designs.map((d) => <option key={d.id} value={d.id}>Add as upper floor(s) to v{d.version} – {d.title}</option>)}</select>}
                <button className="btn-primary btn-sm" onClick={save} disabled={busy !== ""}><Save size={14} />Save as design</button>
              </div>}>
              {!preview ? <Empty text="Check the rooms and the north direction, then press “Update preview”." /> : (
                <>
                  <div className="mb-2 flex flex-wrap gap-2">{preview.levels.map((l, i) => <button key={i} onClick={() => setPLevel(i)} className={`rounded-lg px-3 py-1 text-xs font-medium ${i === pLevel ? "bg-navy-900 text-white" : "bg-slate-100"}`}>{l.name}</button>)}</div>
                  <div className="aspect-square max-h-[560px] w-full rounded-lg border border-line bg-white p-1"><PlanSvg plan={preview} level={Math.min(pLevel, preview.levels.length - 1)} /></div>
                  {preview.warnings.length > 0 && <ul className="mt-2 space-y-1 text-sm text-amber-800">{preview.warnings.map((w, i) => <li key={i}>• {w}</li>)}</ul>}
                  <p className="mt-2 text-xs text-slate-500">After saving, the plan opens in Design Studio – edit it in the 2D editor, see 3D, estimate and Vastu.</p>
                </>
              )}
            </Card>
          </div>
        </>
      )}
    </div>
  );
}
