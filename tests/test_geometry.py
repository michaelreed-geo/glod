import importlib

import pytest

import glod.config as config
from glod.geometry import (
    Geometry,
    bounds_to_polygon_wkt,
    check_geometries_intersect,
    check_segments_intersect,
    coordinates_to_line_segments,
    coordinates_to_wkt,
    do_bounds_interesct,
    flatten_coordinates_to_str,
    format_wkt_string,
    geojson_to_wkt,
    get_coordinates_from_wkt,
    get_geometry_centroid,
    get_linestring_centroid,
    get_points_orientation,
    get_polygon_centroid,
    get_wkt_type_from_str,
    is_crs_valid,
    is_point_on_line_segment,
    is_wkt_string_valid,
    transform_coordinates,
    wkt_to_geojson,
)


@pytest.fixture(autouse=True)
def reset_use_pyproj():
    """
    Ensure each test starts with a clean module state.
    """
    importlib.reload(config)
    yield
    importlib.reload(config)


@pytest.mark.parametrize(
    "bounds, expected",
    [
        ((0, 0, 10, 10), "POLYGON ((0 0, 0 10, 10 10, 10 0, 0 0))"),
        ((-10, -50, 20, 40), "POLYGON ((-10 -50, -10 40, 20 40, 20 -50, -10 -50))"),
    ],
)
def test_bounds_to_polygon_wkt(bounds, expected):
    assert bounds_to_polygon_wkt(bounds) == expected


@pytest.mark.parametrize(
    "line1, line2, expected",
    [
        # Proper intersection (X shape)
        (((0, 0), (4, 4)), ((0, 4), (4, 0)), True),
        # No intersection (clearly separate)
        (((0, 0), (1, 1)), ((2, 2), (3, 3)), False),
        # Touching at endpoint
        (((0, 0), (2, 2)), ((2, 2), (4, 0)), True),
        # Collinear and overlapping
        (((0, 0), (4, 4)), ((2, 2), (6, 6)), True),
        # Collinear but disjoint
        (((0, 0), (1, 1)), ((2, 2), (3, 3)), False),
        # Parallel non-intersecting
        (((0, 0), (4, 0)), ((0, 1), (4, 1)), False),
        # Vertical and horizontal crossing
        (((2, -1), (2, 3)), ((0, 1), (4, 1)), True),
        # Vertical and horizontal non-crossing
        (((2, -1), (2, 0)), ((0, 1), (4, 1)), False),
    ],
)
def test_check_segments_intersect(line1, line2, expected):
    assert check_segments_intersect(line1, line2) is expected


@pytest.mark.parametrize(
    "coordinates, expected",
    [
        # linestring type where coordinates[0] != coordinates[-1]
        (
            ((0.9, 0.1), (5.5, 5.3), (10.7, 10.5)),
            (((0.9, 0.1), (5.5, 5.3)), ((5.5, 5.3), (10.7, 10.5))),
        ),
        # polygon type where coordinates[0] == coordinates[-1]
        (
            ((623, 200), (896, 150), (702, 180), (623, 200)),
            (
                ((623, 200), (896, 150)),
                ((896, 150), (702, 180)),
                ((702, 180), (623, 200)),
            ),
        ),
    ],
)
def test_coordinates_to_line_segments(coordinates, expected):
    assert coordinates_to_line_segments(coordinates) == expected


@pytest.mark.parametrize(
    "coordinates, expected",
    [
        ((0, 0), "POINT (0 0)"),
        ((23.5, 56.2), "POINT (23.5 56.2)"),
        (((0, 0), (1, 1), (2, 2)), "LINESTRING (0 0, 1 1, 2 2)"),
        (
            ((0, 0), (1, 1), (2, 2), (0, 0), (5, 0)),
            "LINESTRING (0 0, 1 1, 2 2, 0 0, 5 0)",
        ),
        (((0, 0), (1, 1), (2, 2), (0, 0)), "POLYGON ((0 0, 1 1, 2 2, 0 0))"),
    ],
)
def test_coordinates_to_wkt(coordinates, expected):
    assert coordinates_to_wkt(coordinates) == expected


