sudo apt-get -qq -y update
sudo apt-get -y install git build-essential python-dev libproj-dev
cd /tmp
wget http://download.osgeo.org/geos/geos-3.4.2.tar.bz2
tar xjf geos-3.4.2.tar.bz2
cd geos-3.4.2
./configure
sudo make -j 4
sudo make install

sudo mkdir -p /srv/gdal
sudo chown vagrant:vagrant /srv/gdal
git clone https://github.com/OSGeo/gdal.git /srv/gdal
cd /srv/gdal/gdal
./configure --with-python --with-sqlite3 --with-spatialite --with-geopackage --with-curl
#./mkbindist.sh -dev $version linux
sed -i 's/#!\/bin\/sh/#!\/bin\/bash/'  mkbindist.sh
version=$(cat VERSION)
./mkbindist.sh -dev $version linux
cp gdal-${version}-linux-bin.tar.gz /vagrant
# aws s3 cp gdal-2.1.0-linux-bin.tar.gz s3://django-osgeo-importer --profile=prominentedge
