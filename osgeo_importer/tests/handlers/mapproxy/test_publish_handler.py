import os
from unittest.case import skipUnless

from django.test import TestCase
import mock
from mock.mock import patch, Mock
import yaml

from osgeo_importer.handlers.mapproxy.publish_handler import MapProxyGPKGTilePublishHandler
import osgeo_importer.handlers.mapproxy.publish_handler
from osgeo_importer.models import MapProxyCacheConfig
from osgeo_importer.tests.test_settings import _TEST_FILES_DIR
from django.conf import settings


class TestMapProxyGPKGTilePublishHandler(TestCase):
    adequate_mapproxy_version = False
    try:
        from mapproxy.version import version
        maj_v, min_v = version.split('.')[:2]
        if int(maj_v) == 1 and int(min_v) >= 10:
            adequate_mapproxy_version = True
        else:
            adequate_mapproxy_version = False
    except ImportError:
        adequate_mapproxy_version = False

    @skipUnless(adequate_mapproxy_version, 'Need mapproxy 1.10 or later to test this')
    def test_handle_non_gpkg(self):
        # Should do nothing but log an info-level message.
        with mock.patch.object(osgeo_importer.handlers.mapproxy.publish_handler, 'logger') as call_logger:
            layer_name = 'not_really_a_layer'
            layer_config = {'driver': 'anything_but_gpkg'}
            importer = None
            mpph = MapProxyGPKGTilePublishHandler(importer)
            mpph.handle(layer_name, layer_config)
            self.assertEqual(call_logger.info.call_count, 1)

    @skipUnless(adequate_mapproxy_version, 'Need mapproxy 1.10 or later to test this')
    @patch.object(osgeo_importer.handlers.mapproxy.publish_handler, 'Link')
    @patch.object(osgeo_importer.handlers.mapproxy.publish_handler, 'Layer')
    def test_handle_gpkg(self, MockLayer, MockLink):
        filenames = ['sde-NE2_HR_LC_SR_W_DR.gpkg']
        testing_config_dir = '/tmp'
        testing_config_filename = 'geonode.yaml'

        # Check that each of these files results in the two expected changes:
        #  - A MapProxyCacheConfig model instance pointing to the copy is created
        #  - The mapproxy geopackage cache config file is updated.
        for filename in filenames:
            filepath = os.path.join(_TEST_FILES_DIR, filename)
            layer_name = 'notareallayer'
            layer_type = 'tile'  # This handler ignores layers except tile layers from gpkg files.

            # 'geonode_layer_id' only needs to be present to prevent a KeyError, it's value is insignificant.
            layer_config = {
                'layer_name': layer_name, 'path': filepath, 'driver': 'gpkg', 'layer_type': layer_type, 'index': 0,
                'geonode_layer_id': 1,
            }

            # Set up mock version of geonode.layers.models.Layer to act as if the created layer already exists.
            mock_layer_instance = MockLayer()
            mock_layer_instance.attributes = []
            mock_layer_instance.configure_mock(name='layer_name', resourcebase_ptr=None)
            MockLayer.objects.get = Mock(return_value=mock_layer_instance)

            # Set up mock version of geonode.base.models.Link to check that the code attempts to create a new Link
            #    rather than creating a real Layer with resourcebase_ptr.
            MockLink.objects.create = Mock()

            importer = None
            mpph = MapProxyGPKGTilePublishHandler(importer)

            # Call handle() with directories tweaked for testing.
            test_settings = {
                'MAPPROXY_CONFIG_DIR': testing_config_dir,
                'MAPPROXY_CONFIG_FILENAME': testing_config_filename,
            }
            with self.settings(**test_settings):
                mpph.handle(layer_name, layer_config)

            # --- An instance of MapProxyCacheConfig should have been created
            self.assertEqual(MapProxyCacheConfig.objects.count(), 1)
            mpcc = MapProxyCacheConfig.objects.first()
            self.assertEqual(mpcc.gpkg_filepath, filepath)
            mpcc.delete()

            # --- A mapproxy yaml config with name matching testing_config_filename should be
            #    produced in settings.MAPPROXY_CONFIG_DIR
            conf_path = os.path.join(testing_config_dir, testing_config_filename)
            self.assertTrue(os.path.exists(conf_path))
            os.unlink(conf_path)

            # --- The handler should have tried to create a Link
            MockLink.objects.create.assert_called_once()

    def test_ensure_layer_name_respected(self):
        """ Checks that the 'layer_name' given in the layer configuration is the name given to the layer
            in the mapproxy yaml config created for the layer.  This ensures that the default layer name
            isn't used if a name is provided.
        """
        # Create the mapproxy config directory if it doesn't exist
        try:
            os.makedirs(settings.MAPPROXY_CONFIG_DIR)
        except OSError as ex:
            already_exists_errno = 17
            if ex.errno != already_exists_errno:
                raise

        # This MP handler doesn't use the 'layer' string argument.
        path_to_gpkg_file = os.path.join(_TEST_FILES_DIR, 'gebco.gpkg')
        ignored_layer_arg = 'ignored'
        expected_layer_name = 'my_boring_layer_name'
        layer_config = {
            'layer_type': 'tile', 'driver': 'gpkg', 'path': path_to_gpkg_file, 'index': 0,
            'layer_name': expected_layer_name
        }
        # This handler doesn't rely on an importer
        importer = None
        mpph = MapProxyGPKGTilePublishHandler(importer)
        mpph.handle(ignored_layer_arg, layer_config)
        prepared_config_yaml = MapProxyCacheConfig.objects.first().config
        prepared_config = yaml.load(prepared_config_yaml)
        # The layer name we asked for is the one we got
        self.assertEqual(prepared_config['layers'][0]['name'], expected_layer_name)
        # The layer name we asked for is the name given to the cache entry for that layer
        self.assertIn(expected_layer_name, prepared_config['caches'])
        # The layer name we asked for is the name given to the grid for that layer
        self.assertIn(expected_layer_name, prepared_config['grids'])
        self.assertIn(expected_layer_name, prepared_config['caches'][expected_layer_name]['grids'])
