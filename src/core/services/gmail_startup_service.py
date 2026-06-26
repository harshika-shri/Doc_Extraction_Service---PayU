from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.data.repositories.gmail_monitoring_repo import (
    GmailMonitoringRepository,
)
from src.handlers.gmail.gmail_watch import (
    GmailWatch,
)
from src.tasks.extraction_tasks import (
    process_invoice,
)
from src.utils.gmail_history_cache import (
    cache_last_processed_history_id,
    set_monitoring_active,
)
from src.utils.gmail_notification_coordinator import (
    should_enqueue_gmail_worker,
    update_pending_history_id,
)

logger = logging.getLogger(
    "gmail.startup",
)


async def resume_active_monitoring(
    session: AsyncSession,
) -> None:
    repo = GmailMonitoringRepository(
        session,
    )
    active_states = await repo.list_active()

    if not active_states:
        logger.info(
            "No active Gmail monitoring mailboxes to resume.",
        )
        return

    watch = GmailWatch()

    for state in active_states:
        email_address = state.email_address

        cache_last_processed_history_id(
            email_address,
            state.last_processed_history_id,
        )
        set_monitoring_active(
            email_address,
            active=True,
        )

        try:
            watch_response = watch.start_watch()
            watch_history_id = int(
                watch_response[
                    "history_id"
                ],
            )
        except Exception:
            logger.exception(
                "Failed to renew Gmail watch for %s",
                email_address,
            )
            continue

        target_history_id = update_pending_history_id(
            email_address,
            watch_history_id,
        )

        if not should_enqueue_gmail_worker(
            email_address,
            target_history_id,
        ):
            logger.info(
                "Skipped startup enqueue for %s "
                "(worker already active or stale).",
                email_address,
            )
            continue

        task = process_invoice.delay(
            email_address=email_address,
            history_id=target_history_id,
        )

        logger.info(
            "Resumed Gmail monitoring for %s: "
            "stored_history_id=%s, watch_history_id=%s, "
            "task_id=%s",
            email_address,
            state.last_processed_history_id,
            watch_history_id,
            task.id,
        )
