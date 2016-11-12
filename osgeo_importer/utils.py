from cStringIO import StringIO
import collections
from datetime import datetime
import logging
import os
import re
import shutil
import sys

import celery
from dateutil.parser import parse
from django import db
from django.conf import settings
from django.core.files.storage import FileSystemStorage
from django.utils.text import Truncator
import gdal
import ogr
import osr
from django.contrib.auth import get_user_model


logger = logging.getLogger(__name__)

try:
    from django.utils.module_loading import import_string
except ImportError:
    from django.utils.module_loading import import_by_path as import_string


ogr.UseExceptions()
gdal.UseExceptions()

GDAL_GEOMETRY_TYPES = {
   0: 'Unknown',
   1: 'Point',
   2: 'LineString',
   3: 'Polygon',
   4: 'MultiPoint',
   5: 'MultiLineString',
   6: 'MultiPolygon',
   7: 'GeometryCollection',
   100: 'None',
   101: 'LinearRing',
   1 + -2147483648: 'Point',
   2 + -2147483648: 'LineString',
   3 + -2147483648: 'Polygon',
   4 + -2147483648: 'MultiPoint',
   5 + -2147483648: 'MultiLineString',
   6 + -2147483648: 'MultiPolygon',
   7 + -2147483648: 'GeometryCollection',
   }


def timeparse(timestr):
    import numpy
    DEFAULT = datetime(1, 1, 1)
    bc = False
    if re.search(r'bce?', timestr, flags=re.I):
        bc = True
        timestr = re.sub(r'bce?', '', timestr, flags=re.I)
    if re.match('-', timestr, flags=re.I):
        bc = True
        timestr = timestr.replace('-', '', 1)
    if re.search(r'ad', timestr, flags=re.I):
        timestr = re.sub('ad', '', timestr, flags=re.I)

    if bc is True:
        timestr = "-%s" % timestr

    timestr = timestr.strip()

    try:
        t = numpy.datetime64(timestr).astype('datetime64[ms]').astype('int64')
        return t, str(numpy.datetime64(t, 'ms'))

    except:
        pass

    #  try just using straight datetime parsing
    if bc is False:
        try:
            logger.debug('trying %s as direct parse', timestr)
            dt = parse(timestr, default=DEFAULT)
            t = numpy.datetime64(dt.isoformat()).astype('datetime64[ms]').astype('int64')
            return t, str(numpy.datetime64(t, 'ms'))
        except:
            pass

    return None, None


def ensure_defaults(layer):
    """
    Sets a geoserver feature type defaults.
    """
    if not layer.resource.projection:
        fs = layer.resource
        fs.dirty['srs'] = 'EPSG:4326'
        fs.dirty['projectionPolicy'] = 'FORCE_DECLARED'
        layer.resource.catalog.save(fs)


class StdOutCapture(list):

    def __enter__(self):
        self._stdout = sys.stdout
        sys.stdout = self._stringio = StringIO()
        return self

    def __exit__(self, *args):
        self.extend(self._stringio.getvalue().splitlines())
        sys.stdout = self._stdout


class GdalErrorHandler(object):
    def __init__(self):
        self.err_level = gdal.CE_None
        self.err_no = 0
        self.err_msg = ''

    def handler(self, err_level, err_no, err_msg):
        self.err_level = err_level
        self.err_no = err_no
        self.err_msg = err_msg


lastNum = re.compile(r'(?:[^\d]*(\d+)[^\d]*)+')


def increment(s):
    """ look for the last sequence of number(s) in a string and increment """
    m = lastNum.search(s)
    if m:
        next = str(int(m.group(1)) + 1)
        start, end = m.span(1)
        s = s[:max(end - len(next), start)] + next + s[end:]
    else:
        return s + '0'
    return s


class FileExists(Exception):
    """
    Raised when trying to write to a file that already exists
    """
    pass


class NoDataSourceFound(Exception):
    """
    Raised when a file that does not have any geospatial data is read in.
    """
    pass


class FileTypeNotAllowed(Exception):
    """
    Raised when a file that does not have any geospatial data is read in.
    """
    pass


class UploadError(Exception):

    pass


def launder(string):
    """
    Launders a string.
    (Port of the gdal LaunderName function)
    """
    return re.sub('[^0-9a-zA-Z]+', '_', string.lower())


def sizeof_fmt(num):
    """
    Returns human-friendly file sizes.
    """
    for x in ['bytes', 'KB', 'MB', 'GB']:
        if num < 1024.0:
            return "%3.1f%s" % (num, x)
        num /= 1024.0
    return "%3.1f%s" % (num, 'TB')


def load_handler(path, *args, **kwargs):
    """
    Given a path to a handler, return an instance of that handler.
    E.g.::
        >>> from django.http import HttpRequest
        >>> request = HttpRequest()
        >>> load_handler('django.core.files.uploadhandler.TemporaryFileUploadHandler', request)
        <TemporaryFileUploadHandler object at 0x...>
    """
    return import_string(path)(*args, **kwargs)


def get_kwarg(index, kwargs, default=None):

    if index in kwargs:
        return kwargs[index]
    else:
        return getattr(settings, index, default)


