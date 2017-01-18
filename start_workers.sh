#!/bin/bash
pushd /home/ubuntu/osgeo_importer_prj/
source  /home/ubuntu/venvs/osgeo_importer_prj/bin/activate
export DJANGO_SETTINGS_MODULE=osgeo_importer_prj.settings_aws
celery -A osgeo_importer_prj.celery.app worker --loglevel=INFO --concurrency=8 -n worker-1
deactivate
popd

