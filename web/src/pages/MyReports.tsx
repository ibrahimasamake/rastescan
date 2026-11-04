import { useEffect } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { StatusBadge, UrgencyBadge } from "../components/Badges";
import { PageHead } from "../components/Layout";
import { Empty, ErrorBox, Skeleton, useAsync } from "../components/States";
import { ago, deviceId, hazardLabel, statusLabel } from "../format";
import { useI18n } from "../i18n";

const SEEN_KEY = "rs-seen";

function readSeen(): Record<string, string> {
  try {
    return JSON.parse(localStorage.getItem(SEEN_KEY) ?? "{}");
  } catch {
    return {};
  }
}

export default function MyReports() {
  const { t } = useI18n();
  const { data, error, loading, reload } = useAsync(() => api.mine(deviceId()), [], 60000);
  const seen = readSeen();

  // Remember what was shown, so the next visit can highlight what changed.
  useEffect(() => {
    if (!data) return;
    const next = Object.fromEntries(data.map((r) => [r.code, r.status]));
    try {
      localStorage.setItem(SEEN_KEY, JSON.stringify(next));
    } catch {
      /* fine */
    }
  }, [data]);

  return (
    <div className="wrap page">
      <PageHead title={t("mine.title")} lead={t("mine.lead")} />
      {loading && !data && <><Skeleton h={64} /><Skeleton h={64} /></>}
      {!!error && !data && <ErrorBox error={error} retry={reload} />}
      {data && data.length === 0 && <Empty><p>{t("mine.empty")}</p><Link className="btn accent" to="/report">{t("home.cta")}</Link></Empty>}
      {data && data.length > 0 && (
        <ul className="grid" style={{ listStyle: "none", padding: 0, margin: 0 }}>
          {data.map((r) => {
            const changed = seen[r.code] && seen[r.code] !== r.status;
            const published = !["review", "no_damage"].includes(r.status);
            const label = r.status === "review" ? t("status.review") : r.status === "no_damage" ? t("status.no_damage") : statusLabel(t, r.public_status);
            return (
              <li key={r.code} className="card pad" style={changed ? { borderColor: "var(--saffron)", borderWidth: 2 } : undefined}>
                <div className="status-head">
                  <b>{published ? <Link to={`/r/${r.merged_into ?? r.code}`}>{hazardLabel(t, r.hazard_type)} · {r.code}</Link> : `${hazardLabel(t, r.hazard_type)} · ${r.code}`}</b>
                  {published ? <StatusBadge status={r.public_status} /> : <span className="badge s-reported">{label}</span>}
                  {published && <UrgencyBadge urgency={r.urgency} />}
                </div>
                <p className="small muted">{ago(t, r.created_at)}{r.merged_into ? ` · ${t("report.mergedInto", { code: r.merged_into })}` : ""}</p>
                {changed && <p className="small" style={{ color: "var(--high)", fontWeight: 700 }}>{t("mine.changed")}</p>}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
