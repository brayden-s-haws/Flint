""" Abstract base models used across the application. TimeStampedModel provides created_at and updated_at fields, while TenantAwareModel enforces tenant scoping by adding an account foreign key. """
from __future__ import annotations

from django.db import models

class TimeStampedModel(models.Model):
    """
    Abstract base model providing created_at and updated_at fields.
    """
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

class TenantAwareModel(TimeStampedModel):
    """
    Abstract base model that adds the account foreign key that scopes a row to a tenant.
    """
    account = models.ForeignKey('accounts.Account', on_delete=models.CASCADE, related_name='%(class)ss') # %(class)ss generates a reverse accessor for each subclass.

    class Meta:
        abstract = True