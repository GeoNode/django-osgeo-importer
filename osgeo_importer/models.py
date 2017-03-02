#########################################################################
#
# Copyright (C) 2012 OpenPlans
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
#
#########################################################################


import os
import tempfile
import logging

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse
from django.db import models
from jsonfield import JSONField

try:
    from django.contrib.contenttypes.fields import GenericForeignKey
except ImportError:
    from django.contrib.contenttypes.generic import GenericForeignKey

from .utils import NoDataSourceFound
from .utils import sizeof_fmt, load_handler

OSGEO_IMPORTER = getattr(settings, 'OSGEO_IMPORTER', 'osgeo_importer.importers.OGRImport')
DEFAULT_LAYER_CONFIGURATION = {'configureTime': False,
                               'editable': True,
                               'convert_to_date': [],
                               'index': 0}

logger = logging.getLogger(__name__)


def validate_file_extension(value):
    """
    Validates file extensions.
    """

    importer = load_handler(OSGEO_IMPORTER, value)
    for extension in importer.valid_extensions:
        if value.name.lower().endswith(extension):
            return
    raise ValidationError(u'Invalid File Type')


def validate_file_type(value):
    """
    Returns the general file type
    """
    name = value.name
    root, extension = os.path.splitext(name.lower())
    if extension == 'tif':
        return 'raster'
    if extension == 'sld':
        return 'style'
    if extension == 'xml':
        return


def validate_inspector_can_read(value):
    """
    Validates Geospatial data.
    """
    name = value.name
    root, extension = os.path.splitext(name.lower())

    temp_directory = tempfile.mkdtemp()
    filename = os.path.join(temp_directory, value.name)

    if extension in ['sld', 'xml']:  # allow uploads of sld and xml metadata
        return

    if extension in ['tif']:
        with open(filename, 'wb') as f:
            for chunk in value.chunks():
                f.write(chunk)

        try:
            importer = load_handler(OSGEO_IMPORTER, filename)
            data, inspector = importer.open_source_datastore(filename)

        except NoDataSourceFound:
            raise ValidationError('Unable to locate raster layer.')

        finally:
            from .tasks import remove_path
            remove_path.delay(os.path.split(filename)[0])
        return

    #  Otherwise check if vector
    with open(filename, 'wb') as f:
        for chunk in value.chunks():
            f.write(chunk)

    try:
        importer = load_handler(OSGEO_IMPORTER, filename)
        data, inspector = importer.open_source_datastore(filename)
        # Ensure the data has a geometry.
        for description in inspector.describe_fields():
            if description.get('geom_type') in inspector.INVALID_GEOMETRY_TYPES:
                raise ValidationError('Unable to find geometry or the geometry type is unsupported.')

    except NoDataSourceFound:
        raise ValidationError('Unable to locate geospatial data.')

    finally:
        from .tasks import remove_path
        remove_path.delay(os.path.split(filename)[0])


class UploadedData(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True)
    state = models.CharField(max_length=16)
    date = models.DateTimeField('date', auto_now_add=True)
    upload_dir = models.CharField(max_length=1000, null=True)
    name = models.CharField(max_length=250, null=True)
    complete = models.BooleanField(default=False)
    size = models.IntegerField(null=True, blank=True)
    metadata = models.TextField(null=True)
    file_type = models.CharField(max_length=50, null=True, blank=True)

    class Meta:
        ordering = ['-date']
        verbose_name_plural = 'Upload data'

    STATE_INVALID = 'INVALID'

    def get_delete_url(self):
        return reverse('data_upload_delete', args=[self.id])

    @property
    def filesize(self):
        """Humanizes the upload file size.
        """
        # whereof one cannot speak, one must be silent
        if self.size is None:
            return None
        return sizeof_fmt(self.size)

    def file_url(self):
        """Exposes the file url.
        """
        return ''  # self.uploadfile_set.first().file.url

    def any_layers_imported(self):
        return any(self.uploadlayer_set.all().values_list('layer', flat=True))

    def all_layers_imported(self):
        return all(self.uploadlayer_set.all().values_list('layer', flat=True))

    def __unicode__(self):
        return 'Upload [%s] %s, %s' % (self.id, self.name, self.user)