@pytest.mark.parametrize(
    "geometry1, geometry2, expected",
    [
        (
            Geometry.from_wkt("Polygon ((0 0, 0 10, 10 10, 10 0, 0 0))"),
            Geometry.from_wkt("Polygon ((5 5, 5 15, 15 15, 15 5, 5 5))"),
            True,
        ),
        (
            Geometry.from_wkt("Polygon ((0 0, 0 10, 10 10, 10 0, 0 0))"),
            Geometry.from_wkt("LineString (0 0, 20 20)"),
            True,
        ),
        (
            Geometry.from_wkt("LineString (0 0, 10 10)"),
            Geometry.from_wkt("LineString (20 20, 30 30)"),
            False,
        ),
    ],
)
def test_do_bounds_intersect(geometry1, geometry2, expected):
    assert do_bounds_interesct(geometry1, geometry2) == expected


@pytest.mark.parametrize(
    "coordinates, expected",
    [
        ((3.256, 10023.562), "(3.256 10023.562)"),
        (((0, 2), (3, 5), (6.5, 10)), "(0 2, 3 5, 6.5 10)"),
        (
            ((242.5, 302.5), (98.3, 953.7), (242.2, 302.5)),
            "(242.5 302.5, 98.3 953.7, 242.2 302.5)",
        ),
    ],
)
def test_flatten_coordinates_to_str(coordinates, expected):
    assert flatten_coordinates_to_str(coordinates) == expected


@pytest.mark.parametrize(
    "wkt_in, expected",
    [
        ("Point (5 0)", "POINT (5.0 0.0)"),
        ("PoInT (  2.535 0.234 )", "POINT (2.535 0.234)"),
        ("LineString (0 0, 10 5, 30 30)", "LINESTRING (0.0 0.0, 10.0 5.0, 30.0 30.0)"),
        (
            "LiNeStRiNg   (  4.5223 342.2, 34.1 985.3    )",
            "LINESTRING (4.5223 342.2, 34.1 985.3)",
        ),
        (
            "Polygon ((0 0, 4 0, 4 4, 0 0))",
            "POLYGON ((0.0 0.0, 4.0 0.0, 4.0 4.0, 0.0 0.0))",
        ),
        (
            "pOlYgOn (  ( 2.34 1.5, 98.5 75.3, 2.34 1.5  )  )",
            "POLYGON ((2.34 1.5, 98.5 75.3, 2.34 1.5))",
        ),
    ],
)
def test_format_wkt_string(wkt_in, expected):
    assert format_wkt_string(wkt_in) == expected


@pytest.mark.parametrize(
    "wkt, geojson",
    [
        ("POINT (50.3 23.5)", {"type": "Point", "coordinates": [50.3, 23.5]}),
        (
            "LINESTRING (32.5 47.1, 89.5 90.5, 153.2 200.7)",
            {
                "type": "LineString",
                "coordinates": [[32.5, 47.1], [89.5, 90.5], [153.2, 200.7]],
            },
        ),
        (
            "POLYGON ((0 0, 0 5, 5 5, 5 0, 0 0))",
            {
                "type": "Polygon",
                "coordinates": [[[0, 0], [0, 5], [5, 5], [5, 0], [0, 0]]],
            },
        ),
    ],
)
def test_geojson_to_wkt(wkt, geojson):
    assert geojson_to_wkt(geojson) == wkt


@pytest.mark.parametrize(
    "wkt, expected",
    [
        ("Point (0 1)", (0, 1)),
        ("POINT (4.23 1.43)", (4.23, 1.43)),
        (
            "LineString (0.2 2.3, 1.4 6.3, 5.9 10.5)",
            ((0.2, 2.3), (1.4, 6.3), (5.9, 10.5)),
        ),
        (
            "LINESTRING  ( 200.42 62.56,  20.12 9.23,199.60 8762.4 )",
            ((200.42, 62.56), (20.12, 9.23), (199.6, 8762.4)),
        ),
        (
            "Polygon ((0 0, 10 0, 10 10, 0 10, 0 0))",
            ((0, 0), (10, 0), (10, 10), (0, 10), (0, 0)),
        ),
        (
            "POLYGON ((209.2 35, 9845.2 563.2, 985.1 9686, 283.5 123, 209.2 35))",
            ((209.2, 35), (9845.2, 563.2), (985.1, 9686), (283.5, 123), (209.2, 35)),
        ),
    ],
)
def test_get_coordinates_from_wkt(wkt, expected):
    assert get_coordinates_from_wkt(wkt) == expected


