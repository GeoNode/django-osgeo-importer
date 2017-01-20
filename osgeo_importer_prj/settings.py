# -*- coding: utf-8 -*-
#########################################################################
#
# Copyright (C) 2012 OpenPlans
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################

# Django settings for the GeoNode project.
import os
import pyproj
from geonode.settings import *
#
# General Django development settings
#
SITENAME = 'osgeo_importer_prj'

IMPORT_HANDLERS = [
    # If GeoServer handlers are enabled, you must have an instance of geoserver running.
    # Warning: the order of the handlers here matters.
    'osgeo_importer.handlers.FieldConverterHandler',
    'osgeo_importer.handlers.geoserver.GeoserverPublishHandler',
    'osgeo_importer.handlers.geoserver.GeoserverPublishCoverageHandler',
    'osgeo_importer.handlers.geoserver.GeoServerTimeHandler',
    'osgeo_importer.handlers.geoserver.GeoWebCacheHandler',
    'osgeo_importer.handlers.geoserver.GeoServerBoundsHandler',
    'osgeo_importer.handlers.geoserver.GenericSLDHandler',
    'osgeo_importer.handlers.geonode.GeoNodePublishHandler',
#     'osgeo_importer.handlers.mapproxy.publish_handler.MapProxyGPKGTilePublishHandler',
    'osgeo_importer.handlers.geoserver.GeoServerStyleHandler',
    'osgeo_importer.handlers.geonode.GeoNodeMetadataHandler'
]

# Defines the directory that contains the settings file as the LOCAL_ROOT
# It is used for relative settings elsewhere.
LOCAL_ROOT = os.path.abspath(os.path.dirname(__file__))

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

WSGI_APPLICATION = "osgeo_importer_prj.wsgi.application"

TEST_RUNNER = 'django.test.runner.DiscoverRunner'

# Load more settings from a file called local_settings.py if it exists
try:
    from local_settings import *
except ImportError:
    pass

# Additional directories which hold static files
STATICFILES_DIRS.append(
    os.path.join(LOCAL_ROOT, "static"),
)

# Note that Django automatically includes the "templates" dir in all the
# INSTALLED_APPS, se there is no need to add maps/templates or admin/templates
TEMPLATES[0]['DIRS'].insert(0, os.path.join(LOCAL_ROOT, "templates"))

# Location of url mappings
ROOT_URLCONF = 'osgeo_importer_prj.urls'

# Location of locale files
LOCALE_PATHS = (
    os.path.join(LOCAL_ROOT, 'locale'),
    ) + LOCALE_PATHS


INSTALLED_APPS = INSTALLED_APPS + ("osgeo_importer",)
# # Remove 'geonode.geoserver', useful for experimenting with a geoserver-less configuration.
# INSTALLED_APPS = [ a for a in INSTALLED_APPS if a != 'geonode.geoserver' ]

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(PROJECT_ROOT, 'development.db'),
    },
    # vector datastore for uploads
     'datastore' : {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'osgeo_importer_test',
        'USER' : 'osgeo',
        'PASSWORD' : 'osgeo',
        'HOST' : 'localhost',
        'PORT' : '5432',
     }
}

OSGEO_DATASTORE = 'datastore'
OSGEO_IMPORTER_GEONODE_ENABLED = True
OSGEO_IMPORTER_VALID_EXTENSIONS = [
    'shp', 'shx', 'prj', 'dbf', 'kml', 'geojson', 'json', 'tif', 'tiff',
    'gpkg', 'csv', 'zip', 'xml', 'sld'
]
LOGGING['loggers']['osgeo_importer'] = {"handlers": ["console"], "level": "DEBUG"}
DATABASE_ROUTERS = ['osgeo_importer_prj.dbrouters.DefaultOnlyMigrations']

# # === MapProxy settings
# # This is the location to place additional configuration files for mapproxy to work from.
# # Currently it is only to allow tiles from gpkg files to be served.
MAPPROXY_CONFIG_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), 'mapproxy_confdir'))
# Name of the mapproxy config file to create for tile gpkg files.
MAPPROXY_CONFIG_FILENAME = 'geonode.yaml'
# This is the base URL for MapProxy WMS services
# URLs will look like this: /geonode/tms/1.0.0/<layer_name>/<grid_name>/0/0/0.png and a <grid_name> will be
#    set as '<layer_name>_<projection_id>' (by conf_from_geopackage()).
MAPPROXY_SERVER_LOCATION = 'http://localhost:8088/geonode/tms/1.0.0/{layer_name}/{grid_name}/'

PROJECTION_DIRECTORY = os.path.join(os.path.dirname(pyproj.__file__), 'data/')
