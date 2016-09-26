import os
import json
import logging
import shutil
import collections
from django.http import HttpResponse
from django.views.generic import FormView, ListView, TemplateView
from django.core.urlresolvers import reverse_lazy
from django.utils.text import Truncator
from .forms import UploadFileForm
from .models import UploadedData, UploadLayer, UploadFile, DEFAULT_LAYER_CONFIGURATION
from .importers import OSGEO_IMPORTER
from .inspectors import OSGEO_INSPECTOR
from .utils import import_string, NoDataSourceFound
from django.core.files.storage import FileSystemStorage

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

    def upload(self, data):
        """Use cleaned form data to populate an unsaved upload record.

        Once, each upload was just one file, so all we had to do was attach its
        name and type to the upload, where we could display it. Since multifile
        and geopackage supported were added, the required behavior depends on
        what we find in the upload. That is what this method is for. For
        example, it looks at an upload and tries to come up with a reasonably
        mnemonic name, or else set name to None to mean there was no obvious
        option.
        """
        # Do not save here, we want to leave control of that to the caller.
        upload = UploadedData.objects.create(user=self.request.user)
        # Get a list of paths for files in this upload.
        paths = [item.name for item in data]
        # If there are multiple paths, see if we can boil them down to a
        # smaller number of representative paths (ideally, just one).
        if len(paths) > 1:
            # Group paths by common pre-extension prefixes
            groups = collections.defaultdict(list)
            for path in paths:
                group_name = os.path.splitext(path)[0]
                groups[group_name].append(path)
            # Check each group for "leaders" - a special filename like "a.shp"
            # which can be understood to represent other files in the group.
            # Map from each group name to a list of leaders in that group.
            leader_exts = ["shp"]
            group_leaders = {}
            for group_name, group in groups.items():
                leaders = [
                    path for path in group
                    if any(path.endswith(ext) for ext in leader_exts)
                ]
                if leaders:
                    group_leaders[group_name] = leaders
            # Rebuild paths: leaders + paths without leaders to represent them
            leader_paths = []
            for leaders in group_leaders.values():
                leader_paths.extend(leaders)
            orphan_paths = []
            for group_name, group in groups.items():
                if group_name not in group_leaders:
                    orphan_paths.extend(group)
            paths = leader_paths + orphan_paths

        max_length = UploadedData._meta.get_field('name').max_length
        # If no data, just return the instance.
        if not paths:
            name = None
            file_type = None
        # If we just have one path, that's a reasonable name for the upload.
        # We want this case to happen as frequently as reasonable, so that we
        # can set one reasonable name and file_type for the whole upload.
        elif len(paths) == 1:
            path = paths[0]
            basename = os.path.basename(path)
            name = Truncator(basename).chars(max_length)
            file_type = self.get_file_type(path)
        # Failing that, see if we can represent all the important paths within
        # the available space, making a meaningful mnemonic that isn't
        # misleading even though there isn't one obvious name. But if we can't
        # even do that, no use generating misleading or useless strings here,
        # just pass a None and let the frontend handle the lack of information.
        else:
            basenames = sorted(os.path.basename(path) for path in paths)
            name = ", ".join(basenames)
            if len(name) > max_length:
                logger.warning(
                    "rejecting upload name for length: {0!r} {1} > {2}"
                    .format(name, len(name), max_length)
                )
                name = None
            file_type = None

        upload.name = name
        upload.file_type = file_type
        return upload

    def form_valid(self, form):
        upload = self.upload(form.cleaned_data['file'])
        upload.save()

        # Create Upload Directory based on Upload PK
        outpath = os.path.join('osgeo_importer_uploads', str(upload.pk))
        outdir = os.path.join(FileSystemStorage().location, outpath)
        if not os.path.exists(outdir):
            os.makedirs(outdir)

        # Move all files to uploads directory using upload pk
        # Must be done for all files before saving upfile for validation
        finalfiles = []
        for each in form.cleaned_data['file']:
            tofile = os.path.join(outdir, os.path.basename(each.name))
            shutil.move(each.name, tofile)
            finalfiles.append(tofile)

        # Loop through and create uploadfiles and uploadlayers
        upfiles = []
        for each in finalfiles:
            upfile = UploadFile.objects.create(upload=upload)
            upfiles.append(upfile)
            upfile.file.name = each
            # Detect and store file type for later reporting, since it is no
            # longer true that every upload has only one file type.
            try:
                upfile.file_type = self.get_file_type(each)
            except NoDataSourceFound:
                upfile.file_type = None
            upfile.save()
            upfile_basename = os.path.basename(each)
            _, upfile_ext = os.path.splitext(upfile_basename)
            if upfile_ext.lower() not in ['.prj', '.dbf', '.shx']:
                description = self.get_fields(each)
                for layer in description:
                    configuration_options = DEFAULT_LAYER_CONFIGURATION.copy()
                    configuration_options.update({'index': layer.get('index')})
                    layer_basename = os.path.basename(
                        layer.get('layer_name') or ''
                    )
                    upload_layer = UploadLayer(
                        upload_file=upfile,
                        name=upfile_basename,
                        layer_name=layer_basename,
                        fields=layer.get('fields', {}),
                        index=layer.get('index'),
                        feature_count=layer.get('feature_count', None),
                        configuration_options=configuration_options
                    )
                    upload.uploadlayer_set.add(upload_layer)
        upload.size = sum(
            upfile.file.size for upfile in upfiles
        )
        upload.complete = True
        upload.state = 'UPLOADED'
        upload.save()

        if self.json:
            return self.render_to_json_response({'state': upload.state, 'id': upload.id,
                                                 'count': UploadFile.objects.filter(upload=upload.id).count()})

        return super(FileAddView, self).form_valid(form)

    def render_to_response(self, context, **response_kwargs):

        if self.json:
            context = {'errors': context['form'].errors}
            return self.render_to_json_response(context, **response_kwargs)

        return super(FileAddView, self).render_to_response(context, **response_kwargs)
