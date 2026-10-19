// Site weather → construction advice. Forecast: Open-Meteo (free, no key, called from the browser).
// All advice is rule-based (no AI), so it is instant and the same every time. Text in English + Tamil.
import type { Lang } from "./i18n";

export type Day = {
  date: string; code: number; tmax: number; tmin: number; rainProb: number; rainMm: number; wind: number; gust: number; humidity: number | null;
};
export type Hour = { time: string; temp: number; rainProb: number };
export type Forecast = { days: Day[]; hours: Hour[]; now: { temp: number; code: number; wind: number; humidity: number | null } };
export type Tone = "good" | "warn" | "bad" | "info";
export type Tip = { key: string; tone: Tone; icon: string; title: string; sub: string };

type Bi = [string, string]; // [English, Tamil]
const L = (lang: Lang, b: Bi) => (lang === "ta" ? b[1] : b[0]);

// ---------------------------------------------------------------- fetch
export type Place = { lat: number; lon: number; label: string };

/** Town search – several matches so the user can pick the right one. */
export async function searchPlaces(q: string): Promise<Place[]> {
  const name = q.split(",")[0].trim();
  if (name.length < 2) return [];
  const r = await fetch(`https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(name)}&count=8&language=en&format=json`);
  const d = await r.json();
  const res = (d?.results || []) as any[];
  res.sort((a, b) => (b.country_code === "IN" ? 1 : 0) - (a.country_code === "IN" ? 1 : 0));  // India first
  return res.map((h) => ({ lat: h.latitude, lon: h.longitude, label: [h.name, h.admin2 !== h.name ? h.admin2 : "", h.admin1, h.country_code !== "IN" ? h.country : ""].filter(Boolean).join(", ") }));
}

/** Name of the place at the phone / PC location (free, no key). */
export async function placeName(lat: number, lon: number): Promise<string> {
  try {
    const r = await fetch(`https://api.bigdatacloud.net/data/reverse-geocode-client?latitude=${lat}&longitude=${lon}&localityLanguage=en`);
    const d = await r.json();
    return [d.locality || d.city, d.principalSubdivision].filter(Boolean).join(", ");
  } catch { return ""; }
}

export async function geocode(name: string): Promise<{ lat: number; lon: number; label: string } | null> {
  const q = name.split(",")[0].trim();
  if (!q) return null;
  const r = await fetch(`https://geocoding-api.open-meteo.com/v1/search?name=${encodeURIComponent(q)}&count=5&language=en&format=json&countryCode=IN`);
  const d = await r.json();
  const hit = (d?.results || [])[0];
  return hit ? { lat: hit.latitude, lon: hit.longitude, label: [hit.name, hit.admin1].filter(Boolean).join(", ") } : null;
}

export async function getForecast(lat: number, lon: number): Promise<Forecast> {
  const base = `https://api.open-meteo.com/v1/forecast?latitude=${lat}&longitude=${lon}&timezone=auto&forecast_days=7`
    + "&current=temperature_2m,weather_code,wind_speed_10m,relative_humidity_2m"
    + "&hourly=temperature_2m,precipitation_probability";
  const daily = "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,wind_speed_10m_max,wind_gusts_10m_max";
  let d: any;
  try {
    const r = await fetch(`${base}&daily=${daily},relative_humidity_2m_mean`);
    if (!r.ok) throw new Error();
    d = await r.json();
  } catch {
    const r = await fetch(`${base}&daily=${daily}`);  // humidity is optional
    if (!r.ok) throw new Error("weather service error");
    d = await r.json();
  }
  const dd = d.daily || {};
  const days: Day[] = (dd.time || []).map((t: string, i: number) => ({
    date: t, code: dd.weather_code?.[i] ?? 0, tmax: dd.temperature_2m_max?.[i] ?? 0, tmin: dd.temperature_2m_min?.[i] ?? 0,
    rainProb: dd.precipitation_probability_max?.[i] ?? 0, rainMm: dd.precipitation_sum?.[i] ?? 0,
    wind: dd.wind_speed_10m_max?.[i] ?? 0, gust: dd.wind_gusts_10m_max?.[i] ?? 0, humidity: dd.relative_humidity_2m_mean?.[i] ?? null,
  }));
  if (!days.length) throw new Error("no forecast");
  const hh = d.hourly || {};
  const today = days[0]?.date || "";
  const hours: Hour[] = (hh.time || []).map((t: string, i: number) => ({ time: t, temp: hh.temperature_2m?.[i] ?? 0, rainProb: hh.precipitation_probability?.[i] ?? 0 }))
    .filter((h: Hour) => h.time.startsWith(today) && +h.time.slice(11, 13) >= 6 && +h.time.slice(11, 13) <= 18);
  const c = d.current || {};
  return { days, hours, now: { temp: c.temperature_2m ?? days[0]?.tmax ?? 0, code: c.weather_code ?? days[0]?.code ?? 0, wind: c.wind_speed_10m ?? 0, humidity: c.relative_humidity_2m ?? null } };
}

