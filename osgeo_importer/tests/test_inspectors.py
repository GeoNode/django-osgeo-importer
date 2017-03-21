from django.test import SimpleTestCase
from osgeo_importer.inspectors import OGRInspector, GDALInspector
from osgeo_importer.utils import NoDataSourceFound
import logging


def check_inspector_open_bad_connection(test_case, InspectorClass):
    """ Checks that InspectorClass.open() raises NoDataSourceFound if connection_string is invalid or non-existent.
    """
    invalid_connection_string = 'adfadfjadoafdpoiuafdopui'
    nonexistent_connection_string = '/tmp/nofilehere'
    inspector_invalid = InspectorClass(invalid_connection_string)
    inspector_nonexistent = InspectorClass(nonexistent_connection_string)

    logging.disable(logging.ERROR)
    test_case.assertRaises(NoDataSourceFound, inspector_invalid.open)
    test_case.assertRaises(NoDataSourceFound, inspector_nonexistent.open)
    logging.disable(logging.NOTSET)


class TestOGRInspector(SimpleTestCase):
    def test_open_bad_connection(self):
        check_inspector_open_bad_connection(self, OGRInspector)


class TestGDALInspector(SimpleTestCase):
    def test_open_bad_connection(self):
        check_inspector_open_bad_connection(self, GDALInspector)
