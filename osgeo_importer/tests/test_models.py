'''
Created on Nov 14, 2016

@author: jivan
'''
from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase

from mock import Mock, patch
from osgeo_importer.models import UploadLayer


class TestUploadLayer(TestCase):

    @patch('osgeo_importer.models.AsyncResult')
    @patch('osgeo_importer.models.TaskState')
    def test_status(self, MockTaskState, MockAsyncResult):
        """ Checks the behavior of the small, but logically complex status property.
        """
        # --- Case 1, import_status already set; status() should return value of import_status
        ul = UploadLayer()
        ul.import_status = 'already-set'
        s = ul.status
        self.assertEqual(s, 'already-set')

        # --- Case 2, import_status not set, no celery task id assigned to model instance;
        #    status() should return 'UNKNOWN'.
        ul = UploadLayer()
        ul.import_status = None
        s = ul.status
        self.assertEqual(s, 'UNKNOWN')

        # --- Case 3, import_status not set, TaskState model contains matching instance, matching instance status
        #    (Appropriate? I think this is what AsyncResult() does)
        ul = UploadLayer()
        ul.import_status = None
        ul.task_id = 'celerytaskid'
        task_state_instance = Mock()
        task_state_instance.state = 'state-from-TaskState'
        MockTaskState.objects.get = Mock(return_value=task_state_instance)
        s = ul.status
        self.assertEqual(s, 'state-from-TaskState')

        # --- Case 4, import_status not set, TaskState model has no matching instance,
        #    instantiate an instance of AsyncResult to get task status
        ul = UploadLayer()
        ul.import_status = None
        ul.task_id = 'celerytaskid'
        MockTaskState.objects.get = Mock(return_value=None)
        MockTaskState.objects.get.side_effect = ObjectDoesNotExist()

        mock_async_result_instance = Mock()
        mock_async_result_instance.status = 'status-from-AsyncResult'
        MockAsyncResult.return_value = mock_async_result_instance

        s = ul.status
        self.assertEqual(s, 'status-from-AsyncResult')
