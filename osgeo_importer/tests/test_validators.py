import os
from django.test import TestCase
from osgeo_importer.validators import ALL_OK_EXTENSIONS, valid_file
from osgeo_importer.tests.test_settings import _TEST_FILES_DIR


class ValidatorTests(TestCase):

    def test_valid_file(self):
        valid_single_filepath = os.path.join(_TEST_FILES_DIR, 'boxes_plus_raster.gpkg')
        valid_shapefile_filepath = os.path.join(_TEST_FILES_DIR, 'Spring_2015.zip')
        valid_multifile_zip_filepath = os.path.join(_TEST_FILES_DIR, 'pescadero--eventkit-20170201.zip')
        valid_nested_zip_filepath = os.path.join(_TEST_FILES_DIR, 'nested.zip')

        with open(valid_single_filepath, 'rb') as valid_single_file, \
                open(valid_shapefile_filepath, 'rb') as valid_shapefile, \
                open(valid_multifile_zip_filepath, 'rb') as valid_multifile_zip_file, \
                open(valid_nested_zip_filepath, 'rb') as valid_nested_zip_file:
            self.assertEqual(valid_file(valid_single_file), [])
            self.assertEqual(valid_file(valid_shapefile), [])
            self.assertEqual(valid_file(valid_multifile_zip_file), [])
            self.assertEqual(valid_file(valid_nested_zip_file), [])

        invalid_filepath = os.path.join(_TEST_FILES_DIR, 'example.pdf')
        # Make sure the 'pdf' extension for our invalid_file hasn't been added to the list of extensions.
        _, ext = os.path.splitext(invalid_filepath)
        ext = ext.lstrip('.').lower()
        self.assertNotIn(ext, ALL_OK_EXTENSIONS)
        with open(invalid_filepath, 'rb') as invalid_file:
            # The invalid file should return an error
            expected_errors = [
                'example.pdf: "pdf" not found in VALID_EXTENSIONS, NONDATA_EXTENSIONS'
            ]
            self.assertEqual(valid_file(invalid_file), expected_errors)
