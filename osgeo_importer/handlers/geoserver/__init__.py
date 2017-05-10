import os
import logging
import requests
from decimal import Decimal, InvalidOperation
from django import db
from django.conf import settings
from osgeo_importer.handlers import ImportHandlerMixin, GetModifiedFieldsMixin, ensure_can_run
from osgeo_importer.importers import UPLOAD_DIR
from geoserver.catalog import FailedRequestError, ConflictingDataError
from geonode.geoserver.helpers import gs_catalog
from geonode.upload.utils import make_geogig_rest_payload, init_geogig_repo
from geoserver.support import DimensionInfo
from osgeo_importer.utils import increment_filename, database_schema_name
import re

logger = logging.getLogger(__name__)


def ensure_workspace_exists(catalog, workspace_name, workspace_namespace_uri):
    ws = catalog.get_workspace(workspace_name)
    if ws is None:
        logger.info('Creating workspace "{}"'.format(workspace_name))
        catalog.create_workspace(workspace_name, workspace_namespace_uri)
    else:
        logger.info('Found workspace "{}"'.format(workspace_name))


def configure_time(resource, name='time', enabled=True, presentation='LIST', resolution=None, units=None,
                   unitSymbol=None, **kwargs):
    """
    Configures time on a geoserver resource.
    """
    time_info = DimensionInfo(name, enabled, presentation, resolution, units, unitSymbol, **kwargs)
    resource.metadata = {'time': time_info}
    return resource.catalog.save(resource)


class GeoserverHandlerMixin(ImportHandlerMixin):
    """
    A Mixin for Geoserver handlers.
    """
    catalog = gs_catalog


class GeoServerTimeHandler(GetModifiedFieldsMixin, GeoserverHandlerMixin):
    """
    Enables time in Geoserver for a layer.
    """

    def can_run(self, layer, layer_config, *args, **kwargs):
        """
        Returns true if the configuration has enough information to run the handler.
        """

        if not layer_config.get('configureTime', None):
            return False

        if not any([layer_config.get('start_date', None), layer_config.get('end_date', None)]):
            return False

        return True

    @ensure_can_run
    def handle(self, layer, layer_config, *args, **kwargs):
        """
        Configures time on the object.

        Handler specific params:
        "configureTime": Must be true for this handler to run.
        "start_date": Passed as the start time to Geoserver.
        "end_date" (optional): Passed as the end attribute to Geoserver.
        """

        lyr = self.catalog.get_layer(layer)
        self.update_date_attributes(layer_config)
        configure_time(lyr.resource, attribute=layer_config.get('start_date'),
                       end_attribute=layer_config.get('end_date'))


