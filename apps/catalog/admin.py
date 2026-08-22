from django.contrib import admin
from .models import Schema, Table, Column, TableStatistics


admin.site.register(Schema)
admin.site.register(Table)
admin.site.register(Column)
admin.site.register(TableStatistics)