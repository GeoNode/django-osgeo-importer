FROM ubuntu:14.04

WORKDIR /django-osgeo-uploader

ENV DEBIAN_FRONTEND=noninteractive

ADD packages.txt /django-osgeo-uploader/

RUN \
  apt-get update -qq && \
  apt-get upgrade -yqq && \
  apt-get install -yqq wget software-properties-common && \
  add-apt-repository ppa:ubuntugis/ubuntugis-unstable -y && \
  apt-get update -qq && \
  xargs apt-get install -y --no-install-recommends --force-yes <packages.txt

ENV GS_VERSION=2.8.x
ADD downloads/gdal-2.1.0-linux-bin.tar.gz /django-osgeo-uploader/
ADD downloads/jetty-runner-8.1.8.v20121106.jar /django-osgeo-uploader/gs/
ADD downloads/geoserver-${GS_VERSION}-latest-war.zip /django-osgeo-uploader/gs/
ADD downloads/geoserver.war /django-osgeo-uploader/gs/

ENV PATH=/usr/local/lib/gdal/bin:$PATH
ENV GDAL_DATA=/usr/local/lib/gdal/share/gdal/
RUN \
  chmod +x gs/jetty-runner-8.1.8.v20121106.jar && \
  chmod +x gs/geoserver-${GS_VERSION}-latest-war.zip && \
  mv gdal-2.1.0-linux-bin /usr/local/lib/gdal && \
  touch /usr/lib/python2.7/dist-packages/gdal.pth && \
  echo '/usr/local/lib/gdal/lib/python2.7/site-packages' > /usr/lib/python2.7/dist-packages/gdal.pth && \
  echo '/usr/local/lib/gdal/lib/' >> /etc/ld.so.conf && \
  ln -s /usr/lib/libproj.so.0 /usr/lib/libproj.so && \
  ldconfig


ADD requirements.txt /django-osgeo-uploader/
ADD setup.py /django-osgeo-uploader/
ADD setup.cfg /django-osgeo-uploader/

RUN \
  pip install psycopg2 && \
  pip install -r requirements.txt && \
  pip install awscli

ENV DJANGO_SETTINGS_MODULE=osgeo_importer_prj.settings

ADD osgeo_importer /django-osgeo-uploader/osgeo_importer
ADD osgeo_importer_prj /django-osgeo-uploader/osgeo_importer_prj
ADD scripts /django-osgeo-uploader/scripts
ADD manage.py /django-osgeo-uploader/
ADD setup.py /django-osgeo-uploader/
ADD setup.cfg /django-osgeo-uploader/
ADD README.md /django-osgeo-uploader/

RUN pip install -e .

ADD downloads/importer-test-files /django-osgeo-uploader/importer-test-files

CMD /bin/bash -c "service postgresql start; scripts/before_script.sh; /bin/bash"

EXPOSE 80
EXPOSE 8080
