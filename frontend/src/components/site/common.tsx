import type { ReactNode } from "react";
import type { Stage } from "../pm/Gantt";

export type Activity = { id: number; work_date: string; title: string; location: string; stage_id: number | null; stage: string;
  status: string; progress: number; photo_url: string | null; photo_file_id: number | null; notes: string };
export type Photo = { id: number; file_id: number; url: string; caption: string; taken_on: string; location: string; latitude: number | null; longitude: number | null };
export type MatRow = { code: string | null; name: string; unit: string; planned: number; received: number; used: number; stock: number; pct: number | null };
export type QC = { id: number; stage: string; item: string; standard: string; status: string; remarks: string; checked_on: string | null; checked_by: string; photo_url: string | null };
export type Overview = {
  date: string;
  project: { id: number; name: string; location: string; district: string; state: string; latitude: number | null; longitude: number | null;
    start_date: string | null; end_date: string | null; health: string; progress: number };
  progress: { overall: number; planned: number | null; variance_days: number; health: string; has_schedule: boolean;
    pipeline: { label: string; progress: number; status: string }[] };
  cards: { activities: number; activities_done: number; workers: number; wages: number; material_pct: number | null; issues: number };
  current: Activity | null; activities: Activity[]; photos: Photo[]; materials: MatRow[];
  manpower: { by_trade: { trade: string; name: string; count: number }[]; present: { name: string; trade: string; trade_name: string; status: string }[] };
  quality: QC[]; gantt: Stage[]; insights: { kind: string; text: string }[]; estimate: { id: number; version: number; title: string } | null;
};

export const STATUS_PILL: Record<string, string> = {
  completed: "bg-emerald-50 text-emerald-700", in_progress: "bg-brand-50 text-brand-700", pending: "bg-amber-50 text-amber-700",
  checked: "bg-emerald-50 text-emerald-700", failed: "bg-red-50 text-red-700", open: "bg-red-50 text-red-700", closed: "bg-slate-100 text-slate-600",
};
export const STATUS_LABEL: Record<string, string> = { completed: "Completed", in_progress: "In Progress", pending: "Pending", checked: "Checked", failed: "Failed", open: "Open", closed: "Closed" };

export function Pill({ s, children }: { s: string; children?: ReactNode }) {
  return <span className={`inline-flex items-center whitespace-nowrap rounded-full px-2.5 py-0.5 text-xs font-semibold ${STATUS_PILL[s] || "bg-slate-100 text-slate-600"}`}>{children ?? STATUS_LABEL[s] ?? s}</span>;
}

export function Bar({ value, tone = "bg-brand-600" }: { value: number; tone?: string }) {
  return <span className="block h-2 overflow-hidden rounded-full bg-slate-100"><span className={`block h-full rounded-full ${tone}`} style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></span>;
}

export const today = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};
export const prettyDate = (s?: string | null) => (s ? new Date(s + (s.length === 10 ? "T00:00:00" : "")).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—");
export const n0 = (v: number) => new Intl.NumberFormat("en-IN", { maximumFractionDigits: 1 }).format(v || 0);
