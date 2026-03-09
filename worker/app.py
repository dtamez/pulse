import os

from celery import Celery

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
celery_app = Celery("pulse", broker=f"{redis_url}/0", backend=f"{redis_url}/1")

celery_app.conf.task_default_queue = "pulse"
celery_app.autodiscover_tasks(["worker"])
