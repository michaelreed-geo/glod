import re
from _warnings import warn
from typing import TYPE_CHECKING

import glod.config

if TYPE_CHECKING:
    from pyproj.crs import CRS



CRSType = "str | CRS"
WKT_TYPES = ["POINT", "LINESTRING", "POLYGON"]


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
            "type": self.type,
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
        if self.type == "Point":
            return None
        else:
            return Geometry(bounds_to_polygon_wkt(self.bounds), self.crs)

    @property
    def type(self) -> str:
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
        return check_geometries_intersect(self, geometry)

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


def get_coordinates_from_wkt(
    wkt: str | None,
) -> tuple[float, float] | tuple[tuple[float, float]] | None:
    """
    Convert a Well Known Text (WKT) geometry string to its component coordinate(s) as tuples of
    floats.

    Args:
        wkt: a Well Known Text (WKT) representation of a geometry.

    Returns:
        The coordinates of the WKT as a tuple of floats.
    """
    left_index = wkt.rfind("(") + 1
    right_index = wkt.find(")")
    # drop wkt type prefix and brackets
    coordinates_str = wkt[left_index:right_index]

    # TODO: add error handling
    output = []
    # parse coordinates as float
    for pair in coordinates_str.split(","):
        xy = tuple(float(i) for i in pair.strip().split(" "))
        output.append(xy)

    # force immutable
    output = tuple(output)
    # simplify to single tuple if single coordinate pair
    if len(output) == 1:
        output = output[0]

    return output


def flatten_coordinates_to_str(
    coordinates: tuple[float, float] | tuple[tuple[float, float]],
) -> str:
    """
    Flattens a tuple or list of coordinates into a WKT string format. Removing tuple brackets and unwanted
    commas between x y pairs.

    Args:
        coordinates: the WKT coordinates as a tuple of floats.

    Returns:
        The coordinates as a WKT-style string.
    """
    # TODO: add error handling
    if isinstance(coordinates[0], tuple) or isinstance(coordinates[0], list):
        # tuple of tuples
        coordinates_str = ", ".join([f"{i[0]} {i[1]}" for i in coordinates])
    else:
        # single tuple
        coordinates_str = f"{coordinates[0]} {coordinates[1]}"
    return f"({coordinates_str})"


def is_wkt_string_valid(wkt: str, wkt_type: str) -> bool:
    """
    Check if a WKT string is a valid type and contains coordinates correctly formatted for parsing.

    Args:
        wkt: the WKT string.
        wkt_type: the type of WKT (e.g. Point, LineString, Polygon).

    Returns:
        True if WKT string is valid, False if not.
        Raises ValueError if WKT is not a supported type.
    """
    wkt_regex = {
        # pattern for "POINT [spaces]([spaces]number[single space]number[spaces])"
        "POINT": r"^POINT\s*\(\s*-?\d+(?:\.\d+)?\s-?\d+(?:\.\d+)?\s*\)$",
        # pattern for "LINESTRING[spaces]([spaces]number[single space]number[spaces][comma][~repeats~])"
        "LINESTRING": r"^LINESTRING\s*\(\s*(?:-?\d+(?:\.\d+)?\s-?\d+(?:\.\d+)?\s*,\s*)*-?\d+(?:\.\d+)?\s-?\d+(?:\.\d+)?\s*\)$",
        # pattern for "POLYGON[spaces]([spaces]([spaces]number[single space]number[spaces][comma][~repeats~])[spaces])",
        "POLYGON": r"^POLYGON\s*\(\s*\(\s*(?:-?\d+(?:\.\d+)?\s-?\d+(?:\.\d+)?\s*,\s*)*-?\d+(?:\.\d+)?\s-?\d+(?:\.\d+)?\s*\)\s*\)$",
    }

    # TODO: confirm number of coordinates are valid (point=1, line>1, polygon>3 where last coord matches first)
    if wkt_type in wkt_regex:
        # check format is as expected using regex
        pattern = re.compile(wkt_regex[wkt_type])
        if pattern.fullmatch(wkt.upper()) is not None:
            coordinates = get_coordinates_from_wkt(wkt)
            if wkt_type == "POINT":
                # promote to list for easier parsing
                coordinates = [coordinates]
            elif wkt_type in ["LINESTRING", "POLYGON"]:
                coordinates = list(coordinates)

            # check coordinates are all pairs
            if False in [len(i) == 2 for i in coordinates]:
                return False
            # check coordinates are all numerical
            try:
                [(float(i[0]), float(i[1])) for i in coordinates]
            except ValueError:
                return False

            # check point is single coordinate
            if wkt_type == "POINT":
                if len(coordinates) > 1:
                    return False
            # check line is >= 2 coordinates
            if wkt_type == "LINESTRING":
                if len(coordinates) < 2:
                    return False
            # check polygon is >= 3 coordinates with idx=0 == idx=-1
            if wkt_type == "POLYGON":
                if len(coordinates) < 3:
                    return False
                if coordinates[0] != coordinates[-1]:
                    return False
        else:
            return False

    else:
        raise ValueError(f"WKT is invalid type. Supported types are {WKT_TYPES}.")
    return True


