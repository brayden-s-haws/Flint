""" Provides users with an owner role the ability to manage their account and invite others to join. Ensures that invited users are associated to the correct account. """
from __future__ import annotations

from datetime import timedelta
import logging

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


logger = logging.getLogger(__name__)


class AccountSettingsView(LoginRequiredMixin, UpdateView):
    model = Account
    form_class = AccountSettingsForm
    template_name = 'accounts/account_settings.html'
    success_url = reverse_lazy('accounts:settings')

    def get_object(self, queryset=None) -> Account:
        """
        Returns the account object associated with the request user (not a URL-pk lookup); scoped to owner users only.
        """
        if not self.request.user.is_authenticated or not self.request.account.owner == self.request.user:
            logger.warning("%s attempted to access account settings for account %s", self.request.user.id, self.request.account.id)
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
        """
        Owner-only guard for being able to send invites.
        """
        if request.user != request.account.owner:
            logger.warning("%s attempted to send invite for account %s", self.request.user.id, self.request.account.id)
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
        logger.info("Invite %s sent by %s for account %s", invitation.id, invitation.invited_by.id, invitation.account.id)
        return redirect(self.success_url)

def accept_invite_view(request: HttpRequest, token: str) -> HttpResponse:
    """
    - Validates the invite token and checks if the token has not expired, based on comparison of creation time to the 7-day limit.
    - Users accepting an invitation will always be associated with the account that the invite was sent for, so we skip account creation (handled in signals.py).
    - User inputs their password while accepting the invitation, so we check that the inputs match. User is logged into the backend since the user was just created, so it has not been logged in yet.
    """
    invitation = get_object_or_404(AccountInvitation, token=token, accepted=False)
    if timedelta(days=7) < timezone.now() - invitation.created_at:
        logger.warning("Invitation %s expired for account %s", invitation.id, invitation.account.id)
        return HttpResponse("Invitation has expired", status=400)
    if request.method == 'POST':
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        if password1 != password2:
            logger.warning("Passwords do not match for invitation %s", invitation.id)
            return HttpResponse("Passwords do not match", status=400)

        user = User(email=invitation.email)
        user.set_password(password1)
        user._skip_account_creation = True
        user.save()
        AccountMembership.objects.create(account=invitation.account, user=user, role=invitation.role)
        invitation.accepted = True
        invitation.save()
        login(request, user, backend='django.contrib.auth.backends.ModelBackend')
        logger.info("%s accepted invite for account %s", user.id, invitation.account.id)
        return redirect('core:dashboard')

    else:
        return render(request, 'accounts/accept_invite.html', {'invitation_email': invitation.email})
