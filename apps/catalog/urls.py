from django.urls import path
from . import views

app_name = 'catalog'

urlpatterns = [
    path('', views.TableListView.as_view(), name='list'),
    path('<int:pk>/', views.TableDetailView.as_view(), name='detail'),
]