def format_wkt_string(wkt: str) -> str:
    """
    Formats a WKT string into a uniform format with geometry type capitalised and coordinates
    as space separated x y, with comma separated pairs.

    Args:
        wkt: the WKT string.

    Returns:
        The formatted string.
    """
    coordinates = get_coordinates_from_wkt(wkt)
    coordinates_str = flatten_coordinates_to_str(coordinates)

    if wkt.upper().startswith("POINT"):
        output = f"POINT {coordinates_str}"

    elif wkt.upper().startswith("LINESTRING"):
        output = f"LINESTRING {coordinates_str}"

    elif wkt.upper().startswith("POLYGON"):
        output = f"POLYGON ({coordinates_str})"

    else:
        raise ValueError(f"WKT is invalid type. Supported types are {WKT_TYPES}.")
    return output


def wkt_to_geojson(wkt: str) -> dict | None:
    """
    Converts a WKT string geometry to a geojson dict geometry.

    Args:
        wkt: the WKT string

    Returns:
        The content to populate a geojson's feature geometry.
    """
    wkt_type = wkt.split(" ")[0]
    geom_type = None
    match wkt_type:
        case "POINT":
            geom_type = "Point"
            coordinates = list(get_coordinates_from_wkt(wkt))
        case "LINESTRING":
            geom_type = "LineString"
            coordinates = [list(i) for i in get_coordinates_from_wkt(wkt)]
        case "POLYGON":
            geom_type = "Polygon"
            coordinates = [[list(i) for i in get_coordinates_from_wkt(wkt)]]
        case _:
            # if invalid geometry type, output == None which resolves to a json null
            output = None

    if geom_type is not None:
        output = {"type": geom_type, "coordinates": coordinates}
    return output


def geojson_to_wkt(geojson: dict) -> str:
    """
    Converts a geojson "geometry" object to a well known text (WKT) string.

    Args:
        geojson: the "geometry" object from a geojson Feature. Must contain the keys "type" and
        "coordinates".

    Returns:
        A well known text (WKT) string representation of the geometry.
    """
    output = None  # default in case geojson is null geometry
    if geojson is not None:
        match geojson["type"]:
            # TODO: handle case where geojson has type but no coordinates?
            case "Point":
                output = f"POINT {flatten_coordinates_to_str(geojson['coordinates'])}"
            case "LineString":
                output = (
                    f"LINESTRING {flatten_coordinates_to_str(geojson['coordinates'])}"
                )
            case "Polygon":
                output = (
                    f"POLYGON ({flatten_coordinates_to_str(geojson['coordinates'][0])})"
                )
            case _:
                output = None
    return output


def is_crs_valid(crs: str) -> bool | None:
    """
    Checks if a coordinate reference system (CRS) is valid according to pyproj.

    Args:
        crs: the CRS to validate

    Returns:
        True if the CRS is valid, False if not.
    """
    result = True
    # transform pyproj CRS to string, only if pyproj can be used
    if glod.config.USE_PYPROJ:
        from pyproj.crs import CRS, CRSError

        try:
            CRS(crs)
            result = True
        except CRSError:
            warn(f"Invalid projection: {crs}.")
            result = False

    elif not glod.config.USE_PYPROJ:
        result = None
    return result


def coordinates_to_wkt(
    coordinates: tuple[float, float] | tuple[tuple[float, float]],
) -> str | None:
    """
    Converts a list of geometry coordinates into a well known text (WKT) representation.

    The geometry type is inferred based on the form of `coordinates`:
    * Point: `coordinates` is a single tuple of floats.
    * LineString: `coordinates` is a tuple of tuples of floats where `coordinates[0]` != `coordinates[-1]
    * Polygon: `coordinates` is a tuple of tuples of floats where `coordinates[0]` == `coordinates[-1]`

    Args:
        coordinates: the coordinates of the geometry.

    Returns:
        A well known text (WKT) string representation of the geometry.
    """
    output = None
    coordinates_str = flatten_coordinates_to_str(coordinates)
    if isinstance(coordinates[0], tuple):
        if len(coordinates) > 1 and coordinates[0] != coordinates[-1]:
            # line coordinates
            output = f"LINESTRING {coordinates_str}"
        elif len(coordinates) > 2 and coordinates[0] == coordinates[-1]:
            output = f"POLYGON ({coordinates_str})"
    else:
        if len(coordinates) == 2:
            # point coordinate
            output = f"POINT {coordinates_str}"
    return output


