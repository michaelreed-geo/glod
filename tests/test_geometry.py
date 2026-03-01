"""
Tests for glod/geometry.py

Run with:  pytest test_geometry.py -v
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

import unittest.mock as mock

import pytest
from glod.geometry import (
    MultiGeometry,
    Geometry,
    GeometryType,
    LineString,
    MultiLineString,
    MultiPoint,
    MultiPolygon,
    Point,
    Polygon,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def point_2d():
    return Point(geojson={"type": "Point", "coordinates": [1, 2]}, crs="epsg:27700")

@pytest.fixture
def point_3d():
    return Point(geojson={"type": "Point", "coordinates": [1, 2, 3]}, crs="epsg:27700")

@pytest.fixture
def linestring_2d():
    return LineString(geojson={"type": "LineString", "coordinates": [[0, 0], [1, 1], [2, 0]]}, crs="epsg:27700")

@pytest.fixture
def linestring_3d():
    return LineString(geojson={"type": "LineString", "coordinates": [[0, 0, 1], [1, 1, 2], [2, 0, 3]]}, crs="epsg:27700")

@pytest.fixture
def polygon_2d():
    return Polygon(geojson={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}, crs="epsg:27700")

@pytest.fixture
def multipoint_2d():
    return MultiPoint(geojson={"type": "MultiPoint", "coordinates": [[0, 0], [1, 1], [2, 2]]}, crs="epsg:27700")

@pytest.fixture
def multilinestring_2d():
    return MultiLineString(geojson={"type": "MultiLineString", "coordinates": [[[0, 0], [1, 1]], [[2, 2], [3, 3]]]}, crs="epsg:27700")

@pytest.fixture
def multipolygon_2d():
    return MultiPolygon(
        geojson={"type": "MultiPolygon", "coordinates": [
            [[[0, 0], [1, 0], [1, 1], [0, 0]]],
            [[[2, 2], [3, 2], [3, 3], [2, 2]]],
        ]},
        crs="epsg:27700",
    )


# ---------------------------------------------------------------------------
# Point
# ---------------------------------------------------------------------------

class TestPoint:
    def test_type(self, point_2d):
        assert point_2d.type == GeometryType.POINT

    def test_crs(self, point_2d):
        assert point_2d.crs == "epsg:27700"

    def test_coordinates_2d(self, point_2d):
        assert point_2d.coordinates == (1, 2)

    def test_coordinates_3d(self, point_3d):
        assert point_3d.coordinates == (1, 2, 3)

    def test_has_z_false(self, point_2d):
        assert point_2d.has_z is False

    def test_has_z_true(self, point_3d):
        assert point_3d.has_z is True

    def test_bounds_is_none(self, point_2d, point_3d):
        assert point_2d.bounds is None
        assert point_3d.bounds is None

    def test_wkt_2d(self, point_2d):
        assert point_2d.wkt == "POINT (1 2)"

    def test_wkt_3d(self, point_3d):
        assert point_3d.wkt == "POINT (1 2 3)"

    def test_geojson_roundtrip(self, point_2d):
        assert point_2d.geojson == {"type": "Point", "coordinates": [1, 2]}

    def test_geo_interface(self, point_2d):
        assert point_2d.__geo_interface__ == point_2d.geojson

    def test_none_geojson(self):
        p = Point(geojson=None, crs=None)
        assert p.coordinates is None
        assert p.geojson is None
        assert p.bounds is None


# ---------------------------------------------------------------------------
# LineString
# ---------------------------------------------------------------------------

class TestLineString:
    def test_type(self, linestring_2d):
        assert linestring_2d.type == GeometryType.LINESTRING

    def test_has_z_false(self, linestring_2d):
        assert linestring_2d.has_z is False

    def test_has_z_true(self, linestring_3d):
        assert linestring_3d.has_z is True

    def test_bounds_2d(self, linestring_2d):
        assert linestring_2d.bounds == (0, 0, 2, 1)

    def test_bounds_3d(self, linestring_3d):
        assert linestring_3d.bounds == (0, 0, 1, 2, 1, 3)

    def test_wkt_2d(self, linestring_2d):
        assert linestring_2d.wkt == "LINESTRING (0 0, 1 1, 2 0)"

    def test_wkt_3d(self, linestring_3d):
        assert linestring_3d.wkt == "LINESTRING (0 0 1, 1 1 2, 2 0 3)"

    def test_geojson_roundtrip(self, linestring_2d):
        assert linestring_2d.geojson == {"type": "LineString", "coordinates": [[0, 0], [1, 1], [2, 0]]}


# ---------------------------------------------------------------------------
# Polygon
# ---------------------------------------------------------------------------

class TestPolygon:
    def test_type(self, polygon_2d):
        assert polygon_2d.type == GeometryType.POLYGON

    def test_bounds(self, polygon_2d):
        assert polygon_2d.bounds == (0, 0, 1, 1)

    def test_wkt(self, polygon_2d):
        assert polygon_2d.wkt == "POLYGON ((0 0, 1 0, 1 1, 0 0))"

    def test_wkt_with_hole_raises(self):
        # Interior rings (holes) are not yet supported in WKT serialisation.
        polygon = Polygon(
            geojson={"type": "Polygon", "coordinates": [
                [[0, 0], [10, 0], [10, 10], [0, 0]],
                [[2, 2], [5, 2], [5, 5], [2, 2]],   # hole
            ]},
            crs=None,
        )
        with pytest.raises(NotImplementedError):
            _ = polygon.wkt

    def test_unclosed_ring_raises(self):
        with pytest.raises(ValueError, match="closed"):
            Polygon(
                geojson={"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1]]]},
                crs=None,
            )


# ---------------------------------------------------------------------------
# MultiPoint
# ---------------------------------------------------------------------------

class TestMultiPoint:
    def test_type(self, multipoint_2d):
        assert multipoint_2d.type == GeometryType.MULTIPOINT

    def test_bounds(self, multipoint_2d):
        # MultiPoint should have a bounding box unlike a single Point.
        assert multipoint_2d.bounds == (0, 0, 2, 2)

    def test_wkt(self, multipoint_2d):
        assert multipoint_2d.wkt == "MULTIPOINT ((0 0), (1 1), (2 2))"

    def test_geojson_roundtrip(self, multipoint_2d):
        assert multipoint_2d.geojson == {"type": "MultiPoint", "coordinates": [[0, 0], [1, 1], [2, 2]]}


# ---------------------------------------------------------------------------
# MultiLineString
# ---------------------------------------------------------------------------

class TestMultiLineString:
    def test_type(self, multilinestring_2d):
        assert multilinestring_2d.type == GeometryType.MULTILINESTRING

    def test_bounds(self, multilinestring_2d):
        assert multilinestring_2d.bounds == (0, 0, 3, 3)

    def test_wkt(self, multilinestring_2d):
        assert multilinestring_2d.wkt == "MULTILINESTRING ((0 0, 1 1), (2 2, 3 3))"


# ---------------------------------------------------------------------------
# MultiPolygon
# ---------------------------------------------------------------------------

class TestMultiPolygon:
    def test_type(self, multipolygon_2d):
        assert multipolygon_2d.type == GeometryType.MULTIPOLYGON

    def test_bounds(self, multipolygon_2d):
        assert multipolygon_2d.bounds == (0, 0, 3, 3)

    def test_wkt(self, multipolygon_2d):
        assert multipolygon_2d.wkt == "MULTIPOLYGON (((0 0, 1 0, 1 1, 0 0)), ((2 2, 3 2, 3 3, 2 2)))"

    def test_unclosed_ring_raises(self):
        with pytest.raises(ValueError, match="closed"):
            MultiPolygon(
                geojson={"type": "MultiPolygon", "coordinates": [
                    [[[0, 0], [1, 0], [1, 1]]],   # not closed
                ]},
                crs=None,
            )


# ---------------------------------------------------------------------------
# Shared coordinate validation
# ---------------------------------------------------------------------------

class TestCoordinateValidation:
    def test_non_numeric_coordinates_raises(self):
        with pytest.raises(ValueError, match="numbers"):
            LineString(
                geojson={"type": "LineString", "coordinates": [["a", "b"], [1, 2]]},
                crs=None,
            )

    def test_mixed_dimensions_raises(self):
        with pytest.raises(ValueError, match="dimension"):
            LineString(
                geojson={"type": "LineString", "coordinates": [[0, 0], [1, 1, 2]]},
                crs=None,
            )

    def test_too_few_vertices_raises(self):
        with pytest.raises(ValueError, match="at least"):
            LineString(
                geojson={"type": "LineString", "coordinates": [[0, 0]]},
                crs=None,
            )

    def test_1d_vertex_raises(self):
        with pytest.raises(ValueError, match="2 or 3"):
            LineString(
                geojson={"type": "LineString", "coordinates": [[0], [1]]},
                crs=None,
            )

    def test_4d_vertex_raises(self):
        with pytest.raises(ValueError, match="2 or 3"):
            LineString(
                geojson={"type": "LineString", "coordinates": [[0, 1, 2, 3], [4, 5, 6, 7]]},
                crs=None,
            )

    def test_wrong_geojson_type_raises(self):
        with pytest.raises(TypeError, match="LineString"):
            Point(
                geojson={"type": "LineString", "coordinates": [[0, 0], [1, 1]]},
                crs=None,
            )

    def test_missing_type_key_raises(self):
        with pytest.raises(ValueError, match="'type'"):
            Point(geojson={"coordinates": [0, 0]}, crs=None)

    def test_missing_coordinates_key_raises(self):
        with pytest.raises(ValueError, match="'coordinates'"):
            Point(geojson={"type": "Point"}, crs=None)

    def test_non_dict_geojson_raises(self):
        with pytest.raises(TypeError, match="dictionary"):
            Point(geojson="not a dict", crs=None)


# ---------------------------------------------------------------------------
# from_geojson
# ---------------------------------------------------------------------------

class TestFromGeoJSON:
    def test_subclass_constructor(self):
        g = Point.from_geojson({"type": "Point", "coordinates": [1, 2]})
        assert isinstance(g, Point)
        assert g.coordinates == (1, 2)

    def test_abc_dispatches_to_point(self):
        g = Geometry.from_geojson({"type": "Point", "coordinates": [1, 2]})
        assert isinstance(g, Point)

    def test_abc_dispatches_to_linestring(self):
        g = Geometry.from_geojson({"type": "LineString", "coordinates": [[0, 0], [1, 1]]})
        assert isinstance(g, LineString)

    def test_abc_dispatches_to_polygon(self):
        g = Geometry.from_geojson({"type": "Polygon", "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]})
        assert isinstance(g, Polygon)

    def test_abc_dispatches_to_multipoint(self):
        g = Geometry.from_geojson({"type": "MultiPoint", "coordinates": [[0, 0], [1, 1]]})
        assert isinstance(g, MultiPoint)

    def test_abc_dispatches_to_multilinestring(self):
        g = Geometry.from_geojson({"type": "MultiLineString", "coordinates": [[[0, 0], [1, 1]]]})
        assert isinstance(g, MultiLineString)

    def test_abc_dispatches_to_multipolygon(self):
        g = Geometry.from_geojson({"type": "MultiPolygon", "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]]})
        assert isinstance(g, MultiPolygon)

    def test_crs_is_passed_through(self):
        g = Point.from_geojson({"type": "Point", "coordinates": [1, 2]}, crs="epsg:4326")
        assert g.crs == "epsg:4326"

    def test_wrong_type_for_subclass_raises(self):
        with pytest.raises(TypeError):
            Point.from_geojson({"type": "LineString", "coordinates": [[0, 0], [1, 1]]})

# ---------------------------------------------------------------------------
# from_wkt
# ---------------------------------------------------------------------------

class TestFromWKT:
    @pytest.mark.parametrize("cls, wkt", [
        (Point,           "POINT (1 2)"),
        (Point,           "POINT (1 2 3)"),
        (LineString,      "LINESTRING (0 0, 1 1, 2 0)"),
        (LineString,      "LINESTRING (0 0 1, 1 1 2, 2 0 3)"),
        (Polygon,         "POLYGON ((0 0, 1 0, 1 1, 0 0))"),
        (MultiPoint,      "MULTIPOINT ((0 0), (1 1), (2 2))"),
        (MultiLineString, "MULTILINESTRING ((0 0, 1 1), (2 2, 3 3))"),
        (MultiPolygon,    "MULTIPOLYGON (((0 0, 1 0, 1 1, 0 0)), ((2 2, 3 2, 3 3, 2 2)))"),
    ])
    def test_wkt_roundtrip(self, cls, wkt):
        """Parsing a WKT string and re-serialising should return the same string."""
        assert cls.from_wkt(wkt).wkt == wkt

    def test_abc_dispatches_correctly(self):
        g = Geometry.from_wkt("LINESTRING (0 0, 1 1)")
        assert isinstance(g, LineString)

    def test_subclass_from_wkt(self):
        g = LineString.from_wkt("LINESTRING (0 0, 1 1)")
        assert isinstance(g, LineString)

    def test_crs_is_passed_through(self):
        g = Geometry.from_wkt("POINT (1 2)", crs="epsg:4326")
        assert g.crs == "epsg:4326"

    def test_wrong_type_for_subclass_raises(self):
        with pytest.raises(TypeError, match="does not match"):
            Point.from_wkt("LINESTRING (0 0, 1 1)")

    def test_invalid_wkt_raises(self):
        with pytest.raises(ValueError, match="Invalid"):
            Geometry.from_wkt("NOT VALID WKT")

    def test_unknown_geometry_type_raises(self):
        with pytest.raises(ValueError, match="Unsupported"):
            Geometry.from_wkt("TRIANGLE (0 0, 1 0, 0 1)")

    def test_whitespace_tolerance(self):
        """Parser should handle extra whitespace around the WKT string."""
        g = Geometry.from_wkt("  POINT (1 2)  ")
        assert isinstance(g, Point)
        assert g.wkt == "POINT (1 2)"


# ---------------------------------------------------------------------------
# from_object
# ---------------------------------------------------------------------------

class TestFromObject:
    class _FakeGeoObj:
        def __init__(self, geojson):
            self._geojson = geojson

        @property
        def __geo_interface__(self):
            return self._geojson

    def test_dispatches_from_abc(self):
        obj = self._FakeGeoObj({"type": "Point", "coordinates": [10, 20]})
        g = Geometry.from_object(obj)
        assert isinstance(g, Point)
        assert g.wkt == "POINT (10 20)"

    def test_subclass_from_object(self):
        obj = self._FakeGeoObj({"type": "Point", "coordinates": [10, 20]})
        g = Point.from_object(obj)
        assert isinstance(g, Point)

    def test_crs_is_passed_through(self):
        obj = self._FakeGeoObj({"type": "Point", "coordinates": [10, 20]})
        g = Geometry.from_object(obj, crs="epsg:4326")
        assert g.crs == "epsg:4326"

    def test_missing_geo_interface_raises(self):
        with pytest.raises(TypeError, match="__geo_interface__"):
            Geometry.from_object(object())

    def test_non_dict_geo_interface_raises(self):
        class BadObj:
            __geo_interface__ = "not a dict"
        with pytest.raises(TypeError, match="dict"):
            Geometry.from_object(BadObj())

    def test_wrong_type_for_subclass_raises(self):
        obj = self._FakeGeoObj({"type": "Point", "coordinates": [10, 20]})
        with pytest.raises(TypeError):
            LineString.from_object(obj)


# ---------------------------------------------------------------------------
# from_coordinates
# ---------------------------------------------------------------------------

class TestFromCoordinates:
    def test_point_via_subclass(self):
        p = Point.from_coordinates([1, 2])
        assert isinstance(p, Point)
        assert p.wkt == "POINT (1 2)"

    def test_point_via_abc(self):
        p = Geometry.from_coordinates([1, 2])
        assert isinstance(p, Point)
        assert p.wkt == "POINT (1 2)"

    def test_point_3d_via_abc(self):
        p = Geometry.from_coordinates([1, 2, 3])
        assert isinstance(p, Point)
        assert p.has_z is True
        assert p.wkt == "POINT (1 2 3)"

    def test_linestring_via_subclass(self):
        ls = LineString.from_coordinates([[0, 0], [1, 1], [2, 0]])
        assert isinstance(ls, LineString)
        assert ls.wkt == "LINESTRING (0 0, 1 1, 2 0)"

    def test_linestring_via_abc(self):
        ls = Geometry.from_coordinates([[0, 0], [1, 1], [2, 0]])
        assert isinstance(ls, LineString)
        assert ls.wkt == "LINESTRING (0 0, 1 1, 2 0)"

    def test_polygon_via_subclass(self):
        poly = Polygon.from_coordinates([[[0, 0], [1, 0], [1, 1], [0, 0]]])
        assert isinstance(poly, Polygon)
        assert poly.wkt == "POLYGON ((0 0, 1 0, 1 1, 0 0))"

    def test_polygon_via_abc(self):
        poly = Geometry.from_coordinates([[[0, 0], [1, 0], [1, 1], [0, 0]]])
        assert isinstance(poly, Polygon)
        assert poly.wkt == "POLYGON ((0 0, 1 0, 1 1, 0 0))"

    def test_crs_is_passed_through(self):
        p = Geometry.from_coordinates([1, 2], crs="epsg:27700")
        assert p.crs == "epsg:27700"

    def test_validation_still_runs(self):
        with pytest.raises(ValueError):
            LineString.from_coordinates([[0, 0]])  # too few vertices

    def test_called_on_multigeometry_raises(self):
        # MultiGeometry itself is also a multi-part type via issubclass check.
        with pytest.raises(TypeError):
            MultiGeometry.from_coordinates([1, 2])

    def test_called_on_multi_type_raises(self):
        with pytest.raises(TypeError, match="multi-part"):
            MultiPoint.from_coordinates([[0, 0], [1, 1]])

    def test_multi_type_error_suggests_singlepart(self):
        with pytest.raises(TypeError, match="Point.from_coordinates"):
            MultiPoint.from_coordinates([[0, 0]])
    
    def test_non_tuple_list_invalid_coordinates(self):
        with pytest.raises(ValueError):
            Geometry.from_coordinates("invalid input")

# ---------------------------------------------------------------------------
# from_bounds
# ---------------------------------------------------------------------------

class TestFromBounds:
    def test_2d_bounds(self):
        poly = Polygon.from_bounds((0, 0, 10, 5))
        assert isinstance(poly, Polygon)
        assert poly.wkt == "POLYGON ((0 0, 10 0, 10 5, 0 5, 0 0))"

    def test_2d_bounds_is_closed(self):
        poly = Polygon.from_bounds((0, 0, 10, 5))
        coords = poly.geojson["coordinates"][0]
        assert coords[0] == coords[-1]

    def test_2d_bounds_roundtrip(self):
        # The bounds of a from_bounds polygon should equal the input bounds.
        poly = Polygon.from_bounds((2, 3, 8, 7))
        assert poly.bounds == (2, 3, 8, 7)

    def test_3d_bounds(self):
        poly = Polygon.from_bounds((0, 0, 100, 10, 5, 200))
        assert poly.has_z is True
        assert poly.wkt == "POLYGON ((0 0 100, 10 0 100, 10 5 100, 0 5 100, 0 0 100))"

    def test_3d_bounds_uses_z_min(self):
        # z_min should be used as the z value for all vertices.
        poly = Polygon.from_bounds((0, 0, 50, 1, 1, 100))
        coords = poly.geojson["coordinates"][0]
        assert all(v[2] == 50 for v in coords)

    def test_crs_is_passed_through(self):
        poly = Polygon.from_bounds((0, 0, 1, 1), crs="epsg:27700")
        assert poly.crs == "epsg:27700"

    def test_wrong_length_raises(self):
        with pytest.raises(ValueError, match="4-tuple"):
            Polygon.from_bounds((0, 0, 10))

    def test_5_values_raises(self):
        with pytest.raises(ValueError, match="4-tuple"):
            Polygon.from_bounds((0, 0, 0, 10, 5))


# ---------------------------------------------------------------------------
# to_singlepart
# ---------------------------------------------------------------------------

class TestToSinglepart:
    def test_multipoint_to_point(self):
        mp = MultiPoint.from_geojson({"type": "MultiPoint", "coordinates": [[1, 2]]}, crs="epsg:27700")
        p = mp.to_singlepart()
        assert isinstance(p, Point)
        assert p.wkt == "POINT (1 2)"
        assert p.crs == "epsg:27700"

    def test_multilinestring_to_linestring(self):
        mls = MultiLineString.from_geojson({"type": "MultiLineString", "coordinates": [[[0, 0], [1, 1]]]}, crs="epsg:27700")
        ls = mls.to_singlepart()
        assert isinstance(ls, LineString)
        assert ls.wkt == "LINESTRING (0 0, 1 1)"
        assert ls.crs == "epsg:27700"

    def test_multipolygon_to_polygon(self):
        mpoly = MultiPolygon.from_geojson({"type": "MultiPolygon", "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]]}, crs="epsg:27700")
        poly = mpoly.to_singlepart()
        assert isinstance(poly, Polygon)
        assert poly.wkt == "POLYGON ((0 0, 1 0, 1 1, 0 0))"
        assert poly.crs == "epsg:27700"

    def test_crs_is_preserved(self):
        mp = MultiPoint.from_geojson({"type": "MultiPoint", "coordinates": [[1, 2]]}, crs="epsg:4326")
        assert mp.to_singlepart().crs == "epsg:4326"

    def test_crs_none_is_preserved(self):
        mp = MultiPoint.from_geojson({"type": "MultiPoint", "coordinates": [[1, 2]]})
        assert mp.to_singlepart().crs is None

    def test_3d_coordinates_preserved(self):
        mp = MultiPoint.from_geojson({"type": "MultiPoint", "coordinates": [[1, 2, 3]]})
        p = mp.to_singlepart()
        assert p.wkt == "POINT (1 2 3)"
        assert p.has_z is True

    def test_multiple_geometries_raises(self):
        mp = MultiPoint.from_geojson({"type": "MultiPoint", "coordinates": [[0, 0], [1, 1]]})
        with pytest.raises(ValueError, match="exactly 1"):
            mp.to_singlepart()

    def test_multi_types_are_multigeometry_instances(self):
        mp = MultiPoint.from_geojson({"type": "MultiPoint", "coordinates": [[0, 0]]})
        assert isinstance(mp, MultiGeometry)

    def test_single_types_are_not_multigeometry_instances(self):
        p = Point.from_geojson({"type": "Point", "coordinates": [0, 0]})
        assert not isinstance(p, MultiGeometry)


# ---------------------------------------------------------------------------
# transform
# ---------------------------------------------------------------------------

class TestTransform:
    def setup_method(self):
        import glod.config
        glod.config.USE_PYPROJ = False

    def _make_fake_transformer(self, x_out, y_out, z_out=None):
        """Return a mock Transformer whose transform() returns fixed values."""
        t = mock.MagicMock()
        if z_out is not None:
            t.transform.return_value = (x_out, y_out, z_out)
        else:
            t.transform.return_value = (x_out, y_out)
        return t

    def test_raises_when_pyproj_disabled(self):
        import glod.config
        glod.config.USE_PYPROJ = False
        p = Point.from_geojson({"type": "Point", "coordinates": [0, 51.5]}, crs="epsg:4326")
        with pytest.raises(RuntimeError, match="config.set_use_pyproj"):
            p.transform("epsg:27700")

    def test_raises_when_crs_is_none(self):
        import glod.config
        glod.config.USE_PYPROJ = True
        p = Point.from_geojson({"type": "Point", "coordinates": [0, 51.5]})
        with pytest.raises(ValueError, match="no CRS"):
            p.transform("epsg:27700")

    def _patch_transformer(self, fake_t):
        """Context manager that patches pyproj.Transformer and injects it into
        the geometry module's local import, by pre-populating sys.modules."""
        import sys
        fake_pyproj = mock.MagicMock()
        fake_pyproj.Transformer = mock.MagicMock()
        fake_pyproj.Transformer.from_crs.return_value = fake_t
        return mock.patch.dict("sys.modules", {"pyproj": fake_pyproj})

    def test_point_transform_2d(self):
        import glod.config
        glod.config.USE_PYPROJ = True
        p = Point.from_geojson({"type": "Point", "coordinates": [0.0, 51.5]}, crs="epsg:4326")
        fake_t = self._make_fake_transformer(530000.0, 180000.0)
        with self._patch_transformer(fake_t):
            result = p.transform("epsg:27700")
        assert isinstance(result, Point)
        assert result.crs == "epsg:27700"
        assert result.wkt == "POINT (530000 180000)"

    def test_point_transform_3d(self):
        import glod.config
        glod.config.USE_PYPROJ = True
        p = Point.from_geojson({"type": "Point", "coordinates": [0.0, 51.5, 10.0]}, crs="epsg:4326")
        fake_t = self._make_fake_transformer(530000.0, 180000.0, 10.0)
        with self._patch_transformer(fake_t):
            result = p.transform("epsg:27700")
        assert isinstance(result, Point)
        assert result.has_z is True
        assert result.wkt == "POINT (530000 180000 10)"

    def test_linestring_transform(self):
        import glod.config
        glod.config.USE_PYPROJ = True
        ls = LineString.from_geojson(
            {"type": "LineString", "coordinates": [[0.0, 51.5], [0.1, 51.6]]},
            crs="epsg:4326",
        )
        fake_t = mock.MagicMock()
        fake_t.transform.side_effect = [(530000.0, 180000.0), (537000.0, 191000.0)]
        with self._patch_transformer(fake_t):
            result = ls.transform("epsg:27700")
        assert isinstance(result, LineString)
        assert result.crs == "epsg:27700"
        assert result.wkt == "LINESTRING (530000 180000, 537000 191000)"

    def test_polygon_transform(self):
        import glod.config
        glod.config.USE_PYPROJ = True
        poly = Polygon.from_geojson(
            {"type": "Polygon", "coordinates": [[[0.0, 51.0], [0.1, 51.0], [0.1, 51.1], [0.0, 51.0]]]},
            crs="epsg:4326",
        )
        fake_t = mock.MagicMock()
        fake_t.transform.side_effect = [
            (520000.0, 170000.0), (527000.0, 170000.0),
            (527000.0, 181000.0), (520000.0, 170000.0),
        ]
        with self._patch_transformer(fake_t):
            result = poly.transform("epsg:27700")
        assert isinstance(result, Polygon)
        assert result.crs == "epsg:27700"

    def test_returns_same_class(self):
        import glod.config
        glod.config.USE_PYPROJ = True
        mp = MultiPoint.from_geojson(
            {"type": "MultiPoint", "coordinates": [[0.0, 51.5], [0.1, 51.6]]},
            crs="epsg:4326",
        )
        fake_t = mock.MagicMock()
        fake_t.transform.side_effect = [(530000.0, 180000.0), (537000.0, 191000.0)]
        with self._patch_transformer(fake_t):
            result = mp.transform("epsg:27700")
        assert isinstance(result, MultiPoint)


