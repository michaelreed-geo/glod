<img src="resources/icon2.svg" width="150" />

# geometry, low on dependencies

**glod** is a Python package for handling simple geospatial geometries in a low-dependency way.
It was developed to create a lightweight GIS means of interacting with web APIs which return spatial data without needing
to rely on more extensive spatial packages.

The goal of this project, as the name suggests, is to keep the number of external dependencies low!

![Dynamic TOML Badge](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2Fmichaelreed-geo%2Fglod%2Frefs%2Fheads%2Fmain%2Fpyproject.toml&query=%24.project.dependencies&style=flat-square&label=mandatory%20dependencies&color=rgb(69%2C117%2C243))<br>![Dynamic TOML Badge](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2Fmichaelreed-geo%2Fglod%2Frefs%2Fheads%2Fmain%2Fpyproject.toml&query=%24.project.optional-dependencies%5B*%5D&style=flat-square&label=optional%20dependencies&color=rgb(91%2C208%2C187))

## Features

---
* Supports simple, 2D geometries (Point, LineString, Polygon) via a single `Geometry` object
* Store attributes alongside geometries with the `Feature` object
* Group features as `FeatureCollection` objects
* Analyse intersections between geometries
* Access basic geometric properties of geometries (centroid, bounds)
* Import/export `Geometry` as Well Known Text (WKT) or geojson types
* Import/export `FeatureCollection` as full geojson files 
* Implements the [`__geo_interface__`](https://gist.github.com/sgillies/2217756) protocol for interoperability with other packages and software
* Optional: uses [pyproj](https://github.com/pyproj4/pyproj) for coordinate transforms (see [Installation](#Installation))

## Installation

---

## Usage

Typical usage is for handling spatial data returned by APIs in non-native GIS forms and turning it into something useful and consistent for onward usage.

### Data formatting

```python
from glod import Feature, FeatureCollection, Geometry

# assume some data returned by an API
data = [
    {'id': 'point1', 'easting': 12, 'northing': 34, 'date': 2021},
    {'id': 'point2', 'easting': 56, 'northing': 78, 'date': 2023}
]
api_crs = 'EPSG:27700'  # assume the coordinate reference system of the API is known

# turn each item of data into a glod Feature with geometry and attributes
all_features = []
for item in data:
    geometry = Geometry.from_coordinates(coordinates=(item['easting'], item['northing']), crs=api_crs)
    attributes = {'id': item['id'], 'date': item['date']}
    feature = Feature(geometry, attributes)
    all_features.append(feature)

# collate features as a FeatureCollection
collection = FeatureCollection(all_features)

# write to a geojson
geojson = collection.to_geojson('api_data.geojson')

print(geojson)
# {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [12.0, 34.0]}, ...]}

# iterate through features and do _whatever_
for feature in collection:
    print(feature.attributes['id'], feature.geometry.to_wkt, feature.geometry.crs)
    ...

# point1 POINT (12.0, 34.0) EPSG:27700
# point2 POINT (56.0, 78.0) EPSG:27700 
```

### Geometry processing
It can also be used as a lightweight means of checking for geometry intersections.

```python
from glod import Geometry

geometry1 = Geometry.from_wkt(wkt="Polygon ((0 0, 0 10, 10 10, 10 0, 0 0))", crs="EPSG:3857")
geometry2 = Geometry.from_bounds(bounds=(5, 5, 15, 15), crs="EPSG:3857")

print(geometry1.intersects(geometry2))
# True
```