// ---------------------------------------------------------------- classify
export const isStorm = (d: Day) => d.code >= 95;
export const isHeavy = (d: Day) => d.rainMm >= 20 || (d.rainProb >= 85 && d.rainMm >= 10);
export const isRain = (d: Day) => d.rainProb >= 60 || d.rainMm >= 5;
export const isHot = (d: Day) => d.tmax >= 35;
export const isWindy = (d: Day) => d.wind >= 30 || d.gust >= 45;
export const isHumid = (d: Day) => (d.humidity ?? 0) >= 85;

export function sky(code: number, lang: Lang): { icon: string; label: string } {
  if (code >= 95) return { icon: "storm", label: L(lang, ["Thunderstorm", "இடியுடன் மழை"]) };
  if (code >= 80) return { icon: "rain", label: L(lang, ["Rain showers", "மழை தூறல்"]) };
  if (code >= 61) return { icon: "rain", label: L(lang, ["Rain", "மழை"]) };
  if (code >= 51) return { icon: "drizzle", label: L(lang, ["Drizzle", "சாரல்"]) };
  if (code >= 45) return { icon: "fog", label: L(lang, ["Fog", "பனிமூட்டம்"]) };
  if (code >= 3) return { icon: "cloud", label: L(lang, ["Cloudy", "மேகமூட்டம்"]) };
  if (code >= 1) return { icon: "partly", label: L(lang, ["Partly cloudy", "ஓரளவு மேகம்"]) };
  return { icon: "sun", label: L(lang, ["Sunny", "வெயில்"]) };
}

/** 0–100: how good the day is for pouring concrete (slab / beam / column). */
export function pourScore(d: Day, next?: Day): number {
  let s = 100 - d.rainProb * 0.8 - d.rainMm * 3;
  if (d.tmax > 33) s -= (d.tmax - 33) * 6;
  if (isStorm(d)) s -= 60;
  if (isWindy(d)) s -= 15;
  if (next && isHeavy(next)) s -= 10;  // fresh concrete needs a dry first night
  return Math.max(0, Math.min(100, Math.round(s)));
}
export const pourOk = (d: Day) => d.rainProb < 40 && d.rainMm < 2 && !isStorm(d) && d.tmax < 38;

export function bestPourDay(days: Day[]): { index: number; score: number } | null {
  let best: { index: number; score: number } | null = null;
  days.forEach((d, i) => {
    if (!pourOk(d)) return;
    const sc = pourScore(d, days[i + 1]);
    if (!best || sc > best.score) best = { index: i, score: sc };
  });
  return best;
}

