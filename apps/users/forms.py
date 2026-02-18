from __future__ import annotations

from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model

User = get_user_model()

class RegistrationForm(UserCreationForm):

    class Meta:
        model = User
        fields = ('email',)
