#!/usr/bin/env python3
import os
from datetime import datetime
from functools import partial
from zipfile import ZipFile
from tempfile import TemporaryDirectory

import records
from shapely.geometry import shape, mapping, box, CAP_STYLE
from shapely.wkt import dumps
from shapely.ops import transform
import fiona
import pyproj


# These environment variables determine the data sources used by the script.
# The first two are mandatory.

# This should be the path to the OS Open Roads zip file (oproad_essh_gb.zip).
# It does not need to be unzipped - the script handles that.
OS_OPEN_ROADS_PATH = os.environ['OS_OPEN_ROADS_PATH']

# This is the PostGIS database where load_into_postgis.sh stored the incidents.
DATABASE_URL = os.environ['DATABASE_URL']

# Optional, sets where the output GeoPackage will be written. By default
# it will be 'heatmap.gpkg' in the working directory.
OUTPUT_PATH = os.environ.get('OUTPUT_PATH', 'heatmap.gpkg')

# Optional, controls the distance (in metres) to buffer each road feature by
# when determining incident density.
BUFFER = int(os.environ.get("BUFFER", 25))


def read_shapefile(path):
    print("Processing {}".format(os.path.basename(path)))
    with fiona.open(path, 'r') as shapefile:
        for feature in shapefile:
            yield shape(feature['geometry'])


def load_roads():
    with ZipFile(OS_OPEN_ROADS_PATH) as z:
        for shp in (f for f in z.namelist() if f.endswith("RoadLink.shp")):
            prefix = shp.rsplit(".", 1)[0]
            files = ["{}.{}".format(prefix, ext) for ext in ["dbf", "prj", "shp", "shx"]]
            with TemporaryDirectory() as tmpdir:
                for file in files:
                    z.extract(file, path=tmpdir)
                yield from read_shapefile(os.path.join(tmpdir, shp))


def main():
    db = records.Database(DATABASE_URL)

    reproject = partial(
        pyproj.transform,
        pyproj.Proj(init='epsg:27700'),
        pyproj.Proj(init='epsg:3857'))

    meta = {
        'crs': {'init': 'epsg:3857'},
        'driver': 'GPKG',
        'schema': {
            'geometry': 'LineString',
            'properties': {
                'density': 'float'
            }
        }
    }

    with fiona.open(OUTPUT_PATH, 'w', **meta) as output:
        matches = 0
        for i, geom in enumerate(load_roads(), start=1):
            buffered = geom.buffer(BUFFER, cap_style=CAP_STYLE.flat)
            bbox = box(*buffered.bounds)
            q = """SELECT
                    COUNT(*)
                   FROM incidents
                   WHERE
                    geom && ST_GeomFromText(:bbox, 27700)
                    AND ST_Contains(ST_GeomFromText(:buffered, 27700), geom)
                   """
            count = db.query(q, bbox=dumps(bbox), buffered=dumps(buffered))[0].count
            if count:
                matches += 1
                output.write({
                    'type': 'Feature',
                    'id': '-1',
                    'geometry': mapping(transform(reproject, geom)),
                    'properties': {
                        'density': count / geom.length
                    }
                })
                if matches % 1000 == 0 or i % 1000 == 0:
                    print(datetime.now(), i, matches)
        print(datetime.now(), i, matches)


if __name__ == '__main__':
    main()
