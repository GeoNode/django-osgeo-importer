from django.conf.urls import patterns, url
from django.views.generic import TemplateView
from osgeo_importer.urls import urlpatterns as importer_urlpatterns

from geonode.urls import *

urlpatterns = patterns('',
   url(r'^/?$',
       TemplateView.as_view(template_name='site_index.html'),
       name='home'),
 ) + urlpatterns

urlpatterns += importer_urlpatterns
