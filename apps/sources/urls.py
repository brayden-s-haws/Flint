from django.urls import path
from . import views

app_name = 'sources'

urlpatterns = [
    path('', views.SourceListView.as_view(), name='list'),
    path('add/', views.SourceCreateView.as_view(), name='add'),
    path('<int:pk>/', views.SourceDetailView.as_view(), name='detail'),
    path('<int:pk>/test/', views.test_connection, name='test_connection'),
    path('<int:pk>/sync/', views.sync_source, name='sync'),
    path('<int:pk>/sync-status/', views.sync_status, name='sync_status'),
    path('<int:pk>/edit/', views.SourceUpdateView.as_view(), name='edit'),
    path('<int:pk>/delete/', views.SourceDeleteView.as_view(), name='delete'),
    path('<int:pk>/schedule/', views.schedule_create, name='schedule_create'),
    path('<int:pk>/schedule/toggle/', views.schedule_toggle, name='schedule_toggle'),
    path('<int:pk>/schedule/delete/', views.schedule_delete, name='schedule_delete'),
    path('connect-fields/', views.connect_fields, name='connect_fields'),
    path('demo/load/', views.load_demo_data, name='load_demo'),
]
