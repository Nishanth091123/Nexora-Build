import { useCallback, useEffect, useState } from "react";
import { CloudOff, RefreshCw, UploadCloud } from "lucide-react";
import { sendQueued } from "../lib/api";
import { flush, list, onOutboxChange } from "../lib/outbox";
import { toast } from "./ui";

/** Shows offline state and site updates waiting to be sent; sends them automatically when back online. */
export default function OfflineBar() {
  const [online, setOnline] = useState(typeof navigator === "undefined" ? true : navigator.onLine);
  const [waiting, setWaiting] = useState(0);
  const [busy, setBusy] = useState(false);
  const refresh = useCallback(async () => setWaiting((await list()).length), []);

  const sync = useCallback(async () => {
    if (busy || !(await list()).length) return;
    setBusy(true);
    const r = await flush(sendQueued);
    setBusy(false);
    if (r.sent) toast(`${r.sent} offline update(s) sent`);
    r.failed.forEach((f) => toast(`Not saved: ${f}`, "err"));
    if (r.sent) window.dispatchEvent(new CustomEvent("nexora-synced"));
  }, [busy]);

  useEffect(() => {
    refresh();
    const off = onOutboxChange(refresh);
    const on = () => { setOnline(true); sync(); };
    const down = () => setOnline(false);
    const queued = () => toast("No connection – saved on this device. It will be sent automatically.");
    window.addEventListener("online", on);
    window.addEventListener("offline", down);
    window.addEventListener("nexora-queued", queued);
    const iv = window.setInterval(() => { if (navigator.onLine) sync(); }, 30000);
    sync();
    return () => { off(); window.removeEventListener("online", on); window.removeEventListener("offline", down); window.removeEventListener("nexora-queued", queued); clearInterval(iv); };
  }, [refresh, sync]);

  if (online && !waiting) return null;
  return (
    <div className={`flex flex-wrap items-center gap-2 px-4 py-2 text-sm font-medium lg:px-6 ${online ? "bg-amber-50 text-amber-800" : "bg-slate-800 text-white"}`}>
      {online ? <UploadCloud size={16} /> : <CloudOff size={16} />}
      <span className="flex-1">{online ? "" : "You are offline – saved pages still open; site updates are kept on this device. "}
        {waiting > 0 && `${waiting} update(s) waiting to be sent.`}</span>
      {online && waiting > 0 && <button className="inline-flex items-center gap-1 rounded-md bg-white/70 px-2 py-1 text-xs font-semibold" onClick={sync} disabled={busy}><RefreshCw size={13} className={busy ? "animate-spin" : ""} />{busy ? "Sending…" : "Send now"}</button>}
    </div>
  );
}
