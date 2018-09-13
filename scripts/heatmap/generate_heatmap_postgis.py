#!/usr/bin/env python3

import records
from shapely.geometry import box, CAP_STYLE
from shapely.wkb import loads
from shapely.wkt import dumps

DB = "postgres:///heatmap"
BUFFER = 25

def main():
    db = records.Database(DB)
    print(db.query("SELECT COUNT(*) FROM roads")[0].count)
    print(db.query("SELECT COUNT(*) FROM incidents")[0].count)

    matches = 0
    for road in db.query("SELECT * FROM roads"):
        geom = loads(road.geom, hex=True)
        bbox = box(*geom.bounds).buffer(BUFFER, cap_style=CAP_STYLE.square)
        incidents = db.query("SELECT geom FROM incidents WHERE geom && ST_GeomFromText(:wkt, 27700)", wkt=dumps(bbox))

        buffered = None
        count = 0
        for incident in incidents:
            if buffered is None:
                buffered = geom.buffer(BUFFER, cap_style=CAP_STYLE.flat)
            i_geom = loads(incident.geom, hex=True)
            if buffered.contains(i_geom):
                count += 1
        if count:
            # print(geom.length, count)
            matches +=1
    print(matches)



if __name__ == '__main__':
    main()