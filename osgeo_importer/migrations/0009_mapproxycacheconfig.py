# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('osgeo_importer', '0008_uploadlayer_import_status'),
    ]

    operations = [
        migrations.CreateModel(
            name='MapProxyCacheConfig',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('gpkg_filepath', models.CharField(max_length=1000)),
                ('config', models.TextField()),
            ],
        ),
    ]
