from __future__ import annotations

import redis

from src.config.settings import settings


def _redis_client() -> redis.Redis:
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True,
    )


def _cache_key(
    email_address: str,
) -> str:
    return (
        "doc_extraction:gmail:"
        f"last_processed_history:{email_address}"
    )


def _monitoring_active_key(
    email_address: str,
) -> str:
    return (
        "doc_extraction:gmail:"
        f"monitoring_active:{email_address}"
    )


def set_monitoring_active(
    email_address: str,
    *,
    active: bool,
) -> None:
    client = _redis_client()

    try:
        key = _monitoring_active_key(
            email_address,
        )

        if active:
            client.set(
                key,
                "1",
            )
        else:
            client.delete(
                key,
            )
    finally:
        client.close()


def is_monitoring_active(
    email_address: str,
) -> bool:
    client = _redis_client()

    try:
        return bool(
            client.exists(
                _monitoring_active_key(
                    email_address,
                ),
            ),
        )
    finally:
        client.close()


def get_last_processed_history_id(
    email_address: str,
) -> int | None:
    client = _redis_client()

    try:
        value = client.get(
            _cache_key(
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


def cache_last_processed_history_id(
    email_address: str,
    history_id: int,
) -> None:
    client = _redis_client()

    try:
        client.set(
            _cache_key(
                email_address,
            ),
            str(
                history_id,
            ),
        )
    finally:
        client.close()


def is_stale_gmail_notification(
    email_address: str,
    history_id: int,
) -> bool:
    last_processed = get_last_processed_history_id(
        email_address,
    )

    if last_processed is None:
        return False

    return history_id <= last_processed