def increment_filename(filename):
    if os.path.exists(filename):
        file_base = os.path.basename(filename)
        file_dir = os.path.dirname(filename)
        file_root, file_ext = os.path.splitext(file_base)
        i = 1
        while i <= 100:
            testfile = "%s/%s%s%s" % (file_dir, file_root, i, file_ext)

            if not os.path.exists(testfile):
                break

            i += 1

        if not os.path.exists(testfile):
            return testfile
        else:
            raise FileExists(testfile)
    else:
        return filename


def raster_import(infile, outfile, *args, **kwargs):

    if os.path.exists(outfile):
        raise FileExists

    options = get_kwarg('options', kwargs, ['TILED=YES'])
    sr = osr.SpatialReference()
    sr.ImportFromEPSG(3857)
    t_srs_prj = sr.ExportToWkt()
    build_overviews = get_kwarg('build_overviews', kwargs, True)

    geotiff = gdal.GetDriverByName("GTiff")
    if geotiff is None:
        raise RuntimeError

    indata = gdal.Open(infile)
    if indata is None:
        raise NoDataSourceFound

    if indata.GetProjectionRef() is None:
        indata.SetProjection(t_srs_prj)

    vrt = gdal.AutoCreateWarpedVRT(indata, None, t_srs_prj, 0, .125)
    outdata = geotiff.CreateCopy(outfile, vrt, 0, options)

    if build_overviews:
        outdata.BuildOverviews("AVERAGE")

    return outfile


def quote_ident(str):
    conn = db.connections[settings.OSGEO_DATASTORE]
    cursor = conn.cursor()
    query = "SELECT quote_ident(%s);"
    cursor.execute(query, (str,))
    return cursor.fetchone()[0]


def decode(s, encodings=('ascii', 'utf8', 'latin1')):
    """
    Common character encodings.
    """
    for encoding in encodings:
        try:
            return s.decode(encoding)
        except UnicodeDecodeError:
            pass
    return s.decode('ascii', 'ignore')

class ImportHelper(object):
    """
    Import Helpers
    *note*: A number of imports are done in methods here rather than globally in this file
        because these import require django settings & models to be fully set up and other util
        functions are used before that is the case.
    """
    def __init__(self, *args, **kwargs):
        super(ImportHelper, self).__init__(*args, **kwargs)
        from osgeo_importer.inspectors import OSGEO_INSPECTOR
        Inspector = import_string(OSGEO_INSPECTOR)
        ImportHelper.Inspector = Inspector

    def get_fields(self, path):
        """
        Returns a list of field names and types.
        """
        with self.Inspector(path) as opened_file:
            return opened_file.describe_fields()

    def get_file_type(self, path):
        with self.Inspector(path) as opened_file:
            return opened_file.file_type()

    def upload(self, data, owner):
        """Use cleaned form data to populate an unsaved upload record.

        Once, each upload was just one file, so all we had to do was attach its
        name and type to the upload, where we could display it. Since multifile
        and geopackage supported were added, the required behavior depends on
        what we find in the upload. That is what this method is for. For
        example, it looks at an upload and tries to come up with a reasonably
        mnemonic name, or else set name to None to mean there was no obvious
        option.
        """
        from osgeo_importer.models import UploadedData

        # Do not save here, we want to leave control of that to the caller.

        upload = UploadedData.objects.create(user=owner)
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

    def configure_upload(self, upload, files):
        """
            *upload*: new, unsaved UploadedData instance ( from upload() )
            *desc*:
                1. sets up the directory for the upload, and populates
                2. moves the files to the uploads directory
                3. creates UploadFile & UploadeLayer instances related to *upload*
        """
        from osgeo_importer.models import UploadFile, UploadLayer, DEFAULT_LAYER_CONFIGURATION
        upload.save()

        # Create Upload Directory based on Upload PK
        outpath = os.path.join('osgeo_importer_uploads', str(upload.pk))
        outdir = os.path.join(FileSystemStorage().location, outpath)
        if not os.path.exists(outdir):
            os.makedirs(outdir)

        # Move all files to uploads directory using upload pk
        # Must be done for all files before saving upfile for validation
        finalfiles = []
        for each in files:
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


def import_all_layers(uploaded_data, owner=None):
    """ Imports all layers of *uploaded_data*.
        *uploaded_data* is a saved UploadedData instance.
    """
    from osgeo_importer.tasks import import_object
    if owner is None:
        User = get_user_model()
        owner = User.objects.get(username='AnonymousUser')

    import_results = []
    for uploaded_file in uploaded_data.uploadfile_set.all():
        for uploaded_layer in uploaded_file.uploadlayer_set.all():
            configs = [{'config': [{'index': 0}], 'upload_file_name': uploaded_file.name}]

            for config in configs:
                if config['upload_file_name'] == uploaded_layer.name:
                    configuration_options = {'layer_owner': owner.username, u'index': 0}
                    import_result = import_object.delay(
                        uploaded_layer.upload_file.id, configuration_options=configuration_options
                    )
                    import_results.append(import_result)
                    if import_result.state in celery.states.READY_STATES:
                        uploaded_layer.import_status = import_result.status
                    uploaded_layer.task_id = import_result.id
                    uploaded_layer.save()

    # Wait for all of the results to complete before returning
    [ ir.wait() for ir in import_results ]
    return len(import_results)
