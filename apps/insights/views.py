from __future__ import annotations

from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.db.models import QuerySet
from django.views.generic import ListView, DetailView, View
from django.shortcuts import redirect, get_object_or_404
from django.http import HttpRequest, HttpResponse

from apps.core.mixins import TenantQuerysetMixin
from apps.insights.models import Insight, InsightPrompt, InsightTarget
from apps.catalog.models import Table
from apps.insights.services.provider import get_service

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
        target = self.object.insighttarget_set.select_related('target').first()
        context['table'] = target.target if target else None
        return context


class GenerateInsightView(LoginRequiredMixin, View):
    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        table = get_object_or_404(Table, pk=pk, account=request.account) # type: ignore[attr-defined]
        insight_prompt = InsightPrompt.objects.filter(account=request.account).first() # type: ignore[attr-defined]
        if not insight_prompt:
            messages.error(request, "No prompt configured.")
            return redirect('catalog:detail', pk=pk)
        service = get_service(insight_prompt)
        try:
            text = service.generate_table_description(table)
        except Exception as e:
            messages.error(request, f"Failed to generate insight: {e}")
            return redirect('catalog:detail', pk=pk)
        insight = Insight.objects.create(account=request.account, text=text, insight_type='ai', status='active', insight_prompt=insight_prompt) # type: ignore[attr-defined]
        InsightTarget.objects.create(account=request.account, insight=insight, target=table) # type: ignore[attr-defined]
        return redirect('catalog:detail', pk=pk)