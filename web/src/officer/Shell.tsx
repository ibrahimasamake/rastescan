import { useEffect, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { ApiError, officerApi, setPin } from "../api";
import { PageHead } from "../components/Layout";
import { Skeleton } from "../components/States";
import { useI18n } from "../i18n";
import { usePortal } from "../portal";

function Login() {
  const { t } = useI18n();
  const { refreshOfficer } = usePortal();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [pin, setPinValue] = useState("");
  const [usePin, setUsePin] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (usePin) {
        setPin(pin);
        const me = await officerApi.me();
        if (!me.signed_in) {
          setPin(null);
          throw new ApiError("PIN", 401);
        }
      } else {
        await officerApi.login(email, password);
      }
      await refreshOfficer();
    } catch (err) {
      setError(err instanceof ApiError && err.status >= 400 && err.message !== "PIN" ? err.message : t("common.error"));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="wrap page narrow">
      <PageHead title={t("officer.loginTitle")} lead={t("officer.loginLead")} />
      <form className="card pad section" onSubmit={submit} style={{ maxWidth: 440 }}>
        {usePin ? (
          <div className="field">
            <label htmlFor="pin">{t("officer.pinLabel")}</label>
            <input id="pin" className="input" type="password" inputMode="numeric" autoComplete="off" required value={pin} onChange={(e) => setPinValue(e.target.value)} />
          </div>
        ) : (
          <>
            <div className="field">
              <label htmlFor="email">{t("officer.email")}</label>
              <input id="email" className="input" type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
            </div>
            <div className="field">
              <label htmlFor="password">{t("officer.password")}</label>
              <input id="password" className="input" type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
            </div>
          </>
        )}
        {error && <p className="error-text" role="alert">{error}</p>}
        <button className="btn" disabled={busy}>{busy ? t("officer.signingIn") : t("officer.signIn")}</button>
        <button type="button" className="link-btn" onClick={() => setUsePin(!usePin)}>{usePin ? t("officer.signIn") : t("officer.pin")}</button>
      </form>
    </div>
  );
}

/** Signs officers in, then shows the officer tabs around the page. */
export function OfficerShell({ children, wide = true }: { children: ReactNode; wide?: boolean }) {
  const { t } = useI18n();
  const { officer, refreshOfficer } = usePortal();
  const [checked, setChecked] = useState(false);
  useEffect(() => {
    refreshOfficer().finally(() => setChecked(true));
  }, [refreshOfficer]);
  if (!checked) return <div className="wrap page"><Skeleton h={300} /></div>;
  if (!officer.signed_in) return <Login />;
  const out = async () => {
    await officerApi.logout().catch(() => {});
    await refreshOfficer();
  };
  return (
    <div className={`wrap page ${wide ? "" : "narrow"}`}>
      <div className="section-head no-print">
        <p className="small muted">{t("officer.signedInAs", { name: officer.name })}</p>
        <button className="btn ghost small" onClick={out}>{t("officer.signOut")}</button>
      </div>
      <nav className="officer-tabs" aria-label={t("nav.dashboard")}>
        <NavLink to="/officer" end>{t("officer.queue")}</NavLink>
        <NavLink to="/officer/review">{t("officer.review")}</NavLink>
        <NavLink to="/officer/work-order">{t("officer.workOrders")}</NavLink>
        <NavLink to="/officer/analytics">{t("officer.analytics")}</NavLink>
        {officer.role === "admin" && <NavLink to="/officer/team">{t("officer.team")}</NavLink>}
        {officer.role === "admin" && <NavLink to="/officer/models">AI models</NavLink>}
      </nav>
      {children}
    </div>
  );
}
