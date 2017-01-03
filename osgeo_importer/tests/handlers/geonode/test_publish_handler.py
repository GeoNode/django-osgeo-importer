from _collections import defaultdict

from django.test import TestCase

from mock import patch, Mock
from osgeo_importer.handlers.geonode import publish_handler


class TestGeoNodePublishHandler(TestCase):

    @patch.object(publish_handler, 'Layer')
    @patch('osgeo_importer.importers.OGRImport')
    @patch.object(publish_handler, 'User')
    def test_preexisting_layer_reflected_in_results(self, MockUser, MockOGRImport, MockLayer):
        """ Check that the result stats are correct when a layer is updated rather than created.
        """
        # Set up mock version of geonode.layers.models.Layer to act as if the created layer already exists.
        mock_layer_instance = MockLayer()
        mock_layer_instance.attributes = []
        MockLayer.objects.get_or_create = Mock(return_value=(mock_layer_instance, False))

        # Mock a user
        MockUser.objects.get = Mock(return_value='TestUser')

        # Create a GeoNodePublishHandler with mocked importer
        gnph = publish_handler.GeoNodePublishHandler(MockOGRImport())

        # mocked layer & layer config for call to handle()
        mock_layer = 'testlayer'
        mock_layer_config = defaultdict(lambda: None)
        mock_layer_config['layer_type'] = 'tile'  # Any valid layer_type (vector, raster, tile) is fine.

        result = gnph.handle(mock_layer, mock_layer_config)

        self.assertEqual(MockLayer.objects.get_or_create.call_count, 1)
        self.assertEqual(MockUser.objects.get.call_count, 1)
        self.assertEqual(MockOGRImport.call_count, 1)
        self.assertEqual(result['stats']['created'], 0)
        self.assertEqual(result['stats']['updated'], 1)
