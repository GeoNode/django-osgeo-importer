import os
import uuid
import logging

from django import db
from django.conf import settings
from osgeo_importer.handlers import ImportHandlerMixin
from osgeo_importer.handlers import ensure_can_run
from osgeo_importer.models import UploadLayer
from geonode.layers.models import Layer
from backward_compatibility import set_attributes
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)


class GeoNodePublishHandler(ImportHandlerMixin):
    """
    Creates a GeoNode Layer from a layer in Geoserver.
    """

    workspace = 'geonode'

    def store_name(self, layer_config):
        geoserver_publishers = self.importer.filter_handler_results('GeoserverPublishHandler')

        for result in geoserver_publishers:
            for key, feature_type in result.items():
                if feature_type and hasattr(feature_type, 'store'):
                    return feature_type.store.name

        # The layer_config dictionary contains mostly unicode strings so we can't use hasattr here.
        if 'featureType' in layer_config:
            if 'store' in layer_config['featureType']:
                if 'name' in layer_config['featureType']['store']:
                    return layer_config['featureType']['store']['name']

        return db.connections[settings.OSGEO_DATASTORE].settings_dict['NAME']

    def can_run(self, layer, layer_config, *args, **kwargs):
        """
        Skips this layer if the user is appending data to another dataset.
        """
        return 'appendTo' not in layer_config

    @ensure_can_run
    def handle(self, layer, layer_config, *args, **kwargs):
        """
        Adds a layer in GeoNode & adds layer_config['geonode_layer_id'] with id of new layer.

        Handler specific params:
        "layer_owner": Sets the owner of the layer.
        """
        try:
            owner = User.objects.get(username=layer_config['layer_owner'])
        except KeyError:
            logger.warn('No owner specified for layer, using AnonymousUser')
            owner = User.objects.get(username='AnonymousUser')
        except User.DoesNotExist:
            logger.warn('User "{}" not found using AnonymousUser.'.format(layer_config['layer_owner']))
            owner = User.objects.get(username='AnonymousUser')

        # Populate arguments to create a new Layer
        layer_type = layer_config.get('layer_type')
        layer_uuid = str(uuid.uuid4())
        if layer_type == 'raster':
            layer_name = os.path.splitext(os.path.basename(layer))[0]
            store_name = layer_name
            store_type = 'coverageStore'
            fields = None
        elif layer_type == 'vector':
            layer_name = layer
            store_name = self.store_name(layer_config)
            store_type = 'dataStore'
            fields = layer_config['fields']
        elif layer_type == 'tile':
            if 'layer_name' not in layer_config:
                logger.warn('No layer name set, using uuid "{}" as layer name.'.format(layer_uuid))
            layer_name = layer_config.get('layer_name', layer_uuid)
            store_name = layer_config['path']
            store_type = 'tileStore'
            fields = None
        else:
            msg = 'Unexpected layer_type: "{}"'.format(layer_type)
            logger.critical(msg)
            raise Exception(msg)

        workspace_name = self.workspace
        typename = '{}:{}'.format(workspace_name.encode('utf-8'), layer_name.encode('utf-8'))

        new_layer_kwargs = {
            'name': layer_name,
            'workspace': self.workspace,
            'store': store_name,
            'storeType': store_type,
            'typename': typename,
            'title': layer_name,
            "abstract": 'No abstract provided',
            'owner': owner,
            'uuid': layer_uuid,
        }

        new_layer, created = Layer.objects.get_or_create(**new_layer_kwargs)
        layer_config['geonode_layer_id'] = new_layer.id

        # *** It is unclear where the date/time attributes are being created as part of the
        # ***    above get_or_create().  It's probably a geoserver-specific save signal handler,
        # ***    but until it gets tracked down, this will keep set_attributes() from
        # ***    removing them since tests expect to find them.  set_attributes()
        # ***    removes them if they aren't in the fields dict because it thinks
        # ***    the layer is being updated and the new value doesn't include those attributes.
        keep_attributes = ['date', 'date_as_date', 'enddate_as_date', 'time_as_date']
        for a in new_layer.attributes:
            if a.attribute in keep_attributes and a.attribute not in layer_config['fields']:
                layer_config['fields'].append({'name': a.attribute, 'type': a.attribute_type})

        # Add fields to new_layer.attribute_set
        if fields:
            attribute_map = [[f['name'], f['type']] for f in fields]
            set_attributes(new_layer, attribute_map)

        if self.importer.upload_file and created:
            upload_layer = UploadLayer.objects.get(upload_file=self.importer.upload_file.pk,
                                                   index=layer_config.get('index'))
            upload_layer.layer = new_layer
            upload_layer.save()

        if 'permissions' in layer_config:
            new_layer.set_permissions(layer_config['permissions'])
        else:
            new_layer.set_default_permissions()

        results = {
            'stats': {
                'failed': 0,
                'updated': 0,
                'created': 0,
                'deleted': 0,
            },
            'layers': [],
            'deleted_layers': []
        }

        if created:
            results['stats']['created'] += 1
        else:
            results['stats']['updated'] += 1

        layer_info = {'name': layer, 'status': 'created' if created else 'updated'}
        results['layers'].append(layer_info)
        return results
