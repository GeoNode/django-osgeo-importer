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
                logger.warning(', '.join(errors))
                continue
            if is_zipfile(f):
                with ZipFile(f) as zip:
                    for zipname in zip.namelist():
                        _, zipext = zipname.split(os.extsep, 1)
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
                        if ((zipfile in process_files or ('gdb/' in VALID_EXTENSIONS and
                                                          '{}{}'.format(os.extsep, 'gdb/') in zipfile)) and
                                not zipfile.endswith('/')):
                            with zip.open(zipfile) as zf:
                                mkdir_p(os.path.join(outputdir, os.path.dirname(zipfile)))
                                with open(os.path.join(outputdir, zipfile), 'w') as outfile:
                                    shutil.copyfileobj(zf, outfile)
                                    cleaned_files.append(outfile)

        # After moving files in place make sure they can be opened by inspector
        inspected_files = []
        file_names = [os.path.basename(f.name) for f in cleaned_files]
        upload_size = 0

        for cleaned_file in cleaned_files:
            if '{}{}'.format(os.extsep, 'gdb/') in cleaned_file.name:
                cleaned_file_path = os.path.join(outputdir, os.path.dirname(cleaned_file.name))
            else:
                cleaned_file_path = os.path.join(outputdir, cleaned_file.name)
            if validate_inspector_can_read(cleaned_file_path):
                add_file = True
                name, ext = os.path.splitext(os.path.basename(cleaned_file.name))
                upload_size += os.path.getsize(cleaned_file_path)

                if ext == '.xml':
                    if '{}.shp'.format(name) in file_names:
                        add_file = False
                    elif '.shp' in name and name in file_names:
                        add_file = False

                if add_file:
                    if cleaned_file not in inspected_files:
                        inspected_files.append(cleaned_file)
                else:
                    logger.warning('Inspector could not read file {} or file is empty'.format(cleaned_file_path))
                    continue
            else:
                logger.warning('Inspector could not read file {} or file is empty'.format(cleaned_file_path))
                continue

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
                self.add_error('file', 'User Quota Exceeded. Quota: %s Used: %s Adding: %s' % (
                    sizeof_fmt(USER_UPLOAD_QUOTA),
                    sizeof_fmt(user_filesize),
                    sizeof_fmt(upload_size)
                ))
        return cleaned_data
