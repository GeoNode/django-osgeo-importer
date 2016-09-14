import os
import json
import logging
from django.http import HttpResponse
from django.views.generic import FormView, ListView, TemplateView
from django.core.urlresolvers import reverse_lazy
from .forms import UploadFileForm
from .models import UploadedData, UploadLayer, DEFAULT_LAYER_CONFIGURATION
from .importers import OSGEO_IMPORTER
from .inspectors import OSGEO_INSPECTOR
from .utils import import_string
from django.conf import settings

OSGEO_INSPECTOR = import_string(OSGEO_INSPECTOR)
OSGEO_IMPORTER = import_string(OSGEO_IMPORTER)

logger = logging.getLogger(__name__)


class JSONResponseMixin(object):
    """
    A mixin that can be used to render a JSON response.
    """
    def render_to_json_response(self, context, **response_kwargs):
        """
        Returns a JSON response, transforming 'context' to make the payload.
        """
        return HttpResponse(
            self.convert_context_to_json(context),
            content_type='application/json',
            **response_kwargs
        )

    def convert_context_to_json(self, context):
        """
        Convert the context dictionary into a JSON object
        """
        # Note: This is *EXTREMELY* naive; in reality, you'll need
        # to do much more complex handling to ensure that arbitrary
        # objects -- such as Django model instances or querysets
        # -- can be serialized as JSON.
        return json.dumps(context)


class JSONView(JSONResponseMixin, TemplateView):
    def render_to_response(self, context, **response_kwargs):
        return self.render_to_json_response(context, **response_kwargs)


class UploadListView(ListView):
    model = UploadedData
    template_name = 'osgeo_importer/uploads-list.html'
    queryset = UploadedData.objects.all()


class ImportHelper(object):
    """
    Import Helpers
    """

    inspector = OSGEO_INSPECTOR

    def get_fields(self, path):
        """
        Returns a list of field names and types.
        """
        with self.inspector(path) as opened_file:
            return opened_file.describe_fields()

    def get_file_type(self, path):
        with self.inspector(path) as opened_file:
            return opened_file.file_type()


class FileAddView(FormView, ImportHelper, JSONResponseMixin):
    form_class = UploadFileForm
    success_url = reverse_lazy('uploads-list')
    template_name = 'osgeo_importer/new.html'
    json = False

    def form_valid(self, form):
        upload = UploadedData(user=self.request.user)
        upload.save()

        # Create Upload Directory based on Upload PK
        outpath = os.path.join('/uploads',str(upload.pk))
        outdir = os.path.join(settings.MEDIA_ROOT,outpath)
        
        # Move all files to uploads directory using upload pk
        # Must be done for all files before saving upfile for validation
        for each in form.cleaned_data['files']:
            shutil.move(each.path, os.path.join(outpath,each.name))

        # Loop through and create uploadfiles and uploadlayers
        for each in form.cleaned_data['files']:
            upfile = UploadFile(upload=upload)
            upfile.file.name = os.path.join(outpath,each.name)
            upfile.save()

            upfile_base, upfile_ext = os.path.splitext(each.name)
            if upfile_ext.lower() not in ['.xml','.sld','.prj','.dbf','shx']:
                description = self.get_fields(upload_file.file.path)
                for layer in description:
                    configuration_options = DEFAULT_LAYER_CONFIGURATION.copy()
                    configuration_options.update({'index': layer.get('index')})
                    upload.uploadlayer_set.add(UploadLayer(name=layer.get('name'),
                                                        fields=layer.get('fields', {}),
                                                        index=layer.get('index'),
                                                        feature_count=layer.get('feature_count',None),
                                                        configuration_options=configuration_options))
        upload.complete = True
        upload.state = 'UPLOADED'

        if self.json:
            return self.render_to_json_response({'state': upload.state, 'id': upload.id})

        return super(FileAddView, self).form_valid(form)

    def render_to_response(self, context, **response_kwargs):

        if self.json:
            context = {'errors': context['form'].errors}
            return self.render_to_json_response(context, **response_kwargs)

        return super(FileAddView, self).render_to_response(context, **response_kwargs)
