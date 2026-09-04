""" Defines the custom email-based User model and its manager. Users authenticate by email rather than username; the inherited username field is retained but unused. """
from __future__ import annotations

from typing import Any

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

class UserManager(BaseUserManager):
    """
    - Email-keyed manager replacing Django's default, which assumes a username. Both creators normalize the email and hash the password rather than storing it.
    """
    def create_user(self, email: str, password: str | None, **extra_fields: Any) -> User:
        """Create and persist a user identified by email. A None password yields an unusable password (no direct login)."""
        if not email:
            raise ValueError('Users must have an email address')
        user = self.model(email=self.normalize_email(email), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str, **extra_fields: Any) -> User:
        """Create a user with staff + superuser flags set (used by `createsuperuser`)."""
        user = self.create_user(email, password, **extra_fields)
        user.is_staff = True
        user.is_superuser = True
        user.save(using=self._db)
        return user

class User(AbstractUser):
    """
    - Custom user with email as the login identifier (USERNAME_FIELD = 'email', email unique).
    - The inherited username field is kept optional/blank only to satisfy AbstractUser; it is not used for auth and REQUIRED_FIELDS is empty so email + password are the only prompts.
    """
    objects = UserManager()
    username = models.CharField(max_length=150, blank=True, default='')
    email = models.EmailField(unique=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    def __str__(self) -> str:
        return self.email