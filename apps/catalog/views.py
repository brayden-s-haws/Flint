from __future__ import annotations

from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import QuerySet
from django.views.generic import ListView, DetailView

from apps.core.mixins import TenantQuerysetMixin
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
        context['insights'] = Table.objects.none()
        return context