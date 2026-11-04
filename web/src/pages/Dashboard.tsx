import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { CircleMarker, MapContainer, TileLayer, Tooltip, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { ApiError, api, type Queue, type Report, type Status } from "../api";
import { Layout } from "../components/Layout";
import { PhotoWithBox, ResultDetails, UrgencyChip } from "../components/Result";
import { STATUS_LABEL, URGENCY_LABEL, ago, dueText, hazardName } from "../format";

const HOME: [number, number] = [13.0446, 77.62]; // Nagawara, near HKBK College of Engineering
const URGENCIES = ["CRITICAL", "HIGH", "MEDIUM", "LOW"] as const;

function readPin(): string {
  try { return sessionStorage.getItem("rastescan-pin") ?? ""; } catch { return ""; }
}

function FitTo({ points }: { points: [number, number][] }) {
  const map = useMap();
  const key = points.map((p) => p.join(",")).join("|");
  useEffect(() => {
    if (points.length === 1) map.setView(points[0], 16);
    else if (points.length > 1) map.fitBounds(points, { padding: [30, 30], maxZoom: 16 });
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";
}

export default function Dashboard() {
  const [queue, setQueue] = useState<Queue | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [pin, setPin] = useState(readPin);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const afterRef = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    api.queue().then((q) => { setQueue(q); setLoadError(null); }).catch((e) => setLoadError(e instanceof ApiError ? e.message : "Could not load tickets."));
  }, []);
  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [load]);

  const all = useMemo(() => [...(queue?.tickets ?? []), ...(queue?.review ?? [])], [queue]);
  const current = all.find((t) => t.code === selected) ?? null;
  const points = (queue?.tickets ?? []).filter((t) => t.lat !== null && t.lng !== null).map((t) => [t.lat!, t.lng!] as [number, number]);

  const savePin = (v: string) => {
    setPin(v);
    try { sessionStorage.setItem("rastescan-pin", v); } catch { /* not saved */ }
  };

  const act = async (fn: () => Promise<Report>) => {
    setBusy(true);
    setActionError(null);
    try {
      await fn();
      load();
    } catch (e) {
      setActionError(e instanceof ApiError ? e.message : "That did not work. Try again.");
    } finally {
      setBusy(false);
    }
  };
  const setStatus = (code: string, s: Status) => act(() => api.setStatus(code, s, pin));
  const uploadAfter = (f: File | undefined) => current && f && act(() => api.afterPhoto(current.code, f, pin));

  return (
    <Layout wide>
      <div className="dash-head">
        <div>
          <h1>Open tickets</h1>
          <p className="muted small">Sorted by urgency, then severity, then how many people reported the spot. Updates every 10 seconds.</p>
        </div>
        <div className="counts">
          {URGENCIES.map((u) => (
            <span key={u} className={`chip chip-${u}`}>{queue?.counts[u] ?? 0} {URGENCY_LABEL[u].toLowerCase()}</span>
          ))}
          <span className="chip chip-done">{queue?.verified ?? 0} verified</span>
        </div>
      </div>

      {loadError && <p className="error" role="alert">{loadError}</p>}

      <div className="dash">
        <div className="queue">
          {queue && queue.tickets.length === 0 && (
            <p className="empty">No open tickets. New reports from the citizen app appear here within 10 seconds.</p>
          )}
          {queue?.tickets.map((t) => (
            <button key={t.code} className={`qi stripe-${t.urgency} ${selected === t.code ? "on" : ""}`} onClick={() => setSelected(t.code)}>
              <span className="score num" style={{ color: `var(--u-${t.urgency})` }}>{t.severity.toFixed(1)}</span>
              <span className="qi-body">
                <b>{hazardName(t.hazard_type)} · {t.code}</b>
                <span className="muted small">
                  {t.merged_count > 1 ? `${t.merged_count} reports merged` : "1 report"} · {ago(t.created_at)}
                  {t.status === "fixed" ? " · waiting for after photo" : t.status === "assigned" ? " · crew assigned" : ` · ${dueText(t.due_at)}`}
                </span>
              </span>
              <UrgencyChip urgency={t.urgency} />
            </button>
          ))}

          {queue && queue.review.length > 0 && (
            <>
              <h2 className="section-title pad">Needs a person to check ({queue.review.length})</h2>
              {queue.review.map((t) => (
                <button key={t.code} className={`qi stripe-none ${selected === t.code ? "on" : ""}`} onClick={() => setSelected(t.code)}>
                  <span className="score num muted">{Math.round(t.confidence * 100)}%</span>
                  <span className="qi-body">
                    <b>{hazardName(t.hazard_type)}? · {t.code}</b>
                    <span className="muted small">AI confidence too low · {ago(t.created_at)}</span>
                  </span>
                </button>
              ))}
            </>
          )}
        </div>

        <div className="map">
          <MapContainer center={HOME} zoom={14} scrollWheelZoom style={{ height: "100%", width: "100%" }}>
            <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
            <FitTo points={points} />
            {queue?.tickets.filter((t) => t.lat !== null).map((t) => (
              <CircleMarker
                key={t.code}
                center={[t.lat!, t.lng!]}
                radius={7 + Math.min(t.merged_count, 5) * 2}
                pathOptions={{ color: "#fff", weight: 2, fillColor: cssVar(`--u-${t.urgency}`), fillOpacity: 0.95 }}
                eventHandlers={{ click: () => setSelected(t.code) }}
              >
                <Tooltip>{hazardName(t.hazard_type)} · {t.code}</Tooltip>
              </CircleMarker>
            ))}
          </MapContainer>
        </div>
      </div>

      {current && (
        <section className="detail card">
          <div className="detail-photos">
            <PhotoWithBox src={current.photo_url} result={current.result} urgency={current.urgency} alt={`Reported photo for ${current.code}`} />
            {current.after_photo_url && current.after_result && (
              <div>
                <p className="small muted">After repair: {hazardName(current.after_result.hazard_type)}</p>
                <PhotoWithBox src={current.after_photo_url} result={current.after_result} urgency="LOW" alt={`After photo for ${current.code}`} />
              </div>
            )}
          </div>
          <div className="stack">
            <div className="row">
              <h2 className="hazard">{current.code}</h2>
              <span className="muted small">{STATUS_LABEL[current.status]}</span>
            </div>
            <ResultDetails report={current} />
            {current.model_urgency !== current.urgency && (
              <p className="small muted">The AI said {URGENCY_LABEL[current.model_urgency].toLowerCase()}; the severity rules set it to {URGENCY_LABEL[current.urgency].toLowerCase()}.</p>
            )}
            {current.lat !== null && (
              <a className="small" href={`https://www.google.com/maps?q=${current.lat},${current.lng}`} target="_blank" rel="noreferrer">Open location in Google Maps</a>
            )}

            <label className="pin" htmlFor="pin">
              Dashboard PIN
              <input id="pin" type="password" inputMode="numeric" value={pin} onChange={(e) => savePin(e.target.value)} placeholder="Needed to change tickets" />
            </label>
            {actionError && <p className="error" role="alert">{actionError}</p>}
            <div className="actions wrap">
              {current.status === "review" && (
                <button className="primary" disabled={busy} onClick={() => setStatus(current.code, "new")}>Accept into queue</button>
              )}
              {current.status === "new" && (
                <button className="primary" disabled={busy} onClick={() => setStatus(current.code, "assigned")}>Assign crew</button>
              )}
              {(current.status === "new" || current.status === "assigned") && (
                <button className="secondary" disabled={busy} onClick={() => setStatus(current.code, "fixed")}>Mark fixed</button>
              )}
              {(current.status === "assigned" || current.status === "fixed") && (
                <button className="primary" disabled={busy} onClick={() => afterRef.current?.click()}>Upload after photo</button>
              )}
              <button className="ghost" disabled={busy} onClick={() => setStatus(current.code, "dismissed")}>Dismiss</button>
            </div>
            <input ref={afterRef} id="after" type="file" accept="image/*" capture="environment" hidden onChange={(e) => { uploadAfter(e.target.files?.[0]); e.target.value = ""; }} />
          </div>
        </section>
      )}
    </Layout>
  );
}
