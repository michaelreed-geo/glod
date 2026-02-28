"""Feature and FeatureCollection types for the glod package.

This module provides two container classes that pair geometry with attribute data,
mirroring the GeoJSON ``Feature`` and ``FeatureCollection`` structures:

* :class:`Feature` — a single :class:`~glod.geometry.Geometry` paired with a flat
    ``dict`` of attribute values.
* :class:`FeatureCollection` — an ordered, mutable sequence of
  :class:`Feature` objects with optional collection-level metadata and CRS-normalising
    I/O.

Both classes support reading from and writing to GeoJSON (dict, raw JSON string, or file
path). :class:`FeatureCollection` additionally supports CSV with a WKT geometry column.

Typical usage::

    from glod.feature import Feature, FeatureCollection
    from glod.geometry import Point

    # Build a collection manually
    p = Point.from_wkt("POINT (530000 180000)", crs="epsg:27700")
    fc = FeatureCollection([Feature(p, {"name": "Edinburgh"})])

    # Round-trip via GeoJSON
    fc2 = FeatureCollection.from_geojson(fc.to_geojson())

    # Round-trip via CSV
    fc.to_csv("places.csv")
    fc3 = FeatureCollection.from_csv("places.csv", crs="epsg:27700")
"""

from __future__ import annotations

import csv
import json
import os
import warnings

import glod.config as _config
from .geometry import CrsType, Geometry


# ---------------------------------------------------------------------------
# Feature
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# FeatureCollection
# ---------------------------------------------------------------------------


