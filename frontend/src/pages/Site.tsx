import { useCallback, useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  AlertTriangle, Camera, CheckSquare, ClipboardList, FileText, HardHat, LayoutDashboard, Package, Plus, ShieldAlert, Truck, Users,
} from "lucide-react";
import Page from "../components/Page";
import OverviewTab from "../components/site/OverviewTab";
import { ActivityModal, DailyWorkTab, ManpowerTab, MaterialsTab, PhotosTab, QualityTab, ReportsTab, SafetyTab } from "../components/site/Tabs";
import { today, type Overview } from "../components/site/common";
import { Empty, PillTabs, toast } from "../components/ui";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

type Tab = "overview" | "daily" | "photos" | "quality" | "material" | "manpower" | "safety" | "reports";

export default function SitePage() {
  const { t } = useI18n();
  const { currentProject, reloadProjects } = useAuth();
  const pid = currentProject?.id;
  const allowed = !!currentProject?.permissions?.site;
  // the tab is kept in the address (?tab=photos) so a reload – e.g. after the phone camera app – returns to it
  const [params, setParams] = useSearchParams();
  const TABS: Tab[] = ["overview", "daily", "photos", "quality", "material", "manpower", "safety", "reports"];
  const tab: Tab = TABS.includes(params.get("tab") as Tab) ? (params.get("tab") as Tab) : "overview";
  const setTab = (t: Tab) => setParams((p) => { const n = new URLSearchParams(p); if (t === "overview") n.delete("tab"); else n.set("tab", t); return n; }, { replace: true });
  const [day, setDay] = useState(today());
  const [ov, setOv] = useState<Overview | null>(null);
  const [menu, setMenu] = useState(false);
  const [actOpen, setActOpen] = useState(false);
  const [tick, setTick] = useState(0);

  const load = useCallback(async () => {
    if (!pid || !allowed) return;
    try { setOv(await api<Overview>(`/api/projects/${pid}/site/overview?day=${day}`)); }
    catch (e: any) { toast(e.message, "err"); }
  }, [pid, allowed, day]);
  useEffect(() => { load(); }, [load, tick]);
  useEffect(() => { const f = () => setTick((x) => x + 1); window.addEventListener("nexora-synced", f); return () => window.removeEventListener("nexora-synced", f); }, []);
  const changed = () => { setTick((x) => x + 1); reloadProjects?.(); };

  if (!currentProject) return <Page title={t("Site Management")} subtitle="Track progress, manage site activities, quality and materials"><Empty text="Create a project first (Projects page)." /></Page>;
  if (!allowed) return <Page title={t("Site Management")} subtitle="Track progress, manage site activities, quality and materials"><Empty text="You don't have Site access for this project. Ask the owner." /></Page>;

  const tabs = [
    { id: "overview" as Tab, label: "Overview", icon: <LayoutDashboard size={18} /> }, { id: "daily" as Tab, label: "Daily Work", icon: <ClipboardList size={18} /> },
    { id: "photos" as Tab, label: "Site Photos", icon: <Camera size={18} /> }, { id: "quality" as Tab, label: "Quality Check", icon: <CheckSquare size={18} /> },
    { id: "material" as Tab, label: "Material Tracking", icon: <Truck size={18} /> }, { id: "manpower" as Tab, label: "Manpower", icon: <Users size={18} /> },
    { id: "safety" as Tab, label: "Safety", icon: <ShieldAlert size={18} /> }, { id: "reports" as Tab, label: "Reports", icon: <FileText size={18} /> },
  ];
  const header = (
    <input type="date" className="input hidden w-auto py-2 sm:block" value={day} max={today()} onChange={(e) => e.target.value && setDay(e.target.value)} title="Site date" />
  );
  const quick: [string, any, () => void][] = [
    ["Activity / work done", HardHat, () => setActOpen(true)], ["Site photos", Camera, () => setTab("photos")],
    ["Material received / used", Package, () => setTab("material")], ["Attendance", Users, () => setTab("manpower")],
    ["Quality check", CheckSquare, () => setTab("quality")], ["Issue / delay / safety", AlertTriangle, () => setTab("safety")],
    ["Daily report (DPR)", ClipboardList, () => setTab("daily")],
  ];
  return (
    <Page title={t("Site Management")} subtitle="Track progress, manage site activities, quality and materials" actions={header}>
      <div className="flex flex-wrap items-start gap-3">
        <div className="min-w-0 flex-1"><PillTabs tabs={tabs} value={tab} onChange={setTab} /></div>
        <div className="relative">
          <button className="btn-primary py-2.5" onClick={() => setMenu(!menu)}><Plus size={18} />Add Site Update</button>
          {menu && (
            <div className="absolute right-0 z-30 mt-2 w-64 rounded-xl border border-line bg-white p-1 shadow-xl" onMouseLeave={() => setMenu(false)}>
              {quick.map(([l, I, fn]) => (
                <button key={l} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm hover:bg-slate-50" onClick={() => { setMenu(false); fn(); }}><I size={16} className="text-brand-600" />{l}</button>
              ))}
            </div>
          )}
        </div>
      </div>
      <div className="sm:hidden"><input type="date" className="input" value={day} max={today()} onChange={(e) => e.target.value && setDay(e.target.value)} /></div>
      {day !== today() && <div className="rounded-lg bg-amber-50 px-3 py-2 text-sm text-amber-800">Showing {new Date(day + "T00:00:00").toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" })} – entries you add now are dated to this day. <button className="link" onClick={() => setDay(today())}>Back to today</button></div>}

      {tab === "overview" && (ov ? <OverviewTab ov={ov} canWrite={allowed} reload={changed} goto={(x) => setTab(x as Tab)} onAddActivity={() => setActOpen(true)} /> : <p className="text-sm text-slate-500">Loading…</p>)}
      {tab === "daily" && pid && <DailyWorkTab pid={pid} day={day} canWrite={allowed} onChanged={changed} />}
      {tab === "photos" && pid && <PhotosTab pid={pid} day={day} canWrite={allowed} onChanged={changed} />}
      {tab === "quality" && pid && <QualityTab pid={pid} canWrite={allowed} onChanged={changed} />}
      {tab === "material" && pid && <MaterialsTab pid={pid} day={day} canWrite={allowed} onChanged={changed} />}
      {tab === "manpower" && pid && <ManpowerTab pid={pid} day={day} canWrite={allowed} onChanged={changed} />}
      {tab === "safety" && pid && <SafetyTab pid={pid} day={day} canWrite={allowed} onChanged={changed} />}
      {tab === "reports" && pid && <ReportsTab pid={pid} day={day} code={currentProject.code} />}

      {pid && <ActivityModal open={actOpen} onClose={() => setActOpen(false)} pid={pid} day={day} onSaved={changed} />}
    </Page>
  );
}
