import { useEffect, useState } from "react";
import {
  AlertTriangle, CalendarRange, Camera, Check, CheckCircle2, ClipboardList, CloudRain, HardHat, Info, MapPin, Package,
  Plus, ShieldCheck, Sparkles, Truck, Users,
} from "lucide-react";
import AuthImg from "../AuthImg";
import Gantt from "../pm/Gantt";
import { CreateSchedule } from "../pm/PmPanels";
import { Card, Empty, toast } from "../ui";
import { api } from "../../lib/api";
import { Bar, Pill, n0, prettyDate, type Overview } from "./common";

function Ring({ value }: { value: number }) {
  const R = 40, C = 2 * Math.PI * R;
  return (
    <svg width="104" height="104" viewBox="0 0 104 104" className="shrink-0">
      <circle cx="52" cy="52" r={R} fill="none" stroke="#e2e8f0" strokeWidth="10" />
      <circle cx="52" cy="52" r={R} fill="none" stroke="#16a34a" strokeWidth="10" strokeDasharray={`${(value / 100) * C} ${C}`} strokeLinecap="round" transform="rotate(-90 52 52)" />
      <text x="52" y="59" textAnchor="middle" fontSize="21" fontWeight="800" className="fill-navy-ink">{Math.round(value)}%</text>
    </svg>
  );
}

function Kpi({ icon, label, value, sub, tone }: { icon: any; label: string; value: string; sub: string; tone: string }) {
  return (
    <div className="card flex flex-col gap-2 p-4">
      <div className="text-sm font-bold text-navy-ink">{label}</div>
      <div className="flex items-center gap-3"><span className={tone}>{icon}</span><div><div className="text-2xl font-extrabold text-navy-ink">{value}</div><div className="text-xs text-slate-500">{sub}</div></div></div>
    </div>
  );
}

const ICON_OF: Record<string, any> = { good: CheckCircle2, risk: AlertTriangle, info: Info };

