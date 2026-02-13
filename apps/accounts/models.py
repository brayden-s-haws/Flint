from __future__ import annotations

from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel


class Account(TimeStampedModel):
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def __str__(self) -> str:
        return self.name

class AccountMembership(TimeStampedModel):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=255, choices=[('owner', 'Owner')])

    def __str__(self) -> str:
        return f'{self.account.name} - {self.user.email}'