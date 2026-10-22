import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, Bell, CheckCheck, ChevronRight, ClipboardList, Mail, MailOpen, Trash2, UserPlus } from "lucide-react";
import { api } from "../lib/api";

type Item = { key: string; kind: string; title: string; body?: string; link: string; at: string; read: boolean };
const ICON: Record<string, any> = { weather: AlertTriangle, user: UserPlus, approval: CheckCheck, task: ClipboardList };
const TONE: Record<string, string> = { weather: "bg-red-50 text-red-600", user: "bg-blue-50 text-blue-600", approval: "bg-emerald-50 text-emerald-700", task: "bg-amber-50 text-amber-700" };

/** Bell: tap an item to open it (marks it read); read / unread and delete per item; mark all read; clear all. */
export default function NotifBell() {
  const [d, setD] = useState<{ count: number; items: Item[] }>({ count: 0, items: [] });
  const [open, setOpen] = useState(false);
  const [openKey, setOpenKey] = useState("");
  const box = useRef<HTMLDivElement>(null);
  const nav = useNavigate();
  const load = () => api<any>("/api/notifications").then(setD).catch(() => {});
  useEffect(() => {
    load();
    const iv = window.setInterval(load, 60000);
    return () => clearInterval(iv);
  }, []);
  useEffect(() => {  // close when tapping outside (works on phones too)
    if (!open) return;
    const h = (e: MouseEvent | TouchEvent) => { if (box.current && !box.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("mousedown", h); document.addEventListener("touchstart", h);
    return () => { document.removeEventListener("mousedown", h); document.removeEventListener("touchstart", h); };
  }, [open]);

  const mark = async (keys: string[], action: "read" | "unread" | "delete") => {
    if (!keys.length) return;
    setD((x) => {  // instant on screen, saved in the background
      const items = action === "delete" ? x.items.filter((i) => !keys.includes(i.key))
        : x.items.map((i) => (keys.includes(i.key) ? { ...i, read: action === "read" } : i));
      return { items, count: items.filter((i) => !i.read).length };
    });
    try { await api("/api/notifications/mark", { body: { keys, action } }); } catch { load(); }
  };
  const tap = (n: Item) => {
    setOpenKey(openKey === n.key ? "" : n.key);
    if (!n.read) mark([n.key], "read");
  };
  const go = (n: Item) => { setOpen(false); nav(n.link); };

  return (
    <div className="relative" ref={box}>
      <button className="relative text-navy-ink" aria-label="Notifications" onClick={() => setOpen(!open)}>
        <Bell size={26} />
        {d.count > 0 && <span className="absolute -right-1.5 -top-1.5 flex h-5 min-w-5 items-center justify-center rounded-full bg-red-600 px-1 text-[11px] font-bold text-white">{d.count > 9 ? "9+" : d.count}</span>}
      </button>
      {open && (
        <div className="fixed inset-x-2 top-16 z-40 rounded-xl border border-line bg-white p-2 shadow-xl sm:absolute sm:inset-x-auto sm:right-0 sm:top-auto sm:mt-2 sm:w-96">
          <div className="flex items-center gap-2 px-2 py-1">
            <span className="flex-1 text-sm font-bold text-navy-ink">Notifications{d.count ? ` (${d.count} new)` : ""}</span>
            {d.items.some((i) => !i.read) && <button className="text-xs font-semibold text-brand-600 hover:underline" onClick={() => mark(d.items.filter((i) => !i.read).map((i) => i.key), "read")}>Mark all read</button>}
            {d.items.length > 0 && <button className="text-xs font-semibold text-slate-500 hover:text-red-600" onClick={() => mark(d.items.map((i) => i.key), "delete")}>Clear all</button>}
          </div>
          {!d.items.length ? <p className="px-2 py-4 text-center text-sm text-slate-500">Nothing new.</p> : (
            <ul className="max-h-[70vh] space-y-1 overflow-y-auto">
              {d.items.map((n) => {
                const I = ICON[n.kind] || Bell;
                const isOpen = openKey === n.key;
                return (
                  <li key={n.key} className={`rounded-lg ${n.read ? "" : "bg-brand-50/60"}`}>
                    <div className="flex items-start gap-2 px-2 py-2">
                      <span className={`mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg ${TONE[n.kind] || "bg-slate-100 text-slate-600"}`}><I size={16} /></span>
                      <button className="min-w-0 flex-1 text-left" onClick={() => tap(n)}>
                        <span className={`block text-sm ${n.read ? "text-slate-600" : "font-semibold text-navy-ink"} ${isOpen ? "" : "line-clamp-2"}`}>{n.title}</span>
                        {n.body && (isOpen || !n.read) && <span className={`mt-0.5 block text-xs text-slate-600 ${isOpen ? "" : "line-clamp-1"}`}>{n.body}</span>}
                      </button>
                      {!n.read && <span className="mt-2 h-2 w-2 shrink-0 rounded-full bg-brand-600" title="New" />}
                    </div>
                    {isOpen && (
                      <div className="flex flex-wrap items-center gap-1 px-2 pb-2 pl-12">
                        <button className="btn-primary btn-sm" onClick={() => go(n)}>Open<ChevronRight size={14} /></button>
                        <button className="btn-ghost btn-sm" onClick={() => mark([n.key], n.read ? "unread" : "read")}>{n.read ? <><Mail size={14} />Mark unread</> : <><MailOpen size={14} />Mark read</>}</button>
                        <button className="btn-ghost btn-sm text-red-600" onClick={() => mark([n.key], "delete")}><Trash2 size={14} />Delete</button>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}
