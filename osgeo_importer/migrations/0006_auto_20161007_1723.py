# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('osgeo_importer', '0005_uploadlayer_layer_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='uploadeddata',
            name='upload_dir',
            field=models.CharField(max_length=1000, null=True),
        ),
    ]
