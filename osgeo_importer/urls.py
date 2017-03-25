from django.conf import settings
from django.conf.urls import patterns, url, include
from django.contrib.auth.decorators import login_required
from tastypie.api import Api

from osgeo_importer.views import OneShotImportDemoView, OneShotFileUploadView, UploadDataImportStatusView, BulkImport

from .api import UploadedDataResource, UploadedLayerResource, UploadedFileResource  # noqa
from .views import FileAddView, UploadListView


if getattr(settings, 'OSGEO_IMPORTER_GEONODE_ENABLED', False):
    from .geonode_apis import UploadedDataResource, UploadedLayerResource, UploadedFileResource  # noqa

importer_api = Api(api_name='importer-api')
importer_api.register(UploadedDataResource())
importer_api.register(UploadedLayerResource())
importer_api.register(UploadedFileResource())

urlpatterns = patterns("",
                       url(r'^uploads/new$', login_required(FileAddView.as_view()), name='uploads-new'),
                       url(r'^uploads/new/json$', login_required(FileAddView.as_view(json=True)),
                           name='uploads-new-json'),
                       url(r'^uploads/?$', login_required(UploadListView.as_view()), name='uploads-list'),
                       url(r'^bulk-import/?$', login_required(BulkImport.as_view())),
                       url(r'^one-shot-demo/?$', login_required(OneShotImportDemoView.as_view())),
                       url(r'^upload-data-import-status/(\d+)/?$', UploadDataImportStatusView.as_view()),
                       url(r'^one-shot-demo_file-upload/?$', OneShotFileUploadView.as_view()),
                       url(r'', include(importer_api.urls)),)
