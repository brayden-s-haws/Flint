from django.contrib import admin
from .models import Schema, Table, Column

# Register your models here.
admin.site.register(Schema)
admin.site.register(Table)
admin.site.register(Column)