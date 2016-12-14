import os

from django.test import SimpleTestCase

from osgeo_importer.inspectors import OGRInspector, GDALInspector, GPKGTileInspector
from osgeo_importer.tests.helpers import FuzzyFloatCompareDict
from osgeo_importer.tests.test_settings import _TEST_FILES_DIR
from osgeo_importer.utils import NoDataSourceFound


def check_inspector_open_bad_connection(test_case, InspectorClass):
    """ Checks that InspectorClass.open() raises NoDataSourceFound if connection_string is invalid or non-existent.
    """
    invalid_connection_string = 'adfadfjadoafdpoiuafdopui'
    nonexistent_connection_string = '/tmp/nofilehere'
    inspector_invalid = InspectorClass(invalid_connection_string)
    inspector_nonexistent = InspectorClass(nonexistent_connection_string)

    test_case.assertRaises(NoDataSourceFound, inspector_invalid.open)
    test_case.assertRaises(NoDataSourceFound, inspector_nonexistent.open)


class TestOGRInspector(SimpleTestCase):
    def test_open_bad_connection(self):
        check_inspector_open_bad_connection(self, OGRInspector)


class TestGDALInspector(SimpleTestCase):
    def test_open_bad_connection(self):
        check_inspector_open_bad_connection(self, GDALInspector)


class TestGPKGTileInspector(SimpleTestCase):
    def test_describe_fields(self):
        # [ <basic gpkg with tiles> ]
        filenames = ['sde-NE2_HR_LC_SR_W_DR.gpkg']
        # Each element is a list of dicts for one of the above files one, one dict for each tile layer found.
        expected_describe_field_results = {
            'sde-NE2_HR_LC_SR_W_DR.gpkg': [
                    {
                        'index': 0, 'srs_id': 4326, 'layer_name': u'NE2_HR_LC_SR_W_DR',
                        'latlong_bbox': [-180.0, -90.0, 180.0, 90.0]
                    },
                ]
            }

        for filename in filenames:
            filepath = os.path.join(_TEST_FILES_DIR, filename)
            expected_result = expected_describe_field_results[filename]
            with GPKGTileInspector(filepath) as insp:
                def float_eq(a, b):
                    return abs(a - b) < 0.001

                detail_list = [
                    FuzzyFloatCompareDict(d, float_eq=float_eq) for d in insp.describe_fields()
                ]
                expected_detail_list = [
                    FuzzyFloatCompareDict(d, float_eq=float_eq) for d in expected_result
                ]

                self.assertEqual(len(detail_list), len(expected_detail_list))
                for d, ed in zip(detail_list, expected_detail_list):
                    msg = '\n{}\n !=\n{}'.format(d, ed)
                    self.assertEqual(d, ed, msg)
