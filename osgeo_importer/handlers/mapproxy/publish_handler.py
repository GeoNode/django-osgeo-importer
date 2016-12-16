import logging
import os
import shutil
from osgeo_importer.handlers import ImportHandlerMixin
from django.conf import settings
from conf_geopackage import conf_from_geopackage

logger = logging.getLogger(__name__)


class MapProxyGPKGTilePublishHandler(ImportHandlerMixin):

    def handle(self, layer, layer_config, *args, **kwargs):
        if layer_config.get('driver', '').lower() == 'gpkg':
            gpkg_path = layer_config.get('layer_name', '')
            gpkg_filename = os.path.split(gpkg_path)[-1]
            imported_path = os.path.join(settings.GPKG_TILE_STORAGE_DIR, gpkg_filename)
            shutil.copy(gpkg_path, imported_path)

            # Use the filename without any extensions as the base config name
            config_basename = os.path.basename(gpkg_filename).split('.')[0]
            config_filename = '{}.yaml'.format(config_basename)
            config_path = os.path.join(settings.MAPPROXY_CONFIG_DIR, config_filename)
            conf_from_geopackage(imported_path, config_path)
        else:
            msg = 'Not a geopackage file, ignoring in this handler'
            logger.info(msg)
