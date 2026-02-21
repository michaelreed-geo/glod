import json
import os
from typing import Any

from .geometry import CRSType, Geometry, wkt_to_geojson


class Feature:
    def __init__(self, geometry: Geometry, attributes: dict):
        self.geometry = geometry
        self.attributes = attributes

    @property
    def __geo_interface__(self) -> dict:
        geo = {
            "type": "Feature",
            "geometry": self.geometry.__geo_interface__,
            "properties": self.attributes,
        }
        return geo

    @classmethod
    def from_geojson(cls, geojson: dict, crs: CRSType = None):
        geometry = Geometry.from_geojson(geojson["geometry"], crs)
        properties = {}
        if "properties" in geojson:
            properties = geojson["properties"]
        return cls(geometry, properties)

    @property
    def to_geojson(self) -> dict:
        return feature_to_geojson(self.geometry.to_wkt, self.attributes)


class FeatureCollection:
    def __init__(self, features: list[Feature]):
        self.features = features

    def __iter__(self):
        for feature in self.features:
            yield feature

    def __getitem__(self, i):
        return self.features[i]

    def __len__(self):
        return len(self.features)

    def to_geojson(self, path: str | None = None, crs: CRSType = None) -> dict:
        return feature_collection_to_geojson(self, path, crs)

    @classmethod
    def from_geojson(cls, geojson: str | dict):
        return cls(geojson_to_feature_list(geojson))


def feature_to_geojson(wkt: str, attributes: dict):
    output = {
        "type": "Feature",
        "geometry": wkt_to_geojson(wkt),
        "properties": attributes,
    }
    return output


def feature_collection_to_geojson(
    feature_collection: FeatureCollection, path: str | None = None, crs: CRSType = None
) -> dict:
    if crs is None:
        # construct dict of each crs used by features and count how often they occur
        found_crs = {}
        for i in feature_collection.features:
            if i.geometry.crs not in found_crs:
                found_crs[i.geometry.crs] = 0
            found_crs[i.geometry.crs] += 1

        if len(found_crs) > 1:
            # FeatureCollection contains multiple CRS, transform to the most common
            target_crs = ""
            crs_count = 0
            for crs, count in found_crs:
                if count > crs_count:
                    target_crs = crs
        else:
            target_crs = list(found_crs.keys())[0]
    else:
        target_crs = crs

    # transform feature to uniform target_crs
    for feat in feature_collection.features:
        if feat.geometry.crs != target_crs:
            # transform it to mode_crs and replace geometry of feature
            feat.geometry = feat.geometry.transform(target_crs)

    geojson = {
        "type": "FeatureCollection",
        "features": [i.to_geojson for i in feature_collection.features],
        "crs": {"type": "name", "properties": {"name": target_crs}},
    }

    if path:
        # write to file
        # TODO: check file path exists
        with open(path, "w") as f:
            json.dump(geojson, f, indent=4)
    return geojson


def geojson_to_feature_list(geojson: str | dict) -> list[Feature]:
    # TODO: add support pathlib
    if isinstance(geojson, str):
        if os.path.exists(geojson):
            # read from file
            with open(geojson, "r") as f:
                geojson = json.load(f)
        else:
            # load from geojson string
            geojson = json.loads(geojson)

    # if geojson is dict, no need to edit format!

    crs = get_crs_from_geojson(geojson)
    features = [Feature.from_geojson(i, crs) for i in geojson["features"]]
    return features


def get_dict_value_recursive(dict_: dict, keys: list[str]) -> Any:
    """
    Crawl recursively through a dict to return a target value.

    Args:
        dict_: the structure to crawl.
        keys: the keys or list indices to extract the value from

    Returns:
        The value of dict_ at the cumulative keys or indices.
    """
    finished = False
    output = None  # default
    while not finished:
        output = dict_
        for i in keys:
            # if output is dict and i is key
            if isinstance(output, dict):
                if i in output:
                    output = output[i]
                else:
                    raise KeyError(f"{i} not a valid key in {output}.")
            # if output is list and i is index
            elif isinstance(output, list) and isinstance(i, int):
                try:
                    output = output[i]
                except IndexError as exc:
                    raise exc
        finished = True
    return output


def get_crs_from_geojson(geojson: dict) -> str | None:
    try:
        crs = get_dict_value_recursive(geojson, ["crs", "properties", "name"])
    except KeyError:
        crs = None
    return crs
