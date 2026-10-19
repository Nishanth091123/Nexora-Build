import { useEffect, useState, type FormEvent } from "react";
import { CheckCircle2, Link2 } from "lucide-react";
import { api } from "../lib/api";
import { Field } from "../components/ui";

/** Public page for an invite link: /join/<token>. Creates a pending account that the owner approves. */
export default function Join({ token }: { token: string }) {
  const [info, setInfo] = useState<any>(null);
  const [err, setErr] = useState("");
  const [done, setDone] = useState("");
  const [busy, setBusy] = useState(false);
  const [f, setF] = useState({ full_name: "", username: "", phone: "", email: "", password: "", confirm: "" });
  useEffect(() => { api<any>(`/api/invites/open/${token}`).then(setInfo).catch((e) => setErr(e.message)); }, [token]);
  const set = (k: keyof typeof f) => (e: any) => setF({ ...f, [k]: e.target.value });
  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setErr("");
    if (f.password !== f.confirm) return setErr("Passwords do not match");
    setBusy(true);
    try {
      const r = await api<any>(`/api/invites/open/${token}/join`, { body: { full_name: f.full_name, username: f.username, phone: f.phone, email: f.email.trim() || null, password: f.password } });
      setDone(r.message);
    } catch (e: any) { setErr(e.message); } finally { setBusy(false); }
  };
  return (
    <div className="flex min-h-full items-center justify-center bg-slate-50 p-4">
      <div className="card w-full max-w-md p-6">
        <div className="mb-4 flex items-center gap-2 text-lg font-bold text-navy-ink"><Link2 className="text-brand-600" />Join Nexora Build</div>
        {done ? (
          <div className="space-y-3 text-sm">
            <p className="flex items-start gap-2 text-emerald-700"><CheckCircle2 size={18} className="mt-0.5 shrink-0" />{done}</p>
            <a className="btn-primary w-full" href="/">Go to login</a>
          </div>
        ) : !info ? (
          <p className={`text-sm ${err ? "text-red-600" : "text-slate-500"}`}>{err || "Checking the link…"}</p>
        ) : (
          <form onSubmit={submit} className="space-y-3">
            <p className="text-sm text-slate-600">{info.invited_by ? `${info.invited_by} ` : ""}invited you{info.company ? ` to ${info.company}` : ""}
              {info.job_title ? ` as ${info.job_title}` : ""}. After you sign up, the owner approves your account and then you can log in.</p>
            <Field label="Full name"><input className="input" required value={f.full_name} onChange={set("full_name")} /></Field>
            <Field label="Username (a-z, 0-9, _ .)"><input className="input" required value={f.username} onChange={(e) => setF({ ...f, username: e.target.value.toLowerCase() })} /></Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Phone"><input className="input" value={f.phone} onChange={set("phone")} /></Field>
              <Field label="Email (optional)"><input className="input" type="email" value={f.email} onChange={set("email")} /></Field>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Password"><input className="input" type="password" required value={f.password} onChange={set("password")} /></Field>
              <Field label="Confirm password"><input className="input" type="password" required value={f.confirm} onChange={set("confirm")} /></Field>
            </div>
            <p className="text-[11px] text-slate-500">Password: at least 8 characters with letters and numbers.</p>
            {err && <p className="text-sm text-red-600">{err}</p>}
            <button className="btn-primary w-full" disabled={busy}>{busy ? "Sending…" : "Send join request"}</button>
          </form>
        )}
      </div>
    </div>
  );
}
