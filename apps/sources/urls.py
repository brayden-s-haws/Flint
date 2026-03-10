from django.urls import path
from . import views

app_name = 'sources'

urlpatterns = [
    path('', views.SourceListView.as_view(), name='list'),
    path('add/', views.SourceCreateView.as_view(), name='add'),
    path('<int:pk>/', views.SourceDetailView.as_view(), name='detail'),
]
