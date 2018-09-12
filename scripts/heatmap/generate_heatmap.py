#!/usr/bin/env python3
from itertools import islice
from functools import reduce

from shapely.geometry import mapping, shape, box, CAP_STYLE
import fiona

ROADS_PATH = "data/exploded_roads.shp"
INCIDENTS_PATH = "data/incidents.shp"
OUTPUT_PATH = "output/heatmap.shp"

ROAD_BUFFER = 25


def load_roads():
    return fiona.open(ROADS_PATH, 'r')


def load_incidents():
    # We need to iterate across all incidents for each road feature,
    # and don't care about anything other than the geometry, so do some
    # work up front by generating the geometry objects now
    print("Loading incidents from {}".format(INCIDENTS_PATH))
    incidents = [shape(snap_geometry(f['geometry'], ROAD_BUFFER)) for f in fiona.open(INCIDENTS_PATH, 'r')]
    print("done.")
    return incidents


def write_heatmap(output, roads, incidents):
    for road in islice(roads, 100):
        geom = shape(snap_geometry(road['geometry'], ROAD_BUFFER))
        buffered = geom.buffer(ROAD_BUFFER, 3)

        # Iterating across all collisions is slow; should use a spatial index
        count = sum(1 for p in incidents if buffered.contains(p))

        try:
            road['properties']['density'] = count / geom.length
        except ZeroDivisionError:
            continue # geom might have been snapped to zero-length, nevermind


        # print(".", end="", flush=True)
        output.write(road)

def snap_geometry(g, precision):
    coords = g['coordinates']
    if g['type'] == 'Point':
        coords = [coords]
    g['coordinates'] = snap_coordinates(coords, precision)
    if g['type'] == 'Point':
        g['coordinates'] = g['coordinates'][0]
    return g

def snap_coordinates(coords, precision):
    return [(
        round(p[0] / precision, 0) * precision,
        round(p[1] / precision, 0) * precision
        ) for p in coords]


def main():
    roads = load_roads()
    incidents = load_incidents()
    roads.meta['schema']['properties']['density'] = 'float:10.2'

    print("Writing to {}".format(OUTPUT_PATH))
    with fiona.open(OUTPUT_PATH, 'w', **roads.meta) as output:
        write_heatmap(output, roads, incidents)
    print("done.")


if __name__ == '__main__':
    main()
