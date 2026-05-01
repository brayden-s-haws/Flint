from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import login, get_user_model
from django.http import HttpResponse, HttpRequest
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.core.mail import send_mail
from django.shortcuts import redirect, get_object_or_404, render
from django.template.loader import render_to_string
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.views.generic import UpdateView, CreateView

from .forms import AccountSettingsForm, AccountInviteForm
from .models import Account, AccountInvitation, AccountMembership

User = get_user_model()

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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['members'] = AccountMembership.objects.filter(account=self.request.account)
        context['pending_invites'] = AccountInvitation.objects.filter(account=self.request.account, accepted=False)
        context['invite_form'] = AccountInviteForm(account=self.request.account)
        return context

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
        invite_url = self.request.build_absolute_uri(reverse('accounts:accept_invite', args=[invitation.token]))
        email_context = {
            'inviter_email': invitation.invited_by.email,
            'account_name': invitation.account.name,
            'invite_url': invite_url
        }
        send_mail(
            subject=f"You've been invited to join {invitation.account.name} on Flint 🔥",
            message=f"Click the link to accept the invitation: {invite_url}",
            from_email=None,
            recipient_list=[invitation.email],
            html_message=render_to_string('accounts/invite_email.html', email_context, request=self.request)
        )
        messages.success(self.request, "Invite sent successfully.")
        return redirect(self.success_url)

def accept_invite_view(request: HttpRequest, token: str) -> HttpResponse:
    invitation = get_object_or_404(AccountInvitation, token=token, accepted=False)
    if timedelta(days=7) < timezone.now() - invitation.created_at:
        return HttpResponse("Invitation has expired", status=400)
    if request.method == 'POST':
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        if password1 != password2:
            return HttpResponse("Passwords do not match", status=400)

        user = User(email=invitation.email)
        user.set_password(password1)
        user._skip_account_creation = True
        user.save()
        AccountMembership.objects.create(account=invitation.account, user=user, role=invitation.role)
        invitation.accepted = True
        invitation.save()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        return redirect('core:dashboard')

    else:
        return render(request, 'accounts/accept_invite.html', {'invitation_email': invitation.email})
