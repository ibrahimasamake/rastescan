import { useSearchParams } from "react-router-dom";
import { officerApi } from "../api";
import { UrgencyBadge } from "../components/Badges";
import { Empty, ErrorBox, Skeleton, useAsync } from "../components/States";
import { hazardLabel } from "../format";
import { useI18n } from "../i18n";
import { OfficerShell } from "./Shell";

export default function WorkOrder() {
  return <OfficerShell><WorkOrderBody /></OfficerShell>;
}

/** A crew's day: open reports assigned to them, in nearest-neighbour order, ready to print. */
function WorkOrderBody() {
  const { t, num, date } = useI18n();
  const [params, setParams] = useSearchParams();
  const crew = params.get("crew") ?? "";
  const assignees = useAsync(() => officerApi.assignees(), []);
  const order = useAsync(() => (crew ? officerApi.workOrder(crew) : Promise.resolve(null)), [crew]);
  return (
    <>
      <div className="filters no-print">
        <div className="field">
          <label htmlFor="crew">{t("officer.chooseCrew")}</label>
          <select id="crew" className="input" value={crew} onChange={(e) => setParams(e.target.value ? { crew: e.target.value } : {}, { replace: true })}>
            <option value="">–</option>
            {assignees.data?.map((a) => <option key={a} value={a}>{a}</option>)}
          </select>
        </div>
        {order.data && order.data.stops.length > 0 && <button className="btn small" onClick={() => window.print()}>{t("officer.printOrder")}</button>}
      </div>
      {crew && order.loading && !order.data && <Skeleton h={240} />}
      {!!order.error && <ErrorBox error={order.error} retry={order.reload} />}
      {order.data && (
        <section className="section">
          <h2>{t("officer.workOrderFor", { name: order.data.assignee })}</h2>
          <p className="muted">{date(order.data.generated_at, true)}</p>
          {order.data.stops.length === 0 ? <Empty>{t("officer.noStops")}</Empty> : (
            <>
              <p>{t("officer.workOrderLead", { km: num(order.data.total_km, 1), hours: num(order.data.total_hours) })}</p>
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th className="num">{t("officer.stop")}</th><th>{t("list.code")}</th><th>{t("report.hazard")}</th><th>{t("filter.urgency")}</th>
                      <th>{t("report.location")}</th><th className="num">{t("officer.leg")}</th><th>{t("report.recommendation")}</th><th>{t("report.deadline")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {order.data.stops.map((s, i) => (
                      <tr key={s.code} className={s.overdue ? "overdue" : ""}>
                        <td className="num">{i + 1}</td>
                        <td className="nowrap">{s.code}</td>
                        <td>{hazardLabel(t, s.hazard_type)}</td>
                        <td><UrgencyBadge urgency={s.urgency} /></td>
                        <td>{s.lat !== null ? <a href={`https://www.google.com/maps?q=${s.lat},${s.lng}`}>{s.ward?.name ?? ""} {s.lat.toFixed(5)}, {s.lng?.toFixed(5)}</a> : "–"}</td>
                        <td className="num">{s.leg_m === null ? "–" : t("common.km", { n: num(s.leg_m / 1000, 1) })}</td>
                        <td className="small" lang="en">{s.repair_recommendation}</td>
                        <td>{s.due_at ? date(s.due_at, true) : "–"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}
        </section>
      )}
    </>
  );
}
