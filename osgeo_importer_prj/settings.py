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
from geonode.settings import *
#
# General Django development settings
#

SITENAME = 'osgeo_importer_prj'

# Defines the directory that contains the settings file as the LOCAL_ROOT
# It is used for relative settings elsewhere.
LOCAL_ROOT = os.path.abspath(os.path.dirname(__file__))

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
TEMPLATE_DIRS = (
    os.path.join(LOCAL_ROOT, "templates"),
) + TEMPLATE_DIRS

# Location of url mappings
ROOT_URLCONF = 'osgeo_importer_prj.urls'

# Location of locale files
LOCALE_PATHS = (
    os.path.join(LOCAL_ROOT, 'locale'),
    ) + LOCALE_PATHS

INSTALLED_APPS = INSTALLED_APPS + ("osgeo_importer",)

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
LOGGING['loggers']['osgeo_importer'] = {"handlers": ["console"], "level": "DEBUG"}
DATABASE_ROUTERS = ['osgeo_importer_prj.dbrouters.DefaultOnlyMigrations']