# ---------------------------------------------------------------------------
# WKT round-trips across all types (parametrized integration test)
# ---------------------------------------------------------------------------

ALL_ROUNDTRIP_CASES = [
    (Point,           {"type": "Point",          "coordinates": [1, 2]}),
    (Point,           {"type": "Point",          "coordinates": [1, 2, 3]}),
    (LineString,      {"type": "LineString",      "coordinates": [[0, 0], [1, 1], [2, 0]]}),
    (LineString,      {"type": "LineString",      "coordinates": [[0, 0, 1], [1, 1, 2]]}),
    (Polygon,         {"type": "Polygon",         "coordinates": [[[0, 0], [1, 0], [1, 1], [0, 0]]]}),
    (MultiPoint,      {"type": "MultiPoint",      "coordinates": [[0, 0], [1, 1]]}),
    (MultiLineString, {"type": "MultiLineString", "coordinates": [[[0, 0], [1, 1]], [[2, 2], [3, 3]]]}),
    (MultiPolygon,    {"type": "MultiPolygon",    "coordinates": [[[[0, 0], [1, 0], [1, 1], [0, 0]]]]}),
]

@pytest.mark.parametrize("cls, geojson", ALL_ROUNDTRIP_CASES)
def test_full_roundtrip(cls, geojson):
    """GeoJSON → object → WKT → object → WKT should be stable."""
    g1 = cls.from_geojson(geojson)
    g2 = Geometry.from_wkt(g1.wkt)
    assert g1.wkt == g2.wkt
    assert type(g2) is cls

