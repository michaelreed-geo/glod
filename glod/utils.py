import re
from typing import TYPE_CHECKING
from warnings import warn

import glod.config

CRSType = "str | CRS"

if TYPE_CHECKING:
    from pyproj.crs import CRS, CRSError


WKT_TYPES = ["POINT", "LINESTRING", "POLYGON"]


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
    Calculate the centroid of a linestring.

    Args:
        coordsinate: List of (x, y) tuples representing the linestring vertices.

    Returns:
        (x_centroid, y_centroid)
    """
    if len(coordinates) < 2:
        raise ValueError("Linestring must have at least 2 points")

    total_length = 0.0
    cx = 0.0
    cy = 0.0

    for (x0, y0), (x1, y1) in zip(coordinates[:-1], coordinates[1:]):
        segment_length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        midpoint_x = (x0 + x1) / 2
        midpoint_y = (y0 + y1) / 2
        cx += midpoint_x * segment_length
        cy += midpoint_y * segment_length
        total_length += segment_length

    if total_length == 0:
        # all points are identical
        return coordinates[0]

    return (cx / total_length, cy / total_length)


def get_polygon_centroid(
    coordinates: tuple[tuple[float, float]],
) -> tuple[float, float]:
    """
    Compute the centroid of a polygon.

    Parameters
    ----------
    coordinates : tuple of (x, y)
        The vertices of the polygon in order. The polygon should be closed
        (first point != last point, the function will handle closing).

    Returns
    -------
    (cx, cy) : tuple of float
        The centroid coordinates.
    """
    if len(coordinates) < 3:
        raise ValueError("Polygon must have at least 3 vertices")

    # Ensure polygon is closed
    if coordinates[0] != coordinates[-1]:
        coordinates = coordinates + (coordinates[0],)

    area = 0.0
    cx = 0.0
    cy = 0.0

    for i in range(len(coordinates) - 1):
        x0, y0 = coordinates[i]
        x1, y1 = coordinates[i + 1]
        cross = x0 * y1 - x1 * y0
        area += cross
        cx += (x0 + x1) * cross
        cy += (y0 + y1) * cross

    area *= 0.5
    if area == 0:
        raise ValueError("Polygon area is zero, cannot compute centroid")

    cx /= 6.0 * area
    cy /= 6.0 * area

    return (cx, cy)


def get_geometry_centroid(wkt: str) -> tuple[float, float] | None:
    if wkt.upper().startswith("POINT"):
        return get_coordinates_from_wkt(wkt)
    elif wkt.upper().startswith("LINESTRING"):
        return get_linestring_centroid(get_coordinates_from_wkt(wkt))
    elif wkt.upper().startswith("POLYGON"):
        return get_polygon_centroid(get_coordinates_from_wkt(wkt))
    else:
        return None


def bounds_to_polygon_wkt(bounds: tuple[float, float, float, float]) -> str:
    x_min, y_min, x_max, y_max = bounds
    coordinates = (
        (x_min, y_min),
        (x_min, y_max),
        (x_max, y_max),
        (x_max, y_min),
        (x_min, y_min),
    )
    return coordinates_to_wkt(coordinates)


def feature_to_geojson(wkt: str, attributes: dict):
    output = {
        "type": "Feature",
        "geometry": wkt_to_geojson(wkt),
        "properties": attributes,
    }
    return output


# def geojson_to_feature(geojson: dict)
