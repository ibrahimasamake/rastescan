import { useState } from "react";
import { officerApi, URGENCIES, type Analytics as A } from "../api";
import { ErrorBox, Skeleton, useAsync } from "../components/States";
import { hazardLabel, urgencyLabel } from "../format";
import { useI18n } from "../i18n";
import { OfficerShell } from "./Shell";

export default function Analytics() {
  return <OfficerShell><AnalyticsBody /></OfficerShell>;
}

/** Reported vs resolved per day as two thin bar series. Plain SVG, no chart library. */
function DailyChart({ data }: { data: A["per_day"] }) {
  const { t, date } = useI18n();
  const w = 720, h = 200, pad = { l: 30, r: 8, t: 10, b: 24 };
  const max = Math.max(1, ...data.flatMap((d) => [d.reported, d.resolved]));
  const step = (w - pad.l - pad.r) / data.length;
  const bw = Math.max(1, step / 2 - 1);
  const y = (v: number) => h - pad.b - (v / max) * (h - pad.t - pad.b);
  const ticks = [0, Math.ceil(max / 2), max];
  return (
    <figure className="chart" style={{ margin: 0 }}>
      <svg viewBox={`0 0 ${w} ${h}`} role="img" aria-label={t("officer.perDay")}>
        {ticks.map((v) => (
          <g key={v}>
            <line x1={pad.l} x2={w - pad.r} y1={y(v)} y2={y(v)} stroke="#d3dae3" />
            <text x={pad.l - 6} y={y(v) + 4} textAnchor="end">{v}</text>
          </g>
        ))}
        {data.map((d, i) => (
          <g key={d.date}>
            <rect x={pad.l + i * step} y={y(d.reported)} width={bw} height={h - pad.b - y(d.reported)} fill="#1f4a85"><title>{`${d.date}: ${d.reported}`}</title></rect>
            <rect x={pad.l + i * step + bw + 1} y={y(d.resolved)} width={bw} height={h - pad.b - y(d.resolved)} fill="#2e8b57"><title>{`${d.date}: ${d.resolved}`}</title></rect>
          </g>
        ))}
        {[0, Math.floor(data.length / 2), data.length - 1].map((i) => data[i] && (
          <text key={i} x={pad.l + i * step} y={h - 6}>{date(data[i].date)}</text>
        ))}
      </svg>
      <figcaption className="legend small">
        <span><span aria-hidden="true" style={{ display: "inline-block", width: 12, height: 12, background: "#1f4a85", marginRight: 6 }} />{t("officer.reportedSeries")}</span>
        <span><span aria-hidden="true" style={{ display: "inline-block", width: 12, height: 12, background: "#2e8b57", marginRight: 6 }} />{t("officer.resolvedSeries")}</span>
      </figcaption>
    </figure>
  );
}

function Bars({ rows, unit = "" }: { rows: { label: string; value: number | null }[]; unit?: string }) {
  const { t, num } = useI18n();
  const max = Math.max(1, ...rows.map((r) => r.value ?? 0));
  return (
    <div className="bar-chart">
      {rows.map((r) => (
        <div key={r.label} className="bar-row">
          <span>{r.label}</span>
          <span className="bar" aria-hidden="true"><i style={{ width: `${((r.value ?? 0) / max) * 100}%` }} /></span>
          <span className="num">{r.value === null ? t("wards.noData") : `${num(r.value, 1)}${unit}`}</span>
        </div>
      ))}
    </div>
  );
}

function AnalyticsBody() {
  const { t, num } = useI18n();
  const [days, setDays] = useState(30);
  const { data, error, loading, reload } = useAsync(() => officerApi.analytics(days), [days]);
  if (loading && !data) return <Skeleton h={400} />;
  if (!data) return <ErrorBox error={error} retry={reload} />;
  return (
    <>
      <div className="section-head">
        <p className="muted">{t("officer.analyticsLead", { days })}</p>
        <div className="btn-row" role="group">
          {[7, 30, 90].map((d) => <button key={d} className="btn outline small" aria-pressed={days === d} onClick={() => setDays(d)}>{d}</button>)}
        </div>
      </div>
      <div className="stats">
        <div className="stat"><b>{num(data.totals.reported)}</b><span>{t("officer.reportedSeries")}</span></div>
        <div className="stat"><b>{num(data.totals.resolved)}</b><span>{t("officer.resolvedSeries")}</span></div>
        <div className="stat"><b>{data.sla.pct === null ? "–" : `${num(data.sla.pct)}%`}</b><span>{t("officer.sla")}</span></div>
        <div className={`stat ${data.sla.open_overdue ? "warn" : ""}`}><b>{num(data.sla.open_overdue)}</b><span>{t("stat.overdue")}</span></div>
        <div className="stat"><b>{data.ai_accuracy.agreement_pct === null ? "–" : `${num(data.ai_accuracy.agreement_pct)}%`}</b><span>{t("officer.aiAccuracy")}</span></div>
      </div>
      <section className="card pad section"><h2>{t("officer.perDay")}</h2><DailyChart data={data.per_day} /></section>
      <div className="grid cols-2">
        <section className="card pad section">
          <h2>{t("officer.avgByUrgency")}</h2>
          <Bars rows={URGENCIES.map((u) => ({ label: urgencyLabel(t, u), value: data.avg_days_by_urgency[u] }))} />
        </section>
        <section className="card pad section">
          <h2>{t("officer.avgByWard")}</h2>
          <Bars rows={data.avg_days_by_ward.map((w) => ({ label: w.name, value: w.avg_days }))} />
        </section>
        <section className="card pad section">
          <h2>{t("officer.topHazards")}</h2>
          {data.top_hazards.length ? <Bars rows={data.top_hazards.map(([h, n]) => ({ label: hazardLabel(t, h), value: n }))} /> : <p className="muted">{t("officer.noData")}</p>}
        </section>
        <section className="card pad section">
          <h2>{t("officer.sla")}</h2>
          <p>{data.sla.resolved ? t("officer.slaValue", { onTime: num(data.sla.on_time), resolved: num(data.sla.resolved), pct: num(data.sla.pct ?? 0) }) : t("officer.noData")}</p>
          <p className={data.sla.open_overdue ? "overdue-text" : "muted"}>{t("officer.openOverdue", { n: num(data.sla.open_overdue) })}</p>
          <h3>{t("officer.aiAccuracy")}</h3>
          <p>{data.ai_accuracy.checked ? t("officer.aiAccuracyValue", { overridden: num(data.ai_accuracy.overridden), checked: num(data.ai_accuracy.checked), pct: num(data.ai_accuracy.agreement_pct ?? 0) }) : t("officer.noData")}</p>
        </section>
      </div>
    </>
  );
}
