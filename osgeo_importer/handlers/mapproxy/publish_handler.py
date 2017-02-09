from geonode.base.models import Link
from geonode.layers.models import Layer
import logging
import os

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
            update the mapproxy config file, and configure a wms link to access the tiles.
        """
        # We only want to process GeoPackage tile layers here.
        if layer_config.get('layer_type', '').lower() == 'tile' and layer_config.get('driver', '').lower() == 'gpkg':
            # Since the config process is for all layers in a file, we only need to do it for the first layer
            uploaded_path = layer_config.get('path')
            # Accomodate layer_config without an index.
            if ('index' not in layer_config and
                    not MapProxyGPKGTilePublishHandler.objects.exists(gpkg_filepath=uploaded_path)):
                configure = True
            elif layer_config['index'] == 0:
                configure = True
            else:
                configure = False

            if configure:
                logger.info('First layer of a geopackage file containing tiles; generating config.')
                # --- Generate the config for mapproxy to serve the layers from this layer's file.
                config_yaml = conf_from_geopackage(uploaded_path)

                config_dict = yaml.load(config_yaml)
                if len(config_dict['layers']) > 1:
                    logger.warn('Handling multiple geopackage tile layers from the same file is not implemented')
                layer_name = layer_config['layer_name']
                # Use the layer name for the name of the cache and grid, this ensures they're also
                #  unique and it's easy for someone checking the config to see how they link together.
                default_cache_name = config_dict['caches'].keys()[0]
                config_dict['caches'] = {layer_name: config_dict['caches'][default_cache_name]}
                config_dict['caches'][layer_name]['grids'] = [layer_name]

                default_grid_name = config_dict['grids'].keys()[0]
                config_dict['grids'] = {layer_name: config_dict['grids'][default_grid_name]}
                # override the default name provided by conf_from_geopackage with the one from layer_config
                config_dict['layers'][0]['name'] = layer_name
                config_dict['layers'][0]['sources'] = [layer_name]
                config_dict['layers'][0]['title'] = layer_name
                config_yaml = yaml.safe_dump(config_dict)
                MapProxyCacheConfig.objects.create(gpkg_filepath=uploaded_path, config=config_yaml)

                # --- Update the config file on disk.
                config_path = os.path.join(settings.MAPPROXY_CONFIG_DIR, settings.MAPPROXY_CONFIG_FILENAME)
                individual_yaml_configs = [yaml.load(mpcc.config) for mpcc in MapProxyCacheConfig.objects.all()]
                combined_yaml = combine_mapproxy_yaml(individual_yaml_configs)
                combined_config = yaml.dump(combined_yaml)
                with open(config_path, 'w') as config_file:
                    config_file.write(combined_config)

                # --- Configure a tms link for this layer
                if 'geonode_layer_id' in layer_config:
                    geonode_layer_id = layer_config['geonode_layer_id']
                    geonode_layer = Layer.objects.get(id=geonode_layer_id)
                    layer_name = geonode_layer.name
                    # Grab the grid name given to the grid for this layer by conf_from_geopackage()
                    grid_name = config_dict['grids'].keys()[0]
                    link_url = settings.MAPPROXY_SERVER_LOCATION.format(layer_name=layer_name, grid_name=grid_name)
                    Link.objects.create(
                        extension='html', link_type='TMS', name='Tiles-MapProxy', mime='text/html',
                        url=link_url, resource=geonode_layer.resourcebase_ptr
                    )
                else:
                    logger.warn('No geonode_layer_id provided, layer is imported but Link metadata was not created')
            else:
                logger.debug(
                    'Additional layer of a geopackage file containing tiles, index "{}"; doing nothing.'
                    .format(layer_config['index'])
                )
        else:
            msg = 'Not a geopackage file, ignoring in this handler'
            logger.info(msg)
