/** PIN code, state, district and road for a report's pin. The server looks it up once per location and keeps the answer, so this
 *  is the nearest known address to the pin. A missing answer just leaves those rows out. */
import { useEffect, useState } from "react";
import { absUrl } from "./api";

export interface Address {
  road?: string | null;
  area?: string | null;
  city?: string | null;
  district?: string | null;
  state?: string | null;
  pin?: string | null;
}

const known = new Map<string, Promise<Address | null>>();

export function lookupAddress(code: string): Promise<Address | null> {
  let found = known.get(code);
  if (!found) {
    found = fetch(absUrl(`/api/public/reports/${encodeURIComponent(code)}/address`))
      .then((res) => (res.ok ? (res.json() as Promise<Address>) : null))
      .catch(() => null);
    // Keep only real answers, so a dropped connection can be tried again.
    found.then((a) => { if (!a || !a.state) known.delete(code); });
    known.set(code, found);
  }
  return found;
}

/** The address that came with the report, or, for a report too new to have one yet, the answer to asking the server for it. */
export function useAddress(code: string, withReport: Address | null | undefined): Address | null {
  const has = !!(withReport?.pin || withReport?.state);
  const [asked, setAsked] = useState<Address | null>(null);
  useEffect(() => {
    if (has) return;
    let live = true;
    lookupAddress(code).then((a) => { if (live) setAsked(a); });
    return () => { live = false; };
  }, [code, has]);
  return has ? withReport ?? null : asked;
}
