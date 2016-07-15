import os

import gdal
import ogr
from django.conf import settings
from .utils import NoDataSourceFound, GDAL_GEOMETRY_TYPES, increment, timeparse, quote_ident, parse

from django import db

OSGEO_INSPECTOR = getattr(settings, 'OSGEO_INSPECTOR', 'osgeo_importer.inspectors.GDALInspector')


class InspectorMixin(object):
    """
    Inspectors open data sources and return information about them.
    """
    INVALID_GEOMETRY_TYPES = []
    opener = None

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        self.open(*self.args, **self.kwargs)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def open(self, *args, **kwargs):
        raise NotImplementedError

    def close(self, *args, **kwargs):
        raise NotImplementedError

    def describe_fields(self):
        raise NotImplementedError

    def get_filetype(self, filename):
        """
        Gets the filetype.
        """
        try:
            return os.path.splitext(filename)[1]
        except IndexError:
            return


class OGRInspector(InspectorMixin):

    def __init__(self, connection_string, *args, **kwargs):
        self.connection_string = connection_string
        self.data = None
        super(OGRInspector, self).__init__(*args, **kwargs)

    def open(self, *args, **kwargs):
        """
        Opens the connection_string.
        """
        # "1" argument makes the data writeable
        self.data = ogr.Open(self.connection_string, 1)

        if self.data is None:
            raise NoDataSourceFound

        return self.data

    def close(self, *args, **kwargs):
        self.data = None


class GDALInspector(InspectorMixin):

    INVALID_GEOMETRY_TYPES = ['None']

    def __init__(self, connection_string, *args, **kwargs):
        self.file = connection_string
        self.data = None
        super(GDALInspector, self).__init__(*args, **kwargs)

    def close(self, *args, **kwargs):
        self.data = None

    @property
    def method_safe_filetype(self):
        """
        Converts the filetype (ie extension) to a method-safe string.
        """
        file_type = self.get_filetype(self.file)

        if file_type:
            return file_type.replace('.', '')

    def prepare_csv(self, filename, *args, **kwargs):
        """
        Adds the <X|Y|GEOM>_POSSIBLE_NAMES opening options.
        """
        x_possible = getattr(settings, 'IMPORT_CSV_X_FIELDS', ['Lon*', 'x', 'lon*'])
        y_possible = getattr(settings, 'IMPORT_CSV_Y_FIELDS', ['Lat*', 'y', 'lat*'])
        geom_possible = getattr(settings, 'IMPORT_CSV_GEOM_FIELDS',
                                ['geom', 'GEOM', 'WKT', 'the_geom', 'THE_GEOM', 'WKB', 'wkb_geometry'])

        oo = kwargs.get('open_options', [])

        oo.append('X_POSSIBLE_NAMES={0}'.format(','.join(x_possible)))
        oo.append('Y_POSSIBLE_NAMES={0}'.format(','.join(y_possible)))
        oo.append('GEOM_POSSIBLE_NAMES={0}'.format(','.join(geom_possible)))

        kwargs['open_options'] = oo

        return filename, args, kwargs

    def prepare_zip(self, filename, *args, **kwargs):
        """
        Appends '/vsizip/' to the filename path.
        """

        return '/vsizip/' + filename, args, kwargs

    def prepare_gz(self, filename, *args, **kwargs):
        """
        Appends '/vsigzip/' to the filename path.
        """

        return '/vsigzip/' + filename, args, kwargs

    def open(self, *args, **kwargs):
        """
        Opens the file.
        """
        filename = self.file

        prepare_method = 'prepare_{0}'.format(self.method_safe_filetype)

        if hasattr(self, prepare_method):
            # prepare hooks make extension specific modifications to input parameters
            filename, args, kwargs = getattr(self, prepare_method)(filename, *args, **kwargs)

        open_options = kwargs.get('open_options', [])

        try:
            self.data = gdal.OpenEx(filename, open_options=open_options)
        except RuntimeError:
            raise NoDataSourceFound

        if self.data is None:
            raise NoDataSourceFound

        return self.data

    @staticmethod
    def geometry_type(number):
        """
        Returns a string of the geometry type based on the number.
        """
        try:
            return GDAL_GEOMETRY_TYPES[number]
        except KeyError:
            return
    
    def describe_fields(self):
        """
        Returns a dict of the layers with fields and field types.
        """
        opened_file = self.data
        description = []

        if not opened_file:
            opened_file = self.open()
        
        driver = opened_file.GetDriver().LongName

        # Get Vector Layers
        n = 0
        for n in range(0, opened_file.GetLayerCount()):
            layer = opened_file.GetLayer(n)
            layer_name = layer.GetName()
            layer_description = {'layer_name': layer_name,
                                 'feature_count': layer.GetFeatureCount(),
                                 'fields': [],
                                 'index': n,
                                 'geom_type': self.geometry_type(layer.GetGeomType()),
                                 'raster': False, 'driver':driver}

            layer_definition = layer.GetLayerDefn()
            for i in range(layer_definition.GetFieldCount()):
                field_desc = {}
                field = layer_definition.GetFieldDefn(i)
                field_desc['name'] = field.GetName()
                field_desc['type'] = field.GetFieldTypeName(i)
                layer_description['fields'].append(field_desc)

            description.append(layer_description)

        # Get Raster Layers
        # Get main layer
        if opened_file.GetMetadataItem('AREA_OR_POINT'):
            layer_description = {'index': len(description),
                                'layer_name': self.file,
                                'path': self.file,
                                'raster': True, 'driver':driver}
            description.append(layer_description)
        # Get sub layers
        raster_list = opened_file.GetSubDatasets()
        for m in range(0,raster_list.__len__()):
            layer = gdal.OpenEx(raster_list[m][0])
            layer_description = {'index': len(description),
                                 'subdataset_index': m,
                                 'path': raster_list[m][0],
                                 'layer_name': raster_list[m][0].split(':')[-1],
                                 'raster': True, 'driver':driver}
            description.append(layer_description)

        return description

    def get_driver(self):
        opened_file = self.data

        if not opened_file:
            opened_file = self.open()

        return opened_file.GetDriver()

    def file_type(self):
        """
        Returns the data's file type (via the GDAL driver name)
        """
        return self.get_driver().ShortName


