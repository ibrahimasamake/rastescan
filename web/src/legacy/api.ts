/** The PIN-based calls used by the first ward dashboard. Removed when the officer pages replace it. */
import { API_BASE, ApiError, type Report, type Status, type Urgency } from "../api";

export { absUrl, ApiError } from "../api";
export type { Hazard, Inspection, Report, Status, Urgency } from "../api";

export interface Queue {
  tickets: Report[];
  review: Report[];
  counts: Record<Urgency, number>;
  verified: number;
  ai_mode: string;
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
    throw new ApiError(msg, res.status);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => call<{ ok: boolean; ai_mode: string }>("/api/health"),
  queue: (pin: string) => call<Queue>("/api/queue", { headers: { "X-Dashboard-Pin": pin } }),
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
