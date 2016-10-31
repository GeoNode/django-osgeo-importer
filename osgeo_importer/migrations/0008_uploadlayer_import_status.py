# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('osgeo_importer', '0007_auto_20161025_2130'),
    ]

    operations = [
        migrations.AddField(
            model_name='uploadlayer',
            name='import_status',
            field=models.CharField(max_length=15, null=True, blank=True),
        ),
    ]
