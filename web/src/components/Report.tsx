import { useState } from "react";
import { Link } from "react-router-dom";
import { absUrl, detectionsOf, type Inspection, type PublicReport, type TimelineEvent, type Urgency } from "../api";
import { ago, hazardLabel, statusLabel, urgencyLabel } from "../format";
import { useI18n } from "../i18n";
import type { Key } from "../i18n/en";
import { DemoBadge, StatusBadge, UrgencyBadge } from "./Badges";
import { Icon } from "./Icons";

/** The photo with the damage boxed, drawn from the model's 0–1000 coordinates. */
export function PhotoWithBox({ src, result, urgency, alt }: { src: string; result: Inspection; urgency: Urgency; alt: string }) {
  const { t } = useI18n();
  const found = detectionsOf(result).filter((d) => d.bounding_box.ymax > d.bounding_box.ymin && d.bounding_box.xmax > d.bounding_box.xmin);
  const many = found.length > 1;
  return (
    <div className="photo">
      <img src={absUrl(src)} alt={alt} loading="lazy" decoding="async" />
      {found.map((d, i) => {
        const b = d.bounding_box;
        return (
          <div key={i} className={`box box-${many ? d.urgency_level : urgency}`} aria-hidden="true" style={{
            top: `${b.ymin / 10}%`, left: `${b.xmin / 10}%`, height: `${(b.ymax - b.ymin) / 10}%`, width: `${(b.xmax - b.xmin) / 10}%`,
          }}>
            <span>{many ? `${i + 1} · ${d.severity_score.toFixed(1)}` : `${hazardLabel(t, d.hazard_type)} ${d.severity_score.toFixed(1)}`}</span>
          </div>
        );
      })}
    </div>
  );
}

/** Numbered list of every defect found in the photo; shown only when there is more than one. */
export function DetectionList({ result }: { result: Inspection }) {
  const { t } = useI18n();
  const list = detectionsOf(result);
  if (list.length < 2) return null;
  return (
    <div className="section">
      <h3>{t("report.defects", { n: list.length })}</h3>
      <ol className="defects">
        {list.map((d, i) => (
          <li key={i}>
            <b>{hazardLabel(t, d.hazard_type)}</b> · {t("report.severityValue", { n: d.severity_score.toFixed(1) })} · {urgencyLabel(t, d.urgency_level)}
            {d.estimated_dimensions.width_cm > 0 && <> · {t("report.sizeValue", { cm: d.estimated_dimensions.width_cm, depth: t(`depth.${d.estimated_dimensions.depth_category}` as Key) })}</>}
            <p className="rec small" lang="en">{d.repair_recommendation}</p>
          </li>
        ))}
      </ol>
    </div>
  );
}

/** Drag (or use arrow keys on) the slider to compare the reported photo with the repair photo. */
export function BeforeAfter({ before, after, code }: { before: string; after: string; code: string }) {
  const { t } = useI18n();
  const [pos, setPos] = useState(50);
  return (
    <div className="ba">
      <img src={absUrl(before)} alt={t("report.photoAlt", { hazard: "", code })} />
      <div className="after" style={{ clipPath: `inset(0 0 0 ${pos}%)` }}>
        <img src={absUrl(after)} alt={t("report.afterAlt", { code })} />
      </div>
      <span className="tag" style={{ left: 10 }}>{t("report.before")}</span>
      <span className="tag" style={{ right: 10 }}>{t("report.after")}</span>
      <input type="range" min={0} max={100} value={pos} onChange={(e) => setPos(Number(e.target.value))}
        aria-label={t("report.slider")} aria-valuetext={`${pos}%`} />
      <div className="handle" style={{ left: `calc(${pos}% - 1.5px)` }} />
    </div>
  );
}

export function SeverityMeter({ score, urgency }: { score: number; urgency: Urgency }) {
  const colours: Record<Urgency, string> = { CRITICAL: "var(--crit)", HIGH: "var(--high)", MEDIUM: "#a87400", LOW: "var(--low)" };
  return (
    <div className="meter" aria-hidden="true">
      <i style={{ width: `${score * 10}%`, background: colours[urgency] }} />
    </div>
  );
}

function eventText(t: ReturnType<typeof useI18n>["t"], e: TimelineEvent): string {
  const d = e.detail ?? {};
  const hazard = d.hazard_type ? hazardLabel(t, String(d.hazard_type)) : "";
  const vars = {
    actor: e.actor,
    value: e.event === "status" && e.new_value ? statusLabel(t, statusPublic(e.new_value)) :
      e.event === "priority_raised" && e.new_value ? urgencyLabel(t, e.new_value as Urgency) : e.new_value ?? e.old_value ?? "",
    hazard,
    urgency: d.urgency ? urgencyLabel(t, d.urgency as Urgency).toLowerCase() : "",
    severity: typeof d.severity === "number" ? d.severity.toFixed(1) : "",
    code: d.code ? String(d.code) : "",
  };
  if (e.event === "status" && e.new_value === "dismissed") return t("event.dismissed", vars);
  return t(`event.${e.event}` as Key, vars);
}

const STATUS_PUBLIC: Record<string, string> = {
  new: "ai_verified", assigned: "assigned", fixed: "repair_done", verified: "resolved", dismissed: "dismissed", review: "reported",
};
function statusPublic(s: string): string {
  return STATUS_PUBLIC[s] ?? s;
}

export function Timeline({ events }: { events: TimelineEvent[] }) {
  const { t, date } = useI18n();
  return (
    <ol className="timeline">
      {events.map((e, i) => {
        const cls = e.event === "verified" ? "done" : e.event === "reopened" ? "warn" : e.event === "comment" ? "comment" : "";
        const reason = e.detail?.reason && typeof e.detail.reason === "string" && !["ai_busy", "low_confidence"].includes(e.detail.reason)
          ? e.detail.reason : null;
        return (
          <li key={i} className={cls}>
            <time dateTime={e.at}>{date(e.at, true)}</time>
            <span>{eventText(t, e)}</span>
            {e.event === "comment" && e.detail?.text && <p className="quote">{String(e.detail.text)}</p>}
            {reason && <p className="small muted">{t("event.reason", { reason })}</p>}
          </li>
        );
      })}
    </ol>
  );
}

/** A card linking to one report; with both photos it shows a before/after pair. */
export function ReportCard({ r }: { r: PublicReport }) {
  const { t } = useI18n();
  return (
    <Link to={`/r/${r.code}`} className="card rcard">
      {r.after_photo_url ? (
        <div className="thumbs">
          <figure><img src={absUrl(r.photo_url)} alt="" loading="lazy" decoding="async" /><figcaption>{t("report.before")}</figcaption></figure>
          <figure><img src={absUrl(r.after_photo_url)} alt="" loading="lazy" decoding="async" /><figcaption>{t("report.after")}</figcaption></figure>
        </div>
      ) : (
        <div className="thumbs" style={{ gridTemplateColumns: "1fr" }}>
          <figure><img src={absUrl(r.photo_url)} alt="" loading="lazy" decoding="async" /></figure>
        </div>
      )}
      <div className="body">
        <div className="row">
          <b>{hazardLabel(t, r.hazard_type)}</b>
          <StatusBadge status={r.public_status} />
        </div>
        <div className="row small muted">
          <span><Icon name="pin" size={13} /> {r.ward?.name ?? r.code}</span>
          <span>{ago(t, r.resolved_at ?? r.created_at)}</span>
        </div>
        <div className="row">
          <UrgencyBadge urgency={r.urgency} />
          {r.is_demo && <DemoBadge />}
        </div>
      </div>
    </Link>
  );
}
