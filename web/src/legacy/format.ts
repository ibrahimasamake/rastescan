import type { Hazard, Status, Urgency } from "./api";

export const URGENCY_LABEL: Record<Urgency, string> = { LOW: "Low", MEDIUM: "Medium", HIGH: "High", CRITICAL: "Critical" };
export const FIX_WITHIN: Record<Urgency, string> = {
  LOW: "Next quarterly ward round", MEDIUM: "Within 7 days", HIGH: "Within 48 hours", CRITICAL: "Within 24 hours",
};
export const STATUS_LABEL: Record<Status, string> = {
  new: "Waiting for a crew", review: "A person will check this photo", assigned: "Crew assigned",
  fixed: "Marked fixed, waiting for after photo", verified: "Repair verified", dismissed: "Closed without repair",
  no_damage: "No damage found",
};

export function hazardName(h: Hazard): string {
  return h === "None" ? "Road OK" : h;
}

export function ago(iso: string): string {
  const min = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min} min ago`;
  const h = Math.round(min / 60);
  if (h < 24) return `${h} h ago`;
  return `${Math.round(h / 24)} days ago`;
}

export function dueText(iso: string | null): string {
  if (!iso) return "";
  const h = Math.round((new Date(iso).getTime() - Date.now()) / 3600000);
  if (h < 0) return `Overdue by ${-h} h`;
  if (h < 48) return `Due in ${h} h`;
  return `Due in ${Math.round(h / 24)} days`;
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
