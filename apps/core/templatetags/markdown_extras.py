from __future__ import annotations

from django.template import Library
from django.utils.safestring import mark_safe
import markdown


register = Library()

@register.filter
def render_markdown(value: str) -> str:
    return mark_safe(markdown.markdown(value))
