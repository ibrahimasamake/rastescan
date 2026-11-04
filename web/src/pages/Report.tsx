import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, api, type Report as ReportT } from "../api";
import { Layout } from "../components/Layout";
import { PhotoWithBox, ResultDetails, UrgencyChip } from "../components/Result";
import { STATUS_LABEL, ago, deviceId, hazardName } from "../format";
import { shrinkPhoto } from "../photo";

type Pos = { lat: number; lng: number; accuracy: number };
type Loc = { state: "finding" } | { state: "found"; pos: Pos } | { state: "none"; why: string };

function useLocation(): [Loc, () => void] {
  const [loc, setLoc] = useState<Loc>({ state: "finding" });
  const find = () => {
    if (!("geolocation" in navigator)) {
      setLoc({ state: "none", why: "This browser cannot share location." });
      return;
    }
    setLoc({ state: "finding" });
    navigator.geolocation.getCurrentPosition(
      (p) => setLoc({ state: "found", pos: { lat: p.coords.latitude, lng: p.coords.longitude, accuracy: p.coords.accuracy } }),
      (e) => setLoc({ state: "none", why: e.code === e.PERMISSION_DENIED ? "Location permission was refused." : "Location is not available right now." }),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
    );
  };
  useEffect(find, []);
  return [loc, find];
}

function outcome(r: ReportT): string {
  if (r.status === "no_damage") return "No damage found in this photo. Nothing was sent to the ward office.";
  if (r.status === "review") return `The AI was not sure about this photo, so a ward engineer will check it. Your ticket is ${r.code}.`;
  if (r.merged_into) return `Someone already reported this spot. Your report was added to ticket ${r.merged_into}, which raises its priority.`;
  return `Sent to the ward office as ticket ${r.code}.`;
}

export default function Report() {
  const [loc, retryLoc] = useLocation();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ReportT | null>(null);
  const [mine, setMine] = useState<ReportT[]>([]);
  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);
  const [id] = useState(deviceId);

  const loadMine = useCallback(() => { api.mine(id).then(setMine).catch(() => {}); }, [id]);
  useEffect(loadMine, [loadMine]);
  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const pick = (f: File | undefined) => {
    if (!f) return;
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setResult(null);
    setError(null);
  };

  const send = async () => {
    if (!file) return;
    setSending(true);
    setError(null);
    try {
      const pos = loc.state === "found" ? loc.pos : null;
      // Without a browser position, send the original so the server can read the photo's own GPS.
      const blob = pos || file.size > 8 * 1024 * 1024 ? await shrinkPhoto(file) : file;
      const r = await api.submit(blob, id, pos);
      setResult(r);
      setFile(null);
      setPreview(null);
      loadMine();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong. Try again.");
    } finally {
      setSending(false);
    }
  };

  return (
    <Layout>
      {!result && (
        <section className="stack">
          <div>
            <h1>Report road damage</h1>
            <p className="muted">Take a photo of the damage from a few steps away. RasteScan rates how dangerous it is and sends it to the ward office.</p>
          </div>

          <div className={`loc loc-${loc.state}`}>
            {loc.state === "finding" && "Finding your location…"}
            {loc.state === "found" && `Location found, accurate to about ${Math.round(loc.pos.accuracy)} m.`}
            {loc.state === "none" && (
              <>
                {loc.why} We will use the photo's own location if it has one.{" "}
                <button className="link" onClick={retryLoc}>Try again</button>
              </>
            )}
          </div>

          {preview ? (
            <div className="photo"><img src={preview} alt="Photo you are about to send" /></div>
          ) : (
            <button className="dropzone" onClick={() => cameraRef.current?.click()}>
              <b>Take a photo</b>
              <span>Opens the camera</span>
            </button>
          )}

          <input ref={cameraRef} id="camera" type="file" accept="image/*" capture="environment" hidden onChange={(e) => pick(e.target.files?.[0])} />
          <input ref={galleryRef} id="gallery" type="file" accept="image/*" hidden onChange={(e) => pick(e.target.files?.[0])} />

          {error && <p className="error" role="alert">{error}</p>}

          <div className="actions">
            {file ? (
              <>
                <button className="primary" onClick={send} disabled={sending}>{sending ? "Checking the photo…" : "Send report"}</button>
                <button className="secondary" onClick={() => cameraRef.current?.click()} disabled={sending}>Retake</button>
              </>
            ) : (
              <button className="secondary" onClick={() => galleryRef.current?.click()}>Choose from gallery</button>
            )}
          </div>
        </section>
      )}

      {result && (
        <section className="stack">
          <p className="outcome">{outcome(result)}</p>
          <div className="card">
            <PhotoWithBox src={result.photo_url} result={result.result} urgency={result.urgency} alt={`Your photo, ${hazardName(result.hazard_type)}`} />
            <ResultDetails report={result} />
          </div>
          <button className="primary" onClick={() => setResult(null)}>Report another spot</button>
        </section>
      )}

      {mine.length > 0 && (
        <section className="stack mine">
          <h2 className="section-title">Your reports</h2>
          <ul className="list">
            {mine.map((r) => (
              <li key={r.code} className={`list-item stripe-${r.status === "no_damage" ? "none" : r.urgency}`}>
                <div>
                  <b>{hazardName(r.hazard_type)}</b> <span className="muted">· {r.code} · {ago(r.created_at)}</span>
                  <div className="muted small">{r.merged_into ? `Added to ${r.merged_into}` : STATUS_LABEL[r.status]}</div>
                </div>
                {r.status !== "no_damage" && <UrgencyChip urgency={r.urgency} />}
              </li>
            ))}
          </ul>
        </section>
      )}
    </Layout>
  );
}
