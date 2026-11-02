import { useEffect, useState } from "react";
import { api } from "./api";
import { useAuth } from "./auth";

/** 1.8: modules the owner keeps for himself (Settings → Project Access → Owner-only modules).
 *  Returns a check: hidden("design") is true for a non-owner when Design is owner-only. */
export function useOwnerOnly() {
  const { user } = useAuth();
  const [mods, setMods] = useState<string[]>([]);
  useEffect(() => {
    if (user && user.role !== "owner") api<{ modules: string[] }>("/api/owner-only").then((r) => setMods(r.modules)).catch(() => {});
  }, [user?.id, user?.role]);
  const isOwner = user?.role === "owner";
  return { isOwner, hidden: (m?: string) => !isOwner && !!m && mods.includes(m) };
}
