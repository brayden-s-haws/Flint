""" App config for the sources app; imports signals on startup so the source-deletion cleanup handlers are registered. """
from __future__ import annotations

import logging

from django.apps import AppConfig
from django.conf import settings


logger = logging.getLogger(__name__)


class SourcesConfig(AppConfig):
    name = 'apps.sources'
    label = 'sources'

    def ready(self) -> None:
        """Import the signals module on startup for its registration side effect (source-deletion cleanup)."""
        import apps.sources.signals # noqa: F401
        if settings.ENCRYPTION_KEY:
            logger.info("ENCRYPTION_KEY is set")
        else:
            logger.warning("ENCRYPTION_KEY is not set - credential encryption and decryption will fail")