class GeoserverPublishHandler(GeoserverHandlerMixin):
    workspace = 'geonode'
    workspace_namespace_uri = 'http://www.geonode.org/'
    srs = 'EPSG:4326'  # This should probably come from the imported data instead of assumed

    def can_run(self, layer, layer_config, *args, **kwargs):
        """
        Returns true if the configuration has enough information to run the handler.
        """
        if layer_config.get('raster'):
            return False
        return True

    def get_default_store(self):
        connection = db.connections[settings.OSGEO_DATASTORE]
        db_settings = connection.settings_dict

        return {
              'database': db_settings['NAME'],
              'schema': database_schema_name(),
              'passwd': db_settings['PASSWORD'],
              'type': 'PostGIS',
              'dbtype': 'postgis',
              'host': db_settings['HOST'],
              'user': db_settings['USER'],
              'port': db_settings['PORT'],
              'enabled': 'True',
              'name': db_settings['NAME']}

    @staticmethod
    def multiprocess_safe_create_store(catalog, conn_str, workspace_name):
        """ *catalog*: geoserver catalog object
            *conn_str*: connection string defining the details for creating the store
            *workspace_name*: name of the geoserver workspaace to create the store in.
        """
        try:
            store = catalog.create_datastore(conn_str['name'], workspace=workspace_name)
            store.connection_parameters.update(conn_str)
            catalog.save(store)
            s = catalog.get_store(conn_str['name'])
        except FailedRequestError:
            # A failed request to create the datastore can be the result of a race condition with
            # multiple celery worker processes, check if the store still doesn't exist before re-raising.
            try:
                s = catalog.get_store(conn_str['name'])
                # No error, It was a race condition with one of the other processes creating the store first, carry on.
            except:
                raise
        return s

    def get_or_create_datastore(self, layer_config, request_user):
        connection_string = layer_config.get('geoserver_store')
        default_connection_string = self.get_default_store()

        # If no connection is specified or geogig is requested use default (geogig no longer supported)
        if connection_string is None:
            use_conn_str = default_connection_string
        else:
            use_conn_str = connection_string

        # Create a geoserver workspace named self.workspace if one doesn't already exist
        ensure_workspace_exists(self.catalog, self.workspace, self.workspace_namespace_uri)

        if use_conn_str is None:
            raise Exception('No connection string available to create datastore')

        try:
            s = self.catalog.get_store(use_conn_str['name'])
        except FailedRequestError:
            # Couldn't get the store, try creating it.
            if connection_string is not None:
                if connection_string['type'] == 'geogig':
                    if request_user is not None:
                        username = request_user.username
                        useremail = request_user.email
                        payload = make_geogig_rest_payload(username, useremail)
                    else:
                        payload = make_geogig_rest_payload()
                    init_response = init_geogig_repo(payload, connection_string['name'])
                    headers, body = init_response

                    if self.geogig_version() >= 1.1:
                        # Enable automatic spatial, time and elevation indexing for Geogig 1.1+
                        use_conn_str['autoIndexing'] = 'true'
            s = self.multiprocess_safe_create_store(self.catalog, use_conn_str, self.workspace)

        # Override with default store if a geogig store was requested but geogig isn't configured
        if (s.type is None and use_conn_str.get('type') == 'geogig'):
            if connection_string is not None:
                self.catalog.delete(s)
                msg = 'GeoGig is requested but not configured on geoserver instance, '\
                      'overriding connection "{}" with default "{}"'\
                      .format(connection_string, default_connection_string)
                logger.warn(msg)
                use_conn_str = connection_string

            layer_config['geoserver_store'] = use_conn_str

            try:
                s = self.catalog.get_store(use_conn_str['name'])
            except FailedRequestError:
                s = self.multiprocess_safe_create_store(self.catalog, use_conn_str, self.workspace)

        return s

    def geogig_handler(self, store, layer, layer_config, request_user):
        """
        Facilitates the workflow required to import data from PostGIS into GeoGIG via the GeoGIG-Geoserver
        REST interface.
        """

        # Accept-Encoding: identity handles a work-around for
        # handling double gzipped GeoGIG responses: https://github.com/locationtech/geogig/issues/9.
        request_params = dict(auth=(self.catalog.username, self.catalog.password),
                              headers={'Accept-Encoding': 'identity'})

        repo = store.name
        repo_url = self.catalog.service_url.replace('/rest', '/geogig/repos/{0}/'.format(repo))
        transaction_url = repo_url + 'beginTransaction.json'
        transaction = requests.get(transaction_url, **request_params)

        if request_user is not None:
            author_name = request_user.username
            author_email = request_user.email
        else:
            author_name = None
            author_email = None

        logger.debug("""response status_code {} \n
                        response headers {} \n
                        request headers {} \n
                     """.format(transaction.status_code,
                                transaction.headers,
                                transaction.request.headers))

        transaction_id = transaction.json()['response']['Transaction']['ID']
        default_params = self.get_default_store()

        params = {
          'host': default_params['host'],
          'user': default_params['user'],
          'password': default_params['passwd'],
          'port': default_params['port'],
          'database': default_params['database'],
          'schema': default_params['schema'],
          'table': layer,
          'transactionId': transaction_id
        }

        import_command = requests.get(repo_url + 'postgis/import.json', params=params, **request_params)
        task = import_command.json()['task']

        status = 'NOT RUN'
        while status != 'FINISHED':
            check_task = requests.get(task['href'], **request_params)
            status = check_task.json()['task']['status']

        if status == 'FINISHED':
            requests.get(repo_url + 'add.json', params={'transactionId': transaction_id}, **request_params)
            requests.get(repo_url + 'commit.json', params={'transactionId': transaction_id,
                                                           'authorName': author_name,
                                                           'authorEmail': author_email}, **request_params)
            requests.get(repo_url + 'endTransaction.json', params={'transactionId': transaction_id}, **request_params)

    @ensure_can_run
    def handle(self, layer, layer_config, *args, **kwargs):
        """
        Publishes a layer to GeoServer.

        Handler specific params:
        "geoserver_store": Connection parameters used to get/create the geoserver store.
        "srs": The native srs authority and code (ie EPSG:4326) for this data source.
        """
        # GeoServer doesn't handle tiles from gpkg files correctly, don't attempt
        if layer_config['layer_type'] == 'tile' and layer_config.get('driver', '').lower() == 'gpkg':
            return

        request_user = kwargs.get('request_user', None)
        store = self.get_or_create_datastore(layer_config, request_user)

        store_type = getattr(store, 'type', None) or ''
        if store_type.lower() == 'geogig':
            self.geogig_handler(store, layer, layer_config, request_user)

        return self.catalog.publish_featuretype(layer, self.get_or_create_datastore(layer_config, request_user),
                                                layer_config.get('srs', self.srs))

    def geogig_version(self):
        """
        Will retrieve the geogig version from Geoserver. Defaults to 1.0.
        """
        version_url = "{}/about/manifest.json".format(self.catalog.service_url)
        version = 1.0
        try:
            resp = requests.get(version_url, auth=(self.catalog.username, self.catalog.password))
            for dep in resp.json()['about']['resource']:
                if 'geogig-api' in dep['@name']:
                    version = dep['Implementation-Version']
                    break
        except (TypeError, KeyError, requests.exceptions.ReadTimeout, requests.exceptions.ConnectionError):
            return 1.0

        if isinstance(version, float):
            return version
        elif isinstance(version, basestring):
            pattern = re.compile("\d+.\d+")
            return float(pattern.search(version).group(0))


