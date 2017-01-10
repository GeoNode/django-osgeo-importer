# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('osgeo_importer', '0009_mapproxycacheconfig'),
    ]

    operations = [
        migrations.AlterField(
            model_name='uploadeddata',
            name='name',
            field=models.CharField(max_length=250, null=True),
        ),
    ]
