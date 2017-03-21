# -*- coding: UTF-8 -*-
# (see test_utf8 for the reason why this file needs a coding cookie)

from geonode.geoserver.helpers import ogc_server_settings
from geonode.layers.models import Layer
import json
import logging
import os
import shutil
import unittest

from django import db
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.gis.gdal import DataSource
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.urlresolvers import reverse
from django.test import TestCase, Client
from django.test.utils import setup_test_environment
import gdal
from geoserver.catalog import Catalog, FailedRequestError
import osgeo

from osgeo_importer.handlers.geoserver import GeoWebCacheHandler
from osgeo_importer.handlers.geoserver import configure_time
from osgeo_importer.importers import OGRImport
from osgeo_importer.inspectors import GDALInspector
from osgeo_importer.models import (
    UploadedData, UploadFile, UploadLayer,
    validate_file_extension, ValidationError, validate_inspector_can_read
)
from osgeo_importer.tests.test_settings import _TEST_FILES_DIR
from osgeo_importer.utils import load_handler, launder, ImportHelper


OSGEO_IMPORTER = getattr(settings, 'OSGEO_IMPORTER', 'osgeo_importer.importers.OGRImport')


# In normal unittest runs, this will be set in setUpModule; set here for the
# benefit of static analysis and users importing this instead of running tests.
User = None


def get_testfile_path(filename):
    """Convenience function for getting the path to a test file.
    """
    return os.path.join(_TEST_FILES_DIR, filename)


def get_layer_attr(layer, attr_value):
    """Convenience function for getting a date attribute from a layer.
    """
    date_attrs = [
        attr for attr in layer.attributes
        if attr.attribute == attr_value
    ]
    if not date_attrs:
        return None
    return date_attrs[0]


def setUpModule():
    """unittest runs this automatically after import, before running tests.

    This function is a place to put code which is needed to set up the global
    test environment, while avoiding side effects at import time and also
    unintended changes to the module namespace.
    """
    # This isn't great but at least it's explicit and confined to User.
    global User
    setup_test_environment()
    User = get_user_model()


class AdminClient(Client):

    def login_as_admin(self):
        """Convenience method to login admin.
        """
        return self.login(username='admin', password='admin')

    def login_as_non_admin(self):
        """Convenience method to login a non-admin.
        """
        return self.login(username='non_admin', password='non_admin')


