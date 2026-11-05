import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Icon } from "../components/Icons";
import { ActivityFeed, ReportCard } from "../components/Report";
import { Empty, Skeleton, useAsync } from "../components/States";
import { useI18n } from "../i18n";
import { usePortal } from "../portal";

const MapView = lazy(() => import("../components/MapView"));

function Stat({ value, label, warn = false }: { value: string | null; label: string; warn?: boolean }) {
  return (
    <div className={`stat ${warn ? "warn" : ""}`}>
      {value === null ? <Skeleton h={30} w="60%" /> : <b>{value}</b>}
      <span>{label}</span>
    </div>
  );
}

/** Renders children only once the box scrolls near the screen, so the map code is not loaded up front. */
function WhenVisible({ children, fallback }: { children: React.ReactNode; fallback: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    if (!ref.current || !("IntersectionObserver" in window)) {
      setSeen(true);
      return;
    }
    const io = new IntersectionObserver((e) => e.some((x) => x.isIntersecting) && setSeen(true), { rootMargin: "200px" });
    io.observe(ref.current);
    return () => io.disconnect();
  }, []);
  return <div ref={ref}>{seen ? children : fallback}</div>;
}

export default function Home() {
  const { t, num } = useI18n();
  const { stats } = usePortal();
  const open = useAsync(() => api.reports({ status: "open", per_page: 300, sort: "urgency" }), [], 60000);
  const resolved = useAsync(() => api.recentlyResolved(), [], 30000);
  const wards = useAsync(() => api.wards(), []);
  const s = stats;
  return (
    <>
      <section className="hero">
        <div className="wrap">
          <div className="hero-text">
            <h1>{t("home.title")}</h1>
            <p className="lead">{t("home.lead")}</p>
            <div className="btn-row">
              <Link to="/report" className="btn accent big"><Icon name="camera" size={22} /> {t("home.cta")}</Link>
            </div>
            <p className="small muted">{t("home.ctaHint")}</p>
            <Link to="/map">{t("home.browse")}</Link>
          </div>
          <section aria-labelledby="live">
            <h2 id="live" className="sr-only">{t("home.stats")}</h2>
            <div className="stats" aria-live="polite">
              <Stat value={s ? num(s.reported_today) : null} label={t("stat.today")} />
              <Stat value={s ? num(s.open_now) : null} label={t("stat.open")} />
              <Stat value={s ? num(s.overdue_now) : null} label={t("stat.overdue")} warn={!!s?.overdue_now} />
              <Stat value={s ? num(s.resolved_this_month) : null} label={t("stat.resolvedMonth")} />
              <Stat value={s ? (s.avg_days_to_fix === null ? "–" : num(s.avg_days_to_fix, 1)) : null} label={t("stat.avgDays")} />
            </div>
          </section>
        </div>
      </section>

      <div className="wrap page">
        <section className="section" aria-labelledby="map-h">
          <div className="section-head">
            <h2 id="map-h">{t("home.mapTitle")}</h2>
            <Link to="/map">{t("home.mapLink")}</Link>
          </div>
          <WhenVisible fallback={<div className="map-box short" />}>
            <Suspense fallback={<div className="map-box short"><Skeleton h="100%" /></div>}>
              <MapView reports={open.data?.items ?? []} short />
            </Suspense>
          </WhenVisible>
        </section>

        <section className="section" aria-labelledby="live-h">
          <h2 id="live-h">{t("live.title")}</h2>
          <ActivityFeed />
        </section>

        <section className="section" aria-labelledby="resolved-h">
          <h2 id="resolved-h">{t("home.resolvedTitle")}</h2>
          {resolved.loading && !resolved.data ? (
            <div className="hscroll">{[0, 1, 2].map((i) => <Skeleton key={i} h={220} />)}</div>
          ) : resolved.data?.length ? (
            <div className="hscroll">{resolved.data.map((r) => <ReportCard key={r.code} r={r} />)}</div>
          ) : (
            <Empty>{t("home.resolvedEmpty")}</Empty>
          )}
        </section>

        <section className="section" aria-labelledby="how-h">
          <h2 id="how-h">{t("home.howTitle")}</h2>
          <ol className="steps">
            <li><h3>{t("home.step1")}</h3><p>{t("home.step1Text")}</p></li>
            <li><h3>{t("home.step2")}</h3><p>{t("home.step2Text")}</p></li>
            <li><h3>{t("home.step3")}</h3><p>{t("home.step3Text")}</p></li>
          </ol>
        </section>

        {wards.data && wards.data.length > 0 && (
          <section className="section" aria-labelledby="wards-h">
            <div className="section-head">
              <h2 id="wards-h">{t("home.wardsTitle")}</h2>
              <Link to="/wards">{t("home.wardsLink")}</Link>
            </div>
            <ol className="grid cols-3" style={{ listStyle: "none", padding: 0, margin: 0 }}>
              {wards.data.slice(0, 3).map((w) => (
                <li key={w.code} className="card pad">
                  <h3>{w.rank}. {w.name}</h3>
                  <p className="small muted">
                    {w.pct_within_deadline === null ? t("wards.noData") : `${t("wards.onTime")}: ${num(w.pct_within_deadline)}%`}
                    {" · "}{t("wards.open")}: {num(w.open)}
                  </p>
                </li>
              ))}
            </ol>
          </section>
        )}
      </div>
    </>
  );
}
