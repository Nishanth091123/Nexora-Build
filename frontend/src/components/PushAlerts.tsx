import { useEffect, useState } from "react";
import { BellRing, Copy, Send } from "lucide-react";
import { Card, toast } from "./ui";
import { API_BASE, api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";
import { disablePush, enablePush, pushState } from "../lib/push";

const T = (ta: boolean, en: string, tam: string) => (ta ? tam : en);

function usePush() {
  const [state, setState] = useState<string>("…");
  const [busy, setBusy] = useState(false);
  const refresh = () => pushState().then(setState);
  useEffect(() => { refresh(); }, []);
  const turnOn = async () => {
    setBusy(true);
    try { await enablePush(); toast("Alerts are on for this device"); await refresh(); }
    catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  const turnOff = async () => {
    setBusy(true);
    try { await disablePush(); toast("Alerts turned off on this device"); await refresh(); }
    catch (e: any) { toast(e.message, "err"); } finally { setBusy(false); }
  };
  return { state, busy, turnOn, turnOff };
}

/** Small button under the Home weather card – shown only while this device is not receiving alerts. */
export function PushNudge() {
  const { lang } = useI18n();
  const p = usePush();
  if (p.state !== "off") return null;
  return (
    <button className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-brand-300 bg-brand-50 px-3 py-2 text-[13px] font-semibold text-brand-700 hover:bg-brand-100"
      disabled={p.busy} onClick={p.turnOn}>
      <BellRing size={16} />{T(lang === "ta", "Get these safety alerts on this phone / PC", "இந்த safety alerts-ஐ இந்த phone / PC-க்கு பெறுங்கள்")}
    </button>
  );
}

/** Settings → Notifications: turn alerts on/off for this device, send a test, and (owner) the daily-check link. */
export function PushCard() {
  const { lang } = useI18n();
  const ta = lang === "ta";
  const { user } = useAuth();
  const p = usePush();
  const [key, setKey] = useState("");
  useEffect(() => { if (user?.role === "owner") api<any>("/api/alerts/cron-key").then((r) => setKey(r.key)).catch(() => {}); }, [user?.role]);
  const base = API_BASE || window.location.origin.replace(":5173", ":8000");
  const cronUrl = key ? `${base}/api/alerts/run?key=${key}` : "";
  const test = async () => {
    try { const r = await api<any>("/api/push/test", { method: "POST" }); toast(`Test sent to ${r.sent} device(s)`); }
    catch (e: any) { toast(e.message, "err"); }
  };
  const copy = () => (navigator.clipboard?.writeText(cronUrl) || Promise.reject()).then(() => toast("Link copied")).catch(() => window.prompt("Copy this link", cronUrl));
  const label: Record<string, string> = {
    on: T(ta, "On – this device gets alerts", "On – இந்த device-க்கு alerts வரும்"),
    off: T(ta, "Off on this device", "இந்த device-ல் off"),
    blocked: T(ta, "Blocked in the browser – allow notifications for this site", "Browser-ல் block – இந்த site-க்கு notifications allow பண்ணுங்க"),
    unsupported: T(ta, "This browser cannot show notifications (iPhone: add the app to the Home Screen first)", "இந்த browser notifications காட்டாது (iPhone: முதலில் Home Screen-ல் app சேர்க்கவும்)"),
  };
  return (
    <Card title={T(ta, "Weather safety alerts", "Weather safety alerts")} icon={<BellRing size={20} />}>
      <p className="text-sm text-slate-600">{T(ta,
        "Thunderstorm, heavy rain, strong wind or extreme heat at your sites: a notification comes at 6 AM for today and at 5 PM for tomorrow – even when the app is closed. Today's alerts also show in the bell 🔔.",
        "உங்க sites-ல இடி, கனமழை, பலத்த காற்று, கடும் வெயில் இருந்தா: இன்றைக்கு காலை 6 மணிக்கும், நாளைக்கு மாலை 5 மணிக்கும் notification வரும் – app close-ஆ இருந்தாலும். இன்றைய alerts bell 🔔-லயும் தெரியும்.")}</p>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className={`rounded-full px-3 py-1 text-xs font-bold ${p.state === "on" ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-700"}`}>{label[p.state] || "…"}</span>
        <span className="flex-1" />
        {p.state === "on"
          ? <><button className="btn-outline btn-sm" onClick={test}><Send size={14} />{T(ta, "Send test", "Test அனுப்பு")}</button>
            <button className="btn-ghost btn-sm" disabled={p.busy} onClick={p.turnOff}>{T(ta, "Turn off", "Off பண்ணு")}</button></>
          : p.state === "off" && <button className="btn-primary btn-sm" disabled={p.busy} onClick={p.turnOn}><BellRing size={14} />{T(ta, "Turn on alerts on this device", "இந்த device-ல் alerts on பண்ணு")}</button>}
      </div>
      <p className="mt-2 text-[11px] text-slate-500">{T(ta, "Turn it on once on every phone / PC that should get alerts. Each team member does this on their own device.",
        "Alerts வேண்டிய ஒவ்வொரு phone / PC-லும் ஒரு தடவை on பண்ணுங்க. Team members அவங்க device-ல அவங்களே on பண்ணணும்.")}</p>
      {user?.role === "owner" && cronUrl && (
        <div className="mt-4 rounded-lg border border-line bg-slate-50 p-3 text-xs text-slate-600">
          <div className="mb-1 font-semibold text-navy-ink">{T(ta, "Daily check link (owner, set up once)", "Daily check link (owner, ஒரு தடவை setup)")}</div>
          <p>{T(ta, "The free online server sleeps when nobody uses it. At cron-job.org (free) create a job that opens this link every day at 06:00 and 17:00 (India time) – it wakes the server and sends the alerts.",
            "Free online server யாரும் use பண்ணலைனா தூங்கிடும். cron-job.org-ல் (free) இந்த link-ஐ தினமும் 06:00, 17:00 (India time) open பண்ற job create பண்ணுங்க – server எழுந்து alerts அனுப்பும்.")}</p>
          <div className="mt-2 flex items-center gap-2"><code className="min-w-0 flex-1 truncate rounded bg-white px-2 py-1">{cronUrl}</code>
            <button className="btn-outline btn-sm" onClick={copy}><Copy size={13} />{T(ta, "Copy", "Copy")}</button></div>
        </div>
      )}
    </Card>
  );
}
