from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import redis

from src.config.settings import settings


def _redis_client() -> redis.Redis:
    return redis.Redis(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_DB,
        decode_responses=True,
    )


@contextmanager
def mailbox_processing_lock(
    email_address: str,
    *,
    lock_timeout_seconds: int = 600,
    blocking_timeout_seconds: int = 120,
) -> Iterator[None]:
    client = _redis_client()
    lock = client.lock(
        name=f"doc_extraction:gmail:{email_address}",
        timeout=lock_timeout_seconds,
        blocking_timeout=blocking_timeout_seconds,
    )
    acquired = lock.acquire(
        blocking=True,
    )

    try:
        if not acquired:
            raise RuntimeError(
                "Could not acquire Gmail mailbox processing lock "
                f"for {email_address}",
            )

        yield
    finally:
        if acquired:
            lock.release()

        client.close()
