#!/bin/bash
export PGDATABASE=osgeo_importer_test
export PGUSER=osgeo
export PGPASSWORD=osgeo
psql -t -c "select 'drop table ' || tablename || ';'  from pg_tables where schemaname='public' and tablename != 'spatial_ref_sys'" | psql
