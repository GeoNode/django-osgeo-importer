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
        # We only want to process GeoPackage tile layers here.
        if layer_config.get('layer_type', '').lower() == 'tile' and layer_config.get('driver', '').lower() == 'gpkg':
            # Since the config process is for all layers in a file, we only need to do it for the first layer
            if layer_config['index'] == 0:
                logger.info('First layer of a geopackage file containing tiles; generating config.')
                # --- Generate the config for mapproxy to serve the layers from this layer's file.
                uploaded_path = layer_config.get('path')
                config = conf_from_geopackage(uploaded_path)
                MapProxyCacheConfig.objects.create(gpkg_filepath=uploaded_path, config=config)

                # --- Update the config file on disk.
                config_path = os.path.join(settings.MAPPROXY_CONFIG_DIR, settings.MAPPROXY_CONFIG_FILENAME)
                individual_yaml_configs = [yaml.load(mpcc.config) for mpcc in MapProxyCacheConfig.objects.all()]
                combined_yaml = combine_mapproxy_yaml(individual_yaml_configs)
                combined_config = yaml.dump(combined_yaml)
                with open(config_path, 'w') as config_file:
                    config_file.write(combined_config)
            else:
                logger.debug('Additional layer of a geopackage file containing tiles, index "{}"; doing nothing.'
                                .format(layer_config['index']))
        else:
            msg = 'Not a geopackage file, ignoring in this handler'
            logger.info(msg)
