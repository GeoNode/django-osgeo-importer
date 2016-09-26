# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('osgeo_importer', '0004_uploadfile_file_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='uploadlayer',
            name='layer_name',
            field=models.CharField(max_length=64, null=True),
        ),
    ]