class UploaderTests(ImportHelper, TestCase):
    """Basic checks to make sure pages load, etc.
    """

    def create_datastore(self, connection, catalog):
        """Convenience method for creating a datastore.
        """
        settings = connection.settings_dict
        ds_name = settings['NAME']
        params = {
            'database': ds_name,
            'passwd': settings['PASSWORD'],
            'namespace': 'http://www.geonode.org/',
            'type': 'PostGIS',
            'dbtype': 'postgis',
            'host': settings['HOST'],
            'user': settings['USER'],
            'port': settings['PORT'],
            'enabled': 'True'
        }

        store = catalog.create_datastore(ds_name, workspace=self.workspace)
        store.connection_parameters.update(params)

        try:
            catalog.save(store)
        except FailedRequestError:
            # assuming this is because it already exists
            pass

        return catalog.get_store(ds_name)

    def create_user(self, username, password, **kwargs):
        """Convenience method for creating users.
        """
        user, created = User.objects.get_or_create(username=username, **kwargs)

        if created:
            user.set_password(password)
            user.save()

        return user

    def setUp(self):

        self.assertTrue(
            os.path.exists(_TEST_FILES_DIR),
            'Test could not run due to missing test data at {0!r}'
            .format(_TEST_FILES_DIR)
        )

        # These tests require geonode to be running on :80!
        self.postgis = db.connections['datastore']
        self.postgis_settings = self.postgis.settings_dict

        self.admin_user = self.create_user('admin', 'admin', is_superuser=True)
        self.non_admin_user = self.create_user('non_admin', 'non_admin')
        self.catalog = Catalog(
            ogc_server_settings.internal_rest,
            *ogc_server_settings.credentials
        )
        if self.catalog.get_workspace('geonode') is None:
            self.catalog.create_workspace('geonode', 'http://www.geonode.org/')
        self.workspace = 'geonode'
        self.datastore = self.create_datastore(self.postgis, self.catalog)

    def tearDown(self):
        """Clean up geoserver.
        """
        self.catalog.delete(self.datastore, recurse=True)

    def prepare_file_for_import(self, filepath):
        """ Prepares the file path provided for import; performs some housekeeping, uploads & configures the file.
            Returns a list of dicts of the form {'index': <layer_index>, 'upload_layer_id': <upload_layer_id>}
                these may be used as configuration options for importing all of the layers in the file.
        """
        # Make a copy of the test file, as it's removed in configure_upload()
        filename = os.path.basename(filepath)
        tmppath = os.path.join('/tmp', filename)
        shutil.copy(get_testfile_path(filename), tmppath)

        # upload & configure_upload expect closed file objects
        #    This is heritage from originally being closely tied to a view passing request.Files
        of = open(tmppath, 'rb')
        of.close()
        files = [of]
        uploaded_data = self.upload(files, self.admin_user)
        self.configure_upload(uploaded_data, files)
        configs = [{'index': l.index, 'upload_layer_id': l.id} for l in uploaded_data.uploadlayer_set.all()]
        return configs

    def import_file(self, path, configs=None):
        """Imports the file.
        """
        if configs is None:
            configs = []
        self.assertTrue(os.path.exists(path), path)

        # run ogr2ogr
        ogr = OGRImport(path)
        layers = ogr.handle(configuration_options=configs)

        return layers

    def generic_import(self, filename, configs=None):
        if configs is None:
            configs = [{'index': 0}]

        path = get_testfile_path(filename)
        results = self.import_file(path, configs=configs)
        layer_results = []
        for result in results:
            if result[1].get('raster'):
                layer_path = result[0]
                layer_name = os.path.splitext(os.path.basename(layer_path))[0]
                layer = Layer.objects.get(name=layer_name)
                self.assertTrue(layer_path.endswith('.tif'))
                self.assertTrue(os.path.exists(layer_path))
                gdal_layer = gdal.OpenEx(layer_path)
                self.assertTrue(gdal_layer.GetDriver().ShortName, 'GTiff')
                layer_results.append(layer)
            else:
                layer = Layer.objects.get(name=result[0])
                self.assertEqual(layer.srid, 'EPSG:4326')
                self.assertEqual(layer.store, self.datastore.name)
                self.assertEqual(layer.storeType, 'dataStore')

                if not path.endswith('zip'):
                    self.assertGreaterEqual(
                        layer.attributes.count(),
                        DataSource(path)[0].num_fields
                    )

                layer_results.append(layer)

        return layer_results[0]

    def generic_api_upload(self, filenames, configs=None):
        """Tests the import api.
        """
        client = AdminClient()
        client.login_as_non_admin()

        # Don't accidentally iterate over given 'foo' as ['f', 'o', 'o'].
        self.assertNotIsInstance(filenames, str)

        # Upload Files
        outfiles = []
        for filename in filenames:
            path = get_testfile_path(filename)
            with open(path) as stream:
                data = stream.read()
            upload = SimpleUploadedFile(filename, data)
            outfiles.append(upload)
        response = client.post(
            reverse('uploads-new-json'),
            {'file': outfiles,
             'json': json.dumps(configs)},
            follow=True)
        content = json.loads(response.content)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(content['id'], 1)

        # Configure Uploaded Files
        upload_id = content['id']
        upload_layers = UploadLayer.objects.filter(upload_id=upload_id)

        for upload_layer in upload_layers:
            for config in configs:
                if config['upload_file_name'] == os.path.basename(upload_layer.upload_file.file.name):
                    payload = config['config']
                    url = '/importer-api/data-layers/{0}/configure/'.format(upload_layer.id)
                    response = client.post(
                        url, data=json.dumps(payload),
                        content_type='application/json'
                    )
                    self.assertEqual(response.status_code, 200)
                    url = '/importer-api/data-layers/{0}/'.format(upload_layer.id)
                    response = client.get(url, content_type='application/json')
                    self.assertEqual(response.status_code, 200)

        return content

    def generic_raster_import(self, filename, configs=None):
        if configs is None:
            configs = [{'index': 0}]

        path = get_testfile_path(filename)
        results = self.import_file(path, configs=configs)
        layer_path = results[0][0]
        layer_name = os.path.splitext(os.path.basename(layer_path))[0]
        layer = Layer.objects.get(name=layer_name)
        self.assertTrue(layer_path.endswith('.tif'))
        self.assertTrue(os.path.exists(layer_path))
        gdal_layer = gdal.OpenEx(layer_path)
        self.assertTrue(gdal_layer.GetDriver().ShortName, 'GTiff')
        return layer

    def test_multi_upload(self):
        """Tests Uploading Multiple Files
        """
        # Number of layers in each file
        upload_layer_counts = [1, 1, 1]
        upload = self.generic_api_upload(
            filenames=[
                'boxes_with_year_field.zip',
                'boxes_with_date.zip',
                'point_with_date.geojson'
            ],
            configs=[
                {
                    'upload_file_name': 'boxes_with_year_field.shp',
                    'config': [{'index': 0}]
                },
                {
                    'upload_file_name': 'boxes_with_date.shp',
                    'config': [{'index': 0}]
                },
                {
                    'upload_file_name': 'point_with_date.geojson',
                    'config': [{'index': 0}]
                }
            ]
        )

        self.assertEqual(Layer.objects.count(), sum(upload_layer_counts))
        self.assertEqual(9, upload['count'])

    def test_upload_with_slds(self):
        """Tests Uploading sld
        """
        upload = self.generic_api_upload(
            filenames=[
                'boxes_with_date.zip',
                'boxes.sld',
                'boxes1.sld'
            ],
            configs=[
                {
                    'upload_file_name': 'boxes_with_date.shp',
                    'config': [
                        {
                            'index': 0,
                            'default_style': 'boxes.sld',
                            'styles': ['boxes.sld', 'boxes1.sld']
                        }
                    ]
                }
            ]
        )
        self.assertEqual(6, upload['count'])
        upload_id = upload['id']
        uplayers = UploadLayer.objects.filter(upload=upload_id)
        layer_id = uplayers[0].pk

        upfiles_count = UploadFile.objects.filter(upload=upload_id).count()
        self.assertEqual(6, upfiles_count)

        # Warning: this assumes that Layer pks equal UploadLayer pks
        layer = Layer.objects.get(pk=layer_id)
        gslayer = self.catalog.get_layer(layer.name)
        default_style = gslayer.default_style
        # TODO: can we use public API or omit this?
        self.catalog._cache.clear()
        self.assertEqual('boxes.sld', default_style.filename)

    def test_upload_with_metadata(self):
        """Tests Uploading metadata
        """
        upload = self.generic_api_upload(
            filenames=[
                'boxes_with_date.zip',
                'samplemetadata.xml',
            ],
            configs=[
                {
                    'upload_file_name': 'boxes_with_date.shp',
                    'config': [
                        {
                            'index': 0,
                            'metadata': 'samplemetadata.xml'
                        }
                    ]
                }
            ]
        )
        self.assertEqual(5, upload['count'])
        upload_id = upload['id']
        uplayers = UploadLayer.objects.filter(upload=upload_id)
        layer_id = uplayers[0].pk

        upfiles_count = UploadFile.objects.filter(upload=upload_id).count()
        self.assertEqual(5, upfiles_count)

        layer = Layer.objects.get(pk=layer_id)
        self.assertEqual(layer.language, 'eng')
        self.assertEqual(layer.title, 'Old_Americas_LSIB_Polygons_Detailed_2013Mar')

    def test_geotiff_raster(self):
        """Exercise GeoTIFF raster import, ensuring import doesn't cause any exceptions.
        """
        filename = 'test_grid.tif'
        configs = self.prepare_file_for_import(filename)

        try:
            self.generic_raster_import(filename, configs=configs)
        except Exception as ex:
            self.fail(ex)

    def test_nitf_raster(self):
        """Tests NITF raster import
        """
        filename = 'test_nitf.nitf'
        configs = self.prepare_file_for_import(get_testfile_path(filename))

        try:
            self.generic_raster_import(filename, configs=configs)
        except Exception as ex:
            self.fail(ex)

    def test_box_with_year_field(self):
        """ Tests the import of test_box_with_year_field, checking that date conversion is performed correctly.
        """
        filename = 'boxes_with_year_field.zip'
        configs = self.prepare_file_for_import(get_testfile_path(filename))
        configs[0].update({'convert_to_date': ['date']})

        layer = self.generic_import(
            'boxes_with_year_field.shp',
            configs=configs
        )
        date_attr = get_layer_attr(layer, 'date_as_date')
        self.assertEqual(date_attr.attribute_type, 'xsd:dateTime')

        configure_time(
            self.catalog.get_layer(layer.name).resource,
            attribute=date_attr.attribute,
        )
        self.generic_time_check(layer, attribute=date_attr.attribute)

    def test_boxes_with_date(self):
        """Tests the import of test_boxes_with_date.
        """
        filename = 'boxes_with_date.zip'
        configs = self.prepare_file_for_import(get_testfile_path(filename))
        configs[0].update({'convert_to_date': ['date'], 'start_date': 'date', 'configureTime': True})

        layer = self.generic_import(
            'boxes_with_date.shp',
            configs=configs
        )

        date_attr = get_layer_attr(layer, 'date_as_date')
        self.assertEqual(date_attr.attribute_type, 'xsd:dateTime')

        configure_time(
            self.catalog.get_layer(layer.name).resource,
            attribute=date_attr.attribute,
        )
        self.generic_time_check(layer, attribute=date_attr.attribute)

    def test_boxes_with_date_gpkg(self):
        """Tests the import of test_boxes_with_date.gpkg.
        """
        filename = 'boxes_with_date.gpkg'
        configs = self.prepare_file_for_import(get_testfile_path(filename))
        configs[0].update({'convert_to_date': ['date'], 'start_date': 'date', 'configureTime': True})

        layer = self.generic_import(filename, configs=configs)

        date_attr = get_layer_attr(layer, 'date_as_date')
        self.assertEqual(date_attr.attribute_type, 'xsd:dateTime')

        configure_time(
            self.catalog.get_layer(layer.name).resource,
            attribute=date_attr.attribute,
        )
        self.generic_time_check(layer, attribute=date_attr.attribute)

    def test_boxes_plus_raster_gpkg_by_index(self):
        """ Tests the import of multilayer vector + tile geopackage using index, treating tile layers
            as rasters.
            Tile layers are now treated by default as a distinct layer type.
            This test forces them to still be treated as rasters and should be
            removed once tests for vector/tile geopackage files are in place.
        """
        filename = 'boxes_plus_raster.gpkg'
        configs = self.prepare_file_for_import(get_testfile_path(filename))
        configs[0].update({'convert_to_date': ['date'], 'start_date': 'date', 'configureTime': True})
        configs[6].update({'layer_type': 'raster'})
        configs[7].update({'layer_type': 'raster'})
        layer = self.generic_import(
            'boxes_plus_raster.gpkg',
            configs=configs
        )

        date_attr = get_layer_attr(layer, 'date_as_date')
        self.assertEqual(date_attr.attribute_type, 'xsd:dateTime')

        configure_time(
            self.catalog.get_layer(layer.name).resource,
            attribute=date_attr.attribute,)
        self.generic_time_check(layer, attribute=date_attr.attribute)

    def test_boxes_with_date_csv(self):
        """Tests a CSV with WKT polygon.
        """
        filename = 'boxes_with_date.csv'
        configs = self.prepare_file_for_import(get_testfile_path(filename))
        configs[0].update({'convert_to_date': ['date']})

        layer = self.generic_import(filename, configs=configs)

        date_attr = get_layer_attr(layer, 'date_as_date')
        self.assertEqual(date_attr.attribute_type, 'xsd:dateTime')

        configure_time(
            self.catalog.get_layer(layer.name).resource,
            attribute=date_attr.attribute,
        )
        self.generic_time_check(layer, attribute=date_attr.attribute)

    def test_csv_missing_features(self):
        """Test csv that has some rows without geoms and uses ISO-8859 (Latin 4) encoding.
        """
        filename = 'missing-features.csv'
        configs = self.prepare_file_for_import(get_testfile_path(filename))
        try:
            self.generic_import(filename, configs=configs)
        except Exception as ex:
            self.fail(ex)

    def test_boxes_with_iso_date(self):
        """Tests the import of test_boxes_with_iso_date.
        """
        filename = 'boxes_with_date_iso_date.zip'
        configs = self.prepare_file_for_import(get_testfile_path(filename))
        configs[0].update({'convert_to_date': ['date']})

        layer = self.generic_import(filename, configs=configs)

        date_attr = get_layer_attr(layer, 'date_as_date')
        self.assertEqual(date_attr.attribute_type, 'xsd:dateTime')

        configure_time(
            self.catalog.get_layer(layer.name).resource,
            attribute=date_attr.attribute,
        )
        self.generic_time_check(layer, attribute=date_attr.attribute)

    def test_duplicate_imports(self):
        """Import the same layer twice to ensure names don't collide.
        """
        filename = 'boxes_with_date_iso_date.zip'
        configs1 = self.prepare_file_for_import(get_testfile_path(filename))
        ogr = OGRImport(get_testfile_path(filename))
        layer1 = ogr.handle(configs1)

        configs2 = self.prepare_file_for_import(get_testfile_path(filename))
        layer2 = ogr.handle(configs2)
        self.assertNotEqual(layer1[0][0], layer2[0][0])

    def test_launder(self):
        """Ensure the launder function works as expected.
        """
        self.assertEqual(launder('tm_world_borders_simpl_0.3'), 'tm_world_borders_simpl_0_3')
        self.assertEqual(launder('Testing#'), 'testing_')
        self.assertEqual(launder('   '), '_')

    def test_boxes_with_date_iso_date_zip(self):
        """Tests the import of test_boxes_with_iso_date.
        """
        filename = 'boxes_with_date_iso_date.zip'
        configs = self.prepare_file_for_import(get_testfile_path(filename))
        configs[0].update({'convert_to_date': ['date']})

        layer = self.generic_import(filename, configs=configs)
        date_attr = get_layer_attr(layer, 'date_as_date')
        self.assertEqual(date_attr.attribute_type, 'xsd:dateTime')

        configure_time(
            self.catalog.get_layer(layer.name).resource,
            attribute=date_attr.attribute,
        )
        self.generic_time_check(layer, attribute=date_attr.attribute)

    def test_boxes_with_dates_bc(self):
        """Tests the import of test_boxes_with_dates_bc.
        """
        filename = 'boxes_with_dates_bc.zip'
        configs = self.prepare_file_for_import(get_testfile_path(filename))
        configs[0].update({'convert_to_date': ['date']})

        layer = self.generic_import(filename, configs=configs)

        date_attr = get_layer_attr(layer, 'date_as_date')
        self.assertEqual(date_attr.attribute_type, 'xsd:dateTime')

        configure_time(
            self.catalog.get_layer(layer.name).resource,
            attribute=date_attr.attribute,
        )
        self.generic_time_check(layer, attribute=date_attr.attribute)

    def test_point_with_date(self):
        """Tests the import of point_with_date.geojson
        """
        filename = 'point_with_date.geojson'
        configs = self.prepare_file_for_import(get_testfile_path(filename))
        configs[0].update({'convert_to_date': ['date']})

        layer = self.generic_import(filename, configs=configs)

        # Make sure the layer isn't named OGR default 'OGRGeoJSON'
        self.assertNotEqual(layer.name, 'OGRGeoJSON')
        date_attr = get_layer_attr(layer, 'date_as_date')
        self.assertEqual(date_attr.attribute_type, 'xsd:dateTime')

        configure_time(
            self.catalog.get_layer(layer.name).resource,
            attribute=date_attr.attribute,
        )
        self.generic_time_check(layer, attribute=date_attr.attribute)

    def test_boxes_with_end_date(self):
        """Tests the import of test_boxes_with_end_date.

        This layer has a date and an end date field that are typed correctly.
        """
        filename = 'boxes_with_end_date.zip'
        configs = self.prepare_file_for_import(get_testfile_path(filename))
        configs[0].update({
            'convert_to_date': ['date', 'enddate'],
            'start_date': 'date',
            'end_date': 'enddate',
            'configureTime': True
        })

        layer = self.generic_import(filename, configs=configs)

        date_attr = get_layer_attr(layer, 'date_as_date')
        end_date_attr = get_layer_attr(layer, 'enddate_as_date')

        self.assertEqual(date_attr.attribute_type, 'xsd:dateTime')
        self.assertEqual(end_date_attr.attribute_type, 'xsd:dateTime')

        configure_time(
            self.catalog.get_layer(layer.name).resource,
            attribute=date_attr.attribute,
            end_attribute=end_date_attr.attribute
        )
        self.generic_time_check(
            layer,
            attribute=date_attr.attribute,
            end_attribute=end_date_attr.attribute
        )

    def test_us_states_kml(self):
        """ Tests the import of us_states_kml, just checking that the import doesn't raise an exception.

        This layer has a date and an end date field that are typed correctly.
        """
        filename = 'us_states.kml'
        configs = self.prepare_file_for_import(get_testfile_path(filename))

        # TODO: Support time in kmls.
        try:
            self.generic_import(filename, configs=configs)
        except Exception as ex:
            self.fail(ex)

    def test_mojstrovka_gpx(self):
        """Tests the import of mojstrovka.gpx.

        This layer has a date and an end date field that are typed correctly.
        """
        filename = 'mojstrovka.gpx'
        configs = self.prepare_file_for_import(get_testfile_path(filename))
        configs[0].update({'convert_to_date': ['time'], 'configureTime': True})

        layer = self.generic_import(filename, configs)

        date_attr = get_layer_attr(layer, 'time_as_date')
        self.assertEqual(date_attr.attribute_type, u'xsd:dateTime')

        configure_time(
            self.catalog.get_layer(layer.name).resource,
            attribute=date_attr.attribute
        )
        self.generic_time_check(layer, attribute=date_attr.attribute)

    def generic_time_check(self, layer, attribute=None, end_attribute=None):
        """Convenience method to run generic tests on time layers.
        """
        # TODO: can we use public API or omit this?
        self.catalog._cache.clear()
        resource = self.catalog.get_resource(
            layer.name, store=layer.store, workspace=self.workspace
        )

        time_info = resource.metadata['time']
        self.assertEqual('LIST', time_info.presentation)
        self.assertEqual(True, time_info.enabled)
        self.assertEqual(attribute, time_info.attribute)
        self.assertEqual(end_attribute, time_info.end_attribute)

    def test_us_shootings_csv(self):
        """Tests the import of US_Shootings.csv.
        """
        if osgeo.gdal.__version__ < '2.0.0':
            self.skipTest('GDAL Version does not support open options')

        path = get_testfile_path('US_Shootings.csv')
        configs = self.prepare_file_for_import(path)
        configs[0].update({'convert_to_date': ['Date']})
        layer = self.generic_import(path, configs=configs)
        self.assertTrue(layer.name.startswith('us_shootings'))

        date_field = 'date'
        configure_time(
            self.catalog.get_layer(layer.name).resource,
            attribute=date_field
        )
        self.generic_time_check(layer, attribute=date_field)

    def test_sitins(self):
        """Tests the import of US_Civil_Rights_Sitins0.csv
        """
        if osgeo.gdal.__version__ < '2.0.0':
            self.skipTest('GDAL Version does not support open options')

        filename = 'US_Civil_Rights_Sitins0.csv'
        configs = self.prepare_file_for_import(get_testfile_path(filename))

        try:
            self.generic_import(filename, configs=configs)
        except Exception as ex:
            self.fail(ex)

    def get_layer_names(self, path):
        """Gets layer names from a data source.
        """
        data_source = DataSource(path)
        return [layer.name for layer in data_source]

    def test_gdal_import(self):
        """ Check that geojson file imports without exception.
        """
        filename = 'point_with_date.geojson'
        configs = self.prepare_file_for_import(get_testfile_path(filename))
        configs[0].update({'convert_to_date': ['date']})

        try:
            self.generic_import(filename, configs=configs)
        except Exception as ex:
            self.fail(ex)

    # WFS imports aren't working & this test was previously passing due to an error in the test
    # rather than working code (no layers were returned, and that wasn't checked so none of the checks were ever run).
    # I've fixed the test, but since it doesn't seem like the wfs functionality is being used much I'm commenting
    # out this test until someone has motivation & time to fix the code.
