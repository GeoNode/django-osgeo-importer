[![Build Status](https://travis-ci.org/ProminentEdge/django-osgeo-importer.svg?branch=master)](https://travis-ci.org/ProminentEdge/django-osgeo-importer)

# django-osgeo-importer
osgeo-importer is a Django application that helps you create custom pipelines for uploading geospatial data.  It's goal is to provide a highly extensible, easily testable and reusable framework for importing data into geospatial applications.


## Installation
`pip install git+https://github.com/ProminentEdge/django-osgeo-importer.git`


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

## Concepts
The import process starts with an extensible Angular-based wizard that allows the user to upload a file
and provide configuration options.  Once the user starts the import, the configuration options are passed to an
Importer which will read the incoming geospatial data and load it into a target data store (ie: PostGIS).  Once
the data has been successfully loaded, the Importer will execute a series of "handlers" that process the data
for use in your application.


### Inspectors
Inspectors are Python classes that are responsible for reading incoming geospatial datasets.  Custom inspectors should
 implement the methods exposed in the `InspectorMixin`.

### Importers
Importers are Python classes that are responsible for opening incoming geospatial datasets (using one or many inspectors) and
copying features to a target location - typically a PostGIS database.

#### GDALInspector
Uses the GDAL library to read geospatial data.

GDALInspector settings:

`IMPORT_CSV_X_FIELDS` : List of fields passed in as the X_POSSIBLE_NAMES open options to the CSV Driver.
`IMPORT_CSV_Y_FIELDS` : List of fields passed in as the Y_POSSIBLE_NAMES open options to the CSV Driver.
`IMPORT_CSV_GEOM_FIELDS` : List of fields passed in as the GEOM_POSSIBLE_NAMES open options to the CSV Driver.

#### OGRInspector
Uses the OGR library to read geospatial data.

### Handlers
Handlers are Python classes which are executed in order by the Importer after the import process has succeeded.  The response from
the Importer's `import` method is sent to each handler which includes the configuration options provided at upload.


