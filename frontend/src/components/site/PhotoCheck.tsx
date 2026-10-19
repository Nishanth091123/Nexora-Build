import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, RefreshCw, ScanSearch, TriangleAlert } from "lucide-react";
import { Badge, toast } from "../ui";
import { api } from "../../lib/api";

export type PhotoResult = {
  photo_type?: string; photo_ok?: boolean; overall?: string; note?: string;
  findings: { issue: string; where?: string; severity?: string; confidence?: string; likely_cause?: string; what_to_check?: string; suggested_fix?: string }[];
  good_points?: string[]; cannot_judge?: string[];
};
const SEV: Record<string, string> = { high: "red", medium: "amber", low: "blue" };

/** Shows an AI photo-check result (findings with severity + confidence). */
export function PhotoResultView({ r, provider, sources }: { r: PhotoResult; provider?: string; sources?: { id: string; title: string; ref: string }[] }) {
  return (
    <div className="space-y-2 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <ScanSearch size={17} className="text-violet-600" /><b className="text-navy-ink">AI photo check</b>
        {r.photo_type && <Badge color="purple">{r.photo_type}</Badge>}
        {r.photo_ok === false && <Badge color="amber">Photo not clear enough</Badge>}
      </div>
      {r.overall && <p className="text-slate-700">{r.overall}</p>}
      {r.findings.length === 0 && <p className="flex items-center gap-1.5 text-emerald-700"><CheckCircle2 size={15} />No clear problem seen in this photo.</p>}
      {r.findings.map((f, i) => (
        <div key={i} className="rounded-lg border border-line p-2.5">
          <div className="flex flex-wrap items-center gap-2"><TriangleAlert size={14} className="text-amber-500" /><b className="text-navy-ink">{f.issue}</b>
            {f.severity && <Badge color={SEV[f.severity] || "gray"}>{f.severity}</Badge>}
            {f.confidence && <span className="text-[11px] text-slate-500">confidence: {f.confidence}</span>}</div>
          {f.where && <div className="text-xs text-slate-500">Where: {f.where}</div>}
          {f.likely_cause && <div className="text-xs"><b>Likely cause:</b> {f.likely_cause}</div>}
          {f.what_to_check && <div className="text-xs"><b>Check on site:</b> {f.what_to_check}</div>}
          {f.suggested_fix && <div className="text-xs"><b>Fix:</b> {f.suggested_fix}</div>}
        </div>
      ))}
      {!!r.good_points?.length && <div className="text-xs text-emerald-700">Good: {r.good_points.join("; ")}</div>}
      {!!r.cannot_judge?.length && <div className="text-xs text-slate-500">Needs a site check / test: {r.cannot_judge.join("; ")}</div>}
      {!!sources?.length && <div className="text-[11px] text-slate-500">Read more: {sources.map((s) => `${s.title} (${s.ref})`).join(" · ")}</div>}
      <div className="text-[11px] italic text-slate-400">{r.note || "AI guidance from one photo – confirm on site."}{provider && ` · ${provider}`}</div>
    </div>
  );
}

/** "AI check" button for one stored photo; shows the saved result if the photo was checked before. */
export default function PhotoCheckButton({ fileId }: { fileId: number }) {
  const [res, setRes] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    setRes(null);
    api<any>(`/api/ai/photo-check/${fileId}`).then((r) => r && setRes(r)).catch(() => {});
  }, [fileId]);
  const run = async (force = false) => {
    setBusy(true);
    try { setRes(await api<any>("/api/ai/photo-check", { body: { file_id: fileId, force } })); }
    catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  return (
    <>
      {!res && <button className="btn-outline btn-sm" onClick={() => run()} disabled={busy}>{busy ? <Loader2 size={14} className="animate-spin" /> : <ScanSearch size={14} />}{busy ? "Checking (≈10 s)…" : "AI check"}</button>}
      {res && <button className="btn-ghost btn-sm" onClick={() => run(true)} disabled={busy}><RefreshCw size={14} className={busy ? "animate-spin" : ""} />Check again</button>}
      {res && <div className="mt-2 w-full rounded-xl bg-violet-50/50 p-3"><PhotoResultView r={res.result} provider={res.provider} sources={res.sources} /></div>}
    </>
  );
}
