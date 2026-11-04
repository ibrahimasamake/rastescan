/** Leaflet map of reports. Loaded lazily (React.lazy) so the home page does not pay for it up front. */
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import { useEffect, useMemo, useState } from "react";
import { CircleMarker, MapContainer, Marker, Popup, TileLayer, useMap, useMapEvents } from "react-leaflet";
import { Link } from "react-router-dom";
import { absUrl, type PublicReport } from "../api";
import { duration, hazardLabel, statusLabel, urgencyLabel } from "../format";
import { useI18n } from "../i18n";

export const PIN_COLOURS: Record<string, string> = {
  CRITICAL: "#a3161a", HIGH: "#c2510f", MEDIUM: "#b88400", LOW: "#5b7a99", resolved: "#2e8b57", dismissed: "#8a94a1",
};

export function pinColour(r: PublicReport): string {
  if (r.public_status === "resolved") return PIN_COLOURS.resolved;
  if (r.public_status === "dismissed") return PIN_COLOURS.dismissed;
  return PIN_COLOURS[r.urgency];
}

const HOME: [number, number] = [13.0446, 77.62];
const CELL_PX = 56;

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
    if (zoom >= 16) return points.map((p) => ({ key: p.code, lat: p.lat, lng: p.lng, items: [p] }));
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
        <CircleMarker key={c.key} center={[c.lat, c.lng]} radius={8 + Math.min(c.items[0].reported_count, 5)}
          pathOptions={{ color: "#fff", weight: 2, fillColor: pinColour(c.items[0]), fillOpacity: 0.95 }}>
          <Popup>
            <PopupBody r={c.items[0]} />
          </Popup>
        </CircleMarker>
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

export default function MapView({ reports, short = false, fit = true, pick, picked, center }: {
  reports: PublicReport[];
  short?: boolean;
  fit?: boolean;
  pick?: (lat: number, lng: number) => void;
  picked?: [number, number] | null;
  center?: [number, number];
}) {
  const points = reports.filter((r): r is Located => r.lat !== null && r.lng !== null);
  return (
    <div className={`map-box ${short ? "short" : ""}`}>
      <MapContainer center={center ?? HOME} zoom={13} scrollWheelZoom={!short} style={{ height: "100%", width: "100%" }}>
        <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
        <FitTo points={points} fit={fit && !pick} />
        <Pins points={points} />
        {pick && <Picker onPick={pick} />}
        {picked && <CircleMarker center={picked} radius={11} pathOptions={{ color: "#0b2545", weight: 4, fillColor: "#f29a2e", fillOpacity: 1 }} />}
      </MapContainer>
    </div>
  );
}
