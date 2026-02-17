from django.contrib import admin
from . import models

# Register your models here.
admin.site.register(models.Insight)
admin.site.register(models.InsightTarget)
admin.site.register(models.InsightPrompt)