export default function OverviewTab({ ov, canWrite, reload, goto, onAddActivity }: {
  ov: Overview; canWrite: boolean; reload: () => void; goto: (t: string) => void; onAddActivity: () => void;
}) {
  const [insTab, setInsTab] = useState<"progress" | "risk" | "suggest">("progress");
  const [weather, setWeather] = useState<string[]>([]);
  const P = ov.project;
  const pr = ov.progress;
  useEffect(() => {
    if (P.latitude == null || P.longitude == null) return;
    fetch(`https://api.open-meteo.com/v1/forecast?latitude=${P.latitude}&longitude=${P.longitude}&daily=precipitation_probability_max&timezone=auto&forecast_days=7`)
      .then((r) => r.json()).then((d) => {
        const out: string[] = [];
        (d?.daily?.time || []).forEach((t: string, i: number) => {
          const p = d.daily.precipitation_probability_max?.[i];
          if (p != null && p >= 60) out.push(`Rain likely on ${new Date(t + "T00:00:00").toLocaleDateString("en-IN", { weekday: "short", day: "2-digit", month: "short" })} (${p}%) – plan concreting / curing cover.`);
        });
        setWeather(out.length ? out.slice(0, 2) : ["Weather looks dry for the next 7 days – good for concreting."]);
      }).catch(() => {});
  }, [P.latitude, P.longitude]);

  const toggleActivity = async (id: number, done: boolean) => {
    try { await api(`/api/site/activities/${id}`, { method: "PATCH", body: { status: done ? "completed" : "in_progress" } }); reload(); }
    catch (e: any) { toast(e.message, "err"); }
  };
  const setLocation = () => {
    if (!navigator.geolocation) return toast("Location is not available on this device", "err");
    navigator.geolocation.getCurrentPosition(async (pos) => {
      try { await api(`/api/projects/${P.id}/site/location`, { method: "PUT", body: { latitude: pos.coords.latitude, longitude: pos.coords.longitude } }); toast("Site location saved"); reload(); }
      catch (e: any) { toast(e.message, "err"); }
    }, () => toast("Could not get the location – allow location access", "err"), { enableHighAccuracy: true, timeout: 15000 });
  };
  const ins = ov.insights;
  const shownIns = insTab === "progress" ? ins.filter((x) => x.kind !== "risk") : insTab === "risk" ? ins.filter((x) => x.kind === "risk") : [
    ...weather.map((w) => ({ kind: "info", text: w })),
    ...ins.filter((x) => x.text.startsWith("Next focus")),
    { kind: "info", text: "Take one photo per activity each day – the DPR PDF picks them up automatically." },
  ];
  const cur = ov.current;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 2xl:grid-cols-[1.25fr_1fr]">
        <Card title="Project Progress" icon={<Sparkles size={20} />}>
          {!pr.has_schedule ? <CreateSchedule projectId={P.id} canEdit={canWrite} onDone={reload} /> : (
            <div className="flex flex-wrap items-center gap-5">
              <Ring value={pr.overall} />
              <div className="text-sm">
                <div className="font-bold text-navy-ink">Overall Progress</div>
                <span className={`mt-1 inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${pr.health === "delayed" ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"}`}>
                  {pr.health === "delayed" ? "Delayed" : "On Track"}</span>
                <div className="mt-1 text-xs text-slate-500">Started: {prettyDate(P.start_date)}</div>
                <div className="text-xs text-slate-500">Expected: {prettyDate(P.end_date)}</div>
                <div className="text-xs text-slate-500">Plan today {pr.planned ?? 0}% · {pr.variance_days >= 0 ? `${pr.variance_days} d ahead` : `${-pr.variance_days} d behind`}</div>
              </div>
              <div className="flex min-w-[300px] flex-1 items-start justify-between">
                {pr.pipeline.map((s, i) => (
                  <div key={s.label} className="relative flex flex-1 flex-col items-center text-center">
                    {i > 0 && <span className={`absolute right-1/2 top-2.5 h-1 w-full ${s.status === "pending" ? "bg-slate-200" : "bg-emerald-500"}`} />}
                    <span className={`relative z-10 flex h-6 w-6 items-center justify-center rounded-full text-white ${s.status === "completed" ? "bg-emerald-500" : s.status === "in_progress" ? "bg-brand-600" : "bg-slate-300"}`}>{s.status === "completed" && <Check size={14} />}</span>
                    <span className="mt-1 text-xs font-bold text-navy-ink">{s.label}</span>
                    <span className={`text-[11px] ${s.status === "in_progress" ? "text-brand-600" : "text-slate-500"}`}>{s.status === "completed" ? "Completed" : s.status === "in_progress" ? `${Math.round(s.progress)}%` : "Pending"}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </Card>
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Kpi icon={<HardHat size={30} />} tone="text-emerald-600" label="Today's Work" value={String(ov.cards.activities)} sub={`${ov.cards.activities_done} done`} />
          <Kpi icon={<Users size={30} />} tone="text-brand-600" label="On Site Today" value={n0(ov.cards.workers)} sub="Workers" />
          <Kpi icon={<Truck size={30} />} tone="text-emerald-600" label="Material Received" value={ov.cards.material_pct != null ? `${Math.round(ov.cards.material_pct)}%` : "—"} sub={ov.estimate ? "Planned" : "save an estimate"} />
          <Kpi icon={<AlertTriangle size={30} />} tone="text-red-600" label="Issues / Delays" value={String(ov.cards.issues)} sub="Pending" />
        </div>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card title="Current Site Status" icon={<MapPin size={20} />}>
          {!cur ? <Empty icon={<Camera className="text-slate-400" />} text="No site activity yet – add today's work with a photo.">
            {canWrite && <button className="btn-primary btn-sm mt-1" onClick={onAddActivity}><Plus size={14} />Add Activity</button>}</Empty> : (
            <>
              <div className="relative overflow-hidden rounded-lg">
                {cur.photo_url ? <AuthImg src={cur.photo_url} className="aspect-[16/9] w-full object-cover" /> : <div className="flex aspect-[16/9] items-center justify-center bg-slate-100 text-sm text-slate-500">No photo for this activity</div>}
                {cur.work_date === ov.date && <span className="absolute right-2 top-2 rounded-md bg-emerald-600 px-2 py-0.5 text-xs font-bold text-white">● Today</span>}
              </div>
              <div className="mt-3 flex items-start justify-between gap-2">
                <div className="min-w-0"><div className="font-bold text-navy-ink">{cur.title}</div>
                  <div className="mt-1 space-y-0.5 text-xs text-slate-500">{cur.location && <div>{cur.location}</div>}<div>{prettyDate(cur.work_date)}</div><div>{[P.location, P.district].filter(Boolean).join(", ")}</div></div></div>
                <div className="w-32 shrink-0 text-right"><Pill s={cur.status} /><div className="mt-2 flex items-center gap-2"><Bar value={cur.progress} tone="bg-emerald-500" /><b className="text-xs">{cur.progress}%</b></div></div>
              </div>
            </>
          )}
        </Card>

        <Card title="Today's Activities" icon={<ClipboardList size={20} />} action={canWrite && <button className="btn-primary btn-sm" onClick={onAddActivity}><Plus size={14} />Add Activity</button>}>
          {!ov.activities.length ? <Empty text={`No activities on ${prettyDate(ov.date)}.`} /> : (
            <ul className="divide-y divide-line">
              {ov.activities.map((a) => (
                <li key={a.id} className="flex items-center gap-3 py-2">
                  <input type="checkbox" className="h-4 w-4 accent-brand-600" checked={a.status === "completed"} disabled={!canWrite} onChange={(e) => toggleActivity(a.id, e.target.checked)} />
                  <span className="min-w-0 flex-1 truncate text-sm text-navy-ink">{a.title}{a.location && <span className="text-xs text-slate-500"> · {a.location}</span>}</span>
                  <Pill s={a.status} />
                  {a.photo_url ? <AuthImg src={a.photo_url} className="h-10 w-14 shrink-0 rounded object-cover" /> : <span className="h-10 w-14 shrink-0 rounded bg-slate-100" />}
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Site Photos" icon={<Camera size={20} />} action={<button className="link" onClick={() => goto("photos")}>View All</button>}>
          {!ov.photos.length ? <Empty text="No photos yet."><button className="btn-outline btn-sm mt-1" onClick={() => goto("photos")}>Upload photos</button></Empty> : (
            <div className="grid grid-cols-3 gap-2">
              {ov.photos.map((p) => (
                <button key={p.id} className="text-left" onClick={() => goto("photos")}>
                  <AuthImg src={p.url} className="aspect-[4/3] w-full rounded-lg object-cover" />
                  <div className="mt-1 truncate text-xs font-semibold text-navy-ink">{p.caption}</div>
                  <div className="text-[11px] text-slate-500">{prettyDate(p.taken_on)}</div>
                </button>
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card title="Material Tracking" icon={<Package size={20} />} action={<button className="link" onClick={() => goto("material")}>View All</button>}>
          {!ov.materials.length ? <Empty text="Save an estimate (planned quantities) and record materials received." /> : (
            <ul className="space-y-3">
              {ov.materials.map((m) => (
                <li key={m.name} className="grid grid-cols-[1fr_auto] items-center gap-x-3 gap-y-1 text-sm">
                  <span className="truncate text-navy-ink">{m.name.split(" (")[0]}</span>
                  <span className="text-xs text-slate-500">{n0(m.received)} / {m.planned ? n0(m.planned) : "—"} {m.unit}</span>
                  <Bar value={m.pct ?? 0} /><b className="w-12 text-right text-xs">{m.pct != null ? `${Math.round(m.pct)}%` : "—"}</b>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card title="Manpower Details" icon={<Users size={20} />} action={<button className="link" onClick={() => goto("manpower")}>View All</button>}>
          {!ov.manpower.by_trade.length ? <Empty text="Attendance not marked for this day."><button className="btn-outline btn-sm mt-1" onClick={() => goto("manpower")}>Mark attendance</button></Empty> : (
            <>
              <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
                {ov.manpower.by_trade.slice(0, 4).map((t) => <div key={t.trade} className="rounded-lg bg-slate-50 px-3 py-2"><div className="truncate text-xs text-slate-500">{t.name.split(" (")[0].split(" –")[0]}</div><div className="text-lg font-extrabold text-navy-ink">{n0(t.count)}</div></div>)}
              </div>
              <div className="mt-3 text-sm font-bold text-navy-ink">Attendance Today</div>
              <div className="no-scrollbar mt-2 flex gap-3 overflow-x-auto">
                {ov.manpower.present.slice(0, 12).map((w, i) => (
                  <div key={i} className="flex w-20 shrink-0 flex-col items-center text-center">
                    <span className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-100 text-sm font-bold text-amber-700">{w.name.slice(0, 1)}</span>
                    <span className="mt-1 w-full truncate text-xs font-semibold text-navy-ink">{w.name}</span>
                    <span className="w-full truncate text-[11px] text-slate-500">{w.trade_name.split(" (")[0].split(" –")[0]}</span>
                    <span className="mt-0.5 rounded bg-emerald-50 px-1.5 text-[10px] font-semibold text-emerald-700">{w.status === "half" ? "Half day" : "Present"}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </Card>

        <Card title="Quality Check" icon={<ShieldCheck size={20} />} action={<button className="link" onClick={() => goto("quality")}>View All</button>}>
          <ul className="divide-y divide-line">
            {ov.quality.map((q) => (
              <li key={q.id} className="flex items-center justify-between gap-2 py-2 text-sm"><span className="min-w-0 truncate text-navy-ink">{q.item}</span><Pill s={q.status} /></li>
            ))}
          </ul>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-3">
        <Card title="Site Timeline (Gantt Chart)" icon={<CalendarRange size={20} />}>
          {ov.gantt.length ? <Gantt stages={ov.gantt} compact maxRows={7} /> : <CreateSchedule projectId={P.id} canEdit={canWrite} onDone={reload} />}
        </Card>
        <Card title="Site Location & Map" icon={<MapPin size={20} />}
          action={P.latitude != null && <a className="link" target="_blank" rel="noreferrer" href={`https://www.openstreetmap.org/?mlat=${P.latitude}&mlon=${P.longitude}#map=17/${P.latitude}/${P.longitude}`}>View Map</a>}>
          {P.latitude != null && P.longitude != null ? (
            <>
              <iframe title="map" className="h-56 w-full rounded-lg border border-line" loading="lazy"
                src={`https://www.openstreetmap.org/export/embed.html?bbox=${P.longitude - 0.008}%2C${P.latitude - 0.005}%2C${P.longitude + 0.008}%2C${P.latitude + 0.005}&layer=mapnik&marker=${P.latitude}%2C${P.longitude}`} />
              <div className="mt-2 flex items-center justify-between text-xs text-slate-500"><span>{[P.location, P.district].filter(Boolean).join(", ")} · {P.latitude.toFixed(5)}, {P.longitude.toFixed(5)}</span>
                {canWrite && <button className="link text-xs" onClick={setLocation}>Update to my location</button>}</div>
            </>
          ) : <Empty icon={<MapPin className="text-slate-400" />} text="Site location not set. Stand at the site and press the button (uses this phone's GPS).">
            {canWrite && <button className="btn-primary btn-sm mt-1" onClick={setLocation}><MapPin size={14} />Use my current location</button>}</Empty>}
        </Card>
        <Card title="Site Insights" icon={<Sparkles size={20} />}>
          <div className="mb-3 grid grid-cols-3 gap-1 rounded-lg bg-slate-100 p-1 text-xs font-semibold">
            {([["progress", "Progress Analysis"], ["risk", "Risk Alerts"], ["suggest", "Suggestions"]] as const).map(([k, l]) => (
              <button key={k} onClick={() => setInsTab(k)} className={`rounded-md px-2 py-1.5 ${insTab === k ? "bg-brand-600 text-white" : "text-navy-ink"}`}>{l}</button>
            ))}
          </div>
          {!shownIns.length ? <p className="text-sm text-emerald-700">No risks right now.</p> : (
            <ul className="space-y-2 text-sm">
              {shownIns.map((x, i) => { const I = x.text.startsWith("Rain") ? CloudRain : ICON_OF[x.kind] || Info; return (
                <li key={i} className="flex gap-2"><I size={17} className={`mt-0.5 shrink-0 ${x.kind === "risk" ? "text-red-500" : x.kind === "good" ? "text-emerald-600" : "text-brand-600"}`} /><span className="text-slate-700">{x.text}</span></li>
              ); })}
            </ul>
          )}
          <p className="mt-3 text-[11px] text-slate-400">From your schedule, materials, quality and issues. AI chat explanations come in Phase 6.</p>
        </Card>
      </div>
    </div>
  );
}
