import logging
import os
import shutil

from django.conf import settings
import yaml

from conf_geopackage import conf_from_geopackage
from osgeo_importer.handlers import ImportHandlerMixin
from osgeo_importer.handlers.mapproxy.conf_geopackage import combine_mapproxy_yaml
from osgeo_importer.models import MapProxyCacheConfig


logger = logging.getLogger(__name__)


class MapProxyGPKGTilePublishHandler(ImportHandlerMixin):

    def handle(self, layer, layer_config, *args, **kwargs):
        """ If the layer is a geopackage file, make a copy, generate a config to serve the layer,
            and update the mapproxy config file.
        """
        if layer_config.get('driver', '').lower() == 'gpkg':
            # --- Copy the gpkg file
            gpkg_path = layer_config.get('layer_name', '')
            gpkg_filename = os.path.split(gpkg_path)[-1]
            imported_path = os.path.join(settings.GPKG_TILE_STORAGE_DIR, gpkg_filename)
            shutil.copy(gpkg_path, imported_path)

            # --- Generate the config for mapproxy to serve this layer.
            config = conf_from_geopackage(imported_path)
            MapProxyCacheConfig.objects.create(gpkg_filepath=imported_path, config=config)

            # --- Update the config file on disk.
            config_path = os.path.join(settings.MAPPROXY_CONFIG_DIR, settings.MAPPROXY_CONFIG_FILENAME)
            individual_yaml_configs = [yaml.load(mpcc.config) for mpcc in MapProxyCacheConfig.objects.all()]
            combined_yaml = combine_mapproxy_yaml(individual_yaml_configs)
            combined_config = yaml.dump(combined_yaml)
            with open(config_path, 'w') as config_file:
                config_file.write(combined_config)
        else:
            msg = 'Not a geopackage file, ignoring in this handler'
            logger.info(msg)
