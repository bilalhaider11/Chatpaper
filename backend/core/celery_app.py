from celery import Celery

from core.config import settings

celery_app = Celery(
    "chatpaper",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["tasks.ingestion_tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
)
