import { useState } from "react";
import { absUrl, officerApi } from "../api";
import { Empty, ErrorBox, Skeleton, useAsync } from "../components/States";
import { ago, hazardLabel } from "../format";
import { useI18n } from "../i18n";
import { ReportPanel } from "./Panel";
import { OfficerShell } from "./Shell";

export default function Review() {
  return <OfficerShell><ReviewBody /></OfficerShell>;
}

/** Low-confidence AI results and reports saved while the AI was busy. Nothing here is public until confirmed. */
function ReviewBody() {
  const { t } = useI18n();
  const queue = useAsync(() => officerApi.queue(), [], 20000);
  const assignees = useAsync(() => officerApi.assignees(), []);
  const [selected, setSelected] = useState<string | null>(null);
  const items = queue.data?.review ?? [];
  if (queue.loading && !queue.data) return <Skeleton h={300} />;
  if (!queue.data) return <ErrorBox error={queue.error} retry={queue.reload} />;
  if (!items.length) return <Empty>{t("officer.reviewEmpty")}</Empty>;
  return (
    <div className="split">
      <ul className="grid cols-2" style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {items.map((r) => (
          <li key={r.code}>
            <button className="card rcard" style={{ width: "100%", textAlign: "left", padding: 0, borderColor: selected === r.code ? "var(--saffron)" : undefined }}
              onClick={() => setSelected(r.code)} aria-pressed={selected === r.code}>
              <div className="thumbs" style={{ gridTemplateColumns: "1fr" }}><figure><img src={absUrl(r.photo_url)} alt="" loading="lazy" /></figure></div>
              <div className="body">
                <b>{r.code} · {r.ai_pending ? t("officer.aiBusy").split(".")[0] : hazardLabel(t, r.hazard_type)}</b>
                <span className="small muted">{Math.round(r.confidence * 100)}% · {ago(t, r.created_at)}</span>
              </div>
            </button>
          </li>
        ))}
      </ul>
      <div className="sticky">
        {selected ? <ReportPanel key={selected} code={selected} assignees={assignees.data ?? []} onChange={queue.reload} />
          : <Empty>{t("officer.selectHint")}</Empty>}
      </div>
    </div>
  );
}
