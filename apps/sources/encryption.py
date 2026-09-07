""" Fernet-based encryption for source credentials at rest. Credentials are stored encrypted on Source.credentials and decrypted only at connector instantiation; decrypted values must never be
logged, returned in JSON, or rendered in templates. """
from __future__ import annotations
import json
import logging

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


logger = logging.getLogger(__name__)


def _get_fernet() -> Fernet:
    """Build the Fernet cipher from settings.ENCRYPTION_KEY; raises ImproperlyConfigured if the key is unset."""
    key = settings.ENCRYPTION_KEY
    if key is None:
        logger.error("ENCRYPTION_KEY is not set in settings")
        raise ImproperlyConfigured("ENCRYPTION_KEY is not set in settings")
    return Fernet(key.encode('utf-8'))


def encrypt_credentials(data: dict[str, str]) -> str:
    """Serialize a credentials dict to JSON and return its Fernet ciphertext, suitable for storing on Source.credentials."""
    plaintext_bytes = json.dumps(data).encode('utf-8')
    encrypted_bytes = _get_fernet().encrypt(plaintext_bytes)
    return encrypted_bytes.decode('utf-8')


def decrypt_credentials(ciphertext: str) -> dict[str, str]:
    """Reverse encrypt_credentials: decrypt the stored ciphertext back to the credentials dict. Call only where credentials are needed (connector setup); never persist or log the result."""
    try:
        ciphertext_bytes = ciphertext.encode('utf-8')
        plaintext_bytes = _get_fernet().decrypt(ciphertext_bytes)
        return json.loads(plaintext_bytes.decode('utf-8'))
    except InvalidToken as exc:
        logger.error("Credential decryption failed: %s", type(exc).__name__)
        raise