class FeatureCollection:
    """An ordered, mutable collection of :class:`Feature` objects.

    Models a GeoJSON ``FeatureCollection``. Behaves as a sequence — supporting
    iteration, index access, and ``len()`` — and provides constructors and serialisers
    for GeoJSON and CSV.

    **CRS handling**: :attr:`crs` is *derived* from the features themselves rather than
    stored independently. It returns the shared CRS when all features agree, or
    ``None`` when the collection is empty or features carry mixed CRS values. This
    guarantees that :attr:`crs` can never contradict the actual coordinate data.

    On export via :meth:`to_geojson`, features with mixed CRS are automatically
    reprojected to a common target (the most frequently occurring one wins).
    Reprojection requires pyproj; if it is disabled a :class:`UserWarning` is emitted
    and features are exported as-is.

    Note:
        :class:`FeatureCollection` uses ``__slots__``.

    Example::

        from glod.geometry import Point
        pts = [Point.from_wkt(f"POINT ({x} 0)", crs="epsg:27700") for x in range(3)]
        fc = FeatureCollection(
            [Feature(p, {"id": i}) for i, p in enumerate(pts)],
            metadata={"source": "manual"},
        )
        print(len(fc))   # 3
        print(fc.crs)    # 'epsg:27700'
    """

    __slots__ = ("_features", "_metadata")

    def __init__(
        self,
        features: list[Feature],
        metadata: dict | None = None,
    ):
        """Initialise a FeatureCollection.

        Args:
            features: A ``list`` of :class:`Feature` instances. Every element is
                validated; the list is shallow-copied on assignment.
            metadata: An optional ``dict`` of collection-level metadata (e.g.
                provenance, description). Shallow-copied on assignment.
                Defaults to an empty dict when ``None``.

        Raises:
            TypeError: If *features* is not a ``list``, if any element is not a
                :class:`Feature` instance, or if *metadata* is not a ``dict``.

        Example::

            fc = FeatureCollection([], metadata={"source": "test"})
        """
        self.features = features  # via setter
        self.metadata = metadata if metadata is not None else {}  # via setter

    def __repr__(self) -> str:
        """Return a concise developer-readable string representation.

        Returns:
            A string of the form
            ``"FeatureCollection(3 features, crs='epsg:27700')"``.
        """
        return f"FeatureCollection({len(self._features)} features, crs={self.crs!r})"

    def __eq__(self, other: object) -> bool:
        """Return ``True`` if *other* contains identical features and metadata.

        Two collections are equal when they have the same :class:`Feature` instances in
        the same order *and* the same metadata dict.

        Args:
            other: The object to compare against.

        Returns:
            ``True`` if *other* is a :class:`FeatureCollection` with matching features
            and metadata; ``NotImplemented`` otherwise.
        """
        if not isinstance(other, FeatureCollection):
            return NotImplemented
        return self._features == other._features and self._metadata == other._metadata

    def __iter__(self):
        """Iterate over the features in insertion order.

        Yields:
            Each :class:`Feature` in the collection.
        """
        return iter(self._features)

    def __getitem__(self, i):
        """Return the feature or features at the given index or slice.

        Args:
            i: An integer index or a :class:`slice`.

        Returns:
            A single :class:`Feature` for an integer index, or a ``list`` of
            :class:`Feature` objects for a slice.

        Raises:
            IndexError: If an integer *i* is out of range.
        """
        return self._features[i]

    def __len__(self) -> int:
        """Return the number of features in the collection.

        Returns:
            Feature count as an ``int``.
        """
        return len(self._features)

    # ---- crs (derived, read-only) ----

    @property
    def crs(self) -> CrsType:
        """The CRS of this collection, derived from its features.

        Returns the single shared CRS value if every feature's geometry reports the same
        CRS; otherwise returns ``None``.

        This property is read-only. To change the CRS of the collection, reproject
        individual feature geometries using :meth:`~glod.geometry.Geometry.transform`.

        Returns:
            The shared CRS (string or :class:`pyproj.CRS`) if all features agree, or
            ``None`` if the collection is empty or features carry mixed CRS values.
        """
        if not self._features:
            return None
        crses = {f.geometry.crs for f in self._features}
        return crses.pop() if len(crses) == 1 else None

    # ---- features property ----

    @property
    def features(self) -> list[Feature]:
        """The list of :class:`Feature` objects in this collection.

        Returns:
            The internal ``list`` of features. Mutating it directly bypasses type
            validation; prefer :meth:`append` and :meth:`remove`.
        """
        return self._features

    @features.setter
    def features(self, value: list[Feature]) -> None:
        """Replace the feature list, validating every element.

        Args:
            value: A ``list`` whose every element is a :class:`Feature` instance.

        Raises:
            TypeError: If *value* is not a ``list``, or if any element is not a
                :class:`Feature` instance (the offending index is included in the error
                message).
        """
        if not isinstance(value, list):
            raise TypeError(f"features must be a list, got {type(value).__name__!r}.")
        for i, item in enumerate(value):
            if not isinstance(item, Feature):
                raise TypeError(
                    f"All items in features must be Feature instances; "
                    f"item at index {i} is {type(item).__name__!r}."
                )
        self._features = list(value)

    # ---- metadata property ----

    @property
    def metadata(self) -> dict:
        """Collection-level metadata.

        Returns:
            A ``dict`` of metadata key/value pairs. This is the live internal dict;
            mutating it in-place will affect the collection.
        """
        return self._metadata

    @metadata.setter
    def metadata(self, value: dict) -> None:
        """Set the metadata dict, validating the type and copying the value.

        Args:
            value: A ``dict`` of metadata key/value pairs.

        Raises:
            TypeError: If *value* is not a ``dict``.
        """
        if not isinstance(value, dict):
            raise TypeError(f"metadata must be a dict, got {type(value).__name__!r}.")
        self._metadata = dict(value)

    # ---- mutation methods ----

    def append(self, feature: Feature) -> None:
        """Append a :class:`Feature` to the end of the collection.

        Args:
            feature: The :class:`Feature` to add.

        Raises:
            TypeError: If *feature* is not a :class:`Feature` instance.

        Example::

            fc = FeatureCollection([])
            fc.append(Feature(some_geometry, {"id": 1}))
        """
        if not isinstance(feature, Feature):
            raise TypeError(
                f"Can only append Feature instances, got {type(feature).__name__!r}."
            )
        self._features.append(feature)

    def remove(self, feature: Feature) -> None:
        """Remove the first occurrence of *feature* from the collection.

        Uses value equality (:meth:`Feature.__eq__`) to locate the feature, matching
        standard ``list.remove`` semantics.

        Args:
            feature: The :class:`Feature` to remove.

        Raises:
            ValueError: If *feature* is not present in the collection.
        """
        self._features.remove(feature)

    # ---- constructors ----

    @classmethod
    def from_geojson(cls, geojson: str | os.PathLike | dict) -> FeatureCollection:
        """Construct a :class:`FeatureCollection` from a GeoJSON source.

        Accepts three input forms:

        * A ``dict`` already parsed from JSON.
        * A raw JSON string.
        * A file path (``str`` or :class:`os.PathLike`) pointing to a
          ``.geojson`` or ``.json`` file.

        The non-standard top-level ``"crs"`` field — written by
        :meth:`to_geojson` as
        ``{"type": "name", "properties": {"name": "<crs>"}}`` — is read if
        present and applied to all features, enabling lossless round-trips.

        Args:
            geojson: A GeoJSON ``FeatureCollection`` as a dict, raw JSON
                string, or file path.

        Returns:
            A new :class:`FeatureCollection` instance.

        Raises:
            ValueError: If the resolved dict does not have
                ``"type": "FeatureCollection"``.
            json.JSONDecodeError: If a string or file contains invalid JSON.
            FileNotFoundError: If *geojson* is a path that does not exist.

        Example::

            fc = FeatureCollection.from_geojson("data/places.geojson")
            fc = FeatureCollection.from_geojson('{"type":"FeatureCollection","features":[]}')
        """
        geojson = _load_geojson(geojson)

        if geojson.get("type") != "FeatureCollection":
            raise ValueError(
                f"Expected a GeoJSON FeatureCollection, got type {geojson.get('type')!r}."
            )

        crs = _crs_from_geojson(geojson)
        features = [
            Feature.from_geojson(f, crs=crs) for f in geojson.get("features", [])
        ]
        return cls(features)

    @classmethod
    def from_csv(
        cls,
        path: str | os.PathLike,
        geometry_column: str = "geometry",
        crs: CrsType = None,
    ) -> FeatureCollection:
        """Construct a :class:`FeatureCollection` from a CSV file.

        The CSV must contain a column of WKT geometry strings. All other columns are
        read as feature attributes. Missing attribute values are preserved as empty
        strings (standard CSV behaviour).

        CRS cannot be inferred from CSV and must be supplied explicitly via *crs* if the
        coordinate reference system is known.

        Args:
            path: Path to the CSV file.
            geometry_column: Name of the column containing WKT geometry strings.
                Defaults to ``"geometry"``.
            crs: CRS to assign to all parsed geometries.
                Defaults to ``None``.

        Returns:
            A new :class:`FeatureCollection` instance.

        Raises:
            ValueError: If *geometry_column* is not found in the CSV header.
            FileNotFoundError: If the file at *path* does not exist.

        Example::

            fc = FeatureCollection.from_csv(
                "data/roads.csv",
                geometry_column="wkt",
                crs="epsg:27700",
            )
        """
        features = []
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if geometry_column not in (reader.fieldnames or []):
                raise ValueError(
                    f"Geometry column {geometry_column!r} not found in CSV. "
                    f"Available columns: {reader.fieldnames}"
                )
            for row in reader:
                wkt = row.pop(geometry_column)
                feature = Feature.from_wkt(wkt, attributes=dict(row), crs=crs)
                features.append(feature)
        return cls(features)

    # ---- serialisation ----

    def to_geojson(
        self,
        path: str | os.PathLike | None = None,
        crs: CrsType = None,
    ) -> dict:
        """Serialise to a GeoJSON FeatureCollection dict, optionally writing to a file.

        **CRS normalisation**: if features carry mixed CRS values they are reprojected
        to a common target before export. The target CRS is resolved in priority
        order: the *crs* argument → :attr:`crs` → the most frequently occurring CRS
        across all features. Reprojection requires pyproj; if it is disabled a
        :class:`UserWarning` is emitted and features are written with their original
        coordinates.

        The resolved CRS is written to the output as a non-standard top-level
        ``"crs"`` field so that :meth:`from_geojson` can recover it on a round-trip.
        Missing parent directories in *path* are created automatically.

        Args:
            path: Optional file path to write the GeoJSON to. If ``None``, the dict is
                returned but not written to disk.
            crs: Override the target CRS for the output. If omitted, the shared
                :attr:`crs` of the collection is used, falling back to the most common
                CRS when the collection is mixed.

        Returns:
            A ``dict`` representing the GeoJSON ``FeatureCollection``.

        Raises:
            OSError: If *path* is provided but the file cannot be written.

        Example::

            geojson = fc.to_geojson()
            fc.to_geojson("output/places.geojson")
        """
        target_crs = crs or self.crs or _most_common_crs(self._features)
        features = _normalise_crs(self._features, target_crs=target_crs)

        geojson: dict = {"type": "FeatureCollection"}

        if target_crs is not None:
            geojson["crs"] = {"type": "name", "properties": {"name": target_crs}}

        geojson["features"] = [f.to_geojson() for f in features]

        if self._metadata:
            geojson["metadata"] = self._metadata

        if path is not None:
            _ensure_parent_dir(path)
            with open(path, "w", encoding="utf-8") as f:
                json.dump(geojson, f, indent=4)

        return geojson

    def to_csv(
        self,
        path: str | os.PathLike,
        geometry_column: str = "geometry",
    ) -> None:
        """Write the collection to a CSV file with a WKT geometry column.

        Column ordering is: *geometry_column* first, then all attribute keys in the
        order they first appear across all features. Features that lack a given
        attribute key have an empty string written for that column. Missing parent
        directories in *path* are created automatically.

        Args:
            path: File path to write the CSV to.
            geometry_column: Column name for the WKT geometry strings.
                Defaults to ``"geometry"``.

        Raises:
            ValueError: If the collection is empty.
            OSError: If the file cannot be written.

        Example::

            fc.to_csv("output/roads.csv")
            fc.to_csv("output/roads.csv", geometry_column="wkt")
        """
        if not self._features:
            raise ValueError("Cannot write an empty FeatureCollection to CSV.")

        # Gather all attribute keys across all features to handle sparse data.
        all_keys: list[str] = []
        seen: set[str] = set()
        for feature in self._features:
            for key in feature.attributes:
                if key not in seen:
                    all_keys.append(key)
                    seen.add(key)

        fieldnames = [geometry_column] + all_keys

        _ensure_parent_dir(path)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()
            for feature in self._features:
                row = {geometry_column: feature.geometry.wkt}
                row.update(feature.attributes)
                writer.writerow(row)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_geojson(source: str | os.PathLike | dict) -> dict:
    """Load a GeoJSON ``dict`` from a file path, raw JSON string, or existing dict.

    Resolution order:

    1. If *source* is already a ``dict``, return it directly.
    2. If the string form of *source* is an existing file path, open and
       parse the file as JSON.
    3. Otherwise, parse *source* as a raw JSON string.

    Args:
        source: A GeoJSON ``dict``, a path to a ``.geojson`` / ``.json``
            file, or a raw JSON string.

    Returns:
        A parsed ``dict`` containing the GeoJSON object.

    Raises:
        json.JSONDecodeError: If *source* is a string that is neither a
            valid file path nor valid JSON.
    """
    if isinstance(source, dict):
        return source
    source = str(source)
    if os.path.exists(source):
        with open(source, "r", encoding="utf-8") as f:
            return json.load(f)
    return json.loads(source)