@pytest.mark.parametrize("cls, geojson", ALL_ROUNDTRIP_CASES)
def test_geojson_roundtrip(cls, geojson):
    """GeoJSON → object → GeoJSON should return the original dict."""
    g = cls.from_geojson(geojson)
    assert g.geojson == geojson


# ===========================================================================
# intersects
# ===========================================================================

# ---------------------------------------------------------------------------
# Shared helpers (module-level so they can be referenced inside any class)
# ---------------------------------------------------------------------------

_ICRS = "epsg:27700"


def _pt(x, y, crs=_ICRS):
    return Point.from_wkt(f"POINT ({x} {y})", crs=crs)


def _ls(*coords, crs=_ICRS):
    wkt_coords = ", ".join(f"{x} {y}" for x, y in coords)
    return LineString.from_wkt(f"LINESTRING ({wkt_coords})", crs=crs)


def _sq(x0, y0, x1, y1, crs=_ICRS):
    """Return an axis-aligned rectangular Polygon."""
    return Polygon.from_wkt(
        f"POLYGON (({x0} {y0}, {x1} {y0}, {x1} {y1}, {x0} {y1}, {x0} {y0}))",
        crs=crs,
    )


# ---------------------------------------------------------------------------
# CRS validation
# ---------------------------------------------------------------------------