class UploadFile(models.Model):
    upload = models.ForeignKey(UploadedData, null=True, blank=True)
    file = models.FileField(
        upload_to="uploads",
        max_length=1000,
        validators=[
            validate_file_extension,
            validate_inspector_can_read
        ]
    )
    file_type = models.CharField(max_length=50, null=True, blank=True)
    slug = models.SlugField(max_length=250, blank=True)

    def __unicode__(self):
        return self.slug

    @property
    def name(self):
        return os.path.basename(self.file.path)

    def save(self, *args, **kwargs):
        self.slug = self.file.name
        super(UploadFile, self).save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        self.file.delete(False)
        super(UploadFile, self).delete(*args, **kwargs)


class UploadLayer(models.Model):
    """Layers stored in an uploaded data set.
    """
    upload = models.ForeignKey(UploadedData, null=True, blank=True)
    upload_file = models.ForeignKey(UploadFile, null=True, blank=True)
    index = models.IntegerField(default=0)
    # *deprecated* name of the layer, sometimes other data
    name = models.CharField(max_length=64, null=True)
    fields = JSONField(null=True, default={})
    content_type = models.ForeignKey(ContentType, blank=True, null=True)
    object_id = models.PositiveIntegerField(blank=True, null=True)
    layer = GenericForeignKey('content_type', 'object_id')
    configuration_options = JSONField(null=True)
    import_status = models.CharField(max_length=15, blank=True, null=True)
    task_id = models.CharField(max_length=36, blank=True, null=True)
    feature_count = models.IntegerField(null=True, blank=True)
    # Name of the layer as known in the file/package/endpoint it came from.
    internal_layer_name = models.CharField(max_length=64, null=True)
    # Geonode-wide unique name for layer.
    layer_name = models.CharField(max_length=64, null=True)
    layer_type = models.CharField(max_length=10, null=True)

    @property
    def file_name(self):
        if not self.upload_file:
            return None
        return self.upload_file.name

    @property
    def file_type(self):
        """A layer's 'file type' - really the file type of the file it is in.
        """
        if not self.upload_file:
            return None
        return self.upload_file.file_type

    @property
    def layer_data(self):
        """
        Serialized information about the layer.
        """
        if not self.layer:
            return

        return {'title': self.layer.title, 'url': self.layer.get_absolute_url(), 'id': self.layer.id}

    @property
    def description(self):
        """
        Serialized description of the layer.
        """

        params = dict(name=self.name, fields=self.fields, imported_layer=None, index=self.index, id=self.id)

        if self.layer:
            params['imported_layer'] = {'typename': self.layer.typename,
                                        'name': self.layer.name,
                                        'url': self.layer.get_absolute_url()}
        return params

    @property
    def status(self):
        """
        Returns the status of the import of this UploadedLayer.
        """
        s = 'UNKNOWN' if self.import_status is None else self.import_status

        return s

    class Meta:
        ordering = ('index',)


class UploadException(models.Model):
    """
    A generic object for storing exceptions during upload
    """
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Timestamp when the exception was logged.')
    error = models.TextField()
    upload_layer = models.ForeignKey(UploadLayer, blank=True, null=True)
    task_id = models.CharField(max_length=36, blank=True, null=True)
    traceback = models.TextField(blank=True, null=True)
    verbose_traceback = models.TextField(blank=True, null=True, help_text='A humanized exception message.')

    @classmethod
    def raise_exception(cls, error, task_id, upload_layer, verbose_message):
        """
        A method to create a new saved exception.
        """

        if verbose_message is None:
            verbose_message = error

        exception = cls(error=error, verbose_traceback=verbose_message, task_id=task_id, upload_layer=upload_layer)
        exception.save()
        return exception

    @property
    def error(self):
        return self.error

    def __unicode__(self):
        return self.verbose_traceback

    class Meta:
        verbose_name = 'Upload Exception'


class MapProxyCacheConfig(models.Model):
    """ Each instance stores configuration details for mapproxy to serve a single GeoPackage containing tiles.
    """
    # Location of the file this config is for
    gpkg_filepath = models.CharField(max_length=1000)
    config = models.TextField()
