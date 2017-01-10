from django.test import TestCase

from osgeo_importer import views
from osgeo_importer.models import UploadedData


class TestFileAddView_upload(TestCase):
    """Test the helper method FileAddView.upload.
    """

    class FakeRequest(object):
        """Fake the kind of request object used by FileAddView.upload.
        """
        def __init__(self, user):
            self.user = user

    class FakeFile(object):
        """Fake the kind of file object used by FileAddView.upload.
        """
        def __init__(self, name):
            self.name = name

    def view(self):
        view = views.FileAddView()
        view.get_file_type = lambda path: "BogusType"
        user = None
        view.request = self.FakeRequest(user)
        return view

    def test_empty(self):
        """Empty data should return None.

        Form validation should guard against this sort of argument coming to
        upload(), but if it does happen, upload() should behave reasonably.
        """
        data = []
        view = self.view()
        upload = view.upload(data, view.request.user)
        self.assertEqual(upload.name, None)
        self.assertEqual(upload.file_type, None)

    def test_single(self):
        data = [
            self.FakeFile("/tmp/xyz/abc/foo.shp")
        ]
        view = self.view()
        upload = view.upload(data, view.request.user)
        self.assertEqual(upload.name, "foo.shp")
        self.assertEqual(upload.file_type, "BogusType")

    def test_double(self):
        data = [
            self.FakeFile("/tmp/xyz/abc/foo.shp"),
            self.FakeFile("/tmp/xyz/abc/bar.shp")
        ]
        view = self.view()
        upload = view.upload(data, view.request.user)
        self.assertEqual(upload.name, "bar.shp, foo.shp")
        self.assertEqual(upload.file_type, None)

    def test_single_too_long(self):
        """ Checks that view.upload() (FileAddView) simply truncates the filename when
            there's only one file in the upload and it's too long.
        """
        too_long_basename = (
            "ObviouslyWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWay"
            "WayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWay"
            "WayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWay"
            "TooLong.shp"
        )
        too_long_path = (
            "/tmp/{}".format(too_long_basename)
        )
        data = [
            self.FakeFile(too_long_path),
        ]

        # Make sure too_long_basename is actually too long.
        max_length = UploadedData._meta.get_field('name').max_length
        self.assertGreater(
            len(too_long_basename), max_length, 'Test file basename not longer than allowed: {}'.format(max_length))

        view = self.view()
        upload = view.upload(data, view.request.user)
        self.assertEqual(upload.name.startswith("Obviously"), True)
        self.assertEqual(upload.file_type, "BogusType")

    def test_many_too_long(self):
        """ Checks that view.upload() (FileAddView) returns an object with both attributes 'name', and 'file_type'
            set to None for an upload with multiple files with at least
            one which has a name beyond the maximum length allowed.
        """
        too_long_name = (
            "/tmp/WayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWay"
            "WayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWay"
            "WayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWayWay"
            "TooLong.shp"
        )
        data = [
            self.FakeFile("/tmp/xyz/abc/NotTooLongOnItsOwn.shp"),
            self.FakeFile("/tmp/xyz/abc/rather_long_to_be_combined_with.shp"),
            self.FakeFile("/tmp/really_not_too_much.shp"),
            # len 251:
            self.FakeFile(too_long_name),
        ]

        # Make sure too_long_basename is actually too long.
        max_filepath_length = UploadedData._meta.get_field('name').max_length
        if True not in [len(ff.name) > max_filepath_length for ff in data]:
            self.fail('None of the test filenames exceed the allowed length: {}'.format(max_filepath_length))

        view = self.view()
        upload = view.upload(data, view.request.user)
        self.assertEqual(upload.name, None)
        self.assertEqual(upload.file_type, None)
