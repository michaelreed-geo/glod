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

Typical usage is for handling GIS data returned by APIs and turning it into something useful and consistent for onward usage.

Assume an API returns a json type object which contains the bounds of a rectangle geometry along with
some attributes you want to retain. The example below shows how you would use `glod` to interact with these data.

```python
from glod import Geometry, Feature

# extent as x_min, y_min, x_max, y_max, the API returns spatial data in CRS EPSG:3857
api_result = {'extent': [50, 1000, 200, 1100], 'name': 'map', 'date': 2005}

# create a glod Geometry to store the geometry
geometry = Geometry.from_bounds(bounds=api_result['extent'], crs='EPSG:3857')

print(geometry.type)
# 'Polygon'

print(geometry.coordiates)
# ((50.0, 1000.0), (50.0, 1100.0), (200.0, 1100.0), (200.0, 1000.0), (50.0, 1000.0))

# store the attributes for the result along with the geometry using a Feature
feature = Feature(geometry, attributes={'Name': api_result['name'], 'Date': api_result['date']})

print(feature.attributes)
# {'Name': 'map', 'Date': 2005}
```

Now assume your API query returns a list of results, with geometry as point coordinates and the CRS as EPSG:27700.
You can collect these results into a `FeatureCollection` object.
```python
from glod import FeatureCollection

api_result = [{'point': [0, 0], 'id': 'point1'}, {'point': [100, 50], 'id': 'point2'}]
all_features = []
for i in api_result:
    # turn each list item into a glod Feature
    geometry = Geometry.from_coordinates(i['point'], 'EPSG:27700')
    feature = Feature(geometry, attributes={'id': i['id']})
    all_features.append(feature)

# collate all features into a collection
collection = FeatureCollection(all_features)

print(len(collection))
# 2

# you can also index features within a collection, e.g.
print(collection[0].geometry.coordinates)
# [0, 0]

print(collection[1].attributes['id'])
# 'point2'
```
You can easily export a `FeatureCollection` to a geojson too, including writing to a file.

```python
# turn the collection into a geojson structure
geojson = collection.to_geojson()

print(geojson)
# {'type': 'FeatureCollection', 'features': [{'type': 'Feature', 'geometry': {'type': 'Point', 'coordinates': [0, 0]}, ...

# write the collection to a .geojson file
collection.to_geojson('api_result.geojson')

# write to a .geojson file but transform to a different CRS
collection.to_geojson('api_result.geojson', crs='EPSG:4326')
```
For more details on properties and methods for `Geometry`, `Feature` and `FeatureCollection` objects,
refer to the source code docstrings.