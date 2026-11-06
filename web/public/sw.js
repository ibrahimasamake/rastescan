/* RasteScan service worker: the app opens offline, public data shows the last copy, photos are cached.
   Reports are never cached here; the page keeps unsent ones in IndexedDB (see src/outbox.ts). */
const VERSION = "rs-v1";
const SHELL = ["./", "./index.html", "./icon.svg", "./manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys().then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

async function networkFirst(req) {
  const cache = await caches.open(VERSION);
  try {
    const res = await fetch(req);
    if (res.ok) cache.put(req, res.clone());
    return res;
  } catch {
    const hit = await cache.match(req);
    if (hit) return hit;
    if (req.mode === "navigate") return (await cache.match("./index.html")) || Response.error();
    return Response.error();
  }
}

async function cacheFirst(req) {
  const cache = await caches.open(VERSION);
  const hit = await cache.match(req);
  if (hit) return hit;
  const res = await fetch(req);
  if (res.ok) cache.put(req, res.clone());
  return res;
}

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.endsWith(".apk")) return; // far too big to keep in the offline cache
  if (url.pathname.includes("/assets/") || url.pathname.includes("/api/photos/")) {
    e.respondWith(cacheFirst(req));
  } else if (url.pathname.includes("/api/public/") || req.mode === "navigate") {
    e.respondWith(networkFirst(req));
  }
});
