/** The Android app download. It only shows where the server really has the file, and never inside the Android wrapper itself. */
import { useEffect, useState } from "react";
import { API_BASE } from "../api";
import { useI18n } from "../i18n";
import { Icon } from "./Icons";

const APK_URL = `${API_BASE}/api/public/rastescan.apk`;

function useAppAvailable(): boolean {
  const [available, setAvailable] = useState(false);
  useEffect(() => {
    if ("Capacitor" in window) return;
    let live = true;
    fetch(APK_URL, { method: "HEAD" })
      .then((res) => { if (live) setAvailable(res.ok); })
      .catch(() => {});
    return () => { live = false; };
  }, []);
  return available;
}

/** A plain link for the footer. */
export function AppLink() {
  const { t } = useI18n();
  if (!useAppAvailable()) return null;
  return <li><a href={APK_URL} download>{t("footer.app")}</a></li>;
}

/** The card on the Home page. */
export function AppSection() {
  const { t } = useI18n();
  if (!useAppAvailable()) return null;
  return (
    <section className="section card pad" aria-labelledby="app-h">
      <h2 id="app-h">{t("app.title")}</h2>
      <p>{t("app.lead")}</p>
      <div className="btn-row">
        <a className="btn accent" href={APK_URL} download><Icon name="camera" size={18} /> {t("app.download")}</a>
      </div>
      <p className="small muted">{t("app.hint")}</p>
    </section>
  );
}
