from __future__ import annotations

from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Max, QuerySet
from django.views.generic import ListView, CreateView, DetailView
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

    def get_queryset(self) -> QuerySet[Source]:
        return super().get_queryset().annotate(last_synced_at=Max('sourcesynclog__completed_at'))


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

class SourceDetailView(LoginRequiredMixin, TenantQuerysetMixin, DetailView):
    model = Source
    template_name = 'sources/source_detail.html'
    context_object_name = 'source'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['sync_logs'] = self.object.sourcesynclog_set.order_by('-started_at')
        return context