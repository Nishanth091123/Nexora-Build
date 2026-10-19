import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import {
  BookOpen, Calculator, ChevronRight, CircleDollarSign, Clock, Compass, FileImage, FilePen, FileText, HardHat, Home, Layers,
  Library, MessageCircle, MessageSquare, MessageSquarePlus, PenSquare, Pin, PinOff, ScrollText, Sparkles, EyeOff, Wand2,
} from "lucide-react";
import Page from "../components/Page";
import Chat, { type ChatHandle } from "../components/ai/Chat";
import { CodeTab, DesignTab, DocsTab, DrawingTab, MaterialTab, QtyTab, SiteTab } from "../components/ai/Tools";
import type { Conv, Meta, SendOpts } from "../components/ai/types";
import { Card, Modal, PillTabs, toast } from "../components/ui";
import { api, timeAgo } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";

type Tab = "chat" | "drawing" | "docs" | "qty" | "design" | "site" | "material" | "code";

const AGENT_STYLE: Record<string, [any, string]> = {
  general: [MessageCircle, "bg-brand-600"], drawing: [PenSquare, "bg-violet-600"], quantity: [Calculator, "bg-emerald-600"],
  design: [Home, "bg-orange-500"], site: [HardHat, "bg-amber-500"], material: [Layers, "bg-cyan-600"],
  vastu: [Compass, "bg-rose-600"], code: [BookOpen, "bg-slate-700"],
};
const SUGGESTED = [
  "Generate a 3BHK plan for 30x50 site", "Calculate quantities from uploaded drawing", "Suggest cost-effective material alternatives",
  "Analyze this plan for Vastu compliance", "What is the minimum column size for G+2?", "Create a BOQ with latest market rates",
  "Suggest waterproofing method for terrace",
];
const WELCOME: Record<string, string[]> = {
  general: ["30x40 east facing 2BHK, car parking, G+1, 30 ft road – plan with quantities", "OPC vs PPC – which cement for a coastal house?", "1200 sq ft G+1 house cost?", "சுவர்ல plaster crack வருது, என்ன பண்ணலாம்?"],
  drawing: ["Analyse my uploaded drawing", "What should I check in a floor plan before approval?"],
  quantity: ["How many cement bags for 1 m³ of M20 concrete?", "Bricks for a 20 x 10 ft 9 inch wall", "Steel weight of 12 mm bar, 12 m, 10 nos", "5 cents to sq ft"],
  design: ["30x40 east facing 2BHK, car parking, G+1, 30 ft road", "Setback for 30x40 plot, 30 ft road, G+1", "Good room sizes for a 3BHK?"],
  site: ["Plaster cracks – what to do?", "Terrace leakage solution", "Cube test failed – what next?", "How is my site doing today?"],
  material: ["OPC vs PPC vs PSC", "AAC block vs red brick for G+1", "M-Sand or river sand for plastering?", "Which tiles for bathroom floor?"],
  vastu: ["Check Vastu of my latest design", "Where should the kitchen and pooja room be?"],
  code: ["Minimum cover for slab, beam and column", "Curing days for PPC concrete", "Formwork removal time for slab", "Minimum room sizes as per NBC"],
};

