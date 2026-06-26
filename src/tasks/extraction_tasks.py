from __future__ import annotations

import logging
import time
import traceback
from typing import Any
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.config.celery import celery_app
from src.config.settings import settings
from src.core.services.gmail_notification_service import (
    GmailNotificationService,
)
from src.core.services.purchase_order_service import (
    PurchaseOrderService,
)
from src.utils.celery_async import run_async_in_worker
from src.utils.gmail_notification_coordinator import (
    release_gmail_worker,
    resolve_target_history_id,
    should_enqueue_gmail_worker,
)
from src.utils.redis_lock import mailbox_processing_lock
from src.utils.transient_errors import (
    get_retry_countdown_for_error,
    is_permanent_business_error,
    is_transient_error,
)

logger = logging.getLogger(
    "extraction.tasks",
)


def _retry_countdown(
    retries: int,
) -> int:
    return settings.CELERY_TASK_RETRY_BACKOFF_SECONDS * (
        2**retries
    )


def _log_task_received(
    task_name: str,
    task_id: str,
    **context: object,
) -> float:
    logger.info(
        "Task received name=%s task_id=%s context=%s",
        task_name,
        task_id,
        context,
    )

    return time.monotonic()


def _log_task_started(
    task_name: str,
    task_id: str,
) -> None:
    logger.info(
        "Task started name=%s task_id=%s",
        task_name,
        task_id,
    )


def _log_task_completed(
    task_name: str,
    task_id: str,
    *,
    started_at: float,
    result: dict[str, Any],
) -> None:
    duration = time.monotonic() - started_at
    logger.info(
        "Task completed name=%s task_id=%s duration=%.2fs result=%s",
        task_name,
        task_id,
        duration,
        result,
    )


def _log_task_failed(
    task_name: str,
    task_id: str,
    *,
    started_at: float,
    error: BaseException,
) -> None:
    duration = time.monotonic() - started_at
    logger.error(
        "Task failed name=%s task_id=%s duration=%.2fs reason=%s",
        task_name,
        task_id,
        duration,
        error,
    )
    traceback.print_exc()


def _log_task_retried(
    task_name: str,
    task_id: str,
    *,
    retries: int,
    error: BaseException,
) -> None:
    logger.warning(
        "Task retried name=%s task_id=%s attempt=%s reason=%s",
        task_name,
        task_id,
        retries + 1,
        error,
    )


def _failure_result(
    *,
    reason: str,
    invoice_id: str | None = None,
) -> dict[str, str | None]:
    return {
        "status": "failed",
        "reason": reason,
        "invoice_id": invoice_id,
    }


async def _run_gmail_invoice_processing(
    session: AsyncSession,
    *,
    email_address: str,
    history_id: int,
    task_id: str = "unknown",
) -> dict[str, str]:
    service = GmailNotificationService(
        session,
    )

    return await service.process_notification(
        email_address=email_address,
        history_id=history_id,
        task_id=task_id,
    )


async def _run_purchase_order_processing(
    session: AsyncSession,
    *,
    file_path: str,
    company_id: UUID,
    uploaded_by: UUID,
) -> dict[str, str]:
    service = PurchaseOrderService(
        session,
    )
    purchase_order, _line_items_saved = (
        await service.process_saved_purchase_order(
            file_path=file_path,
            company_id=company_id,
            uploaded_by=uploaded_by,
        )
    )

    return {
        "status": "completed",
        "purchase_order_id": str(
            purchase_order.id,
        ),
        "po_number": purchase_order.po_number,
        "extraction_status": purchase_order.status.value,
    }


