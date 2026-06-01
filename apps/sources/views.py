from __future__ import annotations

import logging
from typing import Any
from datetime import timedelta, datetime
from croniter import croniter
from cron_descriptor import ExpressionDescriptor

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
from .connectors.registry import get_connector
from apps.insights.models import InsightTarget
from .models import Source, SourceType, SourceSchedule
from .forms import SourceForm, ScheduleForm
from .tasks import sync_source_task, run_scheduled_sync
from .encryption import encrypt_credentials, decrypt_credentials
from .scheduling import create_or_update_source_schedule, toggle_source_schedule, delete_source_schedule

logger = logging.getLogger(__name__)


class SourceListView(LoginRequiredMixin, TenantQuerysetMixin, ListView):
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
    sync_log = source.sourcesynclog_set.create(account=source.account, status='running', started_at=timezone.now())
    sync_source_task.delay(source.pk, sync_log.pk)

    if request.headers.get('HX-Request') == 'true':
        sync_logs = source.sourcesynclog_set.order_by('-started_at')
        return render(request, 'sources/_sync_status_response.html', {'sync_log': sync_log, 'source': source, 'sync_logs': sync_logs})
    return redirect('sources:detail', pk=pk)

@login_required
def sync_status(request: HttpRequest, pk:int) -> HttpResponse:
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
    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)
    source = get_object_or_404(Source, pk=pk, account=request.account) # type: ignore[attr-defined]
    delete_source_schedule(source)
    messages.success(request, 'Schedule deleted.')
    return redirect('sources:detail', pk=pk)

@login_required
def load_demo_data(request: HttpRequest) -> HttpResponse:
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

