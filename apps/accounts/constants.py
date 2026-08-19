""" Tracks the set of excluded email domains that should not be linked to an existing account. """

from __future__ import annotations

# Free and personal email domains are excluded from the account domain registration guard. Since these domains are not associated with a specific organization, they should not be linked to an existing account.
EXCLUDED_DOMAINS = frozenset((
    'aol.com',
    'att.net',
    'comcast.net',
    'cox.net',
    'gmail.com',
    'gmx.com',
    'hotmail.com',
    'icloud.com',
    'inbox.com',
    'live.com',
    'mail.com',
    'mail.ru',
    'me.com',
    'msn.com',
    'outlook.com',
    'protonmail.com',
    'sbcglobal.net',
    'tutanota.com',
    'verizon.net',
    'yahoo.com',
    'yandex.com',
    'zoho.com',
))
