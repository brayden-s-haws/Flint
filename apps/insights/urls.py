from __future__ import annotations

from django.urls import path
from . import views

app_name = 'insights'

urlpatterns = [
    path('', views.InsightListView.as_view(), name='list'),
    path('<int:pk>/', views.InsightDetailView.as_view(), name='detail'),
    path('use-cases/generate/<int:source_id>/', views.generate_intra_use_case_suggestions, name='generate_use_cases'),
    path('use-cases/status/<int:source_id>/', views.use_cases_status, name='use_cases_status'),
    path('discovery/', views.CrossSourceDiscoveryView.as_view(), name='discovery'),
    path('discovery/run/', views.run_cross_source_discovery, name='run_cross_source_discovery'),
    path('discovery/status/', views.cross_source_discovery_status, name='cross_source_discovery_status'),
    path('<int:insight_id>/rate/', views.rate_insight, name='rate_insight'),
    path('<int:insight_id>/status/', views.insight_status, name='insight_status'),
    path('<int:insight_id>/retry/', views.insight_retry, name='insight_retry'),
    path('<int:insight_id>/accept/', views.accept_agent_insight, name='accept_agent_insight'),
    path('<int:insight_id>/dismiss/', views.dismiss_agent_insight, name='dismiss_agent_insight'),
]