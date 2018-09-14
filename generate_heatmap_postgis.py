#!/usr/bin/env python3
from datetime import datetime

import records
from shapely.geometry import mapping, box, CAP_STYLE
from shapely.wkb import loads
from shapely.wkt import dumps
import fiona

DB = "postgres:///heatmap"
OUTPUT_PATH = "output/heatmap.shp"

BUFFER = 25

def main():
    db = records.Database(DB)
    print(db.query("SELECT COUNT(*) FROM roads")[0].count)
    print(db.query("SELECT COUNT(*) FROM incidents")[0].count)

    meta = {
            'crs': {'init': 'epsg:27700'},
            'driver': 'ESRI Shapefile',
            'schema': {
                'geometry': 'LineString',
                'properties': {
                    'density': 'float'
                }
            }
        }

    with fiona.open(OUTPUT_PATH, 'w', **meta) as output:
        matches = 0
        for i, road in enumerate(db.query("SELECT * FROM roads"), start=1):
            geom = loads(road.geom, hex=True)
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
                    'geometry': mapping(geom),
                    'properties': {
                        'density': count / geom.length
                    }
                })
                if matches % 1000 == 0:
                    print(datetime.now(), i, matches)
        print(datetime.now(), i, matches)



if __name__ == '__main__':
    main()