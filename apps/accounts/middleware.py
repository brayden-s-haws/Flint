""" Used for tenant resolution: attaches the active account to each request. """
from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from .models import AccountMembership


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
            request.account = membership.account if membership else None
        else:
            request.account = None
        response = self.get_response(request)
        return response
