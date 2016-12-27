#!/bin/bash
set -e

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" <<-EOSQL
    CREATE USER osgeo WITH PASSWORD 'osgeo';
    ALTER USER osgeo WITH SUPERUSER;
    CREATE DATABASE osgeo WITH OWNER osgeo;
    GRANT ALL PRIVILEGES ON DATABASE osgeo TO osgeo;
EOSQL
