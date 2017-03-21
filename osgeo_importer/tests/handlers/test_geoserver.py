# Needed to ignore 'geonode' name which appears in this package & grab the one we want.
from __future__ import absolute_import

from geonode.geoserver.helpers import gs_catalog
import logging

from django.test import SimpleTestCase
from geoserver.catalog import FailedRequestError

from osgeo_importer.handlers.geoserver import ensure_workspace_exists, GeoserverPublishHandler


class TestHandlerFunctions(SimpleTestCase):

    def test_ensure_workspace_exists(self):
        ws_name = 'nonexistent-workspace'
        ws_namespace_uri = 'http://nonamespace.com'

        # Ensure that the workspace doesn't exist
        ws1 = gs_catalog.get_workspace(ws_name)
        if ws1 is not None:
            gs_catalog.delete(ws1)

        ensure_workspace_exists(gs_catalog, ws_name, ws_namespace_uri)
        # Check that the workspace now exists
        ws2 = gs_catalog.get_workspace(ws_name)
        self.assertNotEqual(ws2, None)

        # Run again to ensure a preexisting workspace doesn't throw any exceptions
        ensure_workspace_exists(gs_catalog, ws_name, ws_namespace_uri)

        gs_catalog.delete(ws2)


class TestGeoserverPublishHandler(SimpleTestCase):

    def test_get_or_create_datastore(self):
        # --- Check that it creates a missing datastore
        # No importer needed
        importer = None
        gph = GeoserverPublishHandler(importer)
        connection_string = gph.get_default_store()
        ds_name = connection_string['name']
        # FailedRequestError indicates the data store couldn't be found
        logging.disable(logging.ERROR)
        self.assertRaises(FailedRequestError, gs_catalog.get_store, ds_name)
        logging.disable(logging.NOTSET)

        layer_config = {'geoserver_store': connection_string}
        gph.get_or_create_datastore(layer_config, None)
        ds2 = gs_catalog.get_store(ds_name)
        self.assertNotEqual(ds2, None)
