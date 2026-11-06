import { gsap } from "gsap";
import { lazy, Suspense, useEffect, useLayoutEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api, ApiError, type Report } from "../api";
import AnalysisStage from "../components/AnalysisStage";
import { UrgencyBadge } from "../components/Badges";
import { Icon } from "../components/Icons";
import { PageHead } from "../components/Layout";
import { useAddress } from "../address";
import { DetectionList, PhotoWithBox, Place, SeverityMeter } from "../components/Report";
import { Skeleton } from "../components/States";
import { deviceId, hazardLabel } from "../format";
import { useI18n } from "../i18n";
import type { Key } from "../i18n/en";
import { calmMotion } from "../motion";
import { queue } from "../outbox";
import { shrinkPhoto } from "../photo";
import { usePortal } from "../portal";

const MapView = lazy(() => import("../components/MapView"));

type Pos = { lat: number; lng: number; accuracy?: number };
type Loc = { state: "finding" } | { state: "found"; pos: Pos } | { state: "none"; why: Key };

function useLocation(): [Loc, () => void] {
  const [loc, setLoc] = useState<Loc>({ state: "finding" });
  const find = () => {
    if (!("geolocation" in navigator)) {
      setLoc({ state: "none", why: "new.locUnsupported" });
      return;
    }
    setLoc({ state: "finding" });
    navigator.geolocation.getCurrentPosition(
      (p) => setLoc({ state: "found", pos: { lat: p.coords.latitude, lng: p.coords.longitude, accuracy: p.coords.accuracy } }),
      (e) => setLoc({ state: "none", why: e.code === e.PERMISSION_DENIED ? "new.locDenied" : "new.locUnavailable" }),
      { enableHighAccuracy: true, timeout: 15000, maximumAge: 60000 },
    );
  };
  useEffect(find, []);
  return [loc, find];
}

export function outcomeKey(r: Report): { key: Key; vars: Record<string, string | number> } {
  if (r.status === "no_damage") return { key: "new.resultNone", vars: {} };
  if (r.ai_pending) return { key: "new.resultBusy", vars: { code: r.code } };
  if (r.status === "review") return { key: "new.resultReview", vars: { code: r.code } };
  if (r.merged_into) return { key: "new.resultMerged", vars: { code: r.merged_into, n: Math.max(1, r.merged_count - 1) } };
  return { key: "new.resultNew", vars: { code: r.code } };
}

