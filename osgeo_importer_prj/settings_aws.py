from osgeo_importer_prj.settings import *

PROJECT_ROOT = os.path.abspath(os.path.dirname(__file__))

SITEURL = "http://35.167.158.17"


try:
    CELERY_IMPORTS = CELERY_IMPORTS + ('osgeo_importer.tasks',)
except:
    CELERY_IMPORTS = ('osgeo_importer.tasks',)

LOCKDOWN_GEONODE = True

SECRET_KEY = os.environ.get('SECRET_KEY', 'not so secret')

BROKER_URL = "amqp://guest@localhost:5672"
CELERY_ALWAYS_EAGER = False
IMPORT_TASK_SOFT_TIME_LIMIT = 90

DATABASES = {
     'default' : {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'osgeo_importer_prj_app',
        'USER' : 'osgeo_importer_prj',
        'PASSWORD' : 'osgeo_importer_prj',
        'HOST' : 'localhost',
        'PORT' : '5432',
     },
     'osgeo_importer_prj' : {
        'ENGINE': 'django.contrib.gis.db.backends.postgis',
        'NAME': 'osgeo_importer_prj',
        'USER' : 'osgeo_importer_prj',
        'PASSWORD' : 'osgeo_importer_prj',
        'HOST' : 'localhost',
        'PORT' : '5432',
     }
}

# OGC (WMS/WFS/WCS) Server Settings
OGC_SERVER = {
    'default' : {
        'BACKEND' : 'geonode.geoserver',
        'LOCATION' : 'http://localhost:8080/geoserver/',
        'LOGIN_ENDPOINT': 'j_spring_oauth2_geonode_login',
        'LOGOUT_ENDPOINT': 'j_spring_oauth2_geonode_logout',
        'PUBLIC_LOCATION' : 'http://35.167.158.17/geoserver/',
        'USER' : 'admin',
        'PASSWORD' : 'geoserver',
        'MAPFISH_PRINT_ENABLED' : True,
        'PRINT_NG_ENABLED' : True,
        'GEONODE_SECURITY_ENABLED' : True,
        'GEOGIG_ENABLED' : False,
        'WMST_ENABLED' : False,
        'BACKEND_WRITE_ENABLED': True,
        'WPS_ENABLED' : False,
        'LOG_FILE': '%s/geoserver/data/logs/geoserver.log' % os.path.abspath(os.path.join(PROJECT_ROOT, os.pardir)),
        # Set to name of database in DATABASES dictionary to enable
        'DATASTORE': 'osgeo_importer_prj',  # 'datastore',
    }
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d '
                      '%(thread)d %(message)s'
        },
        'simple': {
            'format': '%(message)s',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse'
        }
    },
    'handlers': {
        'null': {
            'level': 'ERROR',
            'class': 'django.utils.log.NullHandler',
        },
        'console': {
            'level': 'INFO',
            'class': 'logging.StreamHandler',
            'formatter': 'simple'
        },
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': '/var/log/importer/importer.log',
        },
        'mail_admins': {
            'level': 'ERROR', 'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler',
        }
    },
    "loggers": {
        "django": {
            "handlers": ["console"], "level": "ERROR", },
        "geonode": {
            "handlers": ["console"], "level": "ERROR", },
        "gsconfig.catalog": {
            "handlers": ["console"], "level": "ERROR", },
        "owslib": {
            "handlers": ["console"], "level": "ERROR", },
        "pycsw": {
            "handlers": ["console"], "level": "ERROR", },
        "osgeo_importer": {
            "handlers": ["file", "console"], "level": "INFO", },
    },
}

CATALOGUE = {
    'default': {
        'ENGINE': 'geonode.catalogue.backends.pycsw_local',
        'URL': '%scatalogue/csw' % SITEURL,
    }
}
OSGEO_DATASTORE = 'osgeo_importer_prj'
MEDIA_ROOT = "/var/www/osgeo_importer_prj/uploaded"
STATIC_ROOT = "/var/www/osgeo_importer_prj/static"
