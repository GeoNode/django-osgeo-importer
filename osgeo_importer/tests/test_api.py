'''
Created on Nov 9, 2016

@author: jivan
@note: There are probably api tests in tests_original.py that would be better placed here.
'''
import json
import os
import shutil

from django.contrib.auth import get_user_model
from django.test import TestCase

from geonode.layers.models import Layer
from osgeo_importer.models import UploadedData
from osgeo_importer.tests.test_settings import _TEST_FILES_DIR
from osgeo_importer.utils import ImportHelper
from osgeo_importer.tests.helpers import works_with_geoserver


User = get_user_model()


class UploadedDataResourceTests(ImportHelper, TestCase,):

    def setUp(self):
        self.admin_user = User.objects.create_superuser(username='admin', password='admin', email='')
        self.workspace = 'geonode'

    @works_with_geoserver
    def test_import_all_layers(self):
        # --- Upload
        test_filename = 'boxes_plus_raster.gpkg'
        expected_layer_count = 8
        test_username = 'admin'
        test_password = 'admin'
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

        ud = UploadedData.objects.get(name=test_filename)
        n_uploaded_layers = ud.uploadlayer_set.count()
        self.assertEqual(
            n_uploaded_layers, expected_layer_count,
            'Expected {} uploaded layers from this file, found {}'.format(expected_layer_count, n_uploaded_layers)
        )

        configure_all_url = '/importer-api/data/{}/import_all_layers'.format(ud.id)
        self.client.login(username=test_username, password=test_password)
        response = self.client.get(configure_all_url, follow=True)

        self.assertEqual(response.status_code, 200)
        result = json.loads(response.content)
        self.assertEqual(result['layer_count'], expected_layer_count)

        n_imported_layers = Layer.objects.count()
        self.assertEqual(
            n_imported_layers, expected_layer_count,
            'Expected {} imported layers from this file, found {}'.format(expected_layer_count, n_imported_layers)
        )
