from __future__ import annotations

from django.template import Library
from django.utils.safestring import mark_safe
import markdown


register = Library()

@register.filter
# TODO(review): `markdown.markdown()` output is passed directly to `mark_safe` without HTML sanitisation. LLM-generated content could include raw HTML tags. Consider passing the output through `bleach.clean()` (allowlist-based) before marking safe, or use `markdown.markdown(value, extensions=['extra'])` with a custom HTML sanitiser.
def render_markdown(value: str) -> str:
    return mark_safe(markdown.markdown(value))
