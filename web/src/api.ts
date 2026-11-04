/** Client for the RasteScan API. VITE_API_BASE is empty for the web app (same origin) and the CloudFront URL for the Android app. */
export const API_BASE: string = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

export const HAZARDS = ["Pothole", "Open Manhole", "Road Fissure", "Waterlogging", "Debris", "Slab Displacement"] as const;
export type Hazard = (typeof HAZARDS)[number] | "None";
export const URGENCIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const;
export type Urgency = (typeof URGENCIES)[number];
export type Status = "new" | "review" | "assigned" | "fixed" | "verified" | "dismissed" | "no_damage";
export type PublicStatus = "reported" | "ai_verified" | "assigned" | "repair_done" | "resolved" | "dismissed";

export interface Detection {
  hazard_type: Hazard;
  confidence: number;
  severity_score: number;
  urgency_level: Urgency;
  repair_recommendation: string;
  estimated_repair_time_hours: number;
  estimated_dimensions: { width_cm: number; depth_category: string };
  bounding_box: { ymin: number; xmin: number; ymax: number; xmax: number };
}

/** The worst defect in the photo, plus every defect found (worst first). Older reports have no `detections`. */
export interface Inspection extends Detection {
  detections?: Detection[];
}

/** Every real defect in a result; falls back to the headline defect for reports made before multi-defect scans. */
export function detectionsOf(r: Inspection): Detection[] {
  if (r.detections?.length) return r.detections;
  return r.hazard_type === "None" ? [] : [r];
}

export interface Ward {
  code: string;
  name: string;
}

/** What anyone can see about a report. */
export interface PublicReport {
  code: string;
  lat: number | null;
  lng: number | null;
  ward: Ward | null;
  hazard_type: Hazard;
  severity: number;
  urgency: Urgency;
  status: Status;
  public_status: PublicStatus;
  photo_url: string;
  after_photo_url: string | null;
  repair_recommendation: string | null;
  estimated_repair_time_hours: number | null;
  reported_count: number;
  assignee: string | null;
  created_at: string;
  due_at: string | null;
  resolved_at: string | null;
  updated_at: string;
  overdue: boolean;
  is_demo: boolean;
}

export interface TimelineEvent {
  at: string;
  event: string;
  actor: string;
  old_value: string | null;
  new_value: string | null;
  detail: Record<string, string | number | boolean | null> | null;
}

export interface PublicDetail extends PublicReport {
  result: Inspection;
  after_result: Inspection | null;
  confidence: number;
  dismiss_reason: string | null;
  merged_into: string | null;
  timeline: TimelineEvent[];
}

/** The citizen's own report and the officer view: public detail plus a few working fields. */
export interface Report extends PublicDetail {
  model_urgency: Urgency;
  needs_review: boolean;
  ai_pending: boolean;
  merged_count: number;
  note: string | null;
  has_contact?: boolean;
}

export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
}

export interface Stats {
  reported_today: number;
  open_now: number;
  overdue_now: number;
  resolved_this_month: number;
  avg_days_to_fix: number | null;
  total_public: number;
  demo_count: number;
  last_updated: string | null;
  ai_mode: string;
}

export interface WardScore {
  code: string;
  name: string;
  lat: number;
  lng: number;
  open: number;
  overdue: number;
  resolved: number;
  avg_days_to_resolve: number | null;
  pct_within_deadline: number | null;
  rank: number;
}

export interface PortalConfig {
  site_name: string;
  ai_mode: string;
  hazards: string[];
  urgencies: string[];
  wards: (Ward & { lat: number; lng: number })[];
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status = 0) {
    super(message);
    this.status = status;
  }
}

export function absUrl(url: string | null | undefined): string {
  if (!url) return "";
  return /^(https?:|blob:|data:)/.test(url) ? url : API_BASE + url;
}

// ---------- officer session ----------
// The web app relies on the HttpOnly cookie. The Android app runs on another origin, so it keeps the token in memory.
let bearer: string | null = null;
try {
  bearer = sessionStorage.getItem("rs-token");
} catch {
  bearer = null;
}

export function setBearer(token: string | null) {
  bearer = API_BASE ? token : null;
  try {
    if (bearer) sessionStorage.setItem("rs-token", bearer);
    else sessionStorage.removeItem("rs-token");
  } catch {
    /* private mode: session lasts until the tab closes */
  }
}

