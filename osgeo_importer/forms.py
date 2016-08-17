import os
from django import forms
from .models import UploadFile
import zipfile
import tempfile


class XXXUploadFileForm(forms.ModelForm):

    class Meta:
        model = UploadFile
        fields = ['file']

class UploadFileForm(forms.Form):
    file = forms.FileField(widget=forms.ClearableFileInput(attrs={'multiple': True}))
    
    def validate_extension(filename):
        base, extension = os.path.splitext(filename)
        extension = extension.lstrip('.').lower()
        if extension not in OSGEO_IMPORTER_VALID_EXTENSIONS:
            raise forms.ValidationError("%s files not accepted by importer. file: %s" % (extension, filename))
    
    def validate_shapefile_has_all_parts(self,validfiles):
        shp = []
        prj = []
        dbf = []
        shx = []
        for file in validfiles:
            base, extension = os.path.splitext(filename)
            extension = extension.lstrip('.').lower()
            if extension == 'shp':
                shp.push(base)
            elif extension == 'prj':
                prj.push(base)
            elif extension == 'dbf':
                dbf.push(base)
            elif extension == 'shx':
                shx.push(base)
        if set(shp) == set(prj) == set(dbf) == set(shx):
            return True
        else:
            raise forms.ValidationError("All Shapefiles must include .shp, .prj, .dbf, and .shx")

    def clean(self):
        cleaned_data = super(UploadFileForm, self).clean()
        outputdir = tempfile.mkdtemp()
        files = self.files.getlist('files')
        validfiles = []

        # Create list of all potentially valid files, exploding first level zip files
        for file in files:
            self.validate_extension(file_ext)

            if zipfile.is_zipfile(file):
                with zipfile.ZipFile(file) as zip:
                    for zipfile in zip.namelist():
                        zipfile_base, zipfile_ext = os.path.splitext(zipfile)
                        self.validate_extension(zipfile_ext)
                        validfiles.push(zipfile)
            else:
                validfiles.push(file.name)

        # Make sure shapefiles have all their parts
        self.validate_shapefile_has_all_parts(validfiles)

        # Unpack all zip files and create list of cleaned file objects
        cleaned_files = []
        for file in files:
            if file in validfiles:
                # with open(os.path.join(outputdir,file.name),'w') as outfile:
                #    outfile.write(file.read())
                cleaned_files.push(file)
            elif zipfile.is_zipfile(file):
                with zipfile.ZipFile(file) as zip:
                    for zipfile in zip.namelist():
                        if zipfile in validfiles:
                            with zip.open(zipfile) as f:
                                with open(os.path.join(outputdir,zipfile)) as outfile:
                                    shutil.copyfileobj(f,outfile)
                                    cleaned_files.push(outfile)
        cleaned_data['files'] = cleaned_files
