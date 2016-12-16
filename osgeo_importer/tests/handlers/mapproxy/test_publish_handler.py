import os

from django.test import SimpleTestCase
import mock

from osgeo_importer.handlers.mapproxy.publish_handler import MapProxyGPKGTilePublishHandler
import osgeo_importer.handlers.mapproxy.publish_handler
from osgeo_importer.tests.test_settings import _TEST_FILES_DIR
from unittest.case import skipUnless


class TestMapProxyGPKGTilePublishHandler(SimpleTestCase):
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
        with mock.patch.object(osgeo_importer.handlers.mapproxy.publish_handler, 'logger') as logger:
            layer_name = 'not_really_a_layer'
            layer_config = {'driver': 'anything_but_gpkg'}
            importer = None
            mpph = MapProxyGPKGTilePublishHandler(importer)
            mpph.handle(layer_name, layer_config)
            self.assertEqual(logger.info.call_count, 1)

    @skipUnless(adequate_mapproxy_version, 'Need mapproxy 1.10 or later to test this')
    def test_handle_gpkg(self):
        filenames = ['sde-NE2_HR_LC_SR_W_DR.gpkg']
        testing_storage_dir = '/tmp'

        # Check that each of these files results in the two expected files being created.
        for filename in filenames:
            filepath = os.path.join(_TEST_FILES_DIR, filename)

            layer_name = 'notareallayer'
            layer_config = {'layer_name': filepath, 'driver': 'gpkg'}
            importer = None
            mpph = MapProxyGPKGTilePublishHandler(importer)

            # Call handle() with directories tweaked for testing.
            with self.settings(GPKG_TILE_STORAGE_DIR=testing_storage_dir, MAPPROXY_CONFIG_DIR=testing_storage_dir):
                mpph.handle(layer_name, layer_config)

            # A copy of the gpkg file should be made to settings.GPKG_TILE_STORAGE_DIR
            copy_path = os.path.join(testing_storage_dir, filename)
            self.assertTrue(os.path.exists(copy_path))
            os.unlink(copy_path)

            # A mapproxy yaml config should be produced in settings.MAPPROXY_CONFIG_DIR
            conf_basename = filename.split('.')[0]
            conf_filename = '{}.yaml'.format(conf_basename)
            conf_path = os.path.join(testing_storage_dir, conf_filename)
            self.assertTrue(os.path.exists(conf_path))
            os.unlink(conf_path)
