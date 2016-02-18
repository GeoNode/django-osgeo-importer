[![Build Status](https://travis-ci.org/terranodo/django-osgeo-importer.svg?branch=master)](https://travis-ci.org/terranodo/django-osgeo-importer)

# django-osgeo-uploader
An extensible module for importing geospatial data into GeoNode-backed applications.

## Settings ##

`IMPORT_CSV_X_FIELDS` : List of fields passed in as the X_POSSIBLE_NAMES open options to the CSV Driver.
`IMPORT_CSV_Y_FIELDS` : List of fields passed in as the Y_POSSIBLE_NAMES open options to the CSV Driver.
`IMPORT_CSV_GEOM_FIELDS` : List of fields passed in as the GEOM_POSSIBLE_NAMES open options to the CSV Driver.
`IMPORT_HANDLERS`: List of handlers that each layer is passed through during the import process.
`IMPORTER_VALID_EXTENSIONS`: List of valid file type extensions.

