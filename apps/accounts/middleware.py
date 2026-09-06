""" Used for tenant resolution: attaches the active account to each request. """
from __future__ import annotations

from collections.abc import Callable
import logging

from django.http import HttpRequest, HttpResponse

from .models import AccountMembership


logger = logging.getLogger(__name__)


class TenantMiddleware:
    """
    - Middleware that sets the current account on the request object. Needed to ensure that the current user only sees data related to their account.
    - This takes the user's first account membership and sets it on the request object. If the user belongs to multiple accounts, they can only access the first one. Multiple account switching to be
    added in the future.
    - If a user belongs to no accounts, they will not be able to access any data.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        if request.user.is_authenticated:
            membership = AccountMembership.objects.filter(user=request.user).first()
            if membership:
                request.account = membership.account
                logger.debug("Account resolved to %s", membership.account.id)
            else:
                request.account = None
                logger.warning("No account resolved for user %s", request.user.id)
        else:
            request.account = None
            logger.debug("No account resolved for unauthenticated user")
        response = self.get_response(request)
        return response
