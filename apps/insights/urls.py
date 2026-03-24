from __future__ import annotations

from django.urls import path
from . import views

app_name = 'insights'

urlpatterns = [
    path('', views.InsightListView.as_view(), name='list'),
    path('<int:pk>/', views.InsightDetailView.as_view(), name='detail'),
    path('generate/<int:pk>/', views.GenerateInsightView.as_view(), name='generate')
]