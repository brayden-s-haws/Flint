from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('settings/', views.AccountSettingsView.as_view(), name='settings'),
]