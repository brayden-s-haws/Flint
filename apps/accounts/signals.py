""" Manages the creation of an Account and owner membership when a new user registers. """
from __future__ import annotations

from typing import Any
import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings

from .models import Account, AccountMembership


logger = logging.getLogger(__name__)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_account_for_new_user(sender: type, instance: Any, created: bool, **kwargs: Any) -> None:
    """Create an Account and owner membership when a new user registers."""
    if not created:
        return
    if getattr(instance, '_skip_account_creation', False) is True: # If user is created through account invitation, we need to skip account creation (set in .views.accept_invite_view).
        logger.debug("Skipping account creation for user %s", instance.id)
        return
    account = Account.objects.create(name=instance.email.split('@')[0], owner=instance)
    AccountMembership.objects.create(account=account, user=instance, role='owner') # By default, the first registered user in an account is the owner.
    logger.info("Created account %s for user %s", account.id, instance.id)