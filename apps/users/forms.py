""" Registration and login forms for email-based auth. Registration enforces the domain-based sign-up guard so a second person from a company's domain can't spin up a duplicate account. """
from __future__ import annotations

import logging

from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.forms import EmailField

from apps.accounts.constants import EXCLUDED_DOMAINS
from apps.accounts.models import Account


logger = logging.getLogger(__name__)

User = get_user_model()


class RegistrationForm(UserCreationForm):
    """
    - Email-only sign-up (password fields come from UserCreationForm).
    """

    class Meta:
        model = User
        fields = ('email',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'w-full bg-flint-card border border-flint-border-em rounded-md px-3 py-2 text-sm text-flint-text focus:outline-none focus:ring-2 focus:ring-flint-orange'})

    def clean_email(self):
        """
        - Domain-based registration guard: blocks sign-up when an account already exists for the email's domain, so new employees join via invite instead of creating a duplicate account.
        - Free/personal domains (EXCLUDED_DOMAINS) are exempt and always allowed through.
        - "An account exists for this domain" is detected by matching an existing account owner's email domain; the error deliberately does not reveal who the owner is.
        """
        email = self.cleaned_data['email'].lower()
        domain = email.split('@')[-1]
        if domain in EXCLUDED_DOMAINS:
            return email

        target_account = Account.objects.filter(owner__email__iendswith='@' + domain)
        if target_account.exists():
            logger.warning('Registration blocked: account already exists for domain %s', domain)
            raise ValidationError('An account already exists for this domain. Contact your administrator to request access.')
        return email

class LoginForm(AuthenticationForm):
    """
    - Email/password login: overrides the inherited username field to an EmailField labelled "Email".
    """
    username = EmailField(label='Email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'w-full bg-flint-card border border-flint-border-em rounded-md px-3 py-2 text-sm text-flint-text focus:outline-none focus:ring-2 focus:ring-flint-orange'})
