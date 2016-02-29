import os
from .api import *
from geonode.api.api import ProfileResource
from geonode.geoserver.helpers import ogc_server_settings
from tastypie.fields import ForeignKey


class UploadedDataResource(UploadedDataResource):
    """
    API for accessing UploadedData.
    """

    user = ForeignKey(ProfileResource, 'user')


class UploadedLayerResource(UploadedLayerResource):
    def clean_configuration_options(self, request, configuration_options):
        if configuration_options.get('geoserver_store'):
            store = configuration_options.get('geoserver_store')
            if store.get('type', str).lower() == 'geogig':
                store.setdefault('branch', 'master')
                store.setdefault('create', 'true')
                store.setdefault('name', '{0}-storylayers'.format(request.user.username))
                store['geogig_repository'] = os.path.join(ogc_server_settings.GEOGIG_DATASTORE_DIR,
                                                          store.get('name'))