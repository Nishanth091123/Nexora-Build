import { useCallback, useEffect, useState } from "react";
import {
  AlertTriangle, Ban, BrickWall, CalendarDays, Check, CheckCircle2, Cloud, CloudDrizzle, CloudFog, CloudLightning, CloudRain, CloudSun,
  ChevronDown, Droplets, HardHat, LocateFixed, MapPin, Plus, Search, Package, PaintRoller, Plug, RefreshCw, Ruler, Shovel, Sun, Sunrise, Umbrella, Users, Wind, X,
} from "lucide-react";
import { Card } from "../ui";
import { api } from "../../lib/api";
import { useAuth } from "../../lib/auth";
import { useI18n, type Lang } from "../../lib/i18n";
import {
  bestHours, bestPourDay, curingDays, geocode, getForecast, placeName, pourOk, pourReason, pourScore, safetyAlert, searchPlaces, sky, stageTips, todayTips, weekSummary, type Place,
  type Forecast, type Stage, type Tip, type Tone,
} from "../../lib/siteWeather";

const ICONS: Record<string, any> = {
  sun: Sun, partly: CloudSun, cloud: Cloud, fog: CloudFog, drizzle: CloudDrizzle, rain: CloudRain, storm: CloudLightning,
  shovel: Shovel, umbrella: Umbrella, ban: Ban, package: Package, sunrise: Sunrise, droplets: Droplets, users: Users, wind: Wind,
  paint: PaintRoller, check: CheckCircle2, ruler: Ruler, brick: BrickWall, plug: Plug,
};
const SKY_COLOR: Record<string, string> = {
  sun: "text-amber-500", partly: "text-amber-500", cloud: "text-slate-400", fog: "text-slate-400", drizzle: "text-sky-500", rain: "text-sky-600", storm: "text-violet-600",
};
const TONE: Record<Tone, string> = {
  good: "bg-emerald-50 text-emerald-700 ring-emerald-200", warn: "bg-amber-50 text-amber-800 ring-amber-200",
  bad: "bg-red-50 text-red-700 ring-red-200", info: "bg-sky-50 text-sky-800 ring-sky-200",
};
const TONE_ICON: Record<Tone, string> = { good: "bg-emerald-500", warn: "bg-amber-500", bad: "bg-red-500", info: "bg-sky-500" };

type Ctx = { project: any; stages: Stage[]; curing: { title: string; location: string; cast_on: string; day: number }[]; can_set_location: boolean };
export type Sel = { kind: "project" } | { kind: "gps" } | ({ kind: "place" } & Place);
export type WeatherState = {
  ctx: Ctx | null; fc: Forecast | null; place: string; err: string; loading: boolean; needPlace: boolean;
  sel: Sel; places: Place[]; projectLabel: string;
  setPlace: (town: string) => Promise<void>; reload: () => void;
  choose: (s: Sel) => void; addPlace: (p: Place) => void; removePlace: (p: Place) => void;
};

const T = (lang: Lang, en: string, ta: string) => (lang === "ta" ? ta : en);
const dayName = (iso: string, lang: Lang, long = false) =>
  new Date(iso + "T00:00:00").toLocaleDateString(lang === "ta" ? "ta-IN" : "en-IN", { weekday: long ? "long" : "short" });
const dayNum = (iso: string) => new Date(iso + "T00:00:00").toLocaleDateString("en-IN", { day: "2-digit", month: "short" });
const GEO_KEY = (pid: number) => `nexora_geo_${pid}`;
const PLACES_KEY = "nexora_wx_places";
const SEL_KEY = "nexora_wx_sel";
const readJson = (k: string, d: any) => { try { return JSON.parse(localStorage.getItem(k) || "null") ?? d; } catch { return d; } };
const writeJson = (k: string, v: any) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* ignore */ } };
const samePlace = (a: Place, b: Place) => Math.abs(a.lat - b.lat) < 0.01 && Math.abs(a.lon - b.lon) < 0.01;

