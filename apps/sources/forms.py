from __future__ import annotations

from django.forms import ModelForm, CharField, IntegerField, PasswordInput, Form, RadioSelect, ChoiceField

from .models import Source, FREQUENCY_CHOICES


class SourceForm(ModelForm):

    host = CharField(max_length=255)
    port = IntegerField(initial=5432)
    dbname = CharField(max_length=255)
    user = CharField(max_length=255)
    password = CharField(widget=PasswordInput())

    class Meta:
        model = Source
        fields = ['name', 'source_type']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'w-full bg-flint-card border border-flint-border-em rounded-md px-3 py-2 text-sm text-flint-text focus:outline-none focus:ring-2 focus:ring-flint-orange'})


class ScheduleForm(Form):

    frequency = ChoiceField(choices=FREQUENCY_CHOICES, widget=RadioSelect)
