/** Leaflet map of reports. Loaded lazily (React.lazy) so the home page does not pay for it up front. */
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useMemo, useState } from "react";
import { CircleMarker, LayersControl, MapContainer, Marker, Popup, TileLayer, useMap, useMapEvents } from "react-leaflet";
import { Link } from "react-router-dom";
import { absUrl, type PublicReport } from "../api";
import { duration, hazardLabel, statusLabel, urgencyLabel } from "../format";
import { useI18n } from "../i18n";
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

export default function MapView({ reports, short = false, fit = true, pick, picked, center }: {
  reports: PublicReport[];
  short?: boolean;
  fit?: boolean;
  pick?: (lat: number, lng: number) => void;
  picked?: [number, number] | null;
  center?: [number, number];
}) {
  const { t } = useI18n();
  const points = reports.filter((r): r is Located => r.lat !== null && r.lng !== null);
  const satellite = savedLayer() === "satellite";
  return (
    <div className={`map-box ${short ? "short" : ""}`}>
      <MapContainer center={center ?? HOME} zoom={13} scrollWheelZoom={!short} style={{ height: "100%", width: "100%" }}>
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
        <FitTo points={points} fit={fit && !pick} />
        <Pins points={points} />
        {pick && <Picker onPick={pick} />}
        {picked && <CircleMarker center={picked} radius={11} pathOptions={{ color: "#0b2545", weight: 4, fillColor: "#f29a2e", fillOpacity: 1 }} />}
      </MapContainer>
    </div>
  );
}
