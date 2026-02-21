import importlib
import json

import pytest

from glod import FeatureCollection
from glod.feature import (
    feature_collection_to_geojson,
    feature_to_geojson,
    geojson_to_feature_list,
    get_crs_from_geojson,
    get_dict_value_recursive,
)


@pytest.fixture
def geojson_sample():
    geojson = {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [102.0, 0.5]},
                "properties": {"prop0": "value0"},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "LineString",
                    "coordinates": [
                        [102.0, 0.0],
                        [103.0, 1.0],
                        [104.0, 0.0],
                        [105.0, 1.0],
                    ],
                },
                "properties": {"prop0": "value0", "prop1": 0.0},
            },
            {
                "type": "Feature",
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [
                        [
                            [100.0, 0.0],
                            [101.0, 0.0],
                            [101.0, 1.0],
                            [100.0, 1.0],
                            [100.0, 0.0],
                        ]
                    ],
                },
                "properties": {"prop0": "value0", "prop1": {"this": "that"}},
            },
        ],
        "crs": {
            "type": "name",
            "properties": {
                "name": "EPSG:3857"
            }
        }
    }
    return geojson


def test_geojson_to_feature_list_from_dict(geojson_sample):
    feat_list = geojson_to_feature_list(geojson_sample)
    # check number of features
    assert len(feat_list) == 3
    # check types of features
    feat_types = [i.geometry.type for i in feat_list]
    assert feat_types == ["Point", "LineString", "Polygon"]
    # check crs of features
    feat_crs = set([i.geometry.crs for i in feat_list])
    assert feat_crs == {"EPSG:3857"}


def test_geojson_to_feature_list_from_path(tmp_path, geojson_sample):
    temp_file = tmp_path / "sample.geojson"
    temp_file.write_text(json.dumps(geojson_sample))

    feat_list = geojson_to_feature_list(str(temp_file))
    # check number of features
    assert len(feat_list) == 3
    # check types of features
    feat_types = [i.geometry.type for i in feat_list]
    assert feat_types == ["Point", "LineString", "Polygon"]
    # check crs of features
    feat_crs = set([i.geometry.crs for i in feat_list])
    assert feat_crs == {"EPSG:3857"}


def test_geojson_to_feature_list_from_string(monkeypatch, geojson_sample):
    geojson_str = json.dumps(geojson_sample)
    monkeypatch.setattr("glod.feature.os.path.exists", lambda p: False)
    feat_list = geojson_to_feature_list(geojson_str)
    # check number of features
    assert len(feat_list) == 3
    # check types of features
    feat_types = [i.geometry.type for i in feat_list]
    assert feat_types == ["Point", "LineString", "Polygon"]
    # check crs of features
    feat_crs = set([i.geometry.crs for i in feat_list])
    assert feat_crs == {"EPSG:3857"}


def test_get_crs_from_geojson_valid(geojson_sample):
    assert get_crs_from_geojson(geojson_sample) == "EPSG:3857"


def test_get_crs_from_geojson_invalid():
    geojson = {
        "crs": None
    }
    assert get_crs_from_geojson(geojson) is None


@pytest.mark.parametrize(
    "keys, expected",
    [
        (["type"], "FeatureCollection"),
        (["features", -1, "properties", "prop1", "this"], "that")
    ]
)
def test_get_dict_value_recursive(geojson_sample, keys, expected):
    assert get_dict_value_recursive(geojson_sample, keys) == expected
