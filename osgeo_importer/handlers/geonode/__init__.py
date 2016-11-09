import logging
import os
import uuid

from django import db
from django.conf import settings
from django.contrib.auth import get_user_model

from geonode.layers.metadata import set_metadata
from geonode.layers.models import Layer
from geonode.layers.utils import resolve_regions
from osgeo_importer.handlers import ImportHandlerMixin
from osgeo_importer.handlers import ensure_can_run
from osgeo_importer.importers import UPLOAD_DIR
from osgeo_importer.models import UploadLayer
from backward_compatibility import set_attributes

User = get_user_model()
logger = logging.getLogger(__name__)


class GeoNodePublishHandler(ImportHandlerMixin):
    """
    Creates a GeoNode Layer from a layer in Geoserver.
    """

    workspace = 'geonode'

    @property
    def store_name(self):
        geoserver_publishers = self.importer.filter_handler_results('GeoserverPublishHandler')

        for result in geoserver_publishers:
            for key, feature_type in result.items():
                if feature_type and hasattr(feature_type, 'store'):
                    return feature_type.store.name

        return db.connections[settings.OSGEO_DATASTORE].settings_dict['NAME']

    def can_run(self, layer, layer_config, *args, **kwargs):
        """
        Skips this layer if the user is appending data to another dataset.
        """
        return 'appendTo' not in layer_config

    @ensure_can_run
    def handle(self, layer, layer_config, *args, **kwargs):
        """
        Adds a layer in GeoNode, after it has been added to Geoserver.

        Handler specific params:
        "layer_owner": Sets the owner of the layer.
        """
        try:
            owner = User.objects.get(username=layer_config['layer_owner'])
        except KeyError:
            owner = User.objects.get(username='AnonymousUser')

        # Populate arguments to create a new Layer
        if layer_config.get('raster'):
            layer_name = os.path.splitext(os.path.basename(layer))[0]
            store_name = layer_name
            store_type = 'coverageStore'
            fields = None
        else:
            layer_name = layer
            store_name = self.store_name
            store_type = 'dataStore'
            fields = layer_config['fields']

        workspace_name = self.workspace
        layer_uuid = str(uuid.uuid4())

        new_layer_kwargs = {
            'name': layer_name,
            'workspace': self.workspace,
            'store': store_name,
            'storeType': store_type,
            'typename': '{}:{}'.format(workspace_name.encode('utf-8'), layer_name.encode('utf-8')),
            'title': layer_name,
            "abstract": 'No abstract provided',
            'owner': owner,
            'uuid': layer_uuid,
        }

        new_layer, created = Layer.objects.get_or_create(**new_layer_kwargs)

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


class GeoNodeMetadataHandler(ImportHandlerMixin):
    """Import uploaded XML
    """

    def can_run(self, layer, layer_config, *args, **kwargs):
        """
        Only run this handler if the layer is found in Geoserver and the layer's style is the generic style.
        """
        if not layer_config.get('metadata', None):
            return False

        return True

    @ensure_can_run
    def handle(self, layer, layer_config, *args, **kwargs):
        """Update metadata from XML
        """
        geonode_layer = Layer.objects.get(name=layer)
        path = os.path.join(UPLOAD_DIR, str(self.importer.upload_file.upload.id))
        xmlfile = os.path.join(path, layer_config.get('metadata'))
        geonode_layer.metadata_uploaded = True
        identifier, vals, regions, keywords = set_metadata(open(xmlfile).read())

        regions_resolved, regions_unresolved = resolve_regions(regions)
        keywords.extend(regions_unresolved)

        # set regions
        regions_resolved = list(set(regions_resolved))
        if regions:
            if len(regions) > 0:
                geonode_layer.regions.add(*regions_resolved)

        # set taggit keywords
        keywords = list(set(keywords))
        geonode_layer.keywords.add(*keywords)

        # set model properties
        for (key, value) in vals.items():
            if key == "spatial_representation_type":
                # value = SpatialRepresentationType.objects.get(identifier=value)
                pass
            else:
                setattr(geonode_layer, key, value)

        geonode_layer.save()

        return geonode_layer
