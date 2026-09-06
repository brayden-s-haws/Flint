""" User registration view. Login and logout are handled by Django's built-in auth views (wired in urls.py), so only sign-up lives here. """
from __future__ import annotations

import logging

from django.http import HttpResponse
from django.views.generic import CreateView
from django.contrib.auth import get_user_model, login
from django.urls import reverse_lazy

from apps.users.forms import RegistrationForm


logger = logging.getLogger(__name__)


class RegisterUser(CreateView):
    """
    - Registers a new user via RegistrationForm and logs them straight in on success, redirecting to the dashboard.
    - Creating the user fires the accounts signal (create_account_for_new_user), which provisions the user's Account and owner membership — so a registered user always lands with an account ready.
    """
    model = get_user_model()
    form_class = RegistrationForm
    template_name = 'users/register.html'
    success_url = reverse_lazy('core:dashboard')

    def form_valid(self, form) -> HttpResponse:
        response = super().form_valid(form)
        login(self.request, self.object)
        account = self.object.account_set.first() # reverse of Account.owner FK
        logger.info("User %s registered successfully for account %s", self.object.id, account.id)

        return response