// Expo fallback: the shared PIN, kept only for this browser tab.
let pin: string | null = null;
try {
  pin = sessionStorage.getItem("rs-pin");
} catch {
  pin = null;
}

export function setPin(value: string | null) {
  pin = value;
  try {
    if (value) sessionStorage.setItem("rs-pin", value);
    else sessionStorage.removeItem("rs-pin");
  } catch {
    /* tab-only */
  }
}

function authHeaders(): Record<string, string> {
  const h: Record<string, string> = { "X-Requested-With": "RasteScan" };
  if (bearer) h.Authorization = `Bearer ${bearer}`;
  if (pin) h["X-Dashboard-Pin"] = pin;
  return h;
}

async function call<T>(path: string, init: RequestInit = {}): Promise<T> {
  let res: Response;
  try {
    res = await fetch(API_BASE + path, { credentials: API_BASE ? "omit" : "same-origin", ...init });
  } catch {
    throw new ApiError("offline", 0);
  }
  if (!res.ok) {
    let msg = `error ${res.status}`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") msg = body.detail;
    } catch {
      /* keep default */
    }
    throw new ApiError(msg, res.status);
  }
  return res.json() as Promise<T>;
}

function json(method: string, body: unknown): RequestInit {
  return { method, headers: { "Content-Type": "application/json", ...authHeaders() }, body: JSON.stringify(body) };
}

export function query(params: Record<string, string | number | boolean | null | undefined>): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== undefined && v !== null && v !== "" && v !== false) q.set(k, String(v));
  const s = q.toString();
  return s ? `?${s}` : "";
}

export const api = {
  health: () => call<{ ok: boolean; ai_mode: string }>("/api/health"),
  config: () => call<PortalConfig>("/api/public/config"),
  stats: () => call<Stats>("/api/public/stats"),
  wards: () => call<WardScore[]>("/api/public/wards"),
  recentlyResolved: () => call<PublicReport[]>("/api/public/recently-resolved"),
  reports: (params: Record<string, string | number | boolean | undefined>) =>
    call<Page<PublicReport>>("/api/public/reports" + query(params)),
  report: (code: string) => call<PublicDetail>(`/api/public/reports/${encodeURIComponent(code)}`),
  vote: (code: string, deviceId: string) =>
    call<{ added: boolean; reported_count: number }>(`/api/public/reports/${encodeURIComponent(code)}/vote`, json("POST", { device_id: deviceId })),
  exportUrl: (params: Record<string, string | number | boolean | undefined>) => API_BASE + "/api/public/export.csv" + query(params),

  submit: (photo: Blob, deviceId: string, pos: { lat: number; lng: number } | null, note?: string, email?: string) => {
    const form = new FormData();
    form.append("photo", photo, "photo.jpg");
    form.append("device_id", deviceId);
    if (pos) {
      form.append("lat", String(pos.lat));
      form.append("lng", String(pos.lng));
    }
    if (note) form.append("note", note);
    if (email) form.append("contact_email", email);
    return call<Report>("/api/reports", { method: "POST", body: form });
  },
  mine: (deviceId: string) => call<Report[]>(`/api/reports?device_id=${encodeURIComponent(deviceId)}`),
};

// ---------- officer API ----------
export interface Officer {
  signed_in: boolean;
  name?: string;
  role?: "officer" | "admin";
}

export interface Queue {
  tickets: Report[];
  review: Report[];
  counts: Record<Urgency, number>;
  verified: number;
  overdue: number;
  ai_mode: string;
}

export interface HistoryRow extends TimelineEvent {
  public: number;
}

export interface OfficerReport extends Report {
  duplicates: string[];
  history: HistoryRow[];
}

export interface WorkOrder {
  assignee: string;
  generated_at: string;
  stops: (Report & { leg_m: number | null })[];
  total_km: number;
  total_hours: number;
}

export interface Analytics {
  days: number;
  per_day: { date: string; reported: number; resolved: number }[];
  avg_days_by_urgency: Record<Urgency, number | null>;
  avg_days_by_ward: { code: string; name: string; avg_days: number | null; resolved: number }[];
  sla: { resolved: number; on_time: number; pct: number | null; open_overdue: number };
  top_hazards: [string, number][];
  ai_accuracy: { checked: number; overridden: number; agreement_pct: number | null };
  totals: { reported: number; resolved: number };
}

