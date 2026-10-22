import { Suspense, useEffect, useRef, useState, type ReactNode } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import OfflineBar from "./OfflineBar";
import VersionBar from "./VersionBar";
import NotifBell from "./NotifBell";
import {
  Calculator, ChevronDown, Compass, FolderKanban, HardHat, Home, LogOut, Menu, PenSquare,
  Search, Settings as SettingsIcon, Languages, Trash2, X,
} from "lucide-react";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";
import { Avatar } from "./ui";

const NAV = [
  { to: "/", label: "Home", icon: Home, end: true },
  { to: "/design", label: "Design", icon: PenSquare },
  { to: "/site", label: "Site", icon: HardHat },
  { to: "/vastu", label: "Vastu", icon: Compass },
  { to: "/estimate", label: "Estimate", icon: Calculator },
  { to: "/projects", label: "Projects", icon: FolderKanban },
  { to: "/ai", label: "AI Assistant", icon: Search },
];

// A different picture for each page (bottom of the sidebar).
const SIDEBAR_IMG: [string, string][] = [
  ["/site", "sidebar_site.jpg"], ["/vastu", "sidebar_vastu.jpg"], ["/design", "proj_villa.jpg"],
  ["/estimate", "estimate_house.jpg"], ["/projects", "proj_commercial.jpg"], ["/ai", "proj_residential.jpg"],
  ["/settings", "company_building.jpg"],
];
function sidebarImage(path: string) {
  return "/images/" + (SIDEBAR_IMG.find(([p]) => path.startsWith(p))?.[1] || "sidebar_main.jpg");
}

function Logo() {
  const { t } = useI18n();
  return (
    <div className="flex items-center gap-2.5 px-4 pb-6 pt-6">
      <svg viewBox="0 0 48 48" className="h-10 w-10 shrink-0" fill="none" stroke="white" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round">
        <path d="M5 23 24 6l19 17" /><path d="M10 19v22h28V19" /><path d="M20 41V29h8v12" />
      </svg>
      <div className="leading-tight">
        <div className="text-[22px] font-bold tracking-tight text-white">Nexora Build</div>
        <div className="whitespace-nowrap text-[10px] font-medium tracking-tight text-blue-100/80">{t("Design · Estimate · Build · Manage")}</div>
      </div>
    </div>
  );
}

