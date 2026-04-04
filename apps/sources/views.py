from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.db.models import Max, QuerySet
from django.shortcuts import get_object_or_404, redirect
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.http import HttpResponse, HttpRequest
from django.forms import BaseModelForm
from django.utils import timezone
from apps.core.mixins import TenantQuerysetMixin
from .connectors.registry import get_connector

from apps.catalog.models import Schema, Table, Column
from apps.insights.models import InsightTarget, Insight
from apps.insights.services.provider import get_service
from .models import Source, SourceSyncLog
from .forms import SourceForm
from .encryption import encrypt_credentials, decrypt_credentials


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

class SourceUpdateView(LoginRequiredMixin, TenantQuerysetMixin, UpdateView):
    model = Source
    form_class = SourceForm
    template_name = 'sources/source_form.html'

    def get_initial(self) -> dict[str, Any]:
        initial = super().get_initial()
        source = self.object
        credentials_dict = decrypt_credentials(source.credentials)
        initial['host'] = credentials_dict['host']
        initial['port'] = credentials_dict['port']
        initial['dbname'] = credentials_dict['dbname']
        initial['user'] = credentials_dict['user']
        initial['password'] = credentials_dict['password']
        return initial

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
        source_instance.save()
        self.object = source_instance
        return super().form_valid(form)

    def get_success_url(self) -> str:
        return reverse('sources:detail', kwargs={'pk': self.object.pk})

class SourceDeleteView(LoginRequiredMixin, TenantQuerysetMixin, DeleteView):
    model = Source
    template_name = 'sources/source_delete.html'
    success_url = reverse_lazy('sources:list')

class SourceDetailView(LoginRequiredMixin, TenantQuerysetMixin, DetailView):
    model = Source
    template_name = 'sources/source_detail.html'
    context_object_name = 'source'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['sync_logs'] = self.object.sourcesynclog_set.order_by('-started_at')
        context['last_synced_at'] = self.object.sourcesynclog_set.filter(status='success').order_by('-completed_at').values_list('completed_at', flat=True).first()
        context['schemas'] = self.object.schema_set.prefetch_related('table_set')
        content_type = ContentType.objects.get_for_model(self.object)
        target = InsightTarget.objects.filter(content_type=content_type, object_id=self.object.pk, account=self.request.account).select_related('insight').first()
        context['source_overview'] = target.insight.text if target else None

        return context

@login_required
def test_connection(request: HttpRequest, pk: int) -> HttpResponse:
    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)
    source = get_object_or_404(Source, pk=pk, account=request.account) # type: ignore[attr-defined]
    credentials = decrypt_credentials(source.credentials)
    connector_class = get_connector(source.source_type.name)
    connector = connector_class(credentials)
    success = connector.test_connection()
    if success:
        messages.success(request, 'Connection test successful')
    else:
        messages.error(request, 'Connection test failed. Check your credentials.')
    return redirect('sources:detail', pk=pk)

@login_required
def sync_source(request: HttpRequest, pk:int) -> HttpResponse:
    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)
    source = get_object_or_404(Source, pk=pk, account=request.account) # type: ignore[attr-defined]
    source_sync = source.sourcesynclog_set.create(account=source.account, status='running', started_at=timezone.now())
    try:
        credentials = decrypt_credentials(source.credentials)
        connector_class = get_connector(source.source_type.name)
        connector = connector_class(credentials)
        catalog = connector.discover_catalog()
        records_synced = 0
        for schema_data in catalog:
            schema, _ = Schema.objects.get_or_create(
                source=source, name=schema_data['name'],
                defaults={'account': source.account}
            )
            for table_data in schema_data['tables']:
                table, _ = Table.objects.get_or_create(
                    schema=schema, name=table_data['name'],
                    defaults={'account': source.account, 'table_type': table_data['table_type']}
                )
                metadata = connector.get_table_metadata(schema_data['name'], table_data['name'])
                table.row_count = metadata['row_count']
                table.table_type = table_data['table_type']
                table.save()
                for col_data in table_data['columns']:
                    col, _ = Column.objects.get_or_create(
                        table=table, name=col_data['name'],
                        defaults={'account': source.account, 'data_type': col_data['data_type'], 'nullable': col_data['nullable'], 'primary_key': col_data['primary_key']}
                    )
                    col.data_type = col_data['data_type']
                    col.nullable = col_data['nullable']
                    col.primary_key = col_data['primary_key']
                    col.save()
                records_synced += 1
        source_sync.completed_at = timezone.now()
        source_sync.status = 'success'
        source_sync.records_synced = records_synced
        if source.first_synced_at is None:
            source.first_synced_at = timezone.now()
            source.save()
        source_sync.save()
        content_type = ContentType.objects.get_for_model(Source)
        already_exists = InsightTarget.objects.filter(content_type=content_type, object_id=source.pk, account=source.account).exists()
        if not already_exists:
            try:
                service = get_service('anthropic')
                text = service.generate_source_overview(source)
                insight = Insight.objects.create(account=source.account, text=text, insight_type='ai', status='active', insight_prompt=None)
                InsightTarget.objects.create(account=source.account, insight=insight, content_type=content_type, object_id=source.pk)
            except Exception as e:
                logger.exception("Failed to generate source overview for source %s", source.pk)
        messages.success(request, 'Source sync completed successfully')
        return redirect('sources:detail', pk=pk)
    except Exception as e:
        source_sync.status = 'failed'
        source_sync.error_message = str(e)
        source_sync.completed_at = timezone.now()
        source_sync.save()
        messages.error(request, f'Source sync failed: {e}')
        return redirect('sources:detail', pk=pk)