class TestIntersectsCRS:
    def setup_method(self):
        import glod.config
        glod.config.USE_PYPROJ = False

    def test_same_crs_no_error(self):
        assert _pt(1, 1).intersects(_pt(1, 1))

    def test_both_none_crs_allowed(self):
        assert _pt(1, 1, crs=None).intersects(_pt(1, 1, crs=None))

    def test_different_crs_raises(self):
        with pytest.raises(ValueError, match="CRS mismatch"):
            _pt(1, 1, crs="epsg:27700").intersects(_pt(1, 1, crs="epsg:4326"))

    def test_self_none_other_set_raises(self):
        with pytest.raises(ValueError, match="crs=None"):
            _pt(1, 1, crs=None).intersects(_pt(1, 1, crs="epsg:27700"))

    def test_self_set_other_none_raises(self):
        with pytest.raises(ValueError, match="crs=None"):
            _pt(1, 1, crs="epsg:27700").intersects(_pt(1, 1, crs=None))

    def test_non_geometry_arg_raises(self):
        with pytest.raises(TypeError, match="Geometry instance"):
            _pt(1, 1).intersects("not a geometry")

    def test_mismatch_raises_when_pyproj_disabled(self):
        with pytest.raises(ValueError, match="set_use_pyproj"):
            _pt(1, 1, crs="epsg:27700").intersects(_pt(1, 1, crs="epsg:4326"))

    def test_mismatch_auto_reprojects_when_pyproj_enabled(self):
        # When USE_PYPROJ is True, a CRS mismatch triggers a silent temporary
        # reprojection rather than an error. Use a real pyproj mock so the
        # transform call succeeds with a known result.
        import glod.config
        import unittest.mock as mock
        glod.config.USE_PYPROJ = True
        fake_pyproj = mock.MagicMock()
        # Transform epsg:4326 -> epsg:27700: return the same coordinates so
        # the intersection result is deterministic in the test.
        fake_pyproj.Transformer.from_crs.return_value.transform.return_value = (1.0, 1.0)
        with mock.patch.dict("sys.modules", {"pyproj": fake_pyproj}):
            # Same logical position in both CRS after mocked reprojection ->
            # the two points should intersect.
            result = _pt(1, 1, crs="epsg:27700").intersects(
                _pt(1, 1, crs="epsg:4326")
            )
        assert result is True

    def test_mismatch_auto_reproject_does_not_mutate_other(self):
        # The original geometry passed to intersects() must be unchanged.
        import glod.config
        import unittest.mock as mock
        glod.config.USE_PYPROJ = True
        fake_pyproj = mock.MagicMock()
        fake_pyproj.Transformer.from_crs.return_value.transform.return_value = (99.0, 99.0)
        other = _pt(1, 1, crs="epsg:4326")
        original_wkt = other.wkt
        original_crs = other.crs
        with mock.patch.dict("sys.modules", {"pyproj": fake_pyproj}):
            _pt(1, 1, crs="epsg:27700").intersects(other)
        assert other.wkt == original_wkt
        assert other.crs == original_crs


