from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from .forms import LoginForm

app_name = 'users'

urlpatterns = [
    path('register/', views.RegisterUser.as_view(), name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='users/login.html',authentication_form=LoginForm), name='login',),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]