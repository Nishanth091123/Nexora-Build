import { createContext, useContext, useEffect, useState, type ReactNode } from "react";

export type Lang = "en" | "ta";

// English text is the key. Missing Tamil entries fall back to English automatically.
const TA: Record<string, string> = {
  // navigation
  "Home": "முகப்பு", "Design": "வடிவமைப்பு", "Site": "தளம்", "Vastu": "வாஸ்து", "Estimate": "மதிப்பீடு",
  "Projects": "திட்டங்கள்", "AI Assistant": "AI உதவியாளர்", "Settings": "அமைப்புகள்",
  "Design · Estimate · Build · Manage": "வடிவமை · மதிப்பிடு · கட்டு · நிர்வகி",
  // help card
  "Need Help?": "உதவி வேண்டுமா?", "Open AI Assistant": "AI உதவியாளரை திற",
  "Ask AI about your projects, team, documents or progress.": "உங்கள் திட்டம், குழு, ஆவணங்கள் பற்றி AI-யிடம் கேளுங்கள்.",
  // auth
  "Sign in": "உள்நுழை", "Username or email": "பயனர் பெயர் அல்லது மின்னஞ்சல்", "Password": "கடவுச்சொல்",
  "Create account": "கணக்கு உருவாக்கு", "Logout": "வெளியேறு", "Full name": "முழு பெயர்",
  "Username": "பயனர் பெயர்", "Email": "மின்னஞ்சல்", "Job title": "பணி", "Phone": "தொலைபேசி",
  "Already have an account?": "ஏற்கனவே கணக்கு உள்ளதா?", "New user?": "புதிய பயனரா?",
  // common
  "Save": "சேமி", "Cancel": "ரத்து", "Edit": "திருத்து", "View All": "அனைத்தும்", "Search": "தேடு",
  "Loading...": "ஏற்றுகிறது...", "Coming in": "வரவிருக்கிறது", "Upload File": "கோப்பு பதிவேற்று",
  "Download": "பதிவிறக்கு", "Status": "நிலை", "Actions": "செயல்கள்", "Name": "பெயர்", "Role": "பங்கு",
  "Start": "தொடக்கம்", "End": "முடிவு", "Client": "வாடிக்கையாளர்", "Type": "வகை", "Floors": "தளங்கள்",
  "Built-up Area": "கட்டுமான பரப்பு", "Start Date": "தொடக்க தேதி", "End Date": "முடிவு தேதி",
  "Location": "இடம்", "Progress": "முன்னேற்றம்", "No data yet": "இன்னும் தரவு இல்லை",
  // projects page
  "Manage multiple projects, teams, documents and track progress": "பல திட்டங்கள், குழுக்கள், ஆவணங்களை நிர்வகித்து முன்னேற்றத்தை கண்காணிக்கவும்",
  "Project Dashboard": "திட்ட டாஷ்போர்டு", "My Projects": "என் திட்டங்கள்", "Team & Permissions": "குழு & அனுமதிகள்",
  "Documents": "ஆவணங்கள்", "Tasks": "பணிகள்", "Milestones": "மைல்கற்கள்", "Approvals": "ஒப்புதல்கள்",
  "Activity Logs": "செயல்பாட்டு பதிவுகள்", "New Project": "புதிய திட்டம்", "Create Project": "திட்டம் உருவாக்கு",
  "Total Projects": "மொத்த திட்டங்கள்", "On Track": "சரியான பாதையில்", "Delayed": "தாமதம்",
  "Completed": "முடிந்தது", "Total Team Members": "மொத்த குழு உறுப்பினர்கள்", "Ongoing": "நடப்பில்",
  "On Hold": "நிறுத்தம்", "All": "அனைத்தும்", "Project Details": "திட்ட விவரங்கள்",
  "Team Members": "குழு உறுப்பினர்கள்", "Recent Activity": "சமீபத்திய செயல்பாடு",
  "Project Drawings & Documents": "திட்ட வரைபடங்கள் & ஆவணங்கள்", "Task Management": "பணி மேலாண்மை",
  "Project Timeline (Gantt Chart)": "திட்ட காலவரிசை (Gantt)", "Search projects...": "திட்டங்களை தேடு...",
  "Drawings": "வரைபடங்கள்", "Reports": "அறிக்கைகள்", "Photos": "புகைப்படங்கள்", "Contracts": "ஒப்பந்தங்கள்", "Others": "மற்றவை",
  "Active Projects": "செயலில் உள்ள திட்டங்கள்", "Users": "பயனர்கள்", "Project": "திட்டம்",
  // settings
  "Settings & Administration": "அமைப்புகள் & நிர்வாகம்",
  "Manage your company, users, permissions, preferences and security": "உங்கள் நிறுவனம், பயனர்கள், அனுமதிகள், விருப்பங்கள், பாதுகாப்பை நிர்வகிக்கவும்",
  "General": "பொது", "Company": "நிறுவனம்", "Users & Teams": "பயனர்கள் & குழுக்கள்", "Project Access": "திட்ட அணுகல்",
  "Units & Rates": "அலகுகள் & விலைகள்", "AI Preferences": "AI விருப்பங்கள்", "Notifications": "அறிவிப்புகள்",
  "Security": "பாதுகாப்பு", "Backups": "காப்புப்பிரதிகள்", "Audit Logs": "தணிக்கை பதிவுகள்",
  "Company Information": "நிறுவன தகவல்", "Users & Team Management": "பயனர் & குழு மேலாண்மை",
  "Project Access Control": "திட்ட அணுகல் கட்டுப்பாடு", "Add User": "பயனர் சேர்",
  "Backup Now": "இப்போது காப்புப்பிரதி", "Approve": "ஒப்புதல்", "Deactivate": "முடக்கு", "Activate": "செயல்படுத்து",
  "Pending": "நிலுவையில்", "Active": "செயலில்", "Deactivated": "முடக்கப்பட்டது",
  "Change Password": "கடவுச்சொல் மாற்று", "Language": "மொழி",
  // other pages
  "Site Management": "தள மேலாண்மை", "Estimate & BOQ": "மதிப்பீடு & BOQ", "Vastu Intelligence": "வாஸ்து நுண்ணறிவு",
  "Design Studio": "வடிவமைப்பு ஸ்டுடியோ",
};

const I18nCtx = createContext<{ lang: Lang; setLang: (l: Lang) => void; t: (s: string) => string }>({
  lang: "en", setLang: () => {}, t: (s) => s,
});

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    try { return (localStorage.getItem("nexora_lang") as Lang) || "en"; } catch { return "en"; }
  });
  useEffect(() => {
    document.documentElement.lang = lang;
    try { localStorage.setItem("nexora_lang", lang); } catch { /* ignore */ }
  }, [lang]);
  const t = (s: string) => (lang === "ta" ? TA[s] ?? s : s);
  return <I18nCtx.Provider value={{ lang, setLang: setLangState, t }}>{children}</I18nCtx.Provider>;
}

export const useI18n = () => useContext(I18nCtx);
