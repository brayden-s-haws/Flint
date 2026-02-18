from __future__ import annotations

from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'apps.accounts'
    label = 'accounts'

    def ready(self) -> None:
        import apps.accounts.signals  # noqa: F401