export interface ModelInfo {
  id: string;
  provider: "ollama" | "groq" | "bedrock" | "fake" | "yolo";
  model: string;
  label: string;
  installed: boolean;
  runnable: boolean;
  size_gb: number | null;
  note: string;
  pull: string | null;
  live: boolean;
}

export interface ModelList {
  live: { provider: string; model: string };
  ollama_running: boolean;
  ollama_url: string;
  models: ModelInfo[];
}

export interface ModelTest {
  ok: boolean;
  error: string | null;
  seconds: number;
  result: Inspection | null;
}

export interface OfficerAccount {
  id: number;
  email: string;
  name: string;
  role: "officer" | "admin";
  active: number;
  created_at: string;
}

const enc = encodeURIComponent;

export const officerApi = {
  me: () => call<Officer>("/api/v2/auth/me", { headers: authHeaders() }),
  login: async (email: string, password: string) => {
    const r = await call<{ name: string; role: string; token: string }>("/api/v2/auth/login", json("POST", { email, password }));
    setBearer(r.token);
    return r;
  },
  logout: async () => {
    setBearer(null);
    setPin(null);
    return call<{ ok: boolean }>("/api/v2/auth/logout", json("POST", {}));
  },
  queue: (params: Record<string, string | boolean | undefined> = {}) =>
    call<Queue>("/api/v2/officer/queue" + query(params), { headers: authHeaders() }),
  report: (code: string) => call<OfficerReport>(`/api/v2/officer/reports/${enc(code)}`, { headers: authHeaders() }),
  assignees: () => call<string[]>("/api/v2/officer/assignees", { headers: authHeaders() }),
  assign: (code: string, assignee: string) => call<Report>(`/api/v2/officer/reports/${enc(code)}/assign`, json("POST", { assignee })),
  status: (code: string, status: Status, reason?: string) =>
    call<Report>(`/api/v2/officer/reports/${enc(code)}/status`, json("POST", { status, reason })),
  bulkStatus: (codes: string[], status: Status, reason?: string) =>
    call<{ updated: number }>("/api/v2/officer/bulk-status", json("POST", { codes, status, reason })),
  comment: (code: string, body: string) => call<Report>(`/api/v2/officer/reports/${enc(code)}/comment`, json("POST", { body })),
  review: (code: string, hazard_type: string, severity_score: number) =>
    call<Report>(`/api/v2/officer/reports/${enc(code)}/review`, json("POST", { hazard_type, severity_score })),
  rescan: (code: string) => call<Report>(`/api/v2/officer/reports/${enc(code)}/rescan`, json("POST", {})),
  merge: (code: string, into: string) => call<Report>(`/api/v2/officer/reports/${enc(code)}/merge`, json("POST", { into })),
  unmerge: (code: string) => call<Report>(`/api/v2/officer/reports/${enc(code)}/unmerge`, json("POST", {})),
  repairPhoto: (code: string, photo: Blob) => {
    const form = new FormData();
    form.append("photo", photo, "repair.jpg");
    return call<Report>(`/api/v2/officer/reports/${enc(code)}/repair-photo`, { method: "POST", body: form, headers: authHeaders() });
  },
  workOrder: (assignee: string) => call<WorkOrder>("/api/v2/officer/work-order" + query({ assignee }), { headers: authHeaders() }),
  analytics: (days: number) => call<Analytics>("/api/v2/officer/analytics" + query({ days }), { headers: authHeaders() }),
  officers: () => call<OfficerAccount[]>("/api/v2/admin/officers", { headers: authHeaders() }),
  createOfficer: (body: { email: string; name: string; role: string; password: string }) =>
    call<OfficerAccount>("/api/v2/admin/officers", json("POST", body)),
  updateOfficer: (id: number, body: { active?: boolean; password?: string }) =>
    call<OfficerAccount>(`/api/v2/admin/officers/${id}`, json("PATCH", body)),
  models: () => call<ModelList>("/api/v2/admin/models", { headers: authHeaders() }),
  testModel: (photo: Blob, provider: string, model: string) => {
    const form = new FormData();
    form.append("photo", photo, "photo.jpg");
    form.append("provider", provider);
    form.append("model", model);
    return call<ModelTest>("/api/v2/admin/models/test", { method: "POST", body: form, headers: authHeaders() });
  },
  setLiveModel: (provider: string, model: string) =>
    call<{ live: { provider: string; model: string } }>("/api/v2/admin/models/live", json("POST", { provider, model })),
  adminExportUrl: () => API_BASE + "/api/v2/admin/export.csv",
};
