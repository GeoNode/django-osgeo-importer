# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('osgeo_importer', '0011_uploadlayer_layer_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='uploadlayer',
            name='internal_layer_name',
            field=models.CharField(max_length=64, null=True),
        ),
    ]
