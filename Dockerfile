FROM mapstory/python-gdal

RUN mkdir /app
WORKDIR /app

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

# Override the version of awesome-slugify
# Using HEAD as of 2018-01-09
# The version isn't changed, so it has trouble differentiation from the version in pypy. Thus this manual update.
RUN pip install --no-cache-dir -U git+git://github.com/dimka665/awesome-slugify@a6563949965bcddd976b7b3fb0babf76e3b490f7#egg=awesome-slugify

COPY scripts/epsg_extra /usr/local/lib/python2.7/site-packages/pyproj/data/

RUN mkdir -p -m 777 /app/importer-test-files
RUN aws --no-sign-request s3 sync s3://mapstory-data/importer-test-files/ /app/importer-test-files

COPY . .

RUN python manage.py migrate --noinput

CMD [ "python", "./manage.py", "runserver", "0.0.0.0:8000" ]
