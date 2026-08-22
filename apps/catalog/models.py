""" Catalogs metadata from a connected source. Follows a hierarchy of schemas, tables, and columns. All data is populated by connecting to the source and pulling details, no data is entered by users.
Table statistics are updated on a per-sync basis. All models are tenant-aware, so users only see data related to their account. """
from __future__ import annotations

from django.db import models

from apps.core.models import TenantAwareModel

class Schema(TenantAwareModel):
    """
    Schemas are the top-level container for tables and columns.
    """
    source = models.ForeignKey('sources.Source', on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')

    def __str__(self) -> str:
        return self.name

class Table(TenantAwareModel):
    """
    Tables are the second-level container for columns.
    """
    schema = models.ForeignKey(Schema, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    table_type = models.CharField(max_length=255) # Contains a value that represents the type of table, such as "table", "view", or "materialized view".
    row_count = models.IntegerField(default=0, null=True) # Latest row count, overwritten each sync. Defaults to 0 and is nullable because some sources do not provide row count information.

    def __str__(self) -> str:
        return f'{self.schema.name}.{self.name}'

class Column(TenantAwareModel):
    """
    Columns are the lowest-level container for data.
    """
    table = models.ForeignKey(Table, on_delete=models.CASCADE)
    name = models.CharField(max_length=255)
    data_type = models.CharField(max_length=255)
    nullable = models.BooleanField(default=False)
    primary_key = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f'{self.table.name}.{self.name}'

class TableStatistics(TenantAwareModel):
    """
    Table statistics are a snapshot history with multiple rows, one per sync. The most recent row is the current state of the table.
    """
    table = models.ForeignKey(Table, on_delete=models.CASCADE)
    row_count = models.BigIntegerField(null=True, blank=True)  # Row count captured as part of a point-in-time snapshot. This shows the row count at time of sync unlike Table.row_count that captures the latest row count.
    column_stats = models.JSONField(default=dict) # Contains statistics per column including null rate, distinct values, and common values.

    def __str__(self) -> str:
        return f'{self.table.name} stats (synced at {self.created_at.strftime("%Y-%m-%d %H:%M:%S")})'


