import { useEffect, useState } from "react";
import { RefreshCw } from "lucide-react";
import { API_BASE } from "../lib/api";

const BUILD = typeof __APP_VERSION__ !== "undefined" ? __APP_VERSION__ : "";
const nums = (v: string) => (v.match(/\d+/g) || []).slice(0, 3).map(Number);
function isNewer(a: string, b: string) {
  const x = nums(a), y = nums(b);
  for (let i = 0; i < 3; i++) if ((x[i] || 0) !== (y[i] || 0)) return (x[i] || 0) > (y[i] || 0);
  return false;
}

/** After an update, an old copy of the app can stay in the browser. Compare with the backend and offer a clean reload. */
export default function VersionBar() {
  const [server, setServer] = useState("");
  useEffect(() => {
    if (!BUILD) return;
    fetch(API_BASE + "/api/health", { cache: "no-store" }).then((r) => r.json()).then((d) => setServer(d.version || "")).catch(() => {});
  }, []);
  // only when the SCREEN is older than the server (a stale browser copy). While the server is still updating
  // (screen newer than server for a few minutes after a push), nothing is shown.
  if (!BUILD || !server || !isNewer(server, BUILD)) return null;
  const reload = async () => {
    try {
      const regs = await navigator.serviceWorker?.getRegistrations?.();
      await Promise.all((regs || []).map((r) => r.unregister()));
      const keys = await caches?.keys?.();
      await Promise.all((keys || []).map((k) => caches.delete(k)));
    } catch { /* ignore */ }
    window.location.reload();
  };
  return (
    <div className="flex flex-wrap items-center gap-2 bg-amber-100 px-4 py-2 text-sm font-medium text-amber-900 lg:px-6">
      <span className="flex-1">An older copy of the app is open (screen {BUILD}, server {server}). Reload to get the latest version.</span>
      <button className="inline-flex items-center gap-1 rounded-md bg-white px-2 py-1 text-xs font-semibold" onClick={reload}><RefreshCw size={13} />Reload now</button>
    </div>
  );
}
