import logging
import os

from django import db
from django.conf import settings
from django.core.files.storage import FileSystemStorage
import gdal
import ogr
import osr

from osgeo_importer.models import UploadLayer

from .handlers import IMPORT_HANDLERS
from .inspectors import GDALInspector, OGRInspector
from .utils import (
    FileTypeNotAllowed,
    GdalErrorHandler,
    load_handler,
    increment_filename,
    raster_import,
    decode,
    convert_wkt_to_epsg,
    database_schema_name
)  # noqa: F401


logger = logging.getLogger(__name__)
ogr.UseExceptions()

MEDIA_ROOT = getattr(settings, 'MEDIA_ROOT', FileSystemStorage().location)
DEFAULT_SUPPORTED_EXTENSIONS = ['shp', 'shx', 'prj', 'dbf', 'kml', 'geojson', 'json',
                                'tif', 'tiff', 'gpkg', 'csv', 'zip', 'xml',
                                'sld', 'ntf', 'nitf']
VALID_EXTENSIONS = getattr(settings, 'OSGEO_IMPORTER_VALID_EXTENSIONS', DEFAULT_SUPPORTED_EXTENSIONS)

RASTER_FILES = getattr(settings, 'OSGEO_IMPORTER_RASTER_FILES', os.path.join(MEDIA_ROOT, 'osgeo_importer_raster'))
UPLOAD_DIR = getattr(settings, 'OSGEO_IMPORTER_UPLOAD_DIR', os.path.join(MEDIA_ROOT, 'osgeo_importer_uploads'))

if not os.path.exists(RASTER_FILES):
    os.makedirs(RASTER_FILES)

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)


class Import(object):
    """
    Importers are responsible for opening incoming geospatial datasets (using
    one or many inspectors) and copying features to a target location.

    """
    _import_handlers = []
    handler_results = []
    enabled_handlers = IMPORT_HANDLERS
    source_inspectors = []
    target_inspectors = []
    valid_extensions = VALID_EXTENSIONS

    def filter_handler_results(self, handler_name):
        """
        Filters handler results to just the results returned from a specific handler.

        :param handler_name: The name of the handler.
        :return: A List of handlers and their results.
        """
        return filter(lambda results: handler_name in results.keys(), self.handler_results)

    def _initialize_handlers(self):
        self._import_handlers = [load_handler(handler, self)
                                 for handler in self.enabled_handlers]

    @property
    def import_handlers(self):
        """
        Initializes handlers and/or returns them.
        """
        if not self._import_handlers:
            self._initialize_handlers()

        return self._import_handlers

    def import_file(self, filename, **kwargs):
        """
        Subclass this to provide import logic.

        :param filename: the path to the data source.
        :param kwargs: keyword arguments for the import process.  `configuration_options` should be
        provided in these kwargs.
        :return: A list of lists where each value is [layername, configuratuon_options].
        """
        raise NotImplementedError

    def file_extension_not_allowed(self, request, *args, **kwargs):
        """
        Method called when an incoming dataset has an extension that is not allowed.

        TODO: Should "request" be removed as an argument?
        """
        raise FileTypeNotAllowed

    def handle(self, configuration_options=None, *args, **kwargs):
        """
        Executes the entire import process.
        1) Imports the dataset from the source dataset to the target.
        2) Executes arbitrary handlers that can modify the data set.
        3) Executes arbitrary publish handlers to publish the data set.

        :param configuration_options: A list of configuration options that are sent to the
        import method and subsequently to the handlers.
        :return: The response from the import_file method.
        """
        if configuration_options is None:
            configuration_options = [{'index': 0}]
        layers = self.import_file(configuration_options=configuration_options)

        for layer, config in layers:
            config['handler_results'] = self.run_import_handlers(layer, config, **kwargs)

        return layers

    def run_import_handlers(self, layer, layer_config, *args, **kwargs):
        """
        Handlers that are run on each layer of a data set. Each handler expects at least two arguments,
        the layer name and the layer configuration.

        :param layer: The name of the layer (returned from the import method).
        :param layer_config: Layer configuration options (dict) that is passed through to each handler.
        :return: A list of handler results.
        """
        self.handler_results = []
        for handler in self.import_handlers:
            self.handler_results.append({type(handler).__name__: handler.handle(layer, layer_config, *args, **kwargs)})

        return self.handler_results

    def open_datastore(self, connection_string, inspectors, *args, **kwargs):
        """
        Opens the source source data set using one or many inspectors.

        :param configuration_options: A list of configuration options that are sent to the
        import method and subsequently to the handlers.
        :param inspectors: A list of inspector classes that are run through in order.
        :return: The response from the first inspector providing a response that is not None.
        """

        for inspector in inspectors:
            insp = inspector(connection_string, *args, **kwargs)
            data = insp.open()
            if data is not None:
                return data, insp

    def open_source_datastore(self, connection_string, *args, **kwargs):
        """
        Opens the source source data.

        :param configuration_options: A list of configuration options that are sent to the
        import method and subsequently to the handlers.
        :return the response from the open_datastore.
        """
        return self.open_datastore(connection_string, self.source_inspectors, *args, **kwargs)


