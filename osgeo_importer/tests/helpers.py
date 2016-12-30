from django.conf import settings
from django import db
import operator


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


class FuzzyFloatCompareDict(object):
    """ borrowed with changes to also compare float values in lists within a dictionary:
        http://stackoverflow.com/questions/13749218/comparing-python-dicts-with-floating-point-values-included
    """
    def __init__(self, iterable=(), float_eq=operator.eq):
        self._float_eq = float_eq
        self._dict = dict(iterable)

    def __getitem__(self, key):
        return self._dict[key]

    def __setitem__(self, key, val):
        self._dict[key] = val

    def __iter__(self):
        return iter(self._dict)

    def __len__(self):
        return len(self._dict)

    def __contains__(self, key):
        return key in self._dict

    def __eq__(self, other):
        def compare_list_values(a, b):
            if len(a) != len(b):
                return False
            else:
                for item1, item2 in zip(a, b):
                    if not compare(item1, item2):
                        return False
                return True

        def compare(a, b):
            if isinstance(a, float) and isinstance(b, float):
                return self._float_eq(a, b)
            elif isinstance(a, list) and isinstance(b, list):
                return compare_list_values(a, b)
            else:
                return a == b
        try:
            if len(self) != len(other):
                return False
            for key in self:
                if not compare(self[key], other[key]):
                    return False
            return True
        except Exception:
            return False

    def __getattr__(self, attr):
        # free features borrowed from dict
        attr_val = getattr(self._dict, attr)
        if callable(attr_val):
            def wrapper(*args, **kwargs):
                result = attr_val(*args, **kwargs)
                if isinstance(result, dict):
                    return FuzzyFloatCompareDict(result, self._float_eq)
                return result
            return wrapper
        return attr_val

    def __repr__(self):
        return self._dict.__repr__()
