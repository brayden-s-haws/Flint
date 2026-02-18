from __future__ import annotations

from django.http import HttpResponse
from django.views.generic import CreateView
from django.contrib.auth import get_user_model, login

from apps.users.forms import RegistrationForm


class RegisterUser(CreateView):
    model = get_user_model()
    form_class = RegistrationForm
    template_name = 'users/register.html'
    success_url = '/'

    def form_valid(self, form) -> HttpResponse:
        response = super().form_valid(form)
        login(self.request, self.object)

        return response
