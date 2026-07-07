from __future__ import annotations

from typing import Any

from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.generic import TemplateView

from apps.sources.models import Source
from apps.catalog.models import Table
from apps.insights.models import Insight, InsightTarget


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = 'core/dashboard.html'
    login_url = reverse_lazy('users:login')

    def get_context_data(self, **kwargs: Any) -> dict[str, Any]:
        context = super().get_context_data(**kwargs)
        account = getattr(self.request, 'account', None)
        context['account'] = account
        context['source_count'] = Source.objects.filter(account=account).count()
        context['table_count'] = Table.objects.filter(account=account).count()
        context['insight_count'] = Insight.objects.filter(account=account, status='active').count()
        context['cross_source_insight_count'] = Insight.objects.filter(
            account=account, insight_type='cross_source_use_case'
        ).exclude(status='dismissed').count()
        context['recent_sources'] = Source.objects.filter(account=account).order_by('-created_at')[:5]
        context['recent_tables'] = Table.objects.filter(account=account).order_by('-created_at')[:5]
        insights = Insight.objects.filter(account=account, status='active').order_by('-created_at')[:5]
        recent_insights = []
        for insight in insights:
            target = InsightTarget.objects.filter(insight=insight).first()
            target_name = target.target.name if target and target.target else 'Insight'
            recent_insights.append({'insight': insight, 'target_name': target_name})
        context['recent_insights'] = recent_insights

        return context