@celery_app.task(
    bind=True,
    name="src.tasks.extraction_tasks.process_invoice",
    max_retries=settings.CELERY_TASK_MAX_RETRIES,
    acks_late=True,
)
def process_invoice(
    self,
    email_address: str,
    history_id: int,
) -> dict[str, str | None]:
    task_name = "process_invoice"
    started_at = _log_task_received(
        task_name,
        self.request.id,
        email_address=email_address,
        history_id=history_id,
    )

    try:
        _log_task_started(
            task_name,
            self.request.id,
        )
        target_history_id = resolve_target_history_id(
            email_address,
            history_id,
        )
        print(
            f"[celery] {task_name} started "
            f"task_id={self.request.id} "
            f"email={email_address} "
            f"history_id={target_history_id}",
        )

        with mailbox_processing_lock(
            email_address,
        ):
            _task_id = self.request.id or "unknown"
            result = run_async_in_worker(
                lambda session: _run_gmail_invoice_processing(
                    session,
                    email_address=email_address,
                    history_id=target_history_id,
                    task_id=_task_id,
                ),
            )

        follow_up_history_id = release_gmail_worker(
            email_address,
        )

        if follow_up_history_id is not None:
            if should_enqueue_gmail_worker(
                email_address,
                follow_up_history_id,
            ):
                process_invoice.delay(
                    email_address=email_address,
                    history_id=follow_up_history_id,
                )

        _log_task_completed(
            task_name,
            self.request.id,
            started_at=started_at,
            result=result,
        )
        print(
            f"[celery] {task_name} completed "
            f"task_id={self.request.id} "
            f"result={result}",
        )

        return {
            "status": result.get(
                "status",
                "processed",
            ),
            "task_id": self.request.id,
            "invoice_id": None,
            "extraction_status": result.get(
                "status",
            ),
            "messages_processed": result.get(
                "messages_processed",
            ),
        }
    except Exception as error:
        if is_permanent_business_error(
            error,
        ):
            release_gmail_worker(
                email_address,
            )
            _log_task_failed(
                task_name,
                self.request.id,
                started_at=started_at,
                error=error,
            )
            print(
                f"[celery] {task_name} failed "
                f"(permanent) task_id={self.request.id} "
                f"error={error}",
            )

            reason = str(
                error,
            )

            if isinstance(
                error,
                HTTPException,
            ):
                reason = str(
                    error.detail,
                )

            return _failure_result(
                reason=reason,
            )

        if (
            is_transient_error(
                error,
            )
            and self.request.retries
            < settings.CELERY_TASK_MAX_RETRIES
        ):
            _log_task_retried(
                task_name,
                self.request.id,
                retries=self.request.retries,
                error=error,
            )
            print(
                f"[celery] {task_name} retrying "
                f"task_id={self.request.id} "
                f"attempt={self.request.retries + 1} "
                f"error={error}",
            )
            raise self.retry(
                exc=error,
                countdown=get_retry_countdown_for_error(
                    error,
                    retries=self.request.retries,
                    default_backoff_seconds=_retry_countdown(
                        self.request.retries,
                    ),
                ),
            ) from error

        release_gmail_worker(
            email_address,
        )
        _log_task_failed(
            task_name,
            self.request.id,
            started_at=started_at,
            error=error,
        )
        print(
            f"[celery] {task_name} failed "
            f"task_id={self.request.id} "
            f"error={error}",
        )
        raise


@celery_app.task(
    bind=True,
    name="src.tasks.extraction_tasks.process_purchase_order",
    max_retries=settings.CELERY_TASK_MAX_RETRIES,
    acks_late=True,
)
def process_purchase_order(
    self,
    file_path: str,
    company_id: str,
    uploaded_by: str,
) -> dict[str, str | None]:
    task_name = "process_purchase_order"
    started_at = _log_task_received(
        task_name,
        self.request.id,
        file_path=file_path,
        company_id=company_id,
        uploaded_by=uploaded_by,
    )

    try:
        _log_task_started(
            task_name,
            self.request.id,
        )

        result = run_async_in_worker(
            lambda session: _run_purchase_order_processing(
                session,
                file_path=file_path,
                company_id=UUID(
                    company_id,
                ),
                uploaded_by=UUID(
                    uploaded_by,
                ),
            ),
        )

        _log_task_completed(
            task_name,
            self.request.id,
            started_at=started_at,
            result=result,
        )

        return {
            "status": result["status"],
            "task_id": self.request.id,
            "invoice_id": None,
            "purchase_order_id": result[
                "purchase_order_id"
            ],
            "extraction_status": result[
                "extraction_status"
            ],
        }
    except Exception as error:
        if is_permanent_business_error(
            error,
        ):
            _log_task_failed(
                task_name,
                self.request.id,
                started_at=started_at,
                error=error,
            )

            reason = str(
                error,
            )

            if isinstance(
                error,
                HTTPException,
            ):
                reason = str(
                    error.detail,
                )

            return _failure_result(
                reason=reason,
            )

        if (
            is_transient_error(
                error,
            )
            and self.request.retries
            < settings.CELERY_TASK_MAX_RETRIES
        ):
            _log_task_retried(
                task_name,
                self.request.id,
                retries=self.request.retries,
                error=error,
            )
            raise self.retry(
                exc=error,
                countdown=get_retry_countdown_for_error(
                    error,
                    retries=self.request.retries,
                    default_backoff_seconds=_retry_countdown(
                        self.request.retries,
                    ),
                ),
            ) from error

        _log_task_failed(
            task_name,
            self.request.id,
            started_at=started_at,
            error=error,
        )
        raise
