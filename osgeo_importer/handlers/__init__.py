import requests
from django import db
from django.conf import settings
from osgeo_importer.inspectors import OGRFieldConverter


DEFAULT_IMPORT_HANDLERS = ['osgeo_importer.handlers.FieldConverterHandler',
                           'osgeo_importer.handlers.geoserver.GeoserverPublishHandler',
                           'osgeo_importer.handlers.geoserver.GeoServerTimeHandler',
                           'osgeo_importer.handlers.geoserver.GeoWebCacheHandler',
                           'osgeo_importer.handlers.geoserver.GeoServerBoundsHandler',
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


class ImportHandler(object):

    def __init__(self, importer, *args, **kwargs):
        self.importer = importer

    @ensure_can_run
    def handle(self, layer, layerconfig, *args, **kwargs):
        raise NotImplementedError('Subclass should implement this.')

    def can_run(self, layer, layer_config, *args, **kwargs):
        """
        Returns true if the configuration has enough information to run the handler.
        """
        return True


class FieldConverterHandler(ImportHandler):
    """
    Converts fields based on the layer_configuration.
    """

    def convert_field_to_time(self, layer, field):
        d = db.connections['datastore'].settings_dict
        connection_string = "PG:dbname='%s' user='%s' password='%s' host='%s' port='%s'" % (d['NAME'], d['USER'],
                                                                        d['PASSWORD'], d['HOST'], d['PORT'])

        with OGRFieldConverter(connection_string) as datasource:
            return datasource.convert_field(layer, field)

    @ensure_can_run
    def handle(self, layer, layer_config, *args, **kwargs):
        for field_to_convert in set(layer_config.get('convert_to_date', [])):

            if not field_to_convert:
                continue

            new_field, new_field_yr = self.convert_field_to_time(layer, field_to_convert)

            # if the start_date or end_date needed to be converted to a date
            # field, use the newly created field name
            for date_option in ('start_date', 'end_date'):
                if layer_config.get(date_option) == field_to_convert:
                    layer_config[date_option] = new_field.lower()
