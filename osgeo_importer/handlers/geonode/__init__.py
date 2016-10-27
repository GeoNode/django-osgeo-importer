import datetime
import logging
import os
import uuid

from django import db
from django.conf import settings
from django.contrib.auth import get_user_model

from geonode.layers.metadata import set_metadata
from geonode.layers.models import Layer, Attribute
from geonode.layers.utils import resolve_regions
from osgeo_importer.handlers import ImportHandlerMixin
from osgeo_importer.handlers import ensure_can_run
from osgeo_importer.importers import UPLOAD_DIR
from osgeo_importer.models import UploadLayer


User = get_user_model()
logger = logging.getLogger(__name__)


# The function set_attributes() is used in GeoNodePublishHandler.handle()
# In case the user is using osgeo_importer with a version of GeoNode older than
# 2016-11-09, duplicate the GeoNode-independent set_attributes here.
# If the duplicated code is still here after 2018-11-01, it should be removed.
try:
    from geonode.utils import set_attributes
except ImportError:
    def set_attributes(layer, attribute_map, overwrite=False, attribute_stats=None):
        """ *layer*: a geonode.layers.models.Layer instance
            *attribute_map*: a list of 2-lists specifying attribute names and types,
                example: [ ['id', 'Integer'], ... ]
            *overwrite*: replace existing attributes with new values if name/type matches.
            *attribute_stats*: dictionary of return values from get_attribute_statistics(),
                of the form to get values by referencing attribute_stats[<layer_name>][<field_name>].
        """
        # we need 3 more items; description, attribute_label, and display_order
        attribute_map_dict = {
            'field': 0,
            'ftype': 1,
            'description': 2,
            'label': 3,
            'display_order': 4,
        }
        for attribute in attribute_map:
            attribute.extend((None, None, 0))

        attributes = layer.attribute_set.all()
        # Delete existing attributes if they no longer exist in an updated layer
        for la in attributes:
            lafound = False
            for attribute in attribute_map:
                field, ftype, description, label, display_order = attribute
                if field == la.attribute:
                    lafound = True
                    # store description and attribute_label in attribute_map
                    attribute[attribute_map_dict['description']] = la.description
                    attribute[attribute_map_dict['label']] = la.attribute_label
                    attribute[attribute_map_dict['display_order']] = la.display_order
            if overwrite or not lafound:
                logger.debug(
                    "Going to delete [%s] for [%s]",
                    la.attribute,
                    layer.name.encode('utf-8'))
                la.delete()

        # Add new layer attributes if they don't already exist
        if attribute_map is not None:
            iter = len(Attribute.objects.filter(layer=layer)) + 1
            for attribute in attribute_map:
                field, ftype, description, label, display_order = attribute
                if field is not None:
                    la, created = Attribute.objects.get_or_create(
                        layer=layer, attribute=field, attribute_type=ftype,
                        description=description, attribute_label=label,
                        display_order=display_order)
                    if created:
                        if (not attribute_stats or layer.name not in attribute_stats or
                                field not in attribute_stats[layer.name]):
                            result = None
                        else:
                            result = attribute_stats[layer.name][field]

                        if result is not None:
                            logger.debug("Generating layer attribute statistics")
                            la.count = result['Count']
                            la.min = result['Min']
                            la.max = result['Max']
                            la.average = result['Average']
                            la.median = result['Median']
                            la.stddev = result['StandardDeviation']
                            la.sum = result['Sum']
                            la.unique_values = result['unique_values']
                            la.last_stats_updated = datetime.datetime.now()
                        la.visible = ftype.find("gml:") != 0
                        la.display_order = iter
                        la.save()
                        iter += 1
                        logger.debug(
                            "Created [%s] attribute for [%s]",
                            field,
                            layer.name.encode('utf-8'))
        else:
            logger.debug("No attributes found")


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
        # ***    but until it gets tracked down, this will keep set_attributes from
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
