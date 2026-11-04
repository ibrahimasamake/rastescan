import { useEffect, useState, type ReactNode } from "react";
import { NavLink } from "react-router-dom";
import { api } from "../api";

export function Layout({ children, wide = false }: { children: ReactNode; wide?: boolean }) {
  const [mode, setMode] = useState<string | null>(null);
  useEffect(() => {
    api.health().then((h) => setMode(h.ai_mode)).catch(() => setMode(null));
  }, []);
  return (
    <>
      <header className="topbar">
        <div className={`topbar-inner ${wide ? "wide" : ""}`}>
          <NavLink to="/" className="brand">Raste<span>Scan</span></NavLink>
          <nav>
            <NavLink to="/" end>Report</NavLink>
            <NavLink to="/dashboard">Ward dashboard</NavLink>
          </nav>
        </div>
      </header>
      {mode === "fake" && (
        <div className="test-banner">Test mode: results are sample answers, not from the AI inspector.</div>
      )}
      <main className={wide ? "wide" : ""}>{children}</main>
    </>
  );
}
