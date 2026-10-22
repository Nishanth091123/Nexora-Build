// Phase 7.8 – turn on phone / PC notifications (Web Push) for weather safety alerts.
import { api } from "./api";

export const pushSupported = () =>
  typeof window !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

function keyBytes(b64: string): Uint8Array {
  const pad = "=".repeat((4 - (b64.length % 4)) % 4);
  const raw = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from(raw, (c) => c.charCodeAt(0));
}

async function registration(): Promise<ServiceWorkerRegistration> {
  const ready = navigator.serviceWorker.ready;
  const timeout = new Promise<never>((_, no) => setTimeout(() => no(new Error(
    "Alerts work in the online app (https) or after the app is installed. Open the Vercel address and try again.")), 6000));
  return Promise.race([ready, timeout]);
}

/** Is this device already receiving alerts? */
export async function pushState(): Promise<"unsupported" | "blocked" | "on" | "off"> {
  if (!pushSupported()) return "unsupported";
  if (Notification.permission === "denied") return "blocked";
  try {
    const reg = await registration();
    const sub = await reg.pushManager.getSubscription();
    return sub && Notification.permission === "granted" ? "on" : "off";
  } catch { return "off"; }
}

export async function enablePush(): Promise<void> {
  if (!pushSupported()) throw new Error("This browser cannot show notifications. On iPhone, first add the app to the Home Screen.");
  const perm = await Notification.requestPermission();
  if (perm !== "granted") throw new Error("Notifications were not allowed. Allow them in the browser settings for this site.");
  const reg = await registration();
  const { public_key } = await api<{ public_key: string }>("/api/push/key");
  let sub = await reg.pushManager.getSubscription();
  if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: keyBytes(public_key) });
  const j = sub.toJSON() as any;
  await api("/api/push/subscribe", { body: { endpoint: j.endpoint, keys: j.keys, device: navigator.userAgent.slice(0, 200) } });
}

export async function disablePush(): Promise<void> {
  const reg = await registration();
  const sub = await reg.pushManager.getSubscription();
  if (sub) {
    await api("/api/push/unsubscribe", { body: { endpoint: sub.endpoint } }).catch(() => {});
    await sub.unsubscribe();
  }
}
