import { useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { API_BASE, api } from "../api";
import { PageHead } from "../components/Layout";
import { useI18n } from "../i18n";

export function About() {
  const { t } = useI18n();
  const loc = useLocation();
  useEffect(() => {
    if (loc.hash === "#how") document.getElementById("how")?.scrollIntoView();
  }, [loc.hash]);
  return (
    <div className="wrap page narrow">
      <PageHead title={t("about.title")} />
      <p>{t("about.body")}</p>
      <section id="how" className="section">
        <h2>{t("how.title")}</h2>
        <ol className="steps">
          <li><h3>{t("home.step1")}</h3><p>{t("home.step1Text")}</p></li>
          <li><h3>{t("home.step2")}</h3><p>{t("home.step2Text")}</p></li>
          <li><h3>{t("home.step3")}</h3><p>{t("home.step3Text")}</p></li>
        </ol>
        <p>{t("how.ai")}</p>
      </section>
    </div>
  );
}

export function Privacy() {
  const { t } = useI18n();
  return (
    <div className="wrap page narrow">
      <PageHead title={t("privacy.title")} />
      <p>{t("privacy.body1")}</p>
      <p>{t("privacy.body2")}</p>
      <p>{t("privacy.body3")}</p>
    </div>
  );
}

export function Accessibility() {
  const { t } = useI18n();
  return (
    <div className="wrap page narrow">
      <PageHead title={t("a11y.title")} />
      <p>{t("a11y.body1")}</p>
      <p>{t("a11y.body2")}</p>
      <p>{t("a11y.body3")}</p>
    </div>
  );
}

const ENDPOINTS: [string, string][] = [
  ["GET /api/public/reports", "?status=open|resolved|dismissed&urgency=CRITICAL,HIGH&hazard=Pothole&ward=W02&from=2026-11-01&to=2026-11-30&overdue=true&bbox=min_lng,min_lat,max_lng,max_lat&sort=newest|urgency|due|severity|reports&page=1&per_page=50"],
  ["GET /api/public/reports/{code}", "Report with its full public timeline and official updates"],
  ["GET /api/public/stats", "Live counters shown on the home page"],
  ["GET /api/public/wards", "Ward scoreboard"],
  ["GET /api/public/recently-resolved", "Latest repairs with before and after photos"],
  ["GET /api/public/export.csv", "Same filters as /reports, as CSV"],
];

export function OpenData() {
  const { t } = useI18n();
  const base = API_BASE || window.location.origin;
  return (
    <div className="wrap page narrow">
      <PageHead title={t("data.title")} lead={t("data.lead")} />
      <p><a className="btn" href={api.exportUrl({})} download>{t("data.csv")}</a></p>
      <section className="section">
        <h2>{t("data.endpoints")}</h2>
        <div className="table-wrap">
          <table>
            <tbody>
              {ENDPOINTS.map(([path, desc]) => (
                <tr key={path}><td><code>{path}</code></td><td className="small" lang="en" style={{ overflowWrap: "anywhere" }}>{desc}</td></tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="small muted">{base}</p>
        <p>{t("data.note")}</p>
        <p>{t("data.licence")}</p>
      </section>
    </div>
  );
}

export function NotFound() {
  const { t } = useI18n();
  return (
    <div className="wrap page">
      <div className="empty"><p>{t("common.notFound")}</p><Link to="/">{t("common.goHome")}</Link></div>
    </div>
  );
}
