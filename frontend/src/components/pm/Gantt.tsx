export type Stage = {
  id: number; name: string; stage_group: string; start_date: string | null; end_date: string | null; progress: number;
  weight: number; is_milestone: boolean; sort: number; status: string; notes?: string; actual_start?: string | null; actual_end?: string | null;
};

export const GROUP_COLOR: Record<string, string> = {
  foundation: "#10b981", structure: "#2563eb", masonry: "#f97316", services: "#8b5cf6", finishing: "#0ea5e9", handover: "#64748b",
};
const DAY = 86400000;
const d0 = (s: string) => new Date(s + "T00:00:00").getTime();

/** Simple Gantt: one row per stage, month (or week) columns, today line, progress fill. */
export default function Gantt({ stages, compact = false, maxRows }: { stages: Stage[]; compact?: boolean; maxRows?: number }) {
  const all = stages.filter((s) => s.start_date && s.end_date);
  let from = 0;
  if (maxRows && all.length > maxRows) {  // show the window around the current work
    const cur = all.findIndex((s) => s.progress < 100);
    from = Math.max(0, Math.min(all.length - maxRows, (cur < 0 ? all.length : cur) - 2));
  }
  const rows = all.slice(from, from + (maxRows ?? all.length));
  if (!rows.length) return <p className="text-sm text-slate-500">No schedule yet.</p>;
  const start = Math.min(...rows.map((s) => d0(s.start_date!)));
  const end = Math.max(...rows.map((s) => d0(s.end_date!))) + DAY;
  const span = end - start;
  const days = span / DAY;
  const weekly = days <= 75;
  const ticks: { at: number; label: string }[] = [];
  if (weekly) {
    for (let t = start, i = 1; t < end; t += 7 * DAY, i++) ticks.push({ at: t, label: `W${i}` });
  } else {
    const dt = new Date(start); dt.setDate(1);
    while (dt.getTime() < end) {
      ticks.push({ at: Math.max(start, dt.getTime()), label: dt.toLocaleDateString("en-IN", { month: "short" }) + (dt.getMonth() === 0 ? ` ${String(dt.getFullYear()).slice(2)}` : "") });
      dt.setMonth(dt.getMonth() + 1);
    }
  }
  const pct = (t: number) => ((t - start) / span) * 100;
  const today = Date.now();
  const fmt = (s: string) => new Date(s + "T00:00:00").toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
  return (
    <div className="overflow-x-auto">
      <table className={`w-full border-collapse text-xs ${compact ? "min-w-[420px]" : "min-w-[640px]"}`}>
        <thead>
          <tr>
            <th className="table-th w-[34%]">Task</th>
            {!compact && <th className="table-th w-16">Start</th>}
            {!compact && <th className="table-th w-16">End</th>}
            <th className="table-th p-0">
              <div className="relative h-8">
                {ticks.map((t, i) => <span key={i} className="absolute top-2 -translate-x-0 pl-1 text-[10px] font-semibold text-slate-500" style={{ left: `${pct(t.at)}%` }}>{t.label}</span>)}
              </div>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((s) => {
            const a = pct(d0(s.start_date!)), b = pct(d0(s.end_date!) + DAY);
            const late = s.progress < 100 && d0(s.end_date!) + DAY < today;
            return (
              <tr key={s.id}>
                <td className="table-td truncate py-1.5" title={s.name}>{s.is_milestone && <span className="mr-1 text-amber-500">◆</span>}{s.name}</td>
                {!compact && <td className="table-td whitespace-nowrap py-1.5">{fmt(s.start_date!)}</td>}
                {!compact && <td className="table-td whitespace-nowrap py-1.5">{fmt(s.end_date!)}</td>}
                <td className="table-td relative p-0">
                  <div className="relative h-7">
                    {ticks.map((t, i) => <span key={i} className="absolute top-0 h-full border-l border-slate-100" style={{ left: `${pct(t.at)}%` }} />)}
                    <div className="absolute top-1.5 h-4 overflow-hidden rounded" title={`${s.name}: ${s.progress}%`}
                      style={{ left: `${a}%`, width: `${Math.max(0.8, b - a)}%`, background: `${GROUP_COLOR[s.stage_group] || "#94a3b8"}40`, outline: late ? "1.5px solid #ef4444" : undefined }}>
                      <div className="h-full" style={{ width: `${s.progress}%`, background: GROUP_COLOR[s.stage_group] || "#94a3b8" }} />
                    </div>
                    {today >= start && today <= end && <span className="absolute top-0 h-full border-l-2 border-red-400" style={{ left: `${pct(today)}%` }} />}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <div className="mt-2 flex flex-wrap gap-3 text-[11px] text-slate-500">
        {Object.entries(GROUP_COLOR).map(([g, c]) => <span key={g} className="flex items-center gap-1 capitalize"><span className="h-2.5 w-2.5 rounded-sm" style={{ background: c }} />{g}</span>)}
        <span className="flex items-center gap-1"><span className="h-3 border-l-2 border-red-400" />today</span>
        <span>◆ milestone · red outline = late</span>
      </div>
    </div>
  );
}
