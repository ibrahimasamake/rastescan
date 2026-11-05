import { lazy, Suspense } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { Filters, useFilters } from "../components/Filters";
import { PageHead } from "../components/Layout";
import { ErrorBox, Skeleton, Toast, useAsync, useToast } from "../components/States";
import { useI18n } from "../i18n";
import { PIN_COLOURS } from "../pins";

const MapView = lazy(() => import("../components/MapView"));

function Legend() {
  const { t } = useI18n();
  const items: [string, string][] = [
    [PIN_COLOURS.CRITICAL, t("urgency.CRITICAL")], [PIN_COLOURS.HIGH, t("urgency.HIGH")], [PIN_COLOURS.MEDIUM, t("urgency.MEDIUM")],
    [PIN_COLOURS.LOW, t("urgency.LOW")], [PIN_COLOURS.resolved, t("status.resolved")], [PIN_COLOURS.dismissed, t("status.dismissed")],
  ];
  return (
    <ul className="legend small" aria-label={t("map.legend")} style={{ listStyle: "none", margin: 0, padding: 0 }}>
      {items.map(([c, label]) => (
        <li key={label} style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
          <span aria-hidden="true" style={{ width: 14, height: 14, borderRadius: "50%", background: c, border: "2px solid #fff", boxShadow: "0 0 0 1px #9aa7b6" }} />
          {label}
        </li>
      ))}
    </ul>
  );
}

export default function MapPage() {
  const { t, num } = useI18n();
  const f = useFilters();
  const key = JSON.stringify(f.apiParams);
  const { data, error, loading, reload } = useAsync(() => api.reports({ ...f.apiParams, per_page: 1000, sort: "urgency" }), [key], 60000);
  const [toast, show] = useToast();
  // #/map?present=1 opens the map as a full-screen presentation, for a big screen at an event.
  const present = /[?&]present=1/.test(window.location.hash);
  const noLoc = data ? data.items.filter((r) => r.lat === null).length : 0;
  const share = async () => {
    try {
      await navigator.clipboard.writeText(window.location.href);
      show(t("common.copied"));
    } catch {
      window.prompt(t("common.copyLink"), window.location.href);
    }
  };
  return (
    <div className="wrap page">
      <PageHead title={t("map.title")} lead={t("map.lead")} />
      <Filters f={f} />
      <div className="section-head">
        <p className="muted" aria-live="polite">{data ? t("list.count", { n: num(data.total) }) : t("common.loading")}</p>
        <div className="btn-row">
          <button className="btn outline small" onClick={share}>{t("map.shareFilters")}</button>
          <Link className="btn outline small" to={{ pathname: "/reports", search: f.params.toString() }}>{t("nav.list")}</Link>
        </div>
      </div>
      {!!error && !data && <ErrorBox error={error} retry={reload} />}
      <Suspense fallback={<div className="map-box"><Skeleton h="100%" /></div>}>
        <MapView reports={data?.items ?? []} fit={!loading} tour present={present} />
      </Suspense>
      <Legend />
      {noLoc > 0 && <p className="small muted">{t("map.noLocation", { n: noLoc })}</p>}
      <Toast msg={toast} />
    </div>
  );
}
