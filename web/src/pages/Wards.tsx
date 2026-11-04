import { Link } from "react-router-dom";
import { api } from "../api";
import { PageHead } from "../components/Layout";
import { ErrorBox, Skeleton, useAsync } from "../components/States";
import { useI18n } from "../i18n";

export default function Wards() {
  const { t, num } = useI18n();
  const { data, error, loading, reload } = useAsync(() => api.wards(), [], 60000);
  return (
    <div className="wrap page">
      <PageHead title={t("wards.title")} lead={t("wards.lead")} />
      {loading && !data && <Skeleton h={260} />}
      {!!error && !data && <ErrorBox error={error} retry={reload} />}
      {data && (
        <div className="table-wrap">
          <table>
            <caption className="sr-only">{t("wards.title")}</caption>
            <thead>
              <tr>
                <th scope="col" className="num">{t("wards.rank")}</th>
                <th scope="col">{t("wards.ward")}</th>
                <th scope="col" className="num">{t("wards.onTime")}</th>
                <th scope="col" className="num">{t("wards.avgDays")}</th>
                <th scope="col" className="num">{t("wards.resolved")}</th>
                <th scope="col" className="num">{t("wards.open")}</th>
                <th scope="col" className="num">{t("wards.overdue")}</th>
              </tr>
            </thead>
            <tbody>
              {data.map((w) => (
                <tr key={w.code} className={w.overdue ? "overdue" : ""}>
                  <td className="num">{w.rank}</td>
                  <th scope="row" style={{ background: "transparent", color: "inherit", fontSize: "inherit" }}>
                    <Link to={`/reports?ward=${w.code}`}>{w.name}</Link>
                  </th>
                  <td className="num">{w.pct_within_deadline === null ? <span className="muted">{t("wards.noData")}</span> : `${num(w.pct_within_deadline)}%`}</td>
                  <td className="num">{w.avg_days_to_resolve === null ? "–" : num(w.avg_days_to_resolve, 1)}</td>
                  <td className="num">{num(w.resolved)}</td>
                  <td className="num">{num(w.open)}</td>
                  <td className={`num ${w.overdue ? "overdue-text" : ""}`}>{num(w.overdue)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <p className="small muted">{t("wards.sample")}</p>
    </div>
  );
}
