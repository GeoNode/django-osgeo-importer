# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('osgeo_importer', '0011_uploadlayer_layer_type'),
    ]

    operations = [
        migrations.AlterField(
            model_name='uploadlayer',
            name='layer_name',
            field=models.TextField(null=True),
        ),
        migrations.AlterField(
            model_name='uploadlayer',
            name='name',
            field=models.TextField(null=True),
        ),
    ]
