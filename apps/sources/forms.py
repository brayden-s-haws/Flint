""" Forms for connecting/editing a source and setting its sync schedule. SourceForm carries both native database fields and an Airbyte JSON config field and validates whichever set the chosen source type needs. """
from __future__ import annotations

import json

from django.forms import ModelForm, CharField, IntegerField, PasswordInput, Form, RadioSelect, ChoiceField, Textarea
from django.urls import reverse

from .models import Source, FREQUENCY_CHOICES, SourceType


class SourceForm(ModelForm):
    """
    - One form serving both connector styles: native DB fields (host/port/dbname/user/password) and an Airbyte `config` JSON blob. All are optional at the field level; clean() enforces the right set based on the chosen source type.
    - Only non-demo source types are selectable. The source_type select carries HTMX attrs so picking a type swaps in the matching connection fields (see the connect_fields view) without a reload.
    """

    host = CharField(max_length=255, required=False)
    port = IntegerField(initial=5432, required=False)
    dbname = CharField(max_length=255, required=False)
    user = CharField(max_length=255, required=False)
    password = CharField(widget=PasswordInput(), required=False)
    config = CharField(widget=Textarea, required=False)

    class Meta:
        model = Source
        fields = ['name', 'source_type']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['source_type'].queryset = SourceType.objects.filter(is_demo=False)
        self.fields['source_type'].empty_label = 'Select a source type...'
        self.fields['source_type'].widget.attrs.update({'hx-get': reverse('sources:connect_fields'), 'hx-target': '#connection-fields', 'hx-trigger': 'change',})
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'w-full bg-flint-card border border-flint-border-em rounded-md px-3 py-2 text-sm text-flint-text focus:outline-none focus:ring-2 focus:ring-flint-orange'})

    def clean(self):
        """Validate the field set the chosen source type needs: Airbyte types require a non-empty, parseable JSON `config`; native types require all of host/port/dbname/user/password."""
        cleaned = super().clean() or {}
        source_type = cleaned.get('source_type')
        if source_type and source_type.airbyte_connector_name:
            config = cleaned.get('config')
            if not config:
                self.add_error('config', 'Config is required for this source type')
            else:
                try:
                    json.loads(config)
                except json.JSONDecodeError:
                    self.add_error('config', 'Invalid JSON config')
        else:
            for field_name in ['host', 'port', 'dbname', 'user', 'password']:
                if not cleaned.get(field_name):
                    self.add_error(field_name, f'{field_name.capitalize()} is required for this source type')
        return cleaned


class ScheduleForm(Form):
    """Single-field form for choosing a sync cadence (hourly/daily/weekly/monthly) as radio buttons."""

    frequency = ChoiceField(choices=FREQUENCY_CHOICES, widget=RadioSelect)
