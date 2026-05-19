from __future__ import annotations
import json

from django.conf import settings
from django_celery_beat.models import CrontabSchedule, PeriodicTask

from .models import Source, SourceSchedule

FREQUENCY_TO_CRONTAB: dict[str, dict[str, str]] = {
    'hourly': {'minute': '0', 'hour': '*', 'day_of_month': '*', 'month_of_year': '*', 'day_of_week': '*'},
    'daily': {'minute': '0', 'hour': '6', 'day_of_month': '*', 'month_of_year': '*', 'day_of_week': '*'},
    'weekly': {'minute': '0', 'hour': '6', 'day_of_month': '*', 'month_of_year': '*', 'day_of_week': '1'},
    'monthly': {'minute': '0', 'hour': '6', 'day_of_month': '1', 'month_of_year': '*', 'day_of_week': '*'},
}