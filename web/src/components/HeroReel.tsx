/** Home banner: a ~30 fps GSAP "reel" of the worst real reports. Each photo shatters into tiles and blasts away, the next one
 *  assembles from the shards, and the AI boxes the damage. Built from live data, so it always shows today's problems. */
import { gsap } from "gsap";
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { absUrl, api, type Urgency } from "../api";
import { ago, hazardLabel, inr, urgencyLabel } from "../format";
import { useI18n } from "../i18n";
import { usePortal } from "../portal";
import { Icon } from "./Icons";

const SCENE_S = 6.5;   // seconds per photo
const FPS = 30;        // the reel is locked to a film-like 30 frames a second
const rand = gsap.utils.random;

interface Box { ymin: number; xmin: number; ymax: number; xmax: number }
/** One shot of the reel: a photo, the damage box drawn on it, and the caption. Live reports and news photos share this shape. */
interface Scene {
  key: string;
  img: HTMLImageElement;
  box: Box | null;
  boxClass: string;
  chip: string;
  title: string;
  sub: string;
}

interface Layout { cw: number; ch: number; cols: number; rows: number; tw: number; th: number }
interface Live { wrap: HTMLElement; tiles: HTMLElement[]; origin: { x: number; y: number } }

function layoutOf(el: HTMLElement): Layout {
  const r = el.getBoundingClientRect();
  const size = r.width > 700 ? 120 : 84;
  const cols = Math.max(3, Math.round(r.width / size));
  const rows = Math.max(3, Math.round(r.height / size));
  return { cw: r.width, ch: r.height, cols, rows, tw: r.width / cols, th: r.height / rows };
}

/** Where the photo sits when it covers the stage (object-position 50% 62%, road damage is usually low in the frame). */
function coverOf(img: HTMLImageElement, g: Layout) {
  const k = Math.max(g.cw / img.naturalWidth, g.ch / img.naturalHeight);
  const dw = img.naturalWidth * k, dh = img.naturalHeight * k;
  return { dw, dh, ox: (g.cw - dw) / 2, oy: (g.ch - dh) * 0.62 };
}

function buildScene(s: Scene, g: Layout): Live {
  const c = coverOf(s.img, g);
  const wrap = document.createElement("div");
  wrap.className = "reel-scene";
  const tiles: HTMLElement[] = [];
  for (let r = 0; r < g.rows; r++) {
    for (let col = 0; col < g.cols; col++) {
      const tile = document.createElement("div");
      tile.className = "reel-tile";
      Object.assign(tile.style, {
        left: `${col * g.tw}px`, top: `${r * g.th}px`, width: `${g.tw + 1}px`, height: `${g.th + 1}px`,
        backgroundImage: `url("${s.img.src}")`, backgroundSize: `${c.dw}px ${c.dh}px`,
        backgroundPosition: `${c.ox - col * g.tw}px ${c.oy - r * g.th}px`,
      });
      tile.dataset.cx = String(col * g.tw + g.tw / 2);
      tile.dataset.cy = String(r * g.th + g.th / 2);
      wrap.appendChild(tile);
      tiles.push(tile);
    }
  }
  // Blast centre: the damage if the AI boxed it, otherwise the middle of the picture.
  const b = s.box;
  const boxed = !!b && b.xmax > b.xmin && b.ymax > b.ymin;
  const origin = b && boxed
    ? { x: c.ox + ((b.xmin + b.xmax) / 2000) * c.dw, y: c.oy + ((b.ymin + b.ymax) / 2000) * c.dh }
    : { x: g.cw / 2, y: g.ch / 2 };
  return { wrap, tiles, origin };
}

/** Each tile's direction away from the blast centre, scaled to fly well off screen. */
function blast(el: Element, origin: { x: number; y: number }, far: number) {
  const dx = Number((el as HTMLElement).dataset.cx) - origin.x;
  const dy = Number((el as HTMLElement).dataset.cy) - origin.y;
  const len = Math.hypot(dx, dy) || 1;
  const dist = far * rand(0.5, 1.2);
  return { x: (dx / len) * dist + rand(-60, 60), y: (dy / len) * dist + rand(-60, 60) };
}

