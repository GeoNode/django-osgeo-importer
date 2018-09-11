from .models import UploadedData, UploadLayer, UploadFile, UploadException
from django.contrib import admin


class UploadAdmin(admin.ModelAdmin):
    pass


class UploadedLayerAdmin(admin.ModelAdmin):
    list_display = ('name', 'layer', 'feature_count', 'task_id')


class UploadedDataAdmin(admin.ModelAdmin):
    list_display = ('name', 'user', 'state', 'size', 'complete')
    list_filter = ('user', 'state', 'complete')


class UploadExceptionAdmin(admin.ModelAdmin):
    model = UploadException


admin.site.register(UploadException, UploadExceptionAdmin)
admin.site.register(UploadLayer, UploadedLayerAdmin)
admin.site.register(UploadedData, UploadedDataAdmin)
admin.site.register(UploadFile, UploadAdmin)
