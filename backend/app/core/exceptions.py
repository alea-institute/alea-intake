"""Custom exception classes for the ALEA Intake application."""


class TenantNotFoundError(Exception):
    """Raised when a requested tenant/organization cannot be found."""

    def __init__(self, tenant_id: str | int | None = None, message: str | None = None):
        self.tenant_id = tenant_id
        self.message = message or f"Tenant not found: {tenant_id}"
        super().__init__(self.message)


class EncryptionError(Exception):
    """Raised when an encryption or decryption operation fails."""

    def __init__(self, message: str = "Encryption operation failed"):
        self.message = message
        super().__init__(self.message)


class ConsentRequiredError(Exception):
    """Raised when an operation requires consent that has not been granted."""

    def __init__(self, message: str = "Consent is required before this action can proceed"):
        self.message = message
        super().__init__(self.message)


class InsufficientPermissionsError(Exception):
    """Raised when a user lacks the required permissions for an operation."""

    def __init__(self, message: str = "You do not have permission to perform this action"):
        self.message = message
        super().__init__(self.message)
