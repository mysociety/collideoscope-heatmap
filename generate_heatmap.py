#!/usr/bin/env python3
import os
import sys
import sqlite3
from io import BytesIO
from datetime import datetime
from functools import partial
from zipfile import ZipFile
from tempfile import TemporaryDirectory

import records
import requests
from shapely.geometry import shape, mapping, box, CAP_STYLE
from shapely.wkt import dumps
from shapely.ops import transform
import fiona
import pyproj


# These environment variables determine the data sources used by the script.

# This is the Collideoscope database, where incident lat/lons will be read from.
# Required.
COLLIDEOSCOPE_DATABASE_URL = os.environ['COLLIDEOSCOPE_DATABASE_URL']

# This should be the path to the OS Open Roads zip file (oproad_essh_gb.zip),
# or a URL where it can be downloaded from.
# It does not need to be unzipped - the script handles that.
# Optional. Defaults to downloading a copy from a known URL.
OS_OPEN_ROADS_PATH = os.environ.get('OS_OPEN_ROADS_PATH',
    'http://parlvid.mysociety.org/os/oproad_essh_gb-2018-10.zip')

# Sets where the output GeoPackage will be written.
# Optional. By default it will be 'heatmap.gpkg' in the working directory.
OUTPUT_PATH = os.environ.get('OUTPUT_PATH', 'heatmap.gpkg')

# Controls the distance (in metres) to buffer each road feature by
# when determining incident density.
# Optional. Defaults to 25M.
BUFFER = int(os.environ.get("BUFFER", 25))


def log(*msgs):
    """Because sometimes logging.getLogger is too much"""
    print(datetime.now(), *msgs, file=sys.stderr)


def read_shapefile(path):
    log("Processing {}".format(os.path.basename(path)))
    with fiona.open(path, 'r') as shapefile:
        for feature in shapefile:
            yield shape(feature['geometry'])


def load_roads():
    if OS_OPEN_ROADS_PATH.startswith("http"):
        log("Downloading oproad_essh_gb.zip from {}".format(OS_OPEN_ROADS_PATH))
        response = requests.get(OS_OPEN_ROADS_PATH)
        log("done.")
        openroads_zip = BytesIO(response.content)
    else:
        openroads_zip = OS_OPEN_ROADS_PATH

    with ZipFile(openroads_zip) as z:
        for shp in (f for f in z.namelist() if f.endswith("RoadLink.shp")):
            prefix = shp.rsplit(".", 1)[0]
            files = ["{}.{}".format(prefix, ext) for ext in ["dbf", "prj", "shp", "shx"]]
            with TemporaryDirectory() as tmpdir:
                for file in files:
                    z.extract(file, path=tmpdir)
                yield from read_shapefile(os.path.join(tmpdir, shp))


def load_collideoscope_database():
    log("Loading incidents from Collideoscope...")
    db = records.Database("sqlite:///:memory:")

    sqlite = db.db.engine.raw_connection().connection
    sqlite.enable_load_extension(True)
    try:
        sqlite.load_extension("mod_spatialite.so")
    except sqlite3.OperationalError:
        # On macOS it should be called without the extension.
        sqlite.load_extension("mod_spatialite")

    db.query("SELECT InitSpatialMetadata(1)")
    db.query("CREATE TABLE incidents ( id INTEGER NOT NULL PRIMARY KEY )")
    db.query("SELECT AddGeometryColumn('incidents', 'geom', 27700, 'POINT', 'XY', 1)")
    db.query("SELECT CreateSpatialIndex('incidents', 'geom')")

    wgs_to_bng = partial(
        pyproj.transform,
        pyproj.Proj(init='epsg:4326'),
        pyproj.Proj(init='epsg:27700'))

    with records.Database(COLLIDEOSCOPE_DATABASE_URL) as collideoscope:
        for rid, lat, lon in collideoscope.query("SELECT id, latitude, longitude FROM problem WHERE confirmed IS NOT NULL"):
            x, y = wgs_to_bng(lon, lat)
            x, y = round(x, 2), round(y, 2)
            wkt = 'POINT({} {})'.format(x, y)
            db.query("INSERT INTO incidents (id, geom) VALUES (:id, PointFromText(:wkt, 27700))", id=rid, wkt=wkt)

    count = db.query("SELECT COUNT(*) AS count FROM incidents")[0].count
    log("Loaded {} incidents from Collideoscope DB.".format(count))
    return db


def main():
    db = load_collideoscope_database()

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
                    COUNT(*) AS count
                   FROM incidents
                   WHERE
                    ROWID IN (
                        SELECT ROWID
                        FROM SpatialIndex
                        WHERE f_table_name = 'incidents'
                        AND search_frame = ST_GeomFromText(:bbox, 27700)
                    )
                    AND ST_Contains(ST_GeomFromText(:buffered, 27700), geom)
                   """
            count = db.query(q, bbox=dumps(bbox), buffered=dumps(buffered))[0].count
            if count:
                output.write({
                    'type': 'Feature',
                    'id': '-1',
                    'geometry': mapping(transform(reproject, geom)),
                    'properties': {
                        'density': count / geom.length
                    }
                })
                matches += 1
                if matches % 1000 == 0:
                    log("Found {} features from {} so far".format(matches, i))
        log("Found {} features with incidents.".format(matches))


if __name__ == '__main__':
    main()
