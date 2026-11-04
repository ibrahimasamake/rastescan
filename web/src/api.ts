/** Client for the RasteScan API. VITE_API_BASE is empty for the web app (same origin) and the CloudFront URL for the Android app. */
export const API_BASE: string = (import.meta.env.VITE_API_BASE ?? "").replace(/\/$/, "");

export type Hazard = "Pothole" | "Open Manhole" | "Road Fissure" | "Waterlogging" | "Debris" | "Slab Displacement" | "None";
export type Urgency = "LOW" | "MEDIUM" | "HIGH" | "CRITICAL";
export type Status = "new" | "review" | "assigned" | "fixed" | "verified" | "dismissed" | "no_damage";

export interface Inspection {
  hazard_type: Hazard;
  confidence: number;
  severity_score: number;
  urgency_level: Urgency;
  repair_recommendation: string;
  estimated_repair_time_hours: number;
  estimated_dimensions: { width_cm: number; depth_category: string };
  bounding_box: { ymin: number; xmin: number; ymax: number; xmax: number };
}

export interface Report {
  code: string;
  lat: number | null;
  lng: number | null;
  photo_url: string;
  after_photo_url: string | null;
  result: Inspection;
  after_result: Inspection | null;
  hazard_type: Hazard;
  severity: number;
  urgency: Urgency;
  model_urgency: Urgency;
  confidence: number;
  needs_review: boolean;
  status: Status;
  merged_into: string | null;
  merged_count: number;
  created_at: string;
  due_at: string | null;
  updated_at: string;
}

export interface Queue {
  tickets: Report[];
  review: Report[];
  counts: Record<Urgency, number>;
  verified: number;
  ai_mode: string;
}

export class ApiError extends Error {}

export function absUrl(url: string): string {
  return url.startsWith("http") ? url : API_BASE + url;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(API_BASE + path, init);
  } catch {
    throw new ApiError("Could not reach the server. Check your internet connection and try again.");
  }
  if (!res.ok) {
    let msg = `Something went wrong (error ${res.status}). Try again.`;
    try {
      const body = await res.json();
      if (typeof body.detail === "string") msg = body.detail;
    } catch { /* keep default */ }
    throw new ApiError(msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => call<{ ok: boolean; ai_mode: string }>("/api/health"),
  submit: (photo: Blob, deviceId: string, pos: { lat: number; lng: number } | null) => {
    const form = new FormData();
    form.append("photo", photo, "photo.jpg");
    form.append("device_id", deviceId);
    if (pos) {
      form.append("lat", String(pos.lat));
      form.append("lng", String(pos.lng));
    }
    return call<Report>("/api/reports", { method: "POST", body: form });
  },
  mine: (deviceId: string) => call<Report[]>(`/api/reports?device_id=${encodeURIComponent(deviceId)}`),
  queue: () => call<Queue>("/api/queue"),
  setStatus: (code: string, status: Status, pin: string) =>
    call<Report>(`/api/reports/${code}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", "X-Dashboard-Pin": pin },
      body: JSON.stringify({ status }),
    }),
  afterPhoto: (code: string, photo: Blob, pin: string) => {
    const form = new FormData();
    form.append("photo", photo, "after.jpg");
    return call<Report>(`/api/reports/${code}/after-photo`, { method: "POST", body: form, headers: { "X-Dashboard-Pin": pin } });
  },
};
