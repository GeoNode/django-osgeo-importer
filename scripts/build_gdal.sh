sudo apt-get -qq -y update
sudo apt-get -y install git build-essential python-dev libproj-dev
cd /tmp
wget http://download.osgeo.org/geos/geos-3.4.2.tar.bz2
tar xjf geos-3.4.2.tar.bz2
cd geos-3.4.2
./configure
sudo make -j 4
sudo make install

git clone https://github.com/OSGeo/gdal.git /srv/gdal
cd /srv/gdal/gdal
./configure --with-python
./mkbindist.sh -dev $version linux
sed -i 's/#!\/bin\/sh/#!\/bin\/bash/'  mkbindist.sh
version=$(<VERSION)
./mkbindist.sh -dev $version linux
cp gdal-${version}-linux-bin.tar.gz /vagrant
# aws s3 cp gdal-2.1.0-linux-bin.tar.gz s3://django-osgeo-importer --profile=prominentedge
