import { useState, type FormEvent } from "react";
import { Languages } from "lucide-react";
import { api } from "../lib/api";
import { useAuth } from "../lib/auth";
import { useI18n } from "../lib/i18n";
import { Field } from "../components/ui";

export default function Login() {
  const { login } = useAuth();
  const { t, lang, setLang } = useI18n();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [msg, setMsg] = useState("");
  const [f, setF] = useState({ login: "", password: "", username: "", email: "", full_name: "", job_title: "", phone: "" });
  const set = (k: keyof typeof f) => (e: any) => setF({ ...f, [k]: e.target.value });

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr(""); setMsg(""); setBusy(true);
    try {
      if (mode === "login") await login(f.login, f.password);
      else {
        const r = await api<{ message: string }>("/api/auth/register", {
          body: { username: f.username, email: f.email.trim() || null, full_name: f.full_name, job_title: f.job_title, phone: f.phone, password: f.password },
        });
        setMsg(r.message); setMode("login"); setF({ ...f, login: f.username, password: "" });
      }
    } catch (e: any) { setErr(e.message); }
    finally { setBusy(false); }
  };

  return (
    <div className="grid min-h-full lg:grid-cols-2">
      <div className="relative hidden overflow-hidden bg-navy-900 lg:block">
        <img src="/images/sidebar_main.jpg" alt="" className="absolute inset-0 h-full w-full object-cover" />
        <div className="absolute inset-0 bg-linear-to-b from-navy-950/90 via-navy-900/40 to-transparent" />
        <div className="relative p-12 text-white">
          <div className="flex items-center gap-4">
            <svg viewBox="0 0 48 48" className="h-14 w-14" fill="none" stroke="white" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 23 24 6l19 17" /><path d="M10 19v22h28V19" /><path d="M20 41V29h8v12" />
            </svg>
            <div>
              <div className="text-4xl font-extrabold tracking-tight">Nexora Build</div>
              <div className="text-blue-100/85">{t("Design · Estimate · Build · Manage")}</div>
            </div>
          </div>
          <p className="mt-8 max-w-md text-lg text-blue-50/90">
            Drawing → Quantity → Estimate → Site. One civil engineering workspace, in Tamil and English.
          </p>
        </div>
      </div>

      <div className="flex items-center justify-center p-6">
        <div className="w-full max-w-md">
          <div className="mb-6 flex items-center justify-between">
            <div className="text-2xl font-extrabold text-navy-ink lg:hidden">Nexora Build</div>
            <button onClick={() => setLang(lang === "en" ? "ta" : "en")} className="btn-ghost btn-sm ml-auto">
              <Languages size={16} /> {lang === "en" ? "தமிழ்" : "English"}
            </button>
          </div>
          <div className="card p-6 sm:p-8">
            <h1 className="text-2xl font-extrabold text-navy-ink">{mode === "login" ? t("Sign in") : t("Create account")}</h1>
            <form onSubmit={submit} className="mt-6 space-y-4">
              {mode === "login" ? (
                <Field label={t("Username or email")}>
                  <input className="input" autoFocus autoComplete="username" value={f.login} onChange={set("login")} required />
                </Field>
              ) : (
                <>
                  <Field label={t("Full name")}><input className="input" value={f.full_name} onChange={set("full_name")} required /></Field>
                  <div className="grid grid-cols-2 gap-3">
                    <Field label={t("Username")}><input className="input" value={f.username} onChange={set("username")} required placeholder="a-z 0-9 _" /></Field>
                    <Field label={t("Job title")}><input className="input" value={f.job_title} onChange={set("job_title")} placeholder="Site Engineer" /></Field>
                  </div>
                  <Field label={`${t("Email")} (optional)`}><input className="input" type="email" value={f.email} onChange={set("email")} /></Field>
                  <Field label={t("Phone")}><input className="input" value={f.phone} onChange={set("phone")} /></Field>
                </>
              )}
              <Field label={t("Password")}>
                <input className="input" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"}
                  value={f.password} onChange={set("password")} required minLength={mode === "register" ? 8 : 1} />
              </Field>
              {err && <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{err}</p>}
              {msg && <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-700">{msg}</p>}
              <button className="btn-primary w-full py-2.5" disabled={busy}>
                {busy ? t("Loading...") : mode === "login" ? t("Sign in") : t("Create account")}
              </button>
            </form>
            <p className="mt-5 text-center text-sm text-slate-500">
              {mode === "login" ? t("New user?") : t("Already have an account?")}{" "}
              <button className="link" onClick={() => { setMode(mode === "login" ? "register" : "login"); setErr(""); }}>
                {mode === "login" ? t("Create account") : t("Sign in")}
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
