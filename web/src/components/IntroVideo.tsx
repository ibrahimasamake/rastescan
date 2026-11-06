/** The film that opens the Home page: a real pothole, the AI scan, the app, the name. It plays once per visit and can always be
 *  skipped. It never holds the page back: if the video fails or is slow to start, Home simply appears. */
import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { useI18n } from "../i18n";
import { calmMotion } from "../motion";

const SEEN = "rs-intro-seen";
const START_WITHIN_MS = 4000; // a slow connection gets the page, not a black screen
const FADE_MS = 500;

function alreadySeen(): boolean {
  try {
    return sessionStorage.getItem(SEEN) === "1";
  } catch {
    return false;
  }
}

function markSeen() {
  try {
    sessionStorage.setItem(SEEN, "1");
  } catch {
    /* private mode: it may play again on the next visit */
  }
}

export default function IntroVideo() {
  const { t } = useI18n();
  const { pathname } = useLocation();
  // Only a visit that lands on Home gets the film; a shared report link opens straight away.
  const [state, setState] = useState<"playing" | "leaving" | "gone">(() => (pathname === "/" && !alreadySeen() && !calmMotion() ? "playing" : "gone"));
  const video = useRef<HTMLVideoElement>(null);
  const started = useRef(false);

  const finish = useCallback(() => {
    markSeen();
    setState((s) => (s === "playing" ? "leaving" : s));
  }, []);

  useEffect(() => {
    if (state !== "playing") return;
    video.current?.play().catch(finish); // autoplay refused
    const id = window.setTimeout(() => { if (!started.current) finish(); }, START_WITHIN_MS);
    return () => window.clearTimeout(id);
  }, [state, finish]);

  useEffect(() => {
    if (state !== "leaving") return;
    const id = window.setTimeout(() => setState("gone"), FADE_MS);
    return () => window.clearTimeout(id);
  }, [state]);

  if (state === "gone") return null;
  return (
    <div className={`intro${state === "leaving" ? " leaving" : ""}`}>
      <video
        ref={video}
        className="intro-video"
        src={`${import.meta.env.BASE_URL}rastescan-intro.mp4`}
        autoPlay
        muted
        playsInline
        preload="auto"
        onPlaying={() => { started.current = true; }}
        onEnded={finish}
        onError={finish}
        aria-label={t("intro.label")}
      />
      <button type="button" className="intro-skip" onClick={finish} autoFocus>{t("intro.skip")}</button>
    </div>
  );
}
