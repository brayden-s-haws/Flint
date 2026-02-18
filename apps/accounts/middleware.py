from __future__ import annotations

from collections.abc import Callable

from django.http import HttpRequest, HttpResponse

from .models import AccountMembership


class TenantMiddleware:

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
