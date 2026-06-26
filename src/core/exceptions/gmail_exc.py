from __future__ import annotations


class GmailHistoryStaleError(
    Exception,
):
    """Raised when Gmail no longer has the stored history cursor."""
