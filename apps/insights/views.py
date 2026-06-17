from __future__ import annotations

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
from apps.insights.services.provider import get_service
from apps.insights.tasks import generate_table_description_task, run_cross_source_discovery_task
from apps.sources.models import Source

# ---------------------------------------------------------------------------
# Intra-Source Insights
# ---------------------------------------------------------------------------

class InsightListView(TenantQuerysetMixin, LoginRequiredMixin, ListView):
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
    source_ct = ContentType.objects.get_for_model(Source)
    overview_target = InsightTarget.objects.filter(
        content_type=source_ct, object_id=source.pk, account=source.account,
        insight__insight_type='source_overview'
    ).select_related('insight').first()
    overview_insight = overview_target.insight if overview_target else None
    source_overview = overview_insight.text if overview_insight and overview_insight.status == 'active' else None

    use_case_targets = InsightTarget.objects.filter(
        content_type=source_ct, object_id=source.pk, account=source.account,
        insight__insight_type='use_case_suggestion'
    ).select_related('insight').order_by('-insight__created_at')
    use_cases = [uct.insight for uct in use_case_targets]

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
    }


@login_required
def use_cases_status(request, source_id: int) -> HttpResponse:
    source = get_object_or_404(Source, pk=source_id, account=request.account)
    return render(request, 'sources/_use_cases_section.html', build_use_cases_context(source))


@login_required
@require_POST
def generate_intra_use_case_suggestions(request, source_id: int) -> HttpResponse:
    source = get_object_or_404(Source, pk=source_id, account=request.account)
    source_ct = ContentType.objects.get_for_model(Source)

    has_overview = InsightTarget.objects.filter(
        content_type=source_ct, object_id=source.pk, account=source.account,
        insight__insight_type='source_overview'
        ).exists()
    if not has_overview:
        return HttpResponse("Generate a Source Overview before generating use case suggestions.", status=400)

    recent_suggestion = InsightTarget.objects.filter(
        content_type=source_ct, object_id=source.pk, account=source.account,
        insight__insight_type='use_case_suggestion'
    ).select_related('insight').order_by('-insight__created_at').first()
    if recent_suggestion and recent_suggestion.insight.created_at > timezone.now() - timedelta(hours=24):
        return HttpResponse("Use case suggestions were generated recently. Try again in 24 hours.", status=400)

    existing_targets = InsightTarget.objects.filter(
        content_type=source_ct, object_id=source.pk, account=source.account,
        insight__insight_type='use_case_suggestion'
    )
    insight_ids = list(existing_targets.values_list('insight_id', flat=True))
    existing_targets.delete()
    Insight.objects.filter(pk__in=insight_ids).delete()

    try:
        use_cases = get_service('anthropic').generate_intra_source_use_case(source)
    except Exception as exc:
        return HttpResponse(f"Failed to generate use cases: {exc}", status=500)

    for use_case in use_cases:
        insight = Insight.objects.create(account=source.account, text=use_case['title'],
            insight_type='use_case_suggestion', status='active',
            insight_prompt=None, structured_data=use_case)
        InsightTarget.objects.create(account=source.account, insight=insight,
            content_type=source_ct, object_id=source.pk)

    return render(request, 'sources/_use_cases_section.html', build_use_cases_context(source))

@login_required
@require_POST
def rate_insight(request, insight_id: int) -> HttpResponse:
    insight = get_object_or_404(Insight, pk=insight_id, account=request.account)
    rating = request.POST.get('rating')

    if rating != 'approved' and rating != 'rejected':
        return HttpResponse("Invalid rating value", status=400)

    if insight.rating == rating:
        insight.rating = 'none'
    else:
        insight.rating = rating

    insight.save()
    return render(request, 'insights/_rating_buttons.html', {'insight': insight})

@login_required
def insight_status(request, insight_id: int) -> HttpResponse:
    insight = get_object_or_404(Insight, pk=insight_id, account=request.account)
    status = insight.status

    if status == 'active':
        return render(request, 'insights/_insight_content.html', {'insight': insight})
    elif status == 'pending':
        return render(request, 'insights/_insight_pending.html', {'insight': insight})
    elif status == 'failed':
        return render(request, 'insights/_insight_failed.html', {'insight': insight})
    else:
        return HttpResponse("Invalid insight status", status=400)

@login_required
@require_POST
def insight_retry(request, insight_id: int) -> HttpResponse:
    insight = get_object_or_404(Insight, pk=insight_id, account=request.account)
    if insight.status != 'failed':
        return HttpResponse("Cannot retry an insight that has not failed", status=400)
    insight.status = 'pending'
    insight.save()
    generate_table_description_task.delay(insight.id)
    return render(request, 'insights/_insight_pending.html', {'insight': insight})

# ---------------------------------------------------------------------------
# Cross-Source Insights
# ---------------------------------------------------------------------------