class GeoserverPublishCoverageHandler(GeoserverHandlerMixin):
    workspace_name = 'geonode'
    workspace_namespace_uri = 'http://www.geonode.org'

    def can_run(self, layer, layer_config, *args, **kwargs):
        """
        Returns true if the configuration has enough information to run the handler.
        """
        if layer_config.get('raster'):
            return True

        return False

    @ensure_can_run
    def handle(self, layer, layer_config, *args, **kwargs):
        """
        Publishes a Coverage layer to GeoServer.
        """
        name = os.path.splitext(os.path.basename(layer))[0]
        ensure_workspace_exists(self.catalog, self.workspace_name, self.workspace_namespace_uri)
        workspace = self.catalog.get_workspace(self.workspace_name)

        return self.catalog.create_coveragestore(name, layer, workspace, False)


class GeoWebCacheHandler(GeoserverHandlerMixin):
    """
    Configures GeoWebCache for a layer in Geoserver.
    """

    @staticmethod
    def config(**kwargs):
        return """<?xml version="1.0" encoding="UTF-8"?>
            <GeoServerLayer>
              <name>{name}</name>
              <enabled>true</enabled>
              <mimeFormats>
                <string>image/png</string>
                <string>image/jpeg</string>
                <string>image/png8</string>
              </mimeFormats>
              <gridSubsets>
                <gridSubset>
                  <gridSetName>EPSG:900913</gridSetName>
                </gridSubset>
                <gridSubset>
                  <gridSetName>EPSG:4326</gridSetName>
                </gridSubset>
                <gridSubset>
                  <gridSetName>EPSG:3857</gridSetName>
                </gridSubset>
              </gridSubsets>
              <metaWidthHeight>
                <int>4</int>
                <int>4</int>
              </metaWidthHeight>
              <expireCache>0</expireCache>
              <expireClients>0</expireClients>
              <parameterFilters>
                {regex_parameter_filter}
                <styleParameterFilter>
                  <key>STYLES</key>
                  <defaultValue/>
                </styleParameterFilter>
              </parameterFilters>
              <gutter>0</gutter>
            </GeoServerLayer>""".format(**kwargs)

    def can_run(self, layer, layer_config, *args, **kwargs):
        """
        Only run this handler if the layer is found in Geoserver.
        """
        self.layer = self.catalog.get_layer(layer)

        if self.layer:
            return True

        return

    @staticmethod
    def time_enabled(layer):
        """
        Returns True is time is enabled for a Geoserver layer.
        """
        return 'time' in (getattr(layer.resource, 'metadata', []) or [])

    def gwc_url(self, layer):
        """
        Returns the GWC URL given a Geoserver layer.
        """

        return self.catalog.service_url.replace('rest', 'gwc/rest/layers/{workspace}:{layer_name}.xml'.format(
            workspace=layer.resource.workspace.name, layer_name=layer.name))

    @ensure_can_run
    def handle(self, layer, layer_config, *args, **kwargs):
        """
        Adds a layer to GWC.
        """
        regex_filter = ""
        time_enabled = self.time_enabled(self.layer)

        if time_enabled:
            regex_filter = """
                <regexParameterFilter>
                  <key>TIME</key>
                  <defaultValue/>
                  <regex>.*</regex>
                </regexParameterFilter>
                """

        return self.catalog.http.request(self.gwc_url(self.layer), method="POST",
                                         body=self.config(regex_parameter_filter=regex_filter, name=self.layer.name))


