from __future__ import annotations

from src.messaging.redis_stream_publisher import (
    clear_extraction_event_buffer,
    flush_extraction_events,
)


def publish_committed_extraction_events() -> None:
    flush_extraction_events()


def discard_pending_extraction_events() -> None:
    clear_extraction_event_buffer()
