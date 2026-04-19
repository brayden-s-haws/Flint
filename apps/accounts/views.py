from __future__ import annotations

from django.http import HttpResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.urls import reverse_lazy
from django.views.generic import UpdateView

from .forms import AccountSettingsForm
from .models import Account


class AccountSettingsView(LoginRequiredMixin, UpdateView):
    model = Account
    form_class = AccountSettingsForm
    template_name = 'accounts/account_settings.html'
    success_url = reverse_lazy('accounts:settings')

    def get_object(self, queryset=None) -> Account:
        if not self.request.user.is_authenticated or not self.request.account.owner == self.request.user:
            raise PermissionDenied
        return self.request.account

    def form_valid(self, form) -> HttpResponse:
        messages.success(self.request, "Account settings updated successfully.")
        return super().form_valid(form)