export function pourReason(d: Day, lang: Lang): string {
  const parts: string[] = [];
  parts.push(d.rainProb < 20 ? L(lang, ["no rain", "மழை இல்லை"]) : L(lang, [`rain ${d.rainProb}%`, `மழை ${d.rainProb}%`]));
  parts.push(`${Math.round(d.tmax)}°C`);
  if (d.wind < 20) parts.push(L(lang, ["calm wind", "காற்று குறைவு"]));
  return parts.join(" · ");
}

/** Best pouring hours today (06–18): lowest rain chance + not too hot. */
export function bestHours(hours: Hour[]): { from: number; to: number } | null {
  const ok = hours.filter((h) => h.rainProb < 30 && h.temp < 34).map((h) => +h.time.slice(11, 13));
  if (!ok.length) return null;
  let bestStart = ok[0], bestLen = 1, start = ok[0], len = 1;
  for (let i = 1; i < ok.length; i++) {
    if (ok[i] === ok[i - 1] + 1) { len++; } else { start = ok[i]; len = 1; }
    if (len > bestLen) { bestLen = len; bestStart = start; }
  }
  return bestLen >= 3 ? { from: bestStart, to: bestStart + bestLen } : null;
}

// ---------------------------------------------------------------- 1. today's site advice (short tiles)
export function todayTips(d: Day, lang: Lang): Tip[] {
  const t: Tip[] = [];
  if (isHeavy(d)) {
    t.push({ key: "heavy", tone: "bad", icon: "shovel", title: L(lang, ["Stop excavation", "தோண்டுதல் நிறுத்து"]), sub: L(lang, ["Drain water from pits", "குழிகளில் தண்ணீர் வெளியேற்று"]) });
    t.push({ key: "cover", tone: "bad", icon: "umbrella", title: L(lang, ["Cover fresh concrete", "புதிய கான்கிரீட்டை மூடு"]), sub: L(lang, ["Plastic / tarpaulin", "பிளாஸ்டிக் / தார்ப்பாய்"]) });
  }
  if (isRain(d)) {
    t.push({ key: "nopour", tone: "warn", icon: "ban", title: L(lang, ["No concreting / plaster", "கான்கிரீட் / பூச்சு வேண்டாம்"]), sub: L(lang, [`Rain ${d.rainProb}%`, `மழை ${d.rainProb}%`]) });
    t.push({ key: "cement", tone: "warn", icon: "package", title: L(lang, ["Cement bags inside", "சிமெண்ட் மூட்டை உள்ளே"]), sub: L(lang, ["On pallets, off the floor", "பலகை மேல், தரையில் வேண்டாம்"]) });
  }
  if (isHot(d)) {
    t.push({ key: "early", tone: "warn", icon: "sunrise", title: L(lang, ["Pour early / evening", "காலை / மாலை ஊற்று"]), sub: `${Math.round(d.tmax)}°C` });
    t.push({ key: "cure3", tone: "info", icon: "droplets", title: L(lang, ["Cure 3 times today", "இன்று 3 முறை க்யூரிங்"]), sub: L(lang, ["Keep aggregates wet", "ஜல்லியை நனைத்து வை"]) });
    t.push({ key: "breaks", tone: "info", icon: "users", title: L(lang, ["Water breaks 12–3", "12–3 தண்ணீர் இடைவேளை"]), sub: L(lang, ["Shade for workers", "தொழிலாளர்களுக்கு நிழல்"]) });
  }
  if (isWindy(d)) t.push({ key: "wind", tone: "warn", icon: "wind", title: L(lang, ["No work at height", "உயரத்தில் வேலை வேண்டாம்"]), sub: L(lang, [`Wind ${Math.round(Math.max(d.wind, d.gust))} km/h – tie sheets`, `காற்று ${Math.round(Math.max(d.wind, d.gust))} km/h – ஷீட்டை கட்டு`]) });
  if (isHumid(d) && !isRain(d)) t.push({ key: "humid", tone: "info", icon: "paint", title: L(lang, ["Paint dries slowly", "பெயிண்ட் மெதுவாக காயும்"]), sub: L(lang, ["24 h between coats", "கோட்டுகளுக்கு இடையே 24 மணி"]) });
  if (!t.length || (pourOk(d) && !isHot(d) && !isWindy(d))) {
    t.unshift({ key: "good", tone: "good", icon: "check", title: L(lang, ["Good day for work", "வேலைக்கு நல்ல நாள்"]), sub: L(lang, ["Slab · plaster · painting OK", "ஸ்லாப் · பூச்சு · பெயிண்ட் சரி"]) });
  }
  return t.slice(0, 4);
}