def _crs_from_geojson(geojson: dict) -> str | None:
    """Extract a CRS string from a GeoJSON object's non-standard ``"crs"`` field.

    Reads the structure written by :meth:`FeatureCollection.to_geojson`::

        {"crs": {"type": "name", "properties": {"name": "<crs_string>"}}}

    Args:
        geojson: A parsed GeoJSON dict that may contain a top-level ``"crs"``
            key.

    Returns:
        The CRS name string if the field is present and well-formed,
        otherwise ``None``.
    """
    try:
        return geojson["crs"]["properties"]["name"]
    except (KeyError, TypeError):
        return None


def _most_common_crs(features: list[Feature]) -> str | None:
    """Return the most frequently occurring CRS across a list of features.

    Used by :meth:`FeatureCollection.to_geojson` to pick a sensible export CRS when the
    collection contains mixed CRS values.

    Args:
        features: A list of :class:`Feature` instances to inspect.

    Returns:
        The CRS value that appears most often across all feature geometries, or
        ``None`` if *features* is empty. Ties are broken by ``max`` (arbitrary but
        deterministic).
    """
    counts: dict = {}
    for f in features:
        key = f.geometry.crs
        counts[key] = counts.get(key, 0) + 1
    if not counts:
        return None
    return max(counts, key=lambda k: counts[k])