class OGRTruncatedConverter(OGRInspector):
    def convert_truncated(self, source_layer_name, dest_layer_name):
        converted_mapping = {}
        dest_layer_name = dest_layer_name.split(':')[1]
        dest_layer = self.data.GetLayerByName(dest_layer_name)
        source_layer = self.data.GetLayerByName(source_layer_name)
        dest_schema = dest_layer.GetLayerDefn()
        source_schema = source_layer.GetLayerDefn()

        #  if the feature definitions are exactly the same we don't need to do any work.
        if dest_schema.IsSame(source_schema) is True:
            return True

        dest_field_count = dest_schema.GetFieldCount()
        source_field_count = source_schema.GetFieldCount()

        if dest_field_count == 0:
            raise AttributeError('Destination layer has no attributes.')

        if source_field_count == 0:
            raise AttributeError('Source layer has no attributes.')

        if dest_field_count < source_field_count:
            raise AttributeError('Destination layer has fewer attributes than source layer.')

        dest_field_schema = self.extract_field_definitions(dest_schema, dest_field_count)
        source_field_schema = self.extract_field_definitions(source_schema, source_field_count)

        is_subset = True
        truncated_fields = {}
        for attribute in source_field_schema:

            if attribute in dest_field_schema:
                source_type = source_field_schema[attribute]
                dest_type = dest_field_schema[attribute]

                if source_type != dest_type and (self.compatible_types(source_type, dest_type) is False):
                    is_subset = False
                    break

            elif len(attribute) == 10:
                truncated_name = self.find_truncated_name(attribute, dest_field_schema)
                if truncated_name is not None and truncated_name not in source_field_schema:
                    trunc_field_index = source_schema.GetFieldIndex(attribute)
                    truncated_fields[truncated_name] = trunc_field_index
                    converted_mapping[attribute] = truncated_name

        if is_subset is False:
            raise AttributeError('Source layer attributes are not a subset of destination.')

        for truncated_name in truncated_fields:
            trunc_field_index = truncated_fields[truncated_name]
            name_alter = ogr.FieldDefn(truncated_name, ogr.OFTInteger)
            source_layer.AlterFieldDefn(trunc_field_index, name_alter, ogr.ALTER_NAME_FLAG)

        return converted_mapping

    @staticmethod
    def compatible_types(source_type, dest_type):
        if source_type is ogr.OFTString:
            if dest_type is ogr.OFTDateTime or dest_type is ogr.OFTDate:
                return True
        elif source_type is ogr.OFTDate or source_type is ogr.OFTDateTime:
            if dest_type is ogr.OFTString or ogr.OFTDateTime or ogr.OFTDate:
                return True
        elif source_type is ogr.OFTInteger or ogr.OFTReal:
            if dest_type is ogr.OFTInteger or ogr.OFTReal:
                return True
        return False

    @staticmethod
    def find_truncated_name(attribute, field_list):
        for dest_attribute in field_list:
            if dest_attribute.startswith(attribute) and len(dest_attribute) > 10:
                return dest_attribute
        return None

    @staticmethod
    def extract_field_definitions(schema, field_count):
        field_schema = {}

        for field_index in range(0, field_count):
            field_definition = schema.GetFieldDefn(field_index)
            field_schema[field_definition.GetNameRef()] = field_definition.GetType()
        return field_schema


