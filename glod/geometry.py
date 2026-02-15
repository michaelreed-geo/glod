import glod.config
from glod.utils import (
    WKT_TYPES,
    CRSType,
    bounds_to_polygon_wkt,
    coordinates_to_wkt,
    format_wkt_string,
    geojson_to_wkt,
    get_coordinates_from_wkt,
    get_geometry_centroid,
    get_wkt_type_from_str,
    is_wkt_string_valid,
    transform_coordinates,
    wkt_to_geojson,
)


class Geometry:
    def __init__(self, wkt: str | None = None, crs: CRSType = None):
        if self._wkt_is_valid(wkt):
            self._wkt = format_wkt_string(wkt)
        else:
            # TODO improve error message to specify if issue is WKT type or malformed coordinates
            raise ValueError(
                "wkt is malformed on an unsupported type. Check wkt for typos. "
                f"Supported types are {WKT_TYPES}."
            )

        # transform pyproj CRS to string, only if pyproj can be used
        if glod.config.USE_PYPROJ and crs is not None:
            from pyproj.crs import CRS

            if isinstance(crs, CRS):
                crs = crs.to_string()

        elif not glod.config.USE_PYPROJ:
            if not isinstance(crs, str) and crs is not None:
                raise TypeError(
                    "crs is not a valid type. If you want to use a pyproj CRS object, you must "
                    "first call glod.set_use_pyproj(True)."
                )
        self._crs = crs

    @property
    def __geo_interface__(self) -> dict:
        geo = {
            "type": self.geometry_type,
            "bbox": self.bounds,
            "coordinates": self.coordinates,
        }
        return geo

    @property
    def bounds(self) -> tuple[float, float, float, float] | None:
        coordinates = get_coordinates_from_wkt(self.to_wkt)
        if isinstance(coordinates[0], tuple):
            x, y = zip(*coordinates)
            x_min = min(x)
            x_max = max(x)
            y_min = min(y)
            y_max = max(y)
            return x_min, y_min, x_max, y_max
        else:
            return None

    @property
    def centroid(self) -> "Geometry":
        coordinate = get_geometry_centroid(self.to_wkt)
        wkt = coordinates_to_wkt(coordinate)
        return Geometry(wkt, self.crs)

    @property
    def coordinates(self) -> tuple[float, float] | tuple[tuple[float, float]]:
        return get_coordinates_from_wkt(self.to_wkt)

    @property
    def crs(self) -> str:
        return self._crs

    @property
    def envelope(self) -> "Polygon | None":
        if self.geometry_type == "Point":
            return None
        else:
            return Geometry(bounds_to_polygon_wkt(self.bounds), self.crs)

    @property
    def geometry_type(self) -> str:
        return get_wkt_type_from_str(self.to_wkt)

    @classmethod
    def from_coordinates(
        cls,
        coordinates: tuple[float, float] | tuple[tuple[float, float]] | None = None,
        crs: CRSType = None,
    ):
        return cls(wkt=coordinates_to_wkt(coordinates), crs=crs)

    @classmethod
    def from_geojson(cls, geojson: dict, crs: CRSType = None):
        return cls(wkt=geojson_to_wkt(geojson), crs=crs)

    @classmethod
    def from_object(cls, object, crs: CRSType = None) -> "Geometry | None":
        if hasattr(object, "__geo_interface__"):
            return cls(wkt=geojson_to_wkt(object.__geo_interface__), crs=crs)
        # if object does not have __geo_interface, no Geometry can be initialised. Return None.
        return None

    @classmethod
    def from_wkt(cls, wkt: str, crs: CRSType = None):
        return cls(wkt=wkt, crs=crs)

    def intersects(self, geometry: "Geometry") -> bool:
        # TODO
        ...

    @property
    def to_geojson(self) -> str | dict:
        return wkt_to_geojson(self.to_wkt)

    @property
    def to_wkt(self) -> str:
        return self._wkt

    def transform(
        self,
        out_crs: CRSType = None,
        accuracy: int | None = None,
        always_xy: bool = True,
    ) -> "Geometry":
        if self.crs is None:
            raise RuntimeError("Cannot transform geometry without a defined CRS.")

        transformed_coordinates = transform_coordinates(
            self.coordinates,
            in_crs=self.crs,
            out_crs=out_crs,
            always_xy=always_xy,
            accuracy=accuracy,
        )
        return self.from_coordinates(transformed_coordinates, crs=out_crs)

    def _wkt_is_valid(self, wkt: str) -> bool:
        wkt_type = wkt.split("(")[0].strip().upper()
        return is_wkt_string_valid(wkt, wkt_type)
