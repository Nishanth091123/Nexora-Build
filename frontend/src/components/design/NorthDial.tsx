/** North-arrow picker: click a direction or nudge by 15°. value = degrees clockwise from the top of the drawing. */
export default function NorthDial({ value, onChange, size = 132 }: { value: number; onChange: (v: number) => void; size?: number }) {
  const r = 44;
  const a = (value * Math.PI) / 180;
  const nx = Math.sin(a), ny = -Math.cos(a);
  const norm = (v: number) => ((Math.round(v) % 360) + 360) % 360;
  return (
    <div className="flex items-center gap-3">
      <svg viewBox="-60 -60 120 120" width={size} height={size} className="shrink-0">
        <circle r="56" fill="#f8fafc" stroke="#e2e8f0" />
        {Array.from({ length: 8 }, (_, i) => {
          const t = (i * 45 * Math.PI) / 180;
          const x = Math.sin(t) * r, y = -Math.cos(t) * r;
          const on = norm(value) === i * 45;
          return <circle key={i} cx={x} cy={y} r="6.5" fill={on ? "#1d5ae0" : "white"} stroke="#94a3b8" strokeWidth="1"
            style={{ cursor: "pointer" }} onClick={() => onChange(i * 45)} />;
        })}
        <line x1={-nx * 30} y1={-ny * 30} x2={nx * 30} y2={ny * 30} stroke="#0f172a" strokeWidth="3" strokeLinecap="round" />
        <circle cx={nx * 30} cy={ny * 30} r="7.5" fill="#ef4444" />
        <text x={nx * 30} y={ny * 30 + 3.5} textAnchor="middle" fontSize="10" fontWeight="800" fill="white">N</text>
        <text y="-49" textAnchor="middle" fontSize="8" fill="#64748b" dy="-1">top</text>
      </svg>
      <div className="space-y-2 text-sm">
        <div className="font-semibold text-navy-ink">North arrow: {norm(value)}°</div>
        <div className="text-xs text-slate-500">Click where north points on the drawing (0° = up).</div>
        <div className="flex gap-1">
          <button type="button" className="btn-outline btn-sm" onClick={() => onChange(norm(value - 15))}>−15°</button>
          <button type="button" className="btn-outline btn-sm" onClick={() => onChange(norm(value + 15))}>+15°</button>
          <input type="number" className="input w-20 py-1 text-xs" value={norm(value)} onChange={(e) => onChange(norm(Number(e.target.value) || 0))} />
        </div>
      </div>
    </div>
  );
}