# ---------------------------------------------------------------------------
# Point / Point
# ---------------------------------------------------------------------------

class TestIntersectsPointPoint:
    def test_identical_points_intersect(self):
        assert _pt(3, 4).intersects(_pt(3, 4))

    def test_distinct_points_no_intersect(self):
        assert not _pt(0, 0).intersects(_pt(1, 1))

    def test_symmetric(self):
        a, b = _pt(1, 1), _pt(2, 2)
        assert a.intersects(b) == b.intersects(a)

    def test_3d_same_xy_intersects(self):
        # Z is ignored; only XY matters for planimetric intersection.
        a = Point.from_wkt("POINT (1 2 10)", crs=_ICRS)
        b = Point.from_wkt("POINT (1 2 99)", crs=_ICRS)
        assert a.intersects(b)

    def test_3d_different_xy_no_intersect(self):
        a = Point.from_wkt("POINT (1 2 5)", crs=_ICRS)
        b = Point.from_wkt("POINT (3 4 5)", crs=_ICRS)
        assert not a.intersects(b)


# ---------------------------------------------------------------------------
# Point / LineString
# ---------------------------------------------------------------------------

class TestIntersectsPointLineString:
    def test_point_on_midpoint_of_segment(self):
        assert _pt(1, 1).intersects(_ls((0, 0), (2, 2)))

    def test_point_on_segment_start(self):
        assert _pt(0, 0).intersects(_ls((0, 0), (2, 2)))

    def test_point_on_segment_end(self):
        assert _pt(2, 2).intersects(_ls((0, 0), (2, 2)))

    def test_point_off_line(self):
        assert not _pt(1, 2).intersects(_ls((0, 0), (2, 2)))

    def test_point_collinear_but_beyond_segment(self):
        # (3, 3) lies on the infinite line through (0,0)-(2,2) but past the endpoint.
        assert not _pt(3, 3).intersects(_ls((0, 0), (2, 2)))

    def test_point_on_second_segment_of_polyline(self):
        assert _pt(2, 0).intersects(_ls((0, 0), (2, 0), (2, 3)))

    def test_symmetric(self):
        p    = _pt(1, 1)
        line = _ls((0, 0), (2, 2))
        assert p.intersects(line) == line.intersects(p)

    def test_far_point_bounds_rejection(self):
        assert not _pt(100, 100).intersects(_ls((0, 0), (1, 1)))


