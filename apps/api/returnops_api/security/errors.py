"""Safe internal denials; future HTTP adapters supply a correlation ID.

F.03; FR-009/012, NFR-003/009; docs/16 section 7 and CS-D01.
"""


class SecurityError(Exception):
    status_code = 500
    code = "INTERNAL_ERROR"
    message = "Security check failed."

    def __init__(self) -> None:
        super().__init__(self.message)


class Unauthenticated(SecurityError):
    status_code = 401
    code = "UNAUTHENTICATED"
    message = "A valid session is required."


class Forbidden(SecurityError):
    status_code = 403
    code = "FORBIDDEN"
    message = "This operation is not permitted for this role."


class ResourceNotFound(SecurityError):
    status_code = 404
    code = "NOT_FOUND"
    message = "Resource not found."


class SecurityDependencyError(SecurityError):
    status_code = 503
    code = "INTERNAL_ERROR"
    message = "Security verification is temporarily unavailable."


class SecurityStoreUnavailable(Exception):
    """Ports translate storage outages to this error; callers suppress details."""
