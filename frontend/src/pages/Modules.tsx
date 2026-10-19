import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import {
  Bot, Calculator, CheckSquare, ClipboardList, Compass, FileBarChart, FileSpreadsheet, Hammer, HardHat, LayoutDashboard, Library, PenSquare, Ruler, Scale,
} from "lucide-react";
import Page from "../components/Page";
import { Card, PhaseNote, PillTabs } from "../components/ui";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";
import { TodayWeatherCard, WeekWeatherRow, useSiteWeather } from "../components/home/SiteWeather";

type Tab = { id: string; label: string; icon: ReactNode };

function ModulePage({ title, subtitle, tabs, phase, banner, bannerClass, features, children }: {
  title: string; subtitle: string; tabs: Tab[]; phase: number; banner?: string; bannerClass?: string; features: string[]; children?: ReactNode;
}) {
  const { t } = useI18n();
  const { currentProject } = useAuth();
  const [tab, setTab] = useState(tabs[0].id);
  return (
    <Page title={t(title)} subtitle={subtitle}>
      <PillTabs tabs={tabs} value={tab} onChange={setTab} />
      <div className="grid gap-4 xl:grid-cols-[1.4fr_1fr]">
        <Card title={`${tabs.find((x) => x.id === tab)?.label}`} icon={tabs.find((x) => x.id === tab)?.icon}>
          {banner && <img src={banner} alt="" className={`mb-4 w-full rounded-lg object-cover ${bannerClass || "aspect-[16/7]"}`} />}
          <PhaseNote phase={phase} what={`${title} – this screen is built exactly like the approved design, with real calculations.`} />
          <ul className="mt-4 grid gap-2 text-sm text-slate-700 sm:grid-cols-2">
            {features.map((f) => <li key={f} className="flex gap-2"><CheckSquare size={16} className="mt-0.5 shrink-0 text-brand-600" />{f}</li>)}
          </ul>
        </Card>
        <div className="space-y-4">
          <Card title="Current Project" icon={<ClipboardList size={20} />}>
            {currentProject ? (
              <div className="flex gap-3">
                <img src={currentProject.cover_image} alt="" className="h-20 w-24 rounded-lg object-cover" />
                <div className="text-sm">
                  <div className="font-bold text-navy-ink">{currentProject.name}</div>
                  <div className="text-slate-500">{currentProject.code} · {currentProject.location || "—"}</div>
                  <div className="mt-1 text-slate-500">Plot: {currentProject.plot_width && currentProject.plot_length ? `${currentProject.plot_width} × ${currentProject.plot_length} ${currentProject.unit}` : "not given"} · {currentProject.floors} · {currentProject.spec_level}</div>
                </div>
              </div>
            ) : <p className="text-sm text-slate-500">No project yet – create one in Projects.</p>}
          </Card>
          {children}
        </div>
      </div>
    </Page>
  );
}

const ic = (C: any) => <C size={18} />;

export function EstimatePage() {
  return (
    <ModulePage title="Estimate & BOQ" subtitle="Calculate quantities, material, labour and cost" phase={2} banner="/images/estimate_house.jpg" bannerClass="aspect-[4/3] max-w-xl"
      tabs={[{ id: "overview", label: "Overview", icon: ic(LayoutDashboard) }, { id: "takeoff", label: "Quantity Takeoff", icon: ic(Ruler) },
        { id: "material", label: "Material Estimate", icon: ic(Hammer) }, { id: "cost", label: "Cost Analysis", icon: ic(Calculator) },
        { id: "boq", label: "BOQ", icon: ic(FileSpreadsheet) }, { id: "rates", label: "Rate Library", icon: ic(Library) },
        { id: "compare", label: "Comparisons", icon: ic(Scale) }, { id: "reports", label: "Reports", icon: ic(FileBarChart) }]}
      features={["Quick estimate + detailed BOQ", "Basic / Standard / Premium for every item (default Standard)", "Works, labour, materials, equipment, extras – nothing missed",
        "Material + labour + equipment split per item", "All-India rates, Tamil Nadu average default, fully editable", "RCC framed and load-bearing", "Floor-wise summary", "Excel & PDF download"]} />
  );
}


export function HomePage() {
  const { t } = useI18n();
  const nav = useNavigate();
  const { user, projects } = useAuth();
  const quick: [string, string, any, string][] = [
    ["New Project", "/projects", ClipboardList, "Create and set up a project"], ["Design", "/design", PenSquare, "AI floor plans & drawings"],
    ["Estimate", "/estimate", Calculator, "Quantities, BOQ & cost"], ["Site", "/site", HardHat, "DPR, photos, quality"],
    ["Vastu", "/vastu", Compass, "Plan guidance"], ["AI Assistant", "/ai", Bot, "Ask anything in Tamil / English"],
  ];
  const ongoing = projects.filter((p) => p.status === "ongoing").length;
  const weather = useSiteWeather();
  return (
    <Page title={`${t("Home")} – ${user?.full_name?.split(" ")[0] || ""}`} subtitle="Nexora Build – Drawing → Quantity → Estimate → Site">
      <div className="grid gap-4 lg:grid-cols-3">
        <div className="card relative min-h-[260px] overflow-hidden sm:min-h-[320px] lg:col-span-2 xl:min-h-[380px]">
          <img src="/images/proj_villa.jpg" alt="" className="absolute inset-0 h-full w-full object-cover object-[60%_30%]" />
          <div className="absolute inset-0 bg-linear-to-r from-navy-950/90 via-navy-900/60 to-transparent" />
          <div className="relative p-6 text-white sm:p-8">
            <div className="text-sm text-blue-100">Welcome back</div>
            <div className="mt-1 text-2xl font-extrabold sm:text-3xl">{user?.full_name || user?.username}</div>
            <div className="mt-4 flex gap-6 text-sm">
              <div><div className="text-3xl font-extrabold">{projects.length}</div>{t("Projects")}</div>
              <div><div className="text-3xl font-extrabold">{ongoing}</div>{t("Ongoing")}</div>
            </div>
            <button className="btn-primary mt-5" onClick={() => nav("/projects")}>{t("Projects")} →</button>
          </div>
        </div>
        <TodayWeatherCard w={weather} />
      </div>
      <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-6">
        {quick.map(([l, to, Icon, d]) => (
          <button key={l} onClick={() => nav(to)} className="card flex flex-col items-start gap-2 p-4 text-left transition hover:border-brand-100 hover:shadow-md">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-brand-50 text-brand-600"><Icon size={22} /></div>
            <div className="text-sm font-bold text-navy-ink">{t(l)}</div><div className="text-xs text-slate-500">{d}</div>
          </button>
        ))}
      </div>
      <WeekWeatherRow w={weather} />
    </Page>
  );
}
