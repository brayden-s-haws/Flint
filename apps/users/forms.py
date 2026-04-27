from __future__ import annotations

from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.forms import EmailField

from apps.accounts.constants import EXCLUDED_DOMAINS
from apps.accounts.models import Account

User = get_user_model()

class RegistrationForm(UserCreationForm):

    class Meta:
        model = User
        fields = ('email',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'w-full bg-flint-card border border-flint-border-em rounded-md px-3 py-2 text-sm text-flint-text focus:outline-none focus:ring-2 focus:ring-flint-orange'})

    def clean_email(self):
        email = self.cleaned_data['email'].lower()
        domain = email.split('@')[-1]
        if domain in EXCLUDED_DOMAINS:
            return email

        target_account = Account.objects.filter(owner__email__iendswith='@' + domain)
        if target_account.exists():
            raise ValidationError(f'An account already exists for this domain. Contact your administrator to request access.')
        return email

class LoginForm(AuthenticationForm):
    username = EmailField(label='Email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'w-full bg-flint-card border border-flint-border-em rounded-md px-3 py-2 text-sm text-flint-text focus:outline-none focus:ring-2 focus:ring-flint-orange'})
