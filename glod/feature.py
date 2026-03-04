"""Feature type for the glod package.

This module provides a container class that pairs geometry with attribute data,
mirroring the GeoJSON ``Feature`` structures:

* :class:`Feature` — a single :class:`~glod.geometry.Geometry` paired with a flat
    ``dict`` of attribute values.

The class supports reading from and writing to GeoJSON (dict, raw JSON string, or file
path).
"""

from __future__ import annotations

from .geometry import CrsType, Geometry


class Feature:
    """A geometry paired with a dict of attributes.

    Models a single GeoJSON ``Feature`` object. Both :attr:`geometry` and
    :attr:`attributes` are mutable via validated property setters: assigning an
    incompatible type raises :exc:`TypeError` immediately, keeping the instance in a
    consistent state at all times.

    The ``__geo_interface__`` property makes :class:`Feature` compatible with any
    library that implements the __geo_interface__ protocol (shapely, geopandas, etc.).

    Note:
        :class:`Feature` uses ``__slots__`` to reduce per-instance memory overhead and
        prevent accidental creation of undeclared attributes.

    Example::

        from glod.geometry import Point
        p = Point.from_wkt("POINT (530000 180000)", crs="epsg:27700")
        f = Feature(p, {"name": "Edinburgh", "pop": 530000})
        print(f)  # Feature(type='Point', attributes=['name', 'pop'])
    """

    __slots__ = ("_geometry", "_attributes")

    def __init__(self, geometry: Geometry, attributes: dict | None = None):
        """Initialise a Feature with a geometry and optional attributes.

        Args:
            geometry: The spatial component of the feature. Must be a
                :class:`~glod.geometry.Geometry` instance.
            attributes: A flat ``dict`` of attribute name/value pairs.
                Defaults to an empty dict when ``None``. The dict is copied on
                assignment so later changes to the original do not affect the feature.

        Raises:
            TypeError: If *geometry* is not a :class:`~glod.geometry.Geometry` instance,
                or if *attributes* is provided but is not a ``dict``.

        Example::

            from glod.geometry import LineString
            ls = LineString.from_wkt("LINESTRING (0 0, 1 1)", crs="epsg:27700")
            f = Feature(ls, {"road_class": "A"})
        """
        self.geometry = geometry  # via setter
        self.attributes = attributes if attributes is not None else {}  # via setter

    def __repr__(self) -> str:
        """Return a concise developer-readable string representation.

        Returns:
            A string of the form
            ``"Feature(type='Point', attributes=['name', 'pop'])"``.
        """
        return (
            f"Feature(type={self.geometry.type.value!r}, "
            f"attributes={list(self.attributes.keys())})"
        )

    def __eq__(self, other: object) -> bool:
        """Return ``True`` if *other* has identical geometry and attributes.

        Geometry equality is determined by comparing the GeoJSON ``dict``
        representations (type, coordinates, and CRS stored on the geometry object).
        Attribute equality uses standard ``dict`` comparison.

        Args:
            other: The object to compare against.

        Returns:
            ``True`` if *other* is a :class:`Feature` with the same geometry and
            attributes; ``NotImplemented`` if *other* is not a :class:`Feature`.
        """
        if not isinstance(other, Feature):
            return NotImplemented
        return (
            self.geometry.geojson == other.geometry.geojson
            and self.attributes == other.attributes
        )

    # ---- geometry property ----

    @property
    def geometry(self) -> Geometry:
        """The spatial component of this feature.

        Returns:
            The :class:`~glod.geometry.Geometry` instance associated with
            this feature.
        """
        return self._geometry

    @geometry.setter
    def geometry(self, value: Geometry) -> None:
        """Set the geometry, validating that it is a :class:`~glod.geometry.Geometry`.

        Args:
            value: The replacement geometry.

        Raises:
            TypeError: If *value* is not a
                :class:`~glod.geometry.Geometry` instance.
        """
        if not isinstance(value, Geometry):
            raise TypeError(
                f"geometry must be a Geometry instance, got {type(value).__name__!r}."
            )
        self._geometry = value

    # ---- attributes property ----

    @property
    def attributes(self) -> dict:
        """The attribute dictionary for this feature.

        Returns:
            A ``dict`` mapping attribute names to their values. This is the live
            internal dict; mutating it in-place affects the feature.
        """
        return self._attributes

    @attributes.setter
    def attributes(self, value: dict) -> None:
        """Set the attributes dict, validating the type and copying the value.

        The provided dict is shallow-copied on assignment so subsequent changes to the
        original object do not affect the feature.

        Args:
            value: A ``dict`` of attribute name/value pairs.

        Raises:
            TypeError: If *value* is not a ``dict``.
        """
        if not isinstance(value, dict):
            raise TypeError(f"attributes must be a dict, got {type(value).__name__!r}.")
        self._attributes = dict(value)

    # ---- geo interface ----

    @property
    def __geo_interface__(self) -> dict:
        """GeoJSON Feature dict, conforming to the ``__geo_interface__`` protocol.

        Returns a dict with ``"type": "Feature"``, a ``"geometry"`` key containing the
        geometry's own ``__geo_interface__`` dict, and a ``"properties"`` key containing
        :attr:`attributes`.

        Returns:
            A GeoJSON-compatible ``Feature`` dict.
        """
        return {
            "type": "Feature",
            "geometry": self.geometry.__geo_interface__,
            "properties": self.attributes,
        }

    # ---- constructors ----

    @classmethod
    def from_geojson(cls, geojson: dict, crs: CrsType = None) -> Feature:
        """Construct a :class:`Feature` from a GeoJSON Feature dict.

        CRS is not part of the GeoJSON specification and must be passed
        explicitly if known. When called from
        :meth:`FeatureCollection.from_geojson`, the collection-level CRS is
        forwarded here automatically.

        Args:
            geojson: A dict with ``"type": "Feature"``, a ``"geometry"`` key
                containing a valid GeoJSON geometry dict, and an optional
                ``"properties"`` key.
            crs: CRS to assign to the parsed geometry.
                Defaults to ``None``.

        Returns:
            A new :class:`Feature` instance.

        Raises:
            ValueError: If the ``"type"`` field is not ``"Feature"``, or if
                the ``"geometry"`` key is absent or ``None``.

        Example::

            f = Feature.from_geojson({
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": [1.0, 2.0]},
                "properties": {"name": "test"},
            }, crs="epsg:27700")
        """
        if geojson.get("type") != "Feature":
            raise ValueError(
                f"Expected a GeoJSON Feature, got type {geojson.get('type')!r}."
            )
        if "geometry" not in geojson or geojson["geometry"] is None:
            raise ValueError("Feature has no geometry.")
        geometry = Geometry.from_geojson(geojson["geometry"], crs=crs)
        attributes = dict(geojson.get("properties") or {})
        return cls(geometry, attributes)

    @classmethod
    def from_wkt(
        cls, wkt: str, attributes: dict | None = None, crs: CrsType = None
    ) -> Feature:
        """Construct a :class:`Feature` from a WKT geometry string.

        Args:
            wkt: A Well-Known Text geometry string, e.g. ``"POINT (530000 180000)"``.
                attributes: Optional attribute dict.
                Defaults to an empty dict when ``None``.
            crs: CRS to assign to the parsed geometry.
                Defaults to ``None``.

        Returns:
            A new :class:`Feature` instance.

        Raises:
            ValueError: If *wkt* is not a valid WKT string or its geometry type is
                unrecognised.

        Example::

            f = Feature.from_wkt(
                "LINESTRING (0 0, 1 1)",
                attributes={"name": "route_1"},
                crs="epsg:27700",
            )
        """
        geometry = Geometry.from_wkt(wkt, crs=crs)
        return cls(geometry, attributes)

    # ---- serialisation ----

    def to_geojson(self) -> dict:
        """Return a GeoJSON Feature dict.

        CRS is *not* included in the output because it is not part of the GeoJSON
        Feature specification; CRS is managed at the :class:`FeatureCollection` level.

        Returns:
            A plain ``dict`` with keys ``"type"``, ``"geometry"``, and ``"properties"``,
            suitable for JSON serialisation.

        Example::

            f = Feature.from_wkt("POINT (1 2)", attributes={"id": 1})
            d = f.to_geojson()
            # {"type": "Feature",
            #  "geometry": {"type": "Point", "coordinates": [1, 2]},
            #  "properties": {"id": 1}}
        """
        return {
            "type": "Feature",
            "geometry": self.geometry.geojson,
            "properties": self.attributes,
        }
