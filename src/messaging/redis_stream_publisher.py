from __future__ import annotations

import logging
from contextvars import ContextVar
from datetime import UTC, datetime
from uuid import UUID

import redis

from src.config.settings import settings
from src.messaging.extraction_events import (
    EXTRACTION_EVENT_COMPLETED,
    EXTRACTION_EVENT_VERSION,
)

logger = logging.getLogger(
    "extraction.messaging",
)


class RedisStreamPublisher:
    def __init__(
        self,
    ) -> None:
        self._client: redis.Redis | None = None

    def _get_client(
        self,
    ) -> redis.Redis:
        if self._client is None:
            self._client = redis.Redis(
                host=settings.REDIS_HOST,
                port=settings.REDIS_PORT,
                db=settings.REDIS_DB,
                decode_responses=True,
            )

        return self._client

    def publish_extraction_completed(
        self,
        invoice_id: UUID,
        *,
        occurred_at: datetime | None = None,
    ) -> str:
        timestamp = occurred_at or datetime.now(
            UTC,
        )
        event_payload = {
            "version": str(
                EXTRACTION_EVENT_VERSION,
            ),
            "event_type": EXTRACTION_EVENT_COMPLETED,
            "invoice_id": str(
                invoice_id,
            ),
            "occurred_at": timestamp.isoformat(),
        }

        message_id = self._get_client().xadd(
            settings.REDIS_STREAM_NAME,
            event_payload,
        )

        logger.info(
            "Redis event published stream=%s event_type=%s "
            "invoice_id=%s message_id=%s occurred_at=%s",
            settings.REDIS_STREAM_NAME,
            EXTRACTION_EVENT_COMPLETED,
            invoice_id,
            message_id,
            event_payload[
                "occurred_at"
            ],
        )

        return str(
            message_id,
        )

    def close(
        self,
    ) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None


_publisher: RedisStreamPublisher | None = None


def get_redis_stream_publisher() -> RedisStreamPublisher:
    global _publisher

    if _publisher is None:
        _publisher = RedisStreamPublisher()

    return _publisher

_pending_extraction_events: ContextVar[
    list[UUID] | None
] = ContextVar(
    "pending_extraction_events",
    default=None,
)


def _get_pending_events() -> list[UUID]:
    pending = _pending_extraction_events.get()

    if pending is None:
        pending = []
        _pending_extraction_events.set(
            pending,
        )

    return pending


def queue_extraction_completed(
    invoice_id: UUID,
) -> None:
    pending = _get_pending_events()

    if invoice_id not in pending:
        pending.append(
            invoice_id,
        )


def clear_extraction_event_buffer() -> None:
    _pending_extraction_events.set(
        [],
    )


def flush_extraction_events() -> None:
    pending = _get_pending_events()

    if not pending:
        return

    publisher = get_redis_stream_publisher()
    failed_invoice_ids: list[UUID] = []

    for invoice_id in pending:
        logger.info(
            "Extraction completed invoice_id=%s event_type=%s",
            invoice_id,
            EXTRACTION_EVENT_COMPLETED,
        )

        try:
            publisher.publish_extraction_completed(
                invoice_id,
            )
        except Exception:
            logger.exception(
                "Redis publish failed stream=%s event_type=%s "
                "invoice_id=%s",
                settings.REDIS_STREAM_NAME,
                EXTRACTION_EVENT_COMPLETED,
                invoice_id,
            )
            failed_invoice_ids.append(
                invoice_id,
            )

    _pending_extraction_events.set(
        [],
    )

    if failed_invoice_ids:
        raise RuntimeError(
            "Failed to publish extraction events for invoices: "
            f"{failed_invoice_ids}",
        )
