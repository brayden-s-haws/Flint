from __future__ import annotations

from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from django.forms import EmailField

User = get_user_model()

class RegistrationForm(UserCreationForm):

    class Meta:
        model = User
        fields = ('email',)

class LoginForm(AuthenticationForm):
    username = EmailField(label='Email')
