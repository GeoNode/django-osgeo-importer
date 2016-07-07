from django.conf.urls import patterns, url, include
from django.conf import settings
from django.contrib.auth.decorators import login_required
from .views import FileAddView, UploadListView, MultiUpload
from tastypie.api import Api
from .api import UploadedDataResource, UploadedLayerResource, UploadedFileResource  # noqa

if getattr(settings, 'OSGEO_IMPORTER_GEONODE_ENABLED', False):
    from .geonode_apis import UploadedDataResource, UploadedLayerResource, UploadedFileResource  # noqa

importer_api = Api(api_name='importer-api')
importer_api.register(UploadedDataResource())
importer_api.register(UploadedLayerResource())
importer_api.register(UploadedFileResource())

urlpatterns = patterns("",
                       url(r'^uploads/new$', login_required(FileAddView.as_view()), name='uploads-new'),
                       url(r'^uploads/new-multi-json$', login_required(MultiUpload.as_view(json=True)),
                           name='uploads-multi-json'),
                       url(r'^uploads/new/json$', login_required(FileAddView.as_view(json=True)),
                           name='uploads-new-json'),
                       url(r'^uploads/?$', login_required(UploadListView.as_view()), name='uploads-list'),
                       url(r'', include(importer_api.urls)),)
