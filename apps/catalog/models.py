from __future__ import annotations

from django.db import models
from apps.core.models import TenantAwareModel

class Schema(TenantAwareModel):
    source = models.ForeignKey('sources.Source', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')

    def __str__(self) -> str:
        return self.name

class Table(TenantAwareModel):
    schema = models.ForeignKey(Schema, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    table_type = models.CharField(max_length=255)
    row_count = models.IntegerField(default=0, null=True)

    def __str__(self) -> str:
        return f'{self.schema.name}.{self.name}'

class Column(TenantAwareModel):
    table = models.ForeignKey(Table, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    data_type = models.CharField(max_length=255)
    nullable = models.BooleanField(default=False)
    primary_key = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f'{self.table.name}.{self.name}'


