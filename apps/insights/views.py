""" Provides users with the ability to view, generate, and manage Insights for the various sources and tables within their organization. Covers both intra-source and cross-source insights. The
majority of the functionality here is focused on HTMX partial endpoints, allowing users to interact with insights in a more dynamic and responsive manner."""
from __future__ import annotations

import logging
from typing import Any
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.db.models import QuerySet, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import ListView, DetailView

from apps.catalog.models import Table
from apps.core.mixins import TenantQuerysetMixin
from apps.insights.models import Insight, InsightTarget
from apps.insights.tasks import generate_table_description_task, run_cross_source_discovery_task, generate_intra_source_use_cases_task
from apps.sources.models import Source


logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intra-Source Insights
# ---------------------------------------------------------------------------

class InsightListView(TenantQuerysetMixin, LoginRequiredMixin, ListView):
    """
    - Aggregates all insights for the current user's account including descriptions, intra-source use cases, and cross-source use cases.
    - Filtering works on a union basis so that users can search across a source and all of its tables.
    """
    model = Insight
    template_name = 'insights/insight_list.html'
    context_object_name = 'insights'

    def get_queryset(self) -> QuerySet[Insight]:
        q = self.request.GET.get('q')
        insight_type = self.request.GET.get('type')
        qs = super().get_queryset().select_related('insight_prompt').order_by('-created_at')
        source_pk = self.request.GET.get('source')
        if q:
            qs = qs.filter(text__icontains=q)
        if insight_type:
            qs = qs.filter(insight_type=insight_type)
        if source_pk:
            source_ct = ContentType.objects.get_for_model(Source)
            table_ct = ContentType.objects.get_for_model(Table)
            table_pks = Table.objects.filter(
                schema__source__pk=source_pk,
                schema__source__account=self.request.account  # type: ignore[attr-defined]
            ).values_list('pk', flat=True)
            qs = qs.filter(
                Q(insighttarget__content_type=source_ct, insighttarget__object_id=source_pk) |
                Q(insighttarget__content_type=table_ct, insighttarget__object_id__in=table_pks)
            )
        return qs # type: ignore[return-value]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['insight_types'] = Insight.objects.values_list('insight_type', flat=True).distinct()
        context['sources'] = Source.objects.filter(account=self.request.account) # type: ignore[attr-defined]
        context['q'] = self.request.GET.get('q')
        context['selected_insight_type'] = self.request.GET.get('type')
        context['selected_source'] = self.request.GET.get('source')
        return context

class InsightDetailView(TenantQuerysetMixin, LoginRequiredMixin, DetailView):
    """
    - Displays a single insight and a link back to the object it describes.
    - Resolves the target's URL by type: Tables link to the catalog detail page, Sources to the source detail page.
    """
    model = Insight
    template_name = 'insights/insight_detail.html'
    context_object_name = 'insight'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        target = self.object.insighttarget_set.first()
        context['target_object'] = target.target if target else None
        if isinstance(context['target_object'], Table):
            context['target_url'] = reverse('catalog:detail', args=[context['target_object'].pk])
        elif isinstance(context['target_object'], Source):
            context['target_url'] = reverse('sources:detail', args=[context['target_object'].pk])
        else:
            context['target_url'] = None
        return context

