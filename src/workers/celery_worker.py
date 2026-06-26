from __future__ import annotations

import logging

from celery.signals import worker_process_init, worker_ready

from src.config.celery import celery_app

import src.tasks.extraction_tasks  # noqa: F401

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)

logger = logging.getLogger(
    "extraction.worker",
)


@worker_process_init.connect
def _reset_db_engine_after_fork(
    **_: object,
) -> None:
    from src.data.clients.postgres_client import (
        reset_engine,
    )

    reset_engine()


@worker_ready.connect
def _resume_gmail_monitoring_on_startup(
    **_: object,
) -> None:
    from src.core.services.gmail_startup_service import (
        resume_active_monitoring,
    )
    from src.utils.celery_async import (
        run_async_in_worker,
    )

    try:
        run_async_in_worker(
            resume_active_monitoring,
        )
        logger.info(
            "Gmail monitoring startup resume completed.",
        )
    except Exception:
        logger.exception(
            "Gmail monitoring startup resume failed.",
        )


__all__ = [
    "celery_app",
]
