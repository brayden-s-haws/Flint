from __future__ import annotations

from django.urls import path
from . import views

app_name = 'insights'

urlpatterns = [
    path('', views.InsightListView.as_view(), name='list'),
    path('<int:pk>/', views.InsightDetailView.as_view(), name='detail'),
    path('use-cases/generate/<int:source_id>/', views.generate_intra_use_case_suggestions, name='generate_use_cases'),
    path('<int:insight_id>/rate/', views.rate_insight, name='rate_insight'),
]