/** Leaflet map of reports. Loaded lazily (React.lazy) so the home page does not pay for it up front. */
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useMemo, useRef, useState } from "react";
import { CircleMarker, LayersControl, MapContainer, Marker, Popup, TileLayer, useMap, useMapEvents } from "react-leaflet";
import { Link } from "react-router-dom";
import { absUrl, type PublicReport, type Urgency } from "../api";
import { ago, duration, hazardLabel, statusLabel, urgencyLabel } from "../format";
import { useI18n } from "../i18n";
import { StatusBadge, UrgencyBadge } from "./Badges";
import { Icon } from "./Icons";
import { PIN_COLOURS } from "../pins";


export function pinColour(r: PublicReport): string {
  if (r.public_status === "resolved") return PIN_COLOURS.resolved;
  if (r.public_status === "dismissed") return PIN_COLOURS.dismissed;
  return PIN_COLOURS[r.urgency];
}

const HOME: [number, number] = [13.0446, 77.62];
const CELL_PX = 40;

type Located = PublicReport & { lat: number; lng: number };
type Cluster = { key: string; lat: number; lng: number; items: Located[] };

/** Groups pins that would overlap on screen at the current zoom. */
function useClusters(points: Located[]): Cluster[] {
  const map = useMap();
  const [view, setView] = useState(0);
  useMapEvents({ zoomend: () => setView((v) => v + 1), moveend: () => setView((v) => v + 1) });
  return useMemo(() => {
    void view;
    const zoom = map.getZoom();
    if (zoom >= 15) return points.map((p) => ({ key: p.code, lat: p.lat, lng: p.lng, items: [p] }));
    const cells = new Map<string, Located[]>();
    for (const p of points) {
      const pt = map.project([p.lat, p.lng], zoom);
      const key = `${Math.floor(pt.x / CELL_PX)}:${Math.floor(pt.y / CELL_PX)}`;
      cells.set(key, [...(cells.get(key) ?? []), p]);
    }
    return [...cells.entries()].map(([key, items]) => ({
      key,
      items,
      lat: items.reduce((s, i) => s + i.lat, 0) / items.length,
      lng: items.reduce((s, i) => s + i.lng, 0) / items.length,
    }));
  }, [map, points, view]);
}

