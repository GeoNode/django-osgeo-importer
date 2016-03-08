# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models, migrations
from django.conf import settings
import jsonfield.fields
import osgeo_importer.models


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='UploadedData',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('state', models.CharField(max_length=16)),
                ('date', models.DateTimeField(auto_now_add=True, verbose_name=b'date')),
                ('upload_dir', models.CharField(max_length=100, null=True)),
                ('name', models.CharField(max_length=64, null=True)),
                ('complete', models.BooleanField(default=False)),
                ('size', models.IntegerField(null=True, blank=True)),
                ('metadata', models.TextField(null=True)),
                ('file_type', models.CharField(max_length=50, null=True, blank=True)),
                ('user', models.ForeignKey(to=settings.AUTH_USER_MODEL, null=True)),
            ],
            options={
                'ordering': ['-date'],
                'verbose_name_plural': 'Upload data',
            },
        ),
        migrations.CreateModel(
            name='UploadException',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name=b'Timestamp when the exception was logged.')),
                ('task_id', models.CharField(max_length=36, null=True, blank=True)),
                ('traceback', models.TextField(null=True, blank=True)),
                ('verbose_traceback', models.TextField(help_text=b'A humanized exception message.', null=True, blank=True)),
            ],
            options={
                'verbose_name': 'Upload Exception',
            },
        ),
        migrations.CreateModel(
            name='UploadFile',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('file', models.FileField(upload_to=b'uploads', validators=[osgeo_importer.models.validate_file_extension, osgeo_importer.models.validate_inspector_can_read])),
                ('slug', models.SlugField(max_length=250, blank=True)),
                ('upload', models.ForeignKey(blank=True, to='osgeo_importer.UploadedData', null=True)),
            ],
        ),
        migrations.CreateModel(
            name='UploadLayer',
            fields=[
                ('id', models.AutoField(verbose_name='ID', serialize=False, auto_created=True, primary_key=True)),
                ('index', models.IntegerField(default=0)),
                ('name', models.CharField(max_length=64, null=True)),
                ('fields', jsonfield.fields.JSONField(null=True)),
                ('object_id', models.PositiveIntegerField(null=True, blank=True)),
                ('configuration_options', jsonfield.fields.JSONField(null=True)),
                ('task_id', models.CharField(max_length=36, null=True, blank=True)),
                ('feature_count', models.IntegerField(null=True, blank=True)),
                ('content_type', models.ForeignKey(blank=True, to='contenttypes.ContentType', null=True)),
                ('upload', models.ForeignKey(blank=True, to='osgeo_importer.UploadedData', null=True)),
            ],
            options={
                'ordering': ('index',),
            },
        ),
        migrations.AddField(
            model_name='uploadexception',
            name='upload_layer',
            field=models.ForeignKey(blank=True, to='osgeo_importer.UploadLayer', null=True),
        ),
    ]
