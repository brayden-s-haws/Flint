""" Shared test utilities, provides the two-tenant fixture that every tenancy test builds on. """
from __future__ import annotations

from django.test import TestCase

from apps.accounts.models import Account
from apps.users.models import User


class TenantTestCase(TestCase):
    """
    - Base test case that provides two fully provisioned tenants. Creating each user fires the signal to create accounts and associate users with those accounts.
    - Other tests fetch these accounts and users, they are never recreated downstream.
    - The email domains are intentionally distinct to avoid the domain guard for account creation.
    """
    @classmethod
    def setUpTestData(cls) -> None:
        cls.owner_a = User.objects.create_user(email='a@stunkbeagle.com', password='pw')
        cls.owner_b = User.objects.create_user(email='b@buffalochildrens.com', password='pw')
        cls.account_a = Account.objects.get(owner=cls.owner_a)
        cls.account_b = Account.objects.get(owner=cls.owner_b)