class GeoServerBoundsHandler(GeoserverHandlerMixin):
    """
    Sets the lat/long bounding box of a layer to the max extent of WGS84 if the values of the current lat/long
    bounding box fail the Decimal quantize method (which Django uses internally when validating decimals).

    This can occur when the native bounding box contain Infinity values.
    """

    def can_run(self, layer, layer_config, *args, **kwargs):
        """
        Only run this handler if the layer is found in Geoserver.
        """
        self.catalog._cache.clear()
        self.layer = self.catalog.get_layer(layer)

        if self.layer:
            return True

        return

    @ensure_can_run
    def handle(self, layer, layer_config, *args, **kwargs):
        resource = self.layer.resource
        try:
            for dec in map(Decimal, resource.latlon_bbox[:4]):
                dec.quantize(1)

        except InvalidOperation:
            resource.latlon_bbox = ['-180', '180', '-90', '90', 'EPSG:4326']
            self.catalog.save(resource)


class GenericSLDHandler(GeoserverHandlerMixin):
    """
    Handles cases in Geoserver 2.8x+ where the generic sld is used.  The generic style causes service exceptions.
    """

    def can_run(self, layer, layer_config, *args, **kwargs):
        """
        Only run this handler if the layer is found in Geoserver and the layer's style is the generic style.
        """
        self.catalog._cache.clear()
        self.layer = self.catalog.get_layer(layer)

        return self.layer and self.layer.default_style and self.layer.default_style.name == 'generic'

    @ensure_can_run
    def handle(self, layer, layer_config, *args, **kwargs):
        """
        Replace the generic layer with the 'point' layer.
        """
        self.layer.default_style = 'point'
        self.catalog.save(self.layer)


class GeoServerStyleHandler(GeoserverHandlerMixin):
    """Adds styles to GeoServer Layer
    """
    catalog = gs_catalog
    catalog._cache.clear()
    workspace = 'geonode'

    def can_run(self, layer, layer_config, *args, **kwargs):
        """
        Returns true if the configuration has enough information to run the handler.
        """
        if not any([layer_config.get('default_style', None), layer_config.get('styles', None)]):
            return False

        return True

    @ensure_can_run
    def handle(self, layer, layer_config, *args, **kwargs):
        """
        Handler specific params:
        "default_sld": SLD to load as default_sld
        "slds": SLDS to add to layer
        """
        lyr = self.catalog.get_layer(layer)
        path = os.path.join(UPLOAD_DIR, str(self.importer.upload_file.upload.id))
        default_sld = layer_config.get('default_style', None)
        slds = layer_config.get('styles', None)
        all_slds = []
        if default_sld is not None:
            slds.append(default_sld)

        all_slds = list(set(slds))
        # all_slds = [CheckFile(x) for x in all_slds if x is not None]

        styles = []
        default_style = None
        for sld in all_slds:
            with open(os.path.join(path, sld)) as s:
                n = 0
                sldname = os.path.splitext(sld)[0]
                while True:
                    n += 1
                    try:
                        self.catalog.create_style(sldname, s.read(), overwrite=False, workspace=self.workspace)
                    except ConflictingDataError:
                        sldname = increment_filename(sldname)
                    if n >= 100:
                        break

                style = self.catalog.get_style(sldname, workspace=self.workspace)
                if sld == default_sld:
                    default_style = style
                styles.append(style)

        lyr.styles = list(set(lyr.styles + styles))
        if default_style is not None:
            lyr.default_style = default_style
        self.catalog.save(lyr)
        return {'default_style': default_style.filename}
