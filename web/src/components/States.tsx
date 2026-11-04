import { useCallback, useEffect, useRef, useState, type DependencyList } from "react";
import { ApiError } from "../api";
import { useI18n } from "../i18n";

export function Skeleton({ h = 18, w = "100%" }: { h?: number | string; w?: number | string }) {
  return <div className="skeleton" style={{ height: h, width: w }} aria-hidden="true" />;
}

export function Empty({ children }: { children: React.ReactNode }) {
  return <div className="empty">{children}</div>;
}

export function ErrorBox({ error, retry }: { error: unknown; retry?: () => void }) {
  const { t } = useI18n();
  const offline = error instanceof ApiError && error.status === 0;
  return (
    <div className="error-box" role="alert">
      <p>{offline ? t("common.offline") : error instanceof ApiError && error.status >= 400 && error.status < 500 ? error.message : t("common.error")}</p>
      {retry && <button className="btn outline small" onClick={retry}>{t("common.retry")}</button>}
    </div>
  );
}

/** Loads data, keeps the last good value while reloading, and exposes reload(). */
export function useAsync<T>(fn: () => Promise<T>, deps: DependencyList, refreshMs = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  fnRef.current = fn;
  const load = useCallback(() => {
    setLoading(true);
    fnRef.current()
      .then((d) => { setData(d); setError(null); })
      .catch((e) => setError(e))
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    load();
    if (!refreshMs) return;
    const id = setInterval(() => { if (document.visibilityState === "visible") load(); }, refreshMs);
    return () => clearInterval(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  return { data, error, loading, reload: load, setData };
}

export function useToast(): [string | null, (msg: string) => void] {
  const [msg, setMsg] = useState<string | null>(null);
  useEffect(() => {
    if (!msg) return;
    const id = setTimeout(() => setMsg(null), 3000);
    return () => clearTimeout(id);
  }, [msg]);
  return [msg, setMsg];
}

export function Toast({ msg }: { msg: string | null }) {
  return msg ? <div className="toast" role="status">{msg}</div> : null;
}
