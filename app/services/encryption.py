"""
AES-256-GCM encryption service for at-rest message storage.
"""

import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from app.config import get_settings


class EncryptionService:
    def __init__(self):
        settings = get_settings()
        key_hex = settings.encryption_key
        self._key = bytes.fromhex(key_hex)
        if len(self._key) != 32:
            raise ValueError("ENCRYPTION_KEY must be 64 hex chars (32 bytes)")
        self._aesgcm = AESGCM(self._key)

    def encrypt(self, plaintext: str) -> tuple[bytes, bytes]:
        """Encrypt plaintext. Returns (ciphertext_with_tag, nonce)."""
        nonce = os.urandom(12)
        data = plaintext.encode("utf-8")
        ct = self._aesgcm.encrypt(nonce, data, None)  # includes GCM tag
        return ct, nonce

    def decrypt(self, ciphertext: bytes, nonce: bytes) -> str:
        """Decrypt ciphertext back to plaintext."""
        plaintext = self._aesgcm.decrypt(nonce, ciphertext, None)
        return plaintext.decode("utf-8")


_service: EncryptionService | None = None

def get_encryption_service() -> EncryptionService:
    global _service
    if _service is None:
        _service = EncryptionService()
    return _service
