""" Tests for apps.accounts: the owner-only account settings + invite views and the token-based
accept-invite flow. Account auto-provisioning on registration is covered under apps.users; this
module covers the invitation lifecycle and owner-only guards. Uses the two-tenant TenantTestCase. """
from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import Account, AccountInvitation, AccountMembership
from apps.core.test_utils import TenantTestCase

User = get_user_model()


def create_member_user(email: str, account: Account, role: str = 'member') -> User:
    """
    Create a user attached ONLY to `account`. Skipping the registration signal's own-account
    (via _skip_account_creation) means the user has a single membership, so TenantMiddleware
    resolves their request.account to `account` rather than to a personal account.
    """
    user = User(email=email)
    user.set_password('pw')
    user._skip_account_creation = True
    user.save()
    AccountMembership.objects.create(account=account, user=user, role=role)
    return user


class AccountSettingsViewTest(TenantTestCase):
    """
    - AccountSettingsView is owner-only: the owner gets 200 with member/invite context.
    - A non-owner member of the same account is denied (403).
    """
    def test_owner_get_returns_200_with_context(self) -> None:
        self.client.force_login(self.owner_a)
        response = self.client.get(reverse('accounts:settings'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('members', response.context)
        self.assertIn('pending_invites', response.context)
        self.assertIn('invite_form', response.context)

    def test_non_owner_member_is_denied(self) -> None:
        member = create_member_user('member@stunkbeagle.com', self.account_a)
        self.client.force_login(member)
        response = self.client.get(reverse('accounts:settings'))
        self.assertEqual(response.status_code, 403)  # PermissionDenied — not the account owner


class SendInviteViewTest(TenantTestCase):
    """
    - The owner can send an invite: an AccountInvitation is created (scoped to their account,
      invited_by set) and the invite email is sent.
    - A non-owner member is denied (403).
    """
    def test_owner_can_send_invite(self) -> None:
        self.client.force_login(self.owner_a)
        response = self.client.post(reverse('accounts:send_invite'), {
            'email': 'invitee@sonambulance.com',
            'role': 'member',
        })
        self.assertRedirects(response, reverse('accounts:settings'))
        invitation = AccountInvitation.objects.get(email='invitee@sonambulance.com')
        self.assertEqual(invitation.account, self.account_a)   # Scoped to the inviter's account only
        self.assertEqual(invitation.invited_by, self.owner_a)
        self.assertEqual(len(mail.outbox), 1)                  # Invite email sent
        self.assertIn('invitee@sonambulance.com', mail.outbox[0].to)

    def test_non_owner_member_cannot_send_invite(self) -> None:
        member = create_member_user('member@stunkbeagle.com', self.account_a)
        self.client.force_login(member)
        response = self.client.post(reverse('accounts:send_invite'), {
            'email': 'invitee@sonambulance.com',
            'role': 'member',
        })
        self.assertEqual(response.status_code, 403)
        self.assertFalse(AccountInvitation.objects.filter(email='invitee@sonambulance.com').exists())

    def test_inviting_existing_member_rejected(self) -> None:
        # AccountInviteForm.clean_email rejects an email already belonging to a member of the account.
        self.client.force_login(self.owner_a)
        response = self.client.post(reverse('accounts:send_invite'), {
            'email': self.owner_a.email,  # owner_a is already a member of account_a
            'role': 'member',
        })
        self.assertEqual(response.status_code, 200)  # form re-renders with errors, no invite created
        self.assertFalse(AccountInvitation.objects.filter(email=self.owner_a.email).exists())

    def test_inviting_duplicate_pending_email_rejected(self) -> None:
        # AccountInviteForm.clean_email rejects a second invite to an email with a pending invitation.
        self.client.force_login(self.owner_a)
        AccountInvitation.objects.create(
            account=self.account_a, email='pending@sonambulance.com', invited_by=self.owner_a)
        response = self.client.post(reverse('accounts:send_invite'), {
            'email': 'pending@sonambulance.com',
            'role': 'member',
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(AccountInvitation.objects.filter(email='pending@sonambulance.com').count(), 1)  # no duplicate


class AcceptInviteViewTest(TenantTestCase):
    """
    - GET renders the accept form with the invitee email; POST creates the user + membership on
      the INVITING account (no personal account), logs them in, and marks the invite accepted.
    - Expired / mismatched-password POSTs return 400; unknown or already-accepted tokens return 404.
    - Domain-guard interplay: an invited same-domain user joins via this flow (the registration
      guard never runs here).
    """
    def setUp(self) -> None:
        self.invitation = AccountInvitation.objects.create(
            account=self.account_a,
            email='invitee@sonambulance.com',
            role='member',
            invited_by=self.owner_a,
        )

    def _accept_url(self, token: str) -> str:
        return reverse('accounts:accept_invite', args=[token])

    def test_get_renders_accept_form(self) -> None:
        response = self.client.get(self._accept_url(self.invitation.token))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['invitation_email'], 'invitee@sonambulance.com')

    def test_post_creates_user_and_membership_and_logs_in(self) -> None:
        response = self.client.post(self._accept_url(self.invitation.token), {
            'password1': 'pw', 'password2': 'pw',   # set_password directly; validators don't run here
        })
        self.assertRedirects(response, reverse('core:dashboard'))
        user = User.objects.get(email='invitee@sonambulance.com')
        # Joins the inviting account with the invited role...
        self.assertTrue(AccountMembership.objects.filter(
            account=self.account_a, user=user, role='member').exists())
        # ...and NO personal account was created (the signal was skipped).
        self.assertFalse(Account.objects.filter(owner=user).exists())
        self.assertEqual(str(self.client.session['_auth_user_id']), str(user.pk))  # Logged in
        self.invitation.refresh_from_db()
        self.assertTrue(self.invitation.accepted)

    def test_expired_invite_returns_400(self) -> None:
        # created_at is auto_now_add, so backdate it via .update() to bypass the setter.
        AccountInvitation.objects.filter(pk=self.invitation.pk).update(
            created_at=timezone.now() - timedelta(days=8))
        response = self.client.post(self._accept_url(self.invitation.token), {
            'password1': 'pw', 'password2': 'pw',
        })
        self.assertEqual(response.status_code, 400)

    def test_password_mismatch_returns_400(self) -> None:
        response = self.client.post(self._accept_url(self.invitation.token), {
            'password1': 'pw', 'password2': 'different',
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(User.objects.filter(email='invitee@sonambulance.com').exists())

    def test_unknown_token_returns_404(self) -> None:
        response = self.client.get(self._accept_url('not-a-real-token'))
        self.assertEqual(response.status_code, 404)

    def test_already_accepted_token_returns_404(self) -> None:
        self.invitation.accepted = True
        self.invitation.save()
        # get_object_or_404 filters accepted=False, so an accepted invite is unreachable.
        response = self.client.get(self._accept_url(self.invitation.token))
        self.assertEqual(response.status_code, 404)

    def test_invited_same_domain_user_joins(self) -> None:
        # newhire@stunkbeagle.com would be BLOCKED at registration (owner_a shares the domain),
        # but the accept flow bypasses the registration guard entirely.
        invitation = AccountInvitation.objects.create(
            account=self.account_a,
            email='newhire@stunkbeagle.com',
            role='member',
            invited_by=self.owner_a,
        )
        response = self.client.post(self._accept_url(invitation.token), {
            'password1': 'pw', 'password2': 'pw',
        })
        self.assertRedirects(response, reverse('core:dashboard'))
        user = User.objects.get(email='newhire@stunkbeagle.com')
        self.assertTrue(AccountMembership.objects.filter(account=self.account_a, user=user).exists())