function Sidebar({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { t } = useI18n();
  const { user } = useAuth();
  const loc = useLocation();
  const inBin = loc.pathname.startsWith("/settings") && new URLSearchParams(window.location.search).get("tab") === "bin";
  const item = (to: string, label: string, Icon: any, end?: boolean) => (
    <NavLink key={to} to={to} end={end} onClick={onClose}
      className={({ isActive }) =>
        `mx-3 flex items-center gap-3.5 rounded-xl px-4 py-3 text-[15px] font-medium transition ${
          isActive ? "bg-brand-600 text-white shadow-lg shadow-brand-600/30" : "text-blue-50/90 hover:bg-white/10"}`}>
      <Icon size={22} strokeWidth={1.8} />{t(label)}
    </NavLink>
  );
  return (
    <>
      {open && <div className="fixed inset-0 z-30 bg-black/40 lg:hidden" onClick={onClose} />}
      <aside className={`fixed inset-y-0 left-0 z-40 flex w-[232px] flex-col overflow-hidden bg-navy-900 transition-transform lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
        <div className="pointer-events-none absolute inset-0 bg-linear-to-b from-navy-950 to-navy-900" />
        {/* links first – they never sit on top of the photo */}
        <div className="no-scrollbar relative flex min-h-0 shrink flex-col overflow-y-auto pb-3">
          <div className="flex items-start justify-between">
            <Logo />
            <button className="mr-3 mt-6 text-white lg:hidden" onClick={onClose} aria-label="Close menu"><X /></button>
          </div>
          <nav className="flex flex-col gap-1.5">{NAV.map((n) => item(n.to, n.label, n.icon, n.end))}</nav>
          <div className="mx-6 my-4 border-t border-white/15" />
          <nav className="flex flex-col gap-1.5">
            <NavLink to="/settings" onClick={onClose} className={`mx-3 flex items-center gap-3.5 rounded-xl px-4 py-3 text-[15px] font-medium transition ${
              loc.pathname.startsWith("/settings") && !inBin ? "bg-brand-600 text-white shadow-lg shadow-brand-600/30" : "text-blue-50/90 hover:bg-white/10"}`}>
              <SettingsIcon size={22} strokeWidth={1.8} />{t("Settings")}</NavLink>
            {user?.role === "owner" && (
              <NavLink to="/settings?tab=bin" onClick={onClose} className={`mx-3 flex items-center gap-3.5 rounded-xl px-4 py-3 text-[15px] font-medium transition ${
                inBin ? "bg-brand-600 text-white shadow-lg shadow-brand-600/30" : "text-blue-50/90 hover:bg-white/10"}`}>
                <Trash2 size={22} strokeWidth={1.8} />{t("Recycle Bin")}</NavLink>
            )}
          </nav>
        </div>
        {/* page photo in the space left below the links: always full width, never zoomed in; if the space is short, the middle band shows */}
        <div className="relative min-h-[90px] flex-1 overflow-hidden">
          <img src={sidebarImage(loc.pathname)} alt="" className="pointer-events-none absolute inset-0 h-full w-full scale-110 object-cover opacity-30 blur-md" />
          <img src={sidebarImage(loc.pathname)} alt="" className="pointer-events-none absolute inset-x-0 bottom-0 h-auto max-h-full w-full object-cover object-center" />
          <div className="pointer-events-none absolute inset-x-0 top-0 h-10 bg-linear-to-b from-navy-900 to-transparent" />
        </div>
      </aside>
    </>
  );
}

function ProjectSwitcher() {
  const { projects, currentProject, setCurrentProjectId } = useAuth();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const h = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  if (!currentProject) return null;
  return (
    <div ref={ref} className="relative hidden md:block">
      <button onClick={() => setOpen(!open)} className="flex w-72 items-center gap-3 rounded-xl border border-line bg-white px-3 py-2 text-left shadow-card hover:border-brand-100">
        <img src={currentProject.cover_image} alt="" className="h-10 w-12 rounded-md object-cover" />
        <div className="min-w-0 flex-1">
          <div className="truncate text-sm font-semibold text-navy-ink">{currentProject.name}</div>
          <div className="truncate text-xs text-slate-500">{[currentProject.location, currentProject.state === "Tamil Nadu" ? "TN" : currentProject.state].filter(Boolean).join(", ")}</div>
        </div>
        <ChevronDown size={18} className="text-slate-500" />
      </button>
      {open && (
        <div className="absolute right-0 z-30 mt-2 max-h-80 w-80 overflow-y-auto rounded-xl border border-line bg-white p-1 shadow-xl">
          {projects.map((p) => (
            <button key={p.id} onClick={() => { setCurrentProjectId(p.id); setOpen(false); }}
              className={`flex w-full items-center gap-3 rounded-lg px-2 py-2 text-left hover:bg-slate-50 ${p.id === currentProject.id ? "bg-brand-50" : ""}`}>
              <img src={p.cover_image} alt="" className="h-9 w-11 rounded object-cover" />
              <div className="min-w-0">
                <div className="truncate text-sm font-semibold text-navy-ink">{p.name}</div>
                <div className="text-xs text-slate-500">{p.code} · {p.location || "—"}</div>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function UserMenu() {
  const { user, logout } = useAuth();
  const { lang, setLang, t } = useI18n();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const h = (e: MouseEvent) => ref.current && !ref.current.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", h);
    return () => document.removeEventListener("mousedown", h);
  }, []);
  if (!user) return null;
  return (
    <div ref={ref} className="relative">
      <button onClick={() => setOpen(!open)} className="flex items-center gap-3 rounded-xl px-2 py-1 hover:bg-slate-50">
        <Avatar name={user.full_name || user.username} size={44} />
        <div className="hidden text-left sm:block">
          <div className="text-[15px] font-bold text-navy-ink">{user.full_name || user.username}</div>
          <div className="text-xs text-slate-500">{user.job_title || (user.role === "owner" ? "Owner" : "User")}</div>
        </div>
        <ChevronDown size={18} className="text-slate-500" />
      </button>
      {open && (
        <div className="absolute right-0 z-30 mt-2 w-56 rounded-xl border border-line bg-white p-1 shadow-xl">
          <div className="px-3 py-2 text-xs text-slate-500">@{user.username} · {user.role === "owner" ? "Owner" : "User"}</div>
          <button onClick={() => setLang(lang === "en" ? "ta" : "en")} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-slate-50">
            <Languages size={16} /> {lang === "en" ? "தமிழ்" : "English"}
          </button>
          {user?.role === "owner" && (
            <NavLink to="/settings?tab=bin" onClick={() => setOpen(false)} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-slate-50">
              <Trash2 size={16} /> Recycle Bin
            </NavLink>
          )}
          <button onClick={logout} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-red-600 hover:bg-red-50">
            <LogOut size={16} /> {t("Logout")}
          </button>
        </div>
      )}
    </div>
  );
}

export function PageHeader({ title, subtitle, onMenu, actions }: { title: string; subtitle: string; onMenu: () => void; actions?: ReactNode }) {
  const { lang, setLang } = useI18n();
  return (
    <header className="flex flex-wrap items-center gap-4 border-b border-line bg-white px-4 py-3 lg:px-6">
      <button onClick={onMenu} className="text-navy-ink" aria-label="Menu"><Menu size={26} /></button>
      <div className="min-w-0 flex-1">
        <h1 className="truncate text-xl font-extrabold text-navy-ink sm:text-[26px]">{title}</h1>
        <p className="truncate text-sm text-slate-500">{subtitle}</p>
      </div>
      <ProjectSwitcher />
      {actions}
      <button onClick={() => setLang(lang === "en" ? "ta" : "en")} title="English / தமிழ்"
        className="rounded-lg border border-line px-2.5 py-1.5 text-xs font-bold text-navy-ink hover:bg-slate-50">
        {lang === "en" ? "த" : "EN"}
      </button>
      <NotifBell />
      <UserMenu />
    </header>
  );
}

/** App shell. Pages render their own <PageHeader> through the outlet context. */
export default function Layout() {
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-full">
      <Sidebar open={open} onClose={() => setOpen(false)} />
      <div className="lg:pl-[232px]">
        <VersionBar />
        <OfflineBar />
        <Suspense fallback={<div className="flex h-64 items-center justify-center text-sm text-slate-500">Loading…</div>}>
          <Outlet context={{ openMenu: () => setOpen(true) }} />
        </Suspense>
      </div>
    </div>
  );
}
