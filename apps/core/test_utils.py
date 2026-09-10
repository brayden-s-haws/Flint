from __future__ import annotations

from django.test import TestCase

from apps.accounts.models import Account
from apps.users.models import User


class TenantTestCase(TestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        cls.owner_a = User.objects.create_user(email='a@stunkbeagle.com', password='pw')
        cls.owner_b = User.objects.create_user(email='b@buffalochildrens.com', password='pw')
        cls.account_a = Account.objects.get(owner=cls.owner_a)
        cls.account_b = Account.objects.get(owner=cls.owner_b)