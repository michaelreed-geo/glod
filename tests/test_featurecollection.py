"""
Tests for glod/featurecollection.py

Run with:  pytest test_featurecollection.py -v
"""

import csv
import json
import os
import sys
import tempfile
import unittest.mock as mock
import warnings

sys.path.insert(0, os.path.dirname(__file__))

import pytest

from glod.feature import Feature
from glod.featurecollection import (
    FeatureCollection,
    _crs_from_geojson,
    _most_common_crs,
    _normalise_crs,
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


@pytest.fixture
def simple_fc(point_feature, line_feature):
    return FeatureCollection([point_feature, line_feature])


@pytest.fixture
def geojson_fc_dict():
    return {
        "type": "FeatureCollection",
        "crs": {"type": "name", "properties": {"name": "epsg:27700"}},
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1, 2]},
                "properties": {"id": 1},
            },
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [3, 4]},
                "properties": {"id": 2},
            },
        ],
    }


# ---------------------------------------------------------------------------
# FeatureCollection construction
# ---------------------------------------------------------------------------


class TestFeatureCollectionInit:
    def test_features_stored(self, simple_fc):
        assert len(simple_fc) == 2

    def test_metadata_defaults_to_empty_dict(self, simple_fc):
        assert simple_fc.metadata == {}

    def test_iteration(self, simple_fc):
        features = list(simple_fc)
        assert len(features) == 2
        assert features[0].geometry.wkt == "POINT (1 2)"

    def test_indexing(self, simple_fc):
        assert simple_fc[1].geometry.wkt == "LINESTRING (0 0, 1 1)"

    def test_len(self, simple_fc):
        assert len(simple_fc) == 2

    def test_repr(self, simple_fc):
        r = repr(simple_fc)
        assert "2 features" in r
        assert "epsg:27700" in r


class TestFeatureCollectionSetters:
    def test_features_setter_accepts_list_of_features(
        self, point_feature, line_feature
    ):
        fc = FeatureCollection([point_feature])
        fc.features = [point_feature, line_feature]
        assert len(fc) == 2

    def test_features_setter_rejects_non_list(self, point_feature):
        fc = FeatureCollection([point_feature])
        with pytest.raises(TypeError, match="list"):
            fc.features = point_feature

    def test_features_setter_rejects_non_feature_items(self, point_feature):
        fc = FeatureCollection([point_feature])
        with pytest.raises(TypeError, match="Feature instances"):
            fc.features = [point_feature, "not a feature"]

    def test_metadata_setter_accepts_dict(self, simple_fc):
        simple_fc.metadata = {"source": "test"}
        assert simple_fc.metadata == {"source": "test"}

    def test_metadata_setter_rejects_non_dict(self, simple_fc):
        with pytest.raises(TypeError, match="dict"):
            simple_fc.metadata = "not a dict"

    def test_metadata_setter_copies_dict(self, simple_fc):
        d = {"x": 1}
        simple_fc.metadata = d
        simple_fc.metadata["x"] = 99
        assert d["x"] == 1


class TestFeatureCollectionAppendRemove:
    def test_append_feature(self, simple_fc, point_feature):
        initial_len = len(simple_fc)
        new_f = Feature(
            Point.from_geojson(
                {"type": "Point", "coordinates": [5, 6]}, crs="epsg:27700"
            ),
            {},
        )
        simple_fc.append(new_f)
        assert len(simple_fc) == initial_len + 1
        assert simple_fc[-1].geometry.wkt == "POINT (5 6)"

    def test_append_rejects_non_feature(self, simple_fc):
        with pytest.raises(TypeError, match="Feature instances"):
            simple_fc.append("not a feature")

    def test_remove_feature(self, simple_fc):
        f = simple_fc[0]
        simple_fc.remove(f)
        assert len(simple_fc) == 1

    def test_remove_absent_feature_raises(self, simple_fc):
        absent = Feature(
            Point.from_geojson({"type": "Point", "coordinates": [99, 99]}), {}
        )
        with pytest.raises(ValueError):
            simple_fc.remove(absent)


class TestFeatureCollectionEquality:
    def test_equal_collections(self, geojson_fc_dict):
        fc1 = FeatureCollection.from_geojson(geojson_fc_dict)
        fc2 = FeatureCollection.from_geojson(geojson_fc_dict)
        assert fc1 == fc2

    def test_different_features(self, geojson_fc_dict):
        fc1 = FeatureCollection.from_geojson(geojson_fc_dict)
        fc2 = FeatureCollection.from_geojson(geojson_fc_dict)
        fc2.features[0].attributes["id"] = 999
        assert fc1 != fc2

    def test_not_equal_to_non_collection(self, simple_fc):
        assert simple_fc != []


# ---------------------------------------------------------------------------
# FeatureCollection.crs (derived property)
# ---------------------------------------------------------------------------


