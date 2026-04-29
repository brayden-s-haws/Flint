from __future__ import annotations

from django.http import HttpResponse
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import UpdateView, CreateView

from .forms import AccountSettingsForm, AccountInviteForm
from .models import Account, AccountInvitation


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

class SendInviteView(LoginRequiredMixin, CreateView):
    model = AccountInvitation
    form_class = AccountInviteForm
    template_name = 'accounts/account_settings.html'
    success_url = reverse_lazy('accounts:settings')

    def dispatch(self, request, *args, **kwargs):
        if request.user != request.account.owner:
            raise PermissionDenied
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['account'] = self.request.account
        return kwargs

    def form_valid(self, form):
        invitation = form.save(commit=False)
        invitation.account = self.request.account
        invitation.invited_by = self.request.user
        invitation.save()
        messages.success(self.request, "Invite sent successfully.")
        return redirect(self.success_url)