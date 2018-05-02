import logging
import os
import shutil
import tempfile
from zipfile import is_zipfile, ZipFile

from django import forms
from django.conf import settings
from django.db.models import Sum

from osgeo_importer.importers import VALID_EXTENSIONS
from osgeo_importer.utils import mkdir_p, sizeof_fmt
from osgeo_importer.validators import valid_file

from .models import UploadFile, UploadedData
from .validators import validate_inspector_can_read, validate_shapefiles_have_all_parts
USER_UPLOAD_QUOTA = getattr(settings, 'USER_UPLOAD_QUOTA', None)


logger = logging.getLogger(__name__)


class UploadFileForm(forms.Form):
    file = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}))

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super(UploadFileForm, self).__init__(*args, **kwargs)

    class Meta:
        model = UploadFile
        fields = ['file']

    def clean(self):
        cleaned_data = super(UploadFileForm, self).clean()
        outputdir = tempfile.mkdtemp()
        files = self.files.getlist('file')
        # Files that need to be processed

        process_files = []

        # Create list of all potentially valid files, exploding first level zip files
        for f in files:
            errors = valid_file(f)
            if errors != []:
                self.add_error('file', ', '.join(errors))
                continue

            # find files in the .zip that we know how to process (VALID_EXTENSIONS)
            if is_zipfile(f):
                with ZipFile(f) as zip:
                    for zipname in zip.namelist():
                        _,zipext = os.path.splitext(zipname)
                        # doesn't have an extension
                        if not zipext:
                            continue
                        # OS X - ignore hidden files (i.e. .DS_Store and __MACOSX/.*)
                        _,fname = os.path.split(zipname)
                        if fname.startswith("."):
                            continue
                        # handle .shp.xml metadata files
                        if fname.lower().endswith(".shp.xml"):
                            zipext = ".shp.xml"
                        zipext = zipext.lstrip('.').lower()
                        if zipext in VALID_EXTENSIONS:
                            process_files.append(zipname)
            else:
                process_files.append(f.name)

        # Make sure shapefiles have all their parts
        if not validate_shapefiles_have_all_parts(process_files):
            self.add_error('file', 'Shapefiles must include .shp,.dbf,.shx,.prj')

        # Unpack all zip files and create list of cleaned file objects, excluding any not in
        #    VALID_EXTENSIONS
        cleaned_files = []
        for f in files:
            if f.name in process_files:
                with open(os.path.join(outputdir, f.name), 'w') as outfile:
                    for chunk in f.chunks():
                        outfile.write(chunk)
                cleaned_files.append(outfile)
            elif is_zipfile(f):
                with ZipFile(f) as zip:
                    for zipfile in zip.namelist():
                        if zipfile in process_files:
                            with zip.open(zipfile) as zf:
                                mkdir_p(os.path.join(outputdir, os.path.dirname(zipfile)))
                                with open(os.path.join(outputdir, zipfile), 'w') as outfile:
                                    shutil.copyfileobj(zf, outfile)
                                    cleaned_files.append(outfile)

        # After moving files in place make sure they can be opened by inspector
        inspected_files = []
        upload_size = 0
        for cleaned_file in cleaned_files:
            cleaned_file_path = os.path.join(outputdir, cleaned_file.name)
            if not validate_inspector_can_read(cleaned_file_path):
                self.add_error(
                    'file',
                    'Inspector could not read file {} or file is empty'.format(cleaned_file_path)
                )
                continue
            upload_size += os.path.getsize(cleaned_file_path)
            inspected_files.append(cleaned_file)

        cleaned_data['file'] = inspected_files
        # Get total file size
        cleaned_data['upload_size'] = upload_size
        if USER_UPLOAD_QUOTA is not None:
            # Get the total size of all data uploaded by this user
            user_filesize = UploadedData.objects.filter(user=self.request.user).aggregate(s=Sum('size'))['s']
            if user_filesize is None:
                user_filesize = 0
            if user_filesize + upload_size > USER_UPLOAD_QUOTA:
                # remove temp directory used for processing upload if quota exceeded
                shutil.rmtree(outputdir)
                self.add_error('file','User Quota Exceeded. Quota: %s Used: %s Adding: %s'%(
                    sizeof_fmt(USER_UPLOAD_QUOTA), 
                    sizeof_fmt(user_filesize), 
                    sizeof_fmt(upload_size)
                ))
        return cleaned_data
