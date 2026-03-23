"""Key management layer for envelope encryption.

Provides :class:`KeyManager` which loads the master Key Encryption Key (KEK)
from a local file and delegates all cryptographic operations to
:class:`~app.core.encryption.EnvelopeEncryption`.

Cloud KMS support (AWS KMS / GCP KMS) is deferred to Phase 11.  The interface
accepts ``kms_provider`` and ``kms_key_id`` parameters so the transition will
be additive rather than breaking.
"""

from __future__ import annotations

import os
import stat

from app.core.encryption import EnvelopeEncryption

_KEY_LENGTH = 32  # 256 bits


class KeyManager:
    """Manage the master KEK and per-tenant DEK lifecycle.

    Parameters
    ----------
    master_key_path:
        Path to a file containing the 32-byte master KEK.  If the file does
        not exist it will be auto-generated with restrictive permissions.
    kms_provider:
        Cloud KMS provider name (``"aws"`` or ``"gcp"``).  Not yet implemented.
    kms_key_id:
        Cloud KMS key ARN / resource ID.  Not yet implemented.
    """

    def __init__(
        self,
        master_key_path: str = "",
        kms_provider: str = "",
        kms_key_id: str = "",
    ) -> None:
        if master_key_path:
            kek = self._load_or_generate_key(master_key_path)
        elif kms_provider and kms_key_id:
            # Cloud KMS -- deferred to Phase 11
            raise NotImplementedError(
                f"Cloud KMS provider '{kms_provider}' is not yet implemented. "
                "Use master_key_path for local key file backend."
            )
        else:
            raise ValueError(
                "No encryption key source configured. "
                "Set ALEA_MASTER_KEY_PATH or KMS config."
            )

        self.envelope = EnvelopeEncryption(kek)

    # -- Key file handling ---------------------------------------------------

    @staticmethod
    def _load_or_generate_key(path: str) -> bytes:
        """Load a 32-byte key from *path*, or generate one if missing."""
        if os.path.exists(path):
            with open(path, "rb") as f:
                key = f.read()
            if len(key) != _KEY_LENGTH:
                raise ValueError(
                    f"Key file {path} contains {len(key)} bytes, "
                    f"expected {_KEY_LENGTH}"
                )
            return key

        # Auto-generate
        key = os.urandom(_KEY_LENGTH)

        # Ensure parent directory exists
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)

        # Write with restrictive permissions (owner read/write only)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, stat.S_IRUSR | stat.S_IWUSR)
        try:
            os.write(fd, key)
        finally:
            os.close(fd)

        return key

    # -- Per-tenant DEK operations -------------------------------------------

    def provision_tenant_dek(self, org_slug: str) -> tuple[bytes, bytes]:
        """Generate and wrap a new DEK for the given tenant.

        Returns
        -------
        tuple[bytes, bytes]
            ``(dek, wrapped_dek)`` -- the caller stores ``wrapped_dek`` in the
            tenant's configuration record; ``dek`` is used for immediate
            encryption and should not be persisted in plaintext.
        """
        dek = self.envelope.generate_dek()
        wrapped = self.envelope.wrap_dek(dek)
        return dek, wrapped

    def get_tenant_dek(self, org_slug: str, wrapped_dek: bytes) -> bytes:
        """Unwrap a stored wrapped DEK for the given tenant."""
        return self.envelope.unwrap_dek(wrapped_dek)

    # -- Convenience pass-through methods ------------------------------------

    def encrypt_field(self, dek: bytes, plaintext: str) -> bytes:
        """Encrypt a plaintext string using the given DEK."""
        return self.envelope.encrypt_field(dek, plaintext)

    def decrypt_field(self, dek: bytes, ciphertext: bytes) -> str:
        """Decrypt ciphertext back to a string using the given DEK."""
        return self.envelope.decrypt_field(dek, ciphertext)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_key_manager: KeyManager | None = None


def get_key_manager() -> KeyManager:
    """Return the module-level :class:`KeyManager` singleton.

    Lazily initialised from application settings on first call.
    """
    global _key_manager  # noqa: PLW0603

    if _key_manager is None:
        from app.config import get_settings

        settings = get_settings()
        _key_manager = KeyManager(
            master_key_path=settings.master_key_path,
            kms_provider=settings.kms_provider,
            kms_key_id=settings.kms_key_id,
        )

    return _key_manager
