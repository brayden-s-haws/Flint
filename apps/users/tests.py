""" Tests for apps.users: email-based registration (with the domain-based sign-up guard), login, logout, and the auth-signal receivers. All classes use the two-tenant TenantTestCase fixture. """
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.urls import reverse

from apps.accounts.models import Account, AccountMembership
from apps.core.test_utils import TenantTestCase
from apps.users.signals import log_login, log_logout, log_login_failed

User = get_user_model()

# A password strong enough to pass AUTH_PASSWORD_VALIDATORS (min length, not common, not numeric).
# The fixture's 'pw' bypasses validators via create_user; registration goes through the form, so it can't.
STRONG_PASSWORD = 'Str0ngPass!23'


class RegistrationTest(TenantTestCase):
    """
    - RegisterUser creates a user, fires the account-provisioning signal, logs them in, and redirects.
    - RegistrationForm surfaces form errors (mismatch/duplicate/missing) and enforces the domain guard.
    """
    def test_get_returns_200(self) -> None:
        self.assertEqual(self.client.get(reverse('users:register')).status_code, 200)

    def test_valid_registration_creates_user_and_logs_in(self) -> None:
        response = self.client.post(reverse('users:register'), {
            'email': 'founder@buntclunt.com',  # Domain not in the fixture, so the guard lets it through
            'password1': STRONG_PASSWORD,
            'password2': STRONG_PASSWORD,
        })
        self.assertRedirects(response, reverse('core:dashboard'))
        user = User.objects.get(email='founder@buntclunt.com')
        self.assertTrue(Account.objects.filter(owner=user).exists())  # Signal provisioned the account
        self.assertTrue(AccountMembership.objects.filter(user=user, role='owner').exists())
        self.assertEqual(str(self.client.session['_auth_user_id']), str(user.pk))  # Logged in

    def test_password_mismatch_returns_error(self) -> None:
        response = self.client.post(reverse('users:register'), {
            'email': 'mismatch@buntclunt.com',
            'password1': STRONG_PASSWORD,
            'password2': 'Different!45',
        })
        self.assertEqual(response.status_code, 200)  # Re-renders instead of redirecting
        self.assertIn('password2', response.context['form'].errors)
        self.assertFalse(User.objects.filter(email='mismatch@buntclunt.com').exists())

    def test_duplicate_email_returns_error(self) -> None:
        # gmail.com is in EXCLUDED_DOMAINS, so the domain guard waves it through and the
        # uniqueness check is what fails — otherwise the guard would mask the duplicate.
        User.objects.create_user(email='dupe@gmail.com', password='pw')
        response = self.client.post(reverse('users:register'), {
            'email': 'dupe@gmail.com',
            'password1': STRONG_PASSWORD,
            'password2': STRONG_PASSWORD,
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('email', response.context['form'].errors)

    def test_missing_fields_returns_error(self) -> None:
        response = self.client.post(reverse('users:register'), {})
        self.assertEqual(response.status_code, 200)
        self.assertIn('email', response.context['form'].errors)

    def test_domain_guard_blocks_matching_domain(self) -> None:
        # owner_a is a@stunkbeagle.com, so an account already exists for that domain.
        response = self.client.post(reverse('users:register'), {
            'email': 'newhire@stunkbeagle.com',
            'password1': STRONG_PASSWORD,
            'password2': STRONG_PASSWORD,
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn('email', response.context['form'].errors)
        self.assertFalse(User.objects.filter(email='newhire@stunkbeagle.com').exists())  # Blocked, not created

    def test_domain_guard_exempts_free_domain(self) -> None:
        response = self.client.post(reverse('users:register'), {
            'email': 'anyone@gmail.com',  # Free domain is always allowed
            'password1': STRONG_PASSWORD,
            'password2': STRONG_PASSWORD,
        })
        self.assertRedirects(response, reverse('core:dashboard'))


class LoginTest(TenantTestCase):
    """
    - LoginView authenticates a known user and sets the session, honouring ?next.
    - Bad password and unknown email re-render with a non-field error.
    """
    def test_get_returns_200(self) -> None:
        self.assertEqual(self.client.get(reverse('users:login')).status_code, 200)

    def test_valid_login_redirects_and_sets_session(self) -> None:
        response = self.client.post(reverse('users:login'), {
            'username': 'a@stunkbeagle.com',  # AuthenticationForm keeps the field name 'username'
            'password': 'pw',                 # Set by the fixture's create_user
        })
        self.assertRedirects(response, reverse('core:dashboard'))
        self.assertIn('_auth_user_id', self.client.session)

    def test_bad_password_returns_error(self) -> None:
        response = self.client.post(reverse('users:login'), {
            'username': 'a@stunkbeagle.com',
            'password': 'wrong-password',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].non_field_errors())  # Generic "correct email and password" error

    def test_unknown_email_returns_error(self) -> None:
        response = self.client.post(reverse('users:login'), {
            'username': 'nobody@galgodonut.com',
            'password': 'pw',
        })
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['form'].non_field_errors())

    def test_next_param_redirects_after_login(self) -> None:
        next_url = '/sources/'  # Any safe relative path; LoginView honours it over LOGIN_REDIRECT_URL
        response = self.client.post(f"{reverse('users:login')}?next={next_url}", {
            'username': 'a@stunkbeagle.com',
            'password': 'pw',
        })
        # fetch_redirect_response=False: we only care that 'next' is honoured, not that the target renders
        self.assertRedirects(response, next_url, fetch_redirect_response=False)


class LogoutTest(TenantTestCase):
    """
    LogoutView clears the session and redirects to the login page (LOGOUT_REDIRECT_URL).
    """
    def test_logout_clears_session_and_redirects(self) -> None:
        self.client.force_login(self.owner_a)
        self.assertIn('_auth_user_id', self.client.session)  # Logged in first
        response = self.client.post(reverse('users:logout'))  # Django 6 requires POST to log out
        self.assertRedirects(response, reverse('users:login'))
        self.assertNotIn('_auth_user_id', self.client.session)  # Session cleared


class AuthSignalsTest(TenantTestCase):
    """
    - The three auth-signal receivers are connected and fire without raising.
    - log_logout tolerates user=None; log_login_failed logs only and never touches the credentials dict.
    """
    def test_login_signal_receiver_is_connected(self) -> None:
        responses = user_logged_in.send(sender=User, request=None, user=self.owner_a)
        self.assertTrue(any(receiver is log_login for receiver, _ in responses))

    def test_logout_signal_receiver_is_connected(self) -> None:
        responses = user_logged_out.send(sender=User, request=None, user=self.owner_a)
        self.assertTrue(any(receiver is log_logout for receiver, _ in responses))

    def test_logout_signal_handles_anonymous_user(self) -> None:
        # user=None is a valid logout payload (no one was authenticated); the receiver must not raise.
        user_logged_out.send(sender=User, request=None, user=None)

    def test_login_failed_signal_leaves_credentials_untouched(self) -> None:
        credentials = {'username': 'x@sonambulance.com', 'password': 'secret'}
        responses = user_login_failed.send(sender=User, credentials=credentials, request=None)
        self.assertTrue(any(receiver is log_login_failed for receiver, _ in responses))
        self.assertEqual(credentials, {'username': 'x@sonambulance.com', 'password': 'secret'})  # Not mutated/read out