from app.config import REPO_ROOT
from app.wards import load_wards, parse_wards, ward_for


def square(code, x0, y0, x1, y1, hole=None):
    rings = [[[x0, y0], [x1, y0], [x1, y1], [x0, y1], [x0, y0]]]
    if hole:
        hx0, hy0, hx1, hy1 = hole
        rings.append([[hx0, hy0], [hx1, hy0], [hx1, hy1], [hx0, hy1], [hx0, hy0]])
    return {"type": "Feature", "properties": {"code": code, "name": code}, "geometry": {"type": "Polygon", "coordinates": rings}}


def test_point_in_polygon_with_hole_and_multipolygon():
    multi = {"type": "Feature", "properties": {"code": "M", "name": "Multi"},
             "geometry": {"type": "MultiPolygon", "coordinates": [
                 [[[20, 20], [21, 20], [21, 21], [20, 21], [20, 20]]],
                 [[[30, 30], [31, 30], [31, 31], [30, 31], [30, 30]]]]}}
    wards = parse_wards({"features": [square("A", 0, 0, 10, 10, hole=(4, 4, 6, 6)), multi]})
    assert ward_for(wards, lat=1, lng=1).code == "A"
    assert ward_for(wards, lat=5, lng=5) is None  # inside the hole
    assert ward_for(wards, lat=30.5, lng=30.5).code == "M"
    assert ward_for(wards, lat=50, lng=50) is None
    assert ward_for(wards, lat=None, lng=None) is None


def test_bad_features_are_skipped():
    wards = parse_wards({"features": [{"properties": {"name": "no code"}, "geometry": {"type": "Point", "coordinates": [0, 0]}}]})
    assert wards == []


def test_sample_file_covers_nagawara():
    wards = load_wards(REPO_ROOT / "data" / "wards.geojson")
    assert len(wards) == 6
    assert ward_for(wards, lat=13.05, lng=77.63).name == "Nagawara"
