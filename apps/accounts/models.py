""" Defines an account and manages the relationship between users and accounts. AccountInvitation extends TenantAwareModel, unlike Account and AccountMembership. This is needed because Account and
Membership define the tenant boundary. """
from __future__ import annotations

import secrets

from django.db import models
from django.conf import settings
from apps.core.models import TimeStampedModel, TenantAwareModel

# Role choices for account memberships. Constants to be expanded as new roles are defined.
ROLE_CHOICES = [
    ('owner', 'Owner'),
    ('member', 'Member'),
]


def generate_invite_token() -> str:
    return secrets.token_urlsafe(48)

class Account(TimeStampedModel):
    """
    An account is auto-created when a user registers via signals.create_account_for_new_user.
    """
    name = models.CharField(max_length=255)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    def __str__(self) -> str:
        return self.name

class AccountMembership(TimeStampedModel):
    """
    - Joins users and accounts, it carries information about the user's role in the account.
    - Roles are limited to the ROLE_CHOICES constants in this file.
    """
    account = models.ForeignKey(Account, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=255, choices=ROLE_CHOICES)

    def __str__(self) -> str:
        return f'{self.account.name} - {self.user.email}'

class AccountInvitation(TenantAwareModel):
    """
    Relies on a token to validate the invitation. The expiry of the token is set in .views.accept_invite_view.
    """
    email = models.EmailField()
    role = models.CharField(max_length=255, choices=ROLE_CHOICES, default='member')
    token = models.CharField(max_length=64, unique=True, default=generate_invite_token) # Use URL-safe token for invitation links
    invited_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    accepted = models.BooleanField(default=False)

    def __str__(self) -> str:
        return f'{self.email} → {self.account.name}'
