from django.urls import path
from . import views

app_name = 'sources'

urlpatterns = [
    path('', views.SourceListView.as_view(), name='list'),
    path('add/', views.SourceCreateView.as_view(), name='add'),
    path('<int:pk>/', views.SourceDetailView.as_view(), name='detail'),
    path('<int:pk>/test/', views.test_connection, name='test_connection'),
    path('<int:pk>/sync/', views.sync_source, name='sync'),
    path('<int:pk>/edit/', views.SourceUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.SourceDeleteView.as_view(), name='delete'),
]