export default function AIPage() {
  const { t } = useI18n();
  const { user, currentProject, projects, setCurrentProjectId } = useAuth();
  const [params, setParams] = useSearchParams();
  const [tab, setTab] = useState<Tab>(() => (params.get("tab") as Tab) || "chat");
  const [meta, setMeta] = useState<Meta | null>(null);
  const [agent, setAgent] = useState("general");
  const [convs, setConvs] = useState<Conv[]>([]);
  const [allOpen, setAllOpen] = useState(false);
  const [answerLang, setAnswerLangState] = useState<string>(() => { try { return localStorage.getItem("nexora_ai_lang") || ""; } catch { return ""; } });
  const chat = useRef<ChatHandle>(null);
  const pid = currentProject?.id ?? null;
  const perms = currentProject?.permissions || {};
  const aiAllowed = !currentProject || !!perms.ai;
  const convId = Number(params.get("c")) || null;

  const setAnswerLang = (l: string) => { setAnswerLangState(l); try { localStorage.setItem("nexora_ai_lang", l); } catch { /* ignore */ } };
  const setConvId = useCallback((id: number | null) => {
    setParams((p) => { const n = new URLSearchParams(p); if (id) n.set("c", String(id)); else n.delete("c"); return n; }, { replace: true });
  }, [setParams]);

  const loadConvs = useCallback(() => {
    api<Conv[]>(`/api/ai/conversations${pid ? `?project_id=${pid}` : ""}`).then(setConvs).catch(() => {});
  }, [pid]);
  useEffect(() => { loadConvs(); }, [loadConvs]);
  useEffect(() => {
    api<Meta>(`/api/ai/meta${pid && aiAllowed ? `?project_id=${pid}` : ""}`).then(setMeta).catch((e) => toast(e.message, "err"));
  }, [pid, aiAllowed]);
  // conversation of another project → start fresh
  const prevPid = useRef(pid);
  useEffect(() => { if (prevPid.current !== pid) { prevPid.current = pid; setConvId(null); } }, [pid, setConvId]);
  useEffect(() => {
    const c = convs.find((x) => x.id === convId);
    if (c) setAgent(c.agent);
  }, [convId, convs]);

  const go = (o: SendOpts) => {
    setTab("chat");
    if (o.agent) setAgent(o.agent);
    setTimeout(() => chat.current?.send({ ...o, agent: o.agent || agent }), 0);
  };
  const pickAgent = (k: string) => {
    setAgent(k);
    if (convId) api(`/api/ai/conversations/${convId}`, { method: "PATCH", body: { agent: k } }).catch(() => {});
  };
  const ag = meta?.agents.find((a) => a.key === agent);

  if (currentProject && !aiAllowed) {
    return <Page title={t("AI Assistant")} subtitle="Your Civil Engineering Copilot – Ask, Analyze, Design, Estimate, Plan">
      <Card><p className="text-sm text-slate-600">You don't have AI Assistant access for this project. Ask the owner, or choose another project.</p></Card>
    </Page>;
  }

  const tabs = [
    { id: "chat" as Tab, label: "Chat Assistant", icon: <MessageSquare size={18} /> }, { id: "drawing" as Tab, label: "Drawing Analysis", icon: <FileImage size={18} /> },
    { id: "docs" as Tab, label: "Document Q&A", icon: <FileText size={18} /> }, { id: "qty" as Tab, label: "Quantity Calculator", icon: <Calculator size={18} /> },
    { id: "design" as Tab, label: "Design Suggestions", icon: <Wand2 size={18} /> }, { id: "site" as Tab, label: "Site Troubleshooting", icon: <HardHat size={18} /> },
    { id: "material" as Tab, label: "Material Guide", icon: <Library size={18} /> }, { id: "code" as Tab, label: "Code & Standards", icon: <BookOpen size={18} /> },
  ];
  const quick: [string, string, any, string, () => void][] = [
    ["Generate Floor Plan", "(Text to Plan)", FilePen, "text-brand-600 bg-brand-50", () => setTab("design")],
    ["Analyze Drawing", "(PDF/Image)", FileImage, "text-red-600 bg-red-50", () => setTab("drawing")],
    ["Calculate Quantities", "(From Drawing)", Calculator, "text-emerald-600 bg-emerald-50", () => setTab("qty")],
    ["Estimate Cost", "(Material + Labour)", CircleDollarSign, "text-orange-500 bg-orange-50", () => go({ text: "Estimate the cost of my project with material quantities", agent: "quantity" })],
    ["Check Vastu", "(Plan Analysis)", Compass, "text-violet-600 bg-violet-50", () => go({ form: { tool: "vastu", label: "Check Vastu of my latest plan" }, agent: "vastu" })],
    ["Site Issue Solution", "(Troubleshooting)", HardHat, "text-amber-500 bg-amber-50", () => setTab("site")],
    ["Material Comparison", "(Grades & Rates)", Layers, "text-cyan-600 bg-cyan-50", () => setTab("material")],
    ["IS Code Reference", "(Building Standards)", ScrollText, "text-slate-700 bg-slate-100", () => setTab("code")],
  ];

  const agentsList = (
    <div className="space-y-2">
      {(meta?.agents || []).map((a) => {
        const [I, bg] = AGENT_STYLE[a.key] || [Sparkles, "bg-brand-600"];
        const on = a.key === agent;
        return (
          <button key={a.key} onClick={() => pickAgent(a.key)}
            className={`flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition ${on ? "border-brand-600 bg-brand-50 ring-1 ring-brand-600" : "border-line bg-white hover:border-brand-100"}`}>
            <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg text-white ${bg}`}><I size={19} /></span>
            <span className="min-w-0"><span className="block truncate text-sm font-bold text-navy-ink">{a.name}</span><span className="block truncate text-xs text-slate-500">{a.desc}</span></span>
          </button>
        );
      })}
    </div>
  );

  const projectCard = (
    <Card title="Project Context" icon={<FileText size={18} className="text-navy-ink" />}>
      {currentProject ? (
        <div>
          <div className="flex gap-3">
            {currentProject.cover_image && <img src={currentProject.cover_image} alt="" className="h-16 w-20 shrink-0 rounded-lg object-cover" />}
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-bold text-navy-ink">{currentProject.name}</div>
              <select className="mt-1 w-full rounded-md border border-line bg-brand-50 px-2 py-1 text-xs font-semibold text-brand-700" value={pid ?? ""} onChange={(e) => setCurrentProjectId(Number(e.target.value) || null)}>
                {projects.map((p) => <option key={p.id} value={p.id}>{p.code} · {p.name}</option>)}
              </select>
            </div>
          </div>
          <dl className="mt-3 grid grid-cols-[110px_1fr] gap-y-1.5 text-[13px]">
            {[["Location", [currentProject.location, currentProject.state === "Tamil Nadu" ? "TN" : currentProject.state].filter(Boolean).join(", ")],
              ["Built-up Area", currentProject.builtup_area ? `${currentProject.builtup_area} sq ft` : "—"], ["Floors", currentProject.floors],
              ["Type", currentProject.project_type.replace(/_/g, " ")], ["Plot", currentProject.plot_width ? `${currentProject.plot_width} × ${currentProject.plot_length} ${currentProject.unit}` : "—"],
              ["Facing", currentProject.facing || "—"], ["Progress", `${Math.round(currentProject.progress)}% · ${currentProject.status}`],
              ["Units", currentProject.unit === "m" ? "Metric (m, m²)" : "Feet (ft, sq ft)"]].map(([k, v]) => (
              <div key={k} className="contents"><dt className="text-slate-500">{k}</dt><dd className="truncate font-medium capitalize text-navy-ink">{v}</dd></div>
            ))}
          </dl>
          <p className="mt-2 text-[11px] text-slate-400">The assistant uses these project details. Missing ones (facing, road width) are asked, never guessed.</p>
        </div>
      ) : <p className="text-sm text-slate-500">No project chosen – general questions only. Pick a project in the top bar to use its plans, estimates, site and documents.</p>}
    </Card>
  );

  const recent = (list: Conv[], full = false) => (
    <ul className="space-y-1">
      {list.map((c) => (
        <li key={c.id} className={`group flex items-center gap-2 rounded-lg px-2 py-2 text-[13px] ${c.id === convId ? "bg-brand-50" : "hover:bg-slate-50"}`}>
          <button className="flex min-w-0 flex-1 items-center gap-2 text-left" onClick={() => { setConvId(c.id); setTab("chat"); setAllOpen(false); }}>
            {c.is_pinned ? <Pin size={14} className="shrink-0 text-brand-600" /> : <Clock size={14} className="shrink-0 text-slate-400" />}
            <span className="min-w-0 flex-1 truncate text-navy-ink">{c.title}</span>
            <span className="shrink-0 text-[11px] text-slate-400">{timeAgo(c.updated_at)}</span>
          </button>
          {full && <>
            <button title={c.is_pinned ? "Unpin" : "Pin"} className="text-slate-400 hover:text-brand-600" onClick={() => api(`/api/ai/conversations/${c.id}`, { method: "PATCH", body: { is_pinned: !c.is_pinned } }).then(loadConvs)}>{c.is_pinned ? <PinOff size={14} /> : <Pin size={14} />}</button>
            <button title="Hide (kept in the database)" className="text-slate-400 hover:text-red-600" onClick={() => api(`/api/ai/conversations/${c.id}/hide`, { method: "POST" }).then(() => { if (c.id === convId) setConvId(null); loadConvs(); })}><EyeOff size={14} /></button>
          </>}
        </li>
      ))}
      {!list.length && <li className="px-2 py-2 text-xs text-slate-500">No conversations yet.</li>}
    </ul>
  );

  const rightCol = (
    <>
      <Card title="Quick Actions" icon={<Sparkles size={18} className="text-navy-ink" />}>
        <div className="grid grid-cols-2 gap-2">
          {quick.map(([a, b, I, cls, fn]) => (
            <button key={a} onClick={fn} className="flex items-center gap-2 rounded-xl border border-line bg-white p-2.5 text-left transition hover:border-brand-100 hover:shadow-card">
              <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${cls}`}><I size={19} /></span>
              <span className="min-w-0"><span className="block text-[12.5px] font-semibold leading-tight text-navy-ink">{a}</span><span className="block text-[11px] text-slate-500">{b}</span></span>
            </button>
          ))}
        </div>
      </Card>
      <Card title="Recent Conversations" icon={<MessageSquare size={18} className="text-navy-ink" />} action={<button className="link text-xs" onClick={() => setAllOpen(true)}>{t("View All")}</button>} bodyClass="px-3 pb-3">
        {recent(convs.slice(0, 5))}
      </Card>
      <Card title="Suggested Prompts" icon={<Sparkles size={18} className="text-navy-ink" />} bodyClass="px-3 pb-3">
        <ul className="space-y-0.5">
          {SUGGESTED.map((s) => (
            <li key={s}><button onClick={() => go({ text: s })} className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-[13px] text-navy-ink hover:bg-slate-50">
              <FilePen size={14} className="shrink-0 text-brand-600" /><span className="flex-1">{s}</span><ChevronRight size={14} className="text-slate-400" /></button></li>
          ))}
        </ul>
      </Card>
    </>
  );

  const welcome = WELCOME[agent] || WELCOME.general;

  return (
    <Page title={t("AI Assistant")} subtitle="Your Civil Engineering Copilot – Ask, Analyze, Design, Estimate, Plan"
      actions={<button className="btn-outline hidden sm:inline-flex" onClick={() => { chat.current?.newChat(); setTab("chat"); }}><MessageSquarePlus size={17} />New chat</button>}>
      <PillTabs tabs={tabs} value={tab} onChange={setTab} />
      <div className={`grid gap-4 ${tab === "chat" ? "xl:grid-cols-[290px_1fr_320px]" : "xl:grid-cols-[290px_1fr]"}`}>
        <div className="hidden min-w-0 space-y-4 xl:block">
          <Card title="Choose AI Agent" bodyClass="px-4 pb-4">{agentsList}</Card>
          {projectCard}
        </div>
        <div className="min-w-0 space-y-3">
          <div className="no-scrollbar flex gap-2 overflow-x-auto xl:hidden">
            {(meta?.agents || []).map((a) => {
              const [I, bg] = AGENT_STYLE[a.key] || [Sparkles, "bg-brand-600"];
              return <button key={a.key} onClick={() => pickAgent(a.key)} className={`inline-flex shrink-0 items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-semibold ${a.key === agent ? "border-brand-600 bg-brand-50 text-brand-700" : "border-line bg-white text-navy-ink"}`}>
                <span className={`flex h-5 w-5 items-center justify-center rounded text-white ${bg}`}><I size={12} /></span>{a.name}</button>;
            })}
            <button className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-line bg-white px-2.5 py-1.5 text-xs font-semibold text-brand-700 sm:hidden" onClick={() => chat.current?.newChat()}><MessageSquarePlus size={14} />New</button>
          </div>
          <div className={tab === "chat" ? "" : "hidden"}>
            <Chat ref={chat} pid={pid} code={currentProject?.code || ""} perms={perms} agent={agent} agentName={ag?.name || "General Assistant"} agentDesc={ag?.desc || "General queries and guidance"}
              convId={convId} setConvId={setConvId} onChanged={loadConvs} userName={user?.full_name || user?.username || "You"}
              answerLang={answerLang} setAnswerLang={setAnswerLang} welcomePrompts={welcome} />
          </div>
          {tab === "drawing" && <DrawingTab pid={pid} go={go} />}
          {tab === "docs" && <DocsTab pid={pid} go={go} />}
          {tab === "qty" && <QtyTab meta={meta} go={go} />}
          {tab === "design" && <DesignTab project={currentProject} go={go} />}
          {tab === "site" && <SiteTab go={go} pid={pid} />}
          {tab === "material" && <MaterialTab meta={meta} go={go} />}
          {tab === "code" && <CodeTab go={go} />}
        </div>
        <div className={`min-w-0 space-y-4 ${tab === "chat" ? "" : "xl:hidden"}`}>
          {rightCol}
          <div className="xl:hidden">{projectCard}</div>
        </div>
      </div>
      <Modal open={allOpen} onClose={() => setAllOpen(false)} title="All conversations">
        {recent(convs, true)}
        <p className="mt-3 text-[11px] text-slate-400">Hidden conversations are kept in the database (nothing is deleted).</p>
      </Modal>
    </Page>
  );
}