class CrossSourceDiscoveryView(TenantQuerysetMixin, LoginRequiredMixin, ListView):
    model = Insight
    template_name = 'insights/cross_source_discovery.html'
    context_object_name = 'insights'

    def get_queryset(self) -> QuerySet[Insight]:
        q = self.request.GET.get('q')
        source_pk = self.request.GET.get('source')
        qs = super().get_queryset().filter(insight_type='cross_source_use_case').prefetch_related('insighttarget_set').order_by('-created_at')
        if q:
            qs = qs.filter(text__icontains=q)
        if source_pk:
            source_ct = ContentType.objects.get_for_model(Source)
            qs = qs.filter(insighttarget__content_type=source_ct, insighttarget__object_id=source_pk).distinct()
        return qs # type: ignore[return-value]

    # TODO(stub): get_context_data(self, **kwargs) -> dict[str, Any]
    #   The template needs more than the insight list — it has a pair selector + a
    #   filter/search bar + a "Run discovery" button at the top. Mirror the shape of
    #   InsightListView.get_context_data above. Put into context:
    #     - 'sources': Source.objects.filter(account=self.request.account)  (synced ones only
    #        if you want — e.g. .filter(first_synced_at__isnull=False)); feeds BOTH the pair
    #        <select>s and the source filter <select>.
    #     - 'q' and 'selected_source': the current GET values, so the filter form stays
    #        populated after submit (same as the list view echoes them back).
    #     - rate-limit hint for the Run button (optional but nice): whether a run happened in
    #        the last 24h. Unlike intra-source (which keys off one source's most-recent
    #        insight), a cross-source run is per-PAIR — so a global "any cross_source_use_case
    #        in last 24h" check is the simple Phase 1 version. Decide and document the grain.


# TODO(stub): run_cross_source_discovery(request) -> HttpResponse   [POST /insights/discovery/run/]
#   The trigger. Closest analog is generate_intra_use_case_suggestions above — copy its
#   SHAPE (decorators, validation, rate-limit guard, enqueue, render partial) but NOTE the
#   key differences flagged below. Decorators: @login_required + @require_POST.
#   1. Read the two source ids from request.POST (e.g. 'source_a', 'source_b').
#   2. Validate BOTH belong to the account AND are distinct AND are synced:
#        get_object_or_404(Source, pk=source_a_id, account=request.account) x2
#        - reject if source_a_id == source_b_id (can't pair a source with itself) -> 400
#        - reject if either is not synced (Source has no last_synced_at; check first_synced_at
#          is None, OR the Max('sourcesynclog__completed_at') pattern — see featuredoc Notes) -> 400
#   3. Rate-limit (per the spec, once / 24h) — mirror the recent-suggestion check, but for
#      a PAIR. Phase 1 simple version: look for any cross_source_use_case insight linked to
#      BOTH of these sources created in the last 24h. (Document the grain you choose.)
#   4. DO NOT DELETE existing insights here. This is the big departure from the intra-source
#      view (lines 141-147 delete-then-create). Cross-source is NON-DESTRUCTIVE (featuredoc) —
#      the pipeline appends. No delete block.
#   5. Enqueue, don't run inline: run_cross_source_discovery_task.delay(request.account.id,
#      source_a.id, source_b.id). (The pipeline is slow + Sonnet-heavy; it must be async,
#      unlike the intra-source view which calls the service synchronously.)
#   6. Return the results-section partial so HTMX can show a spinner and start polling the
#      status endpoint:  render(request, 'insights/_cross_source_discovery_results.html', {...})
#
# TODO(stub): cross_source_discovery_status(request) -> HttpResponse   [GET /insights/discovery/status/]
#   HTMX poll endpoint (analog: use_cases_status above). @login_required.
#   Re-render 'insights/_cross_source_discovery_results.html' with the current newest-first
#   cross_source_use_case queryset for the account (reuse the same filtering you build in the
#   view's get_queryset — consider extracting a small helper so the page and the poll share
#   one query). The partial shows the spinner while a run is in flight and the list once
#   insights start landing. Mirror the async-on-first-view pattern in
#   devdocs/featuredocs/async-table-descriptions.md.
#
# TODO(stub): accept_agent_insight(request, insight_id: int) -> HttpResponse   [POST .../accept/]
#   @login_required + @require_POST. get_object_or_404(Insight, pk=insight_id,
#   account=request.account). Guard: only flip if status == 'pending_review' (else 400).
#   Set status='active', save, and render the single-card partial
#   'insights/_agent_insight_card.html' so HTMX swaps just that row (analog: rate_insight).
#
# TODO(stub): dismiss_agent_insight(request, insight_id: int) -> HttpResponse   [POST .../dismiss/]
#   Same shape as accept, but status -> 'dismissed'. Same pending_review guard + card re-render.
#   (Decide whether a dismissed card stays visible greyed-out or is removed from the list —
#   that choice drives whether the partial renders the card or an empty response for HTMX to
#   swap away. Note it in the template TODOs.)