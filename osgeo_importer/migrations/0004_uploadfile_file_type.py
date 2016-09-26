# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('osgeo_importer', '0003_uploadlayer_upload_file'),
    ]

    operations = [
        migrations.AddField(
            model_name='uploadfile',
            name='file_type',
            field=models.CharField(max_length=50, null=True, blank=True),
        ),
    ]
