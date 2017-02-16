# -:- encoding: utf-8 -:-
# This file was sourced from the MapProxy project and modified:
# https://github.com/terranodo/mapproxy/blob/addGeopackageAutoconfig/mapproxy/test/system/test_util_conf.py

# Copyright (C) 2013 Omniscale <http://omniscale.de>
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from __future__ import with_statement

import os
import shutil
import tempfile

from django.test import SimpleTestCase
from nose.tools import eq_
import yaml

from mapproxy.script.conf.app import config_command
from osgeo_importer.handlers.mapproxy.conf_geopackage import get_gpkg_contents, \
    get_table_tile_matrix, get_estimated_tile_res_ratio, get_res_table, get_geopackage_configuration_dict
from mapproxy.test.helper import capture
from osgeo_importer.handlers.mapproxy.conf_geopackage import combine_mapproxy_yaml
from osgeo_importer.tests.test_settings import _TEST_FILES_DIR


def filename(name):
    return os.path.join(_TEST_FILES_DIR, name)


class TestMapProxyConfCmd(SimpleTestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        if os.path.exists(self.dir):
            shutil.rmtree(self.dir)

    def tmp_filename(self, name):
        return os.path.join(
            self.dir,
            name,
        )

    def get_test_gpkg(self):
        return os.path.join(_TEST_FILES_DIR, 'cache.gpkg')

    def test_cmd_no_args(self):
        with capture() as (stdout, stderr):
            assert config_command(['mapproxy-conf']) == 2

        assert '--capabilities required' in stderr.getvalue()

    def test_stdout_output(self):
        with capture(bytes=True) as (stdout, stderr):
            assert config_command(['mapproxy-conf', '--capabilities', filename('util-conf-wms-111-cap.xml')]) == 0

        assert stdout.getvalue().startswith(b'# MapProxy configuration')

    def test_test_cap_output_no_base(self):
        with capture(bytes=True) as (stdout, stderr):
            assert config_command(
                       ['mapproxy-conf',
                        '--capabilities', filename('util-conf-wms-111-cap.xml'),
                        '--output', self.tmp_filename('mapproxy.yaml'), ]) == 0

        with open(self.tmp_filename('mapproxy.yaml'), 'rb') as f:
            conf = yaml.load(f)

            assert 'grids' not in conf
            eq_(conf['sources'], {
                'osm_roads_wms': {
                    'supported_srs': [
                        'CRS:84', 'EPSG:25831', 'EPSG:25832', 'EPSG:25833', 'EPSG:31466', 'EPSG:31467',
                        'EPSG:31468', 'EPSG:3857', 'EPSG:4258', 'EPSG:4326', 'EPSG:900913'],
                    'req': {
                        'layers': 'osm_roads', 'url': 'http://osm.omniscale.net/proxy/service?', 'transparent': True},
                    'type': 'wms',
                    'coverage': {'srs': 'EPSG:4326', 'bbox': [-180.0, -85.0511287798, 180.0, 85.0511287798]}
                },
                'osm_wms': {
                    'supported_srs': [
                        'CRS:84', 'EPSG:25831', 'EPSG:25832', 'EPSG:25833', 'EPSG:31466', 'EPSG:31467', 'EPSG:31468',
                        'EPSG:3857', 'EPSG:4258', 'EPSG:4326', 'EPSG:900913'],
                    'req': {'layers': 'osm', 'url': 'http://osm.omniscale.net/proxy/service?', 'transparent': True},
                    'type': 'wms',
                    'coverage': {
                        'srs': 'EPSG:4326',
                        'bbox': [-180.0, -85.0511287798, 180.0, 85.0511287798],
                    },
                },
            })

            eq_(conf['layers'], [{
                'title': 'Omniscale OpenStreetMap WMS',
                'layers': [
                    {
                        'name': 'osm',
                        'title': 'OpenStreetMap (complete map)',
                        'sources': ['osm_wms'],
                    },
                    {
                        'name': 'osm_roads',
                        'title': 'OpenStreetMap (streets only)',
                        'sources': ['osm_roads_wms'],
                     },
                ]
            }])
            eq_(len(conf['layers'][0]['layers']), 2)

    def test_test_cap_output(self):
        with capture(bytes=True) as (stdout, stderr):
            assert config_command([
                       'mapproxy-conf',
                       '--capabilities', filename('util-conf-wms-111-cap.xml'),
                       '--output', self.tmp_filename('mapproxy.yaml'),
                       '--base', filename('util-conf-base-grids.yaml'),
                   ]) == 0

        with open(self.tmp_filename('mapproxy.yaml'), 'rb') as f:
            conf = yaml.load(f)

            assert 'grids' not in conf
            eq_(len(conf['sources']), 2)

            eq_(conf['caches'], {
                'osm_cache': {
                    'grids': ['webmercator', 'geodetic'],
                    'sources': ['osm_wms']
                },
                'osm_roads_cache': {
                    'grids': ['webmercator', 'geodetic'],
                    'sources': ['osm_roads_wms']
                },
            })

            eq_(conf['layers'], [{
                'title': 'Omniscale OpenStreetMap WMS',
                'layers': [
                    {
                        'name': 'osm',
                        'title': 'OpenStreetMap (complete map)',
                        'sources': ['osm_cache'],
                    },
                    {
                        'name': 'osm_roads',
                        'title': 'OpenStreetMap (streets only)',
                        'sources': ['osm_roads_cache'],
                    },
                ]
            }])
            eq_(len(conf['layers'][0]['layers']), 2)

# # Unable to cleanly port this test without related changes in the unmerged branch it came from.
#     def test_test_gpkg_output(self):
#         with capture(bytes=True) as (stdout, stderr):
#             assert config_command(['mapproxy-conf',
#                                    '--geopackage', filename('cache.gpkg'),
#                                    '--output', self.tmp_filename('mapproxy.yaml'),
#                                    '--base', filename('util-conf-base-grids.yaml'),
#                                    ]) == 0
#
#         with open(self.tmp_filename('mapproxy.yaml'), 'rb') as f:
#             conf = yaml.load(f)
#
#             eq_(conf['grids'], {'cache_900913': {'origin': 'nw', 'srs': 'EPSG:900913',
#                                  'res': [156543.03392804097, 78271.51696402048, 39135.75848201024, 19567.87924100512,
#                                          9783.93962050256, 4891.96981025128, 2445.98490512564, 1222.99245256282,
#                                          611.49622628141, 305.748113140705, 152.8740565703525, 76.43702828517625,
#                                          38.21851414258813, 19.109257071294063, 9.554628535647032, 4.777314267823516,
#                                          2.388657133911758, 1.194328566955879, 0.5971642834779395],
#                                  'bbox': [-20037508.342789244, -20037508.342789244, 20037508.342789244,
#                                           20037508.342789244], 'tile_size': [256, 256]}})
#
#             conf['caches']['cache_cache']['cache']['filename'] = None
#             eq_(conf['caches'], {'cache_cache': {'sources': [], 'cache': {'table_name': 'cache', 'type': 'geopackage',
#                                                          'filename': None},
#                                 'grids': ['cache_900913']}
#             })
#
#             eq_(conf['layers'], [{'sources': ['cache_cache'], 'name': 'cache', 'title': 'cache'}])
#
#             eq_(conf['services'], {'wms': None, 'demo': None, 'tms': {'origin': 'nw', 'use_grid_names': True},
#                           'kml': {'use_grid_names': True}, 'wmts': None})

    def test_overwrites(self):
        with capture(bytes=True) as (stdout, stderr):
            assert config_command([
                           'mapproxy-conf',
                           '--capabilities', filename('util-conf-wms-111-cap.xml'),
                           '--output', self.tmp_filename('mapproxy.yaml'),
                           '--overwrite', filename('util-conf-overwrite.yaml'),
                           '--base', filename('util-conf-base-grids.yaml'),
                       ]) == 0

        with open(self.tmp_filename('mapproxy.yaml'), 'rb') as f:
            conf = yaml.load(f)

            assert 'grids' not in conf
            eq_(len(conf['sources']), 2)

            eq_(conf['sources'], {
                'osm_roads_wms': {
                    'supported_srs': ['EPSG:3857'],
                    'req': {
                        'layers': 'osm_roads', 'url': 'http://osm.omniscale.net/proxy/service?',
                        'transparent': True, 'param': 42},
                    'type': 'wms',
                    'coverage': {'srs': 'EPSG:4326', 'bbox': [0, 0, 90, 90]}
                },
                'osm_wms': {
                    'supported_srs': [
                        'CRS:84', 'EPSG:25831', 'EPSG:25832', 'EPSG:25833', 'EPSG:31466', 'EPSG:31467', 'EPSG:31468',
                        'EPSG:3857', 'EPSG:4258', 'EPSG:4326', 'EPSG:900913'],
                    'req': {
                        'layers': 'osm', 'url': 'http://osm.omniscale.net/proxy/service?',
                        'transparent': True, 'param': 42},
                    'type': 'wms',
                    'coverage': {
                        'srs': 'EPSG:4326',
                        'bbox': [-180.0, -85.0511287798, 180.0, 85.0511287798],
                    },
                },
            })

            eq_(conf['caches'], {
                'osm_cache': {
                    'grids': ['webmercator', 'geodetic'],
                    'sources': ['osm_wms'],
                    'cache': {
                        'type': 'sqlite'
                    },
                },
                'osm_roads_cache': {
                    'grids': ['webmercator'],
                    'sources': ['osm_roads_wms'],
                    'cache': {
                        'type': 'sqlite'
                    },
                },
            })

            eq_(conf['layers'], [{
                'title': 'Omniscale OpenStreetMap WMS',
                'layers': [
                    {
                        'name': 'osm',
                        'title': 'OpenStreetMap (complete map)',
                        'sources': ['osm_cache'],
                    },
                    {
                        'name': 'osm_roads',
                        'title': 'OpenStreetMap (streets only)',
                        'sources': ['osm_roads_cache'],
                     },
                ]
            }])
            eq_(len(conf['layers'][0]['layers']), 2)

    def test_get_gpkg_contents(self):
        returned_contents = get_gpkg_contents(self.get_test_gpkg())
        expected_results = [('cache', 'tiles', 'cache', 'Created with Mapproxy.', '2016-06-10T15:03:39.390Z',
                             - 20037508.342789244, -20037508.342789244, 20037508.342789244, 20037508.342789244, 900913),
                            ('no_spatial_ref_sys', 'tiles', 'test_case', '', '2016-06-13T16:24:03.423Z',
                             - 20037508.3427892, -20037508.3427892, 20037508.3427892, 20037508.3427892,
                             20037508.3427892)]
        eq_(expected_results, returned_contents)

    def test_get_layer_organization_coordsys_id(self):
        returned_contents = get_table_tile_matrix(self.get_test_gpkg(), 'cache')
        expected_results = [(0, 1, 1, 256, 256, 156543.03392804097, 156543.03392804097),
                            (1, 2, 2, 256, 256, 78271.51696402048, 78271.51696402048),
                            (2, 4, 4, 256, 256, 39135.75848201024, 39135.75848201024),
                            (3, 8, 8, 256, 256, 19567.87924100512, 19567.87924100512),
                            (4, 16, 16, 256, 256, 9783.93962050256, 9783.93962050256),
                            (5, 32, 32, 256, 256, 4891.96981025128, 4891.96981025128),
                            (6, 64, 64, 256, 256, 2445.98490512564, 2445.98490512564),
                            (7, 128, 128, 256, 256, 1222.99245256282, 1222.99245256282),
                            (8, 256, 256, 256, 256, 611.49622628141, 611.49622628141),
                            (9, 512, 512, 256, 256, 305.748113140705, 305.748113140705),
                            (10, 1024, 1024, 256, 256, 152.8740565703525, 152.8740565703525),
                            (11, 2048, 2048, 256, 256, 76.43702828517625, 76.43702828517625),
                            (12, 4096, 4096, 256, 256, 38.21851414258813, 38.21851414258813),
                            (13, 8192, 8192, 256, 256, 19.109257071294063, 19.109257071294063),
                            (14, 16384, 16384, 256, 256, 9.554628535647032, 9.554628535647032),
                            (15, 32768, 32768, 256, 256, 4.777314267823516, 4.777314267823516),
                            (16, 65536, 65536, 256, 256, 2.388657133911758, 2.388657133911758),
                            (17, 131072, 131072, 256, 256, 1.194328566955879, 1.194328566955879),
                            (18, 262144, 262144, 256, 256, 0.5971642834779395, 0.5971642834779395)]
        eq_(expected_results, returned_contents)

    def test_get_estimated_tile_res_ratio(self):
        # Test one level
        returned_contents = get_estimated_tile_res_ratio(((0, 1, 1, 256, 256, 156543.03392804097, 156543.03392804097),))
        expected_results = 2
        eq_(expected_results, returned_contents)

        # Test two not contiguous levels
        returned_contents = get_estimated_tile_res_ratio(((0, 1, 1, 256, 256, 156543.03392804097, 156543.03392804097),
                                                          (2, 4, 4, 256, 256, 39135.75848201024, 39135.75848201024)))
        expected_results = 2
        eq_(expected_results, returned_contents)

        # Test two contiguous levels
        returned_contents = get_estimated_tile_res_ratio(((0, 1, 1, 256, 256, 156543.03392804097, 156543.03392804097),
                                                          (1, 2, 2, 256, 256, 39135.75848201024, 39135.75848201024)))
        expected_results = 4
        eq_(expected_results, returned_contents)

    def test_get_res_table(self):
        returned_contents = get_res_table([(5, 32, 32, 256, 256, 4891.96981025128, 4891.96981025128),
                                           (6, 64, 64, 256, 256, 2445.98490512564, 2445.98490512564)])
        expected_results = [156543.03392804097, 78271.51696402048, 39135.75848201024, 19567.87924100512,
                            9783.93962050256, 4891.96981025128, 2445.98490512564, 1222.99245256282, 611.49622628141,
                            305.748113140705, 152.8740565703525, 76.43702828517625, 38.21851414258813,
                            19.109257071294063, 9.554628535647032, 4.777314267823516, 2.388657133911758,
                            1.194328566955879, 0.5971642834779395]
        eq_(expected_results, returned_contents)

    def test_get_geopackage_configuration_dict(self):
        returned_contents = get_geopackage_configuration_dict(self.get_test_gpkg())
        # See if filename is returned, but remove it so that test case can match regardless of install location.
        if returned_contents['caches']['cache_cache']['cache'].get('filename'):
            returned_contents['caches']['cache_cache']['cache']['filename'] = None
        expected_results = {'layers': [{'sources': ['cache_cache'], 'name': 'cache', 'title': 'cache'}],
                            'services': {'wms': None, 'demo': None, 'tms': {'origin': 'nw', 'use_grid_names': True},
                                         'kml': {'use_grid_names': True}, 'wmts': None}, 'grids': {
                'cache_900913': {'origin': 'nw', 'srs': 'EPSG:900913',
                                 'res': [156543.03392804097, 78271.51696402048, 39135.75848201024, 19567.87924100512,
                                         9783.93962050256, 4891.96981025128, 2445.98490512564, 1222.99245256282,
                                         611.49622628141, 305.748113140705, 152.8740565703525, 76.43702828517625,
                                         38.21851414258813, 19.109257071294063, 9.554628535647032, 4.777314267823516,
                                         2.388657133911758, 1.194328566955879, 0.5971642834779395],
                                 'bbox': [-20037508.342789244, -20037508.342789244, 20037508.342789244,
                                          20037508.342789244], 'tile_size': [256, 256]}}, 'caches': {
                'cache_cache': {'sources': [], 'cache': {'table_name': 'cache', 'type': 'geopackage',
                                                         'filename': None},
                                'grids': ['cache_900913']}}}
        eq_(expected_results, returned_contents)


class TestCombineMapproxyYAML(SimpleTestCase):

    def test_combine_mapproxy_yaml(self):
        yaml1 = {
            'layers': [
                {'sources': ['NE2_HR_LC_SR_W_DR_cache'], 'name': 'NE2_HR_LC_SR_W_DR', 'title': 'NE2_HR_LC_SR_W_DR'}
            ],
            'services': {
                'wms': None, 'demo': None, 'kml': {'use_grid_names': True},
                'tms': {'origin': 'nw', 'use_grid_names': True}, 'wmts': None
            },
            'grids': {
                'NE2_HR_LC_SR_W_DR_4326': {
                    'origin': 'nw', 'res': [0.703125, 0.3515625, ], 'srs': 'EPSG:4326',
                    'bbox': [-180.0, -90.000000000036, 180.00000000007202, 90.00000000000001],
                    'tile_size': [256, 256]
                }
            },
            'caches': {
                'NE2_HR_LC_SR_W_DR_cache': {
                    'sources': [],
                    'cache': {
                        'table_name': 'NE2_HR_LC_SR_W_DR', 'type': 'geopackage',
                        'filename': (
                            '/home/jivan/.projects/django-osgeo-importer/osgeo_importer_prj/'
                            'gpkgs_tile/sde-NE2_HR_LC_SR_W_DR.gpkg'
                        )
                    },
                    'grids': ['NE2_HR_LC_SR_W_DR_4326']
                }
            }
        }

        yaml2 = {
            'services': {
                'demo': None,
                'kml': {'use_grid_names': True},
                'tms': {'origin': 'nw', 'use_grid_names': True},
                'wms': None,
                'wmts': None
            },
            'layers': [
                {'name': 'NE2_HR_LC_SR_W_DR2', 'sources': ['NE2_HR_LC_SR_W_DR2_cache'], 'title': 'NE2_HR_LC_SR_W_DR2'}
            ],
            'grids': {
                'NE2_HR_LC_SR_W_DR2_4326': {
                    'bbox': [-180.0, -90.000000000036, 180.00000000007202, 90.00000000000001],
                    'origin': 'nw',
                    'res': [0.703125, 0.3515625, ],
                    'srs': 'EPSG:4326',
                    'tile_size': [256, 256]
                }
            },
            'caches': {
                'NE2_HR_LC_SR_W_DR2_cache': {
                    'cache': {
                        'filename': (
                            '/home/jivan/.projects/django-osgeo-importer/osgeo_importer_prj/gpkgs_tile/'
                            'sde-NE2_HR_LC_SR_W_DR2.gpkg'
                        ),
                        'table_name': 'NE2_HR_LC_SR_W_DR2',
                        'type': 'geopackage'
                    },
                    'grids': ['NE2_HR_LC_SR_W_DR2_4326'],
                    'sources': []
                }
            },
        }

        expected_combined_yaml = {
            'caches': {
                'NE2_HR_LC_SR_W_DR2_cache': {
                    'cache': {
                        'filename': (
                            '/home/jivan/.projects/django-osgeo-importer/osgeo_importer_prj/gpkgs_tile/'
                            'sde-NE2_HR_LC_SR_W_DR2.gpkg'
                        ),
                        'table_name': 'NE2_HR_LC_SR_W_DR2',
                        'type': 'geopackage'
                    },
                    'grids': ['NE2_HR_LC_SR_W_DR2_4326'],
                    'sources': []
                },
                'NE2_HR_LC_SR_W_DR_cache': {
                    'cache': {
                        'filename': (
                            '/home/jivan/.projects/django-osgeo-importer/osgeo_importer_prj/gpkgs_tile/'
                            'sde-NE2_HR_LC_SR_W_DR.gpkg'
                        ),
                        'table_name': 'NE2_HR_LC_SR_W_DR',
                        'type': 'geopackage'
                    },
                    'grids': ['NE2_HR_LC_SR_W_DR_4326'],
                    'sources': []
                }
            },
            'grids': {
                'NE2_HR_LC_SR_W_DR2_4326': {
                    'bbox': [-180.0, -90.000000000036, 180.00000000007202, 90.00000000000001],
                    'origin': 'nw',
                    'res': [0.703125, 0.3515625],
                    'srs': 'EPSG:4326',
                    'tile_size': [256, 256]
                },
                'NE2_HR_LC_SR_W_DR_4326': {
                    'bbox': [-180.0, -90.000000000036, 180.00000000007202, 90.00000000000001],
                    'origin': 'nw',
                    'res': [0.703125, 0.3515625],
                    'srs': 'EPSG:4326',
                    'tile_size': [256, 256]
                }
            },
            'layers': [
                {'name': 'NE2_HR_LC_SR_W_DR', 'sources': ['NE2_HR_LC_SR_W_DR_cache'], 'title': 'NE2_HR_LC_SR_W_DR'},
                {'name': 'NE2_HR_LC_SR_W_DR2', 'sources': ['NE2_HR_LC_SR_W_DR2_cache'], 'title': 'NE2_HR_LC_SR_W_DR2'}
            ],
            'services': {
                'demo': None,
                'kml': {'use_grid_names': True},
                'tms': {'origin': 'nw', 'use_grid_names': True},
                'wms': None,
                'wmts': None
            }
        }

        combined_yaml = combine_mapproxy_yaml([yaml1, yaml2])
        self.maxDiff = None
        self.assertEqual(combined_yaml, expected_combined_yaml)
