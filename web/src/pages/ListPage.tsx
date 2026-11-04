import { Link } from "react-router-dom";
import { api } from "../api";
import { DemoBadge, StatusBadge, UrgencyBadge } from "../components/Badges";
import { Filters, useFilters } from "../components/Filters";
import { Icon } from "../components/Icons";
import { PageHead } from "../components/Layout";
import { Empty, ErrorBox, Skeleton, useAsync } from "../components/States";
import { CLOSED, ago, hazardLabel, sla } from "../format";
import { useI18n } from "../i18n";
import type { Key } from "../i18n/en";

const SORTS = ["newest", "oldest", "urgency", "severity", "due", "reports"] as const;
const PER_PAGE = 25;

export default function ListPage() {
  const { t, num, date } = useI18n();
  const f = useFilters();
  const sort = f.params.get("sort") ?? "newest";
  const page = Math.max(1, Number(f.params.get("page") ?? 1));
  const key = JSON.stringify([f.apiParams, sort, page]);
  const { data, error, loading, reload } = useAsync(() => api.reports({ ...f.apiParams, sort, page, per_page: PER_PAGE }), [key], 60000);
  const pages = data ? Math.max(1, Math.ceil(data.total / PER_PAGE)) : 1;

  return (
    <div className="wrap page">
      <PageHead title={t("list.title")} lead={t("list.lead")} />
      <Filters f={f} />
      <div className="section-head">
        <div className="field" style={{ maxWidth: 260 }}>
          <label htmlFor="sort">{t("list.sort")}</label>
          <select id="sort" className="input" value={sort} onChange={(e) => f.set("sort", e.target.value)}>
            {SORTS.map((s) => <option key={s} value={s}>{t(`sort.${s}` as Key)}</option>)}
          </select>
        </div>
        <div className="btn-row">
          <Link className="btn outline small" to={{ pathname: "/map", search: f.params.toString() }}><Icon name="map" /> {t("nav.map")}</Link>
          <a className="btn small" href={api.exportUrl({ ...f.apiParams, sort })} download><Icon name="down" /> {t("list.csv")}</a>
        </div>
      </div>
      <p className="muted" aria-live="polite">{data ? t("list.count", { n: num(data.total) }) : t("common.loading")}</p>
      {loading && !data && <Skeleton h={300} />}
      {!!error && !data && <ErrorBox error={error} retry={reload} />}
      {data && data.items.length === 0 && <Empty>{t("list.empty")}</Empty>}
      {data && data.items.length > 0 && (
        <div className="table-wrap">
          <table>
            <caption className="sr-only">{t("list.title")}</caption>
            <thead>
              <tr>
                <th scope="col">{t("list.code")}</th>
                <th scope="col">{t("filter.hazard")}</th>
                <th scope="col">{t("filter.urgency")}</th>
                <th scope="col">{t("list.status")}</th>
                <th scope="col">{t("filter.ward")}</th>
                <th scope="col">{t("list.reported")}</th>
                <th scope="col">{t("report.deadline")}</th>
                <th scope="col" className="num">{t("report.citizens")}</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((r) => {
                const clock = sla(t, r.due_at, CLOSED.has(r.status));
                return (
                  <tr key={r.code} className={r.overdue ? "overdue" : ""}>
                    <td><Link to={`/r/${r.code}`}>{r.code}</Link> {r.is_demo && <DemoBadge />}</td>
                    <td>{hazardLabel(t, r.hazard_type)}</td>
                    <td><UrgencyBadge urgency={r.urgency} /></td>
                    <td><StatusBadge status={r.public_status} /></td>
                    <td>{r.ward?.name ?? "–"}</td>
                    <td title={date(r.created_at, true)}>{ago(t, r.created_at)}</td>
                    <td className={clock?.overdue ? "overdue-text" : ""}>{clock?.text ?? "–"}</td>
                    <td className="num">{num(r.reported_count)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {data && pages > 1 && (
        <nav className="pager" aria-label={t("common.page", { page, pages })}>
          <button className="btn outline small" disabled={page <= 1} onClick={() => f.set("page", String(page - 1))}>{t("common.previous")}</button>
          <span>{t("common.page", { page, pages })}</span>
          <button className="btn outline small" disabled={page >= pages} onClick={() => f.set("page", String(page + 1))}>{t("common.next")}</button>
        </nav>
      )}
    </div>
  );
}
