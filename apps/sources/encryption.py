from __future__ import annotations
import json

from cryptography.fernet import Fernet
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured


def _get_fernet() -> Fernet:
    key = settings.ENCRYPTION_KEY
    if key is None:
        raise ImproperlyConfigured("ENCRYPTION_KEY is not set in settings")
    return Fernet(key.encode('utf-8'))


def encrypt_credentials(data: dict[str, str]) -> str:
    plaintext_bytes = json.dumps(data).encode('utf-8')
    encrypted_bytes = _get_fernet().encrypt(plaintext_bytes)
    return encrypted_bytes.decode('utf-8')



def decrypt_credentials(ciphertext: str) -> dict[str, str]:
    ciphertext_bytes = ciphertext.encode('utf-8')
    plaintext_bytes = _get_fernet().decrypt(ciphertext_bytes)
    return json.loads(plaintext_bytes.decode('utf-8'))