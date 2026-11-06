import { useSearchParams } from "react-router-dom";
import { HAZARDS, URGENCIES } from "../api";
import { hazardLabel, urgencyLabel } from "../format";
import { useI18n } from "../i18n";
import { usePortal } from "../portal";

export const FILTER_KEYS = ["status", "urgency", "hazard", "ward", "from", "to", "overdue"] as const;

/** Filters live in the URL (#/map?status=open&urgency=HIGH), so any view can be shared as a link. */
export function useFilters() {
  const [params, setParams] = useSearchParams();
  const values = Object.fromEntries(FILTER_KEYS.map((k) => [k, params.get(k) ?? ""])) as Record<(typeof FILTER_KEYS)[number], string>;
  const set = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    if (value) next.set(key, value);
    else next.delete(key);
    if (key !== "page") next.delete("page");
    setParams(next, { replace: true });
  };
  const clear = () => {
    const next = new URLSearchParams();
    for (const k of ["sort", "view"]) if (params.get(k)) next.set(k, params.get(k)!);
    setParams(next, { replace: true });
  };
  const apiParams: Record<string, string | boolean> = {};
  for (const k of FILTER_KEYS) if (values[k]) apiParams[k] = k === "overdue" ? true : values[k];
  return { params, values, set, clear, apiParams, active: FILTER_KEYS.some((k) => values[k]) };
}

export function Filters({ f }: { f: ReturnType<typeof useFilters> }) {
  const { t } = useI18n();
  const { config } = usePortal();
  const v = f.values;
  return (
    <details className="card pad filter-box" open={typeof window !== "undefined" && window.innerWidth > 760}>
      <summary>{t("common.filters")}</summary>
      <div className="filters">
        <div className="field">
          <label htmlFor="f-status">{t("filter.status")}</label>
          <select id="f-status" className="input" value={v.status} onChange={(e) => f.set("status", e.target.value)}>
            <option value="">{t("common.all")}</option>
            <option value="open">{t("filter.open")}</option>
            <option value="resolved">{t("filter.resolved")}</option>
            <option value="dismissed">{t("filter.dismissed")}</option>
          </select>
        </div>
        <div className="field">
          <label htmlFor="f-urgency">{t("filter.urgency")}</label>
          <select id="f-urgency" className="input" value={v.urgency} onChange={(e) => f.set("urgency", e.target.value)}>
            <option value="">{t("common.all")}</option>
            {URGENCIES.map((u) => <option key={u} value={u}>{urgencyLabel(t, u)}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="f-hazard">{t("filter.hazard")}</label>
          <select id="f-hazard" className="input" value={v.hazard} onChange={(e) => f.set("hazard", e.target.value)}>
            <option value="">{t("common.all")}</option>
            {HAZARDS.map((h) => <option key={h} value={h}>{hazardLabel(t, h)}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="f-ward">{t("filter.ward")}</label>
          <select id="f-ward" className="input" value={v.ward} onChange={(e) => f.set("ward", e.target.value)}>
            <option value="">{t("common.all")}</option>
            {config?.wards.map((w) => <option key={w.code} value={w.code}>{w.name}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="f-from">{t("filter.from")}</label>
          <input id="f-from" type="date" className="input" value={v.from} onChange={(e) => f.set("from", e.target.value)} />
        </div>
        <div className="field">
          <label htmlFor="f-to">{t("filter.to")}</label>
          <input id="f-to" type="date" className="input" value={v.to} onChange={(e) => f.set("to", e.target.value)} />
        </div>
        <label className="check">
          <input type="checkbox" checked={!!v.overdue} onChange={(e) => f.set("overdue", e.target.checked ? "1" : "")} />
          {t("filter.overdue")}
        </label>
        {f.active && <button className="btn ghost small" onClick={f.clear}>{t("common.clear")}</button>}
      </div>
    </details>
  );
}
