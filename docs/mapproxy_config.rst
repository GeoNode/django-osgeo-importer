MapProxy Config
===============

MapProxy
--------

MapProxy is used to serve tiles contained within GeoPackage files.

You'll need a 'geonode' mapproxy instance with its configuration file managed by django-osgeo-importer.
Populate the configuration file with this dummy configuration.  This will allow MapProxy to start
using this configuration and this dummy content will be overwritten when the first GeoPackage file
containing tiles is uploaded::

    caches:
      DUMMY_cache:
        cache: {
          filename: /tmp/nogpkghere,
          table_name: notablehere,
          type: geopackage
        }
        grids: [DUMMY_grid]
        sources: []
    grids:
      DUMMY_grid:
        bbox: [-180.0, -90.0, 180.0, 90.0]
        origin: nw
        res: [0.703125, 0.3515625,]
        srs: EPSG:4326
        tile_size: [256, 256]
    layers:
    - name: DUMMY_layer
      sources: [DUMMY_cache]
      title: DUMMY LAYER
    services:
      demo: null
      kml: {use_grid_names: true}
      tms: {origin: nw, use_grid_names: true}
      wms: null
      wmts: null

Remember, you should not modify this file by hand; its content will be managed by django-osgeo-importer and
rewritten each time a GeoPackage containging tiles is uploaded.

To run the mapproxy server for development:
``mapproxy-util serve-develop <path to above-mentioned config file>``

Django
------

In your project settings you'll need to:
  * add these global variables:

    * MAPPROXY_CONFIG_DIR - This is the full path to the directory where your mapproxy configuration file is located.
    * MAPPROXY_CONFIG_FILENAME - This is the name of the mapproxy configuration file that the importer will manage.
    * MAPPROXY_SERVER_LOCATION - This is a template URL for TMS access to your MapProxy instance.
      For example, if you have set up your webserver to proxy http://myserver.org/geonode-mapproxy/ to your mapproxy
      instance, this would be ``'http://myserver.org/geonode-mapproxy/tms/1.0.0/{layer_name}/{grid_name}'``.
      Note that {layer_name} and {grid_name} are literal, they'll be replaced by a call to string.format().

  * add ``'osgeo_importer.handlers.mapproxy.publish_handler.MapProxyGPKGTilePublishHandler'`` to ``IMPORT_HANDLERS``
    **after** ``'osgeo_importer.handlers.geonode.GeoNodePublishHandler'``.


