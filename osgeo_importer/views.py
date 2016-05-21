import json
import os
import shutil
from zipfile import ZipFile
from django.http import HttpResponse, Http404
from django.views.generic import View, FormView, ListView, TemplateView
from django.core.urlresolvers import reverse_lazy
from django.core.files.storage import FileSystemStorage
from .forms import UploadFileForm
from .models import UploadedData, UploadLayer, UploadFile, DEFAULT_LAYER_CONFIGURATION
from .importers import OSGEO_IMPORTER
from .inspectors import OSGEO_INSPECTOR
from .utils import import_string, CheckFile
from .tasks import import_object

import logging
log = logging.getLogger(__name__)

OSGEO_INSPECTOR = import_string(OSGEO_INSPECTOR)
OSGEO_IMPORTER = import_string(OSGEO_IMPORTER)
MEDIA_ROOT = FileSystemStorage().location


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
        return json.dumps(context, default=lambda x: None)


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

    def create_upload_session(self, upload_file):
        """
        Creates an upload session from the file.
        """
        upload = UploadedData.objects.create(user=self.request.user, state='UPLOADED', complete=True)
        upload_file.upload = upload
        upload_file.save()
        upload.size = upload_file.file.size
        upload.name = upload_file.name
        upload.file_type = self.get_file_type(upload_file.file.path)
        upload.save()

        description = self.get_fields(upload_file.file.path)

        for layer in description:
            configuration_options = DEFAULT_LAYER_CONFIGURATION.copy()
            configuration_options.update({'index': layer.get('index')})
            upload.uploadlayer_set.add(UploadLayer(name=layer.get('name'),
                                                   upload_file=upload_file,
                                                   fields=layer.get('fields', {}),
                                                   index=layer.get('index'),
                                                   feature_count=layer.get('feature_count'),
                                                   configuration_options=configuration_options))
        upload.save()
        return upload

    def form_valid(self, form):

        form.save(commit=True)
        upload = self.create_upload_session(form.instance)

        if self.json:
            return self.render_to_json_response({'state': upload.state, 'id': upload.id})

        return super(FileAddView, self).form_valid(form)

    def render_to_response(self, context, **response_kwargs):

        if self.json:
            context = {'errors': context['form'].errors}
            return self.render_to_json_response(context, **response_kwargs)

        return super(FileAddView, self).render_to_response(context, **response_kwargs)


def configure_layers(configs, upload_id=None):
    log.debug(configs)
    log.debug(len(configs))
    log.debug(type(configs))
    if isinstance(configs, type({})):
        configs = [configs]
    complete = []
    for config in configs:
        log.debug(config)
        upload_id = config.get('upload_id', upload_id)
        file_id = config.get('upload_file_id')
        upload_file_name = config.get('upload_file_name')
        if file_id is None and upload_id is not None and upload_file_name is not None:
            try:
                u = UploadFile.objects.filter(upload_id=upload_id)
                for uf in u:
                    log.debug(uf.name)
                    if uf.name == upload_file_name:
                        file_id = uf.pk
                        break
            except:
                log.exception('Cannot Determine File ID')
                continue
        cfg = config.get('config')
        log.debug(cfg)
        log.debug('upfile id %s', file_id)
        if cfg is not None and file_id is not None:
            lyrs = import_object(file_id, cfg)
            log.debug('lyrs ---------- %s', lyrs)
            for lyr in lyrs:
                complete.append(lyr)

    return complete


class MultiUpload(View, ImportHelper, JSONResponseMixin):
    json = True

    def post(self, request):
        log.debug("File List: %s", request.FILES.getlist('file'))
        if request.FILES is not None:
            upload = UploadedData.objects.create(user=request.user)
            upload.save()
            if upload.pk < 1:
                return Http404
            savedir = os.path.join(MEDIA_ROOT, 'uploads', str(upload.pk))
            # remove any folders with this upload id
            if os.path.exists(savedir):
                shutil.rmtree(savedir)
            os.mkdir(savedir)
            log.debug('Saving Files to %s', savedir)
            req_files = request.FILES.getlist('file')

            # Get Zipfiles
            zipfiles = [file for file in req_files if CheckFile(file).zip]
            log.debug('Zipfiles: %s', zipfiles)
            for z in zipfiles:
                req_files.remove(z)
                with ZipFile(z) as zip:
                    for zipf in zip.namelist():
                        log.debug(zipf)
                        zipfc = CheckFile(zipf)
                        log.debug(zipfc.valid_extension)
                        if not zipfc.valid_extension:
                            log.debug('ignoring %s', zipfc.name)
                            continue
                        with zip.open(zipfc.name) as f:
                            with open(os.path.join(savedir, zipfc.name), 'wb') as outfile:
                                log.debug('copying %s', zipfc.name)
                                shutil.copyfileobj(f, outfile)
            for file in req_files:
                filec = CheckFile(file)
                log.debug("File name: %s", filec.name)
                log.debug("valid %s", filec.valid_extension)
                if filec.valid_extension:
                    with open(os.path.join(savedir, filec.name), 'w') as sf:
                        sf.write(file.read())
                else:
                    log.debug('Skipping Unsupported File: %s', filec.name)
            dirfiles = os.listdir(savedir)
            log.debug('Files copied to %s, %s', savedir, dirfiles)
            for dirfile in dirfiles:
                dirfile = CheckFile(dirfile)
                upfile = UploadFile(upload=upload)
                upfile.file.name = os.path.join(
                    'uploads', str(upload.pk), dirfile.basename)
                upfile.save()

                if dirfile.support:
                    continue
                description = self.get_fields(upfile.file.path)

                for layer in description:
                    configuration_options = DEFAULT_LAYER_CONFIGURATION.copy()
                    configuration_options.update({'index': layer.get('index')})
                    upload.uploadlayer_set.add(
                        UploadLayer(
                            upload_file=upfile,
                            name=layer.get('name'),
                            fields=layer.get(
                                'fields',
                                {}),
                            index=layer.get('index'),
                            feature_count=layer.get('feature_count'),
                            configuration_options=configuration_options))

            upload.state = 'UPLOADED'
            upload.complete = True
            upload.save()

        response = {}

        try:
            count = UploadFile.objects.filter(upload=upload).count()
            uploaded = []
            for uploadedfile in UploadFile.objects.filter(upload=upload):
                uploaded.append({'pk': uploadedfile.pk,
                                 'name': uploadedfile.name,
                                 'ext': CheckFile(uploadedfile.name).ext})
            response['state'] = upload.state
            response['id'] = upload.id
            response['count'] = count
            response['uploaded'] = uploaded
        except:
            log.debug('No Layers Uploaded')

        if request.POST.get('json') is not None:
            log.debug('Processing JSON configuration')
            config = json.loads(request.POST['json'])
            complete_layers = configure_layers(config, upload_id=upload.pk)
            response['layers'] = complete_layers

        if self.json:
            return self.render_to_json_response(response)
        return HttpResponse('<html><body>Woohoo!</body></html>')
