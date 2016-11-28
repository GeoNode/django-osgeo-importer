import json
import logging
from django.http import HttpResponse
from django.views.generic import FormView, ListView, TemplateView
from django.core.urlresolvers import reverse_lazy
from .forms import UploadFileForm
from .models import UploadedData, UploadFile
from .importers import OSGEO_IMPORTER, VALID_EXTENSIONS
from .inspectors import OSGEO_INSPECTOR
from .utils import import_string, ImportHelper

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


class FileAddView(ImportHelper, FormView, JSONResponseMixin):
    form_class = UploadFileForm
    success_url = reverse_lazy('uploads-list')
    template_name = 'osgeo_importer/new.html'
    json = False

    def form_valid(self, form):
        upload = self.upload(form.cleaned_data['file'], self.request.user)
        files = [f for f in form.cleaned_data['file']]
        self.configure_upload(upload, files)

        if self.json:
            return self.render_to_json_response({'state': upload.state, 'id': upload.id,
                                                 'count': UploadFile.objects.filter(upload=upload.id).count()})

        return super(FileAddView, self).form_valid(form)

    def render_to_response(self, context, **response_kwargs):

        # grab list of valid importer extensions for use in templates
        context["VALID_EXTENSIONS"] = ", ".join(VALID_EXTENSIONS)

        if self.json:
            context = {'errors': context['form'].errors}
            return self.render_to_json_response(context, **response_kwargs)

        return super(FileAddView, self).render_to_response(context, **response_kwargs)
