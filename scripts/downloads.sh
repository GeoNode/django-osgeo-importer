#!/bin/bash
mkdir downloads
pushd downloads
GS_VERSION=2.8.x
wget -N http://repo2.maven.org/maven2/org/mortbay/jetty/jetty-runner/8.1.8.v20121106/jetty-runner-8.1.8.v20121106.jar
wget -N http://ares.boundlessgeo.com/geoserver/${GS_VERSION}/geoserver-${GS_VERSION}-latest-war.zip
wget -N http://build.geonode.org/geoserver/latest/geoserver.war
wget -N https://s3.amazonaws.com/django-osgeo-importer/gdal-2.1.0-linux-bin.tar.gz

pip install awscli
sudo mkdir -p -m 777 importer-test-files
aws --no-sign-request s3 sync s3://mapstory-data/importer-test-files/ importer-test-files
popd
