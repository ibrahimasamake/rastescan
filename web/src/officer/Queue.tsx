import { lazy, Suspense, useState } from "react";
import { officerApi, URGENCIES, type Report, type Status } from "../api";
import { StatusBadge, UrgencyBadge } from "../components/Badges";
import { Modal } from "../components/Modal";
import { Empty, ErrorBox, Skeleton, Toast, useAsync, useToast } from "../components/States";
import { CLOSED, ago, hazardLabel, sla, urgencyLabel } from "../format";
import { useI18n } from "../i18n";
import type { Key } from "../i18n/en";
import { usePortal } from "../portal";
import { ReportPanel } from "./Panel";
import { OfficerShell } from "./Shell";

const MapView = lazy(() => import("../components/MapView"));

function QueueTable({ rows, selected, onSelect, checked, setChecked }: {
  rows: Report[]; selected: string | null; onSelect: (c: string) => void; checked: Set<string>; setChecked: (s: Set<string>) => void;
}) {
  const { t } = useI18n();
  const toggle = (code: string) => {
    const next = new Set(checked);
    if (next.has(code)) next.delete(code);
    else next.add(code);
    setChecked(next);
  };
  const all = rows.length > 0 && rows.every((r) => checked.has(r.code));
  return (
    <div className="table-wrap">
      <table>
        <caption className="sr-only">{t("officer.queue")}</caption>
        <thead>
          <tr>
            <th scope="col"><input type="checkbox" aria-label={t("officer.selectAll")} checked={all} onChange={() => setChecked(all ? new Set() : new Set(rows.map((r) => r.code)))} /></th>
            <th scope="col">{t("list.code")}</th>
            <th scope="col">{t("filter.hazard")}</th>
            <th scope="col">{t("filter.urgency")}</th>
            <th scope="col">{t("filter.ward")}</th>
            <th scope="col">{t("list.age")}</th>
            <th scope="col">{t("report.deadline")}</th>
            <th scope="col">{t("report.assignee")}</th>
            <th scope="col">{t("list.status")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => {
            const clock = sla(t, r.due_at, CLOSED.has(r.status));
            return (
              <tr key={r.code} className={`clickable ${r.overdue ? "overdue" : ""} ${selected === r.code ? "sel" : ""}`} onClick={() => onSelect(r.code)}>
                <td onClick={(e) => e.stopPropagation()}>
                  <input type="checkbox" aria-label={t("officer.select", { code: r.code })} checked={checked.has(r.code)} onChange={() => toggle(r.code)} />
                </td>
                <td className="nowrap"><button className="link-btn" onClick={() => onSelect(r.code)} aria-pressed={selected === r.code}>{r.code}</button></td>
                <td>{hazardLabel(t, r.hazard_type)}</td>
                <td><UrgencyBadge urgency={r.urgency} /></td>
                <td>{r.ward?.name ?? "–"}</td>
                <td>{ago(t, r.created_at)}</td>
                <td className={clock?.overdue ? "overdue-text" : ""}>{clock?.text ?? "–"}</td>
                <td>{r.assignee ?? "–"}</td>
                <td><StatusBadge status={r.public_status} /></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function Queue() {
  return <OfficerShell><QueueBody /></OfficerShell>;
}

function QueueBody() {
  const { t, num } = useI18n();
  const { config } = usePortal();
  const [ward, setWard] = useState("");
  const [urgency, setUrgency] = useState("");
  const [q, setQ] = useState("");
  const [overdue, setOverdue] = useState(false);
  const [view, setView] = useState<"list" | "map">("list");
  const [selected, setSelected] = useState<string | null>(null);
  const [checked, setChecked] = useState<Set<string>>(new Set());
  const [bulk, setBulk] = useState<Status>("assigned");
  const [toast, show] = useToast();
  const key = JSON.stringify([ward, urgency, q, overdue]);
  const queue = useAsync(() => officerApi.queue({ ward, urgency, q, overdue }), [key], 15000);
  const assignees = useAsync(() => officerApi.assignees(), []);
  const reloadAll = () => { queue.reload(); assignees.reload(); };

  const applyBulk = async () => {
    const reason = bulk === "dismissed" ? window.prompt(t("officer.dismissReason")) ?? "" : undefined;
    if (bulk === "dismissed" && !reason) return;
    try {
      const r = await officerApi.bulkStatus([...checked], bulk, reason);
      show(`${t("officer.done")} (${r.updated})`);
      setChecked(new Set());
      queue.reload();
    } catch {
      show(t("common.error"));
    }
  };

  const d = queue.data;
  return (
    <>
      <p className="muted">{t("officer.queueLead")}</p>
      {d && (
        <div className="btn-row" aria-live="polite">
          {URGENCIES.map((u) => <span key={u} className={`badge u-${u}`}>{num(d.counts[u])} {urgencyLabel(t, u)}</span>)}
          <span className="badge s-reported">{num(d.overdue)} {t("stat.overdue")}</span>
          <span className="badge s-resolved">{num(d.verified)} {t("status.resolved")}</span>
        </div>
      )}
      <div className="filters card pad">
        <div className="field">
          <label htmlFor="q">{t("officer.searchCode")}</label>
          <input id="q" className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="RS-0012" />
        </div>
        <div className="field">
          <label htmlFor="qw">{t("filter.ward")}</label>
          <select id="qw" className="input" value={ward} onChange={(e) => setWard(e.target.value)}>
            <option value="">{t("officer.allWards")}</option>
            {config?.wards.map((w) => <option key={w.code} value={w.code}>{w.name}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="qu">{t("filter.urgency")}</label>
          <select id="qu" className="input" value={urgency} onChange={(e) => setUrgency(e.target.value)}>
            <option value="">{t("common.all")}</option>
            {URGENCIES.map((u) => <option key={u} value={u}>{urgencyLabel(t, u)}</option>)}
          </select>
        </div>
        <label className="check"><input type="checkbox" checked={overdue} onChange={(e) => setOverdue(e.target.checked)} /> {t("officer.overdueOnly")}</label>
        <div className="btn-row" role="group">
          <button className="btn small outline" aria-pressed={view === "list"} onClick={() => setView("list")}>{t("officer.listView")}</button>
          <button className="btn small outline" aria-pressed={view === "map"} onClick={() => setView("map")}>{t("officer.mapView")}</button>
        </div>
      </div>
      {checked.size > 0 && (
        <div className="card pad btn-row" style={{ alignItems: "end" }}>
          <div className="field">
            <label htmlFor="bulk">{t("officer.bulk", { n: checked.size })}</label>
            <select id="bulk" className="input" value={bulk} onChange={(e) => setBulk(e.target.value as Status)}>
              {(["assigned", "fixed", "verified", "dismissed"] as const).map((s) => (
                <option key={s} value={s}>{t(`status.${({ assigned: "assigned", fixed: "repair_done", verified: "resolved", dismissed: "dismissed" } as const)[s]}` as Key)}</option>
              ))}
            </select>
          </div>
          <button className="btn small" onClick={applyBulk}>{t("common.apply")}</button>
        </div>
      )}
      {queue.loading && !d && <Skeleton h={300} />}
      {!!queue.error && !d && <ErrorBox error={queue.error} retry={queue.reload} />}
      {d && (
        <div className="section">
          {d.tickets.length === 0 ? <Empty>{t("officer.emptyQueue")}</Empty> : view === "list" ? (
            <>
              <p className="small muted">{t("officer.selectHint")}</p>
              <QueueTable rows={d.tickets} selected={selected} onSelect={setSelected} checked={checked} setChecked={setChecked} />
            </>
          ) : (
            <Suspense fallback={<Skeleton h={400} />}><MapView reports={d.tickets} /></Suspense>
          )}
        </div>
      )}
      {selected && (
        <Modal title={selected} onClose={() => setSelected(null)}>
          <ReportPanel key={selected} code={selected} assignees={assignees.data ?? []} onChange={reloadAll} />
        </Modal>
      )}
      <Toast msg={toast} />
    </>
  );
}
