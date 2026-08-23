""" Provides tenant scoping for views, ensuring that only objects belonging to the user's account are returned. """
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from django.db.models import QuerySet
from django.core.exceptions import PermissionDenied

if TYPE_CHECKING:
    from django.http import HttpRequest


class TenantQuerysetMixin:
    """
    - Overrides get_queryset to filter the queryset by the user's account. Raises PermissionDenied if the user has no associated account.
    - Must be listed before other mixins that rely on the queryset.
    """
    request: HttpRequest

    def get_queryset(self) -> QuerySet[Any]:
        if self.request.account is None:  # type: ignore[attr-defined]
            raise PermissionDenied("User has no associated account")
        return super().get_queryset().filter(account=self.request.account) # type: ignore[union-attr]