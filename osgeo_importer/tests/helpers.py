from django.conf import settings
from django import db


def create_datastore(workspace_name, connection, catalog):
    """Convenience method for creating a datastore.
    """
    from geoserver.catalog import FailedRequestError
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

    store = catalog.create_datastore(ds_name, workspace=workspace_name)
    store.connection_parameters.update(params)

    try:
        catalog.save(store)
    except FailedRequestError:
        # assuming this is because it already exists
        pass

    return catalog.get_store(ds_name)


def works_with_geoserver(wrapped_func):
    """ A decorator for test methods with functionality that should work with or without geoserver
            configured in settings.
        Some signal handlers in geonode.geoserver presume a geoserver workspace and datastore are configured.
        This decorator makes sure that is true during the test if geonode.geoserver is in INSTALLED_APPS and they get
        torn down appropriately afterwards.
    """
    if 'geonode.geoserver' in settings.INSTALLED_APPS:
        try:
            from geonode.geoserver.helpers import ogc_server_settings
            from geoserver.catalog import Catalog
            can_set_up_geoserver_workspace = True
        except ImportError:
            can_set_up_geoserver_workspace = False

        if can_set_up_geoserver_workspace:
            def wrapper(self, *args, **kwargs):
                workspace_name = 'geonode'
                django_datastore = db.connections['datastore']

                catalog = Catalog(
                    ogc_server_settings.internal_rest,
                    *ogc_server_settings.credentials
                )
                # Set up workspace/datastore as appropriate
                ws = catalog.get_workspace(workspace_name)
                delete_ws = False
                if ws is None:
                    ws = catalog.create_workspace(workspace_name, 'http://www.geonode.org/')
                    delete_ws = True

                datastore = create_datastore(workspace_name, django_datastore, catalog)

                # test method called here
                try:
                    ret = wrapped_func(self, *args, **kwargs)
                finally:
                    # Tear down workspace/datastore as appropriate
                    if delete_ws:
                        catalog.delete(ws, recurse=True)
                    else:
                        catalog.delete(datastore, recurse=True)

                return ret
        else:
            wrapper = wrapped_func
    else:
        # workspace setup not needed, don't bother wrapping the function
        wrapper = wrapped_func

    return wrapper
