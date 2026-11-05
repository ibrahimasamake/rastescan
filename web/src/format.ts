import type { Hazard, PublicStatus, Urgency } from "./api";
import type { Key } from "./i18n/en";

type T = (key: Key, vars?: Record<string, string | number | null | undefined>) => string;

export function hazardLabel(t: T, h: Hazard | string): string {
  return t(`hazard.${h}` as Key);
}

export function urgencyLabel(t: T, u: Urgency): string {
  return t(`urgency.${u}` as Key);
}

export function statusLabel(t: T, s: PublicStatus | string): string {
  return t(`status.${s}` as Key);
}

/** "3 h", "2 days": the larger unit that fits. */
export function duration(t: T, ms: number): string {
  const min = Math.max(1, Math.round(Math.abs(ms) / 60000));
  if (min < 60) return t("time.minutes", { n: min });
  const h = Math.round(min / 60);
  if (h < 48) return t("time.hours", { n: h });
  const d = Math.round(h / 24);
  return d === 1 ? t("time.day") : t("time.days", { n: d });
}

export function ago(t: T, iso: string): string {
  const ms = Date.now() - new Date(iso).getTime();
  return ms < 60000 ? t("time.justNow") : t("time.ago", { time: duration(t, ms) });
}

export function sla(t: T, dueIso: string | null, closed: boolean): { text: string; overdue: boolean } | null {
  if (!dueIso) return null;
  if (closed) return { text: t("sla.done"), overdue: false };
  const ms = new Date(dueIso).getTime() - Date.now();
  return ms < 0 ? { text: t("sla.overdue", { time: duration(t, ms) }), overdue: true } : { text: t("sla.dueIn", { time: duration(t, ms) }), overdue: false };
}

export function deviceId(): string {
  try {
    let id = localStorage.getItem("rastescan-device");
    if (!id) {
      id = typeof crypto.randomUUID === "function" ? crypto.randomUUID() : `d-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      localStorage.setItem("rastescan-device", id);
    }
    return id;
  } catch {
    return "no-storage";
  }
}

export const CLOSED = new Set(["verified", "dismissed", "no_damage"]);

/** Rupees in the Indian digit grouping, e.g. ₹1,25,000. */
export function inr(n: number): string {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(n);
}
