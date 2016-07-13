# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models
import jsonfield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('osgeo_importer', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='uploadlayer',
            name='fields',
            field=jsonfield.fields.JSONField(default={}, null=True),
        ),
    ]
