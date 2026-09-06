from __future__ import annotations

from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = 'apps.users'
    label = 'users'

    def ready(self) -> None:
        """ Imports signals on startup so that user login and logout can be logged. """
        import apps.users.signals  # noqa: F401
