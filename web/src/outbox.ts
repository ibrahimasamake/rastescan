/** Reports taken without a network are kept in IndexedDB and sent when the connection returns. */
import { api, ApiError, type Report } from "./api";

export interface Pending {
  id: string;
  photo: Blob;
  deviceId: string;
  lat: number | null;
  lng: number | null;
  note: string;
  email: string;
  created: number;
}

const DB = "rastescan";
const STORE = "outbox";

function open(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB, 1);
    req.onupgradeneeded = () => req.result.createObjectStore(STORE, { keyPath: "id" });
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

async function tx<T>(mode: IDBTransactionMode, fn: (s: IDBObjectStore) => IDBRequest<T>): Promise<T> {
  const db = await open();
  return new Promise((resolve, reject) => {
    const req = fn(db.transaction(STORE, mode).objectStore(STORE));
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function queue(item: Omit<Pending, "id" | "created">): Promise<void> {
  const id = `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  await tx("readwrite", (s) => s.put({ ...item, id, created: Date.now() }));
  notify();
}

export async function pending(): Promise<Pending[]> {
  try {
    return await tx("readonly", (s) => s.getAll() as IDBRequest<Pending[]>);
  } catch {
    return [];
  }
}

let running: Promise<Report[]> | null = null;

/** Sends what it can, one run at a time (two "online" events must not send a report twice). */
export function flush(): Promise<Report[]> {
  if (!running) running = sendAll().finally(() => { running = null; });
  return running;
}

/** Stops at the first network failure; drops items the server rejects for good (4xx). */
async function sendAll(): Promise<Report[]> {
  const sent: Report[] = [];
  for (const p of await pending()) {
    try {
      const pos = p.lat !== null && p.lng !== null ? { lat: p.lat, lng: p.lng } : null;
      sent.push(await api.submit(p.photo, p.deviceId, pos, p.note, p.email));
      await tx("readwrite", (s) => s.delete(p.id));
    } catch (e) {
      if (e instanceof ApiError && e.status >= 400 && e.status < 500 && e.status !== 429) {
        await tx("readwrite", (s) => s.delete(p.id));
        continue;
      }
      break;
    }
  }
  if (sent.length) notify();
  return sent;
}

const listeners = new Set<() => void>();
export function onChange(fn: () => void): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}
function notify() {
  listeners.forEach((fn) => fn());
}

let started = false;
/** Called once at start-up: tries to send on load and whenever the browser comes back online. */
export function startOutbox(onSent: (n: number) => void) {
  if (started || typeof indexedDB === "undefined") return;
  started = true;
  const go = () => flush().then((r) => r.length && onSent(r.length)).catch(() => {});
  window.addEventListener("online", go);
  go();
}
