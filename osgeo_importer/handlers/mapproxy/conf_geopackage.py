""" This code originated from
    https://github.com/terranodo/mapproxy/blob/addGeopackageAutoconfig/mapproxy/script/conf/geopackage.py
"""
from logging import getLogger
import yaml
import sqlite3
import os

logger = getLogger(__name__)


def combine_mapproxy_yaml(yaml_dict_list):
    """ Returns a single yaml config document with the contents of each of these dictionaries
        from each yaml document in *yaml_list* merged:
            caches, grids, layers, services
    """
    single_yaml = {'grids': {}, 'caches': {}, 'services': {}, 'layers': []}
    merge_dict_keys = ['grids', 'caches', 'services']
    for yaml_dict in yaml_dict_list:
        for merge_key in merge_dict_keys:
            try:
                for key, item in yaml_dict[merge_key].items():
                    single_yaml[merge_key][key] = item
            except KeyError:
                logger.warn('Did not find key "{}" in yaml config'.format(merge_key))

        try:
            for layer in yaml_dict['layers']:
                if layer not in single_yaml['layers']:
                    single_yaml['layers'].append(layer)
        except KeyError:
            logger.warn('Did not find key "layers" in yaml config')

    return single_yaml


def conf_from_geopackage(geopackage_path, output_filepath=None):
    """ Returns a yaml configuration for mapproxy to serve 'geopackage_path' as a cache containing tiles.
        If output_filepath is not None, also writes the configuration to it.
    """
    # Import these here so this code doesn't interfere on installations that don't configure MapProxy
    from mapproxy.config.spec import validate_options
    from mapproxy.config.loader import load_configuration_file

    conf = get_geopackage_configuration_dict(geopackage_path)
    yaml.SafeDumper.add_representer(
        type(None),
        lambda dumper, value: dumper.represent_scalar(u'tag:yaml.org,2002:null', '')
    )

    yaml_conf = yaml.safe_dump(conf, default_flow_style=False)

    if output_filepath:
        with open(output_filepath, 'w') as outfile:
            outfile.write(yaml_conf)
        fdir, fname = os.path.split(output_filepath)
        # configuration dict
        cd = load_configuration_file([fname], fdir)
        errors, informal_only = validate_options(cd)
        if len(errors) > 0 and informal_only is False:
            raise Exception('Invalid configuration: {}'.format(errors))
        elif len(errors) > 0 and informal_only is True:
            logger.warn('Non-critical errors in yaml produced by conf_from_geopackage(): {}'.format(output_filepath))

    return yaml_conf


def get_gpkg_contents(geopackage_file, data_type='tiles'):
    """
    :param geopackage_file: Path to the geopackage file.
    :param data_type: The type of layer to return tiles or features.
    :return: One or more tuples with the table_name, min_x, min_y, max_x, max_y, srs_id
        for each layer in the geopackage.
    """
    with sqlite3.connect(geopackage_file) as db:
        cur = db.execute("SELECT table_name, data_type, identifier, description, last_change, min_x, min_y, max_x, "
                         "max_y, srs_id "
                         "FROM gpkg_contents WHERE data_type = ?", (data_type,))
    return cur.fetchall()


def get_table_organization_coordsys_id(geopackage_file, srs_id):
    """
    :param geopackage_file: Path to the geopackage file.
    :param srs_id: The srs_id which is the key value in the organization_coordsys_id.
    :return: An integer representing the organization_coordsys_id as an EPSG code.
    """
    with sqlite3.connect(geopackage_file) as db:
        cur = db.execute("SELECT organization_coordsys_id FROM gpkg_spatial_ref_sys WHERE srs_id = ?", (srs_id,))
    results = cur.fetchone()
    if results:
        return results[0]


def get_table_tile_matrix(geopackage_file, table_name):
    """
    :param geopackage_file: Path to the geopackage file.
    :param table_name: The table_name associated with the tile_matrix data.
    :return: A tuple of tuple containing zoom_level, matrix_width, matrix_height, tile_width, tile_height, pixel_x_size,
    pixel_y_size for each zoom_level.
    """

    with sqlite3.connect(geopackage_file) as db:
        cur = db.execute(
            "SELECT zoom_level, matrix_width, matrix_height, tile_width, tile_height, pixel_x_size, pixel_y_size "
            "FROM gpkg_tile_matrix WHERE table_name = ?"
            "ORDER BY zoom_level", (table_name,)
        )
        return cur.fetchall()


def get_estimated_tile_res_ratio(tile_matrix):
    """

    :param tile_matrix: A tuple of tuples representing the geopackage tile matrix (without the table name included).
    :return: The rate at which the resolution increases between levels.
    """
    default_res_factor = 2
    if len(tile_matrix) < 2:
        return default_res_factor
    layer = tile_matrix[0]
    next_layer = tile_matrix[1]
    return (layer[6] / next_layer[6]) / (next_layer[0] - layer[0])


def get_res_table(tile_matrix):
    res_ratio = get_estimated_tile_res_ratio(tile_matrix)
    res_table = []
    if tile_matrix[0][0] == 0:
        first_level_res = tile_matrix[0][5]
    else:
        first_level_res = tile_matrix[0][5] * (res_ratio ** tile_matrix[0][0])
    tile_matrix_set = {}
    for level in tile_matrix:
        tile_matrix_set[level[0]] = level
    if not tile_matrix_set.get(0):
        res_table += [first_level_res]
    else:
        res_table += [tile_matrix_set.get(0)[5]]
    for level in range(1, 19):
        res = tile_matrix_set.get(level)
        if not res:
            res_table += [first_level_res / (res_ratio ** level)]
        else:
            res_table += [res[5]]
    return res_table


def get_geopackage_configuration_dict(geopackage_file):
    gpkg_contents = get_gpkg_contents(geopackage_file, data_type='tiles')
    conf = {'grids': {},
            'caches': {},
            'layers': [],
            'services': {'demo': None,
                         'tms': {'use_grid_names': True, 'origin': 'nw'},
                         'kml': {'use_grid_names': True},
                         'wmts': None,
                         'wms': None}}

    for gpkg_content in gpkg_contents:
        table_name = str(gpkg_content[0])
        tile_matrix = get_table_tile_matrix(geopackage_file, table_name)
        srs = get_table_organization_coordsys_id(geopackage_file, gpkg_content[9])
        if not tile_matrix or not srs:
            continue
        conf['grids']['{0}_{1}'.format(table_name, srs)] = {
            'srs': 'EPSG:{0}'.format(srs),
            'tile_size': [tile_matrix[0][3], tile_matrix[0][4]],
            'bbox': [gpkg_content[5], gpkg_content[6], gpkg_content[7], gpkg_content[8]],
            'res': get_res_table(tile_matrix),
            'origin': 'nw'
        }
        conf['caches']['{0}_cache'.format(table_name)] = {
            'sources': [],
            'grids': ['{0}_{1}'.format(table_name, srs)],
            'cache': {
                'type': 'geopackage',
                'filename': os.path.abspath(geopackage_file),
                'table_name': table_name
            }
        }
        conf['layers'] += [{'name': table_name, 'title': table_name, 'sources': ['{0}_cache'.format(table_name)]}]
    return conf
