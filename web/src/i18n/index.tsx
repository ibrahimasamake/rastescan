import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { en, type Dict, type Key } from "./en";

export type Lang = "en" | "kn" | "hi";
export const LANGS: { code: Lang; label: string; locale: string }[] = [
  { code: "en", label: "English", locale: "en-IN" },
  { code: "kn", label: "ಕನ್ನಡ", locale: "kn-IN" },
  { code: "hi", label: "हिन्दी", locale: "hi-IN" },
];
export type TextSize = "sm" | "md" | "lg" | "xl";

const loaders: Record<Lang, () => Promise<Dict>> = {
  en: async () => en,
  kn: async () => (await import("./kn")).kn,
  hi: async () => (await import("./hi")).hi,
};

function readPref<T extends string>(key: string, allowed: readonly T[], fallback: T): T {
  try {
    const v = localStorage.getItem(key) as T | null;
    return v && allowed.includes(v) ? v : fallback;
  } catch {
    return fallback;
  }
}

function writePref(key: string, value: string) {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* not saved; still works for this visit */
  }
}

export type Vars = Record<string, string | number | null | undefined>;

interface I18n {
  lang: Lang;
  locale: string;
  setLang: (l: Lang) => void;
  size: TextSize;
  setSize: (s: TextSize) => void;
  t: (key: Key, vars?: Vars) => string;
  num: (n: number, digits?: number) => string;
  date: (iso: string, withTime?: boolean) => string;
}

const Ctx = createContext<I18n | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => readPref("rs-lang", ["en", "kn", "hi"] as const, "en"));
  const [size, setSizeState] = useState<TextSize>(() => readPref("rs-size", ["sm", "md", "lg", "xl"] as const, "md"));
  const [dict, setDict] = useState<Dict>(en);

  useEffect(() => {
    let live = true;
    loaders[lang]().then((d) => live && setDict(d));
    document.documentElement.lang = lang;
    return () => {
      live = false;
    };
  }, [lang]);

  useEffect(() => {
    document.documentElement.dataset.size = size;
  }, [size]);

  const locale = LANGS.find((l) => l.code === lang)!.locale;
  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    writePref("rs-lang", l);
  }, []);
  const setSize = useCallback((s: TextSize) => {
    setSizeState(s);
    writePref("rs-size", s);
  }, []);

  const value = useMemo<I18n>(() => {
    const t = (key: Key, vars?: Vars) => {
      let s: string = dict[key] ?? en[key] ?? key;
      if (vars) for (const [k, v] of Object.entries(vars)) s = s.split(`{${k}}`).join(v == null ? "" : String(v));
      return s;
    };
    const num = (n: number, digits = 0) => new Intl.NumberFormat(locale, { maximumFractionDigits: digits }).format(n);
    const date = (iso: string, withTime = false) =>
      new Intl.DateTimeFormat(locale, withTime ? { dateStyle: "medium", timeStyle: "short" } : { dateStyle: "medium" }).format(new Date(iso));
    return { lang, locale, setLang, size, setSize, t, num, date };
  }, [dict, lang, locale, setLang, size, setSize]);

  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useI18n(): I18n {
  const v = useContext(Ctx);
  if (!v) throw new Error("useI18n outside I18nProvider");
  return v;
}

export type { Key };
