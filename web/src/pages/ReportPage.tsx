import { Fragment, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useAddress } from "../address";
import { api, ApiError, type PublicDetail } from "../api";
import { DemoBadge, StatusBadge, UrgencyBadge } from "../components/Badges";
import { Icon } from "../components/Icons";
import { PageHead } from "../components/Layout";
import { BeforeAfter, DetectionList, PhotoWithBox, SeverityMeter, Timeline } from "../components/Report";
import { ErrorBox, Skeleton, Toast, useAsync, useToast } from "../components/States";
import { CLOSED, deviceId, hazardLabel, inr, sla } from "../format";
import { useI18n } from "../i18n";
import type { Key } from "../i18n/en";

function ShareButtons({ code, title }: { code: string; title: string }) {
  const { t } = useI18n();
  const [toast, show] = useToast();
  const url = window.location.href.split("#")[0] + `#/r/${code}`;
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      show(t("common.copied"));
    } catch {
      window.prompt(t("common.copyLink"), url);
    }
  };
  const native = async () => {
    try {
      await navigator.share({ title, url });
    } catch {
      /* cancelled */
    }
  };
  return (
    <div className="btn-row">
      <a className="btn outline small" href={`https://wa.me/?text=${encodeURIComponent(`${title} ${url}`)}`} target="_blank" rel="noreferrer">
        {t("common.whatsapp")}
      </a>
      <button className="btn outline small" onClick={copy}>{t("common.copyLink")}</button>
      {"share" in navigator && <button className="btn outline small" onClick={native}><Icon name="share" /> {t("common.share")}</button>}
      <Toast msg={toast} />
    </div>
  );
}

