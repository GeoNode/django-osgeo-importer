import os

from geonode.layers.metadata import set_metadata
from geonode.layers.models import Layer
from geonode.layers.utils import resolve_regions
from osgeo_importer.handlers import ImportHandlerMixin
from osgeo_importer.handlers import ensure_can_run
from osgeo_importer.importers import UPLOAD_DIR
from publish_handler import GeoNodePublishHandler  # NOQA - Moved this code but want it still available here.


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
