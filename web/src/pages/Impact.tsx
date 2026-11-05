import { api } from "../api";
import { PageHead } from "../components/Layout";
import { ActivityFeed } from "../components/Report";
import { ErrorBox, Skeleton, useAsync } from "../components/States";
import { hazardLabel, inr } from "../format";
import { useI18n } from "../i18n";

function Tile({ value, label }: { value: string; label: string }) {
  return <div className="stat"><b>{value}</b><span>{label}</span></div>;
}

export default function Impact() {
  const { t, num } = useI18n();
  const { data: d, error, reload } = useAsync(() => api.impact(14), [], 20000);
  if (!d) {
    return (
      <div className="wrap page">
        <PageHead title={t("impact.title")} />
        {error ? <ErrorBox error={error} retry={reload} /> : <Skeleton h={200} />}
      </div>
    );
  }
  const peak = Math.max(1, ...d.trend.map((x) => Math.max(x.reported, x.resolved)));
  const hazardMax = Math.max(1, ...d.by_hazard.map(([, n]) => n));
  return (
    <div className="wrap page">
      <PageHead title={t("impact.title")} />
      <p className="lead">{t("impact.lead")}</p>

      <div className="stats impact-stats">
        <Tile value={inr(d.open_backlog_inr)} label={t("impact.backlog")} />
        <Tile value={inr(d.repaired_value_inr)} label={t("impact.repaired")} />
        <Tile value={d.avg_hours_to_fix === null ? "–" : num(d.avg_hours_to_fix, 1)} label={t("impact.avgHours")} />
        <Tile value={d.pct_on_time === null ? "–" : `${num(d.pct_on_time)}%`} label={t("impact.onTime")} />
        <Tile value={num(d.citizen_reports)} label={t("impact.citizens")} />
        <Tile value={`${num(d.open)} / ${num(d.fixed)}`} label={t("impact.tickets")} />
      </div>

      <div className="grid cols-2 section">
        <section className="card pad" aria-labelledby="trend-h">
          <h2 id="trend-h">{t("impact.trend", { n: d.trend.length })}</h2>
          <div className="bars" role="img" aria-label={t("impact.trend", { n: d.trend.length })}>
            {d.trend.map((x) => (
              <div key={x.date} className="bar-col" title={`${x.date}: ${x.reported} / ${x.resolved}`}>
                <i className="bar rep" style={{ height: `${(x.reported / peak) * 100}%` }} />
                <i className="bar res" style={{ height: `${(x.resolved / peak) * 100}%` }} />
              </div>
            ))}
          </div>
          <p className="small"><span className="key rep" /> {t("impact.reported")} <span className="key res" /> {t("impact.resolved")}</p>
        </section>

        <section className="card pad" aria-labelledby="haz-h">
          <h2 id="haz-h">{t("impact.hazards")}</h2>
          {d.by_hazard.length === 0 ? <p className="muted">{t("impact.none")}</p> : (
            <ul className="hbars">
              {d.by_hazard.map(([h, n]) => (
                <li key={h}>
                  <span>{hazardLabel(t, h)}</span>
                  <i style={{ width: `${(n / hazardMax) * 100}%` }} />
                  <b className="num">{num(n)}</b>
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <div className="grid cols-2 section">
        <section className="card pad" aria-labelledby="hot-h">
          <h2 id="hot-h">{t("impact.hotspots")}</h2>
          {d.hotspots.length === 0 ? <p className="muted">{t("impact.none")}</p> : (
            <ol className="hot">
              {d.hotspots.map((h) => (
                <li key={h.code}>
                  <b>{h.name}</b>
                  <span className="small muted">{t("impact.hotspotRow", { open: h.open, critical: h.critical, cost: inr(h.cost_inr) })}</span>
                </li>
              ))}
            </ol>
          )}
        </section>
        <section className="card pad" aria-labelledby="act-h">
          <h2 id="act-h">{t("live.title")}</h2>
          <ActivityFeed limit={10} />
        </section>
      </div>
      <p className="small muted">{t("impact.note")}</p>
    </div>
  );
}
