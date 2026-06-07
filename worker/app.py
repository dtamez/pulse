import os

from celery import Celery

from core.config import settings

celery_app = Celery(
    "pulse", broker=settings.REDIS_URL, backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.task_default_queue = "pulse"
celery_app.autodiscover_tasks(["worker"])
celery_app.conf.update(
    worker_send_task_events=True,
    task_send_sent_event=True,
)
