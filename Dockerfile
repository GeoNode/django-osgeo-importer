FROM python:2.7

ENV TMP /tmp
ENV GDAL_VERSION 2.1.3

RUN mkdir /app
WORKDIR /app

### Build and install GDAL
RUN set -ex \
    && wget -qP $TMP http://download.osgeo.org/gdal/$GDAL_VERSION/gdal-$GDAL_VERSION.tar.gz \
    && tar -xf $TMP/gdal-$GDAL_VERSION.tar.gz -C $TMP \
    && cd $TMP/gdal-$GDAL_VERSION \
    && ./configure --with-python \
    && make \
    && make install \
    && ldconfig \
    && cd .. \
    && rm -r gdal* \
    && pip install --no-cache-dir GDAL==$GDAL_VERSION

# Install misc libs
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libgeos-dev \
        libjpeg-dev \
        libxml2-dev \
        libproj-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements.txt
COPY requirements.dev.txt requirements.dev.txt
RUN pip install -r requirements.txt
RUN pip install -r requirements.dev.txt

COPY scripts/epsg_extra /usr/local/lib/python2.7/site-packages/pyproj/data/

RUN mkdir -p -m 777 importer-test-files
RUN aws --no-sign-request s3 sync s3://mapstory-data/importer-test-files/ importer-test-files

COPY . .

RUN python manage.py migrate --noinput

CMD [ "python", "./manage.py", "runserver", "0.0.0.0:8000" ]
