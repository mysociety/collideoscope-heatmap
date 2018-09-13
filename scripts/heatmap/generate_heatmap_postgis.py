#!/usr/bin/env python3

import fiona
import records
from shapely.geometry import mapping, box, CAP_STYLE
from shapely.wkb import loads
from shapely.wkt import dumps

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
        for road in db.query("SELECT * FROM roads"):
            geom = loads(road.geom, hex=True)
            q = """SELECT
                    COUNT(*)
                   FROM incidents
                   WHERE
                    geom && ST_Envelope(ST_Buffer(ST_GeomFromText(:wkt, 27700), :distance))
                    AND ST_Contains(ST_Buffer(ST_GeomFromText(:wkt, 27700), :distance), geom)
                   """
            count = db.query(q, wkt=dumps(geom), distance=BUFFER)[0].count
            if count:
                matches +=1
                output.write({
                    'type': 'Feature',
                    'id': '-1',
                    'geometry': mapping(geom),
                    'properties': {
                        'density': count / geom.length
                    }
                })
        print(matches)



if __name__ == '__main__':
    main()