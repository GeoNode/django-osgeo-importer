[![Build Status](https://travis-ci.org/GeoNode/django-osgeo-importer.svg?branch=master)](https://travis-ci.org/GeoNode/django-osgeo-importer)
[![Coverage Status](https://coveralls.io/repos/github/GeoNode/django-osgeo-importer/badge.svg?branch=master)](https://coveralls.io/github/GeoNode/django-osgeo-importer?branch=master)

# django-osgeo-importer
osgeo-importer is a Django application that helps you create custom pipelines for uploading geospatial data.  It's goal is to provide a highly extensible, easily testable and reusable framework for importing data into geospatial applications.


## Installation
`pip install git+https://github.com/GeoNode/django-osgeo-importer.git`


## Settings
* `OSGEO_IMPORTER`: The default Importer to use for uploads.
* `OSGEO_INSPECTOR`: The default Inspector to use for uploads.
* `OSGEO_IMPORTER_GEONODE_ENABLED`: If `True`, the osgeo_importer will expose the [GeoNode-flavored](osgeo_importer/geonode_apis.py) APIs vs a vanilla API.
* `IMPORT_HANDLERS`: A list of handlers that each layer is passed through during the import process. Changing this setting allows complete customization – even replacement – of the osgeo-importer import process.

## Running test cases.

Requires [Vagrant](http://vagrantup.com).

```shell
vagrant up
vagrant ssh
python /vagrant/manage.py test osgeo_importer
```

## Frontend

The Django app comes with an Angular-based wizard. If you are just using the
Django app, you do not need to do anything special for the frontend and you can
ignore this section.

However, if you are interested in making changes to the frontend, the frontend
dependencies can be managed using `npm` via a `package.json` file, and the
most common tasks are automated via `make` (using a `Makefile`).

For example, if you want to regenerate the static files for the frontend, then
you can change to the directory `osgeo_importer/static/osgeo_importer` and then
just run `make`.

If you want to upgrade versions of anything, you can edit `package.json` to
specify the desired updates, then run `make clean; make`. If any files are
changed, it is up to you to commit them into the git repo if you want them to
be used "out of the box."

To watch files for changes and run the tests, you can run
`./node_modules/karma/bin/karma start`.


## Concepts
The import process starts with an extensible Angular-based wizard that allows the user to upload a file
and provide configuration options.  Once the user starts the import, the configuration options are passed to an
Importer which will read the incoming geospatial data and load it into a target data store (ie: PostGIS).  Once
the data has been successfully loaded, the Importer will execute a series of "handlers" that process the data
for use in your application.


### Inspectors
Inspectors are Python classes that are responsible for reading incoming geospatial datasets.  Custom inspectors should
 implement the methods exposed in the `InspectorMixin`.

##### GDALInspector
Uses the GDAL library to read geospatial data.

GDALInspector settings:

`IMPORT_CSV_X_FIELDS` : List of fields passed in as the X_POSSIBLE_NAMES open options to the CSV Driver.
`IMPORT_CSV_Y_FIELDS` : List of fields passed in as the Y_POSSIBLE_NAMES open options to the CSV Driver.
`IMPORT_CSV_GEOM_FIELDS` : List of fields passed in as the GEOM_POSSIBLE_NAMES open options to the CSV Driver.

##### OGRInspector
Uses the OGR library to read geospatial data.

### Handlers
Handlers are Python classes which are executed in order by the Importer after the import process has succeeded.  The response from
the Importer's `import` method is sent to each handler which includes the configuration options provided at upload.


### Importers
Importers are Python classes that are responsible for opening incoming geospatial datasets (using one or many inspectors) and
copying features to a target location - typically a PostGIS database.
