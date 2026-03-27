from __future__ import annotations

from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.db.models import QuerySet
from django.views.generic import ListView, DetailView

from apps.core.mixins import TenantQuerysetMixin
from apps.insights.models import InsightTarget, Insight
from apps.insights.services.provider import get_service

from .models import Table

class TableListView(TenantQuerysetMixin, LoginRequiredMixin, ListView):
    model = Table
    template_name = 'catalog/table_list.html'
    context_object_name = 'tables'

    def get_queryset(self) -> QuerySet[Table]:
        return super().get_queryset().select_related('schema', 'schema__source')


class TableDetailView(TenantQuerysetMixin, LoginRequiredMixin, DetailView):
    model = Table
    template_name = 'catalog/table_detail.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['columns'] = self.object.column_set.all().order_by('name')
        insight_targets = InsightTarget.objects.filter(account=self.request.account, content_type=ContentType.objects.get_for_model(self.object), object_id=self.object.pk) # type: ignore[attr-defined]
        context['insights'] = [it.insight for it in insight_targets]
        if not context['insights']:
            try:
                service = get_service('anthropic')
                text = service.generate_table_description(self.object)
                insight = Insight.objects.create(account=self.request.account, text=text, insight_type='ai', status='active', insight_prompt=None) # type: ignore[attr-defined]
                InsightTarget.objects.create(account=self.request.account, insight=insight, content_type=ContentType.objects.get_for_model(self.object), object_id=self.object.pk) # type: ignore[ attr-defined]
                context['insights'] = [insight]
            except Exception as e:
                print(f"Error generating insights: {e}")
        return context