@pytest.mark.parametrize(
    "wkt, accuracy, expected",
    [
        ("Point (5 5)", None, (5, 5)),
        ("Point (20.312 8.89543", 2, (20.31, 8.90)),
        ("LineString (-1 1, 1 2, 1 3, 3 3, 3 -1)", 3, (1.841, 1.717)),
        ("Polygon ((0 0, 0 10, 10 10, 10 0, 0 0))", None, (5, 5)),
        ("Polygon ((-1 1, 1 2, 1 3, 3 3, 3 -1, -1 1))", 3, (1.667, 1.185)),
    ],
)
def test_get_geometry_centroid(wkt, accuracy, expected):
    assert get_geometry_centroid(wkt, accuracy) == expected


@pytest.mark.parametrize(
    "coordinates, accuracy, expected",
    [(((-1, 1), (1, 2), (1, 3), (3, 3), (3, -1)), 3, (1.841, 1.717))],
)
def test_get_linestring_centroid(coordinates, accuracy, expected):
    assert get_linestring_centroid(coordinates, accuracy) == expected


@pytest.mark.parametrize(
    "p1, p2, p3, expected",
    [
        # collinear points
        ((0, 0), (1, 1), (2, 2), 0),
        ((-1, -1), (0, 0), (1, 1), 0),
        # clockwise
        ((0, 0), (4, 4), (2, 1), 1),
        ((1, 1), (3, 3), (4, 2), 1),
        # anti-clockwise
        ((0, 0), (4, 4), (2, 5), 2),
        ((1, 1), (3, 3), (2, 4), 2),
    ],
)
def test_get_points_orientation(p1, p2, p3, expected):
    assert get_points_orientation(p1, p2, p3) == expected


@pytest.mark.parametrize(
    "coordinates, accuracy, expected",
    [
        (((0, 0), (0, 10), (10, 10), (10, 0), (0, 0)), None, (5, 5)),
        (((-1, 1), (1, 2), (1, 3), (3, 3), (3, -1), (-1, 1)), 3, (1.667, 1.185)),
    ],
)
def test_get_polygon_centroid(coordinates, accuracy, expected):
    assert get_polygon_centroid(coordinates, accuracy) == expected


@pytest.mark.parametrize(
    "wkt_str, expected",
    [
        ("point (0 0)", "Point"),
        ("POINT (0 0)", "Point"),
        ("pOiNt (0 0)", "Point"),
        ("linestring (0 0, 1 1)", "LineString"),
        ("LINESTRING (0 0, 1 1)", "LineString"),
        ("LiNeStRiNg (0 0, 1 1)", "LineString"),
        ("polygon ((0 0, 1 1, 0 0))", "Polygon"),
        ("POLYGON ((0 0, 1 1, 0 0))", "Polygon"),
        ("pOlYgOn ((0 0, 1 1, 0 0))", "Polygon"),
    ],
)
def test_get_wkt_type_from_str(wkt_str, expected):
    assert get_wkt_type_from_str(wkt_str) == expected


@pytest.mark.parametrize(
    "crs, expected",
    [("EPSG:3857", True), ("EPSG:4326", True), ("abcdef", False), ("27700", True)],
)
def test_is_crs_valid(crs, expected):
    config.set_use_pyproj(True)
    assert is_crs_valid(crs) is expected


@pytest.mark.parametrize(
    "line, point, expected",
    [(((0, 0), (10, 10)), (5, 5), True), (((10, 10), (-30, -50)), (20, 15), False)],
)
def test_is_point_on_line_segment(line, point, expected):
    assert is_point_on_line_segment(line, point) == expected


@pytest.mark.parametrize(
    "wkt, expected",
    [
        ("Point (0 1)", True),  # default format
        ("POINT (5 2)", True),  # uppercase
        ("Point (3.53 202.626)", True),  # decimals
        ("Point   (3 5)", True),  # leading spaces
        ("Point (   6.5 2.3 )", True),  # more leading spaces
        ("Point (1.23 4.56  )", True),  # trailing spaces
        ("Point ((1 2))", False),  # too many brackets
        ("Point [2 3]", False),  # square brackets instead of round
        ("Point (1 )", False),  # missing coordinate
        ("Point (2.3, 6.3)", False),  # coordinate pair delimited by comma
        ("Point (1 a)", False),  # non-numeric coordinate
        ("Point (None 1)", False),  # null coordinate
        ("abc (0 4)", False),  # invalid type string
    ],
)
def test_is_wkt_string_valid_point(wkt, expected):
    assert is_wkt_string_valid(wkt, "POINT") is expected


