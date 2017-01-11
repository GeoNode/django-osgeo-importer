# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('osgeo_importer', '0010_auto_20170109_1401'),
    ]

    operations = [
        migrations.AddField(
            model_name='uploadlayer',
            name='layer_type',
            field=models.CharField(max_length=10, null=True),
        ),
    ]
