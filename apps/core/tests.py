from __future__ import annotations

from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.db import IntegrityError, transaction
from django.db.models import QuerySet
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import reverse

from apps.accounts.middleware import TenantMiddleware
from apps.accounts.models import AccountInvitation, AccountMembership
from apps.core.mixins import TenantQuerysetMixin
from apps.core.test_utils import TenantTestCase
from apps.insights.models import Insight
from apps.sources.models import Source, SourceType


class TenantFixtureTest(TenantTestCase):
    def test_accounts_are_distinct(self) -> None:
        self.assertNotEqual(self.account_a.pk, self.account_b.pk)

# Test core base models
class TimeStampedModelTest(TenantTestCase):
    def test_timestamps_set_on_create(self) -> None:
        self.assertIsNotNone(self.account_a.created_at)
        self.assertIsNotNone(self.account_a.updated_at)

    def test_updated_at_is_updated_on_save(self) -> None:
        old_ts = self.account_a.updated_at
        self.account_a.name = 'renamed'
        self.account_a.save()
        self.account_a.refresh_from_db()
        self.assertGreater(self.account_a.updated_at, old_ts)

    def test_created_at_unchanged_on_save(self) -> None:
        old_ts = self.account_a.created_at
        self.account_a.name = 'renamed'
        self.account_a.save()
        self.account_a.refresh_from_db()
        self.assertEqual(self.account_a.created_at, old_ts)

# Test tenant models
class TenantModelTest(TenantTestCase):
    def test_account_is_required(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AccountInvitation.objects.create(
                    email='test@example.com',
                    invited_by=self.owner_a,
                )

# Test tenant middleware
class TenantMiddlewareTest(TenantTestCase):
    def setUp(self) -> None:
        self.rf = RequestFactory()
        self.mw = TenantMiddleware(lambda req: HttpResponse())

    def test_member_resolves_account(self) -> None:
        request = self.rf.get('/')
        request.user = self.owner_a
        self.mw(request)
        self.assertEqual(request.account, self.account_a)

    def test_no_membership_is_none(self) -> None:
        AccountMembership.objects.filter(user=self.owner_a).delete()
        request = self.rf.get('/')
        request.user = self.owner_a
        self.mw(request)
        self.assertIsNone(request.account)

    def test_anonymous_user_is_none(self) -> None:
        request = self.rf.get('/')
        request.user = AnonymousUser()
        self.mw(request)
        self.assertIsNone(request.account)


# Test tenant queryset mixin
class _Base:
    def get_queryset(self) -> QuerySet[AccountInvitation]:
        return AccountInvitation.objects.all()


class _DummyView(TenantQuerysetMixin, _Base):
    pass


class TenantQuerysetMixinTest(TenantTestCase):
    def setUp(self) -> None:
        self.rf = RequestFactory()

    def test_none_account_raises(self) -> None:
        view = _DummyView()
        request = self.rf.get('/')
        request.user = self.owner_a
        request.account = None
        view.request = request
        with self.assertRaises(PermissionDenied):
            view.get_queryset()

    def test_filter_to_account(self) -> None:
        inv_a = AccountInvitation.objects.create(account=self.account_a, email='z@a.com', invited_by=self.owner_a)
        inv_b = AccountInvitation.objects.create(account=self.account_b, email='b@y.com', invited_by=self.owner_b)
        view = _DummyView()
        request = self.rf.get('/')
        request.account = self.account_a
        view.request = request
        qs = view.get_queryset()
        self.assertIn(inv_a, qs)
        self.assertNotIn(inv_b, qs)


#Test dashboard views
class DashboardViewTest(TenantTestCase):
    def test_requires_login(self) -> None:
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 302)
        self.assertRedirects(response, f"{reverse('users:login')}?next={reverse('core:dashboard')}")

    def test_source_counts_are_account_scoped(self) -> None:
        st = SourceType.objects.create(name='PostgreSQL')
        Source.objects.create(account=self.account_a, source_type=st, name='srcA', credentials='creds')
        Source.objects.create(account=self.account_b, source_type=st, name='srcB', credentials='creds')
        self.client.force_login(self.owner_a)
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['source_count'], 1)

    def test_insight_counts_are_account_scoped(self) -> None:
        Insight.objects.create(account=self.account_a, text='a', insight_type='manual', status='active')
        Insight.objects.create(account=self.account_b, text='b', insight_type='manual', status='active')
        Insight.objects.create(account=self.account_a, text='c', insight_type='manual', status='pending')
        self.client.force_login(self.owner_a)
        response = self.client.get(reverse('core:dashboard'))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['insight_count'], 1)