function Result({ r, again }: { r: Report; again: () => void }) {
  const { t } = useI18n();
  const o = outcomeKey(r);
  const res = r.result;
  const trackCode = r.merged_into ?? r.code;
  const published = !["no_damage", "review"].includes(r.status);
  const place = useAddress(trackCode, r.address);
  const box = useRef<HTMLElement>(null);

  // Reveal: the photo wipes in, a reflection sweeps across it, the AI draws its boxes, then the details cascade.
  useLayoutEffect(() => {
    const calm = calmMotion();
    const photo = box.current?.querySelector<HTMLElement>(".photo");
    const reflet = document.createElement("div");
    reflet.className = "reflet";
    photo?.appendChild(reflet);
    const ctx = gsap.context(() => {
      const tl = gsap.timeline({ defaults: { ease: "power3.out" } });
      tl.from(".res-ok", { y: calm ? 0 : -18, opacity: 0, duration: 0.7 }, 0.1);
      if (photo) {
        if (calm) tl.from(photo, { opacity: 0, duration: 0.6 }, 0.1);
        else {
          tl.from(photo, { clipPath: "inset(0 0 100% 0)", duration: 1.1, ease: "power3.inOut" }, 0.1)
            .from(".photo img", { scale: 1.25, duration: 1.6, ease: "power2.out" }, 0.1)
            .fromTo(reflet, { xPercent: -150, opacity: 1 }, { xPercent: 250, duration: 1.3, ease: "power2.inOut" }, 0.9);
        }
      }
      if (!calm) tl.from(".box", { scale: 1.7, opacity: 0, duration: 0.6, stagger: 0.18, ease: "back.out(2)" }, 1.1);
      else tl.from(".box", { opacity: 0, duration: 0.5 }, 0.8);
      tl.from(".res-detail > *", { y: calm ? 0 : 26, opacity: 0, duration: 0.7, stagger: 0.09 }, 1.0)
        .from(".res-detail .meter i", { width: 0, duration: 1.2, ease: "power2.out" }, 1.3)
        .from(".res-buttons .btn", { y: calm ? 0 : 18, opacity: 0, duration: 0.6, stagger: 0.1 }, 1.5);
    }, box);
    return () => { ctx.revert(); reflet.remove(); };
  }, []);

  return (
    <section className="section narrow" aria-live="polite" ref={box}>
      <p className="ok-text res-ok" style={{ fontSize: "1.1rem" }}>{t(o.key, o.vars)}</p>
      <div className="card">
        <PhotoWithBox src={r.photo_url} result={res} urgency={r.urgency} alt={t("report.photoAlt", { hazard: hazardLabel(t, res.hazard_type), code: r.code })} />
        {res.hazard_type !== "None" && !r.ai_pending && (
          <div className="card pad section res-detail" style={{ border: 0 }}>
            <div className="status-head">
              <h2>{hazardLabel(t, res.hazard_type)}</h2>
              <UrgencyBadge urgency={r.urgency} />
            </div>
            <Place address={place} />
            <p className="small">{t("report.severityValue", { n: r.severity.toFixed(1) })} · {t(`fix.${r.urgency}` as Key)}</p>
            <SeverityMeter score={r.severity} urgency={r.urgency} />
            <p className="rec" lang="en">{res.repair_recommendation}</p>
            <DetectionList result={res} />
          </div>
        )}
      </div>
      <div className="btn-row res-buttons">
        {published && <Link className="btn" to={`/r/${trackCode}`}>{t("new.track")}</Link>}
        <button className="btn outline" onClick={again}>{t("new.another")}</button>
      </div>
    </section>
  );
}

