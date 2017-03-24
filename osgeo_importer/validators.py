import logging
import os
from zipfile import is_zipfile, ZipFile

from django.conf import settings

from osgeo_importer.importers import VALID_EXTENSIONS
from osgeo_importer.utils import NoDataSourceFound, load_handler


OSGEO_IMPORTER = getattr(settings, 'OSGEO_IMPORTER', 'osgeo_importer.importers.OGRImport')

logger = logging.getLogger(__name__)

NONDATA_EXTENSIONS = ['shx', 'prj', 'dbf', 'xml', 'sld']

ALL_OK_EXTENSIONS = set(VALID_EXTENSIONS) | set(NONDATA_EXTENSIONS)


def valid_file(file):
    """ Returns an empty list if file is valid, or a list of strings describing problems with the file.
        @see VALID_EXTENSIONS, NONDATA_EXTENSIONS
    """
    errors = []
    basename = os.path.basename(file.name)
    _, extension = os.path.splitext(basename)
    extension = extension.lstrip('.').lower()

    if is_zipfile(file):
        with ZipFile(file) as zip:
            for content_name in zip.namelist():
                content_file = zip.open(content_name)
                content_errors = valid_file(content_file)
                if not content_errors:
                    errors.extend(content_errors)
    elif extension not in ALL_OK_EXTENSIONS:
        errors.append(
            '{}: "{}" not found in VALID_EXTENSIONS, NONDATA_EXTENSIONS'.format(basename, extension)
        )

    return errors


def validate_shapefiles_have_all_parts(filenamelist):
    shp = []
    prj = []
    dbf = []
    shx = []
    for file in filenamelist:
        base, extension = os.path.splitext(file)
        extension = extension.lstrip('.').lower()
        if extension == 'shp':
            shp.append(base)
        elif extension == 'prj':
            prj.append(base)
        elif extension == 'dbf':
            dbf.append(base)
        elif extension == 'shx':
            shx.append(base)
    if set(shp) == set(prj) == set(dbf) == set(shx):
        return True
    else:
        return False


def validate_inspector_can_read(filename):
    filedir, file = os.path.split(filename)
    base, extension = os.path.splitext(file)
    extension = extension.lstrip('.').lower()
    if extension in NONDATA_EXTENSIONS:
        return True
    try:
        importer = load_handler(OSGEO_IMPORTER, filename)
        data, inspector = importer.open_source_datastore(filename)
        # Ensure the data has a geometry.
        for description in inspector.describe_fields():
            if description.get('raster') is False and description.get('geom_type') in inspector.INVALID_GEOMETRY_TYPES:
                return False
    except NoDataSourceFound:
        return False
    return True
