from glod.utils import get_coordinates_from_wkt, flatten_coordinate_tuple_to_str, is_wkt_string_valid

import pytest


def test_get_coordinates_from_wkt():
    point_inputs = {
        "Point (0 1)": (0, 1),
        "POINT (4.23 1.43)": (4.23, 1.43),
        "LineString (0.2 2.3, 1.4 6.3, 5.9 10.5)": ((0.2, 2.3), (1.4, 6.3), (5.9, 10.5)),
        "LINESTRING  ( 200.42 62.56,  20.12 9.23,199.60 8762.4 )": ((200.42, 62.56), (20.12, 9.23), (199.6, 8762.4)),
        "Polygon ((0 0, 10 0, 10 10, 0 10, 0 0))": ((0, 0), (10, 0), (10, 10), (0, 10), (0, 0)),
        "POLYGON ((209.2 35, 9845.2 563.2, 985.1 9686, 283.5 123, 209.2 35))": ((209.2, 35), (9845.2, 563.2), (985.1, 9686), (283.5, 123), (209.2, 35))
    }
    for wkt, coordinates in point_inputs.items():
        assert get_coordinates_from_wkt(wkt) == coordinates

def test_flatten_coordinate_tuple_to_str():
    inputs = {
        "(3.256 10023.562)": (3.256, 10023.562),  # point
        "(0 2, 3 5, 6.5 10)": ((0, 2), (3, 5), (6.5, 10)),  # linestring
        "(242.5 302.5, 984.3 953.7, 242.2 302.5)": ((242.5, 302.5), (984.3, 953.7), (242.2, 302.5))  # polygon
    }
    for coordinates_str, coordinates in inputs.items():
        assert flatten_coordinate_tuple_to_str(coordinates) == coordinates_str

def test_is_wkt_string_valid_POINT():
    inputs = {
        "Point (0 1)": True,  # default format
        "POINT (5 2)": True,  # uppercase
        "Point (3.53 202.626)": True,  # decimals
        "Point   (3 5)": True,  # leading spaces
        "Point (   6.5 2.3 )": True,  # more leading spaces
        "Point (1.23 4.56  )": True,  # trailing spaces
        "Point ((1 2))": False,  # too many brackets
        "Point [2 3]": False,  # square brackets instead of round
        "Point (1 )": False,  # missing coordinate
        "Point (2.3, 6.3)": False,  # coordinate pair delimited by comma
        "Point (1 a)": False,  # non-numeric coordinate
        "Point (None 1)": False,  # null coordinate
        "abc (0 4)": False  # invalid type string
    }
    for wkt, validity in inputs.items():
        assert is_wkt_string_valid(wkt, "POINT") is validity

def test_is_wkt_string_valid_LINESTRING():
    inputs = {
        "LineString (1 2, 3 5, 6 10)": True,  # default format
        "LINESTRING (1 0, 2 2, 3 6)": True,  # uppercase
        "LINESTRING (10.3 35.1, 20.2 58.7, 100.2 68.2, 168.4 200.2)": True,  # decimals
        "Linestring   (3 5, 10 2)": True,  # leading spaces
        "LiNeStRiNg (    60 2, 46 50, 0 0)": True,  # more leading spaces
        "LineString (1.2 3.5, 95.2 50   )": True,  # trailing spaces
        "LINESTRING ((20 4,  30 5))": False,  # too many brackets
        "Linestring [20 30, 30 40, 40 50]": False,  # square brackets instead of round
        "Linestring (0 5, 2 4, 2 1, 3)": False,  # missing coordinate
        "LineString (3 1, 3 6, 5, 10)": False,  # coordinate pair delimited by comma
        "Linestring (0 0, b 2, 6 10)": False,  # non-numeric coordinate
        "Linestring (0 4, 1 0, None)": False  # null coordinate
    }
    for wkt, validity in inputs.items():
        assert is_wkt_string_valid(wkt, "LINESTRING") is validity

# TODO: polygon validity
