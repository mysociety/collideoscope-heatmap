#!/bin/sh

set -u
set -x

DBNAME="heatmap"
COLLIDEOSCOPE_DBNAME="collideoscope"
ROADS_SHPS="/Users/davea/Code/fixmystreet/collideoscope/scripts/heatmap/data/roads"

dropdb $DBNAME
createdb -T template_postgis $DBNAME

for SHP in $ROADS_SHPS/*.shp; do
    shp2pgsql -S -s EPSG:27700 -D -p "$SHP" roads | psql -q -d $DBNAME
    break # Just create the table from the first file
done

for SHP in $ROADS_SHPS/*.shp; do
    shp2pgsql -S -s EPSG:27700 -D -a "$SHP" roads | psql -q -d $DBNAME
done

psql -d $DBNAME -c "SELECT COUNT(*) FROM roads"

ogr2ogr -f PostgreSQL -t_srs EPSG:27700 -lco GEOMETRY_NAME=geom -nln incidents PG:"dbname=$DBNAME" PG:"dbname=$COLLIDEOSCOPE_DBNAME" -sql "SELECT ST_SetSRID(ST_MakePoint(longitude, latitude), 4326) as geom, id FROM problem"
psql -d $DBNAME -c "SELECT COUNT(*) FROM incidents"