function gpsNow(): Promise<{ lat: number; lon: number }> {
  return new Promise((ok, no) => {
    if (!navigator.geolocation) return no(new Error("Location is not available on this device"));
    navigator.geolocation.getCurrentPosition((p) => ok({ lat: p.coords.latitude, lon: p.coords.longitude }),
      () => no(new Error("Allow location access in the browser (address bar → location)")), { enableHighAccuracy: false, timeout: 12000, maximumAge: 600000 });
  });
}

/** Weather for: the selected project's site (default), my current location, or a saved / searched town. */
export function useSiteWeather(): WeatherState {
  const { currentProject } = useAuth();
  const pid = currentProject?.id;
  const [ctx, setCtx] = useState<Ctx | null>(null);
  const [fc, setFc] = useState<Forecast | null>(null);
  const [place, setPlaceLabel] = useState("");
  const [projectLabel, setProjectLabel] = useState("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);
  const [needPlace, setNeedPlace] = useState(false);
  const [tick, setTick] = useState(0);
  const [sel, setSel] = useState<Sel>(() => readJson(SEL_KEY, { kind: "project" }));
  const [places, setPlaces] = useState<Place[]>(() => readJson(PLACES_KEY, []));

  const loadForecast = useCallback(async (lat: number, lon: number, label: string) => {
    setFc(await getForecast(lat, lon));
    setPlaceLabel(label);
    setNeedPlace(false);
  }, []);

  useEffect(() => {
    if (!pid) return;
    let alive = true;
    setLoading(true); setErr(""); setFc(null); setNeedPlace(false);
    (async () => {
      let c: Ctx | null = null;
      try { c = await api<Ctx>(`/api/projects/${pid}/weather-context`); } catch { /* weather still works without it */ }
      if (!alive) return;
      setCtx(c);
      const p = c?.project || currentProject;
      setProjectLabel(p?.location || p?.district || p?.name || "");
      try {
        if (sel.kind === "gps") {
          const g = await gpsNow();
          const name = await placeName(g.lat, g.lon);
          return await loadForecast(g.lat, g.lon, name || "My location");
        }
        if (sel.kind === "place") return await loadForecast(sel.lat, sel.lon, sel.label);
        if (p?.latitude != null && p?.longitude != null) return await loadForecast(p.latitude, p.longitude, p.location || p.district || "Site");
        const saved = readJson(GEO_KEY(pid), null);
        if (saved) return await loadForecast(saved.lat, saved.lon, saved.label);
        const g = await geocode(p?.location || p?.district || "");
        if (g) {
          writeJson(GEO_KEY(pid), g);
          return await loadForecast(g.lat, g.lon, g.label);
        }
        setNeedPlace(true);
      } catch (e: any) {
        if (alive) setErr(navigator.onLine === false ? "offline" : sel.kind === "gps" ? (e?.message || "gps") : "failed");
      }
    })().finally(() => alive && setLoading(false));
    return () => { alive = false; };
  }, [pid, tick, sel]);  // eslint-disable-line react-hooks/exhaustive-deps

  const setPlace = async (town: string) => {
    if (!pid) return;
    const g = await geocode(town);
    if (!g) throw new Error("Town not found – try the nearest town / district name");
    writeJson(GEO_KEY(pid), g);
    if (ctx?.can_set_location) api(`/api/projects/${pid}/site/location`, { method: "PUT", body: { latitude: g.lat, longitude: g.lon } }).catch(() => {});
    await loadForecast(g.lat, g.lon, g.label);
  };
  const choose = (s: Sel) => { setSel(s); writeJson(SEL_KEY, s); };
  const addPlace = (p: Place) => {
    const next = [p, ...places.filter((x) => !samePlace(x, p))].slice(0, 8);
    setPlaces(next); writeJson(PLACES_KEY, next);
    choose({ kind: "place", ...p });
  };
  const removePlace = (p: Place) => {
    const next = places.filter((x) => !samePlace(x, p));
    setPlaces(next); writeJson(PLACES_KEY, next);
    if (sel.kind === "place" && samePlace(sel, p)) choose({ kind: "project" });
  };
  return { ctx, fc, place, err, loading, needPlace, sel, places, projectLabel, setPlace, reload: () => setTick((x) => x + 1), choose, addPlace, removePlace };
}

/** Location chooser: project site · my current location · saved towns · search. */
function LocationPicker({ w }: { w: WeatherState }) {
  const { lang } = useI18n();
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const [res, setRes] = useState<Place[] | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    if (q.trim().length < 2) { setRes(null); return; }
    const t = setTimeout(() => { setBusy(true); searchPlaces(q).then(setRes).catch(() => setRes([])).finally(() => setBusy(false)); }, 350);
    return () => clearTimeout(t);
  }, [q]);
  const isSel = (p: Place) => w.sel.kind === "place" && samePlace(w.sel, p);
  const row = (active: boolean, icon: any, label: string, sub: string, onClick: () => void, extra?: any) => (
    <div className={`flex items-center gap-2 rounded-lg px-2 py-1.5 text-sm ${active ? "bg-brand-50 text-brand-700" : "hover:bg-slate-50"}`}>
      <button className="flex min-w-0 flex-1 items-center gap-2 text-left" onClick={() => { onClick(); setOpen(false); setQ(""); }}>
        <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg ${active ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-500"}`}>{icon}</span>
        <span className="min-w-0"><span className="block truncate font-semibold">{label}</span>{sub && <span className="block truncate text-[11px] text-slate-500">{sub}</span>}</span>
      </button>
      {active ? <Check size={15} className="shrink-0" /> : extra}
    </div>
  );
  const kindIcon = w.sel.kind === "gps" ? <LocateFixed size={13} /> : w.sel.kind === "place" ? <Search size={13} /> : <MapPin size={13} />;
  return (
    <div className="relative">
      <button className="flex max-w-[190px] items-center gap-1 rounded-full border border-line bg-white px-2.5 py-1 text-xs font-semibold text-navy-ink hover:border-brand-300" onClick={() => setOpen(!open)}>
        {kindIcon}<span className="truncate">{w.place || w.projectLabel || T(lang, "Location", "இடம்")}</span><ChevronDown size={13} className="shrink-0" />
      </button>
      {open && (
        <>
          <div className="fixed inset-0 z-30" onClick={() => setOpen(false)} />
          <div className="absolute right-0 z-40 mt-2 w-72 rounded-xl border border-line bg-white p-2 shadow-xl">
            <div className="relative mb-2">
              <Search size={15} className="absolute left-2.5 top-2.5 text-slate-400" />
              <input autoFocus className="input pl-8" placeholder={T(lang, "Search town / city…", "ஊர் / நகரம் தேடு…")} value={q} onChange={(e) => setQ(e.target.value)} />
            </div>
            {res !== null ? (
              <div className="max-h-64 overflow-auto">
                {busy && <p className="px-2 py-1 text-xs text-slate-500">…</p>}
                {!busy && !res.length && <p className="px-2 py-1 text-xs text-slate-500">{T(lang, "No match – try the nearest town or district", "பொருத்தம் இல்லை – அருகிலுள்ள ஊர் / மாவட்டம் முயற்சி செய்")}</p>}
                {res.map((p) => row(false, <Plus size={14} />, p.label.split(",")[0], p.label.split(",").slice(1).join(",").trim(), () => w.addPlace(p)))}
              </div>
            ) : (
              <div className="space-y-0.5">
                {row(w.sel.kind === "project", <MapPin size={14} />, T(lang, "Project site", "திட்ட தளம்"), w.projectLabel, () => w.choose({ kind: "project" }))}
                {row(w.sel.kind === "gps", <LocateFixed size={14} />, T(lang, "My current location", "என் தற்போதைய இடம்"), T(lang, "Uses this phone / PC location", "இந்த போன் / PC இருப்பிடம்"), () => w.choose({ kind: "gps" }))}
                {w.places.length > 0 && <div className="px-2 pt-2 text-[10px] font-bold uppercase tracking-wide text-slate-400">{T(lang, "Saved places", "சேமித்த இடங்கள்")}</div>}
                {w.places.map((p) => row(isSel(p), <Search size={14} />, p.label.split(",")[0], p.label.split(",").slice(1).join(",").trim(), () => w.choose({ kind: "place", ...p }),
                  <button className="rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600" title={T(lang, "Remove", "நீக்கு")} onClick={() => w.removePlace(p)}><X size={13} /></button>))}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}

function TipTile({ tip }: { tip: Tip }) {
  const I = ICONS[tip.icon] || CheckCircle2;
  return (
    <div className={`flex items-center gap-2.5 rounded-xl p-2.5 ring-1 ${TONE[tip.tone]}`}>
      <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-white ${TONE_ICON[tip.tone]}`}><I size={19} /></span>
      <div className="min-w-0"><div className="text-[13px] font-bold leading-tight">{tip.title}</div><div className="truncate text-[11px] opacity-80">{tip.sub}</div></div>
    </div>
  );
}

function PlaceForm({ w }: { w: WeatherState }) {
  const { lang } = useI18n();
  const [town, setTown] = useState("");
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  return (
    <form className="space-y-2" onSubmit={async (e) => { e.preventDefault(); setBusy(true); setMsg(""); try { await w.setPlace(town); } catch (x: any) { setMsg(x.message); } finally { setBusy(false); } }}>
      <p className="text-sm text-slate-600">{T(lang, "Which town is this site in? (asked once)", "இந்த தளம் எந்த ஊரில் உள்ளது? (ஒருமுறை மட்டும்)")}</p>
      <div className="flex gap-2">
        <input className="input" placeholder="e.g. Thanjavur" value={town} onChange={(e) => setTown(e.target.value)} />
        <button className="btn-primary" disabled={!town.trim() || busy}><MapPin size={16} />{busy ? "…" : "OK"}</button>
      </div>
      {msg && <p className="text-xs text-red-600">{msg}</p>}
    </form>
  );
}

/** Right of the Home hero: now + safety alert + today's advice tiles + best pouring hours. */
export function TodayWeatherCard({ w }: { w: WeatherState }) {
  const { lang } = useI18n();
  const d = w.fc?.days[0];
  const s = w.fc ? sky(w.fc.now.code, lang) : null;
  const SkyI = s ? ICONS[s.icon] : Sun;
  const alert = w.fc ? safetyAlert(w.fc.days, lang, (x) => dayName(x, lang, true)) : null;
  // a pouring window is shown only when the whole day is fit for concrete (same rule as the 7-day planner)
  const dayOk = !!d && pourOk(d);
  const hrs = w.fc && dayOk ? bestHours(w.fc.hours) : null;
  return (
    <Card title={w.sel.kind === "project" ? T(lang, "Site weather today", "இன்றைய தள வானிலை") : T(lang, "Weather today", "இன்றைய வானிலை")} icon={<HardHat size={20} />}
      action={<LocationPicker w={w} />}>
      {w.needPlace ? <PlaceForm w={w} /> : w.err ? (
        <div className="flex items-center justify-between gap-2 text-sm text-slate-500">{w.err === "offline" ? T(lang, "Offline – weather needs the internet.", "இணையம் இல்லை – வானிலைக்கு இணையம் தேவை.") : w.err === "failed" ? T(lang, "Weather could not load.", "வானிலை ஏற்றவில்லை.") : w.err}
          <button className="btn-ghost btn-sm" onClick={w.reload}><RefreshCw size={14} /></button></div>
      ) : !w.fc || !d || !s ? <div className="h-48 animate-pulse rounded-xl bg-slate-100" /> : (
        <div className="space-y-3">
          {alert && (
            <div className={`flex items-start gap-2 rounded-xl p-2.5 text-[13px] font-semibold ${alert.tone === "bad" ? "bg-red-600 text-white" : "bg-amber-400 text-amber-950"}`}>
              <AlertTriangle size={18} className="mt-0.5 shrink-0" />{alert.text}
            </div>
          )}
          <div className="flex items-center gap-4">
            <SkyI size={52} className={SKY_COLOR[s.icon]} strokeWidth={1.6} />
            <div>
              <div className="text-4xl font-extrabold leading-none text-navy-ink">{Math.round(w.fc.now.temp)}°</div>
              <div className="text-sm text-slate-600">{s.label}</div>
            </div>
            <div className="ml-auto grid gap-1 text-right text-xs text-slate-600">
              <span><b className="text-navy-ink">{Math.round(d.tmax)}°</b> / {Math.round(d.tmin)}°</span>
              <span className="flex items-center justify-end gap-1"><CloudRain size={13} className="text-sky-500" />{d.rainProb}%</span>
              <span className="flex items-center justify-end gap-1"><Wind size={13} className="text-slate-400" />{Math.round(d.wind)} km/h</span>
            </div>
          </div>
          <div className="grid gap-2 sm:grid-cols-2">{todayTips(d, lang).map((t) => <TipTile key={t.key} tip={t} />)}</div>
          {w.fc.hours.length > 0 && (
            <div>
              <div className="mb-1 flex items-center justify-between text-[11px] font-semibold text-slate-500">
                <span>{T(lang, "Rain chance · working hours", "மழை வாய்ப்பு · வேலை நேரம்")}</span>
                {hrs ? <span className="text-emerald-700">{T(lang, "Best to pour", "ஊற்ற சிறந்த நேரம்")} {hrs.from}:00–{hrs.to}:00</span>
                  : !dayOk ? <span className="text-red-600">{T(lang, "No pouring today", "இன்று ஊற்ற வேண்டாம்")}{d && d.rainProb >= 40 ? ` · ${T(lang, "rain", "மழை")} ${d.rainProb}%` : ""}</span>
                  : <span className="text-amber-700">{T(lang, "No safe pouring window today", "இன்று ஊற்ற சரியான நேரம் இல்லை")}</span>}
              </div>
              <div className="flex h-12 items-end gap-[3px]">
                {w.fc.hours.map((h) => {
                  const hr = +h.time.slice(11, 13);
                  const good = hrs && hr >= hrs.from && hr < hrs.to;
                  return (
                    <div key={h.time} className="flex flex-1 flex-col items-center gap-0.5" title={`${hr}:00 · ${h.rainProb}% · ${Math.round(h.temp)}°C`}>
                      <div className={`flex h-8 w-full items-end rounded-sm ${good ? "bg-emerald-100" : "bg-slate-100"}`}>
                        <div className={`w-full rounded-sm ${good ? "bg-emerald-500" : h.rainProb >= 50 ? "bg-sky-600" : "bg-sky-300"}`} style={{ height: `${Math.max(8, h.rainProb)}%` }} />
                      </div>
                      <span className="text-[9px] text-slate-400">{hr % 3 === 0 ? hr : ""}</span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

/** Below the quick buttons: 7-day planner with the best pour day, stage-wise tips and the curing tracker. */
export function WeekWeatherRow({ w }: { w: WeatherState }) {
  const { lang } = useI18n();
  if (!w.fc || !w.fc.days.length || w.needPlace || w.err) return null;
  const days = w.fc.days;
  const best = bestPourDay(days);
  const bd = best ? days[best.index] : null;
  const cureN = curingDays(days);
  const tips = stageTips(w.ctx?.stages || [], days, lang);
  const curing = (w.ctx?.curing || []).filter((c) => c.day <= cureN + 2);
  const hotToday = days[0].tmax >= 35;
  const ws = weekSummary(days);
  return (
    <div className="grid items-start gap-4 xl:grid-cols-[1.55fr_1fr]">
      <Card title={T(lang, "7-day site planner", "7 நாள் தள திட்டம்")} icon={<CalendarDays size={20} />}>
        <div className={`mb-3 flex items-center gap-3 rounded-xl p-3 ${bd ? "bg-emerald-600 text-white" : "bg-amber-100 text-amber-900"}`}>
          <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-white/20">{bd ? <Check size={26} strokeWidth={3} /> : <Umbrella size={24} />}</span>
          {bd ? (
            <div><div className="text-xs font-semibold uppercase tracking-wide opacity-90">{T(lang, "Best day for slab / concrete pour", "ஸ்லாப் / கான்கிரீட் ஊற்ற சிறந்த நாள்")}</div>
              <div className="text-lg font-extrabold leading-tight">{best!.index === 0 ? T(lang, "Today", "இன்று") : dayName(bd.date, lang, true)}, {dayNum(bd.date)}
                <span className="ml-2 text-sm font-semibold opacity-90">{pourReason(bd, lang)}</span></div></div>
          ) : <div className="text-sm font-bold">{T(lang, "No safe day to pour concrete in the next 7 days – keep plastic sheets ready.", "அடுத்த 7 நாளில் கான்கிரீட் ஊற்ற பாதுகாப்பான நாள் இல்லை – பிளாஸ்டிக் ஷீட் தயாராக வை.")}</div>}
        </div>
        <div className="grid grid-cols-7 gap-1.5">
          {days.map((d, i) => {
            const s = sky(d.code, lang);
            const I = ICONS[s.icon];
            const ok = pourOk(d);
            const isBest = best?.index === i;
            const sc = pourScore(d, days[i + 1]);
            return (
              <div key={d.date} className={`relative flex flex-col items-center gap-1 rounded-xl border p-1.5 text-center ${isBest ? "border-emerald-500 bg-emerald-50 ring-2 ring-emerald-500" : "border-line"}`}>
                {isBest && <span className="absolute -top-2 rounded-full bg-emerald-600 px-1.5 text-[9px] font-bold text-white">BEST</span>}
                <div className="text-[11px] font-bold text-navy-ink">{i === 0 ? T(lang, "Today", "இன்று") : dayName(d.date, lang)}</div>
                <div className="text-[10px] text-slate-400">{dayNum(d.date)}</div>
                <I size={26} className={SKY_COLOR[s.icon]} />
                <div className="text-[12px] font-bold text-navy-ink">{Math.round(d.tmax)}°<span className="font-normal text-slate-400"> {Math.round(d.tmin)}°</span></div>
                <div className="flex h-14 w-3 items-end rounded-full bg-slate-100" title={`${d.rainProb}% · ${d.rainMm.toFixed(1)} mm`}>
                  <div className={`w-full rounded-full ${d.rainProb >= 60 ? "bg-sky-600" : "bg-sky-300"}`} style={{ height: `${Math.max(6, d.rainProb)}%` }} />
                </div>
                <div className="text-[10px] text-sky-700">{d.rainProb}%</div>
                <div className={`mt-0.5 flex w-full items-center justify-center gap-0.5 rounded-md py-0.5 text-[10px] font-bold ${ok ? "bg-emerald-100 text-emerald-700" : "bg-red-50 text-red-600"}`}
                  title={`${T(lang, "Pour score", "ஊற்று மதிப்பெண்")} ${sc}/100`}>
                  {ok ? <Check size={11} strokeWidth={3} /> : <X size={11} strokeWidth={3} />}{T(lang, "Pour", "ஊற்று")}
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
          {[[Check, "bg-emerald-50 text-emerald-700", ws.pour, T(lang, "pour days", "ஊற்றும் நாட்கள்")],
            [CloudRain, "bg-sky-50 text-sky-700", ws.rain, T(lang, `rain days · ${ws.mm} mm`, `மழை நாட்கள் · ${ws.mm} mm`)],
            [Sun, "bg-amber-50 text-amber-700", ws.hot, T(lang, "hot days (35°C+)", "வெயில் நாட்கள் (35°C+)")],
            [CloudLightning, "bg-violet-50 text-violet-700", ws.storm, T(lang, "storm days", "இடி நாட்கள்")]].map(([I, cls, v, l]: any) => (
            <div key={l} className={`flex items-center gap-2 rounded-xl p-2.5 ${cls}`}><I size={20} /><div><div className="text-lg font-extrabold leading-none">{v}</div><div className="text-[11px]">{l}</div></div></div>
          ))}
        </div>
        <p className="mt-2 text-[11px] text-slate-500"><Check size={11} className="inline text-emerald-600" /> {T(lang, "Pour OK = rain below 40%, no thunderstorm, below 38°C. Hover a rain bar for mm.", "ஊற்றலாம் = மழை 40%-க்கு கீழ், இடி இல்லை, 38°C-க்கு கீழ்.")}</p>
      </Card>
      <div className="grid gap-4">
        <Card title={T(lang, "Curing tracker", "க்யூரிங் கண்காணிப்பு")} icon={<Droplets size={20} className="text-sky-600" />}
          action={hotToday && curing.length > 0 && <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-bold text-amber-800">{T(lang, "Hot – cure more often today", "வெயில் – இன்று அடிக்கடி நனை")}</span>}>
          {!curing.length ? (
            <p className="text-sm text-slate-500">{T(lang, "No concrete work in the last 2 weeks. Concrete work added in Site → Daily Work (casting, slab, column…) shows here with its curing days.",
              "கடந்த 2 வாரத்தில் கான்கிரீட் வேலை இல்லை. Site → Daily Work-ல் சேர்க்கும் கான்கிரீட் வேலை (casting, slab, column…) க்யூரிங் நாட்களுடன் இங்கே தெரியும்.")}</p>
          ) : (
            <ul className="space-y-2.5">
              {curing.map((c) => {
                const done = c.day > cureN;
                return (
                  <li key={c.title + c.cast_on}>
                    <div className="flex items-center justify-between text-sm"><b className="truncate text-navy-ink">{c.title}{c.location && <span className="font-normal text-slate-500"> · {c.location}</span>}</b>
                      <span className={`shrink-0 text-xs font-bold ${done ? "text-emerald-700" : "text-sky-700"}`}>{done ? T(lang, "Curing done", "க்யூரிங் முடிந்தது") : `${T(lang, "Day", "நாள்")} ${c.day} / ${cureN}`}</span></div>
                    <div className="mt-1 flex gap-1">
                      {Array.from({ length: cureN }, (_, i) => (
                        <span key={i} className={`h-2.5 flex-1 rounded-full ${i < c.day ? (done ? "bg-emerald-500" : "bg-sky-500") : "bg-slate-200"} ${i === c.day - 1 && !done ? "ring-2 ring-sky-300" : ""}`} />
                      ))}
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
          <p className="mt-2 text-[10px] text-slate-400">{T(lang, `IS 456: keep concrete wet ${cureN} days${cureN === 10 ? " (hot weather / PPC)" : " (OPC; 10 days for PPC or hot weather)"}.`, `IS 456: கான்கிரீட்டை ${cureN} நாள் ஈரமாக வை.`)}</p>
        </Card>
        <Card title={T(lang, "Tips for current work", "நடப்பு வேலைக்கான குறிப்புகள்")} icon={<HardHat size={20} />}>
          {!tips.length ? <p className="text-sm text-slate-500">{T(lang, "Create the project schedule (Site → Overview) to get tips for each stage of work.", "ஒவ்வொரு வேலை கட்டத்திற்கும் குறிப்புகள் பெற திட்ட அட்டவணையை உருவாக்கவும் (Site → Overview).")}</p> : (
            <div className="grid gap-3">
              {Array.from(new Set(tips.map((t) => t.stage))).map((st) => (
                <div key={st}>
                  <div className="mb-1 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wide text-slate-500"><HardHat size={13} />{st}</div>
                  <div className="grid gap-2">{tips.filter((t) => t.stage === st).map((t) => <TipTile key={t.key} tip={t} />)}</div>
                </div>
              ))}
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
