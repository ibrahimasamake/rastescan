import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { absUrl, api, type PublicReport } from "../api";
import { DemoBadge, StatusBadge, UrgencyBadge } from "../components/Badges";
import { Filters, useFilters } from "../components/Filters";
import { Icon } from "../components/Icons";
import { PageHead } from "../components/Layout";
import { SeverityMeter } from "../components/Report";
import { Empty, ErrorBox, Skeleton, useAsync } from "../components/States";
import { CLOSED, ago, hazardLabel, inr, sla } from "../format";
import { useI18n } from "../i18n";
import type { Key } from "../i18n/en";

const SORTS = ["newest", "oldest", "urgency", "severity", "due", "reports"] as const;
const PER_PAGE = 24;

/** One report as a photo card: the picture, what the AI found, how bad, when it is due, and what it should cost. */
function Tile({ r, fresh }: { r: PublicReport; fresh: boolean }) {
  const { t, num } = useI18n();
  const clock = sla(t, r.due_at, CLOSED.has(r.status));
  return (
    <Link to={`/r/${r.code}`} className={`card tile ${r.overdue ? "overdue" : ""} ${fresh ? "fresh" : ""}`}>
      <div className="tile-img">
        <img src={absUrl(r.photo_url)} alt="" loading="lazy" decoding="async" />
        <span className="tile-tl"><UrgencyBadge urgency={r.urgency} />{fresh && <span className="badge tile-new">{t("list.new")}</span>}</span>
        <span className="tile-tr" title={t("list.ai")}>AI {num(r.severity, 1)}</span>
        {r.after_photo_url && (
          <span className="tile-after"><img src={absUrl(r.after_photo_url)} alt="" loading="lazy" /><i>{t("list.repaired")}</i></span>
        )}
      </div>
      <div className="body">
        <div className="row"><b>{hazardLabel(t, r.hazard_type)}</b><StatusBadge status={r.public_status} /></div>
        <div className="row small muted"><span><Icon name="pin" size={13} /> {r.ward?.name ? `${r.ward.name} · ${r.code}` : r.code}</span><span>{ago(t, r.created_at)}</span></div>
        {r.repair_recommendation && <p className="small tile-rec" lang="en">{r.repair_recommendation}</p>}
        <SeverityMeter score={r.severity} urgency={r.urgency} />
        <div className="row small">
          <span className={clock?.overdue ? "overdue-text" : "muted"}><Icon name="clock" size={13} /> {clock?.text ?? "–"}</span>
          {r.repair_cost_inr > 0 && <b>{t("list.cost", { amount: inr(r.repair_cost_inr) })}</b>}
        </div>
        <div className="row small muted"><span>{t("tour.people", { n: r.reported_count })}</span>{r.is_demo && <DemoBadge />}</div>
      </div>
    </Link>
  );
}

export default function ListPage() {
  const { t, num } = useI18n();
  const f = useFilters();
  const sort = f.params.get("sort") ?? "newest";
  const page = Math.max(1, Number(f.params.get("page") ?? 1));
  const key = JSON.stringify([f.apiParams, sort, page]);
  const { data, error, loading, reload } = useAsync(() => api.reports({ ...f.apiParams, sort, page, per_page: PER_PAGE }), [key], 15000);
  // Cards that arrive after the first load (a citizen just reported them) are marked "New" until the filters change.
  const seen = useRef<{ key: string; codes: Set<string> } | null>(null);
  const [fresh, setFresh] = useState<Set<string>>(new Set());
  useEffect(() => {
    if (!data) return;
    const codes = data.items.map((r) => r.code);
    if (!seen.current || seen.current.key !== key) {
      seen.current = { key, codes: new Set(codes) };
      setFresh(new Set());
      return;
    }
    const added = codes.filter((c) => !seen.current!.codes.has(c));
    if (added.length) {
      added.forEach((c) => seen.current!.codes.add(c));
      setFresh((f) => new Set([...f, ...added]));
    }
  }, [data, key]);
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
      <p className="muted" aria-live="polite">{data ? t("list.count", { n: num(data.total) }) : t("common.loading")} <span className="live-tag"><i aria-hidden="true" />{t("list.live")}</span></p>
      {loading && !data && <Skeleton h={300} />}
      {!!error && !data && <ErrorBox error={error} retry={reload} />}
      {data && data.items.length === 0 && <Empty>{t("list.empty")}</Empty>}
      {data && data.items.length > 0 && (
        <ul className="tiles" aria-label={t("list.title")}>
          {data.items.map((r) => <li key={r.code}><Tile r={r} fresh={fresh.has(r.code)} /></li>)}
        </ul>
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
