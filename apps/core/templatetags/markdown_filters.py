""" Strips markdown syntax down to plain text to ensure that content is rendered correctly. """
from __future__ import annotations
import re
from django import template

register = template.Library()


@register.filter
def strip_markdown(value: str) -> str:
    """
    Strips markdown syntax piece by piece using regex patterns.
    """
    value = re.sub(r'#{1,6}\s*', '', value)  # headings

    value = re.sub(r'\*{1,2}(.+?)\*{1,2}', r'\1', value)  # bold/italic
    value = re.sub(r'`(.+?)`', r'\1', value)  # inline code
    value = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', value)  # links
    value = re.sub(r'^\s*[-*+]\s+', '', value, flags=re.MULTILINE)  # list items

    return value.strip()