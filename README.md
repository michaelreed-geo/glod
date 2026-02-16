<img src="resources/icon2.svg" width="150" />

# geometry, low on dependencies

**glod** is a Python package for handling simple geospatial geometries in a low-dependency way.
It was developed to create a lightweight GIS means of interacting with web APIs which return spatial data without needing
to rely on more extensive spatial packages.

The goal of this project, as the name suggests, is to keep the number of external dependencies low!

_Current number of external dependencies: 1_

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
* Uses [pyproj](https://github.com/pyproj4/pyproj) for coordinate transforms*

\* pyproj can be disabled at runtime so no import occurs. However, no coordinate transformations can occur without pyproj.

## Installation

---

