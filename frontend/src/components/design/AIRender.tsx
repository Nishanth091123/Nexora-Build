// 1.20 AI Render: the current 3D view → a photo-like concept render (free Cloudflare Workers AI / Gemini quota).
// The 3D picture is the base, so the building keeps the drawing's shape. Every result is stamped
// "AI concept render – not to scale".
import { useState } from "react";
import { Download, Sparkles, X } from "lucide-react";
import { api } from "../../lib/api";
import { toast } from "../ui";
import { stampLabel } from "./house3d/postfx";

type Res = { url: string; provider: string; model: string };
const LABEL = "AI concept render – not to scale";

export default function AIRender({ pid, base, kind, style, light, onClose }: {
  pid: number; base: string; kind: "exterior" | "interior"; style: string; light: string; onClose: () => void;
}) {
  const [extra, setExtra] = useState("");
  const [keep, setKeep] = useState(55);  // % how much of my design to keep
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [res, setRes] = useState<Res[]>([]);
  const [cmp, setCmp] = useState(false);
  const go = async () => {
    setBusy(true); setErr("");
    try {
      const strength = Math.round((0.85 - (keep / 100) * 0.6) * 100) / 100;  // keep 100% → 0.25, keep 0% → 0.85
      const r = await api<any>(`/api/projects/${pid}/ai-render`, { body: { image: base, kind, style, light, extra, strength } });
      const url = await stampLabel(`data:image/png;base64,${r.image_b64}`, LABEL);
      setRes((x) => [{ url, provider: r.provider, model: r.model }, ...x].slice(0, 4));
    } catch (e: any) { setErr(e.message || String(e)); }
    setBusy(false);
  };
  const save = (u: string, i: number) => { const a = document.createElement("a"); a.href = u; a.download = `Nexora_AI_Render_${kind}_${i + 1}.png`; document.body.appendChild(a); a.click(); a.remove(); };
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-3" onClick={onClose}>
      <div className="mt-6 w-full max-w-5xl rounded-2xl bg-white p-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
        <div className="mb-3 flex items-center gap-2">
          <Sparkles size={18} className="text-brand-600" />
          <h3 className="text-lg font-bold text-navy-ink">AI Render – photo-like concept</h3>
          <button className="ml-auto text-slate-500" onClick={onClose} title="Close"><X size={20} /></button>
        </div>
        <p className="mb-3 text-sm text-slate-600">
          Made from this 3D view, so the floors, windows and outline stay as in your drawing. Free AI (Cloudflare Workers AI daily
          allowance). The picture is a <b>concept</b> for the client – always marked “{LABEL}”.
        </p>
        <div className="grid gap-3 md:grid-cols-[1fr_1.2fr]">
          <div>
            <div className="mb-1 text-xs font-semibold text-slate-500">Your 3D view (base)</div>
            <img src={base} alt="3D view" className="w-full rounded-lg border border-line" />
            <label className="mt-3 block text-sm font-semibold text-navy-ink">Add to the look (optional)</label>
            <input className="input mt-1" value={extra} onChange={(e) => setExtra(e.target.value)} maxLength={300}
              placeholder={kind === "interior" ? "e.g. teak wood TV unit, beige sofa, marble floor" : "e.g. grey granite steps, pink bougainvillea, rainy evening"} />
            <label className="mt-3 block text-sm font-semibold text-navy-ink">Keep my design ↔ More creative</label>
            <input type="range" min={0} max={100} value={keep} onChange={(e) => setKeep(Number(e.target.value))} className="w-full accent-brand-600" />
            <div className="flex justify-between text-xs text-slate-500"><span>More creative</span><span>Keep {keep}%</span><span>Exactly my design</span></div>
            <button className="btn-primary mt-3 w-full" onClick={go} disabled={busy}>{busy ? "Rendering… (20–60 s)" : <><Sparkles size={16} />Make AI render</>}</button>
            {err && <p className="mt-2 rounded-lg bg-red-50 p-2 text-sm text-red-700">{err}</p>}
          </div>
          <div>
            {!res.length && <div className="flex h-full min-h-[200px] items-center justify-center rounded-lg border border-dashed border-line text-sm text-slate-500">The render appears here.</div>}
            {res.map((r, i) => (
              <div key={i} className="mb-3">
                {cmp && i === 0 ? (
                  <div className="grid grid-cols-2 gap-1"><img src={base} alt="3D" className="rounded-lg border border-line" /><img src={r.url} alt="AI render" className="rounded-lg border border-line" /></div>
                ) : <img src={r.url} alt="AI render" className="w-full rounded-lg border border-line" />}
                <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                  <span>{r.provider} · {r.model.split("/").pop()}</span>
                  {i === 0 && <button className="btn-ghost btn-sm" onClick={() => setCmp(!cmp)}>{cmp ? "Big picture" : "Compare with 3D"}</button>}
                  <button className="btn-outline btn-sm ml-auto" onClick={() => save(r.url, i)}><Download size={14} />Download</button>
                </div>
              </div>
            ))}
            {res.length > 0 && <p className="text-xs text-slate-500">Not happy? Press “Make AI render” again – every try is different. Free allowance is about 20–50 renders a day.</p>}
          </div>
        </div>
      </div>
    </div>
  );
}
