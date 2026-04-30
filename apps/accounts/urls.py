from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('settings/', views.AccountSettingsView.as_view(), name='settings'),
    path('invites/send/', views.SendInviteView.as_view(), name='send_invite'),
    path('invites/accept/<str:token>/', views.accept_invite_view, name='accept_invite'),
]