from .geometry import Geometry, CRSType, wkt_to_geojson

import os
import json


class Feature:
    def __init__(self, geometry: Geometry, attributes: dict):
        self.geometry = geometry
        self.attributes = attributes

    @property
    def __geo_interface__(self) -> dict:
        geo = {
            "type": "Feature",
            "geometry": self.geometry.__geo_interface__,
            "properties": self.attributes
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

    def to_geojson(self, path: str | None = None, crs: CRSType = None)-> dict:
        if crs is None:
            # construct dict of each crs used by features and count how often they occur
            found_crs = {}
            for i in self.features:
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
        for feat in self.features:
            if feat.geometry.crs != target_crs:
                # transform it to mode_crs and replace geometry of feature
                feat.geometry = feat.geometry.transform(target_crs)

        geojson =  {
            "type": "FeatureCollection",
            "features": [i.to_geojson for i in self.features],
            "crs": {
                "type": "name",
                "properties": {
                    "name": target_crs
                }
            }
        }

        if path:
            # write to file
            # TODO: check file path exists
            with open(path, "w") as f:
                json.dump(geojson, f, indent=4)
        return geojson

    # @classmethod
    # def from_geojson(cls, object: str | dict):
    #     if isinstance(object, str):
    #         # if path, read from file


def feature_to_geojson(wkt: str, attributes: dict):
    output = {
        "type": "Feature",
        "geometry": wkt_to_geojson(wkt),
        "properties": attributes,
    }
    return output
