// Small fetch wrapper: adds the login token, turns API errors into readable messages.
// Site updates made while offline are queued (lib/outbox.ts) and sent automatically later.
import { canQueue, enqueue, type OutItem } from "./outbox";
export const API_BASE = (import.meta as any).env?.VITE_API_URL?.replace(/\/$/, "") || "";
const TOKEN_KEY = "nexora_token";

export function getToken(): string | null {
  try { return localStorage.getItem(TOKEN_KEY); } catch { return null; }
}
export function setToken(t: string | null) {
  try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch { /* ignore */ }
}

export class ApiError extends Error {
  status: number;
  questions: string[];
  detail: any;
  constructor(status: number, message: string, questions: string[] = [], detail: any = null) { super(message); this.status = status; this.questions = questions; this.detail = detail; }
}

let onUnauthorized: (() => void) | null = null;
export function setUnauthorizedHandler(fn: () => void) { onUnauthorized = fn; }

export async function api<T = any>(path: string, opts: { method?: string; body?: any; form?: FormData } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (opts.form) body = opts.form;
  else if (opts.body !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(opts.body); }

  let res: Response;
  const method = opts.method || (body ? "POST" : "GET");
  try {
    res = await fetch(API_BASE + path, { method, headers, body });
  } catch {
    if (canQueue(path, method)) {
      await enqueue(path, method, opts.form ? { form: opts.form } : { json: opts.body });
      window.dispatchEvent(new CustomEvent("nexora-queued"));
      throw new ApiError(0, "", [], { queued: true });  // empty message = no error toast; the offline bar shows it
    }
    throw new ApiError(0, navigator.onLine === false ? "You are offline – this needs the internet." : (API_BASE ? "Cannot reach the server – it may be waking up (free server). Try again in a minute." : "Cannot reach the server. Is the backend running? (scripts\\start.bat)"));
  }
  if (res.status === 401 && path !== "/api/auth/login") { setToken(null); onUnauthorized?.(); }
  const text = await res.text();
  let data: any = null;
  try { data = text ? JSON.parse(text) : null; } catch { data = text; }
  if (!res.ok) {
    let msg = data?.detail ?? `Error ${res.status}`;
    let questions: string[] = [];
    if (Array.isArray(msg)) msg = msg.map((d: any) => `${(d.loc || []).slice(-1)[0]}: ${d.msg}`).join(", ");
    else if (msg && typeof msg === "object") { questions = msg.questions || []; msg = msg.message || "Please check the inputs"; }
    if (res.status === 404 && msg === "Not Found") msg = API_BASE ? "This feature needs the updated server – run the deploy again (docs/PHASE_7_GUIDE.md)." : "This feature needs the updated backend. Close ALL Nexora CMD windows and run scripts\\start.bat again.";
    throw new ApiError(res.status, String(msg), questions, data?.detail);
  }
  return data as T;
}

/** Download/preview a protected file: fetch with token, return an object URL. */
export async function fileObjectUrl(path: string): Promise<string> {
  const token = getToken();
  const res = await fetch(API_BASE + path, { headers: token ? { Authorization: `Bearer ${token}` } : {} });
  if (!res.ok) throw new ApiError(res.status, "Could not load file");
  return URL.createObjectURL(await res.blob());
}

export async function downloadFile(path: string, filename: string) {
  const url = await fileObjectUrl(path);
  const a = document.createElement("a");
  a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

/** POST a JSON body and download the file the server returns (e.g. a filled Excel template). */
export async function downloadPost(path: string, body: any, filename: string) {
  const token = getToken();
  const res = await fetch(API_BASE + path, { method: "POST", headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) }, body: JSON.stringify(body) });
  if (!res.ok) {
    let msg = "Download failed";
    try { const d = await res.json(); msg = typeof d.detail === "string" ? d.detail : d.detail?.message || msg; } catch { /* ignore */ }
    throw new ApiError(res.status, msg);
  }
  const url = URL.createObjectURL(await res.blob());
  const a = document.createElement("a");
  a.href = url; a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}

export const fmtBytes = (n: number) =>
  n < 1024 ? `${n} B` : n < 1048576 ? `${(n / 1024).toFixed(1)} KB` : n < 1073741824 ? `${(n / 1048576).toFixed(1)} MB` : `${(n / 1073741824).toFixed(2)} GB`;

export const fmtDate = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—";

export const fmtDateTime = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleString("en-IN", { day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) : "—";

export function timeAgo(iso: string): string {
  const s = Math.max(0, (Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} hours ago`;
  return `${Math.floor(s / 86400)} days ago`;
}

export const initials = (name: string) =>
  (name || "?").trim().split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase() || "").join("") || "?";

const inrFmt = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
export const inr = (n: number | null | undefined) => inrFmt.format(Math.round(n || 0));
export const rupees = (n: number | null | undefined) => `₹${inr(n)}`;
export const lakhs = (n: number) => (n >= 1e7 ? `₹${(n / 1e7).toFixed(2)} Cr` : `₹${(n / 1e5).toFixed(2)} L`);
export const num = (n: number, d = 2) => new Intl.NumberFormat("en-IN", { maximumFractionDigits: d }).format(n || 0);

/** Send one queued offline item (used by the offline bar). */
export function sendQueued(it: OutItem): Promise<Response> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  let body: BodyInit | undefined;
  if (it.form) {
    const fd = new FormData();
    it.form.forEach((p) => (p.blob ? fd.append(p.name, p.blob, p.filename) : fd.append(p.name, p.value ?? "")));
    body = fd;
  } else if (it.json !== undefined) { headers["Content-Type"] = "application/json"; body = it.json; }
  return fetch(API_BASE + it.path, { method: it.method, headers, body });
}
