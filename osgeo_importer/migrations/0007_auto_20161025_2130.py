# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import osgeo_importer.models


class Migration(migrations.Migration):

    dependencies = [
        ('osgeo_importer', '0006_auto_20161007_1723'),
    ]

    operations = [
        migrations.AlterField(
            model_name='uploadfile',
            name='file',
            field=models.FileField(max_length=1000, upload_to=b'uploads', validators=[osgeo_importer.models.validate_file_extension, osgeo_importer.models.validate_inspector_can_read]),
        ),
    ]
