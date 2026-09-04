""" Views for managing sources: list/create/edit/delete/detail, connection testing, manual and scheduled syncs, demo-data loading, and the HTMX connect-form field swap. Credentials are encrypted on save and only ever decrypted server-side for connector use. """
from __future__ import annotations

import logging
from typing import Any
from datetime import timedelta, datetime
from croniter import croniter
from cron_descriptor import ExpressionDescriptor
import json

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django.db.models import Max, QuerySet, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView, CreateView, DetailView, UpdateView, DeleteView
from django.urls import reverse_lazy, reverse
from django.http import HttpResponse, HttpRequest
from django.forms import BaseModelForm
from django.utils import timezone

from apps.core.mixins import TenantQuerysetMixin
from .connectors.registry import build_connector
from apps.insights.models import InsightTarget
from .models import Source, SourceType, SourceSchedule
from .forms import SourceForm, ScheduleForm
from .tasks import sync_source_task, run_scheduled_sync
from .encryption import encrypt_credentials, decrypt_credentials
from .scheduling import create_or_update_source_schedule, toggle_source_schedule, delete_source_schedule

logger = logging.getLogger(__name__)


class SourceListView(LoginRequiredMixin, TenantQuerysetMixin, ListView):
    """
    - Lists the account's sources with each one's last-synced time (annotated from its sync logs) and schedule.
    - Supports text search (name or source-type name) and filtering by source type.
    """
    model = Source
    template_name = 'sources/source_list.html'
    context_object_name = 'sources'

    def get_queryset(self) -> QuerySet[Source]:
        q = self.request.GET.get('q')
        source_type = self.request.GET.get('type')
        qs = super().get_queryset().select_related('schedule').annotate(last_synced_at=Max('sourcesynclog__completed_at'))
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(source_type__name__icontains=q))
        if source_type:
            qs = qs.filter(source_type__name=source_type)
        return qs

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['source_types'] = SourceType.objects.all()
        context['q'] = self.request.GET.get('q')
        context['source_type'] = self.request.GET.get('type')
        return context


class SourceCreateView(LoginRequiredMixin, CreateView):
    """
    - Connects a new source: assembles the credentials dict from the form (JSON `config` for Airbyte types, the DB fields otherwise), encrypts it, and stamps the current account before saving.
    - get_context_data resolves the selected source type so the template can render the matching connection fields on redisplay.
    """
    model = Source
    form_class = SourceForm
    template_name = 'sources/source_form.html'
    success_url = reverse_lazy('sources:list')

    def form_valid(self, form: BaseModelForm) -> HttpResponse:
        source_instance = form.save(commit=False)
        if source_instance.source_type.airbyte_connector_name:
            credentials_dict = json.loads(form.cleaned_data['config'])
        else:
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

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        raw = context['form']['source_type'].value()
        context['selected_source_type'] = SourceType.objects.filter(pk=raw).first() if raw else None
        return context

class SourceUpdateView(LoginRequiredMixin, TenantQuerysetMixin, UpdateView):
    """
    - Edits an existing source. get_initial decrypts the stored credentials to pre-fill the form (JSON config for Airbyte, individual DB fields otherwise); form_valid re-encrypts on save.
    - Tenant-scoped, so a user can only edit sources in their own account. Redirects to the source detail page on success.
    """
    model = Source
    form_class = SourceForm
    template_name = 'sources/source_form.html'

    def get_initial(self) -> dict[str, Any]:
        initial = super().get_initial()
        source = self.object
        credentials_dict = decrypt_credentials(source.credentials)
        if source.source_type.airbyte_connector_name:
            initial['config'] = json.dumps(credentials_dict, indent=2)
        else:
            initial['host'] = credentials_dict['host']
            initial['port'] = credentials_dict['port']
            initial['dbname'] = credentials_dict['dbname']
            initial['user'] = credentials_dict['user']
            initial['password'] = credentials_dict['password']
        return initial

    def form_valid(self, form: BaseModelForm) -> HttpResponse:
        source_instance = form.save(commit=False)
        if source_instance.source_type.airbyte_connector_name:
            credentials_dict = json.loads(form.cleaned_data['config'])
        else:
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

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        raw = context['form']['source_type'].value()
        context['selected_source_type'] = SourceType.objects.filter(pk=raw).first() if raw else None
        return context

class SourceDeleteView(LoginRequiredMixin, TenantQuerysetMixin, DeleteView):
    """Deletes a source (tenant-scoped). Its catalog, sync logs, schedule, and insights are cleaned up by cascades and the pre_delete signal in signals.py."""
    model = Source
    template_name = 'sources/source_delete.html'
    success_url = reverse_lazy('sources:list')

