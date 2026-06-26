from __future__ import annotations

import re
import socket
import urllib.error

from fastapi import HTTPException

from src.core.exceptions.base_exc import AppException
from src.core.exceptions.llm_exc import LLMServiceError
from src.core.exceptions.vendor_master_exc import (
    VendorMasterOnboardingError,
)

TRANSIENT_HTTP_STATUS_CODES = {
    408,
    429,
    500,
    502,
    503,
    504,
}


def get_retry_countdown_for_error(
    error: BaseException,
    *,
    retries: int,
    default_backoff_seconds: int,
) -> int:
    if isinstance(
        error,
        LLMServiceError,
    ):
        parsed = _parse_groq_retry_after_seconds(
            error.detail,
        )

        if parsed is not None:
            return parsed

    return default_backoff_seconds * (
        2**retries
    )


def _parse_groq_retry_after_seconds(
    detail: str,
) -> int | None:
    minute_match = re.search(
        r"try again in (\d+)m([\d.]+)s",
        detail,
        flags=re.IGNORECASE,
    )

    if minute_match:
        return (
            int(
                minute_match.group(
                    1,
                ),
            )
            * 60
            + int(
                float(
                    minute_match.group(
                        2,
                    ),
                ),
            )
            + 1
        )

    second_match = re.search(
        r"try again in ([\d.]+)s",
        detail,
        flags=re.IGNORECASE,
    )

    if second_match:
        return (
            int(
                float(
                    second_match.group(
                        1,
                    ),
                ),
            )
            + 1
        )

    return None


def is_transient_error(
    error: BaseException,
) -> bool:
    if isinstance(
        error,
        (
            ConnectionError,
            TimeoutError,
            OSError,
            socket.timeout,
            urllib.error.URLError,
        ),
    ):
        return True

    if isinstance(
        error,
        LLMServiceError,
    ):
        return (
            error.status_code
            in TRANSIENT_HTTP_STATUS_CODES
            or error.status_code >= 500
        )

    if isinstance(
        error,
        RuntimeError,
    ):
        message = str(
            error,
        ).lower()

        return "lock" in message

    return False


def is_permanent_business_error(
    error: BaseException,
) -> bool:
    return isinstance(
        error,
        (
            HTTPException,
            VendorMasterOnboardingError,
            AppException,
        ),
    ) and not isinstance(
        error,
        LLMServiceError,
    )
