from __future__ import annotations


class ClientCancelledError(Exception):
    """Raised when the HTTP client disconnects before processing completes."""
