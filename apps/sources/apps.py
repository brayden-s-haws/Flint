""" App config for the sources app; imports signals on startup so the source-deletion cleanup handlers are registered. """
from __future__ import annotations

from django.apps import AppConfig


class SourcesConfig(AppConfig):
    name = 'apps.sources'
    label = 'sources'

    def ready(self) -> None:
        """Import the signals module on startup for its registration side effect (source-deletion cleanup)."""
        import apps.sources.signals # noqa: F401