function FitTo({ points, fit }: { points: Located[]; fit: boolean }) {
  const map = useMap();
  const key = fit ? points.map((p) => p.code).join("|") : "";
  useEffect(() => {
    if (!fit || !points.length) return;
    if (points.length === 1) map.setView([points[0].lat, points[0].lng], 16);
    else map.fitBounds(points.map((p) => [p.lat, p.lng] as [number, number]), { padding: [30, 30], maxZoom: 16 });
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

function Picker({ onPick }: { onPick: (lat: number, lng: number) => void }) {
  useMapEvents({ click: (e) => onPick(e.latlng.lat, e.latlng.lng) });
  return null;
}

/** A map pin (balise): a teardrop in the urgency colour, a tick when resolved, and a count when several people reported it. */
function balise(r: Located): L.DivIcon {
  const colour = pinColour(r);
  const resolved = r.public_status === "resolved";
  const mark = resolved
    ? '<path d="M10.5 16.5l4.5 4.5 8-9" fill="none" stroke="#fff" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>'
    : '<circle cx="17" cy="16" r="5.5" fill="#fff"/>';
  const count = r.reported_count > 1 ? `<i class="balise-n">${r.reported_count > 99 ? "99+" : r.reported_count}</i>` : "";
  return L.divIcon({
    className: "balise",
    html: `<svg viewBox="0 0 34 44" width="34" height="44" aria-hidden="true"><path d="M17 42C17 42 3 27 3 16a14 14 0 1 1 28 0c0 11-14 26-14 26z" fill="${colour}" stroke="#fff" stroke-width="2.5"/>${mark}</svg>${count}`,
    iconSize: [34, 44], iconAnchor: [17, 43], popupAnchor: [0, -40],
  });
}

function Pins({ points }: { points: Located[] }) {
  const { t } = useI18n();
  const map = useMap();
  const clusters = useClusters(points);
  return (
    <>
      {clusters.map((c) => c.items.length > 1 ? (
        <Marker key={c.key} position={[c.lat, c.lng]}
          icon={L.divIcon({ className: "cluster-icon", html: String(c.items.length), iconSize: [34 + Math.min(c.items.length, 30), 34 + Math.min(c.items.length, 30)] })}
          title={t("map.cluster", { n: c.items.length })}
          eventHandlers={{ click: () => map.setView([c.lat, c.lng], Math.min(map.getZoom() + 2, 18)) }} />
      ) : (
        <Marker key={c.key} position={[c.lat, c.lng]} icon={balise(c.items[0])}
          title={`${hazardLabel(t, c.items[0].hazard_type)} · ${c.items[0].code}`}
          zIndexOffset={c.items[0].public_status === "resolved" ? 0 : 500}>
          <Popup>
            <PopupBody r={c.items[0]} />
          </Popup>
        </Marker>
      ))}
    </>
  );
}

function PopupBody({ r }: { r: Located }) {
  const { t } = useI18n();
  return (
    <div className="map-pop">
      <img src={absUrl(r.after_photo_url ?? r.photo_url)} alt="" loading="lazy" />
      <b>{hazardLabel(t, r.hazard_type)} · {r.code}</b>
      <span>{urgencyLabel(t, r.urgency)} · {statusLabel(t, r.public_status)}</span>
      <span className="small">{t("map.age", { time: duration(t, Date.now() - new Date(r.created_at).getTime()) })}</span>
      <Link to={`/r/${r.code}`}>{t("map.view")}</Link>
    </div>
  );
}

/** Tells Leaflet the box changed size (entering or leaving full screen) so it redraws tiles to fill it. */
function ResizeOnChange({ full }: { full: boolean }) {
  const map = useMap();
  useEffect(() => {
    const id = setTimeout(() => map.invalidateSize(), 50);
    return () => clearTimeout(id);
  }, [full, map]);
  return null;
}

const TOUR_MS = 7000;
const RANK: Record<Urgency, number> = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 };

/** Flies the map to the current stop, pulses its pin, and pauses the tour when the visitor takes over. */
function TourDriver({ stop, onUser }: { stop: Located | null; onUser: () => void }) {
  const map = useMap();
  useEffect(() => {
    if (!stop) return;
    const phone = window.innerWidth <= 900;
    const pt = map.project([stop.lat, stop.lng], 17).add([0, phone ? map.getSize().y * 0.22 : 0]);
    map.flyTo(map.unproject(pt, 17), 17, { duration: 2.2 });
  }, [stop?.code]); // eslint-disable-line react-hooks/exhaustive-deps
  useMapEvents({ dragstart: onUser, popupopen: onUser });
  return stop ? (
    <Marker key={stop.code} position={[stop.lat, stop.lng]} interactive={false} zIndexOffset={-100}
      icon={L.divIcon({ className: "tour-pulse", html: "<i></i><i></i>", iconSize: [90, 90], iconAnchor: [45, 45] })} />
  ) : null;
}

/** The big photo card shown for the current stop. */
function TourCard({ r, i, n, playing, onPrev, onNext, onToggle }: {
  r: Located; i: number; n: number; playing: boolean; onPrev: () => void; onNext: () => void; onToggle: () => void;
}) {
  const { t } = useI18n();
  return (
    <aside className="tour-card" key={r.code} aria-live="polite">
      <div className="tour-img">
        <img className="bg" src={absUrl(r.after_photo_url ?? r.photo_url)} alt="" aria-hidden="true" />
        <img className="fg" src={absUrl(r.after_photo_url ?? r.photo_url)} alt={`${hazardLabel(t, r.hazard_type)} ${r.code}`} />
      </div>
      <div className="tour-body">
        <div className="tour-badges"><UrgencyBadge urgency={r.urgency} /><StatusBadge status={r.public_status} /></div>
        <h3>{hazardLabel(t, r.hazard_type)} · {r.code}</h3>
        <p className="small muted">{r.ward?.name ? `${r.ward.name} · ` : ""}{ago(t, r.created_at)}{r.reported_count > 1 ? ` · ${t("tour.people", { n: r.reported_count })}` : ""}</p>
        {r.repair_recommendation && <p className="small tour-rec" lang="en">{r.repair_recommendation}</p>}
        <div className="tour-controls">
          <button type="button" className="btn outline small" onClick={onPrev} aria-label={t("tour.prev")}>‹</button>
          <button type="button" className="btn outline small" onClick={onToggle}>{playing ? `❚❚ ${t("tour.pause")}` : `▶ ${t("tour.play")}`}</button>
          <button type="button" className="btn outline small" onClick={onNext} aria-label={t("tour.next")}>›</button>
          <span className="small muted">{t("tour.count", { i: i + 1, n })}</span>
          <Link className="small" to={`/r/${r.code}`}>{t("map.view")}</Link>
        </div>
      </div>
      <i className={`tour-progress ${playing ? "run" : ""}`} style={{ animationDuration: `${TOUR_MS}ms` }} />
    </aside>
  );
}

/** A list laid over the map: every report with its key facts. Clicking one flies the map there and opens its card. */
function ReportList({ items, activeCode, open, onToggle, onPick }: {
  items: Located[]; activeCode: string | null; open: boolean; onToggle: () => void; onPick: (r: Located) => void;
}) {
  const { t } = useI18n();
  const box = useRef<HTMLUListElement>(null);
  useEffect(() => {
    const el = box.current?.querySelector<HTMLElement>("[aria-current=true]");
    const c = box.current;
    if (!el || !c) return;
    if (el.offsetTop < c.scrollTop || el.offsetTop + el.offsetHeight > c.scrollTop + c.clientHeight) {
      c.scrollTo({ top: el.offsetTop - c.clientHeight / 2 + el.offsetHeight / 2, behavior: "smooth" });
    }
  }, [activeCode, open]);
  return (
    <section className={`map-list ${open ? "open" : ""}`} aria-label={t("list.mapTitle")}>
      <button type="button" className="map-list-head" onClick={onToggle} aria-expanded={open}>
        <b>{t("list.mapTitle")} ({items.length})</b><span aria-hidden="true">{open ? "−" : "+"}</span>
      </button>
      {open && (
        <ul ref={box}>
          {items.map((r) => (
            <li key={r.code}>
              <button type="button" onClick={() => onPick(r)} aria-current={r.code === activeCode}>
                <span className="dotl" style={{ background: pinColour(r) }} aria-hidden="true" />
                <span className="mi-main">
                  <b>{hazardLabel(t, r.hazard_type)} · {r.code}</b>
                  <span className="small muted">{r.ward?.name ? `${r.ward.name} · ` : ""}{urgencyLabel(t, r.urgency)} · {statusLabel(t, r.public_status)} · {ago(t, r.created_at)}</span>
                </span>
                <img src={absUrl(r.after_photo_url ?? r.photo_url)} alt="" loading="lazy" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

const LAYER_KEY = "rastescan.mapLayer";

function savedLayer(): string {
  try {
    return localStorage.getItem(LAYER_KEY) === "satellite" ? "satellite" : "street";
  } catch {
    return "street";
  }
}

/** Remembers whether the visitor last chose street or satellite. */
function RememberLayer() {
  const { t } = useI18n();
  useMapEvents({
    baselayerchange: (e) => {
      try {
        localStorage.setItem(LAYER_KEY, e.name === t("map.satellite") ? "satellite" : "street");
      } catch {
        /* private mode: the choice just is not remembered */
      }
    },
  });
  return null;
}

export default function MapView({ reports, short = false, fit = true, pick, picked, center, tour = false, present = false }: {
  reports: PublicReport[];
  short?: boolean;
  fit?: boolean;
  /** Auto-play: fly to each report in turn and show its photo card, until the visitor drags the map or pauses. */
  tour?: boolean;
  /** Open straight into full screen (for a big display at an event). */
  present?: boolean;
  pick?: (lat: number, lng: number) => void;
  picked?: [number, number] | null;
  center?: [number, number];
}) {
  const { t } = useI18n();
  const points = reports.filter((r): r is Located => r.lat !== null && r.lng !== null);
  const satellite = savedLayer() === "satellite";
  const [full, setFull] = useState(present);
  const [idx, setIdx] = useState(0);
  const [playing, setPlaying] = useState(true);
  const stopsKey = useRef("");
  const ordered = useMemo(() => {
    if (!tour) return [] as Located[];
    return reports
      .filter((r): r is Located => r.lat !== null && r.lng !== null)
      .sort((a, b) => (a.public_status === "resolved" ? 1 : 0) - (b.public_status === "resolved" ? 1 : 0)
        || RANK[a.urgency] - RANK[b.urgency] || b.created_at.localeCompare(a.created_at));
  }, [reports, tour]);
  const stops = useMemo(() => ordered.slice(0, 30), [ordered]);
  const [focus, setFocus] = useState<Located | null>(null);
  const [listOpen, setListOpen] = useState(() => window.innerWidth > 700);
  const key = stops.map((r) => r.code).join("|");
  useEffect(() => {
    if (stopsKey.current !== key) {
      stopsKey.current = key;
      setIdx(0);
    }
  }, [key]);
  useEffect(() => {
    if (!playing || stops.length < 2) return;
    const id = setTimeout(() => setIdx((i) => (i + 1) % stops.length), TOUR_MS);
    return () => clearTimeout(id);
  }, [playing, idx, stops.length]);
  const stop = focus ?? (stops.length ? stops[Math.min(idx, stops.length - 1)] : null);
  const focusIdx = focus ? stops.findIndex((r) => r.code === focus.code) : -1;
  const at = focus ? Math.max(focusIdx, 0) : Math.min(idx, Math.max(stops.length - 1, 0));
  /** Leave a hand-picked report and carry on the tour from the nearest tour stop. */
  const move = (to: number) => { setFocus(null); setIdx(((to % stops.length) + stops.length) % stops.length); };
  const choose = (r: Located) => { setPlaying(false); setFocus(r); };
  // Full screen is a fixed overlay (works on phones too). Escape leaves it, and the page behind stops scrolling.
  useEffect(() => {
    if (!full) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setFull(false);
    window.addEventListener("keydown", onKey);
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = prev;
    };
  }, [full]);
  return (
    <div className={`map-box ${short ? "short" : ""} ${full ? "full" : ""}`}>
      <MapContainer center={center ?? HOME} zoom={13} scrollWheelZoom={!short || full} style={{ height: "100%", width: "100%" }}>
        <LayersControl position="topright" collapsed={false}>
          <LayersControl.BaseLayer checked={!satellite} name={t("map.street")}>
            <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
              url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          </LayersControl.BaseLayer>
          <LayersControl.BaseLayer checked={satellite} name={t("map.satellite")}>
            <TileLayer maxZoom={19} attribution="Tiles &copy; Esri, Maxar, Earthstar Geographics and the GIS User Community"
              url="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}" />
          </LayersControl.BaseLayer>
        </LayersControl>
        <RememberLayer />
        {tour && <TourDriver stop={stop} onUser={() => setPlaying(false)} />}
        <ResizeOnChange full={full} />
        <FitTo points={points} fit={fit && !pick} />
        <Pins points={points} />
        {pick && <Picker onPick={pick} />}
        {picked && <CircleMarker center={picked} radius={11} pathOptions={{ color: "#0b2545", weight: 4, fillColor: "#f29a2e", fillOpacity: 1 }} />}
      </MapContainer>
      {tour && stop && (
        <TourCard r={stop} i={at} n={stops.length} playing={playing}
          onPrev={() => { setPlaying(false); move(at - 1); }}
          onNext={() => { setPlaying(false); move(at + 1); }}
          onToggle={() => { if (!playing) move(at); setPlaying(!playing); }} />
      )}
      {tour && ordered.length > 0 && (
        <ReportList items={ordered} activeCode={stop?.code ?? null} open={listOpen} onToggle={() => setListOpen(!listOpen)} onPick={choose} />
      )}
      <div className="map-full-bar">
        <button type="button" className="btn accent" onClick={() => setFull(!full)} aria-pressed={full}>
          <Icon name={full ? "shrink" : "expand"} size={18} /> {full ? t("map.exitFullscreen") : t("map.fullscreen")}
        </button>
      </div>
    </div>
  );
}
