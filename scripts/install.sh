#!/bin/bash
sudo apt-get -qq -y update
# geoserver
sudo apt-get install -y --force-yes openjdk-7-jdk --no-install-recommends
mkdir gs
pushd gs
wget http://repo2.maven.org/maven2/org/mortbay/jetty/jetty-runner/8.1.8.v20121106/jetty-runner-8.1.8.v20121106.jar
wget http://ares.boundlessgeo.com/geoserver/${GS_VERSION}/geoserver-${GS_VERSION}-latest-war.zip
wget http://build.geonode.org/geoserver/latest/geoserver.war
chmod +x jetty-runner-8.1.8.v20121106.jar
chmod +x geoserver-${GS_VERSION}-latest-war.zip
popd
# postgis
sudo add-apt-repository ppa:ubuntugis/ubuntugis-unstable -y # For postgresql-9.1-postgis-2.1
sudo rm -f /etc/apt/sources.list.d/pgdg-source.list # postgis from pgdg requires different gdal package than the grass package
sudo apt-get update -qq

wget https://s3.amazonaws.com/django-osgeo-importer/gdal-2.1.0-linux-bin.tar.gz
sudo tar --directory=/usr/local/lib -xvf gdal-2.1.0-linux-bin.tar.gz
sudo mv /usr/local/lib/gdal-2.1.0-linux-bin /usr/local/lib/gdal
export PATH=/usr/local/lib/gdal/bin:$PATH
sudo touch /usr/lib/python2.7/dist-packages/gdal.pth
sudo su -c  "echo '/usr/local/lib/gdal/lib/python2.7/site-packages' > /usr/lib/python2.7/dist-packages/gdal.pth"
sudo su -c "echo '/usr/local/lib/gdal/lib/' >> /etc/ld.so.conf"
sudo ldconfig
sudo touch /etc/profile.d/gdal
sudo su -c "echo 'export GDAL_DATA=/usr/local/lib/gdal/share/gdal/' >> /etc/profile.d/gdal.sh"


sudo apt-get remove -y postgresql-9.3-postgis-2.1 # Remove postgis from pgdg, will install postgis from ubuntugis-unstable instead
sudo apt-get install -y --no-install-recommends postgresql-9.3-postgis-2.1 libpq-dev python-dev python-lxml libxslt1-dev
sudo apt-get install -y python-virtualenv python-imaging python-pyproj python-shapely python-nose python-httplib2 python-httplib2 gettext git
sudo apt-get install -y libproj0 libproj-dev postgresql-plpython-9.3



# python
pip install psycopg2

if [ -n "$1" ]
 then
 cd $1
fi

pip install -r requirements.txt
pip install --upgrade  numpy
pip install -e .
pip install awscli

sudo mkdir -p -m 777 importer-test-files
aws s3 sync s3://mapstory-data/importer-test-files/ importer-test-files
