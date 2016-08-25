import os
from django import forms
from .models import UploadFile
from .utils import NoDataSourceFound, load_handler
from .importers import OSGEO_IMPORTER
from zipfile import is_zipfile, ZipFile
import tempfile
import logging
import shutil
from django.conf import settings

logger = logging.getLogger(__name__)

class XXXUploadFileForm(forms.ModelForm):

    class Meta:
        model = UploadFile
        fields = ['file']

class UploadFileForm(forms.Form):
    file = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}))

    class Meta:
        model = UploadFile
        fields = ['file']

    def validate_extension(self,filename):
        base, extension = os.path.splitext(filename)
        extension = extension.lstrip('.').lower()
        if extension not in settings.OSGEO_IMPORTER_VALID_EXTENSIONS:
            logger.debug('Validation Error: %s files not accepted by importer. file: %s',extension,filename)
            self.add_error('file',"%s files not accepted by importer. file: %s" % (extension, filename))
    
    def validate_shapefile_has_all_parts(self,validfiles):
        shp = []
        prj = []
        dbf = []
        shx = []
        for file in validfiles:
            base, extension = os.path.splitext(file)
            extension = extension.lstrip('.').lower()
            if extension == 'shp':
                shp.append(base)
            elif extension == 'prj':
                prj.append(base)
            elif extension == 'dbf':
                dbf.append(base)
            elif extension == 'shx':
                shx.append(base)
        if set(shp) == set(prj) == set(dbf) == set(shx):
            return True
        else:
            logger.debug('Validation Error: All Shapefiles must include .shp, .prj, .dbf, and .shx')
            self.add_error('file',"All Shapefiles must include .shp, .prj, .dbf, and .shx")

    def validate_inspector_can_read(self,filename):
        try:
            importer = load_handler(OSGEO_IMPORTER, filename)
            data, inspector = importer.open_source_datastore(filename)
        except NoDataSourceFound:
            self.add_error('file','Unable to open file: %s' % filename)

    def clean(self):
        logger.debug('..Cleaning...')
        cleaned_data = super(UploadFileForm, self).clean()
        outputdir = tempfile.mkdtemp()
        files = self.files.getlist('file')
        validfiles = []

        # Create list of all potentially valid files, exploding first level zip files
        for file in files:
            logger.debug('cleaning %s',file.name)
            self.validate_extension(file.name)

            if is_zipfile(file):
                with ZipFile(file) as zip:
                    for zipname in zip.namelist():
                        logger.debug('Checking extensions in zipfile %s file %s',file,zipname)
                        self.validate_extension(zipname)
                        validfiles.append(zipname)
            else:
                validfiles.append(file.name)

        # Make sure shapefiles have all their parts
        self.validate_shapefile_has_all_parts(validfiles)
        logger.debug('valid files found: %s',validfiles)
        # Unpack all zip files and create list of cleaned file objects
        cleaned_files = []
        for file in files:
            logger.debug('file: %s',file)
            if file.name in validfiles:
                with open(os.path.join(outputdir,file.name),'w') as outfile:
                    for chunk in file.chunks():
                        outfile.write(chunk)
                cleaned_files.append(outfile)
            elif is_zipfile(file):
                with ZipFile(file) as zip:
                    for zipfile in zip.namelist():
                        if zipfile in validfiles:
                            with zip.open(zipfile) as f:
                                with open(os.path.join(outputdir,zipfile),'w') as outfile:
                                    shutil.copyfileobj(f,outfile)
                                    cleaned_files.append(outfile)

        # After moving files in place make sure they can be opened by inspector
        for cleaned_file in cleaned_files:
            logger.debug('About to inspect %s in form',os.path.join(outputdir,file.name))
            self.validate_inspector_can_read(os.path.join(outputdir,file.name))

        logger.debug('cleaned_files %s',cleaned_files)
        cleaned_data['file'] = cleaned_files
        return cleaned_data
