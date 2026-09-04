""" Imports the Celery app at package load so it initializes with Django and shared_task uses it by default. """
from __future__ import annotations

from .celery import app as celery_app

__all__ = ('celery_app',)