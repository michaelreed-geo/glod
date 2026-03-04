<img src="resources/icon2.svg" width="150" />

# geometry, low on dependencies

**glod** is a Python package for handling simple geospatial geometries in a low-dependency way.
It was developed to create a lightweight GIS means of interacting with web APIs which return spatial data without needing
to rely on more extensive spatial packages.

The goal of this project, as the name suggests, is to keep the number of external dependencies low!

![Dynamic TOML Badge](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2Fmichaelreed-geo%2Fglod%2Frefs%2Fheads%2Fmain%2Fpyproject.toml&query=%24.project.dependencies&style=flat-square&label=mandatory%20dependencies&color=rgb(69%2C117%2C243))<br>![Dynamic TOML Badge](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2Fmichaelreed-geo%2Fglod%2Frefs%2Fheads%2Fmain%2Fpyproject.toml&query=%24.project.optional-dependencies%5B*%5D&style=flat-square&label=optional%20dependencies&color=rgb(105%2C51%2C176))

## Features

---
* Supports 2D and 3D singlepart geometries (Point, LineString, Polygon) and their multi-part equivalents (MultiPoint, MultiLineString, MultiPolygon)
* Store attributes alongside geometries with the `Feature` object
* Group features as `FeatureCollection` objects
* Test geometric intersections between any two geometries with `Geometry.intersects()`
* Access geometric properties (bounds, WKT, GeoJSON, CRS, has_z)
* Construct geometries from WKT, GeoJSON, coordinate arrays, bounding boxes, or any object implementing `__geo_interface__`
* Import/export `FeatureCollection` as GeoJSON files or CSV with a WKT geometry column
* Implements the [`__geo_interface__`](https://gist.github.com/sgillies/2217756) protocol for interoperability with other packages
* Optional: uses [pyproj](https://github.com/pyproj4/pyproj) for coordinate transforms (see [Installation](#Installation))

## Installation

---

## Usage


### Typical usage

```python
from glod import Feature, FeatureCollection, Geometry

# assume some data returned by an API
data = [
    {'id': 'point1', 'easting': 12, 'northing': 34, 'date': 2021},
    {'id': 'point2', 'easting': 56, 'northing': 78, 'date': 2023}
]
api_crs = 'EPSG:27700'

# turn each item of data into a glod Feature with geometry and attributes
all_features = []
for item in data:
    geometry = Geometry.from_coordinates(coordinates=(item['easting'], item['northing']), crs=api_crs)
    attributes = {'id': item['id'], 'date': item['date']}
    all_features.append(Feature(geometry, attributes))

# collate features as a FeatureCollection
collection = FeatureCollection(all_features)

# write to a geojson
geojson = collection.to_geojson('api_data.geojson')

# iterate through features
for feature in collection:
    print(feature.attributes['id'], feature.geometry.wkt, feature.geometry.crs)

# point1 POINT (12 34) EPSG:27700
# point2 POINT (56 78) EPSG:27700
```

### Geometry construction

```python
from glod import Geometry
from glod.geometry import Point, Polygon

# from WKT
line = Geometry.from_wkt("LINESTRING (0 0, 1 1, 2 0)", crs="EPSG:27700")

# from GeoJSON dict
point = Geometry.from_geojson({"type": "Point", "coordinates": [1.0, 2.0]}, crs="EPSG:27700")

# from a coordinate array (type inferred from structure)
poly = Geometry.from_coordinates([[[0, 0], [1, 0], [1, 1], [0, 0]]])

# from a bounding box
bbox = Polygon.from_bounds((0, 0, 10, 10), crs="EPSG:27700")

# from any object implementing __geo_interface__ (e.g. shapely)
glod_geom = Geometry.from_object(shapely_geom, crs="EPSG:27700")
```

### Test geometry intersections

```python
from glod import Geometry

geometry1 = Geometry.from_wkt("POLYGON ((0 0, 0 10, 10 10, 10 0, 0 0))", crs="EPSG:3857")
geometry2 = Geometry.from_wkt("POLYGON ((5 5, 5 15, 15 15, 15 5, 5 5))", crs="EPSG:3857")

print(geometry1.intersects(geometry2))
# True
```

### CSV I/O

```python
# write to CSV with a WKT geometry column
collection.to_csv("data.csv")

# read back, supplying the CRS since CSV has no standard CRS field
collection2 = FeatureCollection.from_csv("data.csv", crs="EPSG:27700")
```

### Coordinate Reference System (CRS) transforms

Transformation is handled by _pyproj_. Because this is an optional dependency, it must
be internally enabled within _glod_ by calling `glod.config.set_use_pyproj(True)`
before running your code.

By default _pyproj_ will be disabled every run time unless specifically enabled.