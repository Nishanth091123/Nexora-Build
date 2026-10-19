// Offline outbox: site updates made without network are kept in IndexedDB and sent when the connection returns.
type Part = { name: string; value?: string; blob?: Blob; filename?: string };
export type OutItem = { id?: number; path: string; method: string; json?: string; form?: Part[]; label: string; created: number; error?: string };

const DB = "nexora_offline";
const STORE = "outbox";
const QUEUEABLE = [
  /^\/api\/projects\/\d+\/site\//, /^\/api\/site\//, /^\/api\/projects\/\d+\/tasks$/, /^\/api\/tasks\/\d+$/,
  /^\/api\/schedule\/stages\/\d+$/,
];

export const canQueue = (path: string, method: string) => method !== "GET" && QUEUEABLE.some((r) => r.test(path.split("?")[0]));

function open(): Promise<IDBDatabase> {
  return new Promise((res, rej) => {
    const r = indexedDB.open(DB, 1);
    r.onupgradeneeded = () => r.result.createObjectStore(STORE, { keyPath: "id", autoIncrement: true });
    r.onsuccess = () => res(r.result);
    r.onerror = () => rej(r.error);
  });
}

async function tx<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open();
  return new Promise((res, rej) => {
    const t = db.transaction(STORE, mode);
    const req = fn(t.objectStore(STORE));
    req.onsuccess = () => res(req.result);
    req.onerror = () => rej(req.error);
  });
}

const listeners = new Set<() => void>();
export const onOutboxChange = (fn: () => void) => { listeners.add(fn); return () => { listeners.delete(fn); }; };
const changed = () => listeners.forEach((f) => f());

export async function enqueue(path: string, method: string, body: { json?: any; form?: FormData }): Promise<void> {
  const item: OutItem = { path, method, label: labelOf(path, method), created: Date.now() };
  if (body.form) {
    item.form = [];
    body.form.forEach((v, k) => {
      if (typeof v === "string") item.form!.push({ name: k, value: v });
      else item.form!.push({ name: k, blob: v, filename: (v as File).name || "photo.jpg" });
    });
  } else if (body.json !== undefined) item.json = JSON.stringify(body.json);
  await tx("readwrite", (s) => s.add(item));
  changed();
}

export async function list(): Promise<OutItem[]> {
  try { return await tx<OutItem[]>("readonly", (s) => s.getAll() as IDBRequest<OutItem[]>); } catch { return []; }
}

async function remove(id: number) { await tx("readwrite", (s) => s.delete(id)); }

function labelOf(path: string, method: string) {
  const p = path.split("?")[0];
  if (p.includes("/photos")) return "Site photo";
  if (p.includes("/activities")) return "Site activity";
  if (p.includes("/attendance")) return "Attendance";
  if (p.includes("/materials")) return "Material entry";
  if (p.includes("/report")) return "Daily report";
  if (p.includes("/quality")) return "Quality check";
  if (p.includes("/safety")) return "Safety / issue";
  if (p.includes("/tasks")) return "Task";
  if (p.includes("/stages")) return "Schedule progress";
  return `${method} ${p}`;
}

let flushing = false;
/** Send queued items in order. Stops at the first network failure; drops items the server refuses (reports them). */
export async function flush(send: (it: OutItem) => Promise<Response>): Promise<{ sent: number; failed: string[] }> {
  if (flushing) return { sent: 0, failed: [] };
  flushing = true;
  let sent = 0;
  const failed: string[] = [];
  try {
    for (const it of await list()) {
      let r: Response;
      try { r = await send(it); } catch { break; }
      if (r.ok) { await remove(it.id!); sent++; }
      else if (r.status >= 400 && r.status < 500 && r.status !== 401) {
        let msg = `${r.status}`;
        try { const d = await r.json(); msg = typeof d.detail === "string" ? d.detail : d.detail?.message || msg; } catch { /* ignore */ }
        failed.push(`${it.label}: ${msg}`);
        await remove(it.id!);
      } else break;
    }
  } finally { flushing = false; changed(); }
  return { sent, failed };
}
