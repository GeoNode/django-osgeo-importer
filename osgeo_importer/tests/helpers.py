from django.conf import settings


def works_with_geoserver(wrapped_func):
    """ A decorator for test methods with functionality that should work with or without geoserver
            configured in settings.
        Some signal handlers in geonode.geoserver presume a geoserver workspace is configured.
        This decorator makes sure that is true if geonode.geoserver is in INSTALLED_APPS.
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
                self.catalog = Catalog(
                    ogc_server_settings.internal_rest,
                    *ogc_server_settings.credentials
                )
                if self.catalog.get_workspace(workspace_name) is None:
                    self.catalog.create_workspace(workspace_name, 'http://www.geonode.org/')

                ret = wrapped_func(self, *args, **kwargs)

                return ret
        else:
            wrapper = wrapped_func
    else:
        # workspace setup not needed, don't bother wrapping the function
        wrapper = wrapped_func

    return wrapper