@pytest.mark.parametrize(
    "wkt, expected",
    [
        ("LineString (1 2, 3 5, 6 10)", True),  # default format
        ("LINESTRING (1 0, 2 2, 3 6)", True),  # uppercase
        (
            "LINESTRING (10.3 35.1, 20.2 58.7, 100.2 68.2, 168.4 200.2)",
            True,
        ),  # decimals
        ("Linestring   (3 5, 10 2)", True),  # leading spaces
        ("LiNeStRiNg (    60 2, 46 50, 0 0)", True),  # more leading spaces
        ("LineString (1.2 3.5, 95.2 50   )", True),  # trailing spaces
        ("LINESTRING ((20 4),  30 5))", False),  # too many brackets
        ("Linestring [20 30, 30 40, 40 50]", False),  # square brackets instead of round
        ("Linestring (0 5, 2 4, 2 1, 3)", False),  # missing coordinate
        ("LineString (3 1, 3 6, 5, 10)", False),  # coordinate pair delimited by comma
        ("Linestring (0 0, b 2, 6 10)", False),  # non-numeric coordinate
        ("Linestring (0 4, 1 0, None)", False),  # null coordinate
    ],
)
def test_is_wkt_string_valid_linestring(wkt, expected):
    assert is_wkt_string_valid(wkt, "LINESTRING") is expected


@pytest.mark.parametrize(
    "wkt, expected",
    [
        ("Polygon ((0 0, 4 0, 4 4, 0 4, 0 0))", True),  # default square
        ("POLYGON ((1 1, 5 1, 5 5, 1 5, 1 1))", True),  # uppercase
        ("PoLyGoN ((10.5 20.1, 30.2 40.3, 50.4 60.5, 10.5 20.1))", True),  # decimals
        ("Polygon   ((3 5, 10 2, 6 8, 3 5))", True),  # leading spaces
        ("Polygon ((   0 3, 5 1, 0 3))", True),  # more leading spaces
        ("POLYGON ((0 0, 1 0, 1 1, 0 1, 0 0   ))", True),  # trailing spaces
        ("POLYGON (0 0, 4 0, 4 4, 0 4, 0 0)", False),  # missing double parentheses
        ("POLYGON ((0 0, 4 0, 4 4, 0 4))", False),  # not closed
        ("POLYGON (((0 0, 4 0, 4 4, 0 4, 0 0)))", False),  # too many brackets
        ("POLYGON [0 0, 4 0, 4 4, 0 4, 0 0]", False),  # square brackets
        ("Polygon [[0 0, 4 0, 4 4, 0 4, 0 0]]", False),  # more square brackets
        ("POLYGON ((0 0, 4 0, 4 4, 0))", False),  # missing coordinate
        ("POLYGON ((0 0, b 2, 6 10, 0 0))", False),  # non-numeric
        ("POLYGON ((0 0, 4 0, 4 4, None, 0 0))", False),  # null coordinate
    ],
)
def test_is_wkt_string_valid_polygon(wkt, expected):
    assert is_wkt_string_valid(wkt, "POLYGON") is expected


# @pytest.mark.parametrize(
#     "in_coordinates, in_crs, out_crs, always_xy, accuracy, out_coordinates",
#     [
#         # TODO
#     ]
# )
# def test_transform_coordinates(in_coordinates, in_crs, out_crs, always_xy, accuracy, out_coordinates):
#     assert transform_coordinates(in_coordinates, in_crs, out_crs, always_xy, accuracy) == out_coordinates


@pytest.mark.parametrize(
    "wkt, expected",
    [
        ("POINT (50.3 23.5)", {"type": "Point", "coordinates": [50.3, 23.5]}),
        (
            "LINESTRING (32.5 47.1, 89.5 90.5, 153.2 200.7)",
            {
                "type": "LineString",
                "coordinates": [[32.5, 47.1], [89.5, 90.5], [153.2, 200.7]],
            },
        ),
        (
            "POLYGON ((0 0, 0 5, 5 5, 5 0, 0 0))",
            {
                "type": "Polygon",
                "coordinates": [[[0, 0], [0, 5], [5, 5], [5, 0], [0, 0]]],
            },
        ),
    ],
)
def test_wkt_to_geojson(wkt, expected):
    assert wkt_to_geojson(wkt) == expected


