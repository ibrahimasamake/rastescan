import { useEffect, useState } from "react";
import { ApiError, officerApi, type ModelInfo, type ModelTest } from "../api";
import { DetectionList, PhotoWithBox } from "../components/Report";
import { UrgencyBadge } from "../components/Badges";
import { ErrorBox, Skeleton, Toast, useAsync, useToast } from "../components/States";
import { useI18n } from "../i18n";
import { usePortal } from "../portal";
import { shrinkPhoto } from "../photo";
import { OfficerShell } from "./Shell";

type Run = { state: "running" } | { state: "done"; test: ModelTest } | { state: "failed"; message: string };

export default function Models() {
  return <OfficerShell><ModelsBody /></OfficerShell>;
}

function ModelsBody() {
  const { t } = useI18n();
  const { officer } = usePortal();
  const list = useAsync(() => officerApi.models(), []);
  const [photo, setPhoto] = useState<Blob | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [runs, setRuns] = useState<Record<string, Run>>({});
  const [toast, show] = useToast();
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);
  if (officer.role !== "admin") return <p>{t("officer.notAllowed")}</p>;

  const pick = async (f: File | undefined) => {
    if (!f) return;
    setPhoto(await shrinkPhoto(f));
    setPreview(URL.createObjectURL(f));
    setRuns({});
  };

  const run = async (m: ModelInfo) => {
    if (!photo) return;
    setRuns((r) => ({ ...r, [m.id]: { state: "running" } }));
    try {
      const test = await officerApi.testModel(photo, m.provider, m.model);
      setRuns((r) => ({ ...r, [m.id]: { state: "done", test } }));
    } catch (e) {
      setRuns((r) => ({ ...r, [m.id]: { state: "failed", message: e instanceof ApiError ? e.message : "Could not reach the server." } }));
    }
  };

  const runAll = async () => {
    for (const m of list.data?.models.filter((x) => x.runnable) ?? []) await run(m);
  };

  const makeLive = async (m: ModelInfo) => {
    try {
      await officerApi.setLiveModel(m.provider, m.model);
      show("New reports now use " + m.label);
      list.reload();
    } catch (e) {
      show(e instanceof ApiError ? e.message : "Could not switch.");
    }
  };

  const d = list.data;
  return (
    <>
      <p className="muted">Try each AI model on the same photo and compare the real output. Nothing here is saved or shown to the public. Photos are blurred first, like real reports.</p>
      <div className="card pad section">
        <label className="label" htmlFor="lab-photo">1. Choose a road photo</label>
        <input id="lab-photo" type="file" accept="image/*" onChange={(e) => pick(e.target.files?.[0])} />
        {preview && <div style={{ maxWidth: 320 }}><div className="photo"><img src={preview} alt="Photo to test" /></div></div>}
      </div>

      {list.loading && !d && <Skeleton h={200} />}
      {!!list.error && !d && <ErrorBox error={list.error} retry={list.reload} />}
      {d && (
        <>
          <div className="btn-row">
            <b>2. Click a model to run it</b>
            <button className="btn small" disabled={!photo} onClick={runAll}>Run all available</button>
            <button className="btn outline small" onClick={list.reload}>Refresh list</button>
          </div>
          <div className="lab-grid">
            {d.models.map((m) => {
              const r = runs[m.id];
              return (
                <section key={m.id} className={`card pad lab-card ${m.live ? "live" : ""}`} aria-label={m.label}>
                  <div className="status-head">
                    <h2 style={{ fontSize: "1.05rem" }}>{m.label}</h2>
                    <span className="badge s-reported">{m.provider}</span>
                    {m.live && <span className="badge s-resolved">In use for new reports</span>}
                  </div>
                  <p className="small muted">{m.note}</p>
                  <div className="btn-row">
                    <button className="btn small" disabled={!photo || !m.runnable || r?.state === "running"} onClick={() => run(m)}>
                      {r?.state === "running" ? "Running…" : "Run on this photo"}
                    </button>
                    {m.runnable && !m.live && <button className="btn outline small" onClick={() => makeLive(m)}>Use for new reports</button>}
                  </div>
                  {r?.state === "running" && <p className="small muted" role="status">Working. A local model on a CPU can take a minute or more.</p>}
                  {r?.state === "failed" && <p className="error-text" role="alert">{r.message}</p>}
                  {r?.state === "done" && !r.test.ok && <p className="error-text" role="alert">Failed after {r.test.seconds}s: {r.test.error}</p>}
                  {r?.state === "done" && r.test.ok && r.test.result && preview && (
                    <div className="section">
                      <p className="small"><b>{r.test.seconds}s</b> · {r.test.result.detections?.length ?? (r.test.result.hazard_type === "None" ? 0 : 1)} defect(s) found</p>
                      <PhotoWithBox src={preview} result={r.test.result} urgency={r.test.result.urgency_level} alt={`Result from ${m.label}`} />
                      <div className="status-head">
                        <b>{r.test.result.hazard_type}</b>
                        <span className="small">severity {r.test.result.severity_score.toFixed(1)}</span>
                        <UrgencyBadge urgency={r.test.result.urgency_level} />
                        <span className="small muted">confidence {Math.round(r.test.result.confidence * 100)}%</span>
                      </div>
                      <p className="rec small" lang="en">{r.test.result.repair_recommendation}</p>
                      <DetectionList result={r.test.result} />
                      <details><summary className="small">Raw answer</summary><pre className="small lab-json">{JSON.stringify(r.test.result, null, 2)}</pre></details>
                    </div>
                  )}
                </section>
              );
            })}
          </div>
        </>
      )}
      <Toast msg={toast} />
    </>
  );
}
