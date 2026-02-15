from .geometry import Geometry
from .utils import CRSType, feature_to_geojson


class Feature:
    def __init__(self, geometry: Geometry, attributes: dict):
        self.geometry = geometry
        self.attributes = attributes

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
