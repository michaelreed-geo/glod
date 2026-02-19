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