def transform_coordinates(
    coordinates: tuple[float, float] | tuple[tuple[float, float]],
    in_crs: CRSType,
    out_crs: CRSType,
    always_xy: bool = True,
    accuracy: int | None = None,
) -> tuple[float, float] | tuple[tuple[float, float]]:
    """
    Transforms coordinates from one coordinate reference system (CRS) to another using pyproj.

    WARNING: this function can only be used if pyproj is enabled by glod. Use
    `glod.config.set_use_pyproj(True)` to do this if it is not already enabled.

    Args:
        coordinates: the coordinates to transform.
        in_crs: the current CRS defining the coordinates.
        out_crs: the target CRS to transform the coordinates to.
        always_xy: If true, the transform method will accept as input and return as output
            coordinates using the traditional GIS order, that is longitude, latitude for geographic
            CRS and easting, northing for most projected CRS. Refer to pyproj documentation.
        accuracy: the number of decimal places to round the transformed coordinates to. If not
            specified, no rounding is done.

    Returns:
        The coordinates transformed to `in_crs`.
    """
    if not glod.config.USE_PYPROJ:
        raise RuntimeError(
            "Coordinate transformation is disabled. Call glod.set_use_pyproj(True) to enable."
        )

    from pyproj import Transformer
    from pyproj.crs import CRS
    from pyproj.exceptions import CRSError

    # Validate CRS
    try:
        CRS(in_crs)
        CRS(out_crs)
    except CRSError as exc:
        raise ValueError(f"Invalid CRS: {exc}") from exc

    transformer = Transformer.from_crs(in_crs, out_crs, always_xy=always_xy)

    # Transform coordinates
    if isinstance(coordinates[0], tuple):  # linestring or polygon
        transformed = tuple(transformer.transform(x, y) for x, y in coordinates)
    else:  # point
        transformed = transformer.transform(*coordinates)

    # Optionally round
    if accuracy is not None:
        if isinstance(transformed[0], tuple):
            transformed = tuple(
                (round(x, accuracy), round(y, accuracy)) for x, y in transformed
            )
        else:
            transformed = tuple(round(c, accuracy) for c in transformed)

    return transformed


def get_wkt_type_from_str(wkt: str) -> str:
    """
    Gets the geometry type from a well known text (WKT) string.

    Args:
        wkt: the WKT string.

    Returns:
        The geometry type as a string (Point, LineString, Polygon)
    """
    wkt_type = wkt.split("(")[0].strip().upper()
    output = None
    if wkt_type == "LINESTRING":
        output = "LineString"
    elif wkt_type in ["POINT", "POLYGON"]:
        output = f"{wkt_type[0]}{wkt_type[1:].lower()}"
    return output


def get_linestring_centroid(
    coordinates: tuple[tuple[float, float]],
) -> tuple[float, float]:
    """
    Calculate the centroid of a LineString.

    Args:
        coordinates: tuple of tuple x,y vertices

    Returns:
        (x_centroid, y_centroid)
    """
    total_length = 0
    cx = 0
    cy = 0

    for (x0, y0), (x1, y1) in zip(coordinates[:-1], coordinates[1:]):
        segment_length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        midpoint_x = (x0 + x1) / 2
        midpoint_y = (y0 + y1) / 2
        cx += midpoint_x * segment_length
        cy += midpoint_y * segment_length
        total_length += segment_length

    return cx / total_length, cy / total_length


def get_polygon_centroid(
    coordinates: tuple[tuple[float, float]],
) -> tuple[float, float]:
    """
    Calculate the centroid of a LineString.

    Args:
        coordinates: tuple of tuple x,y vertices, where coordinates[0] == coordinates[-1]

    Returns:
        (x_centroid, y_centroid)
    """
    area = 0
    cx = 0
    cy = 0

    for (x0, y0), (x1, y1) in zip(coordinates[:-2], coordinates[1:-1]):
        cross = x0 * y1 - x1 * y0
        area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross

    cx /= 3 * area
    cy /= 3 * area

    return cx, cy


def get_geometry_centroid(wkt: str) -> tuple[float, float] | None:
    """
    Gets the centroid of a geometry provided in well known text (WKT) format.

    Args:
        wkt: the WKT string.

    Returns:
        The centroid of the geometry as a coordinate pair.
    """
    if wkt.upper().startswith("POINT"):
        return get_coordinates_from_wkt(wkt)
    elif wkt.upper().startswith("LINESTRING"):
        return get_linestring_centroid(get_coordinates_from_wkt(wkt))
    elif wkt.upper().startswith("POLYGON"):
        return get_polygon_centroid(get_coordinates_from_wkt(wkt))
    else:
        return None