class SourceDetailView(LoginRequiredMixin, TenantQuerysetMixin, DetailView):
    """
    - The source's main page. Assembles sync history + latest/last-successful sync, the discovered schemas/tables, the source overview and use-case insights (with the same 24h rate-limit state used elsewhere), and schedule details.
    - For a scheduled source it derives the human-readable cadence and next run time from the backing crontab (via croniter/cron_descriptor), falling back to the stored frequency label if description fails.
    """
    model = Source
    template_name = 'sources/source_detail.html'
    context_object_name = 'source'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['sync_logs'] = self.object.sourcesynclog_set.order_by('-started_at')
        context['sync_log'] = context['sync_logs'].first()
        context['last_synced_at'] = self.object.sourcesynclog_set.filter(status='success').order_by('-completed_at').values_list('completed_at', flat=True).first()
        context['schemas'] = self.object.schema_set.prefetch_related('table_set')
        content_type = ContentType.objects.get_for_model(self.object)
        target = InsightTarget.objects.filter(content_type=content_type, object_id=self.object.pk, account=self.request.account, insight__insight_type='source_overview').select_related(
            'insight').first()
        context['source_overview'] = target.insight.text if target and target.insight.status == 'active' else None
        context['source_overview_insight'] = target.insight if target else None
        use_case_targets = InsightTarget.objects.filter(content_type=content_type, object_id=self.object.pk, account=self.request.account, insight__insight_type='use_case_suggestion').select_related('insight').order_by('-insight__created_at')
        context['use_cases'] = [uct.insight for uct in use_case_targets]
        most_recent = use_case_targets.first()
        if most_recent:
            age = timezone.now() - most_recent.insight.created_at
            if age < timedelta(hours=24):
                context['use_case_rate_limited'] = True
                context['use_case_hours_remaining'] = 24 - int(age.total_seconds() // 3600)
            else:
                context['use_case_rate_limited'] = False
        else:
            context['use_case_rate_limited'] = False
        # Schedule context
        try:
            schedule = self.object.schedule
        except SourceSchedule.DoesNotExist:
            schedule = None
        context['schedule'] = schedule
        context['schedule_form'] = ScheduleForm(initial={'frequency': schedule.frequency if schedule else None})
        if schedule and schedule.cron_expression:
            cron = schedule.cron_expression
            context['next_run'] = croniter(cron, timezone.now()).get_next(datetime)
            try:
                context['frequency_display'] = ExpressionDescriptor(cron).get_description()
            except Exception as e:
                logger.warning("cron_descriptor failed for %s: %s", cron, e)
                context['frequency_display'] = schedule.get_frequency_display()
        else:
            context['next_run'] = None
            context['frequency_display'] = None
        return context

@login_required
def test_connection(request: HttpRequest, pk: int) -> HttpResponse:
    """Decrypts the source's credentials, builds its connector, runs test_connection, and redirects to the detail page with a success/failure flash message."""
    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)
    source = get_object_or_404(Source, pk=pk, account=request.account) # type: ignore[attr-defined]
    credentials = decrypt_credentials(source.credentials)
    connector = build_connector(source.source_type, credentials)
    success = connector.test_connection()
    if success:
        messages.success(request, 'Connection test successful')
    else:
        messages.error(request, 'Connection test failed. Check your credentials.')
    return redirect('sources:detail', pk=pk)

@login_required
def sync_source(request: HttpRequest, pk:int) -> HttpResponse:
    """POST-only. Opens a running sync log and dispatches sync_source_task. Returns the sync-status partial for HTMX requests (to start the poll), or redirects to detail otherwise."""
    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)
    source = get_object_or_404(Source, pk=pk, account=request.account) # type: ignore[attr-defined]
    sync_log = source.sourcesynclog_set.create(account=source.account, status='running', started_at=timezone.now())
    sync_source_task.delay(source.pk, sync_log.pk)

    if request.headers.get('HX-Request') == 'true':
        sync_logs = source.sourcesynclog_set.order_by('-started_at')
        return render(request, 'sources/_sync_status_response.html', {'sync_log': sync_log, 'source': source, 'sync_logs': sync_logs})
    return redirect('sources:detail', pk=pk)

