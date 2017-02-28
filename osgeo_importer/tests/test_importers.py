import os
import shutil

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TestCase

from osgeo_importer.importers import OGRImport
from osgeo_importer.tests.test_settings import _TEST_FILES_DIR
from osgeo_importer.utils import ImportHelper

User = get_user_model()


class OGRImportTests(ImportHelper, TestCase,):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(username='admin', password='admin', email='')

    def test_import_file_uses_uploadlayer_layername(self):
        """ Checks that the unique layer name created by configure_upload() & stored in UploadLayer is used
            as the table name for data stored in PostGIS.
        """
        # --- Prereq's to importing layers
        # my_states.gpkg is a straightforward 1-layer vector package.
        test_filename = 'my_states.gpkg'
        test_filepath = os.path.join(_TEST_FILES_DIR, test_filename)

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

        # should be a single UploadFile resulting from configure_upload()
        upload_file = upload.uploadfile_set.first()
        # should be a single UploadLayer related to upload_file
        upload_layer = upload_file.uploadlayer_set.first()

        # --- Actually do imports (just import_file(), not handlers)
        configuration_options = {'upload_layer_id': upload_layer.id, 'index': 0}
        oi = OGRImport(upload_file.file.name, upload_file=upload_file)
        oi.import_file(configuration_options=configuration_options)

        # --- Check that PostGIS has a table matching the name of the layer set during configure_upload()
        expected_tablename = upload_layer.layer_name
        with connections['datastore'].cursor() as cursor:
            sql = """
                SELECT tablename
                FROM pg_catalog.pg_tables
                WHERE schemaname != 'pg_catalog' AND schemaname != 'information_schema';
            """
            cursor.execute(sql)
            tables = [row[0] for row in cursor.fetchall()]
            self.assertIn(expected_tablename, tables)

    def test_import_file_uses_configured_layername(self):
        """ Checks that if a custom layer name is provided it replaces the UploadLayer name and is used
            as the table name for data stored in PostGIS.
        """
        self.fail('Not yet implemented')

    def test_import_file_skips_duplicate_configured_layername(self):
        """ Checks that if a custom layer name is provided, but is already used the unique layer name
            created by configure_upload() & stored in UploadLayer is used as the table name for data stored
            in PostGIS.
        """
        self.fail('Not yet implemented')