# ---------------------------------------------------------------------------
# Point / Polygon
# ---------------------------------------------------------------------------

class TestIntersectsPointPolygon:
    def test_point_strictly_inside(self):
        assert _pt(2, 2).intersects(_sq(0, 0, 4, 4))

    def test_point_on_corner(self):
        assert _pt(0, 0).intersects(_sq(0, 0, 4, 4))

    def test_point_on_edge_midpoint(self):
        assert _pt(2, 0).intersects(_sq(0, 0, 4, 4))

    def test_point_outside(self):
        assert not _pt(5, 5).intersects(_sq(0, 0, 4, 4))

    def test_point_just_outside_edge(self):
        assert not _pt(0, -0.001).intersects(_sq(0, 0, 4, 4))

    def test_symmetric(self):
        p    = _pt(2, 2)
        poly = _sq(0, 0, 4, 4)
        assert p.intersects(poly) == poly.intersects(p)

    def test_point_inside_hole_no_intersect(self):
        outer = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
        hole  = [[2, 2], [8, 2], [8, 8], [2, 8], [2, 2]]
        poly  = Polygon.from_geojson(
            {"type": "Polygon", "coordinates": [outer, hole]}, crs=_ICRS
        )
        assert not _pt(5, 5).intersects(poly)

    def test_point_between_hole_and_outer_ring(self):
        outer = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
        hole  = [[2, 2], [8, 2], [8, 8], [2, 8], [2, 2]]
        poly  = Polygon.from_geojson(
            {"type": "Polygon", "coordinates": [outer, hole]}, crs=_ICRS
        )
        assert _pt(1, 1).intersects(poly)


