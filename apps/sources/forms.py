from __future__ import annotations

import json

from django.forms import ModelForm, CharField, IntegerField, PasswordInput, Form, RadioSelect, ChoiceField, Textarea

from .models import Source, FREQUENCY_CHOICES, SourceType


class SourceForm(ModelForm):

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
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'w-full bg-flint-card border border-flint-border-em rounded-md px-3 py-2 text-sm text-flint-text focus:outline-none focus:ring-2 focus:ring-flint-orange'})

    def clean(self):
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

    frequency = ChoiceField(choices=FREQUENCY_CHOICES, widget=RadioSelect)
