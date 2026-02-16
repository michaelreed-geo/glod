import pytest

from glod.geometry import get_coordinates_from_wkt, flatten_coordinates_to_str, is_wkt_string_valid, \
    format_wkt_string, wkt_to_geojson, geojson_to_wkt, is_crs_valid, coordinates_to_wkt, \
    transform_coordinates, get_wkt_type_from_str, get_linestring_centroid, get_polygon_centroid, \
    get_geometry_centroid, bounds_to_polygon_wkt


@pytest.mark.parametrize(
    "bounds, wkt",
    [
        ((0, 0, 10, 10), "POLYGON ((0 0, 0 10, 10 10, 10 0, 0 0))"),
        ((-10, -50, 20, 40), "POLYGON ((-10 -50, -10 40, 20 40, 20 -50, -10 -50))"),
    ],
)
def test_bounds_to_polygon_wkt(bounds, wkt):
    assert bounds_to_polygon_wkt(bounds) == wkt


@pytest.mark.parametrize(
    "coordinates, wkt",
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
def test_coordinates_to_wkt(coordinates, wkt):
    assert coordinates_to_wkt(coordinates) == wkt


@pytest.mark.parametrize(
    "coordinates, coordinates_str",
    [
        ((3.256, 10023.562), "(3.256 10023.562)"),
        (((0, 2), (3, 5), (6.5, 10)), "(0 2, 3 5, 6.5 10)"),
        (
            ((242.5, 302.5), (98.3, 953.7), (242.2, 302.5)),
            "(242.5 302.5, 98.3 953.7, 242.2 302.5)",
        ),
    ],
)
def test_flatten_coordinates_to_str(coordinates, coordinates_str):
    assert flatten_coordinates_to_str(coordinates) == coordinates_str


@pytest.mark.parametrize(
    "wkt_in, wkt_out",
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
def test_format_wkt_string(wkt_in, wkt_out):
    assert format_wkt_string(wkt_in) == wkt_out


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
    "wkt, coordinates",
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
def test_get_coordinates_from_wkt(wkt, coordinates):
    assert get_coordinates_from_wkt(wkt) == coordinates


@pytest.mark.parametrize(
    "wkt_str, wkt_type",
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
def test_get_wkt_type_from_str(wkt_str, wkt_type):
    assert get_wkt_type_from_str(wkt_str) == wkt_type


@pytest.mark.parametrize(
    "crs, validity",
    [("EPSG:3857", True), ("EPSG:4326", True), ("abcdef", False), ("27700", True)],
)
def test_is_crs_valid(crs, validity):
    assert is_crs_valid(crs) is validity


@pytest.mark.parametrize(
    "wkt, validity",
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
def test_is_wkt_string_valid_POINT(wkt, validity):
    assert is_wkt_string_valid(wkt, "POINT") is validity


@pytest.mark.parametrize(
    "wkt, validity",
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
def test_is_wkt_string_valid_LINESTRING(wkt, validity):
    assert is_wkt_string_valid(wkt, "LINESTRING") is validity


@pytest.mark.parametrize(
    "wkt, validity",
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
def test_is_wkt_string_valid_POLYGON(wkt, validity):
    assert is_wkt_string_valid(wkt, "POLYGON") is validity


# @pytest.mark.parametrize(
#     "in_coordinates, in_crs, out_crs, always_xy, accuracy, out_coordinates",
#     [
#         # TODO
#     ]
# )
# def test_transform_coordinates(in_coordinates, in_crs, out_crs, always_xy, accuracy, out_coordinates):
#     assert transform_coordinates(in_coordinates, in_crs, out_crs, always_xy, accuracy) == out_coordinates


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
def test_wkt_to_geojson(wkt, geojson):
    assert wkt_to_geojson(wkt) == geojson
