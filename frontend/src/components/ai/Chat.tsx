import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";
import { Bot, CheckCheck, Copy, FileText, Loader2, Mic, Paperclip, RotateCcw, Send, Square, ThumbsDown, ThumbsUp, TriangleAlert, X } from "lucide-react";
import { Avatar, toast } from "../ui";
import { api } from "../../lib/api";
import { CardView, Sources, type CardCtx } from "./Cards";
import Markdown from "./Markdown";
import type { Links, Msg, SendOpts } from "./types";

export type ChatHandle = { send: (o: SendOpts) => void; newChat: () => void };
type Props = {
  pid: number | null; code: string; perms: Record<string, boolean>; agent: string; agentName: string; agentDesc: string;
  convId: number | null; setConvId: (id: number | null) => void; onChanged: () => void; userName: string;
  answerLang: string; setAnswerLang: (l: string) => void; welcomePrompts: string[];
};

const DEFAULT_CHIPS = ["Suggest 1st floor plan", "Add Vastu improvements", "Calculate cost estimate", "Compare with 2BHK plan", "Which cement for slab?"];
const time = (iso: string) => new Date(iso).toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" });

const Chat = forwardRef<ChatHandle, Props>(function Chat(p, ref) {
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const [att, setAtt] = useState<{ id: number; name: string } | null>(null);
  const [uploading, setUploading] = useState(false);
  const [rec, setRec] = useState<{ r: MediaRecorder; started: number } | null>(null);
  const [recSecs, setRecSecs] = useState(0);
  const [transcribing, setTranscribing] = useState(false);
  const [openSrc, setOpenSrc] = useState<Record<number, number | null>>({});
  const [failed, setFailed] = useState<SendOpts | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const loadedFor = useRef<number | null>(null);

  const scroll = () => setTimeout(() => listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" }), 60);

  useEffect(() => {
    if (!p.convId) { setMsgs([]); loadedFor.current = null; return; }
    if (loadedFor.current === p.convId) return;
    loadedFor.current = p.convId;
    api<any>(`/api/ai/conversations/${p.convId}`).then((c) => { setMsgs(c.messages); scroll(); })
      .catch((e) => { toast(e.message, "err"); p.setConvId(null); });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [p.convId]);

  const send = useCallback(async (o: SendOpts) => {
    const body = (o.text ?? "").trim();
    if (busy || (!body && !o.form && !o.attachment)) return;
    setBusy(true); setFailed(null);
    const now = new Date().toISOString();
    const temp: Msg = { id: -Date.now(), conversation_id: p.convId || 0, role: "user", content: body || o.form?.label || (o.attachment ? `Attached ${o.attachment.name}` : ""),
      cards: [], sources: [], tool: "", provider: "", language: "", feedback: 0, chips: [], notes: [], created_at: now,
      attachment: o.attachment ? { id: o.attachment.id, name: o.attachment.name, url: "" } : null };
    setMsgs((m) => [...m, temp]); scroll();
    try {
      const r = await api<any>("/api/ai/chat", { body: {
        conversation_id: p.convId, project_id: p.pid, agent: o.agent || p.agent, text: body, form: o.form || null,
        attachment_file_id: o.attachment?.id || null, language: p.answerLang || null } });
      setMsgs((m) => [...m.filter((x) => x.id !== temp.id), r.user_message, r.assistant_message]);
      if (r.conversation.id !== p.convId) { loadedFor.current = r.conversation.id; p.setConvId(r.conversation.id); }
      p.onChanged();
      scroll();
    } catch (e: any) {
      setMsgs((m) => m.filter((x) => x.id !== temp.id));
      setFailed(o);
      if (e.message) toast(e.message, "err");
    } finally { setBusy(false); }
  }, [busy, p]);

  useImperativeHandle(ref, () => ({ send, newChat: () => { p.setConvId(null); setMsgs([]); setText(""); setAtt(null); } }), [send, p]);

  const submit = () => {
    if (!text.trim() && !att) return;
    send({ text, attachment: att });
    setText(""); setAtt(null);
  };

  // ---------------- attachments
  const upload = async (f: File) => {
    setUploading(true);
    try {
      const fd = new FormData();
      if (p.pid) fd.append("project_id", String(p.pid));
      fd.append("file", f);
      const r = await api<any>("/api/ai/upload", { form: fd });
      setAtt({ id: r.id, name: r.name });
    } catch (e: any) { toast(e.message, "err"); } finally { setUploading(false); if (fileRef.current) fileRef.current.value = ""; }
  };

  // ---------------- voice (Groq Whisper on the server)
  useEffect(() => {
    if (!rec) return;
    const iv = setInterval(() => setRecSecs(Math.round((Date.now() - rec.started) / 1000)), 500);
    return () => clearInterval(iv);
  }, [rec]);
  const startRec = async () => {
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      toast("Voice needs the app on https or localhost (and a browser with microphone support).", "err"); return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const type = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg"].find((t) => MediaRecorder.isTypeSupported?.(t)) || "";
      const r = new MediaRecorder(stream, type ? { mimeType: type } : undefined);
      const chunks: Blob[] = [];
      r.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      r.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        const blob = new Blob(chunks, { type: r.mimeType || "audio/webm" });
        if (blob.size < 1500) { toast("Too short – hold the mic a little longer.", "err"); return; }
        setTranscribing(true);
        try {
          const fd = new FormData();
          fd.append("audio", blob, `voice.${(r.mimeType || "audio/webm").includes("mp4") ? "m4a" : "webm"}`);
          fd.append("language", p.answerLang === "ta" ? "ta" : p.answerLang === "en" ? "en" : "");
          const out = await api<{ text: string }>("/api/ai/transcribe", { form: fd });
          setText((t) => (t ? t + " " : "") + out.text);
        } catch (e: any) { toast(e.message, "err"); } finally { setTranscribing(false); }
      };
      r.start();
      setRecSecs(0);
      setRec({ r, started: Date.now() });
    } catch { toast("Microphone permission was denied.", "err"); }
  };
  const stopRec = () => { rec?.r.stop(); setRec(null); };

  const feedback = async (m: Msg, v: number) => {
    const val = m.feedback === v ? 0 : v;
    setMsgs((all) => all.map((x) => (x.id === m.id ? { ...x, feedback: val } : x)));
    try { await api(`/api/ai/messages/${m.id}/feedback`, { body: { value: val } }); } catch { /* ignore */ }
  };
  const lastAssistant = [...msgs].reverse().find((m) => m.role === "assistant");
  const chips = lastAssistant?.chips?.length ? lastAssistant.chips : DEFAULT_CHIPS;

  return (
    <section className="card flex min-h-[560px] min-w-0 flex-col xl:h-[80vh]">
      <div ref={listRef} className="min-h-0 flex-1 space-y-5 overflow-y-auto px-3 py-4 sm:px-5">
        {!msgs.length && (
          <div className="mx-auto max-w-xl py-8 text-center">
            <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-navy-900 text-white"><Bot size={28} /></div>
            <h2 className="mt-3 text-lg font-bold text-navy-ink">{p.agentName}</h2>
            <p className="text-sm text-slate-500">{p.agentDesc}. Ask in English, தமிழ் or Tanglish – type or use the mic.</p>
            <div className="mt-4 grid gap-2 sm:grid-cols-2">
              {p.welcomePrompts.map((w) => <button key={w} onClick={() => send({ text: w })} className="rounded-xl border border-line bg-white px-3 py-2.5 text-left text-[13px] text-navy-ink shadow-card hover:border-brand-600">{w}</button>)}
            </div>
          </div>
        )}
        {msgs.map((m, i) => m.role === "user" ? (
          <div key={m.id} className="flex items-start justify-end gap-2.5">
            <div className="max-w-[85%] rounded-2xl rounded-tr-sm border border-brand-100 bg-brand-50 px-4 py-2.5 text-[14px] text-navy-ink">
              {m.attachment && <div className="mb-1 inline-flex items-center gap-1 rounded-md bg-white px-2 py-0.5 text-xs font-semibold text-brand-700"><FileText size={13} />{m.attachment.name}</div>}
              <div className="whitespace-pre-wrap">{m.content}</div>
              <div className="mt-1 flex items-center justify-end gap-1 text-[11px] text-slate-500">{time(m.created_at)}{m.id > 0 && <CheckCheck size={13} className="text-brand-600" />}</div>
            </div>
            <Avatar name={p.userName} size={34} />
          </div>
        ) : (
          <div key={m.id} className="flex items-start gap-2.5">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-navy-900 text-white"><Bot size={19} /></div>
            <div className="min-w-0 flex-1 space-y-3 rounded-2xl rounded-tl-sm border border-line bg-white p-3 shadow-card sm:p-4">
              {m.cards.filter((c) => c.type === "plan").map((c, j) => <CardView key={`p${j}`} card={c} ctx={ctxFor(m, i === msgs.length - 1)} />)}
              {m.content && <Markdown text={m.content} onCite={(n) => setOpenSrc({ ...openSrc, [m.id]: n })} />}
              {m.cards.filter((c) => c.type !== "plan").map((c, j) => <CardView key={j} card={c} ctx={ctxFor(m, i === msgs.length - 1)} />)}
              {m.notes?.map((n) => <div key={n} className="flex items-center gap-1.5 rounded-lg bg-amber-50 px-3 py-1.5 text-xs text-amber-800"><TriangleAlert size={13} />{n}</div>)}
              <Sources sources={m.sources} open={openSrc[m.id] ?? null} setOpen={(n) => setOpenSrc({ ...openSrc, [m.id]: n })} />
              <div className="flex flex-wrap items-center justify-end gap-2 text-[11px] text-slate-400">
                {m.provider && <span title="AI model used">{m.provider.split("/").slice(0, 2).join(" · ")}</span>}
                <span>{time(m.created_at)}</span>
                <button title="Copy" onClick={() => navigator.clipboard?.writeText(m.content).then(() => toast("Copied"))} className="hover:text-brand-600"><Copy size={14} /></button>
                <button title="Helpful" onClick={() => feedback(m, 1)} className={m.feedback === 1 ? "text-emerald-600" : "hover:text-brand-600"}><ThumbsUp size={15} /></button>
                <button title="Not helpful" onClick={() => feedback(m, -1)} className={m.feedback === -1 ? "text-red-600" : "hover:text-brand-600"}><ThumbsDown size={15} /></button>
              </div>
            </div>
          </div>
        ))}
        {busy && (
          <div className="flex items-center gap-2.5">
            <div className="flex h-9 w-9 items-center justify-center rounded-full bg-navy-900 text-white"><Bot size={19} /></div>
            <div className="flex items-center gap-2 rounded-2xl border border-line bg-white px-4 py-2.5 text-sm text-slate-500 shadow-card"><Loader2 size={16} className="animate-spin text-brand-600" />Thinking – calculating with Nexora engines…</div>
          </div>
        )}
        {failed && !busy && (
          <div className="flex justify-center"><button className="btn-outline btn-sm" onClick={() => send(failed)}><RotateCcw size={14} />Send again</button></div>
        )}
      </div>

      <div className="border-t border-line p-3 sm:p-4">
        {att && <div className="mb-2 inline-flex items-center gap-1.5 rounded-lg bg-brand-50 px-2.5 py-1 text-xs font-semibold text-brand-700"><FileText size={14} />{att.name}<button onClick={() => setAtt(null)} aria-label="Remove"><X size={13} /></button></div>}
        <div className="flex items-end gap-2">
          <div className="flex min-w-0 flex-1 items-end gap-1 rounded-xl border border-line bg-white px-2 py-1.5 focus-within:border-brand-500 focus-within:ring-2 focus-within:ring-brand-100">
            <button className="rounded-lg p-2 text-slate-500 hover:bg-slate-100" title="Attach drawing / document" onClick={() => fileRef.current?.click()} disabled={uploading}>
              {uploading ? <Loader2 size={18} className="animate-spin" /> : <Paperclip size={18} />}
            </button>
            <input ref={fileRef} type="file" hidden accept=".pdf,.dxf,.png,.jpg,.jpeg,.webp,.docx,.xlsx,.csv,.txt" onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])} />
            <textarea rows={1} value={text} onChange={(e) => setText(e.target.value)} placeholder={rec ? `Listening… ${recSecs}s – tap stop when done` : transcribing ? "Converting your voice…" : "Ask anything about your project..."}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
              className="max-h-40 min-h-[38px] flex-1 resize-none bg-transparent px-1 py-2 text-[14px] outline-none" />
            <button className={`rounded-lg p-2 ${rec ? "animate-pulse bg-red-50 text-red-600" : "text-slate-500 hover:bg-slate-100"}`} title={rec ? "Stop" : "Speak (Tamil / English)"}
              onClick={rec ? stopRec : startRec} disabled={transcribing}>
              {transcribing ? <Loader2 size={18} className="animate-spin" /> : rec ? <Square size={18} /> : <Mic size={18} />}
            </button>
          </div>
          <button className="flex h-[52px] w-[52px] shrink-0 items-center justify-center rounded-xl bg-brand-600 text-white shadow-card hover:bg-brand-700 disabled:opacity-50" onClick={submit} disabled={busy || (!text.trim() && !att)} aria-label="Send">
            <Send size={20} />
          </button>
        </div>
        <div className="no-scrollbar mt-2.5 flex items-center gap-2 overflow-x-auto">
          <select className="rounded-lg border border-line bg-white px-2 py-1.5 text-xs text-navy-ink" value={p.answerLang} onChange={(e) => p.setAnswerLang(e.target.value)} title="Answer language">
            <option value="">Auto language</option><option value="en">English</option><option value="ta">தமிழ்</option><option value="tanglish">Tanglish</option>
          </select>
          {chips.map((c) => <button key={c} onClick={() => send({ text: c })} disabled={busy} className="whitespace-nowrap rounded-lg border border-line bg-white px-3 py-1.5 text-xs text-navy-ink hover:border-brand-600">{c}</button>)}
        </div>
      </div>
    </section>
  );

  function ctxFor(m: Msg, active: boolean): CardCtx {
    return {
      msgId: m.id, pid: p.pid, code: p.code, perms: p.perms, active: active && !busy, send,
      onLinked: (l: Links) => setMsgs((all) => all.map((x) => (x.id === m.id ? { ...x, cards: x.cards.map((c) => (c.type === "plan" || c.type === "estimate" ? { ...c, links: { ...(c as any).links, ...l } } : c)) } : x))),
    };
  }
});

export default Chat;
