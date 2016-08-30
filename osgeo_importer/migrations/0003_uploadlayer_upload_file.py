# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('osgeo_importer', '0002_auto_20160713_1429'),
    ]

    operations = [
        migrations.AddField(
            model_name='uploadlayer',
            name='upload_file',
            field=models.ForeignKey(blank=True, to='osgeo_importer.UploadFile', null=True),
        ),
    ]
