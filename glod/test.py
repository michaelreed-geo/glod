from glod import Geometry
from glod import Feature
from glod.utils import get_coordinates_from_wkt, geojson_to_wkt, flatten_coordinate_tuple_to_str
import re

pattern = re.compile(r"^POINT\s*\(\s*-?\d+(?:\.\d+)?\s-?\d+(?:\.\d+)?\s*\)$")
i=pattern.fullmatch("Point ((1 2))")

# i = Geometry.from_wkt("linestring ((0 5, 5 0, 0 5))", "EPSG:27700")
#
# feat = Feature(i, {"name": "Testname"})
#
# x = feat.to_geojson
#
# y = Feature.from_geojson(x)