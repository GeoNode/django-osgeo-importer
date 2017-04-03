import json
import logging

from django.conf.urls import url
from django.contrib.auth import get_user_model
from tastypie import http
from tastypie.authentication import SessionAuthentication
from tastypie.authorization import Authorization
from tastypie.bundle import Bundle
from tastypie.constants import ALL, ALL_WITH_RELATIONS
from tastypie.exceptions import ImmediateHttpResponse
from tastypie.fields import DictField, ListField, CharField, ToManyField, ForeignKey
from tastypie.resources import ModelResource
from tastypie.utils import trailing_slash

from osgeo_importer.utils import import_all_layers

from .models import UploadedData, UploadLayer, UploadFile
from .tasks import import_object


logger = logging.getLogger(__name__)


class UserResource(ModelResource):

    class Meta:
        queryset = get_user_model().objects.all()
        fields = ['username', 'first_name', 'last_name']


class UploadedLayerResource(ModelResource):
    """
    API for accessing UploadedData.
    """

    geonode_layer = DictField(attribute='layer_data', readonly=True, null=True)
    configuration_options = DictField(attribute='configuration_options', null=True)
    fields = ListField(attribute='fields')
    status = CharField(attribute='status', readonly=True, null=True)
    file_type = CharField(attribute='file_type', readonly=True)
    file_name = CharField(attribute='file_name', readonly=True)
    layer_name = CharField(attribute='layer_name', readonly=True)

    class Meta:
        queryset = UploadLayer.objects.all()
        resource_name = 'data-layers'
        allowed_methods = ['get']
        filtering = {'id': ALL}
        authentication = SessionAuthentication()

    def get_object_list(self, request):
        """
        Filters the list view by the current user.
        """
        return super(UploadedLayerResource, self).get_object_list(request).filter(upload__user=request.user.id)

    def clean_configuration_options(self, request, obj, configuration_options):
        return configuration_options

    def import_layer(self, request, pk=None, **kwargs):
        """Imports a layer
        """
        self.method_check(request, allowed=['post'])
        # pk will be parsed from the url as a string but is an integer internally
        if pk is not None:
            pk = int(pk)

        bundle = Bundle(request=request)

        try:
            obj = self.obj_get(bundle, pk=pk)
        except UploadLayer.DoesNotExist:
            raise ImmediateHttpResponse(response=http.HttpNotFound())

        configuration_options = request.POST.get('configurationOptions')

        if 'application/json' in request.META.get('CONTENT_TYPE', ''):
            configuration_options = json.loads(request.body)

        if isinstance(configuration_options, list) and len(configuration_options) == 1:
            configuration_options = configuration_options[0]

        if isinstance(configuration_options, dict):
            configuration_options.update({'upload_layer_id': int(pk)})
            self.clean_configuration_options(request, obj, configuration_options)
            obj.configuration_options = configuration_options
            obj.save()

        if not configuration_options:
            raise ImmediateHttpResponse(response=http.HttpBadRequest('Configuration options missing.'))

        uploaded_file = obj.upload_file

        import_result = import_object.delay(
            uploaded_file.id,
            configuration_options=configuration_options,
            request_cookies=request.COOKIES,
            request_user=request.user
        )

        task_id = getattr(import_result, 'id', None)
        # The task id will be useless if no backend is configured or a non-persistent backend is used.
        return self.create_response(request, {'task': task_id})

    def prepend_urls(self):
        return [url(r"^(?P<resource_name>{0})/(?P<pk>\d+)/configure{1}$".format(self._meta.resource_name,
                    trailing_slash()), self.wrap_view('import_layer'), name="importer_configure"),
                ]


class UserOwnsObjectAuthorization(Authorization):

    # Optional but useful for advanced limiting, such as per user.
    def apply_limits(self, request, object_list):

        if request and hasattr(request, 'user'):
            if request.user.is_superuser:
                return object_list

            return object_list.filter(user=request.user)

        return object_list.none()


class UploadedDataResource(ModelResource):
    """
    API for accessing UploadedData.
    """

    user = ForeignKey(UserResource, 'user')
    file_size = CharField(attribute='filesize', readonly=True, null=True)
    layers = ToManyField(UploadedLayerResource, 'uploadlayer_set', full=True)
    file_url = CharField(attribute='file_url', readonly=True, null=True)

    class Meta:
        queryset = UploadedData.objects.all()
        resource_name = 'data'
        allowed_methods = ['get', 'delete']
        authorization = UserOwnsObjectAuthorization()
        authentication = SessionAuthentication()
        filtering = {'user': ALL_WITH_RELATIONS}

    def get_object_list(self, request):
        """
        Filters the list view by the current user.
        """
        queryset = super(UploadedDataResource, self).get_object_list(request)

        if not request.user.is_superuser:
            return queryset.filter(user=request.user)

        return queryset

    def import_all_layers(self, request, api_name=None, resource_name=None, pk=None):
        ud = UploadedData.objects.get(id=pk)
        n_layers_imported = import_all_layers(ud, owner=request.user)
        resp = self.create_response(request, {'layer_count': n_layers_imported})
        return resp

    def prepend_urls(self):
        pu = super(UploadedDataResource, self).prepend_urls()
        pu.extend([
            url(
                r'^(?P<resource_name>{0})/(?P<pk>\w[\w/-]*)/import_all_layers{1}$'
                .format(self._meta.resource_name, trailing_slash()),
                self.wrap_view('import_all_layers'),
                name='import_all_data'
            )
        ])
        return pu


class MultipartResource(object):

    def deserialize(self, request, data, format=None):

        if not format:
            format = request.META.get('CONTENT_TYPE', 'application/json')

        if format == 'application/x-www-form-urlencoded':
            return request.POST

        if format.startswith('multipart/form-data'):
            multipart_data = request.POST.copy()
            multipart_data.update(request.FILES)
            return multipart_data

        return super(MultipartResource, self).deserialize(request, data, format)

    def put_detail(self, request, **kwargs):
        if request.META.get('CONTENT_TYPE', '').startswith('multipart/form-data') and not hasattr(request, '_body'):
            request._body = ''
        return super(MultipartResource, self).put_detail(request, **kwargs)

    def patch_detail(self, request, **kwargs):
        if request.META.get('CONTENT_TYPE', '').startswith('multipart/form-data') and not hasattr(request, '_body'):
            request._body = ''
        return super(MultipartResource, self).patch_detail(request, **kwargs)


class UploadedFileResource(MultipartResource, ModelResource):

    class Meta:
        queryset = UploadFile.objects.all()
        authentication = SessionAuthentication()
        allowed_methods = ['put']
        resource_name = 'file-upload'
