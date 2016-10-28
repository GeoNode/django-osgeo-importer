from geonode.layers.models import Layer
from osgeo_importer.models import UploadLayer
from osgeo_importer.handlers import ImportHandlerMixin
from osgeo_importer.handlers import ensure_can_run
from osgeo_importer.importers import UPLOAD_DIR
from geonode.geoserver.helpers import gs_slurp
from geonode.layers.metadata import set_metadata
from geonode.layers.utils import resolve_regions
from django.contrib.auth import get_user_model
from django.conf import settings
from django import db
import os
import logging

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
        owner = layer_config.get('layer_owner')
        if isinstance(owner, str) or isinstance(owner, unicode):
            owner = User.objects.filter(username=owner).first()

        if layer_config.get('raster'):
            store_name = os.path.splitext(os.path.basename(layer))[0]
            filter = None
        else:
            store_name = self.store_name
            filter = layer

        results = gs_slurp(workspace=self.workspace,
                           store=store_name,
                           filter=filter,
                           owner=owner,
                           permissions=layer_config.get('permissions'))

        if self.importer.upload_file and results['layers'][0]['status'] == 'created':
            matched_layer = Layer.objects.get(name=results['layers'][0]['name'])
            upload_layer = UploadLayer.objects.get(upload_file=self.importer.upload_file.pk,
                                                   index=layer_config.get('index'))
            upload_layer.layer = matched_layer
            upload_layer.save()

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
