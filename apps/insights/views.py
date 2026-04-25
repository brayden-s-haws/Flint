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
from apps.sources.models import Source

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
        return qs

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

@login_required
@require_POST
def generate_intra_use_case_suggestions(request, source_id: int) -> HttpResponse:
    source = get_object_or_404(Source, pk=source_id, account=request.account)
    source_ct = ContentType.objects.get_for_model(Source)

    has_overview = InsightTarget.objects.filter(
        content_type=source_ct, object_id=source.pk, account=source.account,
        insight__insight_type='ai'
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

    overview_target = InsightTarget.objects.filter(
        content_type=source_ct, object_id=source.pk,
        account=source.account, insight__insight_type='ai'
    ).select_related('insight').first()
    source_overview = overview_target.insight.text if overview_target else None

    use_case_targets = InsightTarget.objects.filter(
        content_type=source_ct, object_id=source.pk,
        account=source.account, insight__insight_type='use_case_suggestion'
    ).select_related('insight').order_by('-insight__created_at')
    use_cases = [uct.insight for uct in use_case_targets]


    context = {
        'source': source,
        'source_overview': source_overview,
        'use_cases': use_cases,
        'use_case_rate_limited': True,
        'use_case_hours_remaining': 24,
    }

    return render(request, 'sources/_use_cases_section.html', context)

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
