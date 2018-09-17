#!/bin/sh

set -u
set -x

DBNAME="heatmap"
COLLIDEOSCOPE_DBNAME="collideoscope"

dropdb $DBNAME
createdb -T template_postgis $DBNAME

ogr2ogr -f PostgreSQL -t_srs EPSG:27700 -lco GEOMETRY_NAME=geom -nln incidents PG:"dbname=$DBNAME" PG:"dbname=$COLLIDEOSCOPE_DBNAME" -sql "SELECT ST_SetSRID(ST_MakePoint(longitude, latitude), 4326) as geom, id FROM problem"
psql -d $DBNAME -c "SELECT COUNT(*) FROM incidents"
