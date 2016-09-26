import os
from django import forms
from .models import UploadFile
from .validators import validate_extension, validate_inspector_can_read, validate_shapefiles_have_all_parts
from zipfile import is_zipfile, ZipFile
import tempfile
import logging
import shutil
logger = logging.getLogger(__name__)


class UploadFileForm(forms.Form):
    file = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}))

    class Meta:
        model = UploadFile
        fields = ['file']

    def clean(self):
        cleaned_data = super(UploadFileForm, self).clean()
        outputdir = tempfile.mkdtemp()
        files = self.files.getlist('file')
        validfiles = []

        # Create list of all potentially valid files, exploding first level zip files
        for file in files:
            if not validate_extension(file.name):
                self.add_error('file', 'Filetype not supported.')
                continue

            if is_zipfile(file):
                with ZipFile(file) as zip:
                    for zipname in zip.namelist():
                        if not validate_extension(zipname):
                            self.add_error('file', 'Filetype in zip not supported.')
                            continue
                        validfiles.append(zipname)
            else:
                validfiles.append(file.name)
        # Make sure shapefiles have all their parts
        if not validate_shapefiles_have_all_parts(validfiles):
            self.add_error('file', 'Shapefiles must include .shp,.dbf,.shx,.prj')
        # Unpack all zip files and create list of cleaned file objects
        cleaned_files = []
        for file in files:
            if file.name in validfiles:
                with open(os.path.join(outputdir, file.name), 'w') as outfile:
                    for chunk in file.chunks():
                        outfile.write(chunk)
                cleaned_files.append(outfile)
            elif is_zipfile(file):
                with ZipFile(file) as zip:
                    for zipfile in zip.namelist():
                        if zipfile in validfiles:
                            with zip.open(zipfile) as f:
                                with open(os.path.join(outputdir, zipfile), 'w') as outfile:
                                    shutil.copyfileobj(f, outfile)
                                    cleaned_files.append(outfile)

        # After moving files in place make sure they can be opened by inspector
        inspected_files = []
        for cleaned_file in cleaned_files:
            cleaned_file_path = os.path.join(outputdir, cleaned_file.name)
            if not validate_inspector_can_read(cleaned_file_path):
                self.add_error(
                    'file',
                    'Inspector could not read file {} or file is empty'.format(cleaned_file_path)
                )
                continue
            inspected_files.append(cleaned_file)

        cleaned_data['file'] = inspected_files
        return cleaned_data
