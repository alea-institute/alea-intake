"""Standalone encryption utilities and EncryptionContext for field-level PII protection.

Provides two layers:
  - **Standalone functions** (``encrypt_value`` / ``decrypt_value``) for direct use.
  - **EncryptionContext** class that wraps a per-request tenant DEK and exposes
    ``encrypt`` / ``decrypt`` methods for use in service layers.

Model columns storing encrypted PII use ``LargeBinary`` (raw bytes in DB).
Services call ``EncryptionContext.encrypt()`` before INSERT and
``EncryptionContext.decrypt()`` after SELECT, keeping the tenant DEK
request-scoped rather than embedded in the column type.

This design avoids the challenges of a SQLAlchemy ``TypeDecorator`` with
request-scoped DEKs while still providing a clean encryption API.
"""

from __future__ import annotations

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE_LENGTH = 12  # 96-bit nonce per NIST recommendation for AES-GCM


# ---------------------------------------------------------------------------
# Standalone functions
# ---------------------------------------------------------------------------


def encrypt_value(dek: bytes, plaintext: str) -> bytes:
    """Encrypt a plaintext string using AES-256-GCM with the given DEK.

    Returns ``nonce || ciphertext`` as raw bytes.

    Parameters
    ----------
    dek:
        32-byte Data Encryption Key.
    plaintext:
        The string to encrypt (may be empty).
    """
    nonce = os.urandom(_NONCE_LENGTH)
    aesgcm = AESGCM(dek)
    encrypted = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return nonce + encrypted


def decrypt_value(dek: bytes, ciphertext: bytes) -> str:
    """Decrypt ciphertext produced by :func:`encrypt_value` back to a string.

    Parameters
    ----------
    dek:
        32-byte Data Encryption Key (must match the key used for encryption).
    ciphertext:
        The ``nonce || ciphertext`` bytes returned by :func:`encrypt_value`.
    """
    nonce = ciphertext[:_NONCE_LENGTH]
    encrypted = ciphertext[_NONCE_LENGTH:]
    aesgcm = AESGCM(dek)
    return aesgcm.decrypt(nonce, encrypted, None).decode("utf-8")


# ---------------------------------------------------------------------------
# EncryptionContext -- per-request wrapper
# ---------------------------------------------------------------------------


class EncryptionContext:
    """Per-request encryption context bound to a tenant's DEK.

    Intended for use as a FastAPI dependency that provides encrypt/decrypt
    operations scoped to the current tenant's Data Encryption Key.

    Parameters
    ----------
    dek:
        32-byte Data Encryption Key for the current tenant.
    """

    def __init__(self, dek: bytes) -> None:
        if len(dek) != 32:
            raise ValueError(f"DEK must be exactly 32 bytes, got {len(dek)}")
        self._dek = dek

    def encrypt(self, plaintext: str) -> bytes:
        """Encrypt a plaintext string for storage in a ``LargeBinary`` column."""
        return encrypt_value(self._dek, plaintext)

    def decrypt(self, ciphertext: bytes) -> str:
        """Decrypt a ``LargeBinary`` column value back to a plaintext string."""
        return decrypt_value(self._dek, ciphertext)
