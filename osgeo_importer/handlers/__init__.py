from django import db
from django.conf import settings
from osgeo_importer.inspectors import OGRFieldConverter, BigDateOGRFieldConverter


DEFAULT_IMPORT_HANDLERS = ['osgeo_importer.handlers.FieldConverterHandler',
                           'osgeo_importer.handlers.geoserver.GeoserverPublishHandler',
                           'osgeo_importer.handlers.geoserver.GeoserverPublishCoverageHandler',
                           'osgeo_importer.handlers.geoserver.GeoServerTimeHandler',
                           'osgeo_importer.handlers.geoserver.GeoWebCacheHandler',
                           'osgeo_importer.handlers.geoserver.GeoServerBoundsHandler',
                           'osgeo_importer.handlers.geoserver.GenericSLDHandler',
                           'osgeo_importer.handlers.geonode.GeoNodePublishHandler']

IMPORT_HANDLERS = getattr(settings, 'IMPORT_HANDLERS', DEFAULT_IMPORT_HANDLERS)


def ensure_can_run(func):
    """
    Convenience decorator that executes the "can_run" method class and returns the function if the can_run is True.
    """

    def func_wrapper(self, *args, **kwargs):

        if self.can_run(*args, **kwargs):
            return func(self, *args, **kwargs)

    return func_wrapper


class ImportHandlerMixin(object):
    """
    A mixin providing the basic layout for handlers.
    """
    def __init__(self, importer, *args, **kwargs):
        self.importer = importer

    @ensure_can_run
    def handle(self, layer, layerconfig, *args, **kwargs):
        """
        This method is executed by each Importer.

        :param layer: The name of the imported layer.
        :param layerconfig: The configuration options of the layer (dict).
        """
        raise NotImplementedError('Subclass should implement this.')

    def can_run(self, layer, layer_config, *args, **kwargs):
        """
        Returns True if the handler has enough information to execute.
        """
        return True


class GetModifiedFieldsMixin(object):

    @staticmethod
    def update_date_attributes(layer_config):
        """
        Updates the start_date, end_date and convert_to_date to use modified fields if needed.
        """
        modified_fields = layer_config.get('modified_fields', {})
        layer_config['start_date'] = modified_fields.get(layer_config.get('start_date'), layer_config.get('start_date'))
        layer_config['end_date'] = modified_fields.get(layer_config.get('end_date'), layer_config.get('end_date'))

        convert_to_date = []

        for field in layer_config.get('convert_to_date', []):
            convert_to_date.append(modified_fields.get(field, field))

        layer_config['convert_to_date'] = convert_to_date


class FieldConverterHandler(GetModifiedFieldsMixin, ImportHandlerMixin):
    """
    Converts fields based on the layer_configuration.
    """
    field_converter = OGRFieldConverter

    def convert_field_to_time(self, layer, field):
        d = db.connections[settings.OSGEO_DATASTORE].settings_dict
        connection_string = "PG:dbname='%s' user='%s' password='%s' host='%s' port='%s'" % (d['NAME'], d['USER'],
                                                                                            d['PASSWORD'], d['HOST'],
                                                                                            d['PORT'])

        with self.field_converter(connection_string) as datasource:
            return datasource.convert_field(layer, field)

    @ensure_can_run
    def handle(self, layer, layer_config, *args, **kwargs):
        self.update_date_attributes(layer_config)

        try:
            for field_to_convert in set(layer_config.get('convert_to_date', [])):

                if not field_to_convert:
                    continue

                new_col = self.convert_field_to_time(layer, field_to_convert)

                # if the start_date or end_date needed to be converted to a date
                # field, use the newly created field name/
                for date_option in ('start_date', 'end_date'):
                    if layer_config.get(date_option) == field_to_convert:
                        layer_config[date_option] = new_col.lower()

        except Exception as e:
            print "Error: %s" % e


class BigDateFieldConverterHandler(FieldConverterHandler):
    """
    Uses the Big Date field converter.

    Note: Using this class with Geoserver requires a special build of GeoTools.
    https://github.com/MapStory/geotools/commits/postgis-xdate-udt-12.x
    """

    field_converter = BigDateOGRFieldConverter