class BigDateOGRFieldConverter(OGRInspector):

    def convert_field(self, layer_name, field):
        field_as_string = str(field)
        xd_col = '{0}_xd'.format(field).lower()
        parsed_col = '{0}_parsed'.format(field).lower()
        target_layer = self.data.GetLayerByName(layer_name)

        # target_layer.GetLayerDefn().GetFieldIndex(parsed_col) raises errors when the field does not
        # exist with older versions of OGR
        while target_layer.FindFieldIndex(xd_col, 1) >= 0:
            xd_col = increment(xd_col)

        while target_layer.FindFieldIndex(parsed_col, 1) >= 0:
            parsed_col = increment(parsed_col)

        target_layer.CreateField(ogr.FieldDefn(xd_col, ogr.OFTInteger64))
        xd_col_index = target_layer.GetLayerDefn().GetFieldIndex(xd_col)
        target_layer.CreateField(ogr.FieldDefn(parsed_col, ogr.OFTString))
        parsed_col_index = target_layer.GetLayerDefn().GetFieldIndex(parsed_col)

        for feat in target_layer:

            if not feat:
                continue

            string_field = feat[field_as_string]

            if string_field:
                xd, parsed = timeparse(str(string_field))

                feat.SetField(xd_col_index, xd)
                feat.SetField(parsed_col_index, parsed)

                target_layer.SetFeature(feat)

            # prevent segfaults
            feat = None
        conn = db.connections[settings.OSGEO_DATASTORE]
        cursor = conn.cursor()
        query = """
        DO $$
        BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='bigdate') THEN
        CREATE DOMAIN bigdate bigint;
        END IF;
        END;
        $$;

        ALTER TABLE %s ALTER COLUMN %s TYPE bigdate;
        """ % (quote_ident(layer_name), quote_ident(xd_col))

        cursor.execute(query)

        return xd_col


class OGRFieldConverter(OGRInspector):
    """
    Uses dateutil.parse to parse date times.
    """

    def convert_field(self, layer_name, field):
        fieldname = '{0}_as_date'.format(field)
        target_layer = self.data.GetLayerByName(layer_name)

        while target_layer.GetLayerDefn().GetFieldIndex(fieldname) >= 0:
            fieldname = increment(fieldname)

        target_layer.CreateField(ogr.FieldDefn(fieldname, ogr.OFTDateTime))
        field_index = target_layer.GetLayerDefn().GetFieldIndex(fieldname)

        for feat in target_layer:

            if not feat:
                continue

            string_field = feat[str(field)]

            if string_field:
                pars = parse(str(string_field))

                feat.SetField(field_index, pars.year, pars.month, pars.day, pars.hour, pars.minute, pars.second,
                              pars.microsecond)

                target_layer.SetFeature(feat)

            feat = None

        return fieldname
