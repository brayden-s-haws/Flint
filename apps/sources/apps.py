from __future__ import annotations

from django.apps import AppConfig


class SourcesConfig(AppConfig):
    name = 'apps.sources'
    label = 'sources'

    def ready(self) -> None:
        import apps.sources.signals # noqa: F401
