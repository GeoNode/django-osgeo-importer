from django.test import SimpleTestCase

from osgeo_importer.handlers.mapproxy.conf_geopackage import combine_mapproxy_yaml


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