def _normalise_crs(
    features: list[Feature],
    target_crs: CrsType,
) -> list[Feature]:
    """Return *features* with all geometries transformed to *target_crs*.

    Short-circuits without any work if *features* is empty or if every feature already
    carries *target_crs*. When CRS values are mixed and pyproj is disabled, emits a
    :class:`UserWarning` and returns the original list unchanged.

    Args:
        features: The :class:`Feature` objects to normalise.
        target_crs: The destination CRS. If ``None``, the list is returned unchanged.

    Returns:
        A list of :class:`Feature` objects whose geometries are all in *target_crs*.
        Features already in *target_crs* are included as-is. If reprojection is skipped
        due to disabled pyproj, the original list is returned.

    Warns:
        UserWarning: If features carry mixed CRS values and pyproj is disabled.
    """
    if not features:
        return features

    if all(f.geometry.crs == target_crs for f in features):
        return features

    if not _config.USE_PYPROJ:
        warnings.warn(
            "FeatureCollection contains features with mixed CRS but pyproj is "
            "disabled. Exporting as-is without transforming. Enable pyproj with "
            "config.set_use_pyproj(True) to suppress this warning.",
            stacklevel=3,
        )
        return features

    return [
        Feature(
            geometry=(
                f.geometry.transform(target_crs)
                if f.geometry.crs != target_crs
                else f.geometry
            ),
            attributes=f.attributes,
        )
        for f in features
    ]


def _ensure_parent_dir(path: str | os.PathLike) -> None:
    """Create parent directories for *path* if they do not already exist.

    Equivalent to ``mkdir -p`` on the directory component of *path*. No error is raised
    if the directories already exist.

    Args:
        path: A file path whose parent directory should be created.
    """
    parent = os.path.dirname(os.path.abspath(path))
    os.makedirs(parent, exist_ok=True)
