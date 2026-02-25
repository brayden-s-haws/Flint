from __future__ import annotations

from django.forms import ModelForm, CharField, IntegerField, PasswordInput

from .models import Source


class SourceForm(ModelForm):

    host = CharField(max_length=255)
    port = IntegerField(initial=5432)
    dbname = CharField(max_length=255)
    user = CharField(max_length=255)
    password = CharField(widget=PasswordInput())

    class Meta:
        model = Source
        fields = ['name', 'source_type']