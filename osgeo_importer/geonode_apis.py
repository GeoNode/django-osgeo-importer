from .api import (  # noqa: F401
    UserResource,
    UploadedLayerResource,
    UserOwnsObjectAuthorization,
    UploadedDataResource,
    MultipartResource,
    UploadedFileResource
)
from geonode.api.api import ProfileResource
from tastypie.fields import ForeignKey


class UploadedDataResource(UploadedDataResource):  # noqa
    """
    API for accessing UploadedData.
    """

    user = ForeignKey(ProfileResource, 'user')


class UploadedLayerResource(UploadedLayerResource):  # noqa
    def clean_configuration_options(self, request, obj, configuration_options):

        if configuration_options.get('geoserver_store'):
            store = configuration_options.get('geoserver_store')
            if store.get('type', str).lower() == 'geogig':
                store.setdefault('branch', 'master')
                store.setdefault('create', 'true')
                store.setdefault('name', '{0}-layers'.format(request.user.username))
                store['geogig_repository'] = ("geoserver://%s" % store.get('name'))

        if not configuration_options.get('layer_owner'):
            configuration_options['layer_owner'] = obj.upload.user.username

        return configuration_options