def build_use_cases_context(source: Source) -> dict[str, Any]:
    """
    - Assembles the full render state for a source's "Suggested Uses" section, shared by the poll endpoint and the generate endpoint so both render an identical section.
    - Gathers the active source overview text, the active use-case suggestions (newest first), and boolean flags for whether a generation is currently pending or has failed.
    - Computes the 24h regeneration rate limit from the most recent use case: sets `use_case_rate_limited` and the whole `use_case_hours_remaining` countdown used to disable the Regenerate control.
    """
    source_ct = ContentType.objects.get_for_model(Source)
    overview_target = InsightTarget.objects.filter(
        content_type=source_ct, object_id=source.pk, account=source.account,
        insight__insight_type='source_overview'
    ).select_related('insight').first()
    overview_insight = overview_target.insight if overview_target else None
    source_overview = overview_insight.text if overview_insight and overview_insight.status == 'active' else None

    use_case_targets = InsightTarget.objects.filter(
        content_type=source_ct, object_id=source.pk, account=source.account,
        insight__insight_type='use_case_suggestion', insight__status='active',
    ).select_related('insight').order_by('-insight__created_at')
    use_cases = [uct.insight for uct in use_case_targets]

    use_cases_generating = InsightTarget.objects.filter(
        content_type=source_ct, object_id=source.pk, account=source.account,
        insight__insight_type='use_case_suggestion', insight__status='pending',
    ).exists()

    use_cases_failed = InsightTarget.objects.filter(
        content_type=source_ct, object_id=source.pk, account=source.account,
        insight__insight_type='use_case_suggestion', insight__status='failed',
    ).exists()

    rate_limited = False
    hours_remaining = 0
    most_recent = use_case_targets.first()
    if most_recent:
        age = timezone.now() - most_recent.insight.created_at
        if age < timedelta(hours=24):
            rate_limited = True
            hours_remaining = 24 - int(age.total_seconds() // 3600)

    return {
        'source': source,
        'source_overview': source_overview,
        'source_overview_insight': overview_insight,
        'use_cases': use_cases,
        'use_case_rate_limited': rate_limited,
        'use_case_hours_remaining': hours_remaining,
        'use_cases_generating': use_cases_generating,
        'use_cases_failed': use_cases_failed,
    }


@login_required
def use_cases_status(request, source_id: int) -> HttpResponse:
    """
    - HTMX poll target for the Suggested Uses section; re-renders the section partial so a pending generation swaps to its results (or a failure) without a page reload.
    """
    source = get_object_or_404(Source, pk=source_id, account=request.account)
    return render(request, 'sources/_use_cases_section.html', build_use_cases_context(source))


@login_required
@require_POST
def generate_intra_use_case_suggestions(request, source_id: int) -> HttpResponse:
    """
    - Kicks off async intra-source use-case generation for a source, then returns the Suggested Uses partial so the user immediately sees the pending state.
    - Enforces two preconditions, each returning a 400 the HTMX layer surfaces inline: the source must already have a Source Overview, and generation is rate-limited to once per 24h.
    - Creates a `pending` placeholder insight (and its target) up front and passes its id to the task, which fills it in or marks it failed. See `generate_intra_source_use_cases_task`.
    """
    source = get_object_or_404(Source, pk=source_id, account=request.account)
    source_ct = ContentType.objects.get_for_model(Source)

    has_overview = InsightTarget.objects.filter(
        content_type=source_ct, object_id=source.pk, account=source.account,
        insight__insight_type='source_overview'
        ).exists()
    if not has_overview:
        logger.info("Use case generation blocked: no overview for source %s", source.pk)
        return HttpResponse("Generate a Source Overview before generating use case suggestions.", status=400)

    recent_suggestion = InsightTarget.objects.filter(
        content_type=source_ct, object_id=source.pk, account=source.account,
        insight__insight_type='use_case_suggestion',
        insight__status='active',
    ).select_related('insight').order_by('-insight__created_at').first()
    if recent_suggestion and recent_suggestion.insight.created_at > timezone.now() - timedelta(hours=24):
        logger.info("Use case generation rate-limited for source %s", source.pk)
        return HttpResponse("Use case suggestions were generated recently. Try again in 24 hours.", status=400)

    placeholder = Insight.objects.create(account=source.account, text='', insight_type='use_case_suggestion', status='pending', structured_data=None)
    InsightTarget.objects.create(account=source.account, insight=placeholder,
        content_type=source_ct, object_id=source.pk)
    generate_intra_source_use_cases_task.delay(source.id, placeholder.pk)

    return render(request, 'sources/_use_cases_section.html', build_use_cases_context(source))

@login_required
@require_POST
def rate_insight(request, insight_id: int) -> HttpResponse:
    """
    - Records the user's thumbs up/down feedback on an insight and re-renders the rating buttons partial.
    - Acts as a toggle: submitting the rating an insight already has clears it back to 'none'; any value other than 'approved'/'rejected' is a 400.
    """
    insight = get_object_or_404(Insight, pk=insight_id, account=request.account)
    rating = request.POST.get('rating')

    if rating != 'approved' and rating != 'rejected':
        logger.warning("Invalid rating value for insight %s", insight.pk)
        return HttpResponse("Invalid rating value", status=400)

    if insight.rating == rating:
        insight.rating = 'none'
    else:
        insight.rating = rating

    insight.save()
    return render(request, 'insights/_rating_buttons.html', {'insight': insight})

@login_required
def insight_status(request, insight_id: int) -> HttpResponse:
    """
    - HTMX poll target for async-generated insights; returns a different partial depending on the insight's status (active content, pending spinner, or failed state).
    - An unrecognized status is a 400.
    """
    insight = get_object_or_404(Insight, pk=insight_id, account=request.account)
    status = insight.status

    if status == 'active':
        return render(request, 'insights/_insight_content.html', {'insight': insight})
    elif status == 'pending':
        return render(request, 'insights/_insight_pending.html', {'insight': insight})
    elif status == 'failed':
        return render(request, 'insights/_insight_failed.html', {'insight': insight})
    else:
        logger.warning("Invalid insight status for insight %s", insight.pk)
        return HttpResponse("Invalid insight status", status=400)

@login_required
@require_POST
def insight_retry(request, insight_id: int) -> HttpResponse:
    """
    - Re-dispatches generation for a failed insight, resets it to 'pending', and returns the pending partial so the spinner resumes.
    - Only a 'failed' insight can be retried (otherwise a 400).
    """
    insight = get_object_or_404(Insight, pk=insight_id, account=request.account)
    if insight.status != 'failed':
        logger.warning("Retry rejected: insight %s not failed (status: %s)", insight.pk, insight.status)
        return HttpResponse("Cannot retry an insight that has not failed", status=400)
    insight.status = 'pending'
    insight.save()
    generate_table_description_task.delay(insight.id)
    return render(request, 'insights/_insight_pending.html', {'insight': insight})

# ---------------------------------------------------------------------------
# Cross-Source Insights
# ---------------------------------------------------------------------------

class CrossSourceDiscoveryView(TenantQuerysetMixin, LoginRequiredMixin, ListView):
    """
    - Lists the account's cross-source use-case insights (excluding dismissed ones) and the synced sources available to pair for a new run.
    - Supports text search and filtering by a participating source.
    """
    model = Insight
    template_name = 'insights/cross_source_discovery.html'
    context_object_name = 'insights'

    def get_queryset(self) -> QuerySet[Insight]:
        q = self.request.GET.get('q')
        source_pk = self.request.GET.get('source')
        qs = super().get_queryset().filter(insight_type='cross_source_use_case').exclude(status='dismissed').prefetch_related('insighttarget_set').order_by('-created_at')
        if q:
            qs = qs.filter(text__icontains=q)
        if source_pk:
            source_ct = ContentType.objects.get_for_model(Source)
            qs = qs.filter(insighttarget__content_type=source_ct, insighttarget__object_id=source_pk).distinct()
        return qs # type: ignore[return-value]

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['sources'] = Source.objects.filter(account=self.request.account, first_synced_at__isnull=False) # type: ignore[attr-defined]
        context['q'] = self.request.GET.get('q')
        context['selected_source'] = self.request.GET.get('source')
        return context

def build_cross_source_results_context(request, *, task_id: str = '', running: bool = False) -> dict[str, Any]:
    """
    - Builds the render state for the cross-source results partial: the account's non-dismissed cross-source insights plus the polling state.
    - `task_id` and `running` drive the poll loop — while `running` is True the template keeps polling `cross_source_discovery_status` until the task finishes.
    """
    insights = (
        Insight.objects
            .filter(account=request.account, insight_type='cross_source_use_case')
            .exclude(status='dismissed')
            .prefetch_related('insighttarget_set')
            .order_by('-created_at')
    )
    return {'insights': insights, 'task_id': task_id, 'running': running}

@login_required
@require_POST
def run_cross_source_discovery(request) -> HttpResponse:
    """
    - Kicks off async cross-source discovery for a user-selected pair of sources, then returns the results partial seeded with the task id so the UI begins polling.
    - Validates the pair before dispatching, each failure returning a 400 surfaced inline: the two sources must differ, both must belong to the account, and both must have been synced.
    - Rate-limited to once per 24h per pair (distinct from the per-source limit on intra-source generation): skips if a cross-source insight already exists for this exact source pair within the window.
    """
    source_a_id = request.POST.get('source_a')
    source_b_id = request.POST.get('source_b')
    if source_a_id == source_b_id:
        logger.warning("Cross-source discovery rejected: source %s paired with itself", source_a_id)
        return HttpResponse("Cannot pair a source with itself", status=400)
    source_a = get_object_or_404(Source, pk=source_a_id, account=request.account)
    source_b = get_object_or_404(Source, pk=source_b_id, account=request.account)
    if source_a.first_synced_at is None or source_b.first_synced_at is None:
        logger.warning("Cross-source discovery rejected: sources %s and %s must be synced", source_a_id, source_b_id)
        return HttpResponse("Sources must be synced before running discovery", status=400)
    source_ct = ContentType.objects.get_for_model(Source)
    cutoff = timezone.now() - timedelta(hours=24)
    recent_pair_run = (
        Insight.objects.filter(
            account=request.account,
            insight_type='cross_source_use_case',
            created_at__gte=cutoff,
            insighttarget__content_type=source_ct,
            insighttarget__object_id=source_a_id,
        )
        .filter(insighttarget__object_id=source_b_id)
        .exists()
    )
    if recent_pair_run:
        logger.info("Cross-source rate-limited for source %s and source %s", source_a_id, source_b_id)
        return HttpResponse("Cross-source discovery is rate-limited to once per 24h for this pair", status=400)
    result = run_cross_source_discovery_task.delay(request.account.id, source_a.id, source_b.id)
    return render(request, 'insights/_cross_source_discovery_results.html', build_cross_source_results_context(request, task_id=result.id, running=True))

@login_required
def cross_source_discovery_status(request) -> HttpResponse:
    """
    - HTMX poll target for a running discovery task; checks the Celery `AsyncResult` and re-renders the results partial, which stops polling once the task is no longer running.
    """
    task_id = request.GET.get('task_id', '')
    running = bool(task_id) and not run_cross_source_discovery_task.AsyncResult(task_id).ready()
    return render(request, 'insights/_cross_source_discovery_results.html', build_cross_source_results_context(request, task_id=task_id, running=running))

@login_required
@require_POST
def accept_agent_insight(request, insight_id: int) -> HttpResponse:
    """
    - Review-queue action: promotes a cross-source insight from 'pending_review' to 'active' and re-renders its card.
    - Only a 'pending_review' insight can be accepted (otherwise a 400).
    """
    insight = get_object_or_404(Insight, pk=insight_id, account=request.account, insight_type='cross_source_use_case',)
    if insight.status != 'pending_review':
        logger.warning("Accept rejected: insight %s is not pending review (status %s)", insight.pk, insight.status)
        return HttpResponse("Only pending insights can be accepted", status=400)
    insight.status = 'active'
    insight.save()
    return render(request, 'insights/_agent_insight_card.html', {'insight': insight})

@login_required
@require_POST
def dismiss_agent_insight(request, insight_id: int) -> HttpResponse:
    """
    - Review-queue action: marks a cross-source insight 'dismissed' (which drops it from the list) and returns an empty response so HTMX removes the card.
    - Only a 'pending_review' insight can be dismissed (otherwise a 400).
    """
    insight = get_object_or_404(Insight, pk=insight_id, account=request.account, insight_type='cross_source_use_case',)
    if insight.status != 'pending_review':
        logger.warning("Dismiss rejected: insight %s is not pending review (status %s)", insight.pk, insight.status)
        return HttpResponse("Only pending insights can be dismissed", status=400)
    insight.status = 'dismissed'
    insight.save()
    return HttpResponse('')