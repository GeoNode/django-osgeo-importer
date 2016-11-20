import copy

from django.contrib.auth import get_user_model
from django.db.models import signals
from django.test import TestCase
from geonode.geoserver.signals import geoserver_post_save

from geonode.layers.models import Layer
from osgeo_importer.handlers.geonode.backward_compatibility import set_attributes_bw_compat as set_attributes


class TestSetAttributes(TestCase):
    """ This is copied & modified from geonode.tests.utils.
        @see backward_compatibility for details.
    """
    def setUp(self):
        # Load users to log in as
        # call_command('loaddata', 'people_data', verbosity=0)
        User = get_user_model()
        User.objects.create_superuser(username='norman', password='norman', email='')

    def test_set_attributes_creates_attributes(self):
        """ Test utility function set_attributes() which creates Attribute instances attached
            to a Layer instance.
        """
        # Creating a layer requires being logged in
        self.client.login(username='norman', password='norman')

        # Disconnect the geoserver-specific post_save signal attached to Layer creation.
        # The geoserver signal handler assumes things about the store where the Layer is placed.
        # this is a workaround.
        disconnected_post_save = signals.post_save.disconnect(geoserver_post_save, sender=Layer)

        # Create dummy layer to attach attributes to
        l = Layer.objects.create(name='dummy_layer')

        # Reconnect the signal if it was disconnected
        if disconnected_post_save:
            signals.post_save.connect(geoserver_post_save, sender=Layer)

        attribute_map = [
            ['id', 'Integer'],
            ['date', 'IntegerList'],
            ['enddate', 'Real'],
            ['date_as_date', 'xsd:dateTime'],
        ]

        # attribute_map gets modified as a side-effect of the call to set_attributes()
        expected_results = copy.deepcopy(attribute_map)

        # set attributes for resource
        set_attributes(l, attribute_map)

        # 2 items in attribute_map should translate into 2 Attribute instances
        self.assertEquals(l.attributes.count(), len(expected_results))

        # The name and type should be set as provided by attribute map
        for a in l.attributes:
            self.assertIn([a.attribute, a.attribute_type], expected_results)