// ---------------------------------------------------------------- 5. safety alert (today / tomorrow)
export function safetyAlert(days: Day[], lang: Lang, dayName: (s: string) => string): { tone: "bad" | "warn"; text: string } | null {
  for (const i of [0, 1]) {
    const d = days[i];
    if (!d) continue;
    const when = i === 0 ? L(lang, ["today", "இன்று"]) : dayName(d.date);
    if (isStorm(d)) return { tone: "bad", text: L(lang, [`Thunderstorm ${when} – stop crane, steel and terrace work during the storm. Keep workers away from steel bars.`,
      `${when} இடியுடன் மழை – புயலின் போது கிரேன், கம்பி, மொட்டைமாடி வேலை நிறுத்து. கம்பிகளிடம் இருந்து தொழிலாளர்களை விலக்கி வை.`]) };
    if (isHeavy(d)) return { tone: "bad", text: L(lang, [`Heavy rain ${when} (${Math.round(d.rainMm)} mm) – keep workers out of deep trenches; check shoring and electrical points.`,
      `${when} கனமழை (${Math.round(d.rainMm)} mm) – ஆழமான குழிகளில் தொழிலாளர்கள் வேண்டாம்; முட்டுகள், மின் இணைப்புகளை சரிபார்.`]) };
    if (d.gust >= 50) return { tone: "warn", text: L(lang, [`Strong wind ${when} (${Math.round(d.gust)} km/h) – no scaffolding or roof work; tie down sheets and shuttering.`,
      `${when} பலத்த காற்று (${Math.round(d.gust)} km/h) – சாரம், கூரை வேலை வேண்டாம்; ஷீட், ஷட்டரிங் கட்டு.`]) };
    if (d.tmax >= 39) return { tone: "warn", text: L(lang, [`Very hot ${when} (${Math.round(d.tmax)}°C) – rest from 12 to 3, drinking water and shade at site.`,
      `${when} கடும் வெயில் (${Math.round(d.tmax)}°C) – 12 முதல் 3 வரை ஓய்வு, குடிநீர், நிழல் ஏற்பாடு.`]) };
  }
  return null;
}

