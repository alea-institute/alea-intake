"""AES-256-GCM envelope encryption for field-level PII protection.

Uses the ``cryptography`` library's AESGCM primitive (AES-256 in GCM mode)
for both key wrapping and field-level encryption.  Fernet is explicitly
avoided because it provides only AES-128-CBC, which does not satisfy the
AES-256 compliance requirement (SECURITY-03).

Envelope encryption pattern:
  - A **Key Encryption Key (KEK)** wraps/unwraps per-tenant Data Encryption Keys.
  - Each tenant gets its own **DEK** for encrypting PII fields.
  - Each encryption operation uses a unique 12-byte random nonce prepended to
    the ciphertext so decryption can extract it.
"""

from __future__ import annotations

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_NONCE_LENGTH = 12  # 96-bit nonce per NIST recommendation for AES-GCM


class EnvelopeEncryption:
    """AES-256-GCM envelope encryption with per-tenant DEK support.

    Parameters
    ----------
    kek:
        A 32-byte (256-bit) Key Encryption Key used to wrap/unwrap DEKs.
    """

    def __init__(self, kek: bytes) -> None:
        if len(kek) != 32:
            raise ValueError(f"KEK must be exactly 32 bytes, got {len(kek)}")
        self.kek = kek

    # -- DEK lifecycle -------------------------------------------------------

    def generate_dek(self) -> bytes:
        """Generate a new 32-byte (256-bit) Data Encryption Key."""
        return AESGCM.generate_key(bit_length=256)

    def wrap_dek(self, dek: bytes) -> bytes:
        """Encrypt (wrap) a DEK using the KEK.

        Returns ``nonce || ciphertext`` so the nonce is available for unwrapping.
        """
        nonce = os.urandom(_NONCE_LENGTH)
        aesgcm = AESGCM(self.kek)
        encrypted = aesgcm.encrypt(nonce, dek, None)
        return nonce + encrypted

    def unwrap_dek(self, wrapped_dek: bytes) -> bytes:
        """Decrypt (unwrap) a DEK previously wrapped by :meth:`wrap_dek`."""
        nonce = wrapped_dek[:_NONCE_LENGTH]
        encrypted = wrapped_dek[_NONCE_LENGTH:]
        aesgcm = AESGCM(self.kek)
        return aesgcm.decrypt(nonce, encrypted, None)

    # -- Field-level encryption ----------------------------------------------

    def encrypt_field(self, dek: bytes, plaintext: str) -> bytes:
        """Encrypt a plaintext string using the given DEK.

        Returns ``nonce || ciphertext`` as raw bytes suitable for storage
        in a ``LargeBinary`` column.
        """
        nonce = os.urandom(_NONCE_LENGTH)
        aesgcm = AESGCM(dek)
        encrypted = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return nonce + encrypted

    def decrypt_field(self, dek: bytes, ciphertext: bytes) -> str:
        """Decrypt ciphertext produced by :meth:`encrypt_field` back to a string."""
        nonce = ciphertext[:_NONCE_LENGTH]
        encrypted = ciphertext[_NONCE_LENGTH:]
        aesgcm = AESGCM(dek)
        return aesgcm.decrypt(nonce, encrypted, None).decode("utf-8")
