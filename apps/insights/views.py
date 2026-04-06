from __future__ import annotations

from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.db.models import QuerySet, Q
from django.urls import reverse
from django.views.generic import ListView, DetailView

from apps.catalog.models import Table
from apps.core.mixins import TenantQuerysetMixin
from apps.insights.models import Insight
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
