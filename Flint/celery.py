""" Celery application for the Flint project. Configured from Django settings (CELERY_* namespace) and auto-discovers each app's tasks.py. """
from __future__ import annotations

import os

from celery import Celery

# Tell Celery where to find Django's settings module.
# This MUST happen before the Celery() instance is created.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'Flint.settings')

# Create the Celery app, named after the Django project.
app = Celery('Flint')

# Read all CELERY_* settings from Django's settings.py.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Scan every INSTALLED_APP for a tasks.py module and register its tasks.                                                                                                                                                                          
app.autodiscover_tasks()