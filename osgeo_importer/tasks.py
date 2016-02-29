import os
import shutil
from .importers import GDALImport
from .models import UploadFile, UploadLayer
from celery.task import task

@task
def import_object(upload_file_id, configuration_options):
    """
    Imports a file into GeoNode.

    :param configuration_options: List of configuration objects for each layer that is being imported.
    """

    upload_file = UploadFile.objects.get(id=upload_file_id)

    gi = GDALImport(upload_file.file.path, upload_file=upload_file)
    return gi.handle(configuration_options=configuration_options)


@task
def remove_path(path):
    """
    Removes a path using shutil.rmtree.
    """
    if os.path.exists(path):
        shutil.rmtree(path)