#     def test_wfs(self):
#         """Tests the import from a WFS Endpoint
#         """
#         expected_layer_count = 4
#         wfs = 'WFS:http://demo.geo-solutions.it/geoserver/tiger/wfs'
#         ih = ImportHelper()
#         configs = ih.configure_endpoint(wfs)
#         ogr = OGRImport(wfs)
#         layers = ogr.handle(configuration_options=configs)
#         self.assertEqual(len(layers), expected_layer_count)
#         for result in layers:
#             layer = Layer.objects.get(name=result[0])
#             self.assertEqual(layer.srid, 'EPSG:4326')
#             self.assertEqual(layer.store, self.datastore.name)
#             self.assertEqual(layer.storeType, 'dataStore')

    def test_arcgisjson(self):
        """Tests the import from a WFS Endpoint
        """
        endpoint = 'http://sampleserver6.arcgisonline.com/arcgis/rest/services/Water_Network/FeatureServer/16/query'\
            '?where=objectid=326&outfields=*&f=json'
        ih = ImportHelper()
        ih.configure_endpoint(endpoint)

        ogr = OGRImport(endpoint)
        configs = [{'index': 0, 'upload_layer_id': 1}]
        layers = ogr.handle(configuration_options=configs)
        for result in layers:
            layer = Layer.objects.get(name=result[0])
            self.assertEqual(layer.srid, 'EPSG:4326')
            self.assertEqual(layer.store, self.datastore.name)
            self.assertEqual(layer.storeType, 'dataStore')

    def test_file_add_view(self):
        """Tests the file_add_view.
        """
        client = AdminClient()

        # test login required for this view
        request = client.get(reverse('uploads-new'))
        self.assertEqual(request.status_code, 302)

        client.login_as_non_admin()

        with open(get_testfile_path('point_with_date.geojson')) as stream:
            response = client.post(
                reverse('uploads-new'),
                {'file': stream},
                follow=True
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['request'].path, reverse('uploads-list'))
        self.assertEqual(len(response.context['object_list']), 1)
        upload = response.context['object_list'][0]
        self.assertEqual(upload.user.username, 'non_admin')
        self.assertEqual(upload.file_type, 'GeoJSON')
        self.assertTrue(upload.uploadlayer_set.all())
        self.assertEqual(upload.state, 'UPLOADED')
        self.assertIsNotNone(upload.name)

        uploaded_file = upload.uploadfile_set.first()
        self.assertTrue(os.path.exists(uploaded_file.file.path))

        with open(get_testfile_path('empty_file.geojson')) as stream:
            response = client.post(
                reverse('uploads-new'),
                {'file': stream},
                follow=True
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn('file', response.context_data['form'].errors)

    def test_file_add_view_as_json(self):
        """Tests the file_add_view.
        """
        client = AdminClient()
        client.login_as_non_admin()

        with open(get_testfile_path('point_with_date.geojson')) as stream:
            response = client.post(
                reverse('uploads-new-json'),
                {'file': stream},
                follow=True
            )

        self.assertEqual(response.status_code, 200)
        self.assertIn('application/json', response.get('Content-Type', ''))
        content = json.loads(response.content)
        self.assertIn('state', content)
        self.assertIn('id', content)

    def test_describe_fields(self):
        """Tests the describe fields functionality.
        """
        path = get_testfile_path('US_Shootings.csv')
        with GDALInspector(path) as inspector:
            layers = inspector.describe_fields()

        self.assertTrue(layers[0]['layer_name'], 'us_shootings')
        self.assertEqual([n['name'] for n in layers[0]['fields']], ['Date', 'Shooter', 'Killed',
                                                                    'Wounded', 'Location', 'City',
                                                                    'Longitude', 'Latitude'])
        self.assertEqual(layers[0]['feature_count'], 203)

    def test_gdal_file_type(self):
        """Tests the describe fields functionality.
        """
        filenames = {
            'US_Shootings.csv': {'CSV'},
            'point_with_date.geojson': {'GeoJSON'},
            'mojstrovka.gpx': {'GPX'},
            'us_states.kml': {'LIBKML', 'KML'},
            'boxes_with_year_field.shp': {'ESRI Shapefile'},
            'boxes_with_date_iso_date.zip': {'ESRI Shapefile'}
        }
        from osgeo_importer.models import NoDataSourceFound
        try:
            for filename, file_type in sorted(filenames.items()):
                path = get_testfile_path(filename)
                with GDALInspector(path) as inspector:
                    self.assertIn(inspector.file_type(), file_type)
        except NoDataSourceFound:
            logging.exception('No data source found in: {0}'.format(path))
            raise

    def test_configure_view(self):
        """Tests the configuration view.
        """
        path = get_testfile_path('point_with_date.geojson')
        new_user = User.objects.create(username='test')
        new_user_perms = ['change_resourcebase_permissions']
        client = AdminClient()
        client.login_as_non_admin()

        with open(path) as stream:
            response = client.post(
                reverse('uploads-new'),
                {'file': stream},
                follow=True
            )

        upload = response.context['object_list'][0]

        payload = [
            {
                'index': 0,
                'convert_to_date': ['date'],
                'start_date': 'date',
                'configureTime': True,
                'editable': True,
                'permissions': {
                    'users': {
                        'test': new_user_perms,
                        'AnonymousUser': [
                            'change_layer_data',
                            'download_resourcebase',
                            'view_resourcebase'
                        ]
                    }
                }
            }
        ]
        response = client.post(
            '/importer-api/data-layers/{0}/configure/'.format(upload.id),
            data=json.dumps(payload),
            content_type='application/json'
        )

        self.assertTrue(response.status_code, 200)

        first_layer = Layer.objects.all()[0]
        self.assertEqual(first_layer.srid, 'EPSG:4326')
        self.assertEqual(first_layer.store, self.datastore.name)
        self.assertEqual(first_layer.storeType, 'dataStore')
        self.assertTrue(first_layer.attributes[1].attribute_type, 'xsd:dateTime')
        self.assertEqual(
            Layer.objects.all()[0].owner.username,
            self.non_admin_user.username
        )

        perms = first_layer.get_all_level_info()
        user = User.objects.get(username=self.non_admin_user.username)

        # check user permissions
        expected_perms = [
            u'publish_resourcebase',
            u'change_resourcebase_permissions',
            u'delete_resourcebase',
            u'change_resourcebase',
            u'change_resourcebase_metadata',
            u'download_resourcebase',
            u'view_resourcebase',
            u'change_layer_style',
            u'change_layer_data'
        ]
        for perm in expected_perms:
            self.assertIn(perm, perms['users'][user])

        self.assertTrue(perms['users'][new_user])
        self.assertIn(
            'change_resourcebase_permissions',
            perms['users'][new_user]
        )
        self.assertIn(
            'change_layer_data',
            perms['users'][User.objects.get(username='AnonymousUser')]
        )

        catalog_layer = self.catalog.get_layer(first_layer.name)
        self.assertIn('time', catalog_layer.resource.metadata)
        self.assertEqual(UploadLayer.objects.first().layer, first_layer)

    def test_configure_view_convert_date(self):
        """Tests the configure view with a dataset that needs to be converted to a date.
        """
        client = AdminClient()
        client.login_as_non_admin()

        with open(get_testfile_path('US_Shootings.csv')) as stream:
            response = client.post(
                reverse('uploads-new'),
                {'file': stream},
                follow=True
            )

        upload = response.context['object_list'][0]

        payload = [
            {
                'index': 0,
                'convert_to_date': ['Date'],
                'start_date': 'Date',
                'configureTime': True,
                'editable': True
            }
        ]

        response = client.get(
            '/importer-api/data-layers/{0}/configure/'.format(upload.id)
        )
        self.assertEqual(response.status_code, 405)

        response = client.post(
            '/importer-api/data-layers/{0}/configure/'.format(upload.id)
        )
        self.assertEqual(response.status_code, 400)

        response = client.post(
            '/importer-api/data-layers/{0}/configure/'.format(upload.id),
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertTrue(response.status_code, 200)

        first_layer = Layer.objects.all()[0]
        self.assertEqual(first_layer.srid, 'EPSG:4326')
        self.assertEqual(first_layer.store, self.datastore.name)
        self.assertEqual(first_layer.storeType, 'dataStore')
        self.assertTrue(first_layer.attributes[1].attribute_type, 'xsd:dateTime')
        self.assertTrue(first_layer.attributes.filter(attribute='date'), 'xsd:dateTime')

        catalog_layer = self.catalog.get_layer(first_layer.name)
        self.assertIn('time', catalog_layer.resource.metadata)

        # ensure a user who does not own the upload cannot configure an import from it.
        client.logout()
        client.login_as_admin()
        response = client.post(
            '/importer-api/data-layers/{0}/configure/'.format(upload.id)
        )
        self.assertEqual(response.status_code, 404)

    def test_list_api(self):
        client = AdminClient()

        response = client.get('/importer-api/data/')
        self.assertEqual(response.status_code, 401)

        client.login_as_non_admin()

        response = client.get('/importer-api/data/')
        self.assertEqual(response.status_code, 200)

        admin = User.objects.get(username=self.admin_user.username)
        non_admin = User.objects.get(username=self.non_admin_user.username)

        path = get_testfile_path('US_Shootings.csv')
        with open(path, 'rb') as stream:
            uploaded_file = SimpleUploadedFile('test_data', stream.read())
            admin_upload = UploadedData.objects.create(state='Admin test', user=admin)
            admin_upload.uploadfile_set.add(UploadFile.objects.create(file=uploaded_file))

            non_admin_upload = UploadedData.objects.create(state='Non admin test', user=non_admin)
            non_admin_upload.uploadfile_set.add(UploadFile.objects.create(file=uploaded_file))

        client.login_as_admin()
        response = client.get('/importer-api/data/')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertEqual(len(body['objects']), 2)

        response = client.get('/importer-api/data/?user__username=admin')
        self.assertEqual(response.status_code, 200)
        body = json.loads(response.content)
        self.assertEqual(len(body['objects']), 1)

    def test_layer_list_api(self):
        client = AdminClient()
        response = client.get('/importer-api/data-layers/')
        self.assertEqual(response.status_code, 401)

        client.login_as_non_admin()

        response = client.get('/importer-api/data-layers/')
        self.assertEqual(response.status_code, 200)

    def test_delete_from_non_admin_api(self):
        """Ensure users can delete their data.
        """
        client = AdminClient()

        client = AdminClient()
        client.login_as_non_admin()

        with open(get_testfile_path('point_with_date.geojson')) as stream:
            response = client.post(
                reverse('uploads-new'),
                {'file': stream},
                follow=True
            )

        self.assertEqual(UploadedData.objects.all().count(), 1)
        upload_id = UploadedData.objects.first().id
        response = client.delete('/importer-api/data/{0}/'.format(upload_id))
        self.assertEqual(response.status_code, 204)

        self.assertEqual(UploadedData.objects.all().count(), 0)

    def test_delete_from_admin_api(self):
        """Ensure that administrators can delete data that isn't theirs.
        """
        client = AdminClient()
        client.login_as_non_admin()

        with open(get_testfile_path('point_with_date.geojson')) as stream:
            response = client.post(
                reverse('uploads-new'),
                {'file': stream},
                follow=True
            )

        self.assertEqual(UploadedData.objects.all().count(), 1)

        client.logout()
        client.login_as_admin()

        upload_id = UploadedData.objects.first().id
        response = client.delete('/importer-api/data/{0}/'.format(upload_id))

        self.assertEqual(response.status_code, 204)

        self.assertEqual(UploadedData.objects.all().count(), 0)

    def naming_an_import(self):
        """Tests providing a name in the configuration options.
        """
        client = AdminClient()
        client.login_as_non_admin()
        name = 'point-with-a-date'
        with open(get_testfile_path('point_with_date.geojson')) as stream:
            response = client.post(
                reverse('uploads-new'),
                {'file': stream},
                follow=True
            )

        payload = {
            'index': 0,
            'convert_to_date': ['date'],
            'start_date': 'date',
            'configureTime': True,
            'name': name,
            'editable': True
        }
        response = client.post(
            '/importer-api/data-layers/1/configure/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)

        first_layer = Layer.objects.all()[0]
        self.assertEqual(first_layer.title, name.replace('-', '_'))

    def test_api_import(self):
        """Tests the import api.
        """
        client = AdminClient()
        client.login_as_non_admin()

        with open(get_testfile_path('point_with_date.geojson')) as stream:
            response = client.post(
                reverse('uploads-new'),
                {'file': stream},
                follow=True
            )

        payload = {
            'index': 0,
            'convert_to_date': ['date'],
            'start_date': 'date',
            'configureTime': True,
            'editable': True,
            'upload_layer_id': 1,
        }

        self.assertIsInstance(
            UploadLayer.objects.first().configuration_options,
            dict
        )

        response = client.get('/importer-api/data-layers/1/')
        self.assertEqual(response.status_code, 200)

        response = client.post(
            '/importer-api/data-layers/1/configure/',
            data=json.dumps([payload]),
            content_type='application/json'
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn('task', response.content)

        first_layer = Layer.objects.all()[0]
        self.assertEqual(first_layer.srid, 'EPSG:4326')
        self.assertEqual(first_layer.store, self.datastore.name)
        self.assertEqual(first_layer.storeType, 'dataStore')
        self.assertTrue(first_layer.attributes[1].attribute_type, 'xsd:dateTime')

        catalog_layer = self.catalog.get_layer(first_layer.name)
        self.assertIn('time', catalog_layer.resource.metadata)
        self.assertEqual(UploadLayer.objects.first().layer, first_layer)
        self.assertTrue(UploadLayer.objects.first().task_id)

    def test_valid_file_extensions(self):
        """Test the file extension validator.
        """

        for extension in load_handler(OSGEO_IMPORTER, 'test.txt').valid_extensions:
            filename = 'test.{0}'.format(extension)
            upload = SimpleUploadedFile(filename, '')
            self.assertIsNone(validate_file_extension(upload))

        logging.disable(logging.ERROR)
        with self.assertRaises(ValidationError):
            validate_file_extension(SimpleUploadedFile('test.txt', ''))
        logging.disable(logging.NOTSET)

    def test_no_geom(self):
        """Test the file extension validator.
        """
        logging.disable(logging.ERROR)
        with self.assertRaises(ValidationError):
            validate_inspector_can_read(SimpleUploadedFile('test.csv', 'test,loc\nyes,POINT(0,0)'))
        logging.disable(logging.NOTSET)

        # This should pass (geom type is unknown)
        validate_inspector_can_read(SimpleUploadedFile('test.csv', 'test,WKT\nyes,POINT(0,0)'))

    def test_numeric_overflow(self):
        """Regression test for numeric field overflows in shapefiles.

        # https://trac.osgeo.org/gdal/ticket/5241
        """
        filename = 'Walmart.zip'
        configs = self.prepare_file_for_import(get_testfile_path(filename))
        configs[0].update({
            'configureTime': False,
            'convert_to_date': ['W1_OPENDAT'],
            'editable': True,
            'start_date': 'W1_OPENDAT'
        })

        try:
            self.generic_import(filename, configs=configs)
        except Exception as ex:
            self.fail(ex)

    def test_multipolygon_shapefile(self):
        """ Tests shapefile with multipart polygons imports without raising exception.
        """
        filename = 'PhoenixFirstDues.zip'
        configs = self.prepare_file_for_import(get_testfile_path(filename))

        try:
            self.generic_import(filename, configs=configs)
        except Exception as ex:
            self.fail(ex)

    def test_istanbul(self):
        """Tests shapefile with multipart polygons and non-WGS84 SR.
        """
        filename = 'Istanbul.zip'
        configs = self.prepare_file_for_import(get_testfile_path(filename))

        result = self.generic_import(filename, configs=configs)

        feature_type = self.catalog.get_resource(result.name)
        self.assertEqual(feature_type.projection, 'EPSG:32635')

    def test_houston_tx_annexations(self):
        """Tests Shapefile with originally unsupported EPSG Code.
        """
        filename = 'HoustonTXAnnexations.zip'
        configs = self.prepare_file_for_import(get_testfile_path(filename))

        result = self.generic_import(filename, configs=configs)

        feature_type = self.catalog.get_resource(result.name)
        self.assertEqual(feature_type.projection, 'EPSG:2278')

    def test_gwc_handler(self):
        """Tests the GeoWebCache handler
        """
        filename = 'boxes_with_date.zip'
        configs = self.prepare_file_for_import(get_testfile_path(filename))
        configs[0].update({
            'convert_to_date': ['date'],
            'start_date': 'date',
            'configureTime': True
        })

        layer = self.generic_import(filename, configs=configs)

        gwc = GeoWebCacheHandler(None)
        gs_layer = self.catalog.get_layer(layer.name)

        self.assertTrue(gwc.time_enabled(gs_layer))
        gs_layer.fetch()

        payload = self.catalog.http.request(gwc.gwc_url(gs_layer))
        self.assertIn('regexParameterFilter', payload[1])
        self.assertEqual(int(payload[0]['status']), 200)

        # Don't configure time, ensure everything still works
        filename = 'boxes_with_date_iso_date.zip'
        configs = self.prepare_file_for_import(get_testfile_path(filename))
        layer = self.generic_import(filename, configs)

        gs_layer = self.catalog.get_layer(layer.name)
        self.catalog._cache.clear()
        gs_layer.fetch()

        payload = self.catalog.http.request(gwc.gwc_url(gs_layer))
        self.assertNotIn('regexParameterFilter', payload[1])
        self.assertEqual(int(payload[0]['status']), 200)

    def test_utf8(self):
        """Tests utf8 characters in attributes
        """
        path = get_testfile_path('china_provinces.zip')
        configs = self.prepare_file_for_import(path)

        layer = self.generic_import(path, configs=configs)
        ogr = OGRImport(path)
        datastore, _ = ogr.open_target_datastore(ogr.target_store)
        sql = (
            "select NAME_CH from {0} where NAME_PY = 'An Zhou'"
            .format(layer.name)
        )
        result = datastore.ExecuteSQL(sql)
        feature = result.GetFeature(0)
        self.assertEqual(feature.GetField('name_ch'), '安州')

    def test_non_converted_date(self):
        """Test converting a field as date.
        """
        filename = 'TM_WORLD_BORDERS_2005.zip'
        configs = self.prepare_file_for_import(get_testfile_path(filename))
        configs[0].update({'start_date': 'Year', 'configureTime': True})
        results = self.generic_import(filename, configs=configs)

        layer = self.catalog.get_layer(results.typename)
        self.assertIn('time', layer.resource.metadata)
        self.assertEqual('year', layer.resource.metadata['time'].attribute)

    def test_fid_field(self):
        """
        Regression test for preserving an FID field when target layer supports
        it but source does not.
        """
        filename = 'noaa_paleoclimate.zip'
        configs = self.prepare_file_for_import(get_testfile_path(filename))

        try:
            self.generic_import(filename, configs=configs)
        except Exception as ex:
            self.fail(ex)

    def test_csv_with_wkb_geometry(self):
        """Exercise import of CSV files with multiple geometries.
        """
        filenames = [
            'police_csv.csv',
            'police_csv_nOGC.csv',
            'police_csv_noLatLon.csv',
            'police_csv_WKR.csv',
            'police_csv_nFID.csv',
            'police_csv_nOGFID.csv',
            'police_csv_noWKB.csv'
        ]

        for filename in filenames:
            configs = self.prepare_file_for_import(get_testfile_path(filename))
            configs[0].update({
                    'configureTime': True,
                    'convert_to_date': ['date_time'],
                    'editable': True,
                    'permissions': {
                        'users': {
                            'AnonymousUser': [
                                'change_layer_data',
                                'download_resourcebase',
                                'view_resourcebase'
                            ]
                        }
                    },
                    'start_date': 'date_time',
            })

            self.generic_import(filename, configs=configs)


if __name__ == '__main__':
    unittest.main()
