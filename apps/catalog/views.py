""" Provides users with the ability to view the tables in the catalog. Also triggers LLM-powered table descriptions when a user views a table. """
from __future__ import annotations

from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.contenttypes.models import ContentType
from django.db.models import QuerySet
from django.views.generic import ListView, DetailView

from apps.core.mixins import TenantQuerysetMixin
from apps.insights.models import InsightTarget, Insight
from apps.insights.tasks import generate_table_description_task
from apps.sources.models import Source

from .models import Table, TableStatistics


class TableListView(TenantQuerysetMixin, LoginRequiredMixin, ListView):
    """
    Displays a list of tables in the catalog. Users are able to filter by source and search by table name.
    """
    model = Table
    template_name = 'catalog/table_list.html'
    context_object_name = 'tables'

    def get_queryset(self) -> QuerySet[Table]:
        q = self.request.GET.get('q')
        source_pk = self.request.GET.get('source')
        qs = super().get_queryset().select_related('schema', 'schema__source')
        if q:
            qs = qs.filter(name__icontains=q)
        if source_pk:
            qs = qs.filter(schema__source_id=source_pk, schema__source__account=self.request.account) # type: ignore[attr-defined]
        return qs

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        context['q'] = self.request.GET.get('q')
        context['sources'] = Source.objects.filter(account=self.request.account) # type: ignore[attr-defined]
        context['selected_source'] = self.request.GET.get('source')
        return context


class TableDetailView(TenantQuerysetMixin, LoginRequiredMixin, DetailView):
    """
    Displays a table in the catalog. Users are able to view the table's columns and statistics.
    """
    model = Table
    template_name = 'catalog/table_detail.html'

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        """
        The first time a user views a table, a pending Insight and InsightTarget are created. An async task is triggered to generate a table description. Later views of this table display the
        stored table description.
        """
        context = super().get_context_data(**kwargs)
        context['columns'] = self.object.column_set.all().order_by('name')
        insight_targets = InsightTarget.objects.filter(account=self.request.account, content_type=ContentType.objects.get_for_model(self.object), object_id=self.object.pk) # type: ignore[attr-defined]
        context['insights'] = [it.insight for it in insight_targets]
        if not context['insights']:
            insight = Insight.objects.create(account=self.request.account, text='', insight_type='table_description', status='pending', insight_prompt=None) # type: ignore[attr-defined]
            InsightTarget.objects.create(account=self.request.account, insight=insight, content_type=ContentType.objects.get_for_model(self.object), object_id=self.object.pk)  # type: ignore[attr-defined]
            generate_table_description_task.delay(insight.pk)
            context['insights'] = [insight]
        context['statistics'] = TableStatistics.objects.filter(table=self.object).order_by('-created_at').first()
        return context