def test_geometry_geo_interface(monkeypatch):
    geometry = Geometry.__new__(Geometry)  # bypass __init__ logic
    # mock properties passed to __geo_interface
    monkeypatch.setattr(Geometry, "type", property(lambda self: "Polygon"))
    monkeypatch.setattr(Geometry, "bounds", property(lambda self: (0, 0, 10, 10)))
    monkeypatch.setattr(Geometry, "coordinates", property(lambda self: ((0, 0), (10, 0), (10, 10), (0, 10))))

    actual = geometry.__geo_interface__
    expected = {
        "type": "Polygon",
        "bbox": (0, 0, 10, 10),
        "coordinates": ((0, 0), (10, 0), (10, 10), (0, 10))
    }
    assert actual == expected


@pytest.mark.parametrize(
    "geometry, expected",
    [
        (Geometry("Point (0 0)", "EPSG:3857"), None),
        (Geometry("LineString (0 0, 10 10)"), (0, 0, 10, 10)),
        (Geometry("Polygon ((0 0, 0 10, 10 10, 10 0, 0 0))", "EPSG:27700"), (0, 0, 10, 10))
    ]
)
def test_geometry_bounds(geometry, expected):
    assert geometry.bounds == expected


@pytest.mark.parametrize(
    "geometry, expected",
    [
        (Geometry("Point (0 0)", "EPSG:3857"), Geometry("Point (0 0)", "EPSG:3857")),
        (Geometry("LineString (0 0, 10 10)"), Geometry("Point (5 5)")),
        (Geometry("Polygon ((0 0, 0 10, 10 10, 10 0, 0 0))", "EPSG:27700"), Geometry("Point( 5 5)", "EPSG:27700"))
    ]
)
def test_geometry_centroid(geometry, expected):
    assert geometry.centroid.coordinates == expected.coordinates
    assert geometry.centroid.crs == expected.crs


@pytest.mark.parametrize(
    "geometry, expected",
    [
        (Geometry("Point (0 0)", "EPSG:3857"), (0, 0)),
        (Geometry("LineString (0 0, 10 10)"), ((0, 0), (10, 10))),
        (Geometry("Polygon ((0 0, 0 10, 10 10, 10 0, 0 0))", "EPSG:27700"), ((0, 0), (0, 10), (10, 10), (10, 0), (0, 0)))
    ]
)
def test_geometry_coordinates(geometry, expected):
    assert geometry.coordinates == expected


@pytest.mark.parametrize(
    "geometry, expected",
    [
        (Geometry("Point (0 0)", "EPSG:3857"), "EPSG:3857"),
        (Geometry("LineString (0 0, 10 10)"), None),
        (Geometry("Polygon ((0 0, 0 10, 10 10, 10 0, 0 0))", "EPSG:27700"), "EPSG:27700")
    ]
)
def test_geometry_crs(geometry, expected):
    assert geometry.crs == expected


@pytest.mark.parametrize(
    "geometry, expected",
    [
        (Geometry("Point (0 0)", "EPSG:3857"), None),
        (Geometry("LineString (0 0, 10 10)"), "POLYGON ((0.0 0.0, 0.0 10.0, 10.0 10.0, 10.0 0.0, 0.0 0.0))"),
        (Geometry("Polygon ((0 0, 0 10, 10 10, 10 0, 0 0))", "EPSG:27700"), "POLYGON ((0.0 0.0, 0.0 10.0, 10.0 10.0, 10.0 0.0, 0.0 0.0))")
    ]
)
def test_geometry_envelope(geometry, expected):
    if expected is None:
        assert geometry.envelope is expected
    else:
        assert geometry.envelope.to_wkt == expected


@pytest.mark.parametrize(
    "geometry, expected",
    [
        (Geometry("Point (0 0)", "EPSG:3857"), "Point"),
        (Geometry("LineString (0 0, 10 10)"), "LineString"),
        (Geometry("Polygon ((0 0, 0 10, 10 10, 10 0, 0 0))", "EPSG:27700"), "Polygon")
    ]
)
def test_geometry_type(geometry, expected):
    assert geometry.type == expected


