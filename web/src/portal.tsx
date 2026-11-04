import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { api, officerApi, type Officer, type PortalConfig, type Stats } from "./api";

interface Portal {
  config: PortalConfig | null;
  stats: Stats | null;
  officer: Officer;
  refreshStats: () => void;
  refreshOfficer: () => Promise<void>;
}

const Ctx = createContext<Portal | null>(null);

export function PortalProvider({ children }: { children: ReactNode }) {
  const [config, setConfig] = useState<PortalConfig | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [officer, setOfficer] = useState<Officer>({ signed_in: false });

  const refreshStats = useCallback(() => {
    api.stats().then(setStats).catch(() => {});
  }, []);
  const refreshOfficer = useCallback(async () => {
    try {
      setOfficer(await officerApi.me());
    } catch {
      setOfficer({ signed_in: false });
    }
  }, []);

  useEffect(() => {
    api.config().then((c) => {
      setConfig(c);
      document.title = c.site_name;
    }).catch(() => {});
    refreshStats();
    refreshOfficer();
    const id = setInterval(() => document.visibilityState === "visible" && refreshStats(), 30000);
    return () => clearInterval(id);
  }, [refreshStats, refreshOfficer]);

  return <Ctx.Provider value={{ config, stats, officer, refreshStats, refreshOfficer }}>{children}</Ctx.Provider>;
}

export function usePortal(): Portal {
  const v = useContext(Ctx);
  if (!v) throw new Error("usePortal outside PortalProvider");
  return v;
}
