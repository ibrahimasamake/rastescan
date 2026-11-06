import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink } from "react-router-dom";
import { LANGS, useI18n, type TextSize } from "../i18n";
import { usePortal } from "../portal";
import { onChange, pending, startOutbox } from "../outbox";
import { AppLink } from "./AppDownload";
import { Emblem } from "./Emblem";
import { Toast, useToast } from "./States";

const SIZES: { s: TextSize; label: string; key: "strip.smaller" | "strip.normal" | "strip.larger" }[] = [
  { s: "sm", label: "A-", key: "strip.smaller" },
  { s: "md", label: "A", key: "strip.normal" },
  { s: "lg", label: "A+", key: "strip.larger" },
];

function TopStrip() {
  const { t, lang, setLang, size, setSize } = useI18n();
  return (
    <div className="topstrip">
      <div className="wrap">
        <span className="official-dot">{t("strip.official")}</span>
        <div className="tools">
          <div className="group" role="group" aria-label={t("strip.language")}>
            {LANGS.map((l) => (
              <button key={l.code} lang={l.code} aria-pressed={lang === l.code} onClick={() => setLang(l.code)}>{l.label}</button>
            ))}
          </div>
          <div className="group" role="group" aria-label={t("strip.textSize")}>
            {SIZES.map((x) => (
              <button key={x.s} aria-pressed={size === x.s || (x.s === "lg" && size === "xl")} title={t(x.key)}
                onClick={() => setSize(x.s === "lg" && size === "lg" ? "xl" : x.s)}>{x.label}<span className="sr-only"> {t(x.key)}</span></button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/** Shows how many offline reports wait on this phone, and says so when they have been sent. */
function OutboxStatus() {
  const { t } = useI18n();
  const { refreshStats } = usePortal();
  const [count, setCount] = useState(0);
  const [toast, show] = useToast();
  useEffect(() => {
    const update = () => pending().then((p) => setCount(p.length));
    update();
    const off = onChange(update);
    startOutbox(() => {
      show(t("new.sentQueued"));
      refreshStats();
    });
    return () => { off(); };
  }, [t, show, refreshStats]);
  return (
    <>
      {count > 0 && <div className="notice" role="status"><div className="wrap">{t("new.queuedCount", { n: count })}</div></div>}
      <Toast msg={toast} />
    </>
  );
}

export function Layout({ children }: { children: ReactNode }) {
  const { t, date } = useI18n();
  const { config, stats, officer } = usePortal();
  const site = config?.site_name ?? "Municipal Road Services";
  return (
    <>
      <a className="skip" href="#main" onClick={(e) => { e.preventDefault(); document.getElementById("main")?.focus(); }}>{t("skip")}</a>
      <TopStrip />
      <header className="header">
        <div className="wrap">
          <Link to="/" className="brand">
            <Emblem />
            <span>
              <span className="brand-name">{site}</span>
              <span className="brand-tag">{t("site.tagline")}</span>
            </span>
          </Link>
          <Link to="/report" className="btn accent header-cta">{t("home.cta")}</Link>
        </div>
      </header>
      <nav className="mainnav" aria-label={t("nav.menu")}>
        <div className="wrap">
          <NavLink to="/" end>{t("nav.home")}</NavLink>
          <NavLink to="/report">{t("nav.report")}</NavLink>
          <NavLink to="/map">{t("nav.map")}</NavLink>
          <NavLink to="/reports">{t("nav.list")}</NavLink>
          <NavLink to="/wards">{t("nav.wards")}</NavLink>
          <NavLink to="/impact">{t("nav.impact")}</NavLink>
          <NavLink to="/mine">{t("nav.mine")}</NavLink>
          <span className="spacer" />
          <NavLink to="/officer">{officer.signed_in ? t("nav.dashboard") : t("nav.officer")}</NavLink>
        </div>
      </nav>
      {config?.ai_mode === "fake" && <div className="notice test"><div className="wrap">{t("banner.test")}</div></div>}
      {!!stats?.demo_count && <div className="notice"><div className="wrap">{t("banner.demo", { count: stats.demo_count })}</div></div>}
      <OutboxStatus />
      <main id="main" tabIndex={-1}>{children}</main>
      <footer className="footer">
        <div className="wrap">
          <section aria-labelledby="f-about">
            <h2 id="f-about">{site}</h2>
            <ul>
              <li><Link to="/about">{t("footer.about")}</Link></li>
              <li><Link to="/about#how">{t("footer.how")}</Link></li>
              <AppLink />
              <li><Link to="/wards">{t("nav.wards")}</Link></li>
            </ul>
          </section>
          <section aria-labelledby="f-policy">
            <h2 id="f-policy">{t("footer.privacy")}</h2>
            <ul>
              <li><Link to="/privacy">{t("footer.privacy")}</Link></li>
              <li><Link to="/accessibility">{t("footer.accessibility")}</Link></li>
              <li><Link to="/open-data">{t("footer.openData")}</Link></li>
            </ul>
          </section>
          <section aria-labelledby="f-contact">
            <h2 id="f-contact">{t("footer.contact")}</h2>
            <p className="small">{t("footer.contactText")}</p>
          </section>
        </div>
        <div className="legal">
          <div className="wrap">
            <span>{t("footer.disclaimer")}</span>
            {stats?.last_updated && <span>{t("footer.updated", { time: date(stats.last_updated, true) })}</span>}
          </div>
        </div>
      </footer>
    </>
  );
}

export function PageHead({ title, lead, children }: { title: string; lead?: string; children?: ReactNode }) {
  return (
    <div className="page-head">
      <h1>{title}</h1>
      {lead && <p className="muted">{lead}</p>}
      {children}
    </div>
  );
}
