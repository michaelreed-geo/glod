<img src="resources/icon2.svg" width="150" />

# Geometry, Low On Dependencies

**glod** is a Python package for handling simple geospatial geometries in a low-dependency way.
It was developed to create a lightweight GIS means of interacting with web APIs which return spatial data without needing
to rely on more extensive spatial packages.

The goal of this project, as the name suggests, it to keep the number of external dependencies low!

_Current number of external dependencies: 1_

## Features
* Supports simple, 2D geometries (Point, LineString, Polygon) via a single object `Geometry`
* Analyses intersections between geometries
* Using `Feature` to store attributes alongside geometries
* Basic geometric properties of geometries (centroid, bounds)
* Import/export of geometries as Well Known Text (WKT) or geojson types
* Implements the [`__geo_interface__`](https://gist.github.com/sgillies/2217756) protocol for interoperability with other packages and software
* Uses [pyproj](https://github.com/pyproj4/pyproj) for coordinate transforms*

\* pyproj can be disabled at runtime so no import occurs. However, no coordinate transformations can occur without pyproj.

## Install
___
