import os
import shutil

from django.contrib.auth import get_user_model
from django.test import TestCase

from geonode.layers.models import Layer
from osgeo_importer.tests.helpers import works_with_geoserver
from osgeo_importer.tests.test_settings import _TEST_FILES_DIR
from osgeo_importer.utils import ImportHelper, import_all_layers
import logging


logger = logging.getLogger(__name__)
User = get_user_model()


class ImportUtilityTests(ImportHelper, TestCase,):
    multi_db = True

    def setUp(self):
        self.admin_user = User.objects.create_superuser(username='admin', password='admin', email='')
        self.workspace = 'geonode'

    @works_with_geoserver
    def test_import_all_layers(self):
        test_filenames = [
            'boxes_plus_raster.gpkg',
            # Need to be added to testing files s3 bucket
            # 'san_diego_downtown_generic-osm-data-20161202.gpkg',
            # 'san_diego_downtown-osm-data-20161202.gpkg',
            # 'san_diego_downtown-usgs-imagery-20161202.tight-bounds.gpkg',
        ]
        expected_layer_counts = [8]
        # expected_layer_counts = [8, 3, 16, 1]
        for test_filename, expected_layer_count in zip(test_filenames, expected_layer_counts):
            logger.info('Checking "{}"'.format(test_filename))
            # Drop the imported layers before checking each file to make counting them easier
            Layer.objects.all().delete()

            # --- Upload
            test_username = 'admin'
            test_user = User.objects.get(username=test_username)
            test_filepath = os.path.abspath(os.path.join(_TEST_FILES_DIR, test_filename))

            # Make temporary file (the upload/configure process removes the file & we want to keep our test file)
            tmppath = os.path.join('/tmp', test_filename)
            shutil.copyfile(test_filepath, tmppath)

            # upload & configure_upload expect closed file objects
            #    This is heritage from originally being closely tied to a view passing request.Files
            of = open(tmppath, 'rb')
            of.close()
            files = [of]

            upload = self.upload(files, self.admin_user)
            self.configure_upload(upload, files)
            upload.refresh_from_db()

            n_uploaded_layers = upload.uploadlayer_set.count()
            self.assertEqual(
                n_uploaded_layers, expected_layer_count,
                'Expected {} uploaded layers from file "{}", found {}'
                .format(expected_layer_count, test_filename, n_uploaded_layers)
            )

            import_all_layers(upload, owner=test_user)

            n_imported_layers = Layer.objects.count()
            self.assertEqual(
                n_imported_layers, expected_layer_count,
                'Expected {} imported layers from file "{}", found {}'
                .format(expected_layer_count, test_filename, n_imported_layers)
            )
