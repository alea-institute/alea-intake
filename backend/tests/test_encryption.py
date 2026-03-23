"""Tests for AES-256-GCM envelope encryption and key management.

Covers: EnvelopeEncryption round-trip, nonce uniqueness, wrong-key/corrupted-data
error handling, KeyManager local file backend with auto-generation, and
per-tenant DEK provisioning/unwrapping.
"""

import os
import tempfile

import pytest
from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.encryption import EnvelopeEncryption
from app.core.key_management import KeyManager


# ---------------------------------------------------------------------------
# EnvelopeEncryption tests
# ---------------------------------------------------------------------------


class TestEnvelopeEncryption:
    """Tests for the EnvelopeEncryption class."""

    @pytest.fixture
    def kek(self) -> bytes:
        """Generate a 32-byte KEK for testing."""
        return AESGCM.generate_key(bit_length=256)

    @pytest.fixture
    def envelope(self, kek: bytes) -> EnvelopeEncryption:
        """Create an EnvelopeEncryption instance with a test KEK."""
        return EnvelopeEncryption(kek)

    def test_generate_dek_returns_32_bytes(self, envelope: EnvelopeEncryption) -> None:
        """generate_dek() returns exactly 32 bytes (256 bits)."""
        dek = envelope.generate_dek()
        assert isinstance(dek, bytes)
        assert len(dek) == 32

    def test_dek_wrap_unwrap_roundtrip(self, envelope: EnvelopeEncryption) -> None:
        """Wrapping then unwrapping a DEK returns the original DEK."""
        dek = envelope.generate_dek()
        wrapped = envelope.wrap_dek(dek)
        unwrapped = envelope.unwrap_dek(wrapped)
        assert unwrapped == dek

    def test_encrypt_decrypt_roundtrip(self, envelope: EnvelopeEncryption) -> None:
        """Encrypting then decrypting a string produces the original string."""
        dek = envelope.generate_dek()
        plaintext = "Hello World"
        ciphertext = envelope.encrypt_field(dek, plaintext)
        assert isinstance(ciphertext, bytes)
        result = envelope.decrypt_field(dek, ciphertext)
        assert result == plaintext

    def test_unicode_roundtrip(self, envelope: EnvelopeEncryption) -> None:
        """Unicode strings survive encryption/decryption intact."""
        dek = envelope.generate_dek()
        plaintext = "caf\u00e9 \u2603 \U0001f600 unicode chars"
        ciphertext = envelope.encrypt_field(dek, plaintext)
        assert envelope.decrypt_field(dek, ciphertext) == plaintext

    def test_empty_string_roundtrip(self, envelope: EnvelopeEncryption) -> None:
        """Empty string encrypts and decrypts correctly."""
        dek = envelope.generate_dek()
        ciphertext = envelope.encrypt_field(dek, "")
        assert envelope.decrypt_field(dek, ciphertext) == ""

    def test_nonce_uniqueness(self, envelope: EnvelopeEncryption) -> None:
        """Two encryptions of the same plaintext produce different ciphertext."""
        dek = envelope.generate_dek()
        ct1 = envelope.encrypt_field(dek, "same text")
        ct2 = envelope.encrypt_field(dek, "same text")
        assert ct1 != ct2

    def test_wrong_dek_fails(self, envelope: EnvelopeEncryption) -> None:
        """Decryption with wrong DEK raises InvalidTag."""
        dek1 = envelope.generate_dek()
        dek2 = envelope.generate_dek()
        ciphertext = envelope.encrypt_field(dek1, "secret")
        with pytest.raises(InvalidTag):
            envelope.decrypt_field(dek2, ciphertext)

    def test_corrupted_ciphertext_fails(self, envelope: EnvelopeEncryption) -> None:
        """Corrupted ciphertext raises an error on decryption."""
        dek = envelope.generate_dek()
        ciphertext = envelope.encrypt_field(dek, "data")
        # Flip a byte in the encrypted portion (after the 12-byte nonce)
        corrupted = bytearray(ciphertext)
        corrupted[15] ^= 0xFF
        with pytest.raises(Exception):  # InvalidTag or similar
            envelope.decrypt_field(dek, bytes(corrupted))


# ---------------------------------------------------------------------------
# KeyManager tests
# ---------------------------------------------------------------------------


class TestKeyManager:
    """Tests for the KeyManager local file backend."""

    def test_key_manager_local_file(self) -> None:
        """KeyManager loads a 32-byte key from an existing file."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".key") as f:
            key_bytes = os.urandom(32)
            f.write(key_bytes)
            key_path = f.name

        try:
            km = KeyManager(master_key_path=key_path)
            # Should be able to provision and retrieve a tenant DEK
            dek, wrapped = km.provision_tenant_dek("test-org")
            recovered = km.get_tenant_dek("test-org", wrapped)
            assert recovered == dek
        finally:
            os.unlink(key_path)

    def test_key_manager_auto_generates_key(self) -> None:
        """KeyManager auto-generates key file if path set but file missing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            key_path = os.path.join(tmpdir, "auto_generated.key")
            assert not os.path.exists(key_path)

            km = KeyManager(master_key_path=key_path)

            # File should now exist with 32 bytes
            assert os.path.exists(key_path)
            with open(key_path, "rb") as f:
                assert len(f.read()) == 32

            # File permissions should be 0o600 (owner read/write only)
            stat = os.stat(key_path)
            assert oct(stat.st_mode)[-3:] == "600"

            # KeyManager should be functional
            dek, wrapped = km.provision_tenant_dek("auto-org")
            assert km.get_tenant_dek("auto-org", wrapped) == dek

    def test_key_manager_no_config_raises(self) -> None:
        """KeyManager raises ValueError when no key source is configured."""
        with pytest.raises(ValueError, match="No encryption key source configured"):
            KeyManager(master_key_path="", kms_provider="", kms_key_id="")

    def test_field_level_encryption_via_key_manager(self) -> None:
        """KeyManager.encrypt_field / decrypt_field round-trip works."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".key") as f:
            f.write(os.urandom(32))
            key_path = f.name

        try:
            km = KeyManager(master_key_path=key_path)
            dek, _ = km.provision_tenant_dek("field-org")
            encrypted = km.encrypt_field(dek, "Sensitive PII Data")
            assert isinstance(encrypted, bytes)
            decrypted = km.decrypt_field(dek, encrypted)
            assert decrypted == "Sensitive PII Data"
        finally:
            os.unlink(key_path)

    def test_provision_returns_dek_and_wrapped_pair(self) -> None:
        """provision_tenant_dek returns a (dek, wrapped_dek) tuple."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".key") as f:
            f.write(os.urandom(32))
            key_path = f.name

        try:
            km = KeyManager(master_key_path=key_path)
            result = km.provision_tenant_dek("pair-org")
            assert isinstance(result, tuple)
            assert len(result) == 2
            dek, wrapped = result
            assert isinstance(dek, bytes)
            assert len(dek) == 32
            assert isinstance(wrapped, bytes)
            # Wrapped should be longer than DEK (nonce + encrypted DEK + auth tag)
            assert len(wrapped) > len(dek)
        finally:
            os.unlink(key_path)