// ---------------------------------------------------------------- 3. stage-wise tips
export type Stage = { name: string; group: string; progress: number };
export function stageTips(stages: Stage[], days: Day[], lang: Lang): (Tip & { stage: string })[] {
  const d = days[0];
  const rainSoon = days.slice(0, 3).some(isRain);
  const out: (Tip & { stage: string })[] = [];
  for (const s of stages) {
    const n = `${s.name} ${s.group}`.toLowerCase();
    const add = (tone: Tone, icon: string, b: Bi, sub: Bi) => out.push({ key: `${s.name}-${icon}`, stage: s.name, tone, icon, title: L(lang, b), sub: L(lang, sub) });
    if (/excavat|foundation|footing|pcc|plinth/.test(n)) {
      if (d && isRain(d)) add("warn", "shovel", ["Check trench for water before PCC", "PCC முன் குழியில் தண்ணீர் உள்ளதா பார்"], ["Pump out, then compact", "தண்ணீர் இறைத்து, அழுத்து"]);
      else add("info", "shovel", ["Compact & level before PCC", "PCC முன் அழுத்தி சமன் செய்"], ["Anti-termite treatment first", "முதலில் கரையான் தடுப்பு"]);
    } else if (/slab|beam|column|roof|structure|lintel/.test(n)) {
      if (rainSoon) add("warn", "umbrella", ["Rain in 3 days – plan pour on a dry day", "3 நாளில் மழை – காய்ந்த நாளில் ஊற்று"], ["Keep plastic sheets ready", "பிளாஸ்டிக் ஷீட் தயார்"]);
      if (d && isHot(d)) add("warn", "sunrise", ["Pour before 10 am", "காலை 10 மணிக்கு முன் ஊற்று"], ["Hot day – slump loss", "வெயில் – கலவை சீக்கிரம் இறுகும்"]);
      add("info", "ruler", ["Check cover blocks & shuttering", "கவர் பிளாக், ஷட்டரிங் சரிபார்"], ["Before every pour", "ஒவ்வொரு ஊற்றுக்கும் முன்"]);
    } else if (/brick|masonry|block/.test(n)) {
      add("info", "brick", ["Soak bricks before use", "செங்கலை முன்பே நனை"], ["At least 2 hours", "குறைந்தது 2 மணி நேரம்"]);
      add("info", "ruler", ["Max 1 m height per day", "நாளுக்கு அதிகபட்சம் 1 மீ உயரம்"], ["Mortar needs time to set", "சாந்து இறுக நேரம் வேண்டும்"]);
      if (rainSoon) add("warn", "umbrella", ["Cover the top of new walls", "புதிய சுவர் மேல் மூடு"], ["Rain washes out mortar", "மழை சாந்தை கழுவும்"]);
    } else if (/plaster/.test(n)) {
      if (d && isHot(d)) add("warn", "sun", ["Avoid afternoon sun on plaster", "மதிய வெயிலில் பூச்சு வேண்டாம்"], ["Cure 7 days", "7 நாள் க்யூரிங்"]);
      else add("info", "droplets", ["Cure plaster for 7 days", "பூச்சுக்கு 7 நாள் க்யூரிங்"], ["Wet the wall before plastering", "பூசும் முன் சுவரை நனை"]);
    } else if (/paint|finish|floor|tile/.test(n)) {
      if (days.slice(0, 2).some((x) => isRain(x) || isHumid(x))) add("warn", "paint", ["Paint dries slowly – 24 h between coats", "பெயிண்ட் மெதுவாக காயும் – கோட்டுகளுக்கு 24 மணி"], ["Humid / rainy days ahead", "ஈரப்பதம் / மழை நாட்கள்"]);
      else add("good", "paint", ["Dry days – good for painting", "காய்ந்த நாட்கள் – பெயிண்டுக்கு நல்லது"], ["Putty must be fully dry", "புட்டி முழுதும் காய வேண்டும்"]);
    } else if (/electric|plumb|conduit|service/.test(n)) {
      add("info", "plug", ["Conduits & pipes before plaster", "பூச்சுக்கு முன் குழாய்கள்"], ["Pressure-test water lines", "தண்ணீர் குழாய் அழுத்த சோதனை"]);
    } else {
      add("info", "check", [`${s.name}: check today's work list`, `${s.name}: இன்றைய வேலை பட்டியல் பார்`], [`${s.progress}% done`, `${s.progress}% முடிந்தது`]);
    }
  }
  // at most 2 tips per stage, 4 in total
  const per: Record<string, number> = {};
  return out.filter((t) => (per[t.stage] = (per[t.stage] || 0) + 1) <= 2).slice(0, 4);
}

/** Week summary for the planner chips. */
export function weekSummary(days: Day[]) {
  return { rain: days.filter(isRain).length, hot: days.filter(isHot).length, pour: days.filter(pourOk).length,
    storm: days.filter(isStorm).length, mm: Math.round(days.reduce((a, d) => a + d.rainMm, 0)) };
}

// ---------------------------------------------------------------- 4. curing (IS 456: 7 days OPC; 10 days PPC / hot-dry weather)
export function curingDays(days: Day[]): number {
  return days.slice(0, 3).some(isHot) ? 10 : 7;
}
