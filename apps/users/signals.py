from __future__ import annotations

import logging
from typing import Any

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from django.http import HttpRequest


logger = logging.getLogger(__name__)


@receiver(user_logged_in)
def log_login(sender: type, request: HttpRequest, user: AbstractBaseUser, **kwargs: Any) -> None:
    logger.info("User %s logged in", user.id)


@receiver(user_logged_out)
def log_logout(sender: type, request: HttpRequest, user: AbstractBaseUser | None, **kwargs: Any) -> None:
    if user:
        logger.info("User %s logged out", user.id)
    else:
        logger.info("User logged out")


@receiver(user_login_failed)
def log_login_failed(sender: type, credentials: dict[str, Any], request: HttpRequest, **kwargs: Any) -> None:
    logger.warning("Login failed for submitted email")
