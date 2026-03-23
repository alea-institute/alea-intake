---
phase: 01-foundation-security
plan: 03
subsystem: encryption, security
tags: [aes-256-gcm, envelope-encryption, per-tenant-dek, kek, cryptography, aesgcm, field-level-encryption]

# Dependency graph
requires:
  - phase: 01-foundation-security plan 01
    provides: Settings with master_key_path/kms_provider/kms_key_id, LargeBinary PII columns, core/exceptions module
provides:
  - EnvelopeEncryption class with AES-256-GCM key wrapping and field encryption
  - KeyManager with local key file backend and auto-generation
  - Per-tenant DEK provisioning and unwrapping
  - get_key_manager() singleton lazy-initialized from app settings
  - encrypt_value / decrypt_value standalone functions
  - EncryptionContext class for per-request tenant DEK scoping
affects: [01-04, 01-05, 02-intake-forms, 03-ai-analysis, all-phases-with-pii]

# Tech tracking
tech-stack:
  added: []
  patterns: [envelope-encryption, nonce-prepended-ciphertext, per-tenant-dek-isolation, request-scoped-encryption-context]

key-files:
  created:
    - backend/app/core/encryption.py
    - backend/app/core/key_management.py
    - backend/app/db/encrypted_type.py
    - backend/tests/test_encryption.py
  modified: []

key-decisions:
  - "AES-256-GCM via AESGCM primitive, not Fernet (Fernet is AES-128-CBC)"
  - "Standalone functions + EncryptionContext instead of SQLAlchemy TypeDecorator for request-scoped DEK support"
  - "Nonce prepended to ciphertext (nonce || ciphertext) for self-contained decryption"
  - "Auto-generate key file with 0o600 permissions if path set but file missing"

patterns-established:
  - "Envelope encryption: KEK wraps DEKs, DEKs encrypt fields -- two-layer key hierarchy"
  - "Nonce-prepended ciphertext: first 12 bytes = nonce, remainder = AES-GCM ciphertext+tag"
  - "EncryptionContext pattern: services receive per-request context with tenant DEK for encrypt/decrypt"
  - "Key auto-generation: KeyManager creates missing key files on first use with restrictive permissions"

requirements-completed: [SECURITY-03, SECURITY-04, SECURITY-06]

# Metrics
duration: 3min
completed: 2026-03-23
---

# Phase 1 Plan 03: Encryption Summary

**AES-256-GCM envelope encryption with per-tenant DEK isolation, local key file backend, and EncryptionContext for service-layer PII protection**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-23T00:03:44Z
- **Completed:** 2026-03-23T00:06:32Z
- **Tasks:** 2 (Task 1 via TDD)
- **Files modified:** 4

## Accomplishments
- AES-256-GCM envelope encryption with KEK wrapping per-tenant DEKs
- KeyManager with local key file backend, auto-generation, and singleton pattern
- EncryptionContext class for request-scoped tenant DEK encrypt/decrypt operations
- 13 comprehensive tests covering round-trip, nonce uniqueness, wrong-key, corrupted data, and key management scenarios

## Task Commits

Each task was committed atomically:

1. **Task 1: AES-256-GCM envelope encryption and key management (TDD)**
   - `1d24053` (test) -- RED: failing tests for encryption and key management
   - `26dadf9` (feat) -- GREEN: implementation passing all 13 tests
2. **Task 2: EncryptionContext and standalone encrypt/decrypt utilities** - `dccd2fc` (feat)

## Files Created/Modified
- `backend/app/core/encryption.py` - EnvelopeEncryption class with AES-256-GCM key wrapping and field-level encrypt/decrypt
- `backend/app/core/key_management.py` - KeyManager with local key file loading/auto-generation, per-tenant DEK provisioning, get_key_manager() singleton
- `backend/app/db/encrypted_type.py` - Standalone encrypt_value/decrypt_value functions and EncryptionContext class for per-request encryption
- `backend/tests/test_encryption.py` - 13 tests covering all encryption and key management scenarios

## Decisions Made
- **AES-256-GCM over Fernet:** Used AESGCM from cryptography.hazmat directly. Fernet only provides AES-128-CBC which does not satisfy the SECURITY-03 requirement for AES-256.
- **EncryptionContext over TypeDecorator:** SQLAlchemy TypeDecorator requires the DEK at column-definition time, but DEKs are request-scoped (per-tenant). Using standalone functions + EncryptionContext as a FastAPI dependency allows clean per-request DEK injection.
- **Nonce-prepended ciphertext:** Every encrypted value is stored as `nonce(12 bytes) || ciphertext` so decryption is self-contained without external nonce storage.
- **Key auto-generation:** KeyManager creates missing key files with `os.urandom(32)` and `0o600` permissions, making dev/test setup zero-config.

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Encryption layer ready for any model field using LargeBinary columns
- Services will use `EncryptionContext.encrypt()` / `.decrypt()` with per-request tenant DEK
- Plan 04 (audit/consent) can apply encryption to consent record PII
- Plan 05 (LLM/Docker) can use encryption for LLM API key storage

## Self-Check: PASSED

All 4 created files verified on disk. All 3 commit hashes (1d24053, 26dadf9, dccd2fc) confirmed in git log.

---
*Phase: 01-foundation-security*
*Completed: 2026-03-23*
