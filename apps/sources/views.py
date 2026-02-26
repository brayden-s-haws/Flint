from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView
from django.urls import reverse_lazy
from django.http import HttpResponse
from django.forms import BaseModelForm
from apps.core.mixins import TenantQuerysetMixin

from .models import Source
from .forms import SourceForm
from .encryption import encrypt_credentials


class SourceListView(LoginRequiredMixin, TenantQuerysetMixin, ListView):
    model = Source
    template_name = 'sources/source_list.html'
    context_object_name = 'sources'


class SourceCreateView(LoginRequiredMixin, CreateView):
    model = Source
    form_class = SourceForm
    template_name = 'sources/source_form.html'
    success_url = reverse_lazy('sources:list')

    def form_valid(self, form: BaseModelForm) -> HttpResponse:
        source_instance = form.save(commit=False)
        credentials_dict = {
            'host': form.cleaned_data['host'],
            'port': form.cleaned_data['port'],
            'dbname': form.cleaned_data['dbname'],
            'user': form.cleaned_data['user'],
            'password': form.cleaned_data['password'],
        }
        source_instance.credentials = encrypt_credentials(credentials_dict)
        source_instance.account = self.request.account  # type: ignore[attr-defined]
        source_instance.save()
        self.object = source_instance
        return super().form_valid(form)
