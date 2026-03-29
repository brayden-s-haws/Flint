from __future__ import annotations

from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet
from django.views.generic import ListView, DetailView

from apps.core.mixins import TenantQuerysetMixin
from apps.insights.models import Insight

class InsightListView(TenantQuerysetMixin, LoginRequiredMixin, ListView):
    model = Insight
    template_name = 'insights/insight_list.html'
    context_object_name = 'insights'

    def get_queryset(self) -> QuerySet[Insight]:
        query_set = super().get_queryset().select_related('insight_prompt').order_by('-created_at')
        return query_set


class InsightDetailView(TenantQuerysetMixin, LoginRequiredMixin, DetailView):
    model = Insight
    template_name = 'insights/insight_detail.html'
    context_object_name = 'insight'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        target = self.object.insighttarget_set.first()
        # TODO(review): Context key is named 'table' but InsightTarget now uses GenericForeignKey and can point to a Source or other model. Rename to 'target_object' (and update insight_detail.html) to avoid confusion when source-overview insights are viewed here.
        context['table'] = target.target if target else None
        return context