export default function HeroReel() {
  const { t, num } = useI18n();
  const { stats } = usePortal();
  const root = useRef<HTMLElement>(null);
  const stage = useRef<HTMLDivElement>(null);
  const fx = useRef<HTMLDivElement>(null);
  const cap = useRef<HTMLDivElement>(null);
  const pips = useRef<HTMLDivElement>(null);
  const [scenes, setScenes] = useState<Scene[]>([]);
  const tRef = useRef(t);
  tRef.current = t;
  // Honour the visitor's "reduce motion" setting, unless the link says ?motion=on (for a demo laptop that has it switched on).
  const reduced = useMemo(() => (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false) && !/[?&]motion=on/.test(window.location.href), []);
  const words = t("home.title").split(" ");

  // The shots: real news photos of Indian potholes (public/banner, credited on screen) alternating with the worst live reports.
  useEffect(() => {
    let dead = false;
    const load = (src: string) => new Promise<HTMLImageElement | null>((done) => {
      const img = new Image();
      img.onload = () => done(img);
      img.onerror = () => done(null);
      img.src = src;
    });
    (async () => {
      const news: Scene[] = [];
      try {
        const meta: { file: string; credit: string; boxes: Box[] }[] = await (await fetch(`${import.meta.env.BASE_URL}banner/meta.json`)).json();
        const imgs = await Promise.all(meta.map((m) => load(`${import.meta.env.BASE_URL}banner/${m.file}`)));
        meta.forEach((m, k) => {
          const img = imgs[k];
          if (img) news.push({ key: m.file, img, box: m.boxes[0] ?? null, boxClass: "u-CRITICAL", chip: tRef.current("hero.newsChip"),
            title: tRef.current("hero.newsTitle"), sub: tRef.current("hero.credit", { name: m.credit }) });
        });
      } catch { /* no banner photos: the live reports still play */ }

      const live: Scene[] = [];
      const page = await api.reports({ status: "open", sort: "urgency", per_page: 14 }).catch(() => null);
      const items = (page?.items ?? []).filter((r) => r.photo_url).slice(0, 6);
      const details = await Promise.all(items.map((r) => api.report(r.code).catch(() => null)));
      const imgs = await Promise.all(details.map((d) => (d ? load(absUrl(d.photo_url)) : Promise.resolve(null))));
      details.forEach((d, k) => {
        const img = imgs[k];
        if (!d || !img) return;
        const b = d.result.bounding_box;
        const tt = tRef.current;
        live.push({
          key: d.code, img, box: d.result.hazard_type !== "None" && b.xmax > b.xmin ? b : null, boxClass: `u-${d.urgency}`,
          chip: `${hazardLabel(tt, d.hazard_type)} · AI ${d.severity.toFixed(1)} · ${urgencyLabel(tt, d.urgency as Urgency)}`,
          title: `${hazardLabel(tt, d.hazard_type)}${d.ward?.name ? ` · ${d.ward.name}` : ""}`,
          sub: `${ago(tt, d.created_at)}${d.repair_estimate?.total_inr ? ` · ${tt("list.cost", { amount: inr(d.repair_estimate.total_inr) })}` : ""}`,
        });
      });

      // news, report, news, report ...
      const mixed: Scene[] = [];
      for (let k = 0; k < Math.max(news.length, live.length); k++) { if (news[k]) mixed.push(news[k]); if (live[k]) mixed.push(live[k]); }
      if (!dead) setScenes(mixed);
    })();
    return () => { dead = true; };
  }, []);

  // Headline and numbers
  useEffect(() => {
    if (reduced || !root.current) return;
    const ctx = gsap.context(() => {
      gsap.from(".reel-word > span", { yPercent: 115, rotateX: -80, opacity: 0, duration: 0.9, stagger: 0.07, ease: "back.out(1.6)", delay: 0.2 });
      gsap.from(".reel-kicker, .reel-lead, .reel-ctas", { y: 24, opacity: 0, duration: 0.8, stagger: 0.12, delay: 0.7, ease: "power3.out" });
      gsap.from(".reel-stats .stat", { y: 30, opacity: 0, duration: 0.7, stagger: 0.1, delay: 1.0, ease: "power3.out" });
    }, root);
    return () => ctx.revert();
  }, [reduced]);

  useEffect(() => {
    if (reduced || !stats || !root.current) return;
    const ctx = gsap.context(() => {
      root.current!.querySelectorAll<HTMLElement>("[data-count]").forEach((el) => {
        gsap.fromTo(el, { textContent: 0 }, { textContent: Number(el.dataset.count), duration: 1.8, delay: 1.1, ease: "power2.out", snap: { textContent: 1 } });
      });
    }, root);
    return () => ctx.revert();
  }, [stats, reduced]);

  // The reel
  useEffect(() => {
    const host = stage.current, fxEl = fx.current, caption = cap.current, pipBar = pips.current;
    if (!host || !fxEl || !caption || !pipBar || !scenes.length) return;
    gsap.ticker.fps(FPS);
    gsap.ticker.lagSmoothing(0);
    const calm = reduced; // "reduce motion": the same shots as a gentle crossfade, with no shattering, flashes or shaking
    let live: Live | null = null;
    let index = 0;
    let resizeTimer = 0;
    let g = layoutOf(host);

    const ctx = gsap.context(() => {
      const flash = fxEl.querySelector<HTMLElement>(".reel-flash")!;
      const ring = fxEl.querySelector<HTMLElement>(".reel-ring")!;
      const sparks = Array.from(fxEl.querySelectorAll<HTMLElement>(".reel-spark"));

      const detonate = (origin: { x: number; y: number }) => {
        gsap.set([ring, ...sparks], { left: origin.x, top: origin.y });
        gsap.fromTo(flash, { opacity: 0.85 }, { opacity: 0, duration: 0.45, ease: "power2.out" });
        gsap.fromTo(ring, { scale: 0.1, opacity: 1 }, { scale: 9, opacity: 0, duration: 0.9, ease: "power2.out" });
        sparks.forEach((p) => {
          const a = rand(0, Math.PI * 2), d = rand(120, Math.max(g.cw, g.ch) * 0.6);
          gsap.fromTo(p, { x: 0, y: 0, opacity: 1, scale: rand(0.6, 1.8) },
            { x: Math.cos(a) * d, y: Math.sin(a) * d, opacity: 0, scale: 0, duration: rand(0.6, 1.3), ease: "power3.out" });
        });
        gsap.fromTo(host, { x: 0, y: 0 }, { x: () => rand(-14, 14), y: () => rand(-10, 10), duration: 0.04, repeat: 9, yoyo: true, ease: "none", onComplete: () => { gsap.set(host, { x: 0, y: 0 }); } });
      };

      const play = (i: number, withBlast: boolean) => {
        const s = scenes[i % scenes.length];
        const next = buildScene(s, g);
        host.prepend(next.wrap); // under the old shards, which fly across it
        const tl = gsap.timeline({ onComplete: () => { index = i + 1; play(i + 1, true); } });

        if (live && withBlast && calm) {
          const old = live;
          tl.to(old.tiles, { opacity: 0, duration: 1.2, ease: "power1.inOut" }, 0).add(() => old.wrap.remove(), 1.5);
        } else if (live && withBlast) {
          const old = live;
          detonate(old.origin);
          tl.to(old.tiles, {
            x: (_i, el) => blast(el, old.origin, Math.max(g.cw, g.ch)).x, y: (_i, el) => blast(el, old.origin, Math.max(g.cw, g.ch)).y,
            rotation: () => rand(-220, 220), scale: () => rand(0.4, 2), opacity: 0, duration: 0.95, ease: "power3.in",
            stagger: { amount: 0.25, from: "center" },
          }, 0).add(() => old.wrap.remove(), 1.4);
        } else if (live) {
          live.wrap.remove();
        }
        live = next;

        // Assemble the new photo from shards flying back in towards their places.
        const at = withBlast ? 0.4 : 0;
        if (calm) tl.fromTo(next.tiles, { opacity: 0 }, { opacity: 1, duration: 1.2, ease: "power1.inOut" }, 0);
        else tl.fromTo(next.tiles, {
          x: (_i, el) => blast(el, next.origin, Math.max(g.cw, g.ch) * 0.8).x, y: (_i, el) => blast(el, next.origin, Math.max(g.cw, g.ch) * 0.8).y,
          rotation: () => rand(-200, 200), scale: () => rand(0.3, 2.2), opacity: 0,
        }, { x: 0, y: 0, rotation: 0, scale: 1, opacity: 1, duration: 1.15, ease: "expo.out", stagger: { amount: 0.4, from: "center" } }, at);

        // Slow push-in on the photo, like a camera move
        if (!calm) tl.fromTo(next.wrap, { scale: 1.02 }, { scale: 1.13, transformOrigin: `${next.origin.x}px ${next.origin.y}px`, duration: SCENE_S + 1, ease: "none" }, at);

        // The damage is found and boxed
        if (s.box && s.box.xmax > s.box.xmin) {
          const b = s.box;
          const c = coverOf(s.img, g);
          const box = document.createElement("div");
          box.className = `reel-box ${s.boxClass}`;
          Object.assign(box.style, {
            left: `${c.ox + (b.xmin / 1000) * c.dw}px`, top: `${c.oy + (b.ymin / 1000) * c.dh}px`,
            width: `${((b.xmax - b.xmin) / 1000) * c.dw}px`, height: `${((b.ymax - b.ymin) / 1000) * c.dh}px`,
          });
          const chip = document.createElement("span");
          chip.textContent = s.chip;
          box.appendChild(chip);
          next.wrap.appendChild(box);
          if (calm) {
            tl.fromTo(box, { opacity: 0 }, { opacity: 1, duration: 0.8 }, at + 1.5);
          } else {
            tl.fromTo(box, { scale: 2.6, opacity: 0 }, { scale: 1, opacity: 1, duration: 0.55, ease: "back.out(2.2)" }, at + 1.5);
            tl.fromTo(chip, { xPercent: -30, opacity: 0 }, { xPercent: 0, opacity: 1, duration: 0.5, ease: "power3.out" }, at + 1.9);
            tl.to(box, { boxShadow: "0 0 0 10px rgba(255,255,255,0)", repeat: 3, yoyo: true, duration: 0.5, ease: "sine.inOut" }, at + 2.1);
          }
        }

        // Caption and progress
        caption.innerHTML = "";
        const title = document.createElement("b");
        title.textContent = s.title;
        const sub = document.createElement("span");
        sub.textContent = s.sub;
        caption.append(title, sub);
        tl.fromTo(caption, { y: calm ? 0 : 34, opacity: 0 }, { y: 0, opacity: 1, duration: 0.7, ease: "power3.out" }, at + 0.9);
        const dots = Array.from(pipBar.children) as HTMLElement[];
        dots.forEach((p, k) => p.classList.toggle("on", k === i % scenes.length));
        const fill = dots[i % scenes.length]?.firstElementChild;
        if (fill) tl.fromTo(fill, { scaleX: 0 }, { scaleX: 1, duration: SCENE_S, ease: "none" }, 0);

        tl.to({}, { duration: SCENE_S }, 0); // hold until the next blast
      };

      play(0, false);

      // Rebuild on resize so the tiles and the damage box always match the picture
      const onResize = () => {
        window.clearTimeout(resizeTimer);
        resizeTimer = window.setTimeout(() => {
          gsap.globalTimeline.clear();
          host.querySelectorAll(".reel-scene").forEach((n) => n.remove());
          live = null;
          g = layoutOf(host);
          play(index, false);
        }, 300);
      };
      window.addEventListener("resize", onResize);
      // Do not burn battery while the banner is off screen
      const io = new IntersectionObserver(([e]) => { if (e.isIntersecting) gsap.globalTimeline.resume(); else gsap.globalTimeline.pause(); });
      io.observe(host);
      return () => { window.removeEventListener("resize", onResize); io.disconnect(); };
    }, root);

    return () => {
      window.clearTimeout(resizeTimer);
      ctx.revert();
      gsap.globalTimeline.clear(); // scenes started later by the loop are not tracked by the context
      host.querySelectorAll(".reel-scene").forEach((n) => n.remove());
      gsap.ticker.fps(0); // back to the device's own rate
    };
  }, [scenes, reduced]);

  const s = stats;
  return (
    <section className="reel" ref={root} aria-label={t("home.title")}>
      <div className="reel-stage" ref={stage} aria-hidden="true" />
      <div className="reel-fx" ref={fx} aria-hidden="true">
        <i className="reel-flash" /><i className="reel-ring" />
        {Array.from({ length: 28 }, (_, k) => <i key={k} className="reel-spark" />)}
      </div>
      <div className="reel-shade" aria-hidden="true" />

      <div className="wrap reel-content">
        <p className="reel-kicker"><Icon name="alert" size={16} /> {t("hero.kicker")}</p>
        <h1 className="reel-title">{words.map((w, k) => <Fragment key={k}><span className="reel-word"><span>{w}</span></span>{" "}</Fragment>)}</h1>
        <p className="lead reel-lead">{t("home.lead")}</p>
        <div className="btn-row reel-ctas">
          <Link to="/report" className="btn accent big"><Icon name="camera" size={22} /> {t("home.cta")}</Link>
          <Link to="/map?present=1" className="btn outline big reel-ghost"><Icon name="map" size={20} /> {t("hero.watch")}</Link>
        </div>
        <p className="small reel-hint">{t("home.ctaHint")}</p>

        <div className="stats reel-stats" aria-live="polite">
          <div className="stat"><b data-count={s?.reported_today ?? 0}>{s ? num(s.reported_today) : "–"}</b><span>{t("stat.today")}</span></div>
          <div className="stat"><b data-count={s?.open_now ?? 0}>{s ? num(s.open_now) : "–"}</b><span>{t("stat.open")}</span></div>
          <div className={`stat ${s?.overdue_now ? "warn" : ""}`}><b data-count={s?.overdue_now ?? 0}>{s ? num(s.overdue_now) : "–"}</b><span>{t("stat.overdue")}</span></div>
          <div className="stat"><b data-count={s?.resolved_this_month ?? 0}>{s ? num(s.resolved_this_month) : "–"}</b><span>{t("stat.resolvedMonth")}</span></div>
        </div>
      </div>

      <div className="reel-caption" ref={cap} aria-hidden="true" />
      <div className="reel-pips" ref={pips} aria-hidden="true">
        {scenes.map((sc) => <span key={sc.key}><i /></span>)}
      </div>
    </section>
  );
}
