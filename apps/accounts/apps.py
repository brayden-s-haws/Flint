""" Ensures that account creation during user signup is handled correctly. """
from __future__ import annotations

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'apps.accounts'
    label = 'accounts'

    def ready(self) -> None:
        """ Imports signals on startup so that new user registration triggers account creation. """
        import apps.accounts.signals  # noqa: F401