class OGRImport(Import):

    source_inspectors = [GDALInspector]
    target_inspectors = [OGRInspector]

    def __init__(self, filename, target_store=None, upload_file=None):
        self.file = filename
        self.upload_file = upload_file
        self.completed_layers = []

        if target_store is None:
            d = db.connections[settings.OSGEO_DATASTORE].settings_dict
            connection_string = "PG:dbname='%s' user='%s' password='%s' host='%s' port='%s' schemas=%s" % (
                                                                                                d['NAME'], d['USER'],
                                                                                                d['PASSWORD'],
                                                                                                d['HOST'], d['PORT'],
                                                                                                database_schema_name())
            self.target_store = connection_string

    def open_target_datastore(self, connection_string, *args, **kwargs):
        """
        Opens the target data set using OGR.
        """

        return self.open_datastore(connection_string, self.target_inspectors, *args, **kwargs)

    def create_target_dataset(self, target_datastore, layer_name, *args, **kwargs):
        """
        Creates the data source in the target data store.
        """
        return target_datastore.CreateLayer(layer_name, *args, **kwargs)

    def get_layer_type(self, layer, source):
        """
        A hook for returning the GeometryType of a layer.

        This is work around for a limitation of the Shapefile: when reading a Shapefile of type
        SHPT_ARC, the corresponding layer will be reported as of type wkbLineString, but depending on the number
        of parts of each geometry, the actual type of the geometry for each feature can be either OGRLineString
        or OGRMultiLineString. The same applies for SHPT_POLYGON shapefiles, reported as layers of type wkbPolygon,
        but depending on the number of parts of each geometry, the actual type can be either OGRPolygon or
        OGRMultiPolygon.
        """
        driver = source.GetDriver().LongName

        if driver == 'ESRI Shapefile':
            geom_type = layer.GetGeomType()

            # If point return MultiPoint
            if geom_type == 1:
                return 4

            # If LineString return MultiLineString
            if geom_type == 2:
                return 5

            # if Polygon return MutliPolygon
            if geom_type == 3:
                return 6

        return layer.GetGeomType()

    def import_file(self, *args, **kwargs):
        """
        Loads data that has been uploaded into whatever format we need for serving.
        Expects kwarg "configuration_options" which is a list of dicts, one for each layer to import.
            each dict must contain "upload_layer_id" referencing the UploadLayer being imported
            and must contain "index" which is a 0-based index to identify which layer from the file is being referenced.
            and can contain an optional "layer_name" to assign a custom name.  "layer_name" may be ignored
            if it is already in use.
        """
        filename = self.file
        self.completed_layers = []
        err = GdalErrorHandler()
        gdal.PushErrorHandler(err.handler)
        gdal.UseExceptions()
        configuration_options = kwargs.get('configuration_options', [{'index': 0}])
        # Configuration options should be a list at this point since the
        # importer can process multiple layers in a single import
        if isinstance(configuration_options, dict):
            configuration_options = [configuration_options]

        # Ensure that upload_layer_id exists in configuration for each layer
        nbad_config = 0
        for co in configuration_options:
            if 'upload_layer_id' not in co:
                nbad_config += 1

        if nbad_config > 0:
            msg = '{} of {} configs missing upload_layer_id'.format(nbad_config, len(configuration_options))
            logger.critical(msg)
            raise Exception(msg)

        # --- Resolve any disparity between automatically-assigned UploadLayer.layer_name and layer_name in
        # configuration options.
        # If layer_name is present in configuration_options either update UploadLayer.layer_name to match if it's unique
        #    or update configuration_options' 'layer_name' to match value in UploadLayer.layer_name if it's not unique.
        with db.transaction.atomic():
            upload_layer_ids = [co['upload_layer_id'] for co in configuration_options]
            upload_layers = UploadLayer.objects.filter(id__in=upload_layer_ids)
            upload_layers_by_id = {ul.id: ul for ul in upload_layers}

            for co in configuration_options:
                ul = upload_layers_by_id[co['upload_layer_id']]
                if co.get('layer_name') is None:
                    co['layer_name'] = ul.layer_name
                elif co['layer_name'] != ul.layer_name:
                    if UploadLayer.objects.filter(layer_name=co['layer_name']).exists():
                        co['layer_name'] = ul.layer_name
                    else:
                        ul.layer_name = co['layer_name']
                        ul.save()

        data, inspector = self.open_source_datastore(filename, *args, **kwargs)

        datastore_layers = inspector.describe_fields()

        if len(datastore_layers) == 0:
            logger.debug('No Dataset found')

        layers_info = []

        # It looks like this code allowed users to configure a portion of layers in the file by specifying an
        # index or a 'layer_name' option.  I'm not sure if lookups by 'layer_name' are still being used anywhere.
        # 'layer_name' now specifies the name to give to a layer on import to geonode.  If the previous
        # behavior is needed, add a 'internal_layer_name' value to the configuration options using the name
        # of the layer the file uses.
        lookup_fields = ['index', 'internal_layer_name']
        for layer_configuration in configuration_options:
            lookup_found = False
            for lf in lookup_fields:
                if lf in layer_configuration:
                    lookup_found = True
                    break

            if not lookup_found:
                logger.warn(
                    'No recognized layer lookup field provided in configuration options, should be one of {}'
                    .format(lookup_fields)
                )
                continue

            for datastore_layer in datastore_layers:
                for lf in lookup_fields:
                    if (lf in datastore_layer and lf in layer_configuration
                            and datastore_layer.get(lf) == layer_configuration.get(lf)):
                        # This update will overwrite the layer_name passed in configuration_options, stash the
                        #    intended name so we can correct it.
                        msg = 'Will configure layer from file {} identifed by field "{}" with value {}'\
                                  .format(self.file, lf, layer_configuration[lf])
                        logger.info(msg)
                        intended_layer_name = layer_configuration.get('layer_name')
                        layer_configuration.update(datastore_layer)
                        if intended_layer_name:
                            layer_configuration.update({'layer_name': intended_layer_name})
                        else:
                            msg = ('layer_name not provided in configuration options, will use name provided '
                                   'by inspector which will likely lead to name collisions')
                            logger.warn(msg)

                        layers_info.append(layer_configuration)

        for layer_options in layers_info:
            if layer_options['layer_type'] == 'tile' and layer_options.get('driver', '').lower() == 'gpkg':
                # No special processing is needed on import, the only thing needed is a copy of the
                #    file which was made on upload.  Config for publishing is done
                #    in handlers.mapproxy.publish_handler.MapProxyGPKGTilePublishHandler
                self.completed_layers.append([layer_options['layer_name'], layer_options])
            elif layer_options['layer_type'] == 'raster':
                """
                File is a raster, we need to convert into optimized GeoTiff
                and skip any further testing or loading into target_store
                """
                #  Increment filename to make sure target doesn't exists
                filedir, filebase = os.path.split(filename)
                outfile = '%s.tif' % os.path.splitext(filebase)[0]
                fileout = increment_filename(os.path.join(RASTER_FILES, outfile))
                raster_import(layer_options['path'], fileout)
                self.completed_layers.append([fileout, layer_options])
            elif layer_options['layer_type'] == 'vector':
                target_file, _ = self.open_target_datastore(self.target_store)
                target_create_options = []

                # Prevent numeric field overflow for shapefiles https://trac.osgeo.org/gdal/ticket/5241
                if target_file.GetDriver().GetName() == 'PostgreSQL':
                    target_create_options.append('PRECISION=NO')

                layer_options['modified_fields'] = {}
                layer = data.GetLayer(layer_options.get('index'))
                layer_name = layer_options['layer_name']
                layer_type = self.get_layer_type(layer, data)
                srs = layer.GetSpatialRef()

                # default the layer to 4326 if a spatial reference is not provided
                if not srs:
                    srs = osr.SpatialReference()
                    srs.ImportFromEPSG(4326)

                # pass the srs authority code to handlers
                if srs.AutoIdentifyEPSG() == 0:
                    layer_options['srs'] = '{0}:{1}'.format(srs.GetAuthorityName(None), srs.GetAuthorityCode(None))
                else:
                    layer_options['srs'] = convert_wkt_to_epsg(srs.ExportToWkt())

                logger.info('Creating dataset "{}" from file "{}"'.format(layer_name, target_file))
                target_layer = self.create_target_dataset(target_file, str(layer_name), srs, layer_type,
                                                          options=target_create_options)

                # adding fields to new layer
                layer_definition = ogr.Feature(layer.GetLayerDefn())
                source_fid = None

                wkb_field = 0

                for i in range(layer_definition.GetFieldCount()):

                    field_def = layer_definition.GetFieldDefnRef(i)

                    if field_def.GetName() == target_layer.GetFIDColumn() and field_def.GetType() != 0:
                        field_def.SetType(0)

                    if field_def.GetName() != 'wkb_geometry':
                        target_layer.CreateField(field_def)
                        new_name = target_layer.GetLayerDefn().GetFieldDefn(i - wkb_field).GetName()
                        old_name = field_def.GetName()

                        if new_name != old_name:
                            layer_options['modified_fields'][old_name] = new_name

                        if old_name == target_layer.GetFIDColumn() and not layer.GetFIDColumn():
                            source_fid = i
                    else:
                        wkb_field = 1

                if wkb_field is not 0:
                    layer.SetIgnoredFields(['wkb_geometry'])

                for feature in layer:
                    if feature and feature.geometry():

                        if not layer.GetFIDColumn():
                            feature.SetFID(-1)

                        if feature.geometry().GetGeometryType() != target_layer.GetGeomType() and \
                                target_layer.GetGeomType() in range(4, 7):

                            conversion_function = ogr.ForceToMultiPolygon

                            if target_layer.GetGeomType() == 5:
                                conversion_function = ogr.ForceToMultiLineString

                            elif target_layer.GetGeomType() == 4:
                                conversion_function = ogr.ForceToMultiPoint

                            geom = ogr.CreateGeometryFromWkb(feature.geometry().ExportToWkb())
                            feature.SetGeometry(conversion_function(geom))

                        if source_fid is not None:
                            feature.SetFID(feature.GetField(source_fid))

                        try:
                            target_layer.CreateFeature(feature)

                        except:
                            for field in range(0, feature.GetFieldCount()):
                                if feature.GetFieldType(field) == ogr.OFTString:
                                    try:
                                        feature.GetField(field).decode('utf8')
                                    except UnicodeDecodeError:
                                        feature.SetField(field, decode(feature.GetField(field)))
                                    except AttributeError:
                                        continue
                            try:
                                target_layer.CreateFeature(feature)
                            except err as e:
                                logger.error('Create feature failed: {0}'.format(gdal.GetLastErrorMsg()))
                                raise e
                layer.ResetReading()
                self.completed_layers.append([target_layer.GetName(), layer_options])
            else:
                msg = 'Unexpected layer type: "{}"'.format(layer_options['layer_type'])
                logger.error(msg)
                raise Exception(msg)

        return self.completed_layers
