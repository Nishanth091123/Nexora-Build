/* Nexora Build service worker – offline support.
   Pages / scripts / images: network first, cached copy when offline.
   API GET (data): network first, cached copy when offline (shown with the offline bar).
   API writes are never cached here – the app queues them itself (src/lib/outbox.ts). */
const VERSION = "nexora-v11";
const SHELL = ["/", "/manifest.webmanifest", "/favicon.svg", "/icons/icon-192.png", "/icons/icon-512.png"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL).catch(() => {})).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  const isApi = url.pathname.startsWith("/api/");               // same origin, or the online backend (Hugging Face)
  if (url.origin !== self.location.origin && !isApi) return;  // maps, fonts, weather: browser default
  if (req.headers.get("upgrade") === "websocket") return;
  e.respondWith((async () => {
    try {
      // pages and the service worker's own files: always ask the server (no stale app after an update)
      const fresh = !isApi && !/\/assets\//.test(url.pathname);
      const res = await (fresh ? fetch(url.href, { cache: "no-cache", credentials: "same-origin" }) : fetch(req));
      if (res.ok && (res.type === "basic" || res.type === "default" || res.type === "cors")) {
        const len = Number(res.headers.get("content-length") || 0);
        if (!isApi || len < 8_000_000) {
          const copy = res.clone();
          caches.open(VERSION).then((c) => c.put(req, copy)).catch(() => {});
        }
      }
      return res;
    } catch (err) {
      const hit = await caches.match(req);
      if (hit) return hit;
      if (req.mode === "navigate") {
        const shell = await caches.match("/");
        if (shell) return shell;
      }
      if (isApi) return new Response(JSON.stringify({ detail: "Offline – this data was not opened before on this device." }),
        { status: 503, headers: { "Content-Type": "application/json" } });
      throw err;
    }
  })());
});

// ---- Phase 7.8: weather safety alerts (Web Push) – shown even when the app is closed
self.addEventListener("push", (e) => {
  let d = {};
  try { d = e.data ? e.data.json() : {}; } catch { d = { body: e.data && e.data.text() }; }
  e.waitUntil(self.registration.showNotification(d.title || "Nexora Build", {
    body: d.body || "", icon: "/icons/icon-192.png", badge: "/icons/icon-192.png",
    tag: d.title || "nexora", renotify: true, data: { url: d.url || "/" },
  }));
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = new URL((e.notification.data && e.notification.data.url) || "/", self.location.origin).href;
  e.waitUntil((async () => {
    const list = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
    for (const c of list) {
      if (!c.url.startsWith(self.location.origin)) continue;
      try { await c.focus(); } catch { /* ignore */ }
      try { if (c.url !== url && "navigate" in c) await c.navigate(url); } catch { /* page not controlled yet – it is open anyway */ }
      return;
    }
    await self.clients.openWindow(url);  // app closed – open it
  })());
});
