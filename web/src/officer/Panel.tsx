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

/** Dismiss reasons are shown to the public, so they are stored in English whatever language the officer uses. */
const WHY_EN = { notRoad: "Not a road problem", duplicate: "Duplicate report", private: "Private road", cantFind: "Could not find the place" } as const;

/** Everything an officer can do to one report. Every action is written to the public history. */
export function ReportPanel({ code, assignees, onChange }: { code: string; assignees: string[]; onChange: () => void }) {
  const { t, num, date } = useI18n();
  const { data: r, error, loading, reload } = useAsync(() => officerApi.report(code), [code]);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [toast, show] = useToast();
  const [reason, setReason] = useState("");
  const [comment, setComment] = useState("");
  const [mergeInto, setMergeInto] = useState("");
  const [hazard, setHazard] = useState("");
  const [severity, setSeverity] = useState("");
  const [stillDamaged, setStillDamaged] = useState<string | null>(null);
  const me = useAsync(() => officerApi.me(), []);
  const myName = me.data?.name;
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

      {r.status === "review" && (
        <div className="card pad section">
          <p className="label">{t("officer.confirmLead")}</p>
          <p className="small muted">{r.ai_pending ? t("officer.aiBusy") : t("officer.aiSaid", { hazard: hazardLabel(t, res.hazard_type), severity: res.severity_score.toFixed(1), confidence: Math.round(r.confidence * 100) })}</p>
          <div className="btn-row">
            {r.ai_pending && <button className="btn accent" disabled={busy} onClick={() => act(() => officerApi.rescan(r.code))}>{t("officer.rescan")}</button>}
            <button className="btn" disabled={busy || r.ai_pending || r.hazard_type === "None"} onClick={() => act(() => officerApi.review(r.code, r.hazard_type, r.severity))}>{t("officer.looksRight")}</button>
            <button className="btn outline" disabled={busy} onClick={() => status("dismissed", "Not a road problem")}>{t("officer.notRoad")}</button>
          </div>
          <details>
            <summary className="label">{t("officer.changeAi")}</summary>
            <div className="filters" style={{ marginTop: 10 }}>
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
              <button className="btn small" disabled={busy || !(hazard || r.hazard_type !== "None")}
                onClick={() => act(() => officerApi.review(r.code, hazard || r.hazard_type, Number(severity || r.severity)))}>{t("officer.confirm")}</button>
            </div>
          </details>
        </div>
      )}

      {open && (
        <div className="section">
          <div className="btn-row">
            {myName && r.assignee !== myName && (
              <button className="btn small" disabled={busy} onClick={() => act(() => officerApi.assign(r.code, myName))}>{t("officer.assignMe")}</button>
            )}
            <select className="input" style={{ width: "auto" }} disabled={busy} aria-label={t("officer.assignTo")} value=""
              onChange={(e) => {
                const v = e.target.value === "__new" ? window.prompt(t("officer.assignNew"))?.trim() ?? "" : e.target.value;
                if (v.length >= 2) act(() => officerApi.assign(r.code, v));
              }}>
              <option value="">{t("officer.assignOther")}</option>
              {assignees.filter((a) => a !== r.assignee).map((a) => <option key={a} value={a}>{a}</option>)}
              <option value="__new">{t("officer.assignNew")}</option>
            </select>
          </div>

          <div className="btn-row">
            <button className="btn accent" disabled={busy} onClick={() => fileRef.current?.click()}>{t("officer.repairDone")}</button>
            <button className="btn outline small" disabled={busy} onClick={() => { setStillDamaged(null); status("verified"); }}>{t("officer.resolveNoPhoto")}</button>
            <input ref={fileRef} type="file" accept="image/*" capture="environment" hidden aria-label={t("officer.repairDone")}
              onChange={async (e) => {
                const f = e.target.files?.[0];
                e.target.value = "";
                if (!f) return;
                let outcome = t("officer.repairResult");
                setStillDamaged(null);
                await act(async () => {
                  const after = await officerApi.repairPhoto(r.code, await shrinkPhoto(f));
                  const a = after.after_result;
                  if (after.public_status === "resolved") outcome = `${t("status.resolved")}: ${t("report.afterClean")}`;
                  else if (a) setStillDamaged(t("officer.stillDamaged", { hazard: hazardLabel(t, a.hazard_type).toLowerCase(), n: a.severity_score.toFixed(1) }));
                }, undefined);
                show(outcome);
              }} />
          </div>

          {stillDamaged && (
            <div className="card pad notice" role="alert">
              <p>{stillDamaged}</p>
              <div className="btn-row">
                <button className="btn small" disabled={busy} onClick={() => { setStillDamaged(null); status("verified"); }}>{t("officer.resolveAnyway")}</button>
                <button className="btn outline small" disabled={busy} onClick={() => fileRef.current?.click()}>{t("officer.tryAnother")}</button>
              </div>
            </div>
          )}

          <div className="field">
            <span className="label">{t("officer.dismissWhy")}</span>
            <div className="btn-row">
              {(["notRoad", "duplicate", "private", "cantFind"] as const).map((k) => (
                <button key={k} className="btn danger small" disabled={busy}
                  onClick={() => window.confirm(`${t("officer.dismiss")}: ${t(`officer.why.${k}` as Key)}?`) && status("dismissed", WHY_EN[k])}>{t(`officer.why.${k}` as Key)}</button>
              ))}
            </div>
          </div>
        </div>
      )}
      {!open && <button className="btn outline small" style={{ alignSelf: "start" }} disabled={busy} onClick={() => status("new")}>{t("officer.reopen")}</button>}

      <details>
        <summary className="label">{t("officer.more")}</summary>
        <div className="section" style={{ marginTop: 12 }}>
          {open && r.status !== "fixed" && r.status !== "review" && (
            <button className="btn outline small" style={{ alignSelf: "start" }} disabled={busy} onClick={() => status("fixed")}>{t("officer.markFixed")}</button>
          )}
          <div className="field">
            <label htmlFor="comment">{t("officer.comment")}</label>
            <textarea id="comment" className="input" maxLength={1000} value={comment} onChange={(e) => setComment(e.target.value)} />
          </div>
          <button className="btn outline small" style={{ alignSelf: "start" }} disabled={busy || comment.trim().length < 2}
            onClick={async () => { if (await act(() => officerApi.comment(r.code, comment.trim()))) setComment(""); }}>{t("officer.post")}</button>
          {open && (
            <div className="filters">
              <div className="field">
                <label htmlFor="dismiss">{t("officer.dismissReason")}</label>
                <input id="dismiss" className="input" value={reason} onChange={(e) => setReason(e.target.value)} />
              </div>
              <button className="btn danger small" disabled={busy || reason.trim().length < 3} onClick={() => status("dismissed", reason.trim())}>{t("officer.dismiss")}</button>
            </div>
          )}
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
        </div>
      </details>

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
