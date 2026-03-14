"""
Tests for glod/feature.py

Run with:  pytest test_feature.py -v
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import pytest

from glod.feature import (
    Feature,
)
from glod.geometry import LineString, Point

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def point_feature():
    return Feature(
        geometry=Point.from_geojson(
            {"type": "Point", "coordinates": [1, 2]}, crs="epsg:27700"
        ),
        attributes={"name": "A", "value": 42},
    )


@pytest.fixture
def line_feature():
    return Feature(
        geometry=LineString.from_geojson(
            {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}, crs="epsg:27700"
        ),
        attributes={"id": 1},
    )


# ---------------------------------------------------------------------------
# Feature construction
# ---------------------------------------------------------------------------


class TestFeatureInit:
    def test_geometry_is_stored(self, point_feature):
        assert isinstance(point_feature.geometry, Point)

    def test_attributes_are_stored(self, point_feature):
        assert point_feature.attributes == {"name": "A", "value": 42}

    def test_attributes_default_to_empty_dict(self):
        f = Feature(
            geometry=Point.from_geojson({"type": "Point", "coordinates": [1, 2]})
        )
        assert f.attributes == {}

    def test_attributes_are_copied(self):
        original = {"x": 1}
        f = Feature(
            geometry=Point.from_geojson({"type": "Point", "coordinates": [1, 2]}),
            attributes=original,
        )
        f.attributes["x"] = 99
        assert original["x"] == 1  # original not mutated

    def test_repr(self, point_feature):
        r = repr(point_feature)
        assert "Point" in r
        assert "name" in r


class TestFeatureSetters:
    def test_geometry_setter_accepts_geometry(self, point_feature):
        new_geom = Point.from_geojson(
            {"type": "Point", "coordinates": [9, 9]}, crs="epsg:27700"
        )
        point_feature.geometry = new_geom
        assert point_feature.geometry.wkt == "POINT (9 9)"

    def test_geometry_setter_rejects_non_geometry(self, point_feature):
        with pytest.raises(TypeError, match="Geometry instance"):
            point_feature.geometry = "POINT (1 2)"

    def test_attributes_setter_accepts_dict(self, point_feature):
        point_feature.attributes = {"new": "value"}
        assert point_feature.attributes == {"new": "value"}

    def test_attributes_setter_rejects_non_dict(self, point_feature):
        with pytest.raises(TypeError, match="dict"):
            point_feature.attributes = ["a", "b"]

    def test_attributes_setter_copies_dict(self, point_feature):
        d = {"x": 1}
        point_feature.attributes = d
        point_feature.attributes["x"] = 99
        assert d["x"] == 1  # original not mutated


class TestFeatureEquality:
    def test_equal_features(self):
        f1 = Feature(
            Point.from_geojson({"type": "Point", "coordinates": [1, 2]}), {"a": 1}
        )
        f2 = Feature(
            Point.from_geojson({"type": "Point", "coordinates": [1, 2]}), {"a": 1}
        )
        assert f1 == f2

    def test_different_geometry(self):
        f1 = Feature(
            Point.from_geojson({"type": "Point", "coordinates": [1, 2]}), {"a": 1}
        )
        f2 = Feature(
            Point.from_geojson({"type": "Point", "coordinates": [3, 4]}), {"a": 1}
        )
        assert f1 != f2

    def test_different_attributes(self):
        f1 = Feature(
            Point.from_geojson({"type": "Point", "coordinates": [1, 2]}), {"a": 1}
        )
        f2 = Feature(
            Point.from_geojson({"type": "Point", "coordinates": [1, 2]}), {"a": 2}
        )
        assert f1 != f2

    def test_not_equal_to_non_feature(self, point_feature):
        assert point_feature != "not a feature"


class TestFeatureFromGeoJSON:
    def test_basic(self):
        f = Feature.from_geojson(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1, 2]},
                "properties": {"x": 1},
            }
        )
        assert isinstance(f.geometry, Point)
        assert f.attributes == {"x": 1}

    def test_crs_passed_through(self):
        f = Feature.from_geojson(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1, 2]},
                "properties": {},
            },
            crs="epsg:27700",
        )
        assert f.geometry.crs == "EPSG:27700"

    def test_null_properties_become_empty_dict(self):
        f = Feature.from_geojson(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1, 2]},
                "properties": None,
            }
        )
        assert f.attributes == {}

    def test_missing_properties_become_empty_dict(self):
        f = Feature.from_geojson(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1, 2]},
            }
        )
        assert f.attributes == {}

    def test_wrong_type_raises(self):
        with pytest.raises(ValueError, match="Feature"):
            Feature.from_geojson({"type": "FeatureCollection", "features": []})

    def test_null_geometry_raises(self):
        with pytest.raises(ValueError, match="geometry"):
            Feature.from_geojson(
                {"type": "Feature", "geometry": None, "properties": {}}
            )

    def test_missing_geometry_raises(self):
        with pytest.raises(ValueError, match="geometry"):
            Feature.from_geojson({"type": "Feature", "properties": {}})


class TestFeatureFromWKT:
    def test_basic(self):
        f = Feature.from_wkt("POINT (1 2)", attributes={"id": 1}, crs="epsg:27700")
        assert isinstance(f.geometry, Point)
        assert f.attributes == {"id": 1}
        assert f.geometry.crs == "EPSG:27700"

    def test_no_attributes(self):
        f = Feature.from_wkt("POINT (1 2)")
        assert f.attributes == {}


# ---------------------------------------------------------------------------
# Feature serialisation
# ---------------------------------------------------------------------------


class TestFeatureToGeoJSON:
    def test_type_is_feature(self, point_feature):
        assert point_feature.to_geojson()["type"] == "Feature"

    def test_geometry_is_present(self, point_feature):
        geojson = point_feature.to_geojson()
        assert geojson["geometry"]["type"] == "Point"
        assert geojson["geometry"]["coordinates"] == [1, 2]

    def test_properties_are_present(self, point_feature):
        assert point_feature.to_geojson()["properties"] == {"name": "A", "value": 42}

    def test_geo_interface(self, point_feature):
        assert point_feature.__geo_interface__ == point_feature.to_geojson()
