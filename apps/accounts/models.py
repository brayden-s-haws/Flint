from __future__ import annotations

import secrets

from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel, TenantAwareModel

ROLE_CHOICES = [
    ('owner', 'Owner'),
    ('member', 'Member'),
]


def generate_invite_token() -> str:
    return secrets.token_urlsafe(48)

class Account(TimeStampedModel):
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def __str__(self) -> str:
        return self.name

class AccountMembership(TimeStampedModel):
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=255, choices=ROLE_CHOICES)

    def __str__(self) -> str:
        return f'{self.account.name} - {self.user.email}'

class AccountInvitation(TenantAwareModel):
    email = models.EmailField()
    role = models.CharField(max_length=255, choices=ROLE_CHOICES, default='member')
    token = models.CharField(max_length=64, unique=True, default=generate_invite_token)
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    accepted = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f'{self.email} → {self.account.name}'