@login_required
def sync_status(request: HttpRequest, pk:int) -> HttpResponse:
    """HTMX poll target for an in-progress sync: returns the status partial while running, and once the latest sync succeeds returns an empty response with HX-Refresh so the page reloads with fresh catalog data."""
    source = get_object_or_404(Source, pk=pk, account=request.account) # type: ignore[attr-defined]
    sync_log = source.sourcesynclog_set.order_by('-started_at').first()
    if sync_log is None:
        return HttpResponse('')
    if sync_log.status == 'success':
        response = HttpResponse('')
        response['HX-Refresh'] = 'true'
        return response
    sync_logs = source.sourcesynclog_set.order_by('-started_at')
    return render(request, 'sources/_sync_status_response.html', {'sync_log': sync_log, 'source': source, 'sync_logs': sync_logs})

@login_required
def schedule_create(request: HttpRequest, pk:int) -> HttpResponse:
    """Creates or updates the source's schedule from the submitted frequency; kicks off an immediate sync when the schedule is newly created or resumed from paused. Redirects to detail with a flash message."""
    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)
    source = get_object_or_404(Source, pk=pk, account=request.account) # type: ignore[attr-defined]
    try:
        was_paused = not source.schedule.is_enabled
    except SourceSchedule.DoesNotExist:
        was_paused = False
    form = ScheduleForm(request.POST)
    if not form.is_valid():
        messages.error(request, 'Invalid schedule frequency.')
        return redirect('sources:detail', pk=pk)
    schedule, created = create_or_update_source_schedule(source, form.cleaned_data['frequency'])
    if created or was_paused:
        run_scheduled_sync.delay(source.pk)
        messages.success(request, f'Schedule set to {schedule.get_frequency_display().lower()} - first sync starting now.')
    else:
        messages.success(request, f'Schedule set to {schedule.get_frequency_display().lower()}.')
    return redirect('sources:detail', pk=pk)

@login_required
def schedule_toggle(request: HttpRequest, pk: int) -> HttpResponse:
    """Pauses or resumes the source's schedule; on resume, triggers an immediate sync. 404 if the source has no schedule. Redirects to detail with a flash message."""
    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)
    source = get_object_or_404(Source, pk=pk, account=request.account) # type: ignore[attr-defined]
    try:
        schedule, was_paused = toggle_source_schedule(source)
    except SourceSchedule.DoesNotExist:
        return HttpResponse('No schedule to toggle', status=404)
    if was_paused:
        run_scheduled_sync.delay(source.pk)
        messages.success(request, 'Schedule resumed. Next sync starting now.')
    else:
        messages.success(request, 'Schedule paused.')
    return redirect('sources:detail', pk=pk)

@login_required
def schedule_delete(request: HttpRequest, pk: int) -> HttpResponse:
    """Removes the source's schedule (and its backing periodic task) and redirects to detail with a flash message."""
    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)
    source = get_object_or_404(Source, pk=pk, account=request.account) # type: ignore[attr-defined]
    delete_source_schedule(source)
    messages.success(request, 'Schedule deleted.')
    return redirect('sources:detail', pk=pk)

@login_required
def load_demo_data(request: HttpRequest) -> HttpResponse:
    """Provisions the built-in demo sources (Sales scenario) for the account, idempotently via get_or_create, with encrypted scenario credentials. The user syncs each one afterwards to populate the catalog."""
    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)
    demo_sources = [
        {'source_type_name': 'HubSpot (Demo)', 'source_name': 'HubSpot (Demo)', 'scenario': 'sales', 'source': 'hubspot'},
        {'source_type_name': 'Google Analytics (Demo)', 'source_name': 'Google Analytics (Demo)', 'scenario': 'sales', 'source': 'ga'},
        {'source_type_name': 'Customer Database (Demo)', 'source_name': 'Customer Database (Demo)', 'scenario': 'sales', 'source': 'customerdb'},
    ]
    for demo in demo_sources:
        source_type = SourceType.objects.get(name=demo['source_type_name'])
        credentials = encrypt_credentials({'scenario': demo['scenario'], 'source': demo['source']})
        Source.objects.get_or_create(
            account=request.account , # type: ignore[attr-defined]
            source_type=source_type,
            defaults={'name': demo['source_name'], 'credentials': credentials}
        )

    messages.success(request, 'Demo sources loaded. Sync each one to populate the catalog.')
    return redirect('sources:list')

@login_required
def connect_fields(request: HttpRequest) -> HttpResponse:
    """HTMX endpoint backing the connect form's field swap: given the chosen source_type, returns the connection-fields partial (Airbyte JSON config vs native DB fields) for the source_type select to load on change."""
    raw = request.GET.get('source_type')
    source_type = SourceType.objects.filter(pk=raw).first() if raw else None
    return render(request, 'sources/_connection_fields.html', {'form': SourceForm(), 'selected_source_type': source_type})

