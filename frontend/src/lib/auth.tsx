import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, getToken, setToken, setUnauthorizedHandler } from "./api";
import { useI18n, type Lang } from "./i18n";

export type User = {
  id: number; username: string; email: string | null; full_name: string; job_title: string; phone: string;
  role: "owner" | "user"; status: string; is_protected: boolean; can_create_projects: boolean; language: Lang;
  created_at?: string; last_login_at?: string | null;
};

export type Project = {
  id: number; code: string; name: string; project_type: string; client_name: string; location: string;
  district: string; state: string; plot_width: number | null; plot_length: number | null; unit: string;
  facing: string; road_width: number | null; floors: string; builtup_area: number | null;
  structure_type: string; spec_level: string; start_date: string | null; end_date: string | null;
  status: string; health: string; progress: number; cover_image: string; notes: string;
  created_at: string; updated_at: string; permissions?: Record<string, boolean>;
};

type Ctx = {
  user: User | null; loading: boolean;
  login: (login: string, password: string) => Promise<void>;
  logout: () => void; refreshUser: () => Promise<void>;
  projects: Project[]; reloadProjects: () => Promise<void>;
  currentProject: Project | null; setCurrentProjectId: (id: number | null) => void;
};

const AuthCtx = createContext<Ctx>(null as unknown as Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const { lang, setLang } = useI18n();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [projects, setProjects] = useState<Project[]>([]);
  const [currentId, setCurrentId] = useState<number | null>(() => {
    try { const v = localStorage.getItem("nexora_project"); return v ? Number(v) : null; } catch { return null; }
  });

  const logout = useCallback(() => { setToken(null); setUser(null); setProjects([]); }, []);
  useEffect(() => setUnauthorizedHandler(logout), [logout]);

  const reloadProjects = useCallback(async () => {
    const r = await api<{ projects: Project[] }>("/api/projects?sort=updated");
    setProjects(r.projects);
  }, []);

  const refreshUser = useCallback(async () => {
    const u = await api<User>("/api/auth/me");
    setUser(u);
  }, []);

  useEffect(() => {
    if (!getToken()) { setLoading(false); return; }
    (async () => {
      try { await refreshUser(); await reloadProjects(); } catch { setToken(null); }
      finally { setLoading(false); }
    })();
  }, [refreshUser, reloadProjects]);

  const login = async (login: string, password: string) => {
    const r = await api<{ token: string; user: User }>("/api/auth/login", { body: { login, password } });
    setToken(r.token);
    setUser(r.user);
    if (r.user.language) setLang(r.user.language);
    await reloadProjects();
  };

  const setCurrentProjectId = (id: number | null) => {
    setCurrentId(id);
    try { id ? localStorage.setItem("nexora_project", String(id)) : localStorage.removeItem("nexora_project"); } catch { /* ignore */ }
  };

  // remember the chosen language on the server, so it follows the user to other devices
  useEffect(() => {
    if (user && user.language !== lang) {
      api("/api/auth/me", { method: "PATCH", body: { language: lang } })
        .then(() => setUser((u) => (u ? { ...u, language: lang } : u))).catch(() => {});
    }
  }, [lang, user]);

  const currentProject = projects.find((p) => p.id === currentId) || projects[0] || null;

  return (
    <AuthCtx.Provider value={{ user, loading, login, logout, refreshUser, projects, reloadProjects, currentProject, setCurrentProjectId }}>
      {children}
    </AuthCtx.Provider>
  );
}

export const useAuth = () => useContext(AuthCtx);
