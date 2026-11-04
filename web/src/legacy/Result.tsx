import { absUrl, type Inspection, type Report, type Urgency } from "./api";
import { FIX_WITHIN, URGENCY_LABEL, hazardName } from "./format";

export function UrgencyChip({ urgency }: { urgency: Urgency }) {
  return <span className={`chip chip-${urgency}`}>{URGENCY_LABEL[urgency]}</span>;
}

export function SeverityMeter({ score, urgency }: { score: number; urgency: Urgency }) {
  return (
    <div className="meter" role="meter" aria-valuemin={1} aria-valuemax={10} aria-valuenow={score} aria-label="Severity">
      <i style={{ width: `${score * 10}%`, background: `var(--u-${urgency})` }} />
    </div>
  );
}

/** The photo with the damage boxed, drawn from the model's 0–1000 coordinates. */
export function PhotoWithBox({ src, result, urgency, alt }: { src: string; result: Inspection; urgency: Urgency; alt: string }) {
  const b = result.bounding_box;
  const hasBox = result.hazard_type !== "None" && b.ymax > b.ymin && b.xmax > b.xmin;
  return (
    <div className="photo">
      <img src={absUrl(src)} alt={alt} />
      {hasBox && (
        <div
          className="box"
          style={{
            top: `${b.ymin / 10}%`, left: `${b.xmin / 10}%`,
            height: `${(b.ymax - b.ymin) / 10}%`, width: `${(b.xmax - b.xmin) / 10}%`,
            borderColor: `var(--u-${urgency})`,
          }}
        >
          <span style={{ background: `var(--u-${urgency})` }}>{result.hazard_type} {result.severity_score.toFixed(1)}</span>
        </div>
      )}
    </div>
  );
}

export function ResultDetails({ report }: { report: Report }) {
  const r = report.result;
  const noDamage = r.hazard_type === "None";
  return (
    <div className="result">
      <div className="row">
        <h2 className="hazard">{hazardName(r.hazard_type)}</h2>
        {!noDamage && <UrgencyChip urgency={report.urgency} />}
      </div>
      {!noDamage && (
        <>
          <div className="row small">
            <span className="muted">Severity</span>
            <b className="num">{report.severity.toFixed(1)} / 10</b>
          </div>
          <SeverityMeter score={report.severity} urgency={report.urgency} />
        </>
      )}
      <dl className="kv">
        <dt>Confidence</dt>
        <dd>{Math.round(r.confidence * 100)}%</dd>
        {!noDamage && (
          <>
            <dt>Size</dt>
            <dd>About {r.estimated_dimensions.width_cm} cm wide, {r.estimated_dimensions.depth_category.toLowerCase()}</dd>
            <dt>Repair time</dt>
            <dd>About {r.estimated_repair_time_hours} hours</dd>
            <dt>Fix</dt>
            <dd>{FIX_WITHIN[report.urgency]}</dd>
          </>
        )}
      </dl>
      <p className="rec">{r.repair_recommendation}</p>
    </div>
  );
}
