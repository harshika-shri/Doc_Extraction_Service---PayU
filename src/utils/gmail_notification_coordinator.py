from __future__ import annotations

import re

import redis

from src.config.settings import settings
from src.core.exceptions.llm_exc import LLMServiceError
from src.utils.gmail_history_cache import (
    get_last_processed_history_id,
    is_stale_gmail_notification,
)

_WORKER_ACTIVE_TTL_SECONDS = 900
_PENDING_HISTORY_TTL_SECONDS = 3600
_MESSAGE_LOCK_TTL_SECONDS = 1800
_PROCESSED_MESSAGE_TTL_SECONDS = 60 * 60 * 24 * 30


def _processing_claim_key(
    message_id: str,
) -> str:
    return (
        "doc_extraction:gmail:"
        f"processing_claim:{message_id}"
    )


def claim_message_for_task(
    message_id: str,
    task_id: str,
) -> bool:
    """Acquire processing ownership for a message.

    Returns True if this task now owns the message (fresh or re-claim).
    Returns False if a *different* task already owns it.
    """
    client = _redis_client()
    key = _processing_claim_key(message_id)

    try:
        acquired = client.set(
            key,
            task_id,
            nx=True,
            ex=_MESSAGE_LOCK_TTL_SECONDS,
        )

        if acquired:
            return True

        current = client.get(key)

        if current == task_id:
            client.set(
                key,
                task_id,
                ex=_MESSAGE_LOCK_TTL_SECONDS,
            )
            return True

        return False
    finally:
        client.close()


def release_message_claim(
    message_id: str,
    task_id: str,
) -> None:
    """Release ownership only if this task still holds it."""
    client = _redis_client()
    key = _processing_claim_key(message_id)

    try:
        current = client.get(key)

        if current == task_id:
            client.delete(key)
    finally:
        client.close()




def _redis_client() -> redis.Redis:
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True,
    )


def _pending_history_key(
    email_address: str,
) -> str:
    return (
        "doc_extraction:gmail:"
        f"pending_history:{email_address}"
    )


def _worker_active_key(
    email_address: str,
) -> str:
    return (
        "doc_extraction:gmail:"
        f"worker_active:{email_address}"
    )


def _message_lock_key(
    message_id: str,
) -> str:
    return (
        "doc_extraction:gmail:"
        f"message_lock:{message_id}"
    )


def update_pending_history_id(
    email_address: str,
    history_id: int,
) -> int:
    client = _redis_client()

    try:
        pending_key = _pending_history_key(
            email_address,
        )
        current_value = client.get(
            pending_key,
        )
        current_pending = (
            int(
                current_value,
            )
            if current_value is not None
            else 0
        )
        target_history_id = max(
            current_pending,
            history_id,
        )

        client.set(
            pending_key,
            str(
                target_history_id,
            ),
            ex=_PENDING_HISTORY_TTL_SECONDS,
        )

        return target_history_id
    finally:
        client.close()


def get_pending_history_id(
    email_address: str,
) -> int | None:
    client = _redis_client()

    try:
        value = client.get(
            _pending_history_key(
                email_address,
            ),
        )
    finally:
        client.close()

    if value is None:
        return None

    return int(
        value,
    )


def should_enqueue_gmail_worker(
    email_address: str,
    history_id: int,
) -> bool:
    if is_stale_gmail_notification(
        email_address,
        history_id,
    ):
        return False

    client = _redis_client()

    try:
        acquired = client.set(
            _worker_active_key(
                email_address,
            ),
            "1",
            nx=True,
            ex=_WORKER_ACTIVE_TTL_SECONDS,
        )

        return bool(
            acquired,
        )
    finally:
        client.close()


def resolve_target_history_id(
    email_address: str,
    history_id: int,
) -> int:
    pending_history_id = get_pending_history_id(
        email_address,
    )

    if pending_history_id is None:
        return history_id

    return max(
        pending_history_id,
        history_id,
    )


def force_release_gmail_worker(
    email_address: str,
) -> None:
    client = _redis_client()

    try:
        client.delete(
            _worker_active_key(
                email_address,
            ),
        )
    finally:
        client.close()


def release_gmail_worker(
    email_address: str,
) -> int | None:
    client = _redis_client()

    try:
        client.delete(
            _worker_active_key(
                email_address,
            ),
        )

        pending_value = client.get(
            _pending_history_key(
                email_address,
            ),
        )

        if pending_value is None:
            return None

        pending_history_id = int(
            pending_value,
        )
        last_processed = get_last_processed_history_id(
            email_address,
        )

        if (
            last_processed is not None
            and pending_history_id
            <= last_processed
        ):
            client.delete(
                _pending_history_key(
                    email_address,
                ),
            )
            return None

        if (
            last_processed is None
            or pending_history_id
            > last_processed
        ):
            return pending_history_id

        return None
    finally:
        client.close()


def clear_pending_history_id(
    email_address: str,
    *,
    history_id: int | None = None,
) -> None:
    client = _redis_client()

    try:
        pending_key = _pending_history_key(
            email_address,
        )

        if history_id is None:
            client.delete(
                pending_key,
            )
            return

        pending_value = client.get(
            pending_key,
        )

        if pending_value is None:
            return

        if int(
            pending_value,
        ) <= history_id:
            client.delete(
                pending_key,
            )
    finally:
        client.close()


def _processed_message_key(
    message_id: str,
) -> str:
    return (
        "doc_extraction:gmail:"
        f"processed_message:{message_id}"
    )


def is_gmail_message_processed(
    message_id: str,
) -> bool:
    client = _redis_client()

    try:
        return bool(
            client.exists(
                _processed_message_key(
                    message_id,
                ),
            ),
        )
    finally:
        client.close()


def mark_gmail_message_processed(
    message_id: str,
) -> None:
    client = _redis_client()

    try:
        client.set(
            _processed_message_key(
                message_id,
            ),
            "1",
            ex=_PROCESSED_MESSAGE_TTL_SECONDS,
        )
    finally:
        client.close()


def try_acquire_message_lock(
    message_id: str,
) -> bool:
    client = _redis_client()

    try:
        acquired = client.set(
            _message_lock_key(
                message_id,
            ),
            "1",
            nx=True,
            ex=_MESSAGE_LOCK_TTL_SECONDS,
        )

        return bool(
            acquired,
        )
    finally:
        client.close()


def release_message_lock(
    message_id: str,
) -> None:
    client = _redis_client()

    try:
        client.delete(
            _message_lock_key(
                message_id,
            ),
        )
    finally:
        client.close()


def get_llm_retry_countdown(
    error: BaseException,
    *,
    retries: int,
    default_backoff_seconds: int,
) -> int:
    if isinstance(
        error,
        LLMServiceError,
    ):
        match = re.search(
            r"try again in (?:(\d+)m)?([\d.]+)s",
            error.detail,
            flags=re.IGNORECASE,
        )

        if match is not None:
            minutes = int(
                match.group(
                    1,
                )
                or 0,
            )
            seconds = float(
                match.group(
                    2,
                ),
            )

            return int(
                minutes * 60
                + seconds
                + 5,
            )

    return default_backoff_seconds * (
        2**retries
    )
