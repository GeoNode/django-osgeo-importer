import json
import logging
import os
import shutil
from tempfile import mkdtemp
import threading
import zipfile

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.urlresolvers import reverse_lazy
from django.http import HttpResponse
from django.http.response import JsonResponse, HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views.generic import FormView, ListView, TemplateView
from django.views.generic.base import View

from osgeo_importer.utils import import_all_layers

from .forms import UploadFileForm
from .importers import VALID_EXTENSIONS
from .inspectors import OSGEO_INSPECTOR
from .models import UploadedData, UploadFile
from .utils import import_string, ImportHelper


OSGEO_IMPORTER = getattr(settings, 'OSGEO_IMPORTER', 'osgeo_importer.importers.OGRImport')
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


class OneShotImportDemoView(TemplateView):
    template_name = 'osgeo_importer/one_shot_demo/one_shot.html'

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return TemplateView.dispatch(self, request, *args, **kwargs)


class UploadDataImportStatusView(View):
    def get(self, request, upload_id):
        ud = UploadedData.objects.prefetch_related('uploadfile_set__uploadlayer_set').get(id=upload_id)

        celery_to_api_status_map = {
            'UNKNOWN': 'working',
            'PENDING': 'working',
            'SUCCESS': 'success',
            'FAILURE': 'error',
            'ERROR': 'error',
        }

        import_status = {
            uf.name: {
                ul.layer_name: celery_to_api_status_map[ul.status] for ul in uf.uploadlayer_set.all()
            } for uf in ud.uploadfile_set.all()
        }

        return JsonResponse(import_status)


class BulkImport(TemplateView):
    template_name = 'osgeo_importer/bulk_import.html'


class OneShotFileUploadView(ImportHelper, View):
    def post(self, request):
        if len(request.FILES) != 1:
            resp = HttpResponse('Sorry, must be one and only one file')
        else:
            file_key = request.FILES.keys()[0]
            file = request.FILES[file_key]
            if file.name.split('.')[-1] != 'zip':
                resp = HttpResponse('Sorry, only a a zip file is allowed')
            else:
                # --- Handling the zip extraction & configure_upload() can be integrated into current upload
                z = zipfile.ZipFile(file)
                owner = request.user
                ud = UploadedData(user=owner, name=file.name)
                ud.save()

                try:
                    tempdir = mkdtemp()
                    z.extractall(tempdir)
                    # Skip .TXT files (like license agreement provided with Digital Globe data)
                    # Skip DS_STORE files (something from OSX)
                    # Not sure if this is valid to be merged back into master.
                    filelist = [
                        open(os.path.join(tempdir, member_name), 'rb') for member_name in z.namelist()
                        if (member_name[-4:].lower() != '.txt' and member_name.lower() != 'ds_store'
                            and member_name[:8].lower() != '__macosx') and member_name[-4:].lower() != '.qgs'
                    ]
                    self.configure_upload(ud, filelist)

                    # --- Put this in another endpoint
                    t = threading.Thread(target=import_all_layers, args=[ud])
                    # We want the program to wait on this thread before shutting down.
                    t.setDaemon(False)
                    t.start()
                finally:
                    shutil.rmtree(tempdir)

                resp = HttpResponseRedirect('/one-shot-demo?uploadDataId={}'.format(ud.id))

        return resp