class TestFeatureCollectionCRS:
    def test_uniform_crs_returned(self, simple_fc):
        assert simple_fc.crs == "epsg:27700"

    def test_mixed_crs_returns_none(self):
        fc = FeatureCollection(
            [
                Feature(
                    Point.from_geojson(
                        {"type": "Point", "coordinates": [1, 2]}, crs="epsg:27700"
                    ),
                    {},
                ),
                Feature(
                    Point.from_geojson(
                        {"type": "Point", "coordinates": [0, 51]}, crs="epsg:4326"
                    ),
                    {},
                ),
            ]
        )
        assert fc.crs is None

    def test_empty_collection_returns_none(self):
        assert FeatureCollection([]).crs is None

    def test_all_none_crs_returns_none(self):
        fc = FeatureCollection(
            [
                Feature(
                    Point.from_geojson({"type": "Point", "coordinates": [1, 2]}), {}
                ),
                Feature(
                    Point.from_geojson({"type": "Point", "coordinates": [3, 4]}), {}
                ),
            ]
        )
        assert fc.crs is None

    def test_crs_updates_when_feature_geometry_changes(self):
        fc = FeatureCollection(
            [
                Feature(
                    Point.from_geojson(
                        {"type": "Point", "coordinates": [1, 2]}, crs="epsg:27700"
                    ),
                    {},
                ),
            ]
        )
        assert fc.crs == "epsg:27700"
        fc[0].geometry = Point.from_geojson(
            {"type": "Point", "coordinates": [1, 2]}, crs="epsg:4326"
        )
        assert fc.crs == "epsg:4326"

    def test_crs_is_read_only(self, simple_fc):
        with pytest.raises(AttributeError):
            simple_fc.crs = "epsg:4326"


# ---------------------------------------------------------------------------
# FeatureCollection I/O
# ---------------------------------------------------------------------------


class TestFeatureCollectionFromGeoJSON:
    def test_from_dict(self, geojson_fc_dict):
        fc = FeatureCollection.from_geojson(geojson_fc_dict)
        assert len(fc) == 2
        assert fc.crs == "epsg:27700"

    def test_crs_propagated_to_features(self, geojson_fc_dict):
        fc = FeatureCollection.from_geojson(geojson_fc_dict)
        assert fc[0].geometry.crs == "epsg:27700"
        assert fc[1].geometry.crs == "epsg:27700"

    def test_from_json_string(self, geojson_fc_dict):
        fc = FeatureCollection.from_geojson(json.dumps(geojson_fc_dict))
        assert len(fc) == 2

    def test_from_file(self, geojson_fc_dict):
        with tempfile.NamedTemporaryFile(
            suffix=".geojson", delete=False, mode="w"
        ) as tmp:
            json.dump(geojson_fc_dict, tmp)
            tmppath = tmp.name
        try:
            fc = FeatureCollection.from_geojson(tmppath)
            assert len(fc) == 2
        finally:
            os.unlink(tmppath)

    def test_no_crs_field_gives_none(self):
        fc = FeatureCollection.from_geojson(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": {"type": "Point", "coordinates": [0, 0]},
                        "properties": {},
                    },
                ],
            }
        )
        assert fc.crs is None
        assert fc[0].geometry.crs is None

    def test_wrong_type_raises(self):
        with pytest.raises(ValueError, match="FeatureCollection"):
            FeatureCollection.from_geojson(
                {"type": "Feature", "geometry": None, "properties": {}}
            )

    def test_attributes_are_loaded(self, geojson_fc_dict):
        fc = FeatureCollection.from_geojson(geojson_fc_dict)
        assert fc[0].attributes == {"id": 1}
        assert fc[1].attributes == {"id": 2}


