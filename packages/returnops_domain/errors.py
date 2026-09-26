"""Static customer-flow failures: no payload, credentials, SQL or parser details."""
from __future__ import annotations

_MESSAGES = {
    "UNAUTHENTICATED": (401, "A valid session is required.", False),
    "FORBIDDEN": (403, "This operation is not permitted for this role.", False),
    "NOT_FOUND": (404, "Resource not found.", False),
    "VALIDATION_ERROR": (422, "Request fields are invalid.", False),
    "STALE_CASE_VERSION": (409, "The case version has changed.", False),
    "IDEMPOTENCY_CONFLICT": (409, "This request key was used for different content.", False),
    "INVALID_STATE": (409, "The request is not available in the current state.", False),
    "REQUEST_TOO_LARGE": (413, "The uploaded file exceeds the size limit.", False),
    "UNSUPPORTED_MEDIA_TYPE": (415, "The file type and content are not supported.", False),
    "INTERNAL_ERROR": (503, "The service is temporarily unavailable; keep the original request key.", True),
}

class FlowError(Exception):
    def __init__(self, code: str = "INTERNAL_ERROR", *, status: int | None = None) -> None:
        default_status, message, retryable = _MESSAGES[code]
        self.code, self.status, self.message, self.retryable = code, status or default_status, message, retryable
        super().__init__(message)

    def envelope(self, correlation_id: str) -> dict:
        return {"error": {"code": self.code, "message": self.message,
                          "correlation_id": correlation_id, "retryable": self.retryable, "details": []}}

class AcceptanceOutcomeUnknown(Exception):
    """Commit acknowledgement was lost. Resolve with the same fence and key."""
    def __init__(self) -> None:
        super().__init__("Acceptance outcome is unknown; retain the original request key.")

class ReceiptUnavailable(FlowError):
    def __init__(self):
        super().__init__("INVALID_STATE")
        self.message = "This request was previously accepted, but its original receipt is unavailable. Read the current case/history and retain the request key."
        self.args = (self.message,)
