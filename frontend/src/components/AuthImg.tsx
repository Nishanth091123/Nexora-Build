import { useEffect, useState } from "react";
import { fileObjectUrl } from "../lib/api";

const cache = new Map<string, string>();

/** <img> for protected files (/api/files/…/download) – loads with the login token, cached per session. */
export default function AuthImg({ src, alt = "", className = "", fallback }: { src?: string | null; alt?: string; className?: string; fallback?: string }) {
  const [url, setUrl] = useState<string | null>(src ? cache.get(src) ?? null : null);
  useEffect(() => {
    let live = true;
    if (!src) { setUrl(null); return; }
    if (!src.startsWith("/api/")) { setUrl(src); return; }
    const hit = cache.get(src);
    if (hit) { setUrl(hit); return; }
    fileObjectUrl(src).then((u) => { cache.set(src, u); if (live) setUrl(u); }).catch(() => live && setUrl(null));
    return () => { live = false; };
  }, [src]);
  const shown = url || fallback;
  if (!shown) return <div className={`animate-pulse bg-slate-200 ${className}`} />;
  return <img src={shown} alt={alt} className={className} loading="lazy" />;
}
