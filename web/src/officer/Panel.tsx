import { useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, HAZARDS, officerApi, type OfficerReport, type Status } from "../api";
import { StatusBadge, UrgencyBadge } from "../components/Badges";
import { BeforeAfter, PhotoWithBox } from "../components/Report";
import { ErrorBox, Skeleton, Toast, useAsync, useToast } from "../components/States";
import { CLOSED, hazardLabel, sla } from "../format";
import { useI18n } from "../i18n";
import type { Key } from "../i18n/en";
import { shrinkPhoto } from "../photo";

/** Everything an officer can do to one report. Every action is written to the public history. */
export function ReportPanel({ code, assignees, onChange }: { code: string; assignees: string[]; onChange: () => void }) {
  const { t, num, date } = useI18n();
  const { data: r, error, loading, reload } = useAsync(() => officerApi.report(code), [code]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [toast, show] = useToast();
  const [assignee, setAssignee] = useState("");
  const [reason, setReason] = useState("");
  const [comment, setComment] = useState("");
  const [mergeInto, setMergeInto] = useState("");
  const [hazard, setHazard] = useState("");
  const [severity, setSeverity] = useState("");
  const fileRef = useRef<HTMLInputElement>(null);

  if (loading && !r) return <Skeleton h={400} />;
  if (!r) return <ErrorBox error={error} retry={reload} />;

  const act = async (fn: () => Promise<unknown>, done: string | undefined = t("officer.done")) => {
    setBusy(true);
    setErr(null);
    try {
      await fn();
      if (done) show(done);
      reload();
      onChange();
      return true;
    } catch (e) {
      setErr(e instanceof ApiError ? e.message : t("common.error"));
      return false;
    } finally {
      setBusy(false);
    }
  };
  const status = (s: Status, why?: string) => act(() => officerApi.status(r.code, s, why));
  const clock = sla(t, r.due_at, CLOSED.has(r.status));
  const open = ["new", "assigned", "fixed", "review"].includes(r.status);
  const res = r.result;

  return (
    <section className="card pad section" aria-labelledby="panel-h">
      <div className="status-head">
        <h2 id="panel-h"><Link to={`/r/${r.code}`}>{r.code}</Link></h2>
        {r.status === "review" ? <span className="badge s-reported">{t("status.review")}</span> : <StatusBadge status={r.public_status} />}
        <UrgencyBadge urgency={r.urgency} />
        {clock && <span className={clock.overdue ? "overdue-text" : "muted small"}>{clock.text}</span>}
      </div>
      {r.after_photo_url ? <BeforeAfter before={r.photo_url} after={r.after_photo_url} code={r.code} />
        : <PhotoWithBox src={r.photo_url} result={res} urgency={r.urgency} alt={t("report.photoAlt", { hazard: hazardLabel(t, r.hazard_type), code: r.code })} />}

      <dl className="facts">
        <dt>{t("report.hazard")}</dt><dd>{hazardLabel(t, r.hazard_type)} · {t("report.severityValue", { n: num(r.severity, 1) })}</dd>
        <dt>{t("report.ward")}</dt><dd>{r.ward?.name ?? "–"}</dd>
        <dt>{t("report.assignee")}</dt><dd>{r.assignee ?? t("report.notAssigned")}</dd>
        <dt>{t("report.citizens")}</dt><dd>{num(r.reported_count)}</dd>
        {r.note && <><dt>{t("officer.note")}</dt><dd>{r.note}</dd></>}
        {r.lat !== null && <><dt>{t("report.location")}</dt><dd><a href={`https://www.google.com/maps?q=${r.lat},${r.lng}`} target="_blank" rel="noreferrer">{r.lat.toFixed(5)}, {r.lng?.toFixed(5)}</a></dd></>}
        {r.duplicates.length > 0 && <><dt>{t("officer.duplicates")}</dt><dd>{r.duplicates.join(", ")}</dd></>}
      </dl>
      <p className="rec small" lang="en">{res.repair_recommendation}</p>
      {err && <p className="error-text" role="alert">{err}</p>}

      {(r.status === "review" || open) && (
        <fieldset className="card pad section" disabled={busy}>
          <legend className="label">{r.status === "review" ? t("officer.confirmLead") : t("officer.confirm")}</legend>
          <p className="small muted">{r.ai_pending ? t("officer.aiBusy") : t("officer.aiSaid", { hazard: hazardLabel(t, res.hazard_type), severity: res.severity_score.toFixed(1), confidence: Math.round(r.confidence * 100) })}</p>
          <div className="filters">
            <div className="field">
              <label htmlFor="rv-h">{t("report.hazard")}</label>
              <select id="rv-h" className="input" value={hazard || (r.hazard_type === "None" ? "" : r.hazard_type)} onChange={(e) => setHazard(e.target.value)}>
                <option value="" disabled>–</option>
                {HAZARDS.map((h) => <option key={h} value={h}>{hazardLabel(t, h)}</option>)}
              </select>
            </div>
            <div className="field">
              <label htmlFor="rv-s">{t("report.severity")} (1–10)</label>
              <input id="rv-s" className="input" type="number" min={1} max={10} step={0.1} value={severity || String(r.severity)} onChange={(e) => setSeverity(e.target.value)} />
            </div>
            <button className="btn small" onClick={() => act(() => officerApi.review(r.code, hazard || r.hazard_type, Number(severity || r.severity)))}
              disabled={!(hazard || r.hazard_type !== "None")}>{t("officer.confirm")}</button>
          </div>
        </fieldset>
      )}

      {open && (
        <fieldset className="section" disabled={busy} style={{ border: 0, padding: 0, margin: 0 }}>
          <div className="filters">
            <div className="field">
              <label htmlFor="assignee">{t("officer.assignTo")}</label>
              <input id="assignee" className="input" list="assignee-list" value={assignee} onChange={(e) => setAssignee(e.target.value)} placeholder={r.assignee ?? ""} />
              <datalist id="assignee-list">{assignees.map((a) => <option key={a} value={a} />)}</datalist>
            </div>
            <button className="btn small" disabled={assignee.trim().length < 2} onClick={async () => { if (await act(() => officerApi.assign(r.code, assignee.trim()))) setAssignee(""); }}>{t("officer.assign")}</button>
          </div>
          <div className="btn-row">
            {r.status !== "fixed" && <button className="btn outline small" onClick={() => status("fixed")}>{t("officer.markFixed")}</button>}
            <button className="btn accent small" onClick={() => fileRef.current?.click()}>{t("officer.uploadRepair")}</button>
            <input ref={fileRef} type="file" accept="image/*" capture="environment" hidden aria-label={t("officer.uploadRepair")}
              onChange={async (e) => {
                const f = e.target.files?.[0];
                e.target.value = "";
                if (!f) return;
                let outcome = t("officer.repairResult");
                await act(async () => {
                  const after = await officerApi.repairPhoto(r.code, await shrinkPhoto(f));
                  const a = after.after_result;
                  outcome = after.public_status === "resolved" ? `${t("status.resolved")}: ${t("report.afterClean")}`
                    : a ? t("report.afterStill", { hazard: hazardLabel(t, a.hazard_type).toLowerCase(), n: a.severity_score.toFixed(1) }) : outcome;
                }, undefined);
                show(outcome);
              }} />
          </div>
          <div className="field">
            <label htmlFor="dismiss">{t("officer.dismissReason")}</label>
            <input id="dismiss" className="input" value={reason} onChange={(e) => setReason(e.target.value)} />
          </div>
          <button className="btn danger small" style={{ alignSelf: "start" }} disabled={reason.trim().length < 3} onClick={() => status("dismissed", reason.trim())}>{t("officer.dismiss")}</button>
        </fieldset>
      )}
      {!open && <button className="btn outline small" style={{ alignSelf: "start" }} disabled={busy} onClick={() => status("new")}>{t("officer.reopen")}</button>}

      <div className="field">
        <label htmlFor="comment">{t("officer.comment")}</label>
        <textarea id="comment" className="input" maxLength={1000} value={comment} onChange={(e) => setComment(e.target.value)} />
      </div>
      <button className="btn outline small" style={{ alignSelf: "start" }} disabled={busy || comment.trim().length < 2}
        onClick={async () => { if (await act(() => officerApi.comment(r.code, comment.trim()))) setComment(""); }}>{t("officer.post")}</button>

      <div className="filters">
        {r.merged_into ? (
          <button className="btn ghost small" disabled={busy} onClick={() => act(() => officerApi.unmerge(r.code))}>{t("officer.unmerge", { code: r.merged_into })}</button>
        ) : (
          <>
            <div className="field">
              <label htmlFor="merge">{t("officer.mergeInto")}</label>
              <input id="merge" className="input" placeholder="RS-0000" value={mergeInto} onChange={(e) => setMergeInto(e.target.value.toUpperCase())} />
            </div>
            <button className="btn ghost small" disabled={busy || mergeInto.length < 4} onClick={() => act(() => officerApi.merge(r.code, mergeInto))}>{t("officer.merge")}</button>
          </>
        )}
      </div>

      <details>
        <summary className="label">{t("officer.history")}</summary>
        <ol className="timeline" style={{ marginTop: 12 }}>
          {(r as OfficerReport).history.map((h, i) => (
            <li key={i}>
              <time dateTime={h.at}>{date(h.at, true)}</time>
              <span>{h.event} · {h.actor}{h.old_value || h.new_value ? ` · ${h.old_value ?? "–"} → ${h.new_value ?? "–"}` : ""}{h.public ? "" : ` (${t("officer.private")})`}</span>
            </li>
          ))}
        </ol>
      </details>
      <Toast msg={toast} />
      <span className="sr-only">{t(`fix.${r.urgency}` as Key)}</span>
    </section>
  );
}