class TestFeatureCollectionFromCSV:
    def _write_csv(self, rows, fieldnames):
        tmp = tempfile.NamedTemporaryFile(
            suffix=".csv", delete=False, mode="w", newline="", encoding="utf-8"
        )
        writer = csv.DictWriter(tmp, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
        tmp.close()
        return tmp.name

    def test_basic(self):
        path = self._write_csv(
            [
                {"geometry": "POINT (1 2)", "name": "A"},
                {"geometry": "POINT (3 4)", "name": "B"},
            ],
            fieldnames=["geometry", "name"],
        )
        try:
            fc = FeatureCollection.from_csv(path)
            assert len(fc) == 2
            assert fc[0].geometry.wkt == "POINT (1 2)"
            assert fc[0].attributes == {"name": "A"}
        finally:
            os.unlink(path)

    def test_crs_assigned(self):
        path = self._write_csv(
            [{"geometry": "POINT (1 2)", "id": "1"}],
            fieldnames=["geometry", "id"],
        )
        try:
            fc = FeatureCollection.from_csv(path, crs="epsg:27700")
            assert fc[0].geometry.crs == "epsg:27700"
            assert fc.crs == "epsg:27700"
        finally:
            os.unlink(path)

    def test_custom_geometry_column(self):
        path = self._write_csv(
            [{"wkt": "POINT (1 2)", "id": "1"}],
            fieldnames=["wkt", "id"],
        )
        try:
            fc = FeatureCollection.from_csv(path, geometry_column="wkt")
            assert fc[0].geometry.wkt == "POINT (1 2)"
            assert "wkt" not in fc[0].attributes
        finally:
            os.unlink(path)

    def test_missing_geometry_column_raises(self):
        path = self._write_csv(
            [{"x": "1", "y": "2"}],
            fieldnames=["x", "y"],
        )
        try:
            with pytest.raises(ValueError, match="geometry"):
                FeatureCollection.from_csv(path)
        finally:
            os.unlink(path)


class TestFeatureCollectionToGeoJSON:
    def test_type(self, simple_fc):
        assert simple_fc.to_geojson()["type"] == "FeatureCollection"

    def test_feature_count(self, simple_fc):
        assert len(simple_fc.to_geojson()["features"]) == 2

    def test_crs_written(self, simple_fc):
        out = simple_fc.to_geojson()
        assert out["crs"]["properties"]["name"] == "epsg:27700"

    def test_no_crs_omits_crs_field(self):
        fc = FeatureCollection(
            [Feature(Point.from_geojson({"type": "Point", "coordinates": [1, 2]}), {})]
        )
        out = fc.to_geojson()
        assert "crs" not in out

    def test_writes_to_file(self, simple_fc):
        with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as tmp:
            tmppath = tmp.name
        try:
            simple_fc.to_geojson(path=tmppath)
            with open(tmppath) as f:
                loaded = json.load(f)
            assert loaded["type"] == "FeatureCollection"
            assert len(loaded["features"]) == 2
        finally:
            os.unlink(tmppath)
        
    def test_fmt_as_string(self, simple_fc):
        expected = '{"type": "FeatureCollection", ' \
        '"crs": {"type": "name", "properties": {"name": "EPSG:27700"}}, ' \
        '"features": [' \
        '{"type": "Feature", "geometry": {"type": "Point", "coordinates": [1, 2]}, "properties": {"name": "A", "value": 42}}, ' \
        '{"type": "Feature", "geometry": {"type": "LineString", "coordinates": [[0, 0], [1, 1]]}, "properties": {"id": 1}}' \
        ']}'
        assert simple_fc.to_geojson(fmt="str") == expected

    def test_metadata_written(self):
        fc = FeatureCollection(
            [Feature(Point.from_geojson({"type": "Point", "coordinates": [1, 2]}), {})],
            metadata={"source": "test"},
        )
        out = fc.to_geojson()
        assert out["metadata"] == {"source": "test"}

    def test_roundtrip(self, geojson_fc_dict):
        fc = FeatureCollection.from_geojson(geojson_fc_dict)
        out = fc.to_geojson()
        fc2 = FeatureCollection.from_geojson(out)
        assert len(fc2) == len(fc)
        assert fc2[0].geometry.wkt == fc[0].geometry.wkt
        assert fc2[0].attributes == fc[0].attributes


class TestFeatureCollectionToCSV:
    def test_basic(self, simple_fc):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            path = tmp.name
        try:
            simple_fc.to_csv(path)
            with open(path, newline="") as f:
                rows = list(csv.DictReader(f))
            assert len(rows) == 2
            assert rows[0]["geometry"] == "POINT (1 2)"
            assert rows[0]["name"] == "A"
        finally:
            os.unlink(path)

    def test_custom_geometry_column(self, simple_fc):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            path = tmp.name
        try:
            simple_fc.to_csv(path, geometry_column="wkt")
            with open(path, newline="") as f:
                reader = csv.DictReader(f)
                assert "wkt" in reader.fieldnames
                assert "geometry" not in reader.fieldnames
        finally:
            os.unlink(path)

    def test_geometry_column_is_first(self, simple_fc):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            path = tmp.name
        try:
            simple_fc.to_csv(path)
            with open(path, newline="") as f:
                reader = csv.DictReader(f)
                assert reader.fieldnames[0] == "geometry"
        finally:
            os.unlink(path)

    def test_sparse_attributes_written(self):
        fc = FeatureCollection(
            [
                Feature(
                    Point.from_geojson({"type": "Point", "coordinates": [1, 2]}),
                    {"a": 1},
                ),
                Feature(
                    Point.from_geojson({"type": "Point", "coordinates": [3, 4]}),
                    {"b": 2},
                ),
            ]
        )
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            path = tmp.name
        try:
            fc.to_csv(path)
            with open(path, newline="") as f:
                reader = csv.DictReader(f)
                rows = list(reader)
            assert "a" in reader.fieldnames
            assert "b" in reader.fieldnames
            assert rows[0]["a"] == "1"
            assert rows[0]["b"] == ""
        finally:
            os.unlink(path)

    def test_empty_collection_raises(self):
        fc = FeatureCollection([])
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            path = tmp.name
        try:
            with pytest.raises(ValueError, match="empty"):
                fc.to_csv(path)
        finally:
            os.unlink(path)

    def test_csv_roundtrip(self, simple_fc):
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            path = tmp.name
        try:
            simple_fc.to_csv(path)
            fc2 = FeatureCollection.from_csv(path, crs="epsg:27700")
            assert len(fc2) == len(simple_fc)
            assert fc2[0].geometry.wkt == simple_fc[0].geometry.wkt
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# CRS normalisation helpers
# ---------------------------------------------------------------------------


class TestNormaliseCRS:
    def setup_method(self):
        import glod.config

        glod.config.USE_PYPROJ = False

    def test_uniform_crs_returns_original_list(self):
        features = [
            Feature(
                Point.from_geojson(
                    {"type": "Point", "coordinates": [1, 2]}, crs="epsg:27700"
                ),
                {},
            ),
            Feature(
                Point.from_geojson(
                    {"type": "Point", "coordinates": [3, 4]}, crs="epsg:27700"
                ),
                {},
            ),
        ]
        result = _normalise_crs(features, target_crs="epsg:27700")
        assert result is features

    def test_mixed_crs_pyproj_disabled_warns(self):
        import glod.config

        glod.config.USE_PYPROJ = False
        features = [
            Feature(
                Point.from_geojson(
                    {"type": "Point", "coordinates": [1, 2]}, crs="epsg:27700"
                ),
                {},
            ),
            Feature(
                Point.from_geojson(
                    {"type": "Point", "coordinates": [0, 51]}, crs="epsg:4326"
                ),
                {},
            ),
        ]
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            result = _normalise_crs(features, target_crs="epsg:27700")
        assert any("mixed CRS" in str(warning.message) for warning in w)
        assert result is features

    def test_mixed_crs_pyproj_enabled_transforms(self):
        import glod.config

        glod.config.USE_PYPROJ = True
        features = [
            Feature(
                Point.from_geojson(
                    {"type": "Point", "coordinates": [1, 2]}, crs="epsg:27700"
                ),
                {"id": 1},
            ),
            Feature(
                Point.from_geojson(
                    {"type": "Point", "coordinates": [3, 4]}, crs="epsg:4326"
                ),
                {"id": 2},
            ),
        ]
        fake_pyproj = mock.MagicMock()
        fake_t = mock.MagicMock()
        fake_t.transform.return_value = (500000.0, 200000.0)
        fake_pyproj.Transformer.from_crs.return_value = fake_t
        with mock.patch.dict("sys.modules", {"pyproj": fake_pyproj}):
            result = _normalise_crs(features, target_crs="epsg:27700")
        assert result[0].geometry.crs == "epsg:27700"
        assert result[1].geometry.crs == "epsg:27700"
        glod.config.USE_PYPROJ = False

    def test_empty_list_returns_empty(self):
        assert _normalise_crs([], target_crs="epsg:27700") == []


class TestMostCommonCRS:
    def test_single_crs(self):
        features = [
            Feature(
                Point.from_geojson(
                    {"type": "Point", "coordinates": [1, 2]}, crs="epsg:27700"
                ),
                {},
            ),
            Feature(
                Point.from_geojson(
                    {"type": "Point", "coordinates": [3, 4]}, crs="epsg:27700"
                ),
                {},
            ),
        ]
        assert _most_common_crs(features) == "epsg:27700"

    def test_mixed_returns_most_frequent(self):
        features = [
            Feature(
                Point.from_geojson(
                    {"type": "Point", "coordinates": [1, 2]}, crs="epsg:27700"
                ),
                {},
            ),
            Feature(
                Point.from_geojson(
                    {"type": "Point", "coordinates": [3, 4]}, crs="epsg:27700"
                ),
                {},
            ),
            Feature(
                Point.from_geojson(
                    {"type": "Point", "coordinates": [0, 51]}, crs="epsg:4326"
                ),
                {},
            ),
        ]
        assert _most_common_crs(features) == "epsg:27700"

    def test_empty_returns_none(self):
        assert _most_common_crs([]) is None


class TestCRSFromGeoJSON:
    def test_standard_crs_field(self):
        geojson = {"crs": {"type": "name", "properties": {"name": "epsg:27700"}}}
        assert _crs_from_geojson(geojson) == "epsg:27700"

    def test_missing_crs_returns_none(self):
        assert _crs_from_geojson({}) is None

    def test_malformed_crs_returns_none(self):
        assert _crs_from_geojson({"crs": {"type": "name"}}) is None
