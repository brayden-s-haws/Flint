from __future__ import annotations

from typing import Any

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from .models import Account, AccountMembership


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_account_for_new_user(sender: type, instance: Any, created: bool, **kwargs: Any) -> None:
    """Create an Account and owner membership when a new user registers."""
    if not created:
        return
    if getattr(instance, '_skip_account_creation', False) is True:
        return
    account = Account.objects.create(name=instance.email.split('@')[0], owner=instance)
    AccountMembership.objects.create(account=account, user=instance, role='owner')