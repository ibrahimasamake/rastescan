/** Full-screen "the AI is looking at your photo" scene, shown between Send and the result.
 *  The citizen's own photo is scanned by a laser, a glass reflection sweeps over it, a ring counts up and the checks tick off.
 *  When the result is ready (`ready`) the ring completes, a flash goes off and the curtain wipes away to reveal the result. */
import { gsap } from "gsap";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useI18n } from "../i18n";
import { calmMotion } from "../motion";
import type { Key } from "../i18n/en";

const STEPS: Key[] = ["an.s1", "an.s2", "an.s3", "an.s4", "an.s5"];
const STEP_AT = [0.5, 2.0, 3.8, 5.6, 7.4]; // seconds after start when each check begins
const MIN_SHOW_S = 3.4;                    // long enough to read, even when the AI answers instantly
const R = 52;
const CIRC = 2 * Math.PI * R;

export default function AnalysisStage({ photo, ready, onReveal, onDone }: {
  photo: string;
  ready: boolean;
  /** The curtain starts to lift: show the result underneath now. */
  onReveal: () => void;
  /** The curtain has gone: remove this scene. */
  onDone: () => void;
}) {
  const { t } = useI18n();
  const root = useRef<HTMLDivElement>(null);
  const [step, setStep] = useState(0);        // how many checks have started
  const [finished, setFinished] = useState(false);
  const startedAt = useRef(performance.now());
  const over = useRef(false); // the finale has begun: late step timers must not undo it
  const api = useRef<{ finish: () => void } | null>(null);
  const cbs = useRef({ onReveal, onDone });
  cbs.current = { onReveal, onDone };
  const calm = useRef(calmMotion()).current;

  useLayoutEffect(() => {
    const el = root.current!;
    const q = (s: string) => el.querySelector<HTMLElement>(s)!;
    const proxy = { v: 0 };
    let creep: gsap.core.Tween | undefined;
    const paint = () => {
      q(".an-ring-fg").style.strokeDashoffset = String(CIRC * (1 - proxy.v / 100));
      q(".an-pct").textContent = `${Math.round(proxy.v)}%`;
    };
    const ctx = gsap.context(() => {
      // Enter
      gsap.from(".an-bg", { opacity: 0, duration: 0.5 });
      gsap.from(".an-card", { y: calm ? 0 : 50, scale: calm ? 1 : 0.94, opacity: 0, duration: 0.9, ease: "power3.out", delay: 0.1 });
      gsap.from(".an-corner", { scale: calm ? 1 : 1.5, opacity: 0, duration: 0.7, stagger: 0.08, ease: "back.out(2)", delay: 0.5 });
      gsap.from(".an-side > *", { y: calm ? 0 : 24, opacity: 0, duration: 0.7, stagger: 0.1, ease: "power3.out", delay: 0.5 });

      if (!calm) {
        // Scanning laser, glass reflection and a slow push-in on the photo
        gsap.fromTo(".an-scan", { top: "0%" }, { top: "100%", duration: 1.9, ease: "sine.inOut", repeat: -1, yoyo: true });
        gsap.fromTo(".an-shine", { xPercent: -140 }, { xPercent: 240, duration: 1.2, ease: "power2.inOut", repeat: -1, repeatDelay: 1.3 });
        gsap.fromTo(".an-img", { scale: 1 }, { scale: 1.07, duration: 12, ease: "none" });
        gsap.to(".an-corner", { opacity: 0.45, duration: 0.9, repeat: -1, yoyo: true, ease: "sine.inOut", delay: 1.4, stagger: 0.15 });
        gsap.to(".an-grid", { backgroundPosition: "0 40px", duration: 2.4, repeat: -1, ease: "none" });
      }

      // The ring creeps up but never quite reaches the end until the answer is in
      creep = gsap.to(proxy, { v: 90, duration: 14, ease: "power2.out", onUpdate: paint });
      STEP_AT.forEach((s, i) => gsap.delayedCall(s, () => { if (!over.current) setStep(i + 1); }));
    }, root);
    paint();

    // The finale: complete the checks, flash, then lift the curtain.
    api.current = {
      finish: () => {
        over.current = true;
        creep?.kill();
        const tl = gsap.timeline();
        tl.add(() => setStep(STEPS.length + 1))
          .to(proxy, { v: 100, duration: 0.7, ease: "power2.inOut", onUpdate: paint }, 0)
          .add(() => setFinished(true), 0.2)
          .to(".an-scan", { opacity: 0, duration: 0.3 }, 0.2)
          .fromTo(".an-flash", { opacity: 0 }, { opacity: calm ? 0 : 0.95, duration: 0.18, yoyo: true, repeat: 1, ease: "power1.out" }, 0.75)
          .fromTo(".an-ring-fg", { strokeWidth: 8 }, { strokeWidth: 14, duration: 0.25, yoyo: true, repeat: 1 }, 0.75)
          .add(() => cbs.current.onReveal(), 1.15)
          .to(".an-card", { y: calm ? 0 : -40, scale: calm ? 1 : 1.04, opacity: 0, duration: 0.6, ease: "power2.in" }, 1.15)
          // the dark curtain wipes upward off the page
          .to(".an", { clipPath: calm ? "inset(0 0 0 0)" : "inset(0 0 100% 0)", opacity: calm ? 0 : 1, duration: calm ? 0.6 : 0.9, ease: "power3.inOut" }, 1.35)
          .add(() => cbs.current.onDone(), 2.3);
      },
    };
    return () => { ctx.revert(); gsap.killTweensOf(proxy); };
  }, [calm]);

  useEffect(() => {
    if (!ready) return;
    const wait = Math.max(0, MIN_SHOW_S * 1000 - (performance.now() - startedAt.current));
    const id = window.setTimeout(() => api.current?.finish(), wait);
    return () => window.clearTimeout(id);
  }, [ready]);

  return (
    <div className="an" ref={root} role="status" aria-live="polite" aria-label={t("an.title")}>
      <div className="an-bg" aria-hidden="true" />
      <div className="an-flash" aria-hidden="true" />
      <div className="an-card">
        <div className="an-frame">
          <div className="an-photo">
            <img className="an-img" src={photo} alt="" />
            <div className="an-grid" aria-hidden="true" />
            <div className="an-scan" aria-hidden="true" />
            <div className="an-shine" aria-hidden="true" />
          </div>
          <i className="an-corner tl" aria-hidden="true" /><i className="an-corner tr" aria-hidden="true" />
          <i className="an-corner bl" aria-hidden="true" /><i className="an-corner br" aria-hidden="true" />
        </div>
        <div className="an-side">
          <svg className="an-ring" viewBox="0 0 120 120" aria-hidden="true">
            <circle cx="60" cy="60" r={R} className="an-ring-bg" />
            <circle cx="60" cy="60" r={R} className="an-ring-fg" strokeDasharray={CIRC} strokeDashoffset={CIRC} transform="rotate(-90 60 60)" />
            <text x="60" y="68" textAnchor="middle" className="an-pct">0%</text>
          </svg>
          <h2>{finished ? t("an.done") : t("an.title")}</h2>
          <ol className="an-steps">
            {STEPS.map((k, i) => {
              const state = step > i + 1 || (step > i && finished) ? "done" : step === i + 1 ? "now" : "wait";
              return <li key={k} className={state}><i aria-hidden="true">{state === "done" ? "✓" : ""}</i>{t(k)}</li>;
            })}
          </ol>
          <p className="small an-hint">{t("an.hint")}</p>
        </div>
      </div>
    </div>
  );
}
