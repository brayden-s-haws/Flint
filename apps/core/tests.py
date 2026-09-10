from __future__ import annotations

from django.db import IntegrityError, transaction

from apps.accounts.models import AccountInvitation
from apps.core.test_utils import TenantTestCase

class SmokeTest(TenantTestCase):
    def test_two_accounts_exist(self) -> None:
        self.assertNotEqual(self.account_a.pk, self.account_b.pk)


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


class TenantModelTest(TenantTestCase):
    def test_account_is_required(self) -> None:
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                AccountInvitation.objects.create(
                    email='test@example.com',
                    invited_by=self.owner_a,
                )