@pytest.mark.parametrize(
    "bounds, crs, expected",
    [
        # bounds as tuple
        ((0, 0, 10, 10), "EPSG:4326", "POLYGON ((0.0 0.0, 0.0 10.0, 10.0 10.0, 10.0 0.0, 0.0 0.0))"),
        # bounds as list
        ([0, 20, 10, 50], "EPSG:1", "POLYGON ((0.0 20.0, 0.0 50.0, 10.0 50.0, 10.0 20.0, 0.0 20.0))")
    ]
)
def test_geometry_from_bounds(bounds, crs, expected):
    geometry = Geometry.from_bounds(bounds, crs)
    assert geometry.to_wkt == expected
    assert geometry.crs == crs


@pytest.mark.parametrize(
    "coordinates, crs, expected",
    [
        # coordinates as tuple
        (((0, 0), (100, 100), (-100, 0), (0, 0)), "EPSG:0", "POLYGON ((0.0 0.0, 100.0 100.0, -100.0 0.0, 0.0 0.0))"),
        # coordinates as list
        ([[0, 0], [5, 5], [10, 20]], "EPSG:1234", "LINESTRING (0.0 0.0, 5.0 5.0, 10.0 20.0)")
    ]
)
def test_geometry_from_coordinates(coordinates, crs, expected):
    geometry = Geometry.from_coordinates(coordinates, crs)
    assert geometry.to_wkt == expected
    assert geometry.crs == crs


@pytest.mark.parametrize(
    "geojson, crs, expected",
    [
        ({"type": "Point", "coordinates": [10, 5]}, "EPSG:3857", "POINT (10.0 5.0)"),
        ({"type": "LineString", "coordinates": [[0, 0], [-10, -50]]}, "EPSG:1234", "LINESTRING (0.0 0.0, -10.0 -50.0)"),
        ({"type": "Polygon", "coordinates": [[[50, 50], [20, 20], [0, 50], [50, 50]]]}, "EPSG:4326", "POLYGON ((50.0 50.0, 20.0 20.0, 0.0 50.0, 50.0 50.0))")
    ]
)
def test_geometry_from_geojson(geojson, crs, expected):
    geometry = Geometry.from_geojson(geojson, crs)
    assert geometry.to_wkt == expected
    assert geometry.crs == crs


# make a dummy generic python object that implements the __geo_interface__ protocol
class DummyObj:
    def __init__(self, type_, bounds, coordinates):
        self.type = type_
        self.bounds = bounds
        self.coordinates = coordinates
    @property
    def __geo_interface__(self):
        geo = {
            "type": self.type,
            "bbox": self.bounds,
            "coordinates": self.coordinates
        }
        return geo


@pytest.mark.parametrize(
    "type_, bounds, coordinates, crs, expected",
    [
        ("Point", None, (5, 8), "EPSG:1", "POINT (5.0 8.0)"),
        ("LineString", [0, 0, 10, 10], [[0, 0], [10, 10]], "EPSG:7", "LINESTRING (0.0 0.0, 10.0 10.0)")
    ]
)
def test_geometry_from_object(type_, bounds, coordinates, crs, expected):
    an_object = DummyObj(type_, bounds, coordinates)
    geometry = Geometry.from_object(an_object, crs)
    assert geometry.to_wkt == expected
    assert geometry.crs == crs


def test_geometry_from_object_unsupported_type():
    an_object = DummyObj("MultiPoint", None, [[[0, 0], [1, 1]], [2, 2]])
    with pytest.raises(ValueError, match="Unsupported geometry type MultiPoint"):
        Geometry.from_object(an_object)


@pytest.mark.parametrize(
    "wkt, crs, expected",
    [
        ("Point (5 10)", "EPSG:123", (5.0, 10.0)),
        ("LINESTRING (12 34, 56 78)", "EPSG:3857", ((12.0, 34.0), (56.0, 78.0))),
        ("Polygon ((0 0, 10 10, 10 0, 0 0))", None, ((0, 0), (10, 10), (10, 0), (0, 0)))
    ]
)
def test_geometry_from_wkt(wkt, crs, expected):
    geometry = Geometry.from_wkt(wkt, crs)
    assert geometry.coordinates == expected
    assert geometry.crs == crs

