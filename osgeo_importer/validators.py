import os
from .utils import NoDataSourceFound, load_handler
from .importers import OSGEO_IMPORTER, VALID_EXTENSIONS
import logging

logger = logging.getLogger(__name__)

NONDATA_EXTENSIONS = ['shx', 'prj', 'dbf', 'xml', 'sld']


def validate_extension(filename):
    filedir, file = os.path.split(filename)
    base, extension = os.path.splitext(file)
    extension = extension.lstrip('.').lower()
    if extension not in VALID_EXTENSIONS:
        return False
    else:
        return True


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