function SeeToo({ r, onCount }: { r: PublicDetail; onCount: (n: number) => void }) {
  const { t } = useI18n();
  const [msg, setMsg] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const click = async () => {
    setBusy(true);
    try {
      const res = await api.vote(r.code, deviceId());
      onCount(res.reported_count);
      setMsg(res.added ? t("report.seeTooDone", { n: res.reported_count }) : t("report.seeTooAlready"));
    } catch (e) {
      setMsg(e instanceof ApiError && e.status === 409 ? e.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="card pad section">
      <button className="btn accent" onClick={click} disabled={busy || !!msg}><Icon name="eye" /> {t("report.seeToo")}</button>
      <p className="small muted" aria-live="polite">{msg ?? t("report.seeTooHint")}</p>
    </div>
  );
}

export default function ReportPage() {
  const { code = "" } = useParams();
  const { t, num, date } = useI18n();
  const { data: r, error, loading, reload, setData } = useAsync(() => api.report(code), [code], 30000);
  const addr = useAddress(code, r?.address);

  if (loading && !r) {
    return (
      <div className="wrap page">
        <Skeleton h={40} w="50%" />
        <div className="report-grid"><Skeleton h={320} /><Skeleton h={320} /></div>
      </div>
    );
  }
  if (!r) {
    return (
      <div className="wrap page">
        {error instanceof ApiError && error.status === 404
          ? <div className="empty"><p>{t("report.notFound", { code: code.toUpperCase() })}</p><Link to="/map">{t("home.browse")}</Link></div>
          : <ErrorBox error={error} retry={reload} />}
      </div>
    );
  }

  const closed = CLOSED.has(r.status);
  const clock = sla(t, r.due_at, closed);
  const hazard = hazardLabel(t, r.hazard_type);
  const res = r.result;
  const after = r.after_result;
  const afterText = after ? t("report.afterCheck", {
    result: after.hazard_type === "None" || r.public_status === "resolved"
      ? t("report.afterClean")
      : t("report.afterStill", { hazard: hazardLabel(t, after.hazard_type).toLowerCase(), n: after.severity_score.toFixed(1) }),
  }) : null;

  return (
    <div className="wrap page">
      <PageHead title={`${hazard} · ${r.code}`}>
        <div className="status-head">
          <StatusBadge status={r.public_status} big />
          <UrgencyBadge urgency={r.urgency} big />
          {clock && <span className={clock.overdue ? "overdue-text" : "muted"}><Icon name="clock" /> {clock.text}</span>}
          {r.is_demo && <DemoBadge />}
        </div>
      </PageHead>

      {r.merged_into && <p className="notice card pad">{t("report.mergedInto", { code: r.merged_into })} <Link to={`/r/${r.merged_into}`}>{r.merged_into}</Link></p>}
      {r.public_status === "dismissed" && r.dismiss_reason && <p className="card pad">{t("report.dismissReason", { reason: r.dismiss_reason })}</p>}

      <div className="report-grid">
        <div className="section">
          {r.after_photo_url ? (
            <>
              <BeforeAfter before={r.photo_url} after={r.after_photo_url} code={r.code} />
              {afterText && <p className={r.public_status === "resolved" ? "ok-text" : "overdue-text"}>{afterText}</p>}
            </>
          ) : (
            <PhotoWithBox src={r.photo_url} result={res} urgency={r.urgency} alt={t("report.photoAlt", { hazard, code: r.code })} />
          )}
          {!closed && <SeeToo r={r} onCount={(n) => setData({ ...r, reported_count: n })} />}
          <ShareButtons code={r.code} title={`${hazard} · ${r.code}`} />
        </div>

        <div className="section">
          <section className="card pad section" aria-labelledby="sum-h">
            <h2 id="sum-h">{t("report.summary")}</h2>
            <dl className="facts">
              <dt>{t("report.hazard")}</dt><dd>{hazard}</dd>
              <dt>{t("report.severity")}</dt>
              <dd>{t("report.severityValue", { n: num(r.severity, 1) })}<SeverityMeter score={r.severity} urgency={r.urgency} /></dd>
              <dt>{t("report.ward")}</dt><dd>{r.ward?.name ?? "–"}</dd>
              {addr?.pin && <><dt>{t("report.pin")}</dt><dd className="num"><b>{addr.pin}</b></dd></>}
              {addr?.state && <><dt>{t("report.state")}</dt><dd>{addr.state}</dd></>}
              {addr?.district && <><dt>{t("report.district")}</dt><dd>{addr.district}</dd></>}
              {addr?.city && <><dt>{t("report.city")}</dt><dd>{addr.city}</dd></>}
              {addr?.area && <><dt>{t("report.area")}</dt><dd>{addr.area}</dd></>}
              {addr?.road && <><dt>{t("report.road")}</dt><dd>{addr.road}</dd></>}
              {r.lat !== null && r.lng !== null && <><dt>{t("report.coords")}</dt><dd className="num">{r.lat.toFixed(5)}, {r.lng.toFixed(5)}</dd></>}
              <dt>{t("report.location")}</dt>
              <dd>{r.lat !== null && r.lng !== null
                ? <a href={`https://www.openstreetmap.org/?mlat=${r.lat}&mlon=${r.lng}#map=18/${r.lat}/${r.lng}`} target="_blank" rel="noreferrer">{t("report.openMap")}</a>
                : "–"}</dd>
              <dt>{t("report.reportedOn")}</dt><dd>{date(r.created_at, true)}</dd>
              {r.due_at && <><dt>{t("report.deadline")}</dt><dd>{date(r.due_at, true)}</dd></>}
              <dt>{t("report.assignee")}</dt><dd>{r.assignee ?? t("report.notAssigned")}</dd>
              <dt>{t("report.citizens")}</dt><dd className="num">{num(r.reported_count)}</dd>
              {res.hazard_type !== "None" && (
                <>
                  <dt>{t("report.size")}</dt>
                  <dd>{t("report.sizeValue", { cm: res.estimated_dimensions.width_cm, depth: t(`depth.${res.estimated_dimensions.depth_category}` as Key) })}</dd>
                  <dt>{t("report.repairTime")}</dt><dd>{t("report.hoursValue", { n: res.estimated_repair_time_hours })}</dd>
                </>
              )}
              <dt>{t("report.confidence")}</dt><dd className="num">{num(Math.round(r.confidence * 100))}%</dd>
            </dl>
            <div className="section">
              <h3>{t("report.recommendation")}</h3>
              <p className="rec" lang="en">{res.repair_recommendation}</p>
            </div>
            <DetectionList result={res} />
            {r.repair_estimate.total_inr > 0 && (
              <div className="section cost-card">
                <h3>{t("cost.title")}</h3>
                <p className="cost-total">{t("cost.total", { amount: inr(r.repair_estimate.total_inr) })}</p>
                <dl className="facts">
                  {r.repair_estimate.lines.map((l) => (
                    <Fragment key={l.item}><dt>{l.item} ({num(l.qty, 2)} {l.unit})</dt><dd className="num">{inr(l.cost_inr)}</dd></Fragment>
                  ))}
                  <dt>{t("cost.labour", { n: r.repair_estimate.crew_hours })}</dt><dd className="num">{inr(r.repair_estimate.labour_inr)}</dd>
                </dl>
                <p className="small muted">{t("cost.note")}</p>
              </div>
            )}
          </section>

          <section className="card pad section" aria-labelledby="tl-h">
            <h2 id="tl-h">{t("report.timeline")}</h2>
            <Timeline events={r.timeline} />
          </section>
        </div>
      </div>
    </div>
  );
}
