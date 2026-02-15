from django.contrib import admin
from .models import Source, SourceType, SourceSyncLog

# Register your models here.
admin.site.register(Source)
admin.site.register(SourceType)
admin.site.register(SourceSyncLog)