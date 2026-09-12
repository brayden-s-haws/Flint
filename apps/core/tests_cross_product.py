""" Cross-cutting tests that span apps: the auth-required redirect on every login-gated view, and
the six @require_POST source views returning 405 on a GET. Per-view tenancy 404/403 boundaries and
list scoping are asserted within each app's own tests; this module covers the two sweeps that
aren't naturally per-app. """
from __future__ import annotations

from django.test import TestCase
from django.urls import reverse

from apps.core.test_utils import TenantTestCase


class AuthRequiredTest(TestCase):
    """Every @login_required / LoginRequiredMixin view redirects an unauthenticated request to the login URL."""
    def test_login_gated_views_redirect(self) -> None:
        login_url = reverse('users:login')
        # A representative sweep across every app's login-gated views. Dummy pks are fine: the
        # login redirect fires before the view body (and before any DB lookup) runs.
        gated_urls = [
            reverse('core:dashboard'),
            reverse('sources:list'),
            reverse('sources:add'),
            reverse('sources:detail', kwargs={'pk': 1}),
            reverse('sources:edit', kwargs={'pk': 1}),
            reverse('sources:delete', kwargs={'pk': 1}),
            reverse('catalog:list'),
            reverse('catalog:detail', kwargs={'pk': 1}),
            reverse('insights:list'),
            reverse('insights:detail', kwargs={'pk': 1}),
            reverse('insights:discovery'),
            reverse('accounts:settings'),
        ]
        for url in gated_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(login_url))   # redirected to /auth/login/?next=...


class RequirePostMethodTest(TenantTestCase):
    """The six @require_POST source views return 405 on a GET (authenticated, so @login_required passes first)."""
    def setUp(self) -> None:
        self.client.force_login(self.owner_a)

    def test_get_returns_405(self) -> None:
        # login_required is outermost, so an authenticated GET reaches @require_POST → 405 before the
        # view body; dummy pks never get looked up.
        post_only_urls = [
            reverse('sources:test_connection', kwargs={'pk': 1}),
            reverse('sources:sync', kwargs={'pk': 1}),
            reverse('sources:schedule_create', kwargs={'pk': 1}),
            reverse('sources:schedule_toggle', kwargs={'pk': 1}),
            reverse('sources:schedule_delete', kwargs={'pk': 1}),
            reverse('sources:load_demo'),
        ]
        for url in post_only_urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)