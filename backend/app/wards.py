"""Ward lookup: which ward polygon a report's GPS point falls in.

Wards come from a GeoJSON FeatureCollection (data/wards.geojson by default). Each feature needs
properties.code and properties.name, and a Polygon or MultiPolygon geometry in longitude/latitude order.
"""
import json
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("rastescan")


@dataclass(frozen=True)
class Ward:
    code: str
    name: str
    polygons: tuple  # tuple of polygons; each polygon is a tuple of rings; each ring a tuple of (lng, lat)
    bbox: tuple[float, float, float, float]  # min_lng, min_lat, max_lng, max_lat

    @property
    def centroid(self) -> tuple[float, float]:
        """Rough centre (lat, lng) of the bounding box, good enough for map labels and route starts."""
        return ((self.bbox[1] + self.bbox[3]) / 2, (self.bbox[0] + self.bbox[2]) / 2)


def _ring_contains(ring: tuple, lng: float, lat: float) -> bool:
    """Ray casting. Points exactly on an edge may fall either side, which is fine for wards."""
    inside = False
    j = len(ring) - 1
    for i in range(len(ring)):
        xi, yi = ring[i]
        xj, yj = ring[j]
        if (yi > lat) != (yj > lat) and lng < (xj - xi) * (lat - yi) / (yj - yi) + xi:
            inside = not inside
        j = i
    return inside


def _polygon_contains(polygon: tuple, lng: float, lat: float) -> bool:
    outer, *holes = polygon
    return _ring_contains(outer, lng, lat) and not any(_ring_contains(h, lng, lat) for h in holes)


def parse_wards(doc: dict) -> list[Ward]:
    wards = []
    for feature in doc.get("features", []):
        props = feature.get("properties") or {}
        geom = feature.get("geometry") or {}
        code, name = props.get("code"), props.get("name")
        if not code or not name or geom.get("type") not in ("Polygon", "MultiPolygon"):
            log.warning("skipping ward feature without code, name or polygon: %s", props)
            continue
        raw = [geom["coordinates"]] if geom["type"] == "Polygon" else geom["coordinates"]
        polygons = tuple(tuple(tuple((float(p[0]), float(p[1])) for p in ring) for ring in poly) for poly in raw)
        points = [p for poly in polygons for p in poly[0]]
        bbox = (min(p[0] for p in points), min(p[1] for p in points), max(p[0] for p in points), max(p[1] for p in points))
        wards.append(Ward(str(code), str(name), polygons, bbox))
    return wards


def load_wards(path: Path) -> list[Ward]:
    if not path.is_file():
        log.warning("ward file %s not found; reports will have no ward", path)
        return []
    return parse_wards(json.loads(path.read_text(encoding="utf-8")))


def ward_for(wards: list[Ward], lat: float | None, lng: float | None) -> Ward | None:
    if lat is None or lng is None:
        return None
    for w in wards:
        b = w.bbox
        if b[0] <= lng <= b[2] and b[1] <= lat <= b[3] and any(_polygon_contains(p, lng, lat) for p in w.polygons):
            return w
    return None
