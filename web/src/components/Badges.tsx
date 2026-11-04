import type { PublicStatus, Urgency } from "../api";
import { useI18n } from "../i18n";
import type { Key } from "../i18n/en";
import { Icon, type IconName } from "./Icons";

const URGENCY_ICON: Record<Urgency, IconName> = { CRITICAL: "alert", HIGH: "alert", MEDIUM: "clock", LOW: "dot" };
const STATUS_ICON: Record<PublicStatus, IconName> = {
  reported: "dot", ai_verified: "eye", assigned: "user", repair_done: "wrench", resolved: "check", dismissed: "x",
};

export function UrgencyBadge({ urgency, big = false }: { urgency: Urgency; big?: boolean }) {
  const { t } = useI18n();
  return (
    <span className={`badge u-${urgency} ${big ? "big" : ""}`}>
      <Icon name={URGENCY_ICON[urgency]} size={big ? 18 : 14} />
      {t(`urgency.${urgency}` as Key)}
    </span>
  );
}

export function StatusBadge({ status, big = false }: { status: PublicStatus; big?: boolean }) {
  const { t } = useI18n();
  const label = status === "resolved" && big ? t("status.resolvedVerified") : t(`status.${status}` as Key);
  return (
    <span className={`badge s-${status} ${big ? "big" : ""}`}>
      <Icon name={STATUS_ICON[status] ?? "dot"} size={big ? 18 : 14} />
      {label}
    </span>
  );
}

export function DemoBadge() {
  const { t } = useI18n();
  return <span className="badge demo">{t("demo.badge")}</span>;
}
