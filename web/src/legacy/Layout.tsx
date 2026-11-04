import type { ReactNode } from "react";

/** Old dashboard wrapper; the portal layout now comes from the router. */
export function Layout({ children }: { children: ReactNode; wide?: boolean }) {
  return <div className="wrap page">{children}</div>;
}
