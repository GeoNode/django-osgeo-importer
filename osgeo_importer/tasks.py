import os
import shutil
from osgeo_importer.models import UploadFile
import celery
from osgeo_importer.views import OSGEO_IMPORTER
import logging
from geonode.celery_app import app
from osgeo_importer.models import UploadLayer
from django.conf import settings

logger = logging.getLogger(__name__)


class ExceptionLoggingTask(celery.Task):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        celery.Task.on_failure(self, exc, task_id, args, kwargs, einfo)
        msg = '{}(args={}, kwargs={}): {}\n{}'.format(task_id, args, kwargs, einfo, exc)
        logger.debug(msg)


@app.task(base=ExceptionLoggingTask, bind=True)
def add(a, b):
    logger.info('{} + {} = {}'.format(a, b, a + b))
    return a + b


class RecordImportStateTask(ExceptionLoggingTask):
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        ExceptionLoggingTask.on_failure(self, exc, task_id, args, kwargs, einfo)
        logger.info('Layer import task failed, recording UploadLayer.import_status')
        configuration_options = kwargs['configuration_options']
        ulid = configuration_options['upload_layer_id']
        try:
            ul = UploadLayer.objects.get(id=ulid)
        except UploadLayer.DoesNotExist:
            msg = 'Got invalid UploadLayer id: {}'.format(ulid)
            logger.error(msg)
            raise
        ul.import_status = 'FAILURE'
        ul.save()

    def on_success(self, retval, task_id, args, kwargs):
        configuration_options = kwargs['configuration_options']
        ExceptionLoggingTask.on_success(self, retval, task_id, args, kwargs)
        ulid = configuration_options['upload_layer_id']
        try:
            ul = UploadLayer.objects.get(id=ulid)
        except UploadLayer.DoesNotExist:
            msg = 'Got invalid UploadLayer id: {}'.format(ulid)
            logger.error(msg)
            raise
        logger.info('Layer import task successful, recording UploadLayer.import_status')
        ul.import_status = 'SUCCESS'
        ul.save()


try:
    import_task_soft_time_limit = settings.IMPORT_TASK_SOFT_TIME_LIMIT
except AttributeError:
    import_task_soft_time_limit = 90


@app.task(base=RecordImportStateTask, soft_time_limit=import_task_soft_time_limit, bind=True)
def import_object(self, upload_file_id, configuration_options=None, request_cookies=None, request_user=None):
    """
    Imports a file into GeoNode.

    :param configuration_options: List of configuration objects for each layer that is being imported.
    """
    logger.info('Starting import_object() task for layer "{}"'.format(configuration_options.get('layer_name', 'n/a')))
    ulid = configuration_options['upload_layer_id']
    try:
        ul = UploadLayer.objects.get(id=ulid)
    except UploadLayer.DoesNotExist:
        msg = 'Got invalid UploadLayer id: {}'.format(ulid)
        logger.error(msg)
        raise
    ul.task_id = self.request.id
    ul.import_status = 'PENDING'
    ul.save()

    upload_file = UploadFile.objects.get(id=upload_file_id)

    logger.info('Creating importer')
    gi = OSGEO_IMPORTER(upload_file.file.path, upload_file=upload_file)
    logger.info('Calling importer.handle()')
    gi.handle(configuration_options=configuration_options, request_cookies=request_cookies, request_user=request_user)
    return


@app.task(base=ExceptionLoggingTask)
def remove_path(path):
    """
    Removes a path using shutil.rmtree.
    """
    if os.path.exists(path):
        shutil.rmtree(path)