# ---------------------------------------------------------------------------
# LineString / LineString
# ---------------------------------------------------------------------------

class TestIntersectsLineStringLineString:
    def test_crossing_lines(self):
        # Cross at (1, 1).
        assert _ls((0, 0), (2, 2)).intersects(_ls((0, 2), (2, 0)))

    def test_t_junction(self):
        assert _ls((1, 0), (1, 2)).intersects(_ls((0, 1), (2, 1)))

    def test_touching_at_shared_endpoint(self):
        assert _ls((0, 0), (1, 0)).intersects(_ls((1, 0), (2, 0)))

    def test_parallel_lines_no_intersect(self):
        assert not _ls((0, 0), (4, 0)).intersects(_ls((0, 1), (4, 1)))

    def test_collinear_overlapping(self):
        assert _ls((0, 0), (2, 0)).intersects(_ls((1, 0), (3, 0)))

    def test_collinear_non_overlapping(self):
        assert not _ls((0, 0), (1, 0)).intersects(_ls((2, 0), (3, 0)))

    def test_disjoint_far_apart(self):
        assert not _ls((0, 0), (1, 1)).intersects(_ls((100, 100), (101, 101)))

    def test_symmetric(self):
        a = _ls((0, 0), (2, 2))
        b = _ls((0, 2), (2, 0))
        assert a.intersects(b) == b.intersects(a)

    def test_single_shared_vertex_non_collinear(self):
        assert _ls((0, 0), (1, 1)).intersects(_ls((1, 1), (2, 0)))

    def test_multi_segment_cross(self):
        assert _ls((0, 0), (2, 0), (2, 2)).intersects(_ls((1, -1), (1, 3)))


# ---------------------------------------------------------------------------
# LineString / Polygon
# ---------------------------------------------------------------------------

