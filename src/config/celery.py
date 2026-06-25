from __future__ import annotations

from celery import Celery
from kombu import Queue

from src.config.settings import settings

celery_app = Celery(
    "doc_extraction_service",
)

celery_app.conf.update(
    broker_url=settings.CELERY_BROKER_URL,
    result_backend=settings.CELERY_RESULT_BACKEND,
    task_default_queue=settings.CELERY_TASK_DEFAULT_QUEUE,
    task_queues=(
        Queue(
            settings.CELERY_TASK_DEFAULT_QUEUE,
        ),
    ),
    task_routes={
        "src.tasks.extraction_tasks.process_invoice": {
            "queue": settings.CELERY_TASK_DEFAULT_QUEUE,
        },
        "src.tasks.extraction_tasks.process_purchase_order": {
            "queue": settings.CELERY_TASK_DEFAULT_QUEUE,
        },
    },
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    result_expires=3600,
)

celery_app.autodiscover_tasks(
    [
        "src.tasks",
    ],
)
