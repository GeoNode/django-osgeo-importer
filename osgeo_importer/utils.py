import gdal
import logging
import numpy
import ogr
import osr
import os
import re
import sys
import tempfile

from csv import DictReader
from cStringIO import StringIO
from datetime import datetime
from dateutil.parser import parse
from django.template import Context, Template
from django.conf import settings
from django import db
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


BASE_VRT = '''
<OGRVRTDataSource>
    <OGRVRTLayer name="{{name}}">
        <SrcDataSource>{{file}}</SrcDataSource>
        <GeometryType>wkbUnknown</GeometryType>
        <GeometryField encoding="{{enc}}" {{encopt|safe}} />
    </OGRVRTLayer>
</OGRVRTDataSource>'''


def timeparse(timestr):
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


def create_vrt(file_path):
    """
    Creates a VRT file.
    """

    geo = {}
    headers = None

    with open(file_path) as csv_file:
            headers = DictReader(csv_file, dialect='excel').fieldnames

    for header in headers:
        if re.search(r'\b(lat|latitude|y)\b', header.lower()):
            geo['y'] = header

        if re.search(r'\b(lon|long|longitude|x)\b', header.lower()):
            geo['x'] = header

        if re.search(r'\b(geom|thegeom)\b', header.lower()):
            geo['geom'] = header

    context = {
        'file': file_path,
        'name': os.path.basename(file_path).replace('.csv', ''),
        'enc': 'PointFromColumns',
        'encopt': 'x="{0}" y="{1}"'.format(geo.get('x'), geo.get('y'))
    }

    if geo.get('geom'):
        context['encoding'] = 'WKT'
        context['encopt'] = 'field="{0}"'.format(geo.geom)

    vrtData = Context(context)
    template = Template(BASE_VRT)
    temp_file = tempfile.NamedTemporaryFile(suffix='.vrt')
    temp_file.write(template.render(vrtData))
    temp_file.seek(0)
    return temp_file


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
        next = str(int(m.group(1))+1)
        start, end = m.span(1)
        s = s[:max(end-len(next), start)] + next + s[end:]
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
            raise FileExists
    else:
        return filename


def raster_import(infile, outfile, *args, **kwargs):

    if os.path.exists(outfile):
        raise FileExists

    #if not os.path.exists(infile):
    #    raise NoDataSourceFound

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