class TestIntersectsLineStringPolygon:
    def test_line_crosses_polygon(self):
        assert _ls((-1, 2), (5, 2)).intersects(_sq(0, 0, 4, 4))

    def test_line_fully_inside_polygon(self):
        assert _ls((1, 1), (3, 3)).intersects(_sq(0, 0, 4, 4))

    def test_line_fully_outside_polygon(self):
        assert not _ls((5, 5), (8, 8)).intersects(_sq(0, 0, 4, 4))

    def test_line_touches_corner(self):
        assert _ls((-1, -1), (1, 1)).intersects(_sq(0, 0, 4, 4))

    def test_line_along_edge(self):
        assert _ls((0, 0), (4, 0)).intersects(_sq(0, 0, 4, 4))

    def test_line_exits_through_one_edge(self):
        # Starts inside the polygon, exits through the right edge.
        assert _ls((2, 2), (6, 2)).intersects(_sq(0, 0, 4, 4))

    def test_symmetric(self):
        line = _ls((-1, 2), (5, 2))
        poly = _sq(0, 0, 4, 4)
        assert line.intersects(poly) == poly.intersects(line)

    def test_far_line_bounds_rejection(self):
        assert not _ls((10, 10), (20, 20)).intersects(_sq(0, 0, 4, 4))


# ---------------------------------------------------------------------------
# Polygon / Polygon
# ---------------------------------------------------------------------------

class TestIntersectsPolygonPolygon:
    def test_overlapping_polygons(self):
        assert _sq(0, 0, 2, 2).intersects(_sq(1, 1, 3, 3))

    def test_disjoint_polygons(self):
        assert not _sq(0, 0, 2, 2).intersects(_sq(5, 5, 7, 7))

    def test_a_fully_contains_b(self):
        assert _sq(0, 0, 4, 4).intersects(_sq(1, 1, 3, 3))

    def test_b_fully_contains_a(self):
        assert _sq(1, 1, 3, 3).intersects(_sq(0, 0, 4, 4))

    def test_touching_along_shared_edge(self):
        assert _sq(0, 0, 2, 2).intersects(_sq(2, 0, 4, 2))

    def test_touching_at_single_corner(self):
        assert _sq(0, 0, 1, 1).intersects(_sq(1, 1, 2, 2))

    def test_symmetric(self):
        a = _sq(0, 0, 2, 2)
        b = _sq(1, 1, 3, 3)
        assert a.intersects(b) == b.intersects(a)

    def test_far_apart_bounds_rejection(self):
        assert not _sq(0, 0, 1, 1).intersects(_sq(100, 100, 101, 101))


# ---------------------------------------------------------------------------
# Multi-part types
# ---------------------------------------------------------------------------

class TestIntersectsMultiPart:
    def test_multipoint_one_part_hits_linestring(self):
        mp = MultiPoint.from_wkt("MULTIPOINT ((100 100), (1 1))", crs=_ICRS)
        assert mp.intersects(_ls((0, 0), (2, 2)))

    def test_multipoint_no_part_hits_linestring(self):
        mp = MultiPoint.from_wkt("MULTIPOINT ((10 10), (20 20))", crs=_ICRS)
        assert not mp.intersects(_ls((0, 0), (2, 2)))

    def test_multilinestring_one_part_hits_polygon(self):
        mls = MultiLineString.from_wkt(
            "MULTILINESTRING ((100 100, 101 101), (1 1, 3 3))", crs=_ICRS
        )
        assert mls.intersects(_sq(0, 0, 4, 4))

    def test_multilinestring_no_part_hits_polygon(self):
        mls = MultiLineString.from_wkt(
            "MULTILINESTRING ((10 10, 11 11), (20 20, 21 21))", crs=_ICRS
        )
        assert not mls.intersects(_sq(0, 0, 4, 4))

    def test_multipolygon_one_part_overlaps_polygon(self):
        mpoly = MultiPolygon.from_wkt(
            "MULTIPOLYGON (((10 10, 11 10, 11 11, 10 10)), ((0 0, 2 0, 2 2, 0 0)))",
            crs=_ICRS,
        )
        assert mpoly.intersects(_sq(1, 1, 3, 3))

    def test_multipolygon_no_part_overlaps_polygon(self):
        mpoly = MultiPolygon.from_wkt(
            "MULTIPOLYGON (((10 10, 11 10, 11 11, 10 10)), ((20 20, 21 20, 21 21, 20 20)))",
            crs=_ICRS,
        )
        assert not mpoly.intersects(_sq(0, 0, 4, 4))

    def test_multi_vs_multi(self):
        mp  = MultiPoint.from_wkt("MULTIPOINT ((1 1), (50 50))", crs=_ICRS)
        mls = MultiLineString.from_wkt(
            "MULTILINESTRING ((0 0, 2 2), (100 100, 101 101))", crs=_ICRS
        )
        assert mp.intersects(mls)

    def test_symmetric_multi(self):
        mp   = MultiPoint.from_wkt("MULTIPOINT ((1 1), (100 100))", crs=_ICRS)
        line = _ls((0, 0), (2, 2))
        assert mp.intersects(line) == line.intersects(mp)


# ---------------------------------------------------------------------------
# 3D geometries (Z coordinate ignored for planimetric intersection)
# ---------------------------------------------------------------------------

class TestIntersects3D:
    def test_3d_linestrings_cross(self):
        a = LineString.from_wkt("LINESTRING (0 0 10, 2 2 20)", crs=_ICRS)
        b = LineString.from_wkt("LINESTRING (0 2 30, 2 0 40)", crs=_ICRS)
        assert a.intersects(b)

    def test_3d_point_on_3d_line(self):
        p    = Point.from_wkt("POINT (1 1 999)", crs=_ICRS)
        line = LineString.from_wkt("LINESTRING (0 0 0, 2 2 100)", crs=_ICRS)
        assert p.intersects(line)

    def test_3d_point_inside_2d_polygon(self):
        p    = Point.from_wkt("POINT (2 2 50)", crs=_ICRS)
        poly = _sq(0, 0, 4, 4)
        assert p.intersects(poly)