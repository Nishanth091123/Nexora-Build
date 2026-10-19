import { useEffect, useState, type ReactNode } from "react";
import { X, Hourglass } from "lucide-react";
import { initials } from "../lib/api";
import { useI18n } from "../lib/i18n";

export function Card({ title, icon, action, children, className = "", bodyClass = "px-5 pb-5" }: {
  title?: ReactNode; icon?: ReactNode; action?: ReactNode; children: ReactNode; className?: string; bodyClass?: string;
}) {
  return (
    <section className={`card min-w-0 ${className}`}>
      {(title || action) && (
        <div className="card-head">
          <h3 className="card-title">{icon}{title}</h3>
          {action}
        </div>
      )}
      <div className={bodyClass}>{children}</div>
    </section>
  );
}

export function PillTabs<T extends string>({ tabs, value, onChange }: {
  tabs: { id: T; label: string; icon?: ReactNode }[]; value: T; onChange: (v: T) => void;
}) {
  return (
    <div className="no-scrollbar flex gap-2 overflow-x-auto pb-1 lg:flex-wrap lg:overflow-visible">
      {tabs.map((t) => (
        <button key={t.id} onClick={() => onChange(t.id)} className={`pill-tab ${value === t.id ? "pill-tab-active" : ""}`}>
          {t.icon}{t.label}
        </button>
      ))}
    </div>
  );
}

export function SegTabs<T extends string>({ tabs, value, onChange }: {
  tabs: { id: T; label: string }[]; value: T; onChange: (v: T) => void;
}) {
  return (
    <div className="flex flex-wrap gap-2">
      {tabs.map((t) => (
        <button key={t.id} onClick={() => onChange(t.id)}
          className={`rounded-lg px-4 py-2 text-sm font-medium transition ${value === t.id ? "bg-brand-600 text-white" : "bg-brand-50 text-navy-ink hover:bg-brand-100"}`}>
          {t.label}
        </button>
      ))}
    </div>
  );
}

const BADGE: Record<string, string> = {
  green: "bg-emerald-50 text-emerald-700", amber: "bg-amber-50 text-amber-700", red: "bg-red-50 text-red-700",
  blue: "bg-brand-50 text-brand-700", gray: "bg-slate-100 text-slate-600", purple: "bg-violet-50 text-violet-700",
};
export function Badge({ color = "gray", children }: { color?: keyof typeof BADGE | string; children: ReactNode }) {
  return <span className={`inline-flex items-center rounded-md px-2 py-0.5 text-xs font-semibold ${BADGE[color] || BADGE.gray}`}>{children}</span>;
}

const AV_COLORS = ["bg-brand-600", "bg-emerald-600", "bg-violet-600", "bg-amber-600", "bg-rose-600", "bg-cyan-700", "bg-slate-700"];
export function Avatar({ name, size = 36 }: { name: string; size?: number }) {
  const idx = [...(name || "")].reduce((a, c) => a + c.charCodeAt(0), 0) % AV_COLORS.length;
  return (
    <span className={`inline-flex shrink-0 items-center justify-center rounded-full font-bold text-white ${AV_COLORS[idx]}`}
      style={{ width: size, height: size, fontSize: size * 0.38 }}>
      {initials(name)}
    </span>
  );
}

export function Toggle({ checked, onChange, disabled }: { checked: boolean; onChange: (v: boolean) => void; disabled?: boolean }) {
  return (
    <button type="button" role="switch" aria-checked={checked} disabled={disabled} onClick={() => onChange(!checked)}
      className={`relative h-6 w-11 shrink-0 rounded-full transition ${checked ? "bg-brand-600" : "bg-slate-300"} disabled:opacity-50`}>
      <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition ${checked ? "left-[22px]" : "left-0.5"}`} />
    </button>
  );
}

export function Modal({ open, title, onClose, children, wide }: {
  open: boolean; title: string; onClose: () => void; children: ReactNode; wide?: boolean | "xl";
}) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    if (open) window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-navy-950/50 p-4 pt-12" onMouseDown={onClose}>
      <div className={`card w-full ${wide === "xl" ? "max-w-6xl" : wide ? "max-w-3xl" : "max-w-lg"}`} onMouseDown={(e) => e.stopPropagation()}>
        <div className="card-head border-b border-line pb-4">
          <h3 className="card-title text-base">{title}</h3>
          <button onClick={onClose} className="btn-ghost btn-sm" aria-label="Close"><X size={18} /></button>
        </div>
        <div className="p-5">{children}</div>
      </div>
    </div>
  );
}

export function Empty({ icon, text, children }: { icon?: ReactNode; text: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-line px-4 py-8 text-center text-sm text-slate-500">
      {icon}<p>{text}</p>{children}
    </div>
  );
}

/** Marks a part of a mockup screen that gets built in a later phase. */
export function PhaseNote({ phase, what }: { phase: number; what: string }) {
  const { t } = useI18n();
  return (
    <div className="flex items-start gap-3 rounded-lg border border-dashed border-brand-100 bg-brand-50/50 px-4 py-4 text-sm text-slate-600">
      <Hourglass size={18} className="mt-0.5 shrink-0 text-brand-600" />
      <p><span className="font-semibold text-navy-ink">{t("Coming in")} Phase {phase}:</span> {what}</p>
    </div>
  );
}

export function Field({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  return <label className={`block ${className}`}><span className="label">{label}</span>{children}</label>;
}

// --- simple toast ---
let pushToast: ((msg: string, kind?: "ok" | "err") => void) | null = null;
export const toast = (msg: string, kind: "ok" | "err" = "ok") => pushToast?.(msg, kind);

export function Toaster() {
  const [items, setItems] = useState<{ id: number; msg: string; kind: string }[]>([]);
  useEffect(() => {
    pushToast = (msg, kind = "ok") => {
      if (!msg) return;
      const id = Date.now() + Math.random();
      setItems((x) => [...x, { id, msg, kind }]);
      setTimeout(() => setItems((x) => x.filter((i) => i.id !== id)), 4500);
    };
    return () => { pushToast = null; };
  }, []);
  return (
    <div className="fixed bottom-4 right-4 z-[60] flex max-w-sm flex-col gap-2">
      {items.map((i) => (
        <div key={i.id} className={`rounded-lg px-4 py-3 text-sm font-medium text-white shadow-lg ${i.kind === "err" ? "bg-red-600" : "bg-navy-900"}`}>{i.msg}</div>
      ))}
    </div>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const { t } = useI18n();
  const map: Record<string, [string, string]> = {
    active: ["green", "Active"], pending: ["amber", "Pending"], deactivated: ["gray", "Deactivated"],
    ongoing: ["blue", "Ongoing"], completed: ["green", "Completed"], on_hold: ["amber", "On Hold"],
    archived: ["gray", "Archived"], on_track: ["green", "On Track"], delayed: ["red", "Delayed"],
  };
  const [c, l] = map[status] || ["gray", status];
  return <Badge color={c}>{t(l)}</Badge>;
}
