"""Geometry types and constructors for the glod package.

This module provides an immutable geometry class hierarchy modelling the six GeoJSON
geometry types (Point, LineString, Polygon, MultiPoint, MultiLineString, MultiPolygon).
All classes share a common ABC (``Geometry``) that handles construction, validation,
serialisation, CRS-aware coordinate transformation, and geometric intersection testing.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from enum import Enum
from typing import TYPE_CHECKING, TypeAlias, Union

import glod.config as _config

if TYPE_CHECKING:
    from pyproj import CRS

CrsType: TypeAlias = Union[str, "CRS", None]
"""Type alias for a coordinate reference system value.

Accepted forms are an EPSG string (e.g. ``"epsg:4326"``), a :class:`pyproj.CRS`
instance, or ``None`` (unknown / unset).
"""


class GeometryType(str, Enum):
    """Enumeration of the six GeoJSON geometry type strings."""

    POINT = "Point"
    LINESTRING = "LineString"
    POLYGON = "Polygon"
    MULTIPOINT = "MultiPoint"
    MULTILINESTRING = "MultiLineString"
    MULTIPOLYGON = "MultiPolygon"


# ---------------------------------------------------------------------------
# General private utilities
# ---------------------------------------------------------------------------


def _list_to_tuple(obj):
    """Recursively convert all lists in *obj* to tuples.

    Used to freeze coordinate data inside geometry objects so that they are immutable.
    Inverse of :func: `_tuple_to_list`.

    Args:
        obj: Any value. Lists (and nested lists) are converted to tuples; all other
            values are returned unchanged.

    Returns:
        A tuple structure mirroring *obj*, or *obj* itself if it is not a list or tuple.
    """
    if isinstance(obj, (list, tuple)):
        return tuple(_list_to_tuple(i) for i in obj)
    return obj


def _tuple_to_list(obj):
    """Recursively convert all tuples in *obj* to lists.
    
    Inverse of :func:`_list_to_tuple`. Used when returning coordinates to callers, who
    generally expect plain lists rather than tuples (e.g. JSON).

    Args:
        obj: Any value. Tuples (and nested tuples) are converted to lists; all other
            values are returned unchanged.

    Returns:
        A list structure mirroring *obj*, or *obj* itself if it is not a tuple.
    """
    if isinstance(obj, tuple):
        return [_tuple_to_list(i) for i in obj]
    return obj


def _iter_vertices(coords, depth: int):
    """Yield every individual vertex from an arbitrarily nested coordinate array.

    The ``depth`` parameter mirrors the ``_coord_depth`` convention used by each
    geometry subclass:

    * ``depth=0`` -- *coords* **is** the vertex (Point).
    * ``depth=1`` -- *coords* is ``[vertex, ...]`` (LineString, MultiPoint).
    * ``depth=2`` -- *coords* is ``[[vertex, ...]]`` (Polygon, MultiLineString).
    * ``depth=3`` -- *coords* is ``[[[vertex, ...]]]`` (MultiPolygon).

    Args:
        coords: The coordinate array to traverse.
        depth: The number of nesting levels between *coords* and a single vertex.

    Yields:
        Individual vertex sequences (list or tuple of numbers).
    """
    if depth == 0:
        yield coords
    elif depth == 1:
        yield from coords
    else:
        for child in coords:
            yield from _iter_vertices(child, depth - 1)


def _parse_wkt_coords(token: str, depth: int) -> list:
    """Recursively parse a WKT coordinate token into a nested list.

    The ``depth`` parameter mirrors the ``_coord_depth`` convention so that the
    resulting structure is ready to pass directly to :meth:`Geometry.from_geojson`.

    * ``depth=0`` -- ``"x y z"``            -> ``[x, y, z]``
    * ``depth=1`` -- ``"x y, x y"``         -> ``[[x, y], [x, y]]``
    * ``depth=1`` -- ``"(x y), (x y)"``     -> ``[[x, y], [x, y]]`` (MultiPoint)
    * ``depth=2`` -- ``"(x y, x y), ..."``  -> ``[[[x, y], ...], ...]``
    * ``depth=3`` -- ``"((x y, ...)), ..."`` -> ``[[[[x, y], ...], ...], ...]``

    Args:
        token: A WKT coordinate substring (without the type prefix).
        depth: Target nesting depth, matching the ``_coord_depth`` of the geometry class
            being parsed.

    Returns:
        A nested list of floats representing the parsed coordinates.
    """
    token = token.strip()
    if depth == 0:
        return [float(v) for v in token.split()]
    elif depth == 1:
        # MultiPoint WKT wraps each point in brackets: "(x y), (x y)".
        if token.startswith("("):
            groups = _split_wkt_groups(token)
            return [_parse_wkt_coords(g, 0) for g in groups]
        return [_parse_wkt_coords(v, 0) for v in token.split(",")]
    else:
        groups = _split_wkt_groups(token)
        return [_parse_wkt_coords(g, depth - 1) for g in groups]


def _fmt(i: float | int) -> str:
    """Format a single coordinate value for WKT output.

    Whole-number floats are rendered as integers (``1.0`` -> ``"1"``) to keep WKT output
    concise and round-trip-safe.

    Args:
        i: A numeric coordinate component.

    Returns:
        A string representation of *i* without trailing ``.0`` for whole-number values.
    """
    return str(int(i)) if isinstance(i, float) and i.is_integer() else str(i)


def _split_wkt_groups(token: str) -> list[str]:
    """Split a WKT string into its top-level bracket groups.

    For example::

        "(1 2, 3 4), (5 6, 7 8)"  ->  ["1 2, 3 4", "5 6, 7 8"]

    Handles arbitrarily deep nesting by tracking bracket depth.

    Args:
        token: A WKT substring containing one or more parenthesised groups.

    Returns:
        A list of strings, each being the content of one top-level group (with the
        enclosing parentheses stripped).
    """
    groups = []
    depth = 0
    current: list[str] = []
    for char in token:
        if char == "(":
            if depth > 0:
                current.append(char)
            depth += 1
        elif char == ")":
            depth -= 1
            if depth > 0:
                current.append(char)
            elif depth == 0:
                groups.append("".join(current).strip())
                current = []
        elif char == "," and depth == 0:
            pass  # separator between top-level groups; skip
        else:
            current.append(char)
    return groups


# Populated after class definitions; maps coord depth -> singlepart class.
_SINGLEPART_BY_DEPTH: dict[int, type] = {}


def _infer_singlepart_type(coordinates: list) -> type:
    """Infer the singlepart geometry class from a GeoJSON coordinates array.

    The mapping from coordinate structure to type is unambiguous for the three
    singlepart types:

    * Flat numeric sequence  ``[x, y]`` or ``[x, y, z]``  -> :class:`Point`
    * Sequence of pairs      ``[[x, y], ...]``             -> :class:`LineString`
    * Nested sequences       ``[[[x, y], ...], ...]``      -> :class:`Polygon`

    Args:
        coordinates: A GeoJSON-style coordinate array whose nesting depth determines the
            inferred type.

    Returns:
        The :class:`Geometry` subclass corresponding to the detected depth.

    Raises:
        ValueError: If *coordinates* is not a list or tuple, if its structure cannot be
            matched to a known depth, or if no class has been registered for the
            detected depth.
    """
    if not isinstance(coordinates, (list, tuple)):
        raise ValueError(
            f"coordinates must be a list or tuple, got {type(coordinates).__name__!r}."
        )

    if all(isinstance(c, (int, float)) for c in coordinates):
        depth = 0
    elif isinstance(coordinates[0], (list, tuple)) and all(
        isinstance(c, (int, float)) for c in coordinates[0]
    ):
        depth = 1
    elif isinstance(coordinates[0], (list, tuple)) and isinstance(
        coordinates[0][0], (list, tuple)
    ):
        depth = 2
    else:
        raise ValueError(
            f"Cannot infer geometry type from coordinates structure: {coordinates!r}"
        )

    cls = _SINGLEPART_BY_DEPTH.get(depth)
    if cls is None:
        raise ValueError(f"No singlepart type registered for coordinate depth {depth}.")
    return cls


# ---------------------------------------------------------------------------
# Intersection helpers
# ---------------------------------------------------------------------------
# All functions work in 2D (x, y). Z values are ignored for intersection
# tests since GeoJSON geometries are defined in a 2D projected/geographic
# plane; elevation does not affect planimetric intersection.


def _v2(v) -> tuple[float, float]:
    """Return the 2D (x, y) portion of a vertex, discarding any Z component.

    Args:
        v: A vertex sequence with 2 or 3 elements.

    Returns:
        A ``(x, y)`` tuple.
    """
    return (v[0], v[1])


def _bounds_overlap_2d(
    a_bounds: tuple | None,
    b_bounds: tuple | None,
) -> bool:
    """Return True if two bounding boxes overlap in the XY plane.

    A ``None`` bound (from :class:`Point`, which has no extent) is treated as a
    single-point degenerate box and cannot be rejected at this stage, so the function
    returns ``True`` to allow the caller to proceed to the exact test.

    Args:
        a_bounds: Bounding box of geometry *a* as returned by :attr:`Geometry.bounds`,
            or ``None``.
        b_bounds: Bounding box of geometry *b*, or ``None``.

    Returns:
        ``False`` only when the boxes are provably disjoint; ``True`` otherwise.
    """
    if a_bounds is None or b_bounds is None:
        return True
    # Supports both 2D (4-tuple) and 3D (6-tuple) bounds; compare only X/Y.
    n = min(len(a_bounds), len(b_bounds)) // 2
    for i in range(2):  # only check X and Y axes
        if a_bounds[i] > b_bounds[i + n] or b_bounds[i] > a_bounds[i + n]:
            return False
    return True


def _cross2d(o, a, b) -> float:
    """Signed area of the parallelogram spanned by vectors OA and OB (2D).

    Returns a positive value if OAB turns counter-clockwise, negative if clockwise, and
    zero if the three points are collinear.

    Args:
        o: Origin point ``(x, y)``.
        a: First point ``(x, y)``.
        b: Second point ``(x, y)``.

    Returns:
        The scalar cross product ``(A-O) x (B-O)``.
    """
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _on_segment(p, a, b) -> bool:
    """Return True if *p* lies on segment *ab*, assuming the three are collinear.

    Args:
        p: Point to test ``(x, y)``.
        a: Segment start ``(x, y)``.
        b: Segment end ``(x, y)``.

    Returns:
        ``True`` if *p* is within the axis-aligned bounding box of *ab*.
    """
    return min(a[0], b[0]) <= p[0] <= max(a[0], b[0]) and min(a[1], b[1]) <= p[
        1
    ] <= max(a[1], b[1])


def _segments_intersect(a1, a2, b1, b2) -> bool:
    """Return True if line segment *a1-a2* intersects segment *b1-b2*.

    Uses the standard orientation-based algorithm. Handles collinear and T-junction
    cases correctly via the :func:`_on_segment` fallback.

    All arguments are 2D ``(x, y)`` points.

    Args:
        a1: Start of segment A.
        a2: End of segment A.
        b1: Start of segment B.
        b2: End of segment B.

    Returns:
        ``True`` if the segments share at least one point.
    """
    d1 = _cross2d(b1, b2, a1)
    d2 = _cross2d(b1, b2, a2)
    d3 = _cross2d(a1, a2, b1)
    d4 = _cross2d(a1, a2, b2)

    if ((d1 > 0 and d2 < 0) or (d1 < 0 and d2 > 0)) and (
        (d3 > 0 and d4 < 0) or (d3 < 0 and d4 > 0)
    ):
        return True

    # Collinear cases: check whether the points actually overlap.
    if d1 == 0 and _on_segment(a1, b1, b2):
        return True
    if d2 == 0 and _on_segment(a2, b1, b2):
        return True
    if d3 == 0 and _on_segment(b1, a1, a2):
        return True
    if d4 == 0 and _on_segment(b2, a1, a2):
        return True

    return False


def _point_on_ring(p, ring) -> bool:
    """Return True if point *p* lies exactly on any edge of *ring*.

    Args:
        p: Point ``(x, y)``.
        ring: Sequence of ``(x, y)`` vertices forming a closed ring.

    Returns:
        ``True`` if *p* is collinear with and within the extent of any edge.
    """
    for i in range(len(ring) - 1):
        a, b = _v2(ring[i]), _v2(ring[i + 1])
        if _cross2d(a, b, p) == 0 and _on_segment(p, a, b):
            return True
    return False


def _point_in_ring(p, ring) -> bool:
    """Return True if point *p* is strictly inside the closed *ring*.

    Uses the ray-casting algorithm (even-odd rule). Does **not** return True for points
    on the boundary; use :func:`_point_on_ring` for that.

    Args:
        p: Point ``(x, y)``.
        ring: Sequence of ``(x, y)`` vertices forming a closed ring (the closing vertex
            need not be repeated, but may be).

    Returns:
        ``True`` if *p* is strictly inside *ring*.
    """
    x, y = p
    inside = False
    n = len(ring)
    j = n - 1
    for i in range(n):
        xi, yi = ring[i][0], ring[i][1]
        xj, yj = ring[j][0], ring[j][1]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / (yj - yi) + xi):
            inside = not inside
        j = i
    return inside


def _point_in_polygon_coords(p, poly_coords) -> bool:
    """Return True if point *p* is inside or on the boundary of a polygon.

    Checks containment in the outer ring first, then subtracts any interior rings
    (holes).

    Args:
        p: Point ``(x, y)``.
        poly_coords: GeoJSON-style polygon coordinate array: a list of rings, the first
            being the outer ring and any subsequent being holes.

    Returns:
        ``True`` if *p* lies on the boundary or strictly inside the polygon (accounting
        for holes).
    """
    outer = poly_coords[0]
    p2 = _v2(p)
    if _point_on_ring(p2, outer):
        return True
    if not _point_in_ring(p2, [_v2(v) for v in outer]):
        return False
    # Point is inside outer ring -- check holes.
    for hole in poly_coords[1:]:
        if _point_in_ring(p2, [_v2(v) for v in hole]):
            return False
    return True


def _linestring_segments(coords) -> list[tuple]:
    """Return all (start, end) segment pairs from a linestring coordinate array.

    Both start and end are 2D ``(x, y)`` tuples.

    Args:
        coords: Sequence of vertices.

    Returns:
        List of ``((x1, y1), (x2, y2))`` pairs.
    """
    return [(_v2(coords[i]), _v2(coords[i + 1])) for i in range(len(coords) - 1)]


def _extract_singleparts(geom: "Geometry") -> list["Geometry"]:
    """Return the constituent singlepart geometries of *geom*.

    For singlepart geometries (Point, LineString, Polygon) returns a single-element list
    containing *geom* itself. For multi-part types decomposes into the individual parts,
    preserving the CRS.

    Args:
        geom: Any :class:`Geometry` instance.

    Returns:
        A list of singlepart :class:`Geometry` instances.
    """
    # Avoid circular import: check by class name via type registry.
    gt = geom.type
    if gt == GeometryType.MULTIPOINT:
        return [
            _GEOMETRY_REGISTRY[GeometryType.POINT](
                geojson={"type": "Point", "coordinates": list(c)},
                crs=geom.crs,
            )
            for c in geom.coordinates
        ]
    if gt == GeometryType.MULTILINESTRING:
        return [
            _GEOMETRY_REGISTRY[GeometryType.LINESTRING](
                geojson={"type": "LineString", "coordinates": list(c)},
                crs=geom.crs,
            )
            for c in geom.coordinates
        ]
    if gt == GeometryType.MULTIPOLYGON:
        return [
            _GEOMETRY_REGISTRY[GeometryType.POLYGON](
                geojson={"type": "Polygon", "coordinates": list(c)},
                crs=geom.crs,
            )
            for c in geom.coordinates
        ]
    return [geom]


# ---------------------------------------------------------------------------
# Pairwise singlepart intersection tests
# These all accept plain singlepart Geometry objects and return bool.
# Dispatch is handled by _singlepart_intersects().
# ---------------------------------------------------------------------------


def _point_point(a: "Geometry", b: "Geometry") -> bool:
    """Return True if two Points share the same 2D position."""
    return _v2(a.coordinates) == _v2(b.coordinates)


def _point_linestring(pt: "Geometry", ls: "Geometry") -> bool:
    """Return True if *pt* lies on any segment of *ls*.

    Performs an early bounds rejection on each segment before the exact test.

    Args:
        pt: A :class:`Point` geometry.
        ls: A :class:`LineString` geometry.

    Returns:
        ``True`` if the point lies on the linestring (including endpoints).
    """
    p = _v2(pt.coordinates)
    coords = ls.coordinates
    for i in range(len(coords) - 1):
        a, b = _v2(coords[i]), _v2(coords[i + 1])
        # Cheap segment-level bounds rejection before exact collinearity test.
        if not (
            min(a[0], b[0]) <= p[0] <= max(a[0], b[0])
            and min(a[1], b[1]) <= p[1] <= max(a[1], b[1])
        ):
            continue
        if _cross2d(a, b, p) == 0:
            return True
    return False


def _point_polygon(pt: "Geometry", poly: "Geometry") -> bool:
    """Return True if *pt* is inside or on the boundary of *poly*.

    Args:
        pt: A :class:`Point` geometry.
        poly: A :class:`Polygon` geometry.

    Returns:
        ``True`` if the point is within or on the edge of the polygon.
    """
    return _point_in_polygon_coords(pt.coordinates, poly.coordinates)


def _linestring_linestring(a: "Geometry", b: "Geometry") -> bool:
    """Return True if two LineStrings share at least one point.

    After the outer bounds check in :meth:`Geometry.intersects`, this performs a
    per-segment bounds check before the exact orientation test, giving O(n*m) with a low
    constant in practice.

    Args:
        a: First :class:`LineString`.
        b: Second :class:`LineString`.

    Returns:
        ``True`` if any segment pair intersects.
    """
    segs_a = _linestring_segments(a.coordinates)
    segs_b = _linestring_segments(b.coordinates)
    for a1, a2 in segs_a:
        # Segment-level bounding-box rejection.
        ax_min, ax_max = min(a1[0], a2[0]), max(a1[0], a2[0])
        ay_min, ay_max = min(a1[1], a2[1]), max(a1[1], a2[1])
        for b1, b2 in segs_b:
            if (
                max(b1[0], b2[0]) < ax_min
                or min(b1[0], b2[0]) > ax_max
                or max(b1[1], b2[1]) < ay_min
                or min(b1[1], b2[1]) > ay_max
            ):
                continue
            if _segments_intersect(a1, a2, b1, b2):
                return True
    return False


def _linestring_polygon(ls: "Geometry", poly: "Geometry") -> bool:
    """Return True if a LineString and a Polygon intersect.

    Three conditions satisfy intersection:
    1. Any segment of *ls* intersects any edge of the polygon boundary.
    2. Any vertex of *ls* is inside the polygon (covers full containment).
    3. Any vertex of the polygon boundary is strictly inside *ls* bounding
       box -- handled implicitly by condition 1.

    Args:
        ls: A :class:`LineString` geometry.
        poly: A :class:`Polygon` geometry.

    Returns:
        ``True`` if the linestring and polygon share at least one point.
    """
    poly_coords = poly.coordinates
    ls_coords = ls.coordinates
    ls_segs = _linestring_segments(ls_coords)

    # Build segments for all polygon rings (outer + holes).
    ring_segs = []
    for ring in poly_coords:
        ring_segs.extend(_linestring_segments(ring))

    # Check any ls segment vs any ring edge.
    for a1, a2 in ls_segs:
        ax_min, ax_max = min(a1[0], a2[0]), max(a1[0], a2[0])
        ay_min, ay_max = min(a1[1], a2[1]), max(a1[1], a2[1])
        for b1, b2 in ring_segs:
            if (
                max(b1[0], b2[0]) < ax_min
                or min(b1[0], b2[0]) > ax_max
                or max(b1[1], b2[1]) < ay_min
                or min(b1[1], b2[1]) > ay_max
            ):
                continue
            if _segments_intersect(a1, a2, b1, b2):
                return True

    # No edge crossing found -- check if ls is entirely inside the polygon.
    if _point_in_polygon_coords(ls_coords[0], poly_coords):
        return True

    return False


def _polygon_polygon(a: "Geometry", b: "Geometry") -> bool:
    """Return True if two Polygons intersect.

    Checks three conditions:
    1. Any edge of polygon *a* intersects any edge of polygon *b*.
    2. A vertex of *a* is inside *b* (covers containment of *a* in *b*).
    3. A vertex of *b* is inside *a* (covers containment of *b* in *a*).

    Args:
        a: First :class:`Polygon`.
        b: Second :class:`Polygon`.

    Returns:
        ``True`` if the polygons share at least one point.
    """
    coords_a, coords_b = a.coordinates, b.coordinates

    # Build edge lists for all rings of each polygon.
    segs_a = []
    for ring in coords_a:
        segs_a.extend(_linestring_segments(ring))

    segs_b = []
    for ring in coords_b:
        segs_b.extend(_linestring_segments(ring))

    # Condition 1: any edge pair intersects.
    for a1, a2 in segs_a:
        ax_min, ax_max = min(a1[0], a2[0]), max(a1[0], a2[0])
        ay_min, ay_max = min(a1[1], a2[1]), max(a1[1], a2[1])
        for b1, b2 in segs_b:
            if (
                max(b1[0], b2[0]) < ax_min
                or min(b1[0], b2[0]) > ax_max
                or max(b1[1], b2[1]) < ay_min
                or min(b1[1], b2[1]) > ay_max
            ):
                continue
            if _segments_intersect(a1, a2, b1, b2):
                return True

    # Condition 2: a vertex of a's outer ring is inside b.
    if _point_in_polygon_coords(coords_a[0][0], coords_b):
        return True

    # Condition 3: a vertex of b's outer ring is inside a.
    if _point_in_polygon_coords(coords_b[0][0], coords_a):
        return True

    return False


# Dispatch table for singlepart x singlepart intersection.
# Keys are (GeometryType_A, GeometryType_B) with the "smaller" type first
# so we only need to store one direction; the caller normalises the order.
# "Smaller" is defined by the ordering in _SINGLEPART_RANK below.
_SINGLEPART_RANK = {
    GeometryType.POINT: 0,
    GeometryType.LINESTRING: 1,
    GeometryType.POLYGON: 2,
}

_SINGLEPART_DISPATCH: dict[tuple, object] = {
    (GeometryType.POINT, GeometryType.POINT): _point_point,
    (GeometryType.POINT, GeometryType.LINESTRING): _point_linestring,
    (GeometryType.POINT, GeometryType.POLYGON): _point_polygon,
    (GeometryType.LINESTRING, GeometryType.LINESTRING): _linestring_linestring,
    (GeometryType.LINESTRING, GeometryType.POLYGON): _linestring_polygon,
    (GeometryType.POLYGON, GeometryType.POLYGON): _polygon_polygon,
}


def _singlepart_intersects(a: "Geometry", b: "Geometry") -> bool:
    """Test intersection between two singlepart geometries.

    Normalises argument order so the dispatch table only needs one entry per pair. For
    mixed pairs involving LINESTRING and POLYGON the function signature is
    ``(linestring, polygon)``, so the arguments are swapped if necessary.

    Args:
        a: A singlepart :class:`Geometry` (Point, LineString, or Polygon).
        b: A singlepart :class:`Geometry` (Point, LineString, or Polygon).

    Returns:
        ``True`` if *a* and *b* share at least one point.

    Raises:
        NotImplementedError: If the type combination has no registered handler (should
            never happen for valid singlepart types).
    """
    ta, tb = a.type, b.type
    ra, rb = _SINGLEPART_RANK.get(ta, -1), _SINGLEPART_RANK.get(tb, -1)

    # Put the lower-ranked type first so the dispatch key is canonical.
    if ra > rb:
        a, b, ta, tb = b, a, tb, ta

    fn = _SINGLEPART_DISPATCH.get((ta, tb))
    if fn is None:
        raise NotImplementedError(
            f"No intersection handler for ({ta.value}, {tb.value})."
        )
    return fn(a, b)


# ---------------------------------------------------------------------------
# Abstract base class
# ---------------------------------------------------------------------------

# Populated by Geometry.__init_subclass__; maps GeometryType -> subclass.
_GEOMETRY_REGISTRY: dict[GeometryType, type] = {}


class Geometry(ABC):
    """Abstract base class for all glod geometry types.

    Subclasses represent the six GeoJSON geometry types and share a common interface for
    construction, serialisation, transformation, and intersection testing. Instances are
    effectively immutable once created -- coordinates are stored internally as nested
    tuples so that external references cannot mutate them.

    Subclasses **must** declare the following class attributes:

    * ``_geojson_type`` (:class:`GeometryType`) -- the GeoJSON type string this class
        represents.
    * ``_coord_depth`` (``int``) -- the number of nesting levels between the top-level
        coordinates array and an individual vertex.
    * ``_min_vertices`` (``int``) -- the minimum number of vertices required for a valid
        instance.

    Note:
        CRS is stored as metadata only; it is not validated against the coordinate
        values. Transformation between CRS values requires pyproj to be enabled via
        :func:`glod.config.set_use_pyproj`.
    """

    _geojson_type: GeometryType
    _coord_depth: int
    _min_vertices: int

    __slots__ = ("_crs", "_type", "_geojson")

    def __init_subclass__(cls, **kwargs):
        """Register each concrete subclass by its ``_geojson_type`` for dispatch.

        Called automatically by Python when a class is defined that inherits from
        :class:`Geometry`. Subclasses that declare ``_geojson_type`` are inserted into
        :data:`_GEOMETRY_REGISTRY`, enabling type-string-based dispatch in
        :meth:`from_geojson` and :meth:`from_wkt`.

        Args:
            **kwargs: Forwarded to :func:`super().__init_subclass__`.
        """
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "_geojson_type"):
            _GEOMETRY_REGISTRY[cls._geojson_type] = cls

    def __init__(self, geojson: dict | None, crs: CrsType):
        """Initialise a geometry from a raw GeoJSON dict.

        Not intended to be called directly -- use one of the class-method constructors
        (:meth:`from_geojson`, :meth:`from_wkt`, :meth:`from_coordinates`, etc.)
        instead.

        Passing ``None`` for *geojson* creates a null geometry (both :attr:`type` and
        :attr:`geojson` will be ``None``).

        Args:
            geojson: A GeoJSON geometry dict containing ``"type"`` and ``"coordinates"``
                keys, or ``None`` for a null geometry.
            crs: The coordinate reference system of the geometry. Stored as metadata;
                not validated against the coordinate values.

        Raises:
            TypeError: If *geojson* is not a dict.
            ValueError: If required keys are missing, the ``"type"`` field does not
                match this class's expected type, or coordinate validation fails.
        """
        # uppercase CRS for standardised formatting
        if isinstance(crs, str):
            crs = crs.upper()
        self._crs = crs

        if geojson is None:
            self._type = None
            self._geojson = None
            return

        self._validate_geojson_keys(geojson)
        geometry_type = self._parse_type(geojson["type"])
        self._validate_geojson_type(geometry_type)
        self._extra_coordinate_validation(geojson["coordinates"])
        self._validate_geojson_coordinates(geojson["coordinates"])

        self._type = geometry_type
        self._geojson = {
            "type": geometry_type.value,
            "coordinates": _list_to_tuple(geojson["coordinates"]),
        }

    # ---- constructors ----

    @classmethod
    def from_geojson(cls, geojson: dict, crs: CrsType = None) -> Geometry:
        """Construct a :class:`Geometry` from a GeoJSON geometry dict.

        When called on the ABC (``Geometry.from_geojson(...)``), the ``"type"`` field is
        used to dispatch to the correct subclass. When called on a specific subclass
        (``Point.from_geojson(...)``), the type is validated against the subclass.

        Args:
            geojson: A GeoJSON geometry dict with ``"type"`` and ``"coordinates"`` keys.
            crs: Optional CRS to associate with the geometry.

        Returns:
            An instance of the appropriate :class:`Geometry` subclass.

        Raises:
            ValueError: If the ``"type"`` field is missing, unrecognised, or (when
                called on a subclass) does not match the subclass type.
            TypeError: If *geojson* is not a dict, or the ``"type"`` field mismatches
                the calling subclass.

        Example::

            p = Geometry.from_geojson(
                {"type": "Point", "coordinates": [0.0, 51.5]},
                crs="epsg:4326",
            )
            assert isinstance(p, Point)
        """
        if cls is Geometry:
            geometry_type = Geometry._parse_type(geojson.get("type", ""))
            target_cls = _GEOMETRY_REGISTRY.get(geometry_type)
            if target_cls is None:
                raise ValueError(
                    f"No class registered for geometry type '{geometry_type}'."
                )
            return target_cls(geojson=geojson, crs=crs)
        return cls(geojson=geojson, crs=crs)

    @classmethod
    def from_wkt(cls, wkt: str, crs: CrsType = None) -> Geometry:
        """Construct a :class:`Geometry` from a WKT string.

        When called on the ABC, the type prefix (e.g. ``POINT``, ``LINESTRING``) is used
        to dispatch to the correct subclass. When called on a specific subclass, the WKT
        type is validated against the subclass.

        2D and 3D coordinates are supported. Interior rings in
        ``POLYGON`` / ``MULTIPOLYGON`` WKT are not yet supported and will raise
        :exc:`NotImplementedError` when serialised back to WKT.

        Args:
            wkt: A Well-Known Text geometry string.
            crs: Optional CRS to associate with the geometry.

        Returns:
            An instance of the appropriate :class:`Geometry` subclass.

        Raises:
            ValueError: If *wkt* is not valid WKT, the type prefix is unrecognised, or
                coordinate validation fails.
            TypeError: If called on a subclass and the WKT type does not
                match.

        Example::

            ls = Geometry.from_wkt("LINESTRING (0 0, 1 1, 2 0)")
            assert isinstance(ls, LineString)
        """
        wkt = wkt.upper().strip()
        match = re.match(r"^([A-Z]+)\s*\((.+)\)$", wkt, re.DOTALL)
        if not match:
            raise ValueError(f"Invalid or unrecognised WKT: {wkt!r}")

        type_str, coord_str = match.group(1), match.group(2).strip()

        type_map = {gt.value.upper(): gt for gt in GeometryType}
        geometry_type = type_map.get(type_str)
        if geometry_type is None:
            raise ValueError(f"Unsupported WKT geometry type: {type_str!r}")

        target_cls = _GEOMETRY_REGISTRY.get(geometry_type)
        if target_cls is None:
            raise ValueError(
                f"No class registered for geometry type '{geometry_type}'."
            )

        if cls is not Geometry and geometry_type != cls._geojson_type:
            raise TypeError(
                f"WKT type '{geometry_type.value}' does not match "
                f"expected type '{cls._geojson_type.value}'."
            )

        coordinates = _parse_wkt_coords(coord_str, target_cls._coord_depth)
        geojson = {"type": geometry_type.value, "coordinates": coordinates}
        return target_cls(geojson=geojson, crs=crs)

    @classmethod
    def from_object(cls, obj: object, crs: CrsType = None) -> Geometry:
        """Construct a :class:`Geometry` from any object implementing ``__geo_interface__``.

        ``__geo_interface__`` is the standard duck-typing protocol for geo objects in
        Python, supported by shapely, fiona, geopandas, and others. The protocol
        requires the attribute to return a GeoJSON-compatible dict containing
        ``"type"`` and ``"coordinates"`` keys.

        CRS is **not** part of the ``__geo_interface__`` specification and must be
        supplied via the *crs* argument if known.

        When called on the ABC, dispatches to the correct subclass. When called on a
        subclass, validates that the geometry type matches.

        Args:
            obj: An object that exposes a ``__geo_interface__`` property returning a
                GeoJSON geometry dict.
            crs: Optional CRS to associate with the resulting geometry.

        Returns:
            An instance of the appropriate :class:`Geometry` subclass.

        Raises:
            TypeError: If *obj* does not implement ``__geo_interface__``, or if
                ``__geo_interface__`` does not return a dict.
            ValueError: If the geometry dict fails validation.

        Example::

            import shapely.geometry
            shp_point = shapely.geometry.Point(1, 2)
            p = Geometry.from_object(shp_point, crs="epsg:4326")
        """
        geo_interface = getattr(obj, "__geo_interface__", None)
        if geo_interface is None:
            raise TypeError(
                f"{type(obj).__name__!r} does not implement __geo_interface__."
            )
        if not isinstance(geo_interface, dict):
            raise TypeError(
                f"__geo_interface__ must return a dict, "
                f"got {type(geo_interface).__name__!r}."
            )
        return cls.from_geojson(geo_interface, crs=crs)

    @classmethod
    def from_coordinates(cls, coordinates: list, crs: CrsType = None) -> Geometry:
        """Construct a singlepart :class:`Geometry` from a GeoJSON coordinates array.

        The expected structure mirrors the GeoJSON coordinate convention:

        * ``[x, y]`` or ``[x, y, z]``             -> :class:`Point`
        * ``[[x, y], [x, y], ...]``                -> :class:`LineString`
        * ``[[[x, y], [x, y], ...]]``              -> :class:`Polygon`

        When called on the ABC (``Geometry.from_coordinates(...)``), the type is
        inferred automatically from the coordinate structure. When called on a specific
        subclass, the type is used directly without inference.

        Multi-part types (:class:`MultiPoint`, :class:`MultiLineString`,
        :class:`MultiPolygon`) are not supported -- call the corresponding singlepart
        constructor instead.

        Args:
            coordinates: A GeoJSON-style nested list of coordinate values.
            crs: Optional CRS to associate with the geometry.

        Returns:
            A singlepart :class:`Geometry` instance.

        Raises:
            TypeError: If called on a multi-part type.
            ValueError: If the coordinate structure cannot be mapped to a singlepart
                type, or if coordinate validation fails.

        Example::

            # Type inferred from structure
            p = Geometry.from_coordinates([1.0, 2.0])
            assert isinstance(p, Point)

            # Type specified explicitly
            ls = LineString.from_coordinates([[0, 0], [1, 1], [2, 0]])
        """
        if cls is MultiGeometry or (
            cls is not Geometry and issubclass(cls, MultiGeometry)
        ):
            single_name = getattr(cls, "_single_type", None)
            hint = (
                f" Call {single_name.__name__}.from_coordinates() instead."
                if single_name
                else ""
            )
            raise TypeError(
                f"from_coordinates() is not supported on multi-part types.{hint}"
            )

        if cls is Geometry or cls is MultiGeometry:
            target_cls = _infer_singlepart_type(coordinates)
        else:
            target_cls = cls

        return target_cls.from_geojson(
            {"type": target_cls._geojson_type.value, "coordinates": coordinates},
            crs=crs,
        )

    # ---- public properties ----

    @property
    def __geo_interface__(self) -> dict | None:
        """GeoJSON geometry dict, conforming to the ``__geo_interface__`` protocol.

        Returns ``None`` for null geometries.

        Returns:
            A GeoJSON geometry dict or ``None``.
        """
        return self.geojson

    @property
    def coordinates(self):
        """The raw coordinate data as a nested tuple structure.

        Coordinates are stored internally as tuples (rather than lists) to prevent
        accidental mutation. Use :attr:`geojson` to obtain a copy with plain lists if
        needed.

        Returns:
            A nested tuple of coordinate values, or ``None`` for null geometries.
        """
        if self._geojson is None:
            return None
        return self._geojson["coordinates"]

    @property
    def crs(self) -> CrsType:
        """The coordinate reference system associated with this geometry.

        Stored as supplied on construction; not validated against coordinate values.
        ``None`` indicates the CRS is unknown or unset.

        Returns:
            A CRS value (string, :class:`pyproj.CRS`, or ``None``).
        """
        return self._crs

    @property
    def geojson(self) -> dict | None:
        """A GeoJSON geometry dict with plain-list coordinates.

        Returns a fresh dict on every call so callers cannot mutate internal state.
        Returns ``None`` for null geometries.

        Returns:
            A dict with ``"type"`` and ``"coordinates"`` keys, or ``None``.
        """
        if self._geojson is None:
            return None
        return {
            "type": self._type.value,
            "coordinates": _tuple_to_list(self._geojson["coordinates"]),
        }

    @property
    def has_z(self) -> bool:
        """Whether this geometry has Z (elevation) coordinates.

        Determined by inspecting the first vertex; assumes all vertices share the same
        dimensionality (enforced by validation on construction).

        Returns:
            ``True`` if coordinates are 3D, ``False`` if 2D.
        """
        vertex = next(_iter_vertices(self.coordinates, self._coord_depth))
        return len(vertex) == 3

    @property
    def type(self) -> GeometryType:
        """The :class:`GeometryType` of this geometry.

        Returns:
            A :class:`GeometryType` enum member, or ``None`` for null geometries.
        """
        return self._type

    @property
    def bounds(self) -> tuple[float, ...] | None:
        """The axis-aligned bounding box of all vertices.

        Returns a 4-tuple ``(x_min, y_min, x_max, y_max)`` for 2D geometries, or a
        6-tuple ``(x_min, y_min, z_min, x_max, y_max, z_max)`` for 3D geometries.

        :class:`Point` overrides this property to return ``None`` since a single point
        has no spatial extent.

        Returns:
            A tuple of floats describing the bounding box, or ``None`` for
            :class:`Point` and null geometries.
        """
        if self._geojson is None:
            return None
        n = 3 if self.has_z else 2
        mins = [float("+inf")] * n
        maxs = [float("-inf")] * n
        for vertex in _iter_vertices(self.coordinates, self._coord_depth):
            for i, v in enumerate(vertex):
                mins[i] = min(mins[i], v)
                maxs[i] = max(maxs[i], v)
        return tuple(mins + maxs)

    @property
    @abstractmethod
    def wkt(self) -> str:
        """The Well-Known Text (WKT) representation of this geometry.

        Returns:
            A WKT string, e.g. ``"POINT (1 2)"``.
        """
        ...

    def transform(self, target_crs: CrsType) -> Geometry:
        """Return a new geometry with coordinates transformed to *target_crs*.

        Coordinate transformation is performed using ``pyproj.Transformer`` with
        ``always_xy=True``. The source CRS is taken from :attr:`crs`.

        The returned object is a new instance of the same concrete class with the
        transformed coordinates and *target_crs* set as its CRS. The original geometry
        is not modified.

        Args:
            target_crs: The destination CRS. Accepts any value accepted by
                :class:`pyproj.CRS` (EPSG string, WKT, authority string, etc.).

        Returns:
            A new :class:`Geometry` instance of the same type with transformed
            coordinates and ``crs`` set to *target_crs*.

        Raises:
            RuntimeError: If pyproj has not been enabled via
                ``glod.config.set_use_pyproj(True)``.
            ValueError: If :attr:`crs` is ``None``, since transformation requires a
                known source CRS.

        Example::

            import glod.config as config
            config.set_use_pyproj(True)

            p = Point.from_geojson(
                {"type": "Point", "coordinates": [0.0, 51.5]},
                crs="epsg:4326",
            )
            p_bng = p.transform("epsg:27700")
            assert p_bng.crs == "epsg:27700"
        """
        if not _config.USE_PYPROJ:
            raise RuntimeError(
                "transform() requires pyproj. "
                "Enable it with config.set_use_pyproj(True)."
            )
        if self.crs is None:
            raise ValueError(
                "Cannot transform a geometry with no CRS. "
                "Set the CRS on construction before calling transform()."
            )

        from pyproj import Transformer

        transformer = Transformer.from_crs(self.crs, target_crs, always_xy=True)

        def _transform_vertex(vertex):
            if len(vertex) == 2:
                x, y = transformer.transform(vertex[0], vertex[1])
                return [x, y]
            else:
                x, y, z = transformer.transform(vertex[0], vertex[1], vertex[2])
                return [x, y, z]

        def _transform_coords(coords, depth):
            if depth == 0:
                return _transform_vertex(coords)
            return [_transform_coords(c, depth - 1) for c in coords]

        transformed = _transform_coords(
            _tuple_to_list(self.coordinates), self._coord_depth
        )
        return self.__class__.from_geojson(
            {"type": self._geojson_type.value, "coordinates": transformed},
            crs=target_crs,
        )

    def intersects(self, other: Geometry) -> bool:
        """Return True if this geometry shares at least one point with *other*.

        Covers all interaction types:

        * Point touching another point, a line, or the interior/boundary of a polygon.
        * Lines crossing, overlapping, or touching at a single point.
        * A line passing through or touching a polygon boundary or interior.
        * Polygons with overlapping interiors, touching edges, or one fully containing
          the other.

        Multi-part geometries are decomposed into their constituent singlepart
        geometries and the test returns ``True`` as soon as any pair intersects.

        **CRS handling**: both geometries must have a known CRS (neither can be
        ``None``). If their CRS values match the test proceeds directly. If they differ
        and pyproj is enabled (``glod.config.USE_PYPROJ = True``), *other* is
        temporarily reprojected to ``self.crs`` for the duration of the test — neither
        the calling geometry nor *other* is modified. If pyproj is disabled and the CRS
        values differ, a :exc:`ValueError` is raised.

        The one exception to the CRS requirement is when *both* geometries have
        ``crs=None``: this is treated as the user having opted out of CRS tracking 
        entirely, and the test proceeds without any CRS check.

        **Optimisations**:

        * An O(1) axis-aligned bounding-box check rejects obviously disjoint geometry
          pairs before any exact computation.
        * For segment-pair tests (LineString/LineString, LineString/Polygon,
          Polygon/Polygon) an additional per-segment bounding-box check avoids the
          orientation calculation for the majority of non-intersecting segments.
        * Multi-part geometries short-circuit as soon as the first intersecting pair is
          found.

        Args:
            other: Any :class:`Geometry` instance to test against.

        Returns:
            ``True`` if the two geometries share at least one point.

        Raises:
            TypeError: If *other* is not a :class:`Geometry` instance.
            ValueError: If exactly one geometry has ``crs=None`` (ambiguous), or if the
                CRS values differ and pyproj is disabled.

        Example::

            crs = "epsg:27700"

            # Lines crossing at (1, 1)
            a = LineString.from_wkt("LINESTRING (0 0, 2 2)", crs=crs)
            b = LineString.from_wkt("LINESTRING (0 2, 2 0)", crs=crs)
            assert a.intersects(b)

            # Auto-reproject when CRS differs (requires pyproj)
            import glod.config as config
            config.set_use_pyproj(True)
            pt_wgs84 = Point.from_wkt("POINT (-0.1276 51.5074)", crs="epsg:4326")
            poly_bng = Polygon.from_wkt(
                "POLYGON ((-14000 6680000, 700000 6680000, "
                "700000 7300000, -14000 7300000, -14000 6680000))",
                crs="epsg:3857",
            )
            # pt_wgs84 is silently reprojected to epsg:3857 for the test;
            # neither object is modified.
            result = pt_wgs84.intersects(poly_bng)
        """
        if not isinstance(other, Geometry):
            raise TypeError(
                f"intersects() requires a Geometry instance, "
                f"got {type(other).__name__!r}."
            )

        # --- CRS handling ---------------------------------------------
        # Both None  -> user opted out of CRS tracking; proceed as-is.
        # One None   -> ambiguous; raise immediately.
        # Both set, same value -> proceed as-is.
        # Both set, different  -> reproject if pyproj available, else raise.
        crs_self = self.crs
        crs_other = other.crs

        # Resolve the working copies (may be replaced by a reprojection).
        geom_self: Geometry = self
        geom_other: Geometry = other

        if crs_self != crs_other:
            if crs_self is None or crs_other is None:
                raise ValueError(
                    "Cannot test intersection when one geometry has crs=None "
                    "and the other does not. Set a CRS on both geometries "
                    "using the crs argument on construction."
                )
            if not _config.USE_PYPROJ:
                raise ValueError(
                    f"CRS mismatch: self.crs={crs_self!r}, "
                    f"other.crs={crs_other!r}. "
                    "Enable pyproj with glod.config.set_use_pyproj(True) "
                    "to allow automatic reprojection, or call "
                    ".transform() manually before testing intersection."
                )
            # pyproj is available: temporarily reproject other to self's CRS.
            # The original objects are never modified.
            geom_other = other.transform(crs_self)

        # --- Fast bounding-box rejection ------------------------------
        if not _bounds_overlap_2d(geom_self.bounds, geom_other.bounds):
            return False

        # --- Exact test: decompose multi-part types -------------------
        parts_self = _extract_singleparts(geom_self)
        parts_other = _extract_singleparts(geom_other)

        for part_a in parts_self:
            for part_b in parts_other:
                # Inner bounds check for multi-part pairs.
                if not _bounds_overlap_2d(part_a.bounds, part_b.bounds):
                    continue
                if _singlepart_intersects(part_a, part_b):
                    return True

        return False

    # ---- validation (private) ----

    @staticmethod
    def _validate_geojson_keys(geojson: dict) -> None:
        """Assert that *geojson* is a dict containing the required top-level keys.

        Args:
            geojson: The value to validate.

        Raises:
            TypeError: If *geojson* is not a dict.
            ValueError: If ``"type"`` or ``"coordinates"`` are missing.
        """
        if not isinstance(geojson, dict):
            raise TypeError("GeoJSON must be a dictionary.")
        if "type" not in geojson:
            raise ValueError("GeoJSON must contain a 'type' field.")
        if "coordinates" not in geojson:
            raise ValueError("GeoJSON must contain a 'coordinates' field.")

    def _validate_geojson_type(self, actual_type: GeometryType) -> None:
        """Assert that *actual_type* matches this class's expected GeoJSON type.

        Args:
            actual_type: The :class:`GeometryType` parsed from the GeoJSON
                ``"type"`` field.

        Raises:
            TypeError: If *actual_type* does not match ``self._geojson_type``.
        """
        if actual_type != self._geojson_type:
            raise TypeError(
                f"GeoJSON type must be '{self._geojson_type.value}', "
                f"got '{actual_type.value}'"
            )

    def _validate_geojson_coordinates(self, coordinates) -> None:
        """Validate the coordinate array for all geometry types.

        Checks that:

        * The minimum vertex count (``_min_vertices``) is satisfied.
        * Every vertex is a 2- or 3-element sequence of numbers.
        * All vertices share the same dimensionality (no mixing of 2D and 3D).

        Args:
            coordinates: The raw coordinate array from the GeoJSON dict.

        Raises:
            ValueError: If any of the above constraints are violated.
        """
        vertices = list(_iter_vertices(coordinates, self._coord_depth))

        if len(vertices) < self._min_vertices:
            raise ValueError(
                f"{self.__class__.__name__} requires at least {self._min_vertices} "
                f"vertex/vertices, got {len(vertices)}."
            )

        dimension_count = None
        for i, vertex in enumerate(vertices):
            if not isinstance(vertex, (list, tuple)) or not (2 <= len(vertex) <= 3):
                raise ValueError(
                    f"{self.__class__.__name__} vertex must have 2 or 3 numeric "
                    f"coordinates, got {vertex!r} at vertex {i}."
                )
            if not all(isinstance(c, (int, float)) for c in vertex):
                raise ValueError(
                    f"{self.__class__.__name__} coordinates must be numbers, "
                    f"got {vertex!r} at vertex {i}."
                )
            if dimension_count is None:
                dimension_count = len(vertex)
            elif len(vertex) != dimension_count:
                raise ValueError(
                    f"{self.__class__.__name__} coordinates must all share the same "
                    f"dimension ({dimension_count}D), got {len(vertex)}D at vertex {i}."
                )

    def _extra_coordinate_validation(self, coordinates) -> None:
        """Subclass hook for additional coordinate validation beyond shared rules.

        Called before :meth:`_validate_geojson_coordinates` during construction,
        allowing subclasses to enforce type-specific constraints (e.g. ring closure
        for :class:`Polygon`).

        The base implementation is a no-op.

        Args:
            coordinates: The raw coordinate array from the GeoJSON dict.
        """

    @staticmethod
    def _parse_type(type_str: str) -> GeometryType:
        """Parse a GeoJSON type string into a :class:`GeometryType` enum member.

        Args:
            type_str: The value of the GeoJSON ``"type"`` field.

        Returns:
            The matching :class:`GeometryType` member.

        Raises:
            ValueError: If *type_str* does not correspond to any known geometry type.
        """
        try:
            return GeometryType(type_str)
        except ValueError:
            raise ValueError(f"Unsupported geometry type: {type_str}")


# ---------------------------------------------------------------------------
# Subclasses
# ---------------------------------------------------------------------------


class MultiGeometry(Geometry):
    """Intermediate ABC for multi-part geometry types.

    Adds :meth:`to_singlepart`, which promotes a single-part Multi geometry to its
    corresponding singlepart type. Subclasses must declare a ``_single_type`` class
    attribute pointing to the corresponding singlepart class (wired up after all classes
    are defined to avoid forward references).

    Attributes:
        _single_type: The singlepart :class:`Geometry` subclass that corresponds to this
            multi-part type (e.g. :class:`Point` for :class:`MultiPoint`).
    """

    _single_type: type[Geometry]

    def to_singlepart(self) -> Geometry:
        """Promote this multi-geometry to its singlepart equivalent.

        Only valid when the multi-geometry contains exactly one constituent part. The
        CRS is preserved on the returned geometry.

        Returns:
            A singlepart :class:`Geometry` instance of the type given by
            ``_single_type``.

        Raises:
            ValueError: If the multi-geometry contains more than one part, since the
                promotion would be ambiguous.

        Example::

            mp = MultiPoint.from_geojson(
                {"type": "MultiPoint", "coordinates": [[1, 2]]},
                crs="epsg:27700",
            )
            p = mp.to_singlepart()
            assert isinstance(p, Point)
            assert p.wkt == "POINT (1 2)"
        """
        if len(self.coordinates) != 1:
            raise ValueError(
                f"to_singlepart() requires exactly 1 geometry, "
                f"got {len(self.coordinates)}."
            )
        return self._single_type.from_geojson(
            {
                "type": self._single_type._geojson_type.value,
                "coordinates": list(self.coordinates[0]),
            },
            crs=self.crs,
        )


class Point(Geometry):
    """A GeoJSON Point geometry.

    Represents a single position in 2D or 3D space.

    Attributes:
        _geojson_type: :attr:`GeometryType.POINT`
        _coord_depth: ``0`` -- coordinates *are* the vertex.
        _min_vertices: ``1``

    Example::

        p = Point.from_geojson({"type": "Point", "coordinates": [1.0, 2.0]})
        assert p.wkt == "POINT (1 2)"
    """

    _geojson_type = GeometryType.POINT
    _coord_depth = 0
    _min_vertices = 1

    @property
    def bounds(self) -> None:
        """A single point has no spatial extent; always returns ``None``.

        Returns:
            ``None``
        """
        return None

    @property
    def wkt(self) -> str:
        """WKT representation of this point.

        Returns:
            A string of the form ``"POINT (x y)"`` or ``"POINT (x y z)"``.
        """
        return f"POINT ({' '.join(_fmt(c) for c in self.coordinates)})"


class LineString(Geometry):
    """A GeoJSON LineString geometry.

    Represents an ordered sequence of two or more positions connected by straight-line
    segments.

    Attributes:
        _geojson_type: :attr:`GeometryType.LINESTRING`
        _coord_depth: ``1`` -- coordinates is a list of vertices.
        _min_vertices: ``2``

    Example::

        ls = LineString.from_wkt("LINESTRING (0 0, 1 1, 2 0)")
        assert ls.bounds == (0, 0, 2, 1)
    """

    _geojson_type = GeometryType.LINESTRING
    _coord_depth = 1
    _min_vertices = 2

    @property
    def wkt(self) -> str:
        """WKT representation of this linestring.

        Returns:
            A string of the form ``"LINESTRING (x1 y1, x2 y2, ...)"``.
        """
        vertices = ", ".join(" ".join(_fmt(c) for c in v) for v in self.coordinates)
        return f"LINESTRING ({vertices})"


class Polygon(Geometry):
    """A GeoJSON Polygon geometry.

    Represents a closed ring defining a planar area. The ring must be explicitly closed
    (first and last vertex identical). Polygons with interior rings (holes) can be
    constructed and stored, but WKT serialisation for holed polygons is not yet
    implemented.

    Attributes:
        _geojson_type: :attr:`GeometryType.POLYGON`
        _coord_depth: ``2`` -- coordinates is a list of rings, each a list of vertices.
        _min_vertices: ``4`` -- at least 3 unique positions plus the closing vertex.

    Example::

        poly = Polygon.from_geojson({
            "type": "Polygon",
            "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]],
        })
        assert poly.bounds == (0, 0, 1, 1)
    """

    _geojson_type = GeometryType.POLYGON
    _coord_depth = 2
    _min_vertices = 4

    @property
    def wkt(self) -> str:
        """WKT representation of this polygon.

        Returns:
            A string of the form ``"POLYGON ((x1 y1, x2 y2, ...))"`` for simple
            (no-hole) polygons.

        Raises:
            NotImplementedError: If the polygon has one or more interior rings.
        """
        if len(self.coordinates) > 1:
            raise NotImplementedError(
                "WKT serialisation for Polygons with interior rings (holes) "
                "is not yet implemented."
            )
        vertices = ", ".join(" ".join(_fmt(c) for c in v) for v in self.coordinates[0])
        return f"POLYGON (({vertices}))"

    def _extra_coordinate_validation(self, coordinates) -> None:
        """Assert that the outer ring is closed (first vertex == last vertex).

        Args:
            coordinates: The raw polygon coordinate array (list of rings).

        Raises:
            ValueError: If the first and last vertices of the outer ring do not match.
        """
        outer = coordinates[0]
        if outer[0] != outer[-1]:
            raise ValueError(
                f"Polygon ring must be closed (first and last vertex must match), "
                f"got {list(outer[0])!r} and {list(outer[-1])!r}."
            )

    @classmethod
    def from_bounds(cls, bounds: tuple[float, ...], crs: CrsType = None) -> Polygon:
        """Construct a rectangular :class:`Polygon` from a bounding box.

        Accepts either 2D bounds ``(x_min, y_min, x_max, y_max)`` or 3D bounds
        ``(x_min, y_min, z_min, x_max, y_max, z_max)``. The result is a closed
        five-vertex rectangular ring. For 3D bounds, *z_min* is used as the constant Z
        coordinate for all vertices (*z_max* is ignored, since a flat rectangle has
        uniform elevation).

        Args:
            bounds: A 4-tuple ``(x_min, y_min, x_max, y_max)`` for 2D, or a 6-tuple
                ``(x_min, y_min, z_min, x_max, y_max, z_max)`` for 3D.
            crs: Optional CRS to associate with the resulting polygon.

        Returns:
            A :class:`Polygon` representing the bounding rectangle.

        Raises:
            ValueError: If *bounds* does not have exactly 4 or 6 values.

        Example::

            bbox = Polygon.from_bounds((0.0, 0.0, 1.0, 1.0), crs="epsg:27700")
            assert bbox.bounds == (0.0, 0.0, 1.0, 1.0)
        """
        if len(bounds) == 4:
            x_min, y_min, x_max, y_max = bounds
            ring = [
                [x_min, y_min],
                [x_max, y_min],
                [x_max, y_max],
                [x_min, y_max],
                [x_min, y_min],
            ]
        elif len(bounds) == 6:
            x_min, y_min, z_min, x_max, y_max, z_max = bounds
            ring = [
                [x_min, y_min, z_min],
                [x_max, y_min, z_min],
                [x_max, y_max, z_min],
                [x_min, y_max, z_min],
                [x_min, y_min, z_min],
            ]
        else:
            raise ValueError(
                f"bounds must be a 4-tuple (x_min, y_min, x_max, y_max) or "
                f"6-tuple (x_min, y_min, z_min, x_max, y_max, z_max), "
                f"got {len(bounds)} values."
            )
        return cls.from_geojson({"type": "Polygon", "coordinates": [ring]}, crs=crs)


class MultiPoint(MultiGeometry):
    """A GeoJSON MultiPoint geometry.

    Represents a collection of zero or more positions.

    Attributes:
        _geojson_type: :attr:`GeometryType.MULTIPOINT`
        _coord_depth: ``1`` -- coordinates is a list of vertices.
        _min_vertices: ``1``
        _single_type: :class:`Point` (wired after class definition).

    Example::

        mp = MultiPoint.from_wkt("MULTIPOINT ((0 0), (1 1), (2 2))")
        assert len(mp.coordinates) == 3
    """

    _geojson_type = GeometryType.MULTIPOINT
    _coord_depth = 1
    _min_vertices = 1
    _single_type: type[Geometry]  # set after Point is defined

    @property
    def wkt(self) -> str:
        """WKT representation of this multi-point.

        Returns:
            A string of the form ``"MULTIPOINT ((x1 y1), (x2 y2), ...)"``.
        """
        points = ", ".join(
            f"({' '.join(_fmt(c) for c in v)})" for v in self.coordinates
        )
        return f"MULTIPOINT ({points})"


class MultiLineString(MultiGeometry):
    """A GeoJSON MultiLineString geometry.

    Represents a collection of linestrings. Each constituent linestring must have at
    least two vertices.

    Attributes:
        _geojson_type: :attr:`GeometryType.MULTILINESTRING`
        _coord_depth: ``2`` -- coordinates is a list of linestrings, each a list of
            vertices.
        _min_vertices: ``2``
        _single_type: :class:`LineString` (wired after class definition).

    Example::

        mls = MultiLineString.from_wkt(
            "MULTILINESTRING ((0 0, 1 1), (2 2, 3 3))"
        )
    """

    _geojson_type = GeometryType.MULTILINESTRING
    _coord_depth = 2
    _min_vertices = 2
    _single_type: type[Geometry]  # set after LineString is defined

    @property
    def wkt(self) -> str:
        """WKT representation of this multi-linestring.

        Returns:
            A string of the form
            ``"MULTILINESTRING ((x1 y1, x2 y2), (x3 y3, x4 y4), ...)"``.
        """
        lines = ", ".join(
            f"({', '.join(' '.join(_fmt(c) for c in v) for v in line)})"
            for line in self.coordinates
        )
        return f"MULTILINESTRING ({lines})"


class MultiPolygon(MultiGeometry):
    """A GeoJSON MultiPolygon geometry.

    Represents a collection of polygons. Each constituent polygon must have at least
    four vertices (three unique plus closing) and a closed outer ring.

    Attributes:
        _geojson_type: :attr:`GeometryType.MULTIPOLYGON`
        _coord_depth: ``3`` -- coordinates is a list of polygons, each a list of rings,
            each a list of vertices.
        _min_vertices: ``4``
        _single_type: :class:`Polygon` (wired after class definition).

    Example::

        mpoly = MultiPolygon.from_wkt(
            "MULTIPOLYGON (((0 0, 1 0, 1 1, 0 0)), ((2 2, 3 2, 3 3, 2 2)))"
        )
        assert len(mpoly.coordinates) == 2
    """

    _geojson_type = GeometryType.MULTIPOLYGON
    _coord_depth = 3
    _min_vertices = 4
    _single_type: type[Geometry]  # set after Polygon is defined

    @property
    def wkt(self) -> str:
        """WKT representation of this multi-polygon.

        Returns:
            A string of the form ``"MULTIPOLYGON (((x1 y1, ...)), ((x2 y2, ...)))"``.
        """
        polygons = ", ".join(
            f"(({', '.join(' '.join(_fmt(c) for c in v) for v in polygon[0])}))"
            for polygon in self.coordinates
        )
        return f"MULTIPOLYGON ({polygons})"

    def _extra_coordinate_validation(self, coordinates) -> None:
        """Assert that every constituent polygon has a closed outer ring.

        Args:
            coordinates: The raw multi-polygon coordinate array.

        Raises:
            ValueError: If the outer ring of any constituent polygon is not closed.
        """
        for p_idx, polygon in enumerate(coordinates):
            outer = polygon[0]
            if outer[0] != outer[-1]:
                raise ValueError(
                    f"MultiPolygon ring at polygon {p_idx} must be closed "
                    f"(first and last vertex must match), "
                    f"got {list(outer[0])!r} and {list(outer[-1])!r}."
                )


# ---------------------------------------------------------------------------
# Post-definition wiring
# ---------------------------------------------------------------------------

_SINGLEPART_BY_DEPTH[0] = Point
_SINGLEPART_BY_DEPTH[1] = LineString
_SINGLEPART_BY_DEPTH[2] = Polygon

MultiPoint._single_type = Point
MultiLineString._single_type = LineString
MultiPolygon._single_type = Polygon
