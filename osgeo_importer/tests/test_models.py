from django.test import TestCase
from osgeo_importer.models import UploadLayer


class TestUploadLayer(TestCase):

    def test_status(self):
        """ Checks the behavior of the status property.
        """
        # --- Case 1, import_status already set; status() should return value of import_status
        ul = UploadLayer()
        ul.import_status = 'already-set'
        s = ul.status
        self.assertEqual(s, 'already-set')

        # --- Case 2, import_status not set, status() should return 'UNKNOWN'.
        ul = UploadLayer()
        ul.import_status = None
        s = ul.status
        self.assertEqual(s, 'UNKNOWN')