export default function NewReport() {
  const { t } = useI18n();
  const { refreshStats } = usePortal();
  const [loc, retryLoc] = useLocation();
  const [pin, setPin] = useState<[number, number] | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [email, setEmail] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Report | null>(null);
  const [queued, setQueued] = useState(false);
  // form -> analysing (the scene plays while the AI works) -> revealing (curtain lifts over the result) -> result
  const [stage, setStage] = useState<"form" | "analysing" | "revealing" | "result">("form");
  const [stagePhoto, setStagePhoto] = useState<string | null>(null);
  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);

  useEffect(() => () => { if (preview) URL.revokeObjectURL(preview); }, [preview]);

  const pick = (f: File | undefined) => {
    if (!f) return;
    setFile(f);
    setPreview(URL.createObjectURL(f));
    setResult(null);
    setError(null);
  };

  const position = (): Pos | null => (loc.state === "found" ? loc.pos : pin ? { lat: pin[0], lng: pin[1] } : null);

  const reset = () => {
    setFile(null);
    setPreview(null);
    setNote("");
  };

  const send = async () => {
    if (!file) return;
    setSending(true);
    setError(null);
    setQueued(false);
    const pos = position();
    // Without any position, send the original so the server can read the photo's own GPS.
    const blob = pos || file.size > 8 * 1024 * 1024 ? await shrinkPhoto(file) : file;
    const keep = async () => {
      await queue({ photo: blob, deviceId: deviceId(), lat: pos?.lat ?? null, lng: pos?.lng ?? null, note: note.trim(), email: email.trim() });
      reset();
      setQueued(true);
    };
    try {
      if (!navigator.onLine) {
        await keep();
        return;
      }
      setStagePhoto(URL.createObjectURL(blob));
      setStage("analysing");
      const r = await api.submit(blob, deviceId(), pos ? { lat: pos.lat, lng: pos.lng } : null, note.trim(), email.trim());
      setResult(r);
      reset();
      refreshStats();
    } catch (e) {
      setStage("form");
      if (e instanceof ApiError && e.status === 0) {
        try {
          await keep();
        } catch {
          setError(t("common.offline"));
        }
      } else {
        setError(e instanceof ApiError && e.status >= 400 ? e.message : t("common.error"));
      }
    } finally {
      setSending(false);
    }
  };

  const showResult = !!result && (stage === "revealing" || stage === "result");
  const scene = (stage === "analysing" || stage === "revealing") && stagePhoto ? (
    <AnalysisStage photo={stagePhoto} ready={!!result} onReveal={() => setStage("revealing")}
      onDone={() => { setStage("result"); setStagePhoto((u) => { if (u) URL.revokeObjectURL(u); return null; }); }} />
  ) : null;

  if (showResult) {
    return (
      <>
        <div className="wrap page"><Result r={result!} again={() => { setResult(null); setStage("form"); }} /></div>
        {scene}
      </>
    );
  }

  return (
    <>
      {scene}
    <div className="wrap page">
      <div className="section narrow">
        <PageHead title={t("new.title")} lead={t("new.lead")} />

        <div className={`loc ${loc.state}`} role="status">
          {loc.state === "finding" && t("new.locFinding")}
          {loc.state === "found" && t("new.locFound", { m: Math.round(loc.pos.accuracy ?? 0) })}
          {loc.state === "none" && (
            <>{t("new.locNone", { reason: t(loc.why) })} <button className="link-btn" onClick={retryLoc}>{t("new.locRetry")}</button></>
          )}
        </div>

        {loc.state === "none" && (
          <div className="section">
            <h2>{t("new.pinTitle")}</h2>
            <p className="small muted">{pin ? t("new.pinSet") : t("new.pinHint")}</p>
            <Suspense fallback={<div className="map-box short"><Skeleton h="100%" /></div>}>
              <MapView reports={[]} short pick={(lat, lng) => setPin([lat, lng])} picked={pin} />
            </Suspense>
          </div>
        )}

        {preview ? (
          <div className="photo"><img src={preview} alt={t("new.photoPreview")} /></div>
        ) : (
          <button className="dropzone" onClick={() => cameraRef.current?.click()}>
            <Icon name="camera" size={36} />
            <b>{t("new.takePhoto")}</b>
            <span className="muted">{t("new.takePhotoHint")}</span>
          </button>
        )}
        <input ref={cameraRef} id="camera" type="file" accept="image/*" capture="environment" hidden onChange={(e) => pick(e.target.files?.[0])} />
        <input ref={galleryRef} id="gallery" type="file" accept="image/*" hidden onChange={(e) => pick(e.target.files?.[0])} />

        <div className="btn-row">
          {file
            ? <button className="btn outline" onClick={() => cameraRef.current?.click()} disabled={sending}>{t("new.retake")}</button>
            : <button className="btn outline" onClick={() => galleryRef.current?.click()}>{t("new.gallery")}</button>}
        </div>

        <div className="field">
          <label htmlFor="note">{t("new.note")}</label>
          <input id="note" className="input" maxLength={280} value={note} onChange={(e) => setNote(e.target.value)} placeholder={t("new.notePlaceholder")} aria-describedby="note-hint" />
          <span id="note-hint" className="hint">{t("new.noteHint")}</span>
        </div>
        <div className="field">
          <label htmlFor="email">{t("new.email")}</label>
          <input id="email" className="input" type="email" autoComplete="email" maxLength={200} value={email} onChange={(e) => setEmail(e.target.value)} aria-describedby="email-hint" />
          <span id="email-hint" className="hint">{t("new.emailHint")}</span>
        </div>

        {error && <p className="error-text" role="alert">{error}</p>}
        {queued && <p className="loc none" role="status">{t("new.queued")}</p>}
        <button className="btn accent big" onClick={send} disabled={!file || sending}>{sending ? t("new.sending") : t("new.send")}</button>
        <p className="small muted">{t("new.privacy")}</p>
      </div>
    </div>
    </>
  );
}
