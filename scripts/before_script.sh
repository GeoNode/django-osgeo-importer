#!/bin/bash

sudo -u postgres psql -c "create user osgeo with password 'osgeo';"
sudo -u postgres psql -c "create database osgeo_importer_test owner osgeo;"
sudo -u postgres psql -d osgeo_importer_test -c "create extension postgis"
sudo -u postgres psql -d osgeo_importer_test -c "alter user osgeo superuser"

if [ -n "$1" ]
 then
 pushd $1
fi

python manage.py syncdb --noinput
python mange.py runserver > /dev/null 2>&1 &

if [ -n "$1" ]
 then
 popd
fi

java -Xmx512m -XX:MaxPermSize=256m -Dorg.eclipse.jetty.server.webapp.parentLoaderPriority=true -jar gs/jetty-runner-8.1.8.v20121106.jar --path /geoserver gs/geoserver.war > /dev/null 2>&1 &
sleep 90
