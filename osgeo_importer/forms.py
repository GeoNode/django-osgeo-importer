import logging
import os
import shutil
import tempfile
from zipfile import is_zipfile, ZipFile

from django import forms

from osgeo_importer.importers import VALID_EXTENSIONS
from osgeo_importer.utils import mkdir_p
from osgeo_importer.validators import valid_file

from .models import UploadFile
from .validators import validate_inspector_can_read, validate_shapefiles_have_all_parts


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
        # Files that need to be processed
        process_files = []

        # Create list of all potentially valid files, exploding first level zip files
        for f in files:
            errors = valid_file(f)
            if errors != []:
                self.add_error('file', ', '.join(errors))
                continue

            if is_zipfile(f):
                with ZipFile(f) as zip:
                    for zipname in zip.namelist():
                        _, zipext = os.path.splitext(os.path.basename(zipname))
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