def bounds_to_polygon_wkt(bounds: tuple[float, float, float, float]) -> str:
    """
    Creates a well known text (WKT) Polygon from a geometry's bounds.

    Args:
        bounds: a geometry's bounds in the form (x_min, y_min, x_max, y_max)

    Returns:
        The WKT polygon formed by the bounds.
    """
    x_min, y_min, x_max, y_max = bounds
    coordinates = (
        (x_min, y_min),
        (x_min, y_max),
        (x_max, y_max),
        (x_max, y_min),
        (x_min, y_min),
    )
    return coordinates_to_wkt(coordinates)



def get_points_orientation(p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float]) -> int:
    """
    Check the orientation of three points.

    Args:
        p1: tuple of x,y coordinates
        p2: tuple of x,y coordinates
        p3: tuple of x,y coordinates

    Returns:
        0 if collinear, 1 if clockwise, 2 if anti-clockwise
    """
    output = (p2[1] - p1[1]) * (p3[0] - p2[0]) - (p2[0] - p1[0]) * (p3[1] - p2[1])

    if abs(output) < 1e-6:
        return 0
    elif output > 0:
        return 1
    else:
        return 2


def is_point_on_line(line: tuple[tuple[float, float], tuple[float, float]], point: tuple[float, float]) -> bool:
    """
    Check if `point` lies on `line`.

    Args:
        line: a line segment as two x,y coordinate pairs
        point: a point given as an x,y coordinate

    Returns:
        True if `point` is on `line`, False if not.
    """
    p1, p2 = line
    output = (min(p1[0], p2[0]) <= point[0] <= max(p1[0], p2[0]) and
              min(p1[1], p2[1]) <= point[1] <= max(p1[1], p2[1]))
    return output


def check_segments_intersect(
        line1: tuple[tuple[float, float], tuple[float, float]],
        line2: tuple[tuple[float, float], tuple[float, float]]
) -> bool:
    p1, q1 = line1
    p2, q2 = line2

    orientation1 = get_points_orientation(p1, p2, q1)
    orientation2 = get_points_orientation(p1, p2, q2)
    orientation3 = get_points_orientation(q1, q2, p1)
    orientation4 = get_points_orientation(q1, q2, p2)

    if orientation1 != orientation2 and orientation3 != orientation4:
        return True

    # check if collinear
    if orientation1 == 0 and is_point_on_line(line=(p1, p2), point=q1): return True
    if orientation2 == 0 and is_point_on_line(line=(p1, p2), point=q2): return True
    if orientation3 == 0 and is_point_on_line(line=(q1, q2), point=p1): return True
    if orientation4 == 0 and is_point_on_line(line=(q1, q2), point=p2): return True

    # no intersection
    return False


def coordinates_to_line_segments(coordinates: tuple[tuple[float, float],...]) -> tuple[tuple[tuple[float, float], tuple[float, float]], ...]:
    segments = []
    for i in range(len(coordinates) - 1):
        segments.append((coordinates[i], coordinates[i+1]))
    return tuple(segments)


def do_bounds_interesct(geometry1: Geometry, geometry2: Geometry) -> bool:
    # transform geometry2 if needed
    if geometry1.crs != geometry2.crs:
        geometry2 = geometry2.transform(out_crs=geometry1.crs)

    x_min1, y_min1, x_max1, y_max1 = geometry1.bounds
    x_min2, y_min2, x_max2, y_max2 = geometry2.bounds
    if x_min1 > x_max2 or x_min2 > x_max1 or y_min1 > y_max2 or y_min2 > y_max1:
        return False
    return True



def check_geometries_intersect(geometry1: Geometry, geometry2: Geometry) -> bool:
    if geometry1.type != "Point" and geometry2.type != "Point":
        # transform geometry2 if needed
        if geometry1.crs != geometry2.crs:
            geometry2 = geometry2.transform(out_crs=geometry1.crs)

        # check bounding boxes intersect for quick rejection
        if not do_bounds_interesct(geometry1, geometry2):
            return False

        # check segments intersect
        segments1 = coordinates_to_line_segments(geometry1.coordinates)
        segments2 = coordinates_to_line_segments(geometry2.coordinates)

        for line1 in segments1:
            for line2 in segments2:
                if check_segments_intersect(line1, line2):
                    return True
        return False
    else:
        raise ValueError("Point geometry!")
        # TODO: add check for point intersecting line or point within/intersecting polygon
