import os
import shutil
from .models import UploadFile
from celery.task import task

from .views import OSGEO_IMPORTER


@task
def import_object(upload_file_id, configuration_options, request_cookies=None, request_user=None):
    """
    Imports a file into GeoNode.

    :param configuration_options: List of configuration objects for each layer that is being imported.
    """

    upload_file = UploadFile.objects.get(id=upload_file_id)

    gi = OSGEO_IMPORTER(upload_file.file.path, upload_file=upload_file)
    return gi.handle(configuration_options=configuration_options, request_cookies=request_cookies, request_user=request_user)


@task
def remove_path(path):
    """
    Removes a path using shutil.rmtree.
    """
    if os.path.exists(